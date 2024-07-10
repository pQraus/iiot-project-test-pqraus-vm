from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils._common import Command, TyperAbort
from .._utils._config import BOX_NAME, DEP_TSH
from .._utils._constants import K8S_CONFIG_USER, TALOS_CONFIG_USER


@check.dependency(*DEP_TSH)
def unset_k8s_context():
    if not K8S_CONFIG_USER.exists():
        raise TyperAbort(f"Kube config doesn't exist at: {K8S_CONFIG_USER}")

    with common.patch_yaml_file(file_path=K8S_CONFIG_USER) as config:
        k8s_context = config.get("current-context")
        if k8s_context is None:
            return

        if BOX_NAME == k8s_context:
            print("Unset global k8s context")
            config["current-context"] = ""


@check.dependency(*DEP_TSH)
def unset_talos_context():
    if not TALOS_CONFIG_USER.exists():
        raise TyperAbort(f"Talos config doesn't exist at: {TALOS_CONFIG_USER}")

    with common.patch_yaml_file(file_path=TALOS_CONFIG_USER) as config:
        talos_context = config.get("context")
        if talos_context is None:
            return

        if BOX_NAME == talos_context:
            print("Unset global talos context")
            config["context"] = ""


@check.dependency(*DEP_TSH)
def teleport_logout():
    Command.check_output(["tsh", "logout"])
    print("Disconnected teleport")
