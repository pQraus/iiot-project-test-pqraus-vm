import json
import subprocess as sp
from time import sleep

from invoke import task

from .. import _common as common
from .. import _teleport as teleport
from .._config import (BOX_NAME, DEP_KUBECTL, DEP_TALOSCTL, DEP_TSH, DEP_YQ,
                       ENCODING, K8S_CONFIG_USER, TALOS_CONFIG_PROJECT,
                       TALOS_CONFIG_USER)


@task(
    optional=["local_port"],
    help={
        "local_port": "local port which should be used to reach the talos api (default: 50000)",
        "switch_context": "switch the (global) talos context to the defined context from the repo"
    },
)
@common.check_dependency(*DEP_TSH)
@common.check_dependency(*DEP_YQ)
@common.check_dependency(*DEP_TALOSCTL)
def connect_talos(c, local_port=50000, switch_context=True):
    """
    connect to the talos-api via teleport; you are connected only as long as the command is running

    EXAMPLES:

    Call without optional arguments to connect to talos api via default teleport cluster:
    >>> invoke connect-talos

        While the command runs in one console you can interact with the talos api via talosctl in another.
    """

    teleport.login()

    print(
        f"Try to connect to the talos-api of {BOX_NAME} via local port: {local_port} ..."
    )

    teleport_app_name = f"talos-{BOX_NAME}"
    teleport.login_app(teleport_app_name)
    print()

    if switch_context and not TALOS_CONFIG_USER.exists():
        talos_config_dir = TALOS_CONFIG_USER.parent
        talos_config_dir.mkdir(exist_ok=True)
        with open(TALOS_CONFIG_USER, "w") as f:
            f.write("{}")

    if switch_context:
        # 1. delete the context to ensure that the right config (from the repo) is used
        # yq doesn't support '-symbol escaping
        sp.check_output(["yq", f'del(.contexts."{BOX_NAME}")', "-i", TALOS_CONFIG_USER])
        # 2. add the context from the repo into the config
        sp.check_output(["talosctl", "config", "merge", TALOS_CONFIG_PROJECT])
        print(f"Set global talos context to: {BOX_NAME}")
        print()

    teleport.proxy_app(teleport_app_name, local_port)


@task(
    help={
        "local_port": "local port where argo can be reached",
        "use_current_context": "use the current selected k8s context, otherwise connect via teleport"
    },
)
@common.check_dependency(*DEP_KUBECTL)
@common.check_dependency(*DEP_TSH)
def connect_argo(c, local_port=8100, use_current_context=False):
    """
    port forward the argo UI to your local machine

    EXAMPLES:

    Call without optional arguments to forward the port at which the argo UI can be accessed via browser (url:
    localhost:8100):
    >>> invoke connect-argo

    Call with argument '--use-current-context' to connect via the currently selected k8s context. Not the remote
    machine's k8s context:
    >>> invoke connect-argo --use-current-context

        Useful if you want to connect via local k8s cert and context, without teleport.

    Call with argument '--local-port' to specify at which local port you can access the argo UI:
    >>> invoke connect-argo --local-port 9200
    """

    if not use_current_context:
        teleport.login()
        teleport.login_k8s()

    print()
    print(f"Argo is available at: http://localhost:{local_port}/argocd")
    argo_resource = "services/argocd-server"
    argo_namespace = "argocd"
    argo_port = 80
    sp.run(
        [
            "kubectl",
            "port-forward",
            "-n",
            argo_namespace,
            argo_resource,
            f"{local_port}:{argo_port}",
        ],
        stdout=sp.DEVNULL,
        check=True,
    )


@task(
    help={
        "local_port": "local port where traefik private entrypoint can be reached",
        "use_current_context": "use the current selected k8s context, otherwise connect via teleport"
    },
)
@common.check_dependency(*DEP_KUBECTL)
@common.check_dependency(*DEP_TSH)
def connect_traefik(c, local_port=3000, use_current_context=False):
    """
    port forward the traefik private entrypoint to your local machine

    EXAMPLES:

    Call without optional arguments to forward the port at which the traefik private entrypoint can be accessed
    via browser (default: localhost:3000):
    >>> invoke connect-traefik

        Now you can connect to certain k8s apps via adding a subdomain and/or path to the url
        ({SUBDOMAIN}.localhost:3000/{PATH}).

    Call with argument '--use-current-context' to connect via the currently selected k8s context.
    >>> invoke connect-traefik --use-current-context

        Useful if you want to connect via local k8s cert and context, without teleport.

    Call with argument '--local-port' to specify at which local port you can access the traefik private entrypoint:
    >>> invoke connect-traefik --local-port 9200
    """

    if not use_current_context:
        teleport.login()
        teleport.login_k8s()

    print()
    print("Connecting to traefik ...")
    forwarding = sp.Popen(
        [
            "kubectl",
            "port-forward",
            "-n",
            "traefik",
            "service/traefik",
            f"{local_port}:80",
        ],
        stdout=sp.DEVNULL
    )

    sleep(3)  # make sure port is forwarded
    response = sp.check_output(["curl", f"http://traefik.localhost:{local_port}/api/http/routers"], stderr=sp.DEVNULL)
    routes = list(json.loads(response))

    print()
    print("Accessible routes for entrypoint 'private':")
    print("~"*100)
    print()

    i = 0

    for route in routes:
        if "private" in route["entryPoints"]:
            i = i + 1
            rule = route['rule'].replace("HostRegexp(`", "")
            rule = rule.replace("PathPrefix(`", "")
            rule = rule.replace("`)", "")
            rule = rule.replace("||", "OR")
            rule = rule.replace("&&", "AND")
            print(f"- ROUTE {i}: {rule}")
            print(f"  SERVICE: {route['service']}")
            print()

    print("Access apps via:")
    print("  - subdomain at: http://{APP_SUBDOMAIN}" + f".localhost:{local_port}")
    print(f"  - path: http://localhost:{local_port}" + "/{APP_PATH}")
    forwarding.wait()


@task()
@common.check_dependency(*DEP_TSH)
@common.check_dependency(*DEP_KUBECTL)
def connect_k8s(c):
    """
    set the global k8s context to the cluster of the machine

    EXAMPLES:

    Call without optional arguments to be able to interact with k8s API of the machine via the default
    teleport cluster:
    >>> invoke connect-k8s

    Locally typed k8s related commands (kubectl get ...) now will no longer interact with your local k8s. Instead
    the commands are directed to the k8s API on the remote machine.
    """

    teleport.login()
    teleport.login_k8s()
    k8s_context_raw = sp.check_output(["kubectl", "config", "current-context"])
    k8s_context = k8s_context_raw.decode(ENCODING).replace("\n", "")
    print()
    print(f"Logged in successfully to k8s-context '{k8s_context}'")


@task
@common.check_dependency(*DEP_YQ)
@common.check_dependency(*DEP_TSH)
def disconnect_from_box(c):
    """
    disconnect from the box via unsetting k8s, talos context, logging out of teleport

    EXAMPLES:

    Call task to stop interacting with the remote machine talos and k8s APIs. Also Logout from teleport:
    >>> invoke disconnect-from-box

    All further typed, talos or k8s related commands will now refer to your local machine.
    """

    if K8S_CONFIG_USER.exists():
        k8s_context_raw = sp.check_output(["yq", '."current-context"', K8S_CONFIG_USER])
        k8s_context = k8s_context_raw.decode(ENCODING).replace("\n", "")
        if BOX_NAME == k8s_context:
            print("Unset global k8s context")
            sp.check_output(["yq", '."current-context" = ""', "-i", K8S_CONFIG_USER])

    if TALOS_CONFIG_USER.exists():
        talos_context_raw = sp.check_output(["yq", ".context", TALOS_CONFIG_USER])
        talos_context = talos_context_raw.decode(ENCODING).replace("\n", "")
        if BOX_NAME == talos_context:
            print("Unset global talos context")
            sp.check_output(["yq", '.context = ""', "-i", TALOS_CONFIG_USER])

    sp.check_output(["tsh", "logout"])
    print("Disconnected teleport")


# DEPRECATED
@task(
    help={
        "local_port": "local port where argo can be reached",
        "use_current_context": "use the current selected k8s context, otherwise connect via teleport"
    },
)
@common.check_dependency(*DEP_KUBECTL)
@common.check_dependency(*DEP_TSH)
def port_forward_argo(c, local_port=8100, use_current_context=False):
    """
    DEPRECATED: port forward the argo UI to your local machine

    DEPRECATED: You should rather use: 'invoke connect-argo'
    """

    print("DEPRECATED: You should rather use: 'invoke connect-argo'\n")
    connect_argo(c, local_port, use_current_context)


# DEPRECATED
@task(
    help={
        "local_port": "local port where traefik private entrypoint can be reached",
        "use_current_context": "use the current selected k8s context, otherwise connect via teleport"
    },
)
@common.check_dependency(*DEP_KUBECTL)
@common.check_dependency(*DEP_TSH)
def port_forward_traefik(c, local_port=3000, use_current_context=False):
    """
    DEPRECATED: port forward the traefik private entrypoint to your local machine

    DEPRECATED: You should rather use: 'invoke connect-traefik'
    """

    print("DEPRECATED: You should rather use: 'invoke connect-traefik'\n")
    connect_traefik(c, local_port, use_current_context)


# DEPRECATED
@task()
@common.check_dependency(*DEP_TSH)
@common.check_dependency(*DEP_KUBECTL)
def set_k8s_context(c):
    """
    DEPRECATED: set the global k8s context to the cluster of the machine

    DEPRECATED: You should rather use: 'invoke connect-k8s'
    """

    print("DEPRECATED: You should rather use: 'invoke connect-k8s'\n")
    connect_k8s(c)


# DEPRECATED
@task
@common.check_dependency(*DEP_YQ)
@common.check_dependency(*DEP_TSH)
def unset_contexts(c):
    """
    DEPRECATED: disconnect from the box; unset k8s + talos contexts and teleport connection

    DEPRECATED: You should rather use: 'invoke disconnect-from-box'
    """

    print("DEPRECATED: You should rather use: 'invoke disconnect-from-box'\n")
    disconnect_from_box(c)
