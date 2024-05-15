import json
import re
import subprocess as sp
import sys
import tempfile
from pathlib import Path
from subprocess import TimeoutExpired
from time import sleep
from typing import Dict, Iterable, List

from ._common import patch_json, print_if
from ._config import ENCODING, JQ_MODULES_DIR, REPO_ROOT, TALOS_EXTENSIONS


def apply_mc(mc: bytes, exit_on_failure=True, **talos_args):
    """apply the mc to a machine with talosctl

    **talos_args: are passed to the talosctl command
    """
    additional_args = _create_talos_args(**talos_args)

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
        cmd_result: sp.CompletedProcess = sp.run(
            base_cmd + additional_args,
            capture_output=True,
        )

    if exit_on_failure and cmd_result.returncode:
        print(cmd_result.stderr.decode(ENCODING), file=sys.stderr, end="\n\n")
        print("Can't apply the machine config", file=sys.stderr)
        print(
            "(Maybe another apply mode must be used to apply the config?)",
            file=sys.stderr,
        )
        exit(1)

    return cmd_result


def fetch_mc(id, **talos_args):
    """fetch the mc by id from a machine with talosctl

    **talos_args: are passed to the talosctl command
    """

    base_cmd = ["talosctl", "get", "mc", id, "-o", "json"]
    additional_args = _create_talos_args(**talos_args)
    mc_with_meta = sp.check_output(base_cmd + additional_args)
    fetched_mc = sp.check_output(["jq", ".spec"], input=mc_with_meta)
    return fetched_mc


def get_current_talos_version(**talos_args):
    """get the talos version from a machine with talosctl

    **talos_args: are passed to the talosctl command
    """
    additional_args = _create_talos_args(**talos_args)
    cmd = ["talosctl", "version"] + additional_args
    try:
        cmd_result: sp.CompletedProcess = sp.run(
            cmd,
            capture_output=True,
            timeout=10.0
        )
    except TimeoutExpired as te:
        print("Can't get the talos version:\n", file=sys.stderr)
        print(te, file=sys.stderr)
        exit(1)

    if cmd_result.returncode:
        print("Can't get the talos version:\n", file=sys.stderr)
        print(cmd_result.stderr.decode(ENCODING), file=sys.stderr)
        exit(1)

    cmd_out = cmd_result.stdout.decode(ENCODING)

    # parse the stdout (it's a text)
    versions: List[str] = re.findall("Tag: *v(.*)", cmd_out)
    # 1. match: client version, 2. match: server / machine version
    if len(versions) != 2:  # exit when it's not possible to get two matches
        print("Can't get the talos version from client and server:\n", file=sys.stderr)
        print(cmd_out, file=sys.stderr)
        exit(1)

    current_version = versions[1]
    return current_version


def get_talos_resource(resource_name, **talos_args):
    """get a resource from the machine via talosctl in json"""
    additional_args = _create_talos_args(**talos_args)
    cmd = ["talosctl", "get", resource_name, "-o", "json"] + additional_args
    cmd_result: sp.CompletedProcess = sp.run(
        cmd,
        capture_output=True,
    )
    if cmd_result.returncode:
        print("Can't get the talos resource:\n", file=sys.stderr)
        print(cmd_result.stderr.decode(ENCODING), file=sys.stderr)
        exit(1)
    return json.loads(cmd_result.stdout)


def _fetch_talos_extension_data(jsonpath: str, **talos_args):
    """fetch talos extension data from remote machine via jsonpath"""
    additional_args = _create_talos_args(**talos_args)
    cmd = ["talosctl", "get", "extensions", "-o", "jsonpath=" + jsonpath] + additional_args
    data = sp.check_output(cmd, encoding="UTF-8")

    return data.rstrip().split("\n")


def get_remote_talos_extension_versions(**talos_args):
    """returns all remote talos extensions with their respective versions"""
    remote_exts_names = _fetch_talos_extension_data(jsonpath="{.spec.metadata.name}", **talos_args)
    remote_exts_versions = _fetch_talos_extension_data(jsonpath="{.spec.metadata.version}", **talos_args)
    return dict(zip(remote_exts_names, remote_exts_versions))


def get_current_k8s_version(mc: bytes):
    """get the current used k8s version from a machine config"""
    # match the image version of kubelet (ghcr.io/siderolabs/kubelet:v...)
    jq_filter = '.machine.kubelet.image | match("(?<=:v).*").string'

    cmd_result = sp.run(["jq", jq_filter], capture_output=True, input=mc)
    if cmd_result.returncode:
        print("Can't get the kubelet image version:\n", file=sys.stderr)
        print(cmd_result.stderr.decode(sys.stdout.encoding), file=sys.stderr)
        exit(1)

    # convert stdout to the k8s version without quotes and newline escapes
    current_version = (
        cmd_result.stdout.decode(ENCODING).replace('"', "").replace("\n", "")
    )
    return current_version


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
        sp.check_output(base_cmd + additional_talos_args)
        controlplane_mc = sp.check_output(["yq", ".", "-o", "json", controlplane_file])
        talosconfig = sp.check_output(["yq", ".", talosconfig_file])

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
        cmd_result: sp.CompletedProcess = sp.run(
            ["talosctl", "validate", "--mode=metal", "-c", mc_file],
            capture_output=True,
        )
    if cmd_result.returncode:
        print("Machine config is not valid:\n", file=sys.stderr)
        print(cmd_result.stderr.decode(sys.stdout.encoding), file=sys.stderr)
        exit(1)


def patch_mc(mc: bytes, patch_files: Iterable[str], validation=True, verbose=False):
    """patches mc with all local jq patch files and validates it for each patch"""
    for patch in patch_files:
        print_if(f"   patch: {patch.relative_to(REPO_ROOT)}", verbose)
        mc = patch_json(mc, patch, JQ_MODULES_DIR)
        # validate the mc after each patch
        if validation:
            validate_mc(mc)

    return mc


def upgrade_k8s(node_name, to_version, verbose, **talos_args):
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
        print("Can't forward the the api-server to your machine:\n", file=sys.stderr)
        raw_error = port_forward_process.stderr.read()
        print(raw_error.decode(ENCODING), file=sys.stderr)
        exit(1)
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
        exit(1)


def upgrade_talos(**talos_args):
    """upgrade talos via talosctl"""
    base_cmd = ["talosctl", "upgrade"]
    additional_args = _create_talos_args(**talos_args)
    sp.run(base_cmd + additional_args, check=True)


def _create_talos_args(**cmd_kw_args):
    """create cmd args from a dict

    add '--' to the key and replace '_' with '-'
    """
    args = []
    for arg, value in cmd_kw_args.items():
        comp_arg = f"--{arg.replace('_', '-')}={value}"
        args.append(comp_arg)
    return args
