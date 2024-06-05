import typer
from typing_extensions import Annotated

from .._utils._constants import K8S_CONFIG_USER, TALOS_CONFIG_USER
from . import _connect

app = typer.Typer(name="connect", help="Connect to different APIs on live machine.")


@app.command()
def talos(
    local_port: Annotated[int, typer.Option("--local-port", help="the local port to reach the talos api by")] = 50000,
    machine_ip: Annotated[
        str, typer.Option("--machine-ip", help="local network ip of live machine", rich_help_panel="Local access")
    ] = None,
    ttl: Annotated[
        str, typer.Option("--ttl", help="time local access is available", rich_help_panel="Local access")
    ] = "3h",
    talosconfig: Annotated[
        str, typer.Option("--talosconfig", help="path to talosconfig to be used")
    ] = TALOS_CONFIG_USER
):
    """
    connect to the talos-api via teleport; you are connected only as long as the command is running

    EXAMPLES:

    Call without optional arguments to connect to talos api via default teleport cluster:
    >>> iiotctl connect talos

        While the command runs in one console you can interact with the talos api via talosctl in another.
    """

    _connect.connect_talos(local_port, machine_ip, ttl, talosconfig)


@app.command()
def k8s(
    machine_ip: Annotated[
        str, typer.Option("--machine-ip", help="local network ip of live machine", rich_help_panel="Local access")
    ] = None,
    ttl: Annotated[
        str, typer.Option("--ttl", help="time local access is available", rich_help_panel="Local access")
    ] = "3h",
    kubeconfig: Annotated[str, typer.Option("--kubeconfig", help="path to kubeconfig to be used")] = K8S_CONFIG_USER
):
    """
    set the global k8s context to the cluster of the machine

    EXAMPLES:

    Call without optional arguments to be able to interact with k8s API of the machine via the default
    teleport cluster:
    >>> iiotctl connect k8s

    Locally typed k8s related commands (kubectl get ...) now will no longer interact with your local k8s. Instead
    the commands are directed to the k8s API of the live machine.
    """

    _connect.connect_k8s(machine_ip, ttl, kubeconfig)


@app.command()
def argo(
    local_port: Annotated[int, typer.Option("--local-port", help="local port where argo can be reached")] = 8100,
    local_address: Annotated[
        str,
        typer.Option("--local-address", help="local address to listen on")
    ] = "localhost",
    use_current_context: Annotated[
        bool,
        typer.Option(
            "--use-current-context", "-u", help="use the current selected k8s context, otherwise connect via teleport"
        )
    ] = False,
    kubeconfig: Annotated[str, typer.Option("--kubeconfig", help="path to kubeconfig to be used")] = K8S_CONFIG_USER
):
    """
    port forward the argo UI to your local machine

    EXAMPLES:

    Call without optional arguments to forward the port at which the argo UI can be accessed via browser (url:
    localhost:8100):
    >>> iiotctl connect argo

    Call with argument '--use-current-context' to connect via the currently selected k8s context. Not the live
    machine's k8s context:
    >>> iiotctl connect argo --use-current-context

        Useful if you want to connect via local k8s cert and context, without teleport.

    Call with argument '--local-port' to specify at which local port you can access the argo UI:
    >>> iiotctl connect argo --local-port 9200
    """

    _connect.connect_argo(local_port, local_address, use_current_context, kubeconfig)


@app.command()
def traefik(
    local_port: Annotated[
        int, typer.Option("--local-port", help="local port where traefik private entrypoint can be reached")
    ] = 3000,
    local_address: Annotated[
        str,
        typer.Option("--local-address", help="local address to listen on")
    ] = "localhost",
    use_current_context: Annotated[
        bool,
        typer.Option(
            "--use-current-context", "-u", help="use the current selected k8s context, otherwise connect via teleport"
        )
    ] = False,
    kubeconfig: Annotated[str, typer.Option("--kubeconfig", help="path to kubeconfig to be used")] = K8S_CONFIG_USER
):
    """
    port forward the traefik private entrypoint to your local machine

    EXAMPLES:

    Call without optional arguments to forward the port at which the traefik private entrypoint can be accessed
    via browser (default: localhost:3000):
    >>> iiotctl connect traefik

        Now you can connect to certain k8s apps via adding a subdomain and/or path to the url
        ({SUBDOMAIN}.localhost:3000/{PATH}).

    Call with argument '--use-current-context' to connect via the currently selected k8s context:
    >>> iiotctl connect traefik --use-current-context

        Useful if you want to connect via local k8s cert and context, without teleport.

    Call with argument '--local-port' to specify at which local port you can access the traefik private entrypoint:
    >>> iiotctl connect traefik --local-port 9200
    """

    _connect.connect_traefik(local_port, local_address, use_current_context, kubeconfig)
