import os
import subprocess as sp
from pathlib import Path

from invoke import task
from packaging.version import parse as parse_version

from .. import _common as common
from .._config import ASDF_PLUGINS, REPO_ROOT


@task
def setup_tools(c):
    """show overview of required and installed tools; set up tools with asdf"""

    if not Path(REPO_ROOT / ".tool-versions").exists():
        print("Missing local '.tool-versions' file to retrieve tool version requirements.")
        return

    # get project tool version requirements
    with open(REPO_ROOT / ".tool-versions") as rd:
        exp_tools = rd.read().split("\n")[1:-1]
        if not exp_tools:
            print("Project has no tool version requirements.")
            return

    exp_tools = dict(line.split(" ")[:2] for line in exp_tools)
    is_installed = {tool: False for tool in exp_tools}
    path_glob_vers = Path(os.path.expanduser("~") + "/.tool-versions")
    glob_tools = {}

    # get global set tool versions
    if path_glob_vers.exists():
        with open(path_glob_vers) as rd:
            glob_tools = rd.read().split("\n")[:-1]

        if glob_tools:
            glob_tools = dict(line.split(" ")[:2] for line in glob_tools)

    plugins = sp.check_output(["asdf", "plugin", "list"]).decode().split("\n")

    # compare installed and required tool versions
    for tool, exp_vers in exp_tools.items():
        exp_vers = parse_version(exp_vers)
        if tool not in plugins:
            continue
        vers_list = sp.check_output(["asdf", "list", tool], stderr=sp.DEVNULL).decode().split("\n")[:-1]
        if not vers_list:
            continue
        for vers in vers_list:
            vers = parse_version(vers[2:])
            if (vers.major == exp_vers.major) and (vers.minor == exp_vers.minor) and (vers.micro >= exp_vers.micro):
                is_installed[tool] = True
                break

    print("Check asdf plugins:")
    print()

    # print tool required <-> tool installed overview
    print(f"{'NAME':<25} {'PROJECT VERSION':<20} {'STATUS':<13} {'SYSTEM VERSION'}")
    print("~"*85)
    for tool in sorted(exp_tools.keys(), key=len):
        version = exp_tools[tool]
        status = "INSTALLED" if is_installed[tool] else "MISSING"
        print(f"{tool + ':':<25} required: {version:<10} {status:<13} (global use: {glob_tools.get(tool, '---')})")
    print("~"*85)

    print()
    to_install = [tool for tool, installed in is_installed.items() if not installed]

    if not to_install:
        print("All tool versions are up-to-date.")
        return

    print("Missing tool versions:")
    print("~"*25)
    print(*[f" - {tool} {exp_tools[tool]}" for tool in to_install], sep="\n")
    print()

    install = common.check_user_choice("Do you want to install the required but missing tool versions? [y/n] ")

    if not install:
        return

    print()
    print("Add as asdf plugins:")
    print("~"*25)
    for tool in ASDF_PLUGINS:
        if tool in to_install:
            sp.run(["asdf", "plugin-add", tool, ASDF_PLUGINS[tool]["source"]], capture_output=True)
            print(f" - added '{tool}'")

    print()
    print("Install tools:")
    print("~"*25)
    for tool in to_install:
        sp.run(["asdf", "install", tool, exp_tools[tool]], capture_output=True)
        print(f" - installed '{tool}'")
