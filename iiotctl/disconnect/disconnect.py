import typer

from . import _disconnect

app = typer.Typer(name="disconnect", help="Disconnect from different APIs of live machine.")


@app.command()
def talos():
    """unset talos context"""
    _disconnect.unset_talos_context()


@app.command()
def k8s():
    """unset kubernetes context"""
    _disconnect.unset_k8s_context()


@app.command()
def teleport():
    """log out from teleport server"""
    _disconnect.teleport_logout()


@app.command()
def all():
    """unset all contexts; log out from teleport server"""
    _disconnect.unset_talos_context()
    _disconnect.unset_k8s_context()
    _disconnect.teleport_logout()
