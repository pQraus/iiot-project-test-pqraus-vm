import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from invoke import task

from .. import _common as common
from .. import _mc_sealer as mc_sealer
from .. import _talosctl as talosctl
from .._config import (DEFAULT_MACHINE_CONFIG_ID, DEP_GPG, DEP_JQ,
                       DEP_TALOSCTL, ENCODING, EXCLUDE_SYNC_PATCHES, K8S_VERSION,
                       PATCH_LOCATIONS, REPO_ROOT, TALOS_CONFIG_PROJECT,
                       TALOS_EXTENSIONS, TALOS_VERSION, TASKS_TMP_DIR)


def _evaluate_talos_ext_diffs(remote_exts: Dict[str, str], local_exts: Dict[str, str]):
    """checks if remote and local talos extensions are unequal"""
    if remote_exts != local_exts:
        print("Your talos system extensions are out of sync.\n")
        common.print_talos_extension_changes(TALOS_EXTENSIONS, remote_exts)
        return True
    else:
        print("There aren't any diffs between remote and local talos system extensions.")
        print("They are synced.")
        print()
        return False


def _evaluate_mc_diffs(diffs: str):
    """checks if remote and local machine configs are unequal"""
    if diffs:
        print("Your machine config is out of sync:\n")
        print(diffs)
        print()
        return True
    else:
        print("There aren't any diffs between the remote and the local machine config.")
        print("They are synced.")
        print()
        return False


def _dry_run_mc_apply(mc: str, mode: str, **config_arg):
    """dry-run tests the applying of machine config to remote machine"""
    result = talosctl.apply_mc(
        mc, exit_on_failure=False, mode=mode, dry_run=True, **config_arg
    )
    return result


def _print_remote_talos_nodename(**config_arg):
    """fetches nodename from remote talos machine; prints it to STDOUT"""
    node_name_rsrc = talosctl.get_talos_resource("nodename", **config_arg)
    node_name = node_name_rsrc["spec"]["nodename"]
    print(f"Selected talos node: {node_name}")


def _compare_local_and_remote_talos_version(force=False, check=False, **config_arg):
    """print remote and local talos versions; with 'check' exits if unequal"""
    current_talos_version = talosctl.get_current_talos_version(**config_arg)
    print(f"Current talos version on machine: {current_talos_version}")
    print(f"Expected talos version: {TALOS_VERSION}\n")
    if check:
        version_diff_talos = bool(current_talos_version != TALOS_VERSION)
        if version_diff_talos:
            print("You should upgrade talos to the expected version\n")
        if version_diff_talos and not force:
            print("Abort; run this task with --force to ignore the talos version diff", file=sys.stderr)
            exit(1)


def _compare_local_and_remote_k8s_versions(current_mc: bytes, force=False, check=False):
    """print remote and local k8s versions; with 'check' exits if unequal"""
    current_k8s_version = talosctl.get_current_k8s_version(current_mc)
    print(f"Current k8s version on machine: {current_k8s_version}")
    print(f"Expected k8s version: {K8S_VERSION}")
    if check:
        version_diff_k8s = current_k8s_version != K8S_VERSION
        if version_diff_k8s:
            print("You should upgrade k8s to the expected version\n")
        if version_diff_k8s and not force:
            print("Abort; run this task with --force to ignore the k8s version diff", file=sys.stderr)
            exit(1)


def _compare_mc_hash(current_mc: bytes, check=False):
    hash_diff = mc_sealer.is_mc_hash_diff(current_mc)
    if hash_diff:
        print()
        print("Diff between saved machine config hash and live machine config hash")
        print("Maybe there was a machine config change without using the invoke sync task?")
        if check:
            print()
            print("Abort, run 'invoke seal-mc' to explicitly overwrite the hash and seal mc", file=sys.stderr)
            exit(1)


def _backup_mc(mc: bytes, out_backup: str):
    file_name = Path(out_backup).name
    dst_dir = Path(out_backup).parent
    files = [file.name for file in common.glob_files(dst_dir, "*")]

    # update filename if it already exists: file(1).json => file(2).json => ...
    i = 1
    while file_name in files:
        new_file_name = Path(out_backup).name
        file_name = new_file_name.split(".")[0] + f"({i})." + new_file_name.split(".")[1]
        i += 1

    out_backup = dst_dir / file_name
    with open(out_backup, "w") as f_backup:
        # write timestamp at top of backup file
        date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f_backup.write("// CREATED AT: " + date_time + " (REMOVE TO MAKE JSON VALID AGAIN)\n")
        # write machine config into backup file
        f_backup.write(json.dumps(json.loads(mc), indent=2))

    print()
    print(f"The backup of the mc is saved at:\n{out_backup}\n")


@task(
    optional=["use_current_context"],
    help={
        "use_current_context": "(optional) use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used",
    }
)
@common.check_dependency(*DEP_GPG)
@common.check_dependency(*DEP_TALOSCTL)
def seal_mc(c, use_current_context=False):
    """
    seal the current machine config and save it in the repo

    EXAMPLES:

    Call without optional arguments to seal and hash the live machine config (only when there is a hash diff):
    >>> invoke seal-mc
    """
    common.print_if(
        "Ensure that 'invoke connect-talos' is running", not use_current_context
    )
    config_arg = (
        {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )

    current_mc = talosctl.fetch_mc(DEFAULT_MACHINE_CONFIG_ID, **config_arg)
    if mc_sealer.is_mc_hash_diff(current_mc):
        print("Create new hash and sealed mc")
        mc_sealer.seal_mc(current_mc)
    else:
        print("There isn't a diff between the remote and the local machine config hash.")
        print("Nothing to do.")


@task(
    optional=["out_diff", "use_current_context"],
    help={
        "out_diff": "(optional) output file for the diffs in the machine config",
        "use_current_context": "(optional) use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used",
        "verbose": "verbose status messages",
    },
)
@common.check_dependency(*DEP_GPG)
@common.check_dependency(*DEP_TALOSCTL)
@common.check_dependency(*DEP_JQ)
def status(c, out_diff: Optional[str] = None, use_current_context=False, verbose=False):
    """
    check the current state of the machine in comparison to this repo

    EXAMPLES:

    Call without optional arguments to see the differences between local and box machine config printed in the console:
    >>> invoke status

    Call with argument '--out-diff' to export differences between local and box machine config to file:
    >>> invoke status --out-diff "diffs.txt"
    """

    common.print_if(
        "Ensure that 'invoke connect-talos' is running", not use_current_context
    )
    config_arg = (
        {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )

    # get the k8s version from the remote machine config
    current_mc = talosctl.fetch_mc(DEFAULT_MACHINE_CONFIG_ID, **config_arg)

    _print_remote_talos_nodename(**config_arg)
    _compare_local_and_remote_talos_version(**config_arg)
    _compare_local_and_remote_k8s_versions(current_mc)
    _compare_mc_hash(current_mc)

    exc_patch_files = common.glob_files(REPO_ROOT, *EXCLUDE_SYNC_PATCHES)
    patch_files = [f for f in common.glob_files(REPO_ROOT, *PATCH_LOCATIONS) if f not in exc_patch_files]

    new_mc = current_mc

    common.print_if("", verbose)
    common.print_if("Create a patched version of the current machine config ...", verbose)
    new_mc = talosctl.patch_mc(new_mc, patch_files, verbose)

    print()
    mc_diffs = common.diffs_mc(current_mc, new_mc, out_diff)
    remote_exts = talosctl.get_remote_talos_extension_versions(**config_arg)

    exts_out_of_sync = _evaluate_talos_ext_diffs(remote_exts, TALOS_EXTENSIONS)
    mc_out_of_sync = _evaluate_mc_diffs(mc_diffs)

    if mc_out_of_sync:
        common.print_if("Check if a reboot is necessary to apply the new config...", verbose)

        apply_no_reboot = _dry_run_mc_apply(new_mc, "no-reboot", **config_arg)
        if apply_no_reboot.returncode:  # if mc can't be applied without reboot
            apply_reboot = _dry_run_mc_apply(new_mc, "reboot", **config_arg)
            if apply_reboot.returncode:  # if mc can't be applied with reboot
                print("The new config can't be applied in reboot mode (via dry-run):", file=sys.stderr)
                print(apply_reboot.stderr.decode(ENCODING), file=sys.stderr)
                exit(1)

            print("The new config must be applied with a reboot")
        else:
            print("The new config can be applied without a reboot")

    # reminder to upgrade talos if there are changes to installer image (e.g. the system talos extensions)
    if exts_out_of_sync:
        print("Executing 'invoke upgrade-talos' is required!")


@task(
    optional=["out_diff", "apply_mode"],
    help={
        "force": "ignore version conflicts for talos and k8s in comparison to the repo",
        "out_backup": f" (default: {(TASKS_TMP_DIR / 'mc-backup.json').relative_to(REPO_ROOT)})",
        "out_diff": "output file for the diffs in the machine config",
        "apply_mode": "mode for applying the machine config (default: no-reboot) (see talosctl apply-config -h)",
        "use_current_context": "use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used",
        "dry_run": "sync without applying the new config",
        "verbose": "verbose status messages",
    },
)
@common.check_dependency(*DEP_GPG)
@common.check_dependency(*DEP_TALOSCTL)
@common.check_dependency(*DEP_JQ)
def sync(
    c,
    force=False,
    out_backup=str((TASKS_TMP_DIR / "mc-backup.json").absolute()),
    out_diff: Optional[str] = None,
    apply_mode="no-reboot",
    dry_run=False,
    use_current_context=False,
    verbose=False,
):
    """
    sync the machine with the config from this repo

    EXAMPLES:

    Call without optional arguments to see the differences between local and box machine config printed in the console
    and then choose if the local machine config changes should be applied to the box:
    >>> invoke sync

    Call with argument '--out-diff' to export differences between local and box machine config to file:
    >>> invoke sync --out-diff "diffs.txt"

    Call with argument '--apply-mode' to specify a mode used by talosctl to apply the machine config
    to the box and then reboot talos on it:
    >>> invoke sync --apply-mode reboot

        Other apply modes are: [auto, interactive, staged, try, (default:) no-reboot]
    """

    common.print_if(
        "Ensure that 'invoke connect-talos' is running", not use_current_context
    )
    config_arg = (
        {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )

    # get the k8s version from the remote machine config
    current_mc = talosctl.fetch_mc(DEFAULT_MACHINE_CONFIG_ID, **config_arg)

    _print_remote_talos_nodename(**config_arg)
    _compare_local_and_remote_talos_version(force, check=True, **config_arg)
    _compare_local_and_remote_k8s_versions(current_mc, force, check=True)
    _compare_mc_hash(current_mc, check=True)

    exc_patch_files = common.glob_files(REPO_ROOT, *EXCLUDE_SYNC_PATCHES)
    patch_files = [f for f in common.glob_files(REPO_ROOT, *PATCH_LOCATIONS) if f not in exc_patch_files]

    new_mc = current_mc
    common.print_if("", verbose)
    common.print_if("Create a patched version of the current machine config ...", verbose)
    new_mc = talosctl.patch_mc(new_mc, patch_files, verbose)

    print()
    mc_diffs = common.diffs_mc(current_mc, new_mc, out_diff)
    remote_exts = talosctl.get_remote_talos_extension_versions(**config_arg)

    exts_out_of_sync = _evaluate_talos_ext_diffs(remote_exts, TALOS_EXTENSIONS)
    mc_out_of_sync = _evaluate_mc_diffs(mc_diffs)

    if mc_out_of_sync:
        print(f"Test if the new config can be applied in '{apply_mode}' mode (via dry-run) ...")
        apply_dry_run = _dry_run_mc_apply(new_mc, apply_mode, **config_arg)
        if apply_dry_run.returncode:
            print(f"The config can't be applied in '{apply_mode}' mode, change to another one")
            return

        print(f"The config can be applied in '{apply_mode}'\n")

        if dry_run:
            print("Synching in dry-run mode finished successfully")

        prompt = f"Do you want to apply the new config (in '{apply_mode}' mode)? [y/n] "
        should_apply = False if dry_run else common.check_user_choice(prompt)
        if should_apply:
            if out_backup:
                _backup_mc(current_mc, out_backup)
            talosctl.apply_mc(new_mc, mode=apply_mode, **config_arg)
            print("Synching finished successfully")

            if not dry_run and apply_mode != "staged":
                mc_sealer.seal_mc(new_mc)

    # reminder to upgrade talos if there are changes to installer image (e.g. the system talos extensions)
    if exts_out_of_sync:
        print("Executing 'invoke upgrade-talos' is required!")
