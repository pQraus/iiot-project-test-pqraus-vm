import base64
import datetime
import json
import re
import subprocess as sp
import sys
import tempfile
from pathlib import Path
from time import sleep
from typing import Dict, Iterable, List

import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from ._common import (Command, TyperAbort, parse_kwargs_to_cli_args,
                      patch_json, print_if)
from ._constants import JQ_MODULES_DIR, K8S_CONFIG_USER, REPO_ROOT

ENCODING = sys.stdout.encoding


def apply_mc(mc: bytes, exit_on_failure=True, print_errors=True, **talos_args):
    """apply the mc to a machine with talosctl

    **talos_args: are passed to the talosctl command
    """
    additional_args = parse_kwargs_to_cli_args(**talos_args)
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
    additional_args = parse_kwargs_to_cli_args(**talos_args)
    mc_with_meta = Command.check_output(cmd=base_cmd + additional_args, in_bytes=True)
    fetched_mc = json.loads(mc_with_meta)["spec"]
    return bytes(json.dumps(fetched_mc, indent=2), ENCODING)


def get_disks(**talos_args) -> Dict[str, Dict[str, str]]:
    base_cmd = ["talosctl", "disks"]
    additional_args = parse_kwargs_to_cli_args(**talos_args)
    disks_table = Command.check_output(cmd=base_cmd + additional_args)
    header_line = disks_table.splitlines()[0]
    keys = header_line.split()[:11]  # only use the first 11 elements, skip READ_ONLY ...
    disk_entries = disks_table.splitlines()[1:]
    disks = {}
    for i in disk_entries:
        disk_values = re.split(r'\s{3,}', i)
        disk = {key: value for key, value in zip(keys, disk_values) if value != "-"}
        name = disk.pop("DEV")
        disks.update({name: disk})
    return disks


def get_live_talos_version(**talos_args) -> str:
    """get the talos version from a machine with talosctl

    **talos_args: are passed to the talosctl command
    """
    additional_args = parse_kwargs_to_cli_args(**talos_args)
    cmd = ["talosctl", "version"] + additional_args
    cmd_result = Command.check_output(cmd, additional_error_msg="Can't get the talos version.", timeout=10.0)

    # parse the stdout (it's a text)
    versions: List[str] = re.findall("Tag: *v(.*)", cmd_result)
    # 1. match: client version, 2. match: server / machine version
    if len(versions) != 2:  # exit when it's not possible to get two matches
        raise TyperAbort("Can't get the talos version from client and server:", cmd_result)

    live_version = versions[1]
    return live_version


def get_talos_resource(resource_name, **talos_args) -> Dict | List[Dict]:
    """get a resource from the machine via talosctl in json"""
    additional_args = parse_kwargs_to_cli_args(**talos_args)
    cmd = ["talosctl", "get", resource_name, "-o", "json"] + additional_args
    cmd_result = Command.check_output(cmd, additional_error_msg=f"Can't get the talos resource: {resource_name}.")

    try:
        return json.loads(cmd_result)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        result = []
        while cmd_result:
            element, new_start = decoder.raw_decode(cmd_result)
            cmd_result = cmd_result[new_start:].strip()
            result.append(element)
        return result


def get_live_talos_extension_versions(**talos_args):
    """returns all live talos extensions with their respective versions"""
    extension_dicts: List[Dict] = get_talos_resource(resource_name="extensions", **talos_args)

    live_exts = {}
    for ext_d in extension_dicts:
        metadata: Dict = ext_d["spec"]["metadata"]
        author = metadata.get("author")
        if (author is None) or ("Talos Machinery" in author):
            continue
        live_exts.update({metadata.get("name"): metadata.get("version")})

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


def generate_mc(cluster_name: str, ttl_years: int, **talos_args):
    """generate a machine config with talosctl + generate and patch in root CAs

    Return: machine_config, talosconfig
    """
    additional_talos_args = parse_kwargs_to_cli_args(**talos_args)

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
        Command.check_output(base_cmd + additional_talos_args, capture_output=False)

        with open(controlplane_file) as file:
            controlplane_mc = yaml.safe_load(file)

        _patch_mc_with_custom_ca(controlplane_mc, ttl_years, cluster_name)
        talos_ca = controlplane_mc["machine"]["ca"]["crt"]
        talos_key = controlplane_mc["machine"]["ca"]["key"]

        controlplane_mc = bytes(json.dumps(controlplane_mc, indent=2), ENCODING)
        talosconfig = _generate_taloconfig(cluster_name, talos_ca, talos_key)

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


def patch_mc(mc: bytes, patch_files: Iterable[Path], validation=True, verbose=False):
    """patches mc with all local jq patch files and validates it for each patch"""
    for patch in patch_files:
        print_if(f"   patch: {patch.relative_to(REPO_ROOT)}", verbose)
        mc = patch_json(mc, patch, JQ_MODULES_DIR)
        # validate the mc after each patch
        if validation:
            validate_mc(mc)

    return mc.rstrip()


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
    additional_talos_args = parse_kwargs_to_cli_args(**talos_args)
    api_server_pod = f"kube-apiserver-{node_name}"
    port_forward_cmd = [
        "kubectl",
        "port-forward",
        "-n",
        "kube-system",
        f"pods/{api_server_pod}",
        "6443:6443",
        "--kubeconfig",
        K8S_CONFIG_USER
    ]
    print_if("Start port forwarding for the k8s api ...", verbose)
    # prepare the port forwarding
    port_forward_process = sp.Popen(port_forward_cmd, stdout=sp.DEVNULL, stderr=sp.PIPE)
    sleep(2)
    if port_forward_process.poll():  # test if the connection has terminated
        raw_error = port_forward_process.stderr.read()
        raise TyperAbort("Can't forward the the api-server to your machine:", raw_error.decode(ENCODING))
    print_if("Start the upgrade process ...", verbose)

    # execute the upgrade
    try:
        # upgrade and retry forwarding + finally kill the port forwarding process
        upgrade_process = sp.Popen(base_talos_cmd + additional_talos_args)
        while upgrade_process.poll() is None:  # as long as upgrade process not terminated (with or without success)
            if port_forward_process.poll() is not None:  # if forwarding terminated - restart forwarding process
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
    additional_args = parse_kwargs_to_cli_args(**talos_args)
    Command.check_output(base_cmd + additional_args)


def _generate_custom_ca(root_name: str, years_valid: int):
    """generate CA cert in "special" format for k8s, etcd, k8s aggregator"""
    root_key = ec.generate_private_key(ec.SECP256R1())
    root_key_serialized = root_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    options = [x509.NameAttribute(
        NameOID.ORGANIZATION_NAME, root_name)] if root_name else []
    subject = issuer = x509.Name(options)
    root_cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        root_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc)
    ).not_valid_after(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=years_valid * 365)
    ).add_extension(
        x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=True,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=True,
    ).add_extension(
        x509.ExtendedKeyUsage(
            [ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH,]),
        critical=False
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None),
        critical=True,
    ).add_extension(
        x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()),
        critical=False
    ).sign(root_key, hashes.SHA256())

    root_cert_serialized = root_cert.public_bytes(serialization.Encoding.PEM)
    b64_cert_str = base64.b64encode(root_cert_serialized).decode()
    b64_key_str = base64.b64encode(root_key_serialized).decode()

    return b64_cert_str, b64_key_str


def _gen_talos_ca(issuer: str, years_valid: int):
    """generate CA cert and key via talosctl for talos"""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cert_file, key_file = root / f"{issuer}.crt", root / f"{issuer}.key"
        Command.check_output(
            ["talosctl", "gen", "ca", f"--organization={issuer}", f"--hours={years_valid * 365 * 24}"], cwd=root
        )
        with open(cert_file, "rb") as f:
            cert_str = f.read()
        with open(key_file, "rb") as f:
            key_str = f.read()

    b64_cert_str = base64.b64encode(cert_str).decode()
    b64_key_str = base64.b64encode(key_str).decode()

    return b64_cert_str, b64_key_str


def _patch_mc_with_custom_ca(mc_dict: dict, years_valid: int, issuer: str):
    """create CA certs and key and patch them into given mc"""
    # generate talos ca cert, key
    b64_talos_cert_str, b64_talos_key_str = _gen_talos_ca(issuer, years_valid)
    # generate k8s ca cert, key
    b64_k8s_cert_str, b64_k8s_key_str = _generate_custom_ca("kubernetes", years_valid)
    # generate etcd ca cert, key
    b64_etcd_cert_str, b64_etcd_key_str = _generate_custom_ca("etcd", years_valid)
    # generate k8s-aggregator ca cert, key
    b64_k8s_agg_cert_str, b64_k8s_agg_key_str = _generate_custom_ca("", years_valid)

    mc_dict["cluster"]["ca"]["crt"] = b64_k8s_cert_str
    mc_dict["cluster"]["ca"]["key"] = b64_k8s_key_str
    mc_dict["cluster"]["aggregatorCA"]["crt"] = b64_k8s_agg_cert_str
    mc_dict["cluster"]["aggregatorCA"]["key"] = b64_k8s_agg_key_str
    mc_dict["cluster"]["etcd"]["ca"]["crt"] = b64_etcd_cert_str
    mc_dict["cluster"]["etcd"]["ca"]["key"] = b64_etcd_key_str
    mc_dict["machine"]["ca"]["crt"] = b64_talos_cert_str
    mc_dict["machine"]["ca"]["key"] = b64_talos_key_str


def _generate_taloconfig(context_name: str, ca_b64: str, ca_key_b64: str):
    client_cert_hours_valid = 10 * 365 * 24
    with tempfile.TemporaryDirectory() as td:
        # copy ca, key, in dir
        tmp_dir = Path(td)
        ca_file = tmp_dir / "talos.crt"
        with open(ca_file, "wb") as f:
            f.write(base64.b64decode(ca_b64))
        key_file = tmp_dir / "talos.key"
        with open(key_file, "wb") as f:
            f.write(base64.b64decode(ca_key_b64))

        sp.check_output(["talosctl", "gen", "key", "--name=client"], cwd=tmp_dir)
        sp.check_output(
            ["talosctl", "gen", "csr", "--key=client.key", "--ip", "127.0.0.1"],
            cwd=tmp_dir,
        )
        sp.check_output(
            [
                "talosctl",
                "gen",
                "crt",
                "--ca",
                "talos",
                "--csr=client.csr",
                "--name",
                "client",
                "--hours",
                str(client_cert_hours_valid),
            ],
            cwd=tmp_dir,
        )
        talosconfig_file = tmp_dir / "talosconfig"
        sp.check_output(
            [
                "talosctl",
                "--talosconfig",
                talosconfig_file,
                "config",
                "add",
                "--ca",
                ca_file,
                "--key",
                "client.key",
                "--crt",
                "client.crt",
                context_name,
            ],
            cwd=tmp_dir,
        )
        sp.check_output(
            [
                "talosctl",
                "--talosconfig",
                talosconfig_file,
                "config",
                "context",
                context_name,
            ],
            cwd=tmp_dir,
        )
        with open(talosconfig_file, "rb") as file:
            return file.read()
