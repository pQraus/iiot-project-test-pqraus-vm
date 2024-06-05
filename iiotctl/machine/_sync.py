from datetime import datetime
from pathlib import Path

import typer
from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _talosctl as talosctl
from .._utils._common import TyperAbort
from .._utils._config import (DEP_GPG, DEP_JQ, DEP_TALOSCTL, K8S_VERSION,
                              TALOS_VERSION)
from .._utils._constants import DEFAULT_MACHINE_CONFIG_ID, TALOS_CONFIG_PROJECT
from .._utils._installer_spec_config import load_repo_extension_versions
from . import _talos_config as talos_config
from ._misc import (check_if_mc_diffs, check_if_talos_ext_diffs,
                    compare_mc_hash, create_new_mc, print_live_talos_nodename,
                    print_status_table)


def _compare_repo_and_live_talos_version(live_talos_vers: str, force: bool):
    """print warning if repo != live talos versions; without 'force' raise if unequal"""
    version_diff_talos = bool(live_talos_vers != TALOS_VERSION)
    if version_diff_talos:
        print("You should upgrade talos to the expected version\n")
    if version_diff_talos and not force:
        raise TyperAbort("Run this task with --force to ignore the talos version diff")


def _compare_repo_and_live_k8s_versions(live_k8s_vers: str, force: bool):
    """print warning if repo != live k8s versions; without 'force' raise if unequal"""
    version_diff_k8s = bool(live_k8s_vers != K8S_VERSION)
    if version_diff_k8s:
        print("You should upgrade k8s to the expected version\n")
    if version_diff_k8s and not force:
        raise TyperAbort("Run this task with --force to ignore the k8s version diff")


def _backup_mc(mc: bytes, out_backup: str):
    """save live mc to local directory as backup"""
    date_time = datetime.now().strftime("%Y-%m-%d#%H:%M:%S")
    file_name = Path(out_backup).name
    file_parts = file_name.split(".")

    if len(file_parts) > 1:
        file_name = file_parts[0] + f"({date_time})." + ".".join(file_parts[1:])
    else:
        file_name = file_name + f"({date_time})"

    dst_dir = Path(out_backup).parent
    out_backup: Path = dst_dir / file_name

    with open(out_backup, "wb") as f_backup:
        # write machine config into backup file
        f_backup.write(mc)

    print()
    print(f"The backup of the mc is saved at:\n'{out_backup}'\n")


@check.dependency(*DEP_GPG)
@check.dependency(*DEP_TALOSCTL)
@check.dependency(*DEP_JQ)
def sync(
    force: bool,
    out_backup: str,
    out_diff: str,
    apply_mode: str,
    dry_run: bool,
    use_current_context: bool,
    verbose: bool,
):

    common.print_if(
        "Ensure that 'iiotctl connect talos' is running", not use_current_context
    )
    config_arg = (
        {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )

    live_mc = talosctl.fetch_mc(DEFAULT_MACHINE_CONFIG_ID, **config_arg)
    live_talos_version = talosctl.get_live_talos_version(**config_arg)
    live_k8s_version = talosctl.get_live_k8s_version(live_mc)

    print_live_talos_nodename(**config_arg)

    new_mc = create_new_mc(live_mc, verbose)
    mc_diffs = common.diffs_mc(live_mc, new_mc, out_diff)
    live_exts = talosctl.get_live_talos_extension_versions(**config_arg)

    exts_out_of_sync = check_if_talos_ext_diffs(live_exts, load_repo_extension_versions())
    mc_out_of_sync = check_if_mc_diffs(mc_diffs)
    hash_diff = talos_config.is_mc_hash_diff(live_mc)
    print_status_table(live_talos_version, live_k8s_version, mc_out_of_sync, exts_out_of_sync, hash_diff)

    _compare_repo_and_live_talos_version(live_talos_version, force)
    _compare_repo_and_live_k8s_versions(live_k8s_version, force)
    compare_mc_hash(hash_diff, check=True)

    if mc_out_of_sync:
        print(f"Test if the new config can be applied in '{apply_mode}' mode (via dry-run) ...")
        # dry-run apply, raise if not possible
        talosctl.apply_mc(
            new_mc, mode=apply_mode, dry_run=True, exit_on_failure=True, print_errors=False, **config_arg
        )

        print(f"The config can be applied via '{apply_mode}'\n")

        if dry_run:
            print("Syncing in dry-run mode finished successfully")

        prompt = f"Do you want to apply the new config (in '{apply_mode}' mode)?"
        should_apply = False if dry_run else typer.confirm(prompt)
        if should_apply:
            if out_backup:
                _backup_mc(live_mc, out_backup)
            talosctl.apply_mc(new_mc, mode=apply_mode, **config_arg)
            print("Syncing finished successfully")

            talos_config.seal(new_mc)

    # reminder to upgrade talos if there are changes to installer image (e.g. the system talos extensions)
    if exts_out_of_sync:
        print("Out of sync talos extensions => Executing 'iiotctl machine upgrade-talos' is required!")
