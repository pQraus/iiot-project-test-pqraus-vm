from invoke.tasks import task

from .. import _common as common
from .. import _sealed_secrets
from .._config import DEP_KUBECTL, DEP_KUBESEAL, DEP_YQ


@task(
    optional=[
        "secret_file",
        "sealed_secret_file",
        "init",
        "bootstrap"],
    help={
        "secret_file": "Secret (input) file",
        "sealed_secret_file": "Sealed-secret (output) file",
        "init": "Initialize the sealed secret public encryption key (default: False)",
        "bootstrap": "Create machine-patches before bootstrap (default: False)"
    },
)
@common.check_dependency(*DEP_KUBESEAL)
@common.check_dependency(*DEP_KUBECTL)
@common.check_dependency(*DEP_YQ)
def seal_secret(
        c,
        secret_file: str = "",
        sealed_secret_file: str = "",
        init: bool = False,
        bootstrap: bool = False):
    """
    Seal a secret

    EXAMPLES:

    Call with arguments '--secret-file' and '--sealed-secret-file' to seal a secret
    >>> invoke seal-secret --secret-file path/to/secret.yaml --sealed-secret-file path/to/sealed-secret.yaml

    Call with argument '--bootstrap' to create the machine patches before booting the box
    >>> invoke seal-secret --bootstrap

    Call with argument '--init' to initialize or renew the encryption key on a running box (needs k8s connection)
    >>> invoke seal-secret --init
    """

    if init and bootstrap:
        print("You can't specify both 'init' and 'bootstrap'")
        exit(1)

    if init:
        _sealed_secrets.push_new_key_to_k8s()
        exit(0)

    if bootstrap:
        _sealed_secrets.bootstrap()
        exit(0)

    if not _sealed_secrets.check_if_sealing_possible():
        exit(1)

    if not secret_file and not sealed_secret_file:
        print("You must provider both the secret-file and the sealed-secret-file")
        exit(1)

    _sealed_secrets.seal_secret(secret_file, sealed_secret_file)
    print("Successfully encrypted secret")
