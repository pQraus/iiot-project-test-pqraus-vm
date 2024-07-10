from collections.abc import Generator
from contextlib import contextmanager
from shutil import copyfile
from typing import Any
from uuid import uuid4

from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _kubectl as kubectl
from .._utils._common import Command, TyperAbort, print_error
from .._utils._config import BOX_NAME, DEP_KUBECTL, DEP_KUBESEAL
from .._utils._constants import K8S_CONFIG_USER, REPO_ROOT

APP_DIR = REPO_ROOT / "system-apps/sealed-secrets"
NAMESPACE_FILE = APP_DIR / "argo-template/resources/sealed-secrets-namespace.yaml"
MACHINE_PATCH_INITIAL_MANIFEST = APP_DIR / "machine-patches/_initial-manifests.boot.jq"
MACHINE_PATCH_SEALED_SECRET_KEY = APP_DIR / "machine-patches/sealed-secrets-key.yaml"
MACHINE_PATCH_SEALED_SECRET_KEY_TEMP = APP_DIR / "machine-patches/sealed-secrets-key.yaml.temp"
PRIVATE_KEY = APP_DIR / "sealing-secret/private-key.key"
PUBLIC_KEY = APP_DIR / "sealing-secret/public-key.crt"


def _check_if_cert_expired(cert_file) -> bool:
    return not Command.check(
        cmd=[
            "openssl",
            "x509",
            "-checkend",
            "0",
            "-noout",
            "-in",
            cert_file
        ]
    )


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


@contextmanager
def _create_key() -> Generator[tuple[str, str], Any, Any]:
    if not MACHINE_PATCH_SEALED_SECRET_KEY.exists():
        copyfile(MACHINE_PATCH_SEALED_SECRET_KEY_TEMP, MACHINE_PATCH_SEALED_SECRET_KEY)

    PUBLIC_KEY.parent.mkdir(parents=True, exist_ok=True)
    Command.check_output(
        cmd=[
            "openssl",
            "req",
            "-x509",
            "-days=365",
            "-nodes",
            "-newkey=rsa:4096",
            f"-keyout={PRIVATE_KEY}",
            f"-out={PUBLIC_KEY}",
            "-subj=/CN=sealed-secret/O=sealed-secret"
        ]
    )

    with open(PUBLIC_KEY) as file:
        public_key = file.read()

    with open(PRIVATE_KEY) as file:
        private_key = file.read()

    yield public_key, private_key

    PRIVATE_KEY.unlink()


def _create_secret(bootstrap: bool = False) -> str:
    if bootstrap:
        name = "repo-key-bootstrap"
    else:
        name = _gen_secret_name()

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

    kubectl.apply(file=MACHINE_PATCH_SEALED_SECRET_KEY)
    kubectl.rollout_restart_deployment(deployment="sealed-secrets-controller", namespace="sealed-secrets")

    print("Successfully pushed encryption key to cluster")


def _bootstrap_key():
    secret = _create_secret(bootstrap=True)

    with open(NAMESPACE_FILE) as file:
        namespace = file.read().replace("\"", "'")

    with open(MACHINE_PATCH_INITIAL_MANIFEST) as file:
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
