from functools import wraps
from ipaddress import IPv4Address
from typing import Optional

from . import _kubectl as kubectl
from ._common import Command, TyperAbort


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


def k8s_connection(cluster_name: str, kubeconfig: str):
    """check if connected to correct k8s cluster; raise if not"""

    node_name = kubectl.fetch(resource="nodes", format="jsonpath={.items[*].metadata.name}", kubeconfig=kubeconfig)

    if node_name.rstrip() != cluster_name:
        raise TyperAbort(
            "Make sure you are connected to the correct k8s cluster.",
            f"Expected: {cluster_name}, got: {node_name.rstrip()}"
        )
