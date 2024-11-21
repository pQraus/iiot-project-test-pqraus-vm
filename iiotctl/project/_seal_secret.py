from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import load_pem_x509_certificate
from cryptography.x509.oid import NameOID
from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _kubectl as kubectl
from .._utils._common import Command, TyperAbort, print_error
from .._utils._config import BOX_NAME
from .._utils._constants import (DEP_KUBECTL, DEP_KUBESEAL, K8S_CONFIG_USER,
                                 REPO_ROOT)

APP_DIR = REPO_ROOT / "system-apps/sealed-secrets"
NAMESPACE_FILE = APP_DIR / "argo-template/resources/sealed-secrets-namespace.yaml"
MACHINE_PATCH_INITIAL_MANIFEST = APP_DIR / "machine-patches/_initial-manifests.boot.jq"
MACHINE_PATCH_INITIAL_MANIFEST_TEMP = APP_DIR / "machine-patches/initial-manifests.boot.jq.temp"
MACHINE_PATCH_SEALED_SECRET_KEY = APP_DIR / "machine-patches/sealed-secrets-key.yaml"
PRIVATE_KEY = APP_DIR / "sealing-secret/private-key.key"
PUBLIC_KEY = APP_DIR / "sealing-secret/public-key.crt"


def _check_if_cert_expired(cert_file) -> bool:
    with open(cert_file, "rb") as file:
        cert = load_pem_x509_certificate(file.read())

    now = datetime.now(timezone.utc)
    valid_until = cert.not_valid_after_utc
    time_valid = valid_until - now
    return time_valid.total_seconds() <= 0.0


def _check_if_sealing_possible() -> bool:
    if not PUBLIC_KEY.exists():
        print_error("Sealed-secrets encryption key not set. Use 'iiotctl project seal-secret --init' to initialize")
        return False

    if _check_if_cert_expired(PUBLIC_KEY):
        print_error(
            "Sealed-secrets encryption key expired. Use 'iiotctl project seal-secret --init' to create a new one"
        )
        return False

    return True


def _gen_key_and_cert():
    root_key = rsa.generate_private_key(public_exponent=65_537, key_size=4096)
    root_key_serialized = root_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    options = [x509.NameAttribute(NameOID.COMMON_NAME, "sealed-secret"),
               x509.NameAttribute(NameOID.ORGANIZATION_NAME, "sealed-secret")]
    subject = issuer = x509.Name(options)
    root_cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        root_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.now(timezone.utc)
    ).not_valid_after(
        datetime.now(timezone.utc) + timedelta(days=365)
    ).add_extension(
        x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()),
        critical=False
    ).add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),
        critical=False
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None),
        critical=True,
    ).sign(root_key, hashes.SHA256())

    root_cert_serialized = root_cert.public_bytes(serialization.Encoding.PEM)
    return root_cert_serialized.decode(), root_key_serialized.decode()


@contextmanager
def _create_key() -> Generator[tuple[str, str], Any, Any]:
    PUBLIC_KEY.parent.mkdir(parents=True, exist_ok=True)
    public_key, private_key = _gen_key_and_cert()

    with open(PUBLIC_KEY, "w") as file:
        file.write(public_key)

    with open(PRIVATE_KEY, "w") as file:
        file.write(private_key)

    yield public_key, private_key

    PRIVATE_KEY.unlink()


def _create_secret(bootstrap: bool = False) -> str:
    name = "repo-key-bootstrap" if bootstrap else _gen_secret_name()

    if not MACHINE_PATCH_SEALED_SECRET_KEY.exists():
        raise TyperAbort(f"Missing sealed secrets config file: {MACHINE_PATCH_SEALED_SECRET_KEY}.")

    with _create_key() as (public_key, private_key):
        with common.patch_yaml_file(file_path=MACHINE_PATCH_SEALED_SECRET_KEY) as content:
            content["stringData"]["tls.crt"] = public_key
            content["stringData"]["tls.key"] = private_key
            content["metadata"]["name"] = name
            yaml_content = common.dump_yaml(content)

    return yaml_content


def _gen_secret_name() -> str:
    current_names = kubectl.fetch(
        resource="secrets", format="jsonpath='{.items[*].metadata.name}'", kubeconfig=K8S_CONFIG_USER
    )

    name = "repo-key-" + str(uuid4())[:8]
    if name not in current_names.split(" "):
        return name
    else:
        return _gen_secret_name()


def _push_new_key_to_k8s():
    check.k8s_connection(BOX_NAME, K8S_CONFIG_USER)

    secret = _create_secret()
    with open(MACHINE_PATCH_SEALED_SECRET_KEY, "w") as file:
        file.write(secret)

    kubectl.apply(file=MACHINE_PATCH_SEALED_SECRET_KEY, kubeconfig=K8S_CONFIG_USER)
    kubectl.rollout_restart_deployment(
        deployment="sealed-secrets-controller",
        namespace="sealed-secrets",
        kubeconfig=K8S_CONFIG_USER)

    print("Successfully pushed encryption key to cluster")


def _bootstrap_key():
    secret = _create_secret(bootstrap=True)

    with open(NAMESPACE_FILE) as file:
        namespace = file.read().replace("\"", "'")

    with open(MACHINE_PATCH_INITIAL_MANIFEST_TEMP) as file:
        initial_manifest = file.read()

    initial_manifest = initial_manifest.replace("<namespace>", namespace)
    initial_manifest = initial_manifest.replace("<sealed-secret-init-key>", secret)

    with open(MACHINE_PATCH_INITIAL_MANIFEST, "w") as file:
        file.write(initial_manifest)

    print(f"Successfully patched initial encryption key into: /{MACHINE_PATCH_INITIAL_MANIFEST.relative_to(REPO_ROOT)}")


def _seal_secret(secret_file: str, sealed_secret_file: str):
    Command.check_output(
        cmd=[
            "kubeseal",
            "--cert",
            PUBLIC_KEY,
            "--controller-namespace",
            "sealed-secrets",
            "-f",
            secret_file,
            "-w",
            sealed_secret_file
        ]
    )


@check.dependency(*DEP_KUBESEAL)
@check.dependency(*DEP_KUBECTL)
def seal_secret(
        secret_file: str = "",
        sealed_secret_file: str = "",
        init: bool = False,
        bootstrap: bool = False):

    if init and bootstrap:
        raise TyperAbort("You can't specify both 'init' and 'bootstrap'")

    if init:
        _push_new_key_to_k8s()
        return

    if bootstrap:
        _bootstrap_key()
        return

    if not _check_if_sealing_possible():
        raise TyperAbort()

    if not secret_file and not sealed_secret_file:
        raise TyperAbort("You must provide both the secret-file and the sealed-secret-file")

    _seal_secret(secret_file, sealed_secret_file)
    print("Successfully encrypted secret")
