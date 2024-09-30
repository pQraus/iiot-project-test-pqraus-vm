from pathlib import Path

from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _kubectl as kubectl
from .._utils import _teleport as teleport
from .._utils._common import Command
from .._utils._config import (BOX_NAME, DEP_KUBECTL, DEP_TALOSCTL, DEP_TSH,
                              TELEPORT_PROXY_URL)
from .._utils._constants import TALOS_CONFIG_PROJECT
from ._local_access import (configure_local_k8s_access,
                            configure_local_talos_access)


@check.dependency(*DEP_TSH)
@check.dependency(*DEP_TALOSCTL)
def connect_talos(local_port: int, machine_ip: str | None, ttl: str, talosconfig: str):

    if machine_ip is not None:
        configure_local_talos_access(machine_ip, ttl, talosconfig)
        return

    teleport.login(TELEPORT_PROXY_URL)

    print(
        f"Try to connect to the talos-api of {BOX_NAME} via local port: {local_port} ..."
    )

    teleport_app_name = f"talos-{BOX_NAME}"
    teleport.login_app(teleport_app_name)

    talosconfig: Path = Path(talosconfig)

    if not talosconfig.exists():
        talos_config_dir = talosconfig.parent
        talos_config_dir.mkdir(exist_ok=True)
        with open(talosconfig, "w") as f:
            f.write("{}")

    # 1. delete the context to ensure that the right config (from the repo) is used
    with common.patch_yaml_file(file_path=talosconfig) as config:
        contexts = config.get("contexts")
        if contexts is not None:
            contexts.pop(BOX_NAME, None)
    # 2. add the context from the repo into the config
    Command.check_output(cmd=["talosctl", "config", "merge", TALOS_CONFIG_PROJECT])
    Command.check_output(cmd=["talosctl", "config", "endpoint", f"127.0.0.1:{local_port}"])
    print(f"Set global talos context to: {BOX_NAME}")
    print()

    teleport.proxy_app(teleport_app_name, local_port)


@check.dependency(*DEP_TSH)
@check.dependency(*DEP_KUBECTL)
def connect_k8s(machine_ip: str | None, ttl: str, kubeconfig: str):

    if machine_ip is not None:
        configure_local_k8s_access(machine_ip, ttl, kubeconfig)
        return

    teleport.login(TELEPORT_PROXY_URL)
    teleport.login_k8s(BOX_NAME)

    check.k8s_connection(BOX_NAME, kubeconfig)

    k8s_context = kubectl.get_current_context(kubeconfig)
    k8s_context = k8s_context.replace("\n", "")
    print()
    print(f"Set k8s-context to: '{k8s_context}'")


@check.dependency(*DEP_KUBECTL)
@check.dependency(*DEP_TSH)
def connect_argo(local_port: int, local_address: str, use_current_context: bool, kubeconfig: str):

    if use_current_context is False:
        teleport.login(TELEPORT_PROXY_URL)
        teleport.login_k8s(BOX_NAME)

    check.k8s_connection(BOX_NAME, kubeconfig)

    print()
    link = f"http://{local_address}:{local_port}/argocd"
    print(f"Argo is available at: [link={link}]{link}[/link]")

    kubectl.port_forward("services/argocd-server", "argocd", f"{local_port}:80", kubeconfig, address=local_address)


@check.dependency(*DEP_KUBECTL)
@check.dependency(*DEP_TSH)
def connect_traefik(local_port: int, local_address: str, use_current_context: bool, kubeconfig: str):
    LOCAL_ADDRESSES = ('localhost', '127.0.0.1', '0.0.0.0')

    if use_current_context is False:
        teleport.login(TELEPORT_PROXY_URL)
        teleport.login_k8s(BOX_NAME)

    check.k8s_connection(BOX_NAME, kubeconfig)

    print()
    if local_address in LOCAL_ADDRESSES:
        print("Access apps behind Traefik via:")
        print(f"  - path: 'http://{local_address}:{local_port}" + "/{APP_PATH}'")
        print(f"  - subdomain at: 'http://{{APP_SUBDOMAIN}}.localhost:{local_port}'")

        print()
        link = f"http://traefik.localhost:{local_port}/dashboard/#/"
        print(f"Traefik Dashboard is available at: [link={link}]{link}[/link]")
    else:
        print("Access apps behind Traefik via:")
        print(f"  - path: 'http://{local_address}:{local_port}" + "/{APP_PATH}'")

    kubectl.port_forward("services/traefik", "traefik", f"{local_port}:80", kubeconfig, address=local_address)
