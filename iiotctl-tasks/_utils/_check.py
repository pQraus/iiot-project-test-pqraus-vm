import sys
from functools import wraps
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any, Optional

import typer

from ._common import Command, print_error
from ._config import BOX_NAME, _config, _get_config_entry


def ip(ip: str):
    """check if *ip* is in a valid address format; raise if not"""
    try:
        IPv4Address(ip)
    except ValueError as verr:
        print_error(verr, f"Invalid ip address: {ip}", sep="\n")
        raise typer.Abort()


def dependency(tool: str, version_cmd: str, expected_version: Optional[str] = None):
    """check if a (tool) dependency is installed (in the expected version)"""
    def inner(func):
        @wraps(func)
        def wrapper_dependency(*args, **kwargs):
            version_cmd_splitted = version_cmd.split(" ")  # create a list for subprocess
            check_cmd = [tool] + version_cmd_splitted
            version = Command.check_output(
                cmd=check_cmd,
                additional_error_msg=f"Have you installed {tool}?\nCan't execute '{check_cmd}'."
            )

            # version check
            if expected_version and (expected_version not in version):
                print_error(
                    f"Current version of {tool} is:\n {version}",
                    file=sys.stderr,
                )
                print_error(
                    f"Expect that version {expected_version} is installed",
                    file=sys.stderr,
                )
                raise typer.Abort()
            func(*args, **kwargs)

        return wrapper_dependency

    return inner


def config_parameter(param_name: str, value: Any):
    """check if 'tasks_config.json' parameter equals 'value'"""
    def inner(func):
        @wraps(func)
        def wrapper_check_config_parameter(*args, **kwargs):
            param_value = _get_config_entry(_config, param_name.lower())
            task_file = Path(__file__).parent.parent.name

            if param_value != value:
                print_error(
                    f"Invalid config in /{task_file}/tasks_config.json! Expected: {param_name}={value},",
                    f"got: {param_name}={param_value}"
                )
                raise typer.Abort()

            func(*args, **kwargs)

        return wrapper_check_config_parameter

    return inner


def k8s_connection(kubeconfig: str):
    """check if connected to correct k8s cluster; raise if not"""

    node_name = Command.check_output(
        cmd=[
            "kubectl",
            "get",
            "nodes",
            "-o",
            "jsonpath={.items[*].metadata.name}",
            "--kubeconfig",
            Path(kubeconfig)
        ],
        additional_error_msg="Unable to retrieve k8s node name."
    )

    if node_name.rstrip() != BOX_NAME:
        print_error("Make sure you are connected to the correct k8s cluster.")
        print_error(f"Expected: {BOX_NAME}, got: {node_name.rstrip()}")
        raise typer.Abort()
