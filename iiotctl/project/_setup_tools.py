import os
from pathlib import Path
from typing import Dict, List

import typer
from packaging.version import parse as parse_version
from rich import print
from rich.table import Table

from .._utils._common import Command, TyperAbort
from .._utils._config import ASDF_PLUGINS
from .._utils._constants import REPO_ROOT


def _get_local_project_tools():
    """get local project asdf tool names + version requirements"""
    with open(REPO_ROOT / ".tool-versions") as rd:
        exp_tools = rd.read().split("\n")[1:-1]
        if not exp_tools:
            raise TyperAbort("Project has no tool version requirements.")

    return dict(line.split(" ")[:2] for line in exp_tools)  # dict with key-value pairs: {TOOL_NAME: VERSION}


def _get_global_project_tools(path_glob_vers: Path):
    """get global asdf tool names + version requirements"""
    glob_tools = {}

    if path_glob_vers.exists():
        with open(path_glob_vers) as rd:
            glob_tools = rd.read().split("\n")[:-1]

        # dict with key-value pairs: {TOOL_NAME: VERSION}
        if glob_tools:
            glob_tools = dict(line.split(" ")[:2] for line in glob_tools)

    return glob_tools


def _list_installed_expected_tools(plugins: List[str], exp_tools: Dict[str, str]):
    """list required tools + version and if they are installed or not"""
    is_installed = {tool: False for tool in exp_tools}

    for tool, exp_vers in exp_tools.items():
        if tool not in plugins:
            continue
        # list all installed versions of tool
        vers_list = Command.check_output(cmd=["asdf", "list", tool]).split("\n")[:-1]
        if not vers_list:
            continue
        exp_vers = parse_version(exp_vers)
        for vers in vers_list:
            vers = parse_version(vers[2:])  # [2:] to cut off '  ' indent or ' *' prefix in 'asdf list *tool*'
            if (vers.major == exp_vers.major) and (vers.minor == exp_vers.minor) and (vers.micro >= exp_vers.micro):
                is_installed[tool] = True
                break

    return is_installed


def _print_tool_version_overview(exp_tools: Dict[str, str], glob_tools: Dict[str, str], is_installed: Dict[str, bool]):
    """print tool required <-> tool installed version overview"""
    table = Table(title="Asdf plugin overview:")
    table.add_column("NAME")
    table.add_column("PROJECT_VERSION")
    table.add_column("INSTALLED", justify="center")
    table.add_column("SYSTEM VERSION")

    for tool in sorted(exp_tools.keys(), key=len):
        version = exp_tools[tool]
        status = ":white_heavy_check_mark:" if is_installed[tool] else ":x:"
        table.add_row(tool, version, status, f"(global use: {glob_tools.get(tool, '---')})")

    print(table)


def _add_required_plugins(plugins_to_add: List[str]):
    """add required tools as plugins to asdf"""
    print()
    print("Add as asdf plugins:")
    print("~"*25)
    for tool in ASDF_PLUGINS:
        if tool in plugins_to_add:
            Command.check_output(cmd=["asdf", "plugin-add", tool, ASDF_PLUGINS[tool]["source"]])
            print(f" - added '{tool}'")


def _install_required_tools(exp_tools: Dict[str, str], to_install: List[str]):
    """install required tools as plugins to asdf"""
    print()
    print("Install tools:")
    print("~"*25)
    for tool in to_install:
        Command.check_output(cmd=["asdf", "install", tool, exp_tools[tool]])
        print(f" - installed '{tool} {exp_tools[tool]}'")


def setup_tools(setup_required: bool):
    if not Path(REPO_ROOT / ".tool-versions").exists():
        raise TyperAbort("Missing local '.tool-versions' file to retrieve tool version requirements.")

    exp_tools = _get_local_project_tools()
    path_glob_vers = Path(os.path.expanduser("~")) / ".tool-versions"
    glob_tools = _get_global_project_tools(path_glob_vers)

    plugins = Command.check_output(cmd=["asdf", "plugin", "list"]).split("\n")
    is_installed = _list_installed_expected_tools(plugins, exp_tools)

    _print_tool_version_overview(exp_tools, glob_tools, is_installed)

    to_install = [tool for tool, installed in is_installed.items() if not installed]

    if not to_install:
        print("All tool versions are up-to-date.")
        return

    install = typer.confirm(
        "Do you want to install the required but missing tool versions?", default=True, abort=setup_required
    )

    if not install:
        return

    plugins_to_add = [tool for tool in to_install if tool not in glob_tools]
    if plugins_to_add:
        _add_required_plugins(plugins_to_add)

    _install_required_tools(exp_tools, to_install)
