from .connect import connect
from .disconnect import disconnect
from .machine import machine
from .project import project

IIOTCTL_VERSION = "v2"

TYPER_APPS = [
    connect.app,
    disconnect.app,
    machine.app,
    project.app
]
