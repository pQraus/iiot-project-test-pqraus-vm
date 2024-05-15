import subprocess as sp
from collections.abc import Generator
from contextlib import contextmanager
from shutil import copyfile
from typing import Any
from uuid import uuid4

from ._common import check_k8s_connection
from ._config import REPO_ROOT

APP_DIR = REPO_ROOT / "system-apps/sealed-secrets"
NAMESPACE_FILE = APP_DIR / "argo-template/resources/sealed-secrets-namespace.yaml"
MACHINE_PATCH_INITIAL_MANIFEST = APP_DIR / "machine-patches/_initial-manifests.boot.jq"
MACHINE_PATCH_SEALED_SECRET_KEY = APP_DIR / "machine-patches/sealed-secrets-key.yaml"
MACHINE_PATCH_SEALED_SECRET_KEY_TEMP = APP_DIR / "machine-patches/sealed-secrets-key.yaml.temp"
PRIVATE_KEY = APP_DIR / "sealing-secret/private-key.key"
PUBLIC_KEY = APP_DIR / "sealing-secret/public-key.crt"


def _check_if_cert_expired(cert_file) -> bool:
    return bool(sp.call(
        [
            "openssl",
            "x509",
            "-checkend",
            "0",
            "-noout",
            "-in",
            cert_file],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL))


def check_if_sealing_possible() -> bool:
    if not PUBLIC_KEY.exists():
        print("Sealed-secrets encryption key not set. Use 'invoke seal-secret --init' to initialize")
        return False

    if _check_if_cert_expired(PUBLIC_KEY):
        print("Sealed-secrets encryption key expired. Use 'invoke seal-secret --init' to create a new one")
        return False

    return True


@contextmanager
def _create_key() -> Generator[tuple[str, str], Any, Any]:
    if not MACHINE_PATCH_SEALED_SECRET_KEY.exists():
        copyfile(MACHINE_PATCH_SEALED_SECRET_KEY_TEMP, MACHINE_PATCH_SEALED_SECRET_KEY)

    PUBLIC_KEY.parent.mkdir(parents=True, exist_ok=True)
    completed_process = sp.run(
        [
            "openssl",
            "req",
            "-x509",
            "-days=365",
            "-nodes",
            "-newkey=rsa:4096",
            f"-keyout={PRIVATE_KEY}",
            f"-out={PUBLIC_KEY}",
            "-subj=/CN=sealed-secret/O=sealed-secret"],
        capture_output=True,
        text=True
        )

    if completed_process.returncode != 0:
        print(completed_process.stderr)
        exit(1)

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
        sp.check_output(["yq", f'.stringData."tls.crt" = "{public_key}"', "-i", MACHINE_PATCH_SEALED_SECRET_KEY])
        sp.check_output(["yq", f'.stringData."tls.key" = "{private_key}"', "-i", MACHINE_PATCH_SEALED_SECRET_KEY])
        sp.check_output(["yq", f'.metadata."name" = "{name}"', "-i", MACHINE_PATCH_SEALED_SECRET_KEY])
    with open(MACHINE_PATCH_SEALED_SECRET_KEY) as file:
        return file.read()


def _gen_secret_name() -> str:
    current_names = sp.check_output(
        [
            "kubectl",
            "-n",
            "sealed-secrets",
            "get",
            "secrets",
            "-o",
            "jsonpath='{.items[*].metadata.name}'"],
        text=True).split(" ")

    name = "repo-key-" + str(uuid4())[:8]
    if name not in current_names:
        return name
    else:
        return _gen_secret_name()


def push_new_key_to_k8s():
    if not check_k8s_connection():
        print("Make sure you are connected to the k8s cluster")
        exit(1)

    secret = _create_secret()
    with open(MACHINE_PATCH_SEALED_SECRET_KEY, "w") as file:
        file.write(secret)

    sp.check_output(["kubectl", "apply", f"-f={MACHINE_PATCH_SEALED_SECRET_KEY}"])
    sp.check_output([
        "kubectl",
        "-n",
        "sealed-secrets",
        "rollout",
        "restart",
        "deployment",
        "sealed-secrets-controller"])

    print("Successfully pushed encryption key to cluster")


def bootstrap():
    secret = _create_secret(bootstrap=True)

    with open(NAMESPACE_FILE) as file:
        namespace = file.read().replace("\"", "\\\"")

    with open(MACHINE_PATCH_INITIAL_MANIFEST) as file:
        initial_manifest = file.read()

    initial_manifest = initial_manifest.replace("<namespace>", namespace)
    initial_manifest = initial_manifest.replace("<sealed-secret-init-key>", secret)

    with open(MACHINE_PATCH_INITIAL_MANIFEST, "w") as file:
        file.write(initial_manifest)

    print(f"Successfully patched initial encryption key into {MACHINE_PATCH_INITIAL_MANIFEST}")


def seal_secret(secret_file: str, sealed_secret_file: str):
    sp.check_output([
        "kubeseal",
        "--cert",
        PUBLIC_KEY,
        "--controller-namespace",
        "sealed-secrets",
        "-f",
        secret_file,
        "-w",
        sealed_secret_file
    ])
