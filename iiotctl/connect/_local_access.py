import base64
import sys
from pathlib import Path

from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _kubectl as kubectl
from .._utils import _talosctl as talosctl
from .._utils import _teleport as teleport
from .._utils._config import BOX_NAME, TELEPORT_PROXY_URL
from .._utils._constants import (DEP_KUBECTL, DEP_TALOSCTL, DEP_TCTL, DEP_TSH,
                                 K8S_CONFIG_USER, TALOS_CONFIG_PROJECT)

ENCODING = sys.stdout.encoding


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
    teleport.login(TELEPORT_PROXY_URL)
    cert_b64, key_b64 = _get_teleport_key_cert(ttl)

    talosconfig: Path = Path(talosconfig)

    # create a new context name for the talosconfig:
    new_context = f"{BOX_NAME}-local-crt"
    # get the root ca from the /machine/talosconfig-teleport file of the project
    with common.patch_yaml_file(file_path=TALOS_CONFIG_PROJECT) as config:
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
    talosctl.config_context_set(new_context, talosconfig=talosconfig)


@check.dependency(*DEP_KUBECTL)
@check.dependency(*DEP_TSH)
@check.dependency(*DEP_TCTL)
def configure_local_k8s_access(machine_ip: str, ttl: str, kubeconfig: str):

    check.ip(machine_ip)

    print("Create a teleport certificate to access the machine's k8s api in local network ...")
    teleport.login(TELEPORT_PROXY_URL)
    cert_b64, key_b64 = _get_teleport_key_cert(ttl)

    # get the root ca from the /machine/talosconfig-teleport file of the project
    with common.patch_yaml_file(file_path=TALOS_CONFIG_PROJECT) as config:
        root_ca: str = config["contexts"][BOX_NAME]["ca"]

    user = BOX_NAME + "-local-crt"
    print(f"Insert / Update cluster, context, user with name '{user}' in {K8S_CONFIG_USER} ...")

    # add local k8s cluster into kubeconfig
    kubectl.config_set_cluster(cluster=user, server="https://" + machine_ip + ":51011", kubeconfig=kubeconfig)
    kubectl.config_set(key=f"clusters.{user}.certificate-authority-data", value=root_ca, kubeconfig=kubeconfig)

    # add local k8s context into kubeconfig
    kubectl.config_set_context(context=user, cluster=user, user=user, kubeconfig=kubeconfig)

    # add local k8s user into kubeconfig
    kubectl.config_set_credentials(credentials=user, kubeconfig=kubeconfig)
    kubectl.config_set(key=f'users.{user}.client-certificate-data', value=cert_b64.decode(), kubeconfig=kubeconfig)
    kubectl.config_set(key=f'users.{user}.client-key-data', value=key_b64.decode(), kubeconfig=kubeconfig)

    # set kube current-context
    kubectl.config_use_context(context=user, kubeconfig=kubeconfig)
