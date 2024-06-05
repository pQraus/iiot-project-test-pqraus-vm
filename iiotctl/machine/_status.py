from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _talosctl as talosctl
from .._utils._config import DEP_GPG, DEP_JQ, DEP_TALOSCTL
from .._utils._constants import DEFAULT_MACHINE_CONFIG_ID, TALOS_CONFIG_PROJECT
from .._utils._installer_spec_config import load_repo_extension_versions
from . import _talos_config as talos_config
from ._misc import (check_if_mc_diffs, check_if_talos_ext_diffs,
                    compare_mc_hash, create_new_mc, print_live_talos_nodename,
                    print_status_table)


@check.dependency(*DEP_GPG)
@check.dependency(*DEP_TALOSCTL)
@check.dependency(*DEP_JQ)
def status(out_diff: str, use_current_context: bool, verbose: bool):

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
    compare_mc_hash(hash_diff)

    if mc_out_of_sync:
        common.print_if("Check if a reboot is necessary to apply the new config...", verbose)

        apply_no_reboot = talosctl.apply_mc(
            new_mc, mode="no-reboot", dry_run=True, exit_on_failure=False, print_errors=False, **config_arg
        )
        # if mc can't be applied without reboot
        if not apply_no_reboot:
            # raise if mc can't be applied with reboot
            talosctl.apply_mc(new_mc, mode="reboot", dry_run=True, exit_on_failure=True, **config_arg)
            print("The new config must be applied with a reboot")
        else:
            print("The new config can be applied without a reboot")

    # reminder to upgrade talos if there are changes to installer image (e.g. the system talos extensions)
    if exts_out_of_sync:
        print("Out of sync talos extensions => Executing 'iiotctl machine upgrade-talos' is required!")
