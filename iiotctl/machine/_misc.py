from typing import Dict

from rich import print
from rich.table import Table

from .._utils import _common as common
from .._utils import _talosctl as talosctl
from .._utils._common import TyperAbort
from .._utils._config import K8S_VERSION, TALOS_VERSION
from .._utils._constants import (EXCLUDE_SYNC_PATCHES, PATCH_LOCATIONS,
                                 REPO_ROOT)
from .._utils._installer_spec_config import load_repo_extension_versions


def print_live_talos_nodename(**config_arg):
    """fetches nodename from live talos machine; prints it to STDOUT"""
    node_name_rsrc = talosctl.get_talos_resource("nodename", **config_arg)
    node_name = node_name_rsrc["spec"]["nodename"]
    print()
    print(f"Selected talos node: '{node_name}'")
    print()


def check_if_talos_ext_diffs(live_exts: Dict[str, str], repo_exts: Dict[str, str]):
    """checks if live and repo talos extensions are unequal"""
    if live_exts != repo_exts:
        print("[bold]The talos system extensions are out of sync:[/]\n")
        common.print_talos_extension_changes(load_repo_extension_versions(), live_exts)
        return True
    else:
        return False


def check_if_mc_diffs(diffs: str):
    """checks if live and repo machine configs are unequal"""
    if diffs:
        print("[bold]The machine config is out of sync:[/]\n")
        print(diffs)
        print()
        return True
    else:
        return False


def print_status_table(live_talos_vers: str, live_k8s_vers: str, mc_diffs: bool, ext_diffs: bool, hash_diffs: bool):
    """showcase overview of repo and live machine statuses"""
    talos_vers_diff = live_talos_vers != TALOS_VERSION
    k8s_vers_diff = live_k8s_vers != K8S_VERSION

    table = Table(title="Summary", show_lines=True)
    table.add_column("Synced", justify="center")
    table.add_column("Name")
    table.add_column("Status")

    table.add_row(
        ":x:" if talos_vers_diff else ":white_heavy_check_mark:",
        "Talos version",
        f"repo: '{TALOS_VERSION}' | live: '{live_talos_vers}'"
    )
    table.add_row(
        ":x:" if k8s_vers_diff else ":white_heavy_check_mark:",
        "K8s version",
        f"repo: '{K8S_VERSION}' | live: '{live_k8s_vers}'"
    )
    table.add_row(
        ":x:" if mc_diffs else ":white_heavy_check_mark:",
        "Machine config",
        "out of sync" if mc_diffs else "synced"
    )
    table.add_row(
        ":x:" if hash_diffs else ":white_heavy_check_mark:",
        "Machine config hash",
        "out of sync" if hash_diffs else "synced"
    )
    table.add_row(
        ":x:" if ext_diffs else ":white_heavy_check_mark:",
        "Talos extensions",
        "out of sync" if ext_diffs else "synced"
    )

    print(table)
    print()


def create_new_mc(live_mc: bytes, verbose: bool):
    """create live mc from repo mc anda list of local patch files; return new mc"""
    exc_patch_files = common.glob_files(REPO_ROOT, *EXCLUDE_SYNC_PATCHES)
    patch_files = [f for f in common.glob_files(REPO_ROOT, *PATCH_LOCATIONS) if f not in exc_patch_files]

    new_mc = live_mc
    common.print_if("", verbose)
    common.print_if("Create a patched version of the live machine config ...", verbose)
    new_mc = talosctl.patch_mc(new_mc, patch_files, verbose=verbose)
    return new_mc


def compare_mc_hash(hash_diff: bool, check=False):
    if hash_diff:
        print("Diff between saved machine config hash and live machine config hash")
        print("Maybe there was a machine config change without using the 'iiotctl machine sync' task?")
        if check:
            print()
            raise TyperAbort("Run 'iiotctl machine seal-config' to explicitly overwrite the hash and seal mc")
