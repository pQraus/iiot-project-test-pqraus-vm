import typer
from rich import print
from rich.table import Table

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _kubectl as kubectl
from .._utils import _talosctl as talosctl
from .._utils import _teleport as teleport
from .._utils._config import (BOX_NAME, K8S_VERSION,
                              TALOS_INSTALLED_EXTENSIONS, TALOS_VERSION,
                              TELEPORT_PROXY_URL)
from .._utils._constants import (DEP_JQ, DEP_KUBECTL, DEP_TALOSCTL, DEP_TSH,
                                 K8S_CONFIG_USER, TALOS_CONFIG_PROJECT)
from .._utils._installer_spec_config import (load_repo_extension_versions,
                                             load_repo_installer_image_ref)


def _print_current_extensions():
    """print current custom talos system extensions"""
    table = Table(title="Current extensions in repo and live:")
    table.add_column("NAME")
    table.add_column("VERSION")

    repo_extension_versions = load_repo_extension_versions(TALOS_INSTALLED_EXTENSIONS)

    for name, vers in repo_extension_versions.items():
        table.add_row(name, vers)

    print(table)
    print()


def _print_talos_overview_table(node_name: str, image: str, repo_vers: str, live_vers: str):
    """print table overview with names of selected talos node, talos image, talos versions"""
    table = Table(title="TALOS")
    table.add_column("NODE")
    table.add_column("INSTALLER IMAGE")
    table.add_column("REPO VERSION")
    table.add_column("LIVE VERSION")
    table.add_row(node_name, image, repo_vers, live_vers)
    print(table)
    print()


def _set_talos_upgrade_kwargs(image_ref: str, use_current_context: bool, verbose: bool, preserve: bool, stage: bool):
    """create dict with args to configure talos update process"""
    upgrade_args = {"image": image_ref, "preserve": preserve, "stage": stage}
    if not use_current_context:
        upgrade_args["talosconfig"] = TALOS_CONFIG_PROJECT.resolve()
    if verbose:
        upgrade_args["wait"] = True
        upgrade_args["debug"] = True
    else:
        upgrade_args["wait"] = False

    return upgrade_args


@check.dependency(*DEP_TALOSCTL)
def prepare_upgrade(use_current_context: bool):
    common.print_if(
        "Ensure that 'iiotctl connect talos' is running\n", not use_current_context
    )
    config_args = (
        {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )

    response: str = talosctl.image_default(**config_args)
    images = response.splitlines()
    images.remove(f"ghcr.io/siderolabs/installer:v{TALOS_VERSION}")

    for img in images:
        print(f"Pull image: '{img}' ...", end=" ")
        talosctl.image_pull(img, **config_args)
        print(":white_heavy_check_mark:")

    print("Preloading images done.\n")


@check.dependency(*DEP_TALOSCTL)
@check.dependency(*DEP_JQ)
def upgrade_talos(use_current_context: bool, preserve: bool, stage: bool, verbose: bool):

    common.print_if(
        "Ensure that 'iiotctl connect talos' is running\n", not use_current_context
    )
    config_args = (
        {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )
    live_talos_version = talosctl.get_live_talos_version(**config_args)
    node_name_rsrc = talosctl.get(resource="nodename", **config_args)
    node_name = node_name_rsrc["spec"]["nodename"]
    image_ref = load_repo_installer_image_ref(required_extensions=TALOS_INSTALLED_EXTENSIONS)
    _print_talos_overview_table(node_name, image_ref, TALOS_VERSION, live_talos_version)

    live_exts = talosctl.get_live_talos_extension_versions(**config_args)
    repo_exts = load_repo_extension_versions(required_extensions=TALOS_INSTALLED_EXTENSIONS)
    common.print_talos_extension_changes(repo_exts, live_exts)
    if live_exts == repo_exts:
        _print_current_extensions()
        print("There aren't any diffs between repo and live talos system extensions.")
        print("They are synced.")
        print()

    should_upgrade = typer.confirm("Start upgrading?")

    if should_upgrade:
        print()
        print("It takes a while (~ 5 min) before the machine can be reconnected.")
        print("It's necessary to restart the 'iiotctl connect talos' task.")
        upgrade_kwargs = _set_talos_upgrade_kwargs(image_ref, use_current_context, verbose, preserve, stage)
        talosctl.upgrade_talos(**upgrade_kwargs)


@check.dependency(*DEP_KUBECTL)
@check.dependency(*DEP_TALOSCTL)
@check.dependency(*DEP_TSH)
def upgrade_k8s(use_current_contexts: bool, dry_run: bool, verbose: bool):

    common.print_if(
        "Ensure that 'iiotctl connect talos' is running'\n",
        not use_current_contexts,
    )
    config_args = (
        {} if use_current_contexts else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )

    talosctl.get_live_talos_version(**config_args)

    node_name_rsrc = talosctl.get(resource="nodename", **config_args)
    node_name = node_name_rsrc["spec"]["nodename"]
    print(f"Selected talos node for the upgrade: {node_name}")
    print()

    if not use_current_contexts:
        teleport.login(TELEPORT_PROXY_URL)
        teleport.login_k8s(BOX_NAME)

    k8s_context = kubectl.get_current_context(K8S_CONFIG_USER)
    print(f"Selected k8s context for the upgrade: {k8s_context}")

    should_upgrade = typer.confirm(f"Start upgrading to k8s {K8S_VERSION} ?")
    print()

    if should_upgrade:
        talosctl.upgrade_k8s(node_name, K8S_VERSION, dry_run=dry_run, verbose=verbose)
