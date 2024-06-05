from functools import wraps
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any, Optional

from ._common import Command, TyperAbort
from ._config import BOX_NAME, TASK_CONFIG, get_config_entry


def ip(ip: str):
    """check if *ip* is in a valid address format; raise if not"""
    try:
        IPv4Address(ip)
    except ValueError as verr:
        raise TyperAbort(verr, f"Invalid ip address: {ip}")


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
                raise TyperAbort(
                    f"Current installed version of {tool} is: {version}", f"Expected version: {expected_version}"
                )
            func(*args, **kwargs)

        return wrapper_dependency

    return inner


def config_parameter(param_name: str, value: Any):
    """check if 'tasks_config.json' parameter equals 'value'"""
    def inner(func):
        @wraps(func)
        def wrapper_check_config_parameter(*args, **kwargs):
            param_value = get_config_entry(TASK_CONFIG, param_name.lower())
            task_file = Path(__file__).parent.parent.name

            if param_value != value:
                raise TyperAbort(
                    f"Invalid config in /{task_file}/tasks_config.json!",
                    f"Expected: {param_name}={value}, got: {param_name}={param_value}"
                )

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
        raise TyperAbort(
            "Make sure you are connected to the correct k8s cluster.",
            f"Expected: {BOX_NAME}, got: {node_name.rstrip()}"
        )
