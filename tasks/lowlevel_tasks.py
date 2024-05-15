import base64
import json
import shutil
import subprocess as sp
import sys
from difflib import unified_diff
from pathlib import Path
from typing import List

from invoke import task

from . import _common as common
from . import _talosctl as talosctl
from . import _teleport as teleport
from ._config import (BOX_NAME, DEFAULT_MACHINE_CONFIG_ID, DEP_HELM, DEP_JQ,
                      DEP_KUBECTL, DEP_TALOSCTL, DEP_TCTL, DEP_TSH, DEP_YQ,
                      ENCODING, EXCLUDE_SYNC_PATCHES, JQ_MODULES_DIR,
                      K8S_CONFIG_USER, LOCAL_K8S_ACCESS, PATCH_LOCATIONS,
                      REPO_ROOT, TALOS_CONFIG_PROJECT, TALOS_CONFIG_USER,
                      TALOS_INSTALLER)


@task(
    optional=["machine_ip", "ttl", "talosconfig"],
    help={
        "machine_ip": "local IP-address of the machine",
        "ttl": "certificate's time to live (default 2h) ",
        "talosconfig": f"the talosconfig in which the certificate should be inserted / updated (default: {TALOS_CONFIG_USER.absolute()}"
    },
)
@common.check_dependency(*DEP_KUBECTL)
@common.check_dependency(*DEP_TALOSCTL)
@common.check_dependency(*DEP_TSH)
@common.check_dependency(*DEP_TCTL)
@common.check_dependency(*DEP_YQ)
def create_local_certs(
    c,
    machine_ip,
    ttl="2h",
    talosconfig=TALOS_CONFIG_USER.absolute()
):
    """
    create local certs to access the machine's talos and k8s api on a local network

    EXAMPLES:

    Call with argument '--ttl' to change the time the to-be-created certificate is valid:
    >>> invoke lowlevel.create-local-certs 192.168.117.129 --ttl 5h
    """

    if not common.validate_ip(machine_ip):
        exit(1)

    print("Create a teleport certificate to access the machine's talos and k8s api locally ...")
    teleport.login()
    teleport_cert, teleport_key = teleport.create_local_cert(ttl)
    cert_b64 = base64.b64encode(teleport_cert)
    key_b64 = base64.b64encode(teleport_key)

    # create a new context name for the talosconfig:
    new_context = f"{BOX_NAME}-local-crt"
    # get the root ca from the /machine/talosconfig-teleport file of the project
    root_ca = sp.check_output(
        ["yq", f".contexts.{BOX_NAME}.ca", TALOS_CONFIG_PROJECT]
    )

    context_values = {
        "endpoints": [f"{machine_ip}:51001"],
        "nodes": [machine_ip],
        "ca": root_ca.decode(ENCODING).replace("\n", ""),
        "crt": cert_b64.decode(ENCODING),
        "key": key_b64.decode(ENCODING),
    }
    context_values_converted = json.dumps(context_values)

    print(f"Insert / Update context with name '{new_context}' in {talosconfig.absolute()} ...")
    upsert_context_filter = f'.contexts."{new_context}" = {context_values_converted}'
    # add local talos context into talosconfig
    sp.check_output(["yq", "-i", upsert_context_filter, talosconfig])
    # set talos current-context
    sp.check_output(["talosctl", "config", "context", new_context])

    if not LOCAL_K8S_ACCESS:
        return

    user = BOX_NAME + "-local"
    print(f"Insert / Update cluster, context, user with name '{user}' in {K8S_CONFIG_USER} ...")

    # add local k8s cluster into kubeconfig
    sp.check_output(["kubectl", "config", "set-cluster", user, "--server", "https://" + machine_ip + ":51011"])
    sp.check_output(["kubectl", "config", "set", f"clusters.{user}.certificate-authority-data", root_ca])

    # add local k8s context into kubeconfig
    sp.check_output(["kubectl", "config", "set-context", user, "--cluster", user, "--user", user])

    # add local k8s user into kubeconfig
    sp.check_output(["kubectl", "config", "set-credentials", user])
    sp.check_output(["kubectl", "config", "set", f'users.{user}.client-certificate-data', cert_b64.decode()])
    sp.check_output(["kubectl", "config", "set", f'users.{user}.client-key-data', key_b64.decode()])

    # set kube current-context
    sp.check_output(["kubectl", "config", "use-context", user])


@task(help={"file_a": "path to file a", "file_b": "path to file b"})
def diff(c, file_a: str, file_b: str):
    """
    print diffs between file a and file b

    EXAMPLES:

    Call with arguments 'file_a' and 'file_b' to print out the differences in the files contents:
    >>> invoke lowlevel.diff "/foo/mc1.json" "/bar/mc2.json"
    """

    f_a_location = Path(file_a)
    f_b_location = Path(file_b)
    with (
        open(f_a_location.absolute()) as f_a,
        open(f_b_location.absolute()) as f_b,
    ):
        a = f_a.readlines()
        b = f_b.readlines()
        diffs = unified_diff(a, b, fromfile=f_a_location.name, tofile=f_b_location.name)
    print("".join(diffs), end="")


@task(
    optional=["use_current_context"],
    help={
        "id": f"fetch machine config with certain id (default: {DEFAULT_MACHINE_CONFIG_ID})",
        "use_current_context": "(optional) use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used"
    },
)
@common.check_dependency(*DEP_JQ)
@common.check_dependency(*DEP_TALOSCTL)
def fetch(c, id=DEFAULT_MACHINE_CONFIG_ID, use_current_context=False):
    """
    fetch a current machine config by id from the remote machine

    EXAMPLES:

    Call with argument '--use-current-context' to connect via the currently selected talos context.
    >>> invoke lowlevel.fetch --use-current-context

        Useful if you want to connect via local talos cert and context, without teleport.
    """

    config_arg = (
        {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )
    print(talosctl.fetch_mc(id, **config_arg).decode(ENCODING), end="")


@task(
    help={
        "gen": "generate blank mc instead of fetching it from machine before patching it",
        "use_current_context": "(optional) use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used",
        "verbose": "(optional) verbose status messages",
    },
)
@common.check_dependency(*DEP_TALOSCTL)
@common.check_dependency(*DEP_YQ)
def create_mc(
    c,
    gen=False,
    use_current_context=False,
    verbose=False,
):
    """
    fetch current mc from machine / generate new mc; patch it with jq patch files from local repo

    EXAMPLES:

    Call without arguments while connected to talos machine to get the machine mc and patch it with
    non-boot-related jq patch files. Pipe the resulting mc into a json file for better readability:
    >>> invoke lowlevel.create-mc > mc.json

    Call with argument '--gen' to generate a blank mc before patching it with all jq patch files.
    Pipe the resulting mc into a json file for better readability:
    >>> invoke lowlevel.create-mc --gen > mc.json

    Call with argument '--use-current-context' to connect via the currently selected talos context:
    >>> invoke lowlevel.create-mc --use-current-context

        Useful if you want to connect via local talos cert and context, without teleport.
    """

    if gen:
        mc, _ = talosctl.generate_mc(BOX_NAME, install_image=TALOS_INSTALLER)
        patch_files = common.glob_files(REPO_ROOT, *PATCH_LOCATIONS)
    else:
        config_arg = (
            {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
        )
        mc = talosctl.fetch_mc(**config_arg)
        exc_patch_files = common.glob_files(REPO_ROOT, *EXCLUDE_SYNC_PATCHES)
        patch_files = [f for f in common.glob_files(REPO_ROOT, *PATCH_LOCATIONS) if f not in exc_patch_files]

    if verbose:
        print("\nCreate an initial machine config with patches ...", file=sys.stderr)

    for patch in patch_files:
        if verbose:
            print(f"   patch: {patch.relative_to(REPO_ROOT)}", file=sys.stderr)
        mc = common.patch_json(mc, patch, JQ_MODULES_DIR)
        # validate the mc after each patch
        talosctl.validate_mc(mc)

    print(mc.decode(ENCODING), end="")


@task(
    iterable=["patch_file_pattern"],
    optional=["root_dir"],
    help={
        "patch_file_pattern": "glob pattern(s) to find the patches multiple patterns accepted",
        "root_dir": f"use the glob pattern(s) on this dir (default: {REPO_ROOT.resolve()})",
        "validation": "validate the machine config after every patch (default: true)",
    },
)
@common.check_dependency(*DEP_TALOSCTL)
@common.check_dependency(*DEP_JQ)
def patch(
    c,
    patch_file_pattern: List[str],
    root_dir: str = REPO_ROOT.resolve(),
    validation=True,
):
    """
    patch config from STDIN with patches from file glob patterns

    EXAMPLES:

    Call with the to-be-patched content of the machine config piped into STDIN and use argument '--patch-file-pattern'
    to specify via filename pattern which patch files should be used to patch the machine config:
    >>> cat mc.json | lowlevel.patch --patch-file-pattern "machine/config/*/*.jq", "system-apps/*/machine-patches/*.jq"

    Call with additional argument '--root-dir' to specify from which directory patch files, which names fit the given
    glob pattern, should be used to patch the machine config:
    >>> cat mc.json | lowlevel.patch --patch-file-pattern "*/machine-patches/*.jq" --root-dir "system-apps"
    """

    root = Path(root_dir)
    patch_files = common.glob_files(root, *patch_file_pattern)

    new_mc = sys.stdin.buffer.read()  # read piped-in file content
    talosctl.validate_mc(new_mc)
    new_mc = talosctl.patch_mc(new_mc, patch_files, validation=validation)

    print(new_mc.decode(ENCODING), end="")


@task(
    iterable=["apps"],
    help={
        "apps": "one or more specific system-apps or user-apps to create collective deployment manifests for"
    },
)
@common.check_dependency(*DEP_HELM)
@common.check_dependency(*DEP_KUBECTL)
def kustomize_argo_templates(c, apps: List[str] = []):
    """
    create a collective deployment manifest for each system-app and user-app with 'argo-template' directory;
    put manifest unter /APP_NAME/argo/APP_NAME.yaml

    EXAMPLES:

    Call without arguments to create collective deployment manifests for all system-apps and user-apps
    in their respective /argo directory:
    >>> invoke lowlevel.kustomize-argo-templates

    Call with additional argument '--apps' ('-a') if you want to create collective
    deployment manifests only for certain system-apps and/or user-apps:
    >>> invoke lowlevel.kustomize-argo-templates -a "openebs" -a "traefik
    """

    if not apps:
        apps = ["*"]

    # selection of argo-templates to be kustomized
    templates_locations = [f"system-apps/{app}/argo-template" for app in apps]  # templates for system-apps
    templates_locations.extend([f"user-apps/{app}/argo-template" for app in apps])  # templates for user-apps
    template_paths = common.glob_files(REPO_ROOT, *templates_locations)

    for path in template_paths:
        relative_path = str(path.relative_to(REPO_ROOT))
        absolute_path = str(path.absolute())
        manifest = "/argo/" + absolute_path.split("/")[-2] + ".yaml"

        print(f"Kustomizing template: '{relative_path}' > '{relative_path.replace('/argo-template', manifest)}' ...")

        # remove old helm chart dir to ensure usage of correct resources
        shutil.rmtree(path / "charts", ignore_errors=True)

        # if no argo directory exists in app dir >> create new one
        if not (path.parent / "argo").exists():
            (path.parent / "argo").mkdir(exist_ok=True)

        # kustomize selection of argo-templates and transfer output into /argo/APP_NAME.yaml files
        sp.check_output(
            [
                "kubectl",
                "kustomize",
                "--enable-helm",
                absolute_path,
                "-o",
                absolute_path.replace("/argo-template", manifest)
            ]
        )
