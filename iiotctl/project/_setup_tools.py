from pathlib import Path
from typing import Dict, List, Set

import typer
from packaging.version import Version
from packaging.version import parse as parse_version
from rich import print
from rich.table import Table

from .._utils import _check as check
from .._utils._common import Command, TyperAbort
from .._utils._config import ASDF_PLUGINS, DEP_GH


def _get_globally_used_tools() -> Dict[str, str]:
    """get global asdf tool names + version requirements; return dict with key-value pairs: {TOOL_NAME: VERSION}"""
    path_glob_vers = Path.home() / ".tool-versions"
    glob_tools = {}

    if not path_glob_vers.exists():
        return glob_tools

    with open(path_glob_vers) as rd:
        glob_tools = rd.read().splitlines()

    if glob_tools:
        glob_tools = dict(line.split(" ")[:2] for line in glob_tools)

    return glob_tools


def is_valid_version_in_list(vers_list: List[str], exp_vers: Version) -> bool:
    """
    return true if in given list is a version number, that has equal major and minor versions
    and a patch version >= the given expected version number patch version
    """
    for vers in vers_list:
        vers = parse_version(vers[2:])  # [2:] to cut off '  ' indent or ' *' prefix in 'asdf list *tool*'
        if (vers.major == exp_vers.major) and (vers.minor == exp_vers.minor) and (vers.micro >= exp_vers.micro):
            return True
    return False


def _list_tools_to_install() -> Set[str]:
    """list required tools + version and if they are installed or not"""
    curr_plugins = Command.check_output(cmd=["asdf", "plugin", "list"]).splitlines()
    to_install = set()

    for tool, data in ASDF_PLUGINS.items():
        if tool not in curr_plugins:
            to_install.add(tool)
            continue
        exp_vers = parse_version(data["version"])
        # list all installed versions of specific tool
        vers_list: List[str] = Command.check_output(cmd=["asdf", "list", tool]).splitlines()
        if (not vers_list) or (not is_valid_version_in_list(vers_list, exp_vers)):
            to_install.add(tool)

    return to_install


def _print_tool_version_overview(glob_tools: Dict[str, str], to_install: Set[str]):
    """print tool required <-> tool installed version overview"""
    table = Table(title="Asdf tool overview:")
    table.add_column("NAME")
    table.add_column("PROJECT VERSION")
    table.add_column("INSTALLED", justify="center")
    table.add_column("SYSTEM VERSION")

    for tool in sorted(ASDF_PLUGINS.keys(), key=len):
        version = ASDF_PLUGINS[tool]["version"]
        status = ":x:" if tool in to_install else ":white_heavy_check_mark:"
        table.add_row(tool, version, status, f"(global use: {glob_tools.get(tool, '---')})")

    print(table)


def _get_current_plugin_urls() -> dict[str, str]:
    """get asdf plugin '{name: repo_url}' dict"""
    tool_text = Command.check_output(["asdf", "plugin", "list", "--urls"])
    tool_url_config = {}
    for line in tool_text.splitlines():
        tool, url = line.split(" ", 1)
        url = url.lstrip()
        tool_url_config.update({tool: url})
    return tool_url_config


def _install_tools(tools_to_install: Set[str]):
    """add tools as asdf plugins; install tools"""
    curr_tool_urls = _get_current_plugin_urls()
    print()
    print("Install tools:")
    print("~"*25)
    for tool in tools_to_install:
        plugin_url = ASDF_PLUGINS[tool]["source"]
        local_version = ASDF_PLUGINS[tool]["version"]

        if tool not in curr_tool_urls.keys():
            Command.check_output(["asdf", "plugin", "add", tool, plugin_url])
            print(f" - added plugin '{tool}'")
        elif plugin_url != curr_tool_urls[tool]:
            Command.check_output(["asdf", "plugin", "remove", tool])
            Command.check_output(["asdf", "plugin", "add", tool, plugin_url])
            print(f" - updated plugin '{tool}' repo url")
        else:
            Command.check_output(["asdf", "plugin", "update", tool])
            print(f" - updated plugin '{tool}' repo")

        Command.check_output(["asdf", "install", tool, local_version])
        print(f" - installed tool '{tool}'")
        print()

    print()


@check.dependency(*DEP_GH)
def setup_tools(setup_required: bool):
    logged_into_gh = Command.check(cmd=["gh", "auth", "status"])
    if not logged_into_gh:
        raise TyperAbort("You need to be logged into github cli tool 'gh'.")

    glob_tools = _get_globally_used_tools()
    tools_to_install = _list_tools_to_install()

    _print_tool_version_overview(glob_tools, tools_to_install)

    if not tools_to_install:
        print("All tool versions are up-to-date.")
        return

    install_tools = typer.confirm(
        "Do you want to add the missing tools?",
        default=True,
        abort=setup_required
    )

    if not install_tools:
        return

    _install_tools(tools_to_install)
