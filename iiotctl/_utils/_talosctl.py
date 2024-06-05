import json
import re
import subprocess as sp
import sys
import tempfile
from pathlib import Path
from time import sleep
from typing import Iterable, List

from ._common import Command, TyperAbort, patch_json, patch_yaml_file, print_if
from ._constants import JQ_MODULES_DIR, REPO_ROOT

ENCODING = sys.stdout.encoding


def apply_mc(mc: bytes, exit_on_failure=True, print_errors=True, **talos_args):
    """apply the mc to a machine with talosctl

    **talos_args: are passed to the talosctl command
    """
    additional_args = _create_talos_args(**talos_args)
    mode = talos_args["mode"] if "mode" in talos_args else "auto"
    error_msg = f'Can not apply the machine config in {mode} mode.'
    error_msg = error_msg + " (via dry-run)" if "dry_run" in talos_args else error_msg

    # tempdir is required because the apply cmd must read from a file
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        mc_file = tmp_dir / "mc.json"
        with open(mc_file, "wb") as fmc:
            fmc.write(mc)
        base_cmd = [
            "talosctl",
            "apply-config",
            "--file",
            mc_file,
        ]

        cmd_result = Command.check(
            cmd=base_cmd + additional_args,
            ignore_error_msg=not print_errors,
            additional_error_msg=error_msg if print_errors else ""
        )

    if exit_on_failure and not cmd_result:
        raise TyperAbort()

    return cmd_result


def fetch_mc(id, **talos_args) -> bytes:
    """fetch the mc by id from a machine with talosctl

    **talos_args: are passed to the talosctl command
    """

    base_cmd = ["talosctl", "get", "mc", id, "-o", "json"]
    additional_args = _create_talos_args(**talos_args)
    mc_with_meta = Command.check_output(cmd=base_cmd + additional_args, in_bytes=True)
    fetched_mc = Command.check_output(cmd=["jq", ".spec"], in_bytes=True, input=mc_with_meta)
    return fetched_mc


def get_live_talos_version(**talos_args):
    """get the talos version from a machine with talosctl

    **talos_args: are passed to the talosctl command
    """
    additional_args = _create_talos_args(**talos_args)
    cmd = ["talosctl", "version"] + additional_args
    cmd_result = Command.check_output(cmd, additional_error_msg="Can't get the talos version.", timeout=10.0)

    # parse the stdout (it's a text)
    versions: List[str] = re.findall("Tag: *v(.*)", cmd_result)
    # 1. match: client version, 2. match: server / machine version
    if len(versions) != 2:  # exit when it's not possible to get two matches
        raise TyperAbort("Can't get the talos version from client and server:", cmd_result)

    live_version = versions[1]
    return live_version


def get_talos_resource(resource_name, **talos_args):
    """get a resource from the machine via talosctl in json"""
    additional_args = _create_talos_args(**talos_args)
    cmd = ["talosctl", "get", resource_name, "-o", "json"] + additional_args
    cmd_result = Command.check_output(cmd, additional_error_msg="Can't get the talos resource.")
    return json.loads(cmd_result)


def _fetch_talos_extension_data(jsonpath: str, **talos_args):
    """fetch talos extension data from live machine via jsonpath"""
    additional_args = _create_talos_args(**talos_args)
    cmd = ["talosctl", "get", "extensions", "-o", "jsonpath=" + jsonpath] + additional_args
    data: str = Command.check_output(cmd)

    return data.rstrip().split("\n")


def get_live_talos_extension_versions(**talos_args):
    """returns all live talos extensions with their respective versions"""
    live_exts_names = _fetch_talos_extension_data(jsonpath="{.spec.metadata.name}", **talos_args)
    live_exts_versions = _fetch_talos_extension_data(jsonpath="{.spec.metadata.version}", **talos_args)
    live_exts_authors = _fetch_talos_extension_data(jsonpath="{.spec.metadata.author}", **talos_args)

    live_exts = {}
    for name, vers, author in zip(live_exts_names, live_exts_versions, live_exts_authors):
        if "Talos Machinery" not in author:
            live_exts.update({name: vers})

    return live_exts


def get_live_k8s_version(mc: bytes):
    """get the live used k8s version from a machine config"""
    # match the image version of kubelet (ghcr.io/siderolabs/kubelet:v...)
    jq_filter = '.machine.kubelet.image | match("(?<=:v).*").string'

    cmd_result: bytes = Command.check_output(
        cmd=["jq", jq_filter],
        additional_error_msg="Can't get the kubelet image version.",
        input=mc,
        in_bytes=True
    )

    # convert stdout to the k8s version without quotes and newline escapes
    live_version = cmd_result.decode(ENCODING).replace('"', "").replace("\n", "")
    return live_version


def generate_mc(cluster_name="CLUSTER_NAME", **talos_args):
    """generate a machine config with talosctl

    Return: machine_config, talosconfig
    """
    additional_talos_args = _create_talos_args(**talos_args)

    # tmpdir is required because talosctl gen can't write to stdout
    with tempfile.TemporaryDirectory(prefix="talos-blank-config") as td:
        tmp_dir = Path(td)
        base_cmd = [
            "talosctl",
            "gen",
            "config",
            "--output-dir",
            tmp_dir.absolute(),
            cluster_name,
            f"https://{cluster_name}:6443",
        ]
        controlplane_file = tmp_dir / "controlplane.yaml"
        talosconfig_file = tmp_dir / "talosconfig"
        Command.check_output(base_cmd + additional_talos_args, capture_output=False)

        with patch_yaml_file(file_path=controlplane_file) as file:
            controlplane_mc = file

        controlplane_mc = bytes(json.dumps(controlplane_mc, indent=2), ENCODING)

        with open(talosconfig_file, "rb") as rd:
            talosconfig = rd.read()

    return controlplane_mc, talosconfig


def validate_mc(mc: bytes):
    """validate the *mc* with talosctl

    exit 1 when there is a validation error
    """
    # tmpdir is required because talosctl validate needs a file which contains the mc
    with tempfile.TemporaryDirectory("talos-validate") as td:
        tmp_dir = Path(td)
        mc_file = tmp_dir / "mc.json"
        with open(mc_file, "wb") as fmc:
            fmc.write(mc)

        Command.check_output(
            cmd=["talosctl", "validate", "--mode=metal", "-c", mc_file],
            additional_error_msg="Machine config is not valid.",
        )


def patch_mc(mc: bytes, patch_files: Iterable[str], validation=True, verbose=False):
    """patches mc with all local jq patch files and validates it for each patch"""
    for patch in patch_files:
        print_if(f"   patch: {patch.relative_to(REPO_ROOT)}", verbose)
        mc = patch_json(mc, patch, JQ_MODULES_DIR)
        # validate the mc after each patch
        if validation:
            validate_mc(mc)

    return mc


def upgrade_k8s(node_name: str, to_version: str, pull_images: bool, verbose: bool, **talos_args):
    """upgrade k8s via talosctl and port forwarding the kube-api

    How a k8s upgrade on a talos machine works:
    1. port forward the k8s-api-server to the local machine
       (this is required because the talos upgrade command expects the k8s endpoint at a domain name)
    2. start the k8s upgrade
    3. while upgrading (the api server), the forwarding of the api must restart sometimes
    4. after the upgrade has finished, the port forwarding process
    """
    base_talos_cmd = [
        "talosctl",
        "upgrade-k8s",
        "--to",
        to_version,
        f"--pre-pull-images={str(pull_images).lower()}",
        "--endpoint",
        "localhost",
    ]
    additional_talos_args = _create_talos_args(**talos_args)
    api_server_pod = f"kube-apiserver-{node_name}"
    port_forward_cmd = [
        "kubectl",
        "port-forward",
        "-n",
        "kube-system",
        f"pods/{api_server_pod}",
        "6443:6443",
    ]
    print_if("Start port forwarding for the k8s api ...", verbose)
    # prepare the port forwarding
    port_forward_process = sp.Popen(port_forward_cmd, stdout=sp.DEVNULL, stderr=sp.PIPE)
    sleep(2)
    if port_forward_process.poll():  # test if the connection is ready
        raw_error = port_forward_process.stderr.read()
        raise TyperAbort("Can't forward the the api-server to your machine:", raw_error.decode(ENCODING))
    print_if("Start the upgrade process ...", verbose)

    # execute the upgrade
    try:  # upgrade and kill the port forwarding process definitely
        upgrade_process = sp.Popen(base_talos_cmd + additional_talos_args)
        while upgrade_process.poll() is None:
            if port_forward_process.poll() is not None:
                print_if("Retry to port forward the k8s-api ...\n", verbose)
                port_forward_process = sp.Popen(
                    port_forward_cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL
                )
            sleep(4)
    finally:
        port_forward_process.kill()

    if upgrade_process.returncode:
        raise TyperAbort()


def upgrade_talos(**talos_args):
    """upgrade talos via talosctl"""
    base_cmd = ["talosctl", "upgrade"]
    additional_args = _create_talos_args(**talos_args)
    Command.check_output(base_cmd + additional_args)


def _create_talos_args(**cmd_kw_args):
    """create cmd args from a dict

    add '--' to the key and replace '_' with '-'
    """
    args = []
    for arg, value in cmd_kw_args.items():
        comp_arg = f"--{arg.replace('_', '-')}={value}"
        args.append(comp_arg)
    return args
