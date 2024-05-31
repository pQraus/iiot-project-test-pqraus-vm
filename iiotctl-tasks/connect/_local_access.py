import base64
from pathlib import Path

from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _teleport as teleport
from .._utils._common import Command
from .._utils._config import (BOX_NAME, DEP_KUBECTL, DEP_TALOSCTL, DEP_TCTL,
                              DEP_TSH, ENCODING, K8S_CONFIG_USER,
                              TALOS_CONFIG_PROJECT)


def _get_teleport_key_cert(ttl: str):
    teleport_cert, teleport_key = teleport.create_local_cert(ttl)
    cert_b64 = base64.b64encode(teleport_cert)
    key_b64 = base64.b64encode(teleport_key)
    return cert_b64, key_b64


@check.dependency(*DEP_TALOSCTL)
@check.dependency(*DEP_TSH)
@check.dependency(*DEP_TCTL)
def configure_local_talos_access(machine_ip: str, ttl: str, talosconfig: str):

    check.ip(machine_ip)

    print("Create a teleport certificate to access the machine's talos api in local network ...")
    teleport.login()
    cert_b64, key_b64 = _get_teleport_key_cert(ttl)
    Command.check_output(cmd=["tsh", "logout"])

    talosconfig: Path = Path(talosconfig)

    # create a new context name for the talosconfig:
    new_context = f"{BOX_NAME}-local-crt"
    # get the root ca from the /machine/talosconfig-teleport file of the project
    talosconfig: Path = Path(talosconfig)
    with common.patch_yaml_file(file_path=talosconfig) as config:
        root_ca: str = config["contexts"][BOX_NAME]["ca"]

    context_values = {
        'endpoints': [f'{machine_ip}:51001'],
        'nodes': [machine_ip],
        'ca': root_ca.replace('\n', ''),
        'crt': cert_b64.decode(ENCODING),
        'key': key_b64.decode(ENCODING),
    }

    print(f"Insert / Update context with name '{new_context}' in {talosconfig.absolute()} ...")

    # add local talos context into talosconfig
    with common.patch_yaml_file(file_path=talosconfig) as config:
        config["contexts"][new_context] = context_values

    # set talos current-context
    Command.check_output(cmd=["talosctl", "config", "context", new_context, "--talosconfig", talosconfig])


@check.config_parameter("LOCAL_K8S_ACCESS", True)
@check.dependency(*DEP_KUBECTL)
@check.dependency(*DEP_TSH)
@check.dependency(*DEP_TCTL)
def configure_local_k8s_access(machine_ip: str, ttl: str, kubeconfig: str):

    check.ip(machine_ip)

    print("Create a teleport certificate to access the machine's k8s api in local network ...")
    teleport.login()
    cert_b64, key_b64 = _get_teleport_key_cert(ttl)
    Command.check_output(["tsh", "logout"])

    # get the root ca from the /machine/talosconfig-teleport file of the project
    root_ca = Command.check_output(cmd=["yq", f".contexts.{BOX_NAME}.ca", TALOS_CONFIG_PROJECT])

    user = BOX_NAME + "-local-crt"
    print(f"Insert / Update cluster, context, user with name '{user}' in {K8S_CONFIG_USER} ...")
    kubeconfig = Path(kubeconfig)
    config = ["kubectl", "config", "--kubeconfig", kubeconfig]

    # add local k8s cluster into kubeconfig
    Command.check_output(config + ["set-cluster", user, "--server", "https://" + machine_ip + ":51011"])
    Command.check_output(config + ["set", f"clusters.{user}.certificate-authority-data", root_ca])

    # add local k8s context into kubeconfig
    Command.check_output(config + ["set-context", user, "--cluster", user, "--user", user])

    # add local k8s user into kubeconfig
    Command.check_output(config + ["set-credentials", user])
    Command.check_output(config + ["set", f'users.{user}.client-certificate-data', cert_b64.decode()])
    Command.check_output(config + ["set", f'users.{user}.client-key-data', key_b64.decode()])

    # set kube current-context
    Command.check_output(config + ["use-context", user])
