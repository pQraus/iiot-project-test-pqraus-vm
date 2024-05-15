import subprocess as sp

from invoke import task

from .. import _common as common
from .. import _talosctl as talosctl
from .. import _teleport as teleport
from .._config import (DEP_JQ, DEP_KUBECTL, DEP_TALOSCTL, DEP_TSH, ENCODING,
                       K8S_VERSION, TALOS_CONFIG_PROJECT, TALOS_EXTENSIONS,
                       TALOS_INSTALLER, TALOS_VERSION)


@task(
    help={
        "use_current_contexts": "use the current selected talos and k8s context instead of config from the repo",
        "dry_run": "execute the upgrade in dry-run mode",
        "verbose": "verbose status messages"
    },
)
@common.check_dependency(*DEP_KUBECTL)
@common.check_dependency(*DEP_TALOSCTL)
@common.check_dependency(*DEP_TSH)
def upgrade_k8s(c, use_current_contexts=False, dry_run=False, verbose=False):
    """
    upgrade k8s to the version which is specified in the repo

    EXAMPLES:

    Call with argument '--use-current-contexts' to connect to the machine's talos and k8s APIs via the currently
    selected contexts. Not with the remote machine's contexts via teleport:
    >>> invoke upgrade-k8s --use-current-contexts

        Useful if you want to connect via local k8s + talos certs and contexts, without teleport.
    """

    common.print_if(
        "Ensure that 'invoke connect-talos' is running and you have executed 'invoke connect-k8s'\n",
        not use_current_contexts,
    )
    config_arg = (
        {} if use_current_contexts else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )
    talosctl.get_current_talos_version(**config_arg)

    node_name_rsrc = talosctl.get_talos_resource("nodename")
    node_name = node_name_rsrc["spec"]["nodename"]
    print(f"Selected talos node for the upgrade: {node_name}")

    if not use_current_contexts:
        teleport.login()
        teleport.login_k8s()

    get_k8s_context_cmd = ["kubectl", "config", "current-context"]
    k8s_context = sp.check_output(get_k8s_context_cmd).decode(ENCODING)
    print(f"Selected k8s context for the upgrade: {k8s_context}")

    should_upgrade = common.check_user_choice(f"Start upgrading to k8s {K8S_VERSION}? [y/n] ")
    print()

    if should_upgrade:
        talosctl.upgrade_k8s(node_name, K8S_VERSION, dry_run=dry_run, verbose=verbose)


@task(
    help={
        "use_current_context": "(optional) use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used",
        "preserve": "preserve data on disk",
        "stage": "stage the upgrade to perform it after a reboot",
        "verbose": "verbose upgrade messages",
    },
)
@common.check_dependency(*DEP_TALOSCTL)
@common.check_dependency(*DEP_JQ)
def upgrade_talos(c, use_current_context=False, preserve=True, stage=True, verbose=False):
    """
    upgrade talos to the version which is specified in the repo

    Call with argument '--use-current-context' to connect via the currently selected talos context.
    >>> invoke upgrade-talos --use-current-context

        Useful if you want to connect via local talos cert and context, without teleport.
    """

    common.print_if(
        "Ensure that 'invoke connect-talos' is running\n", not use_current_context
    )
    config_arg = (
        {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )
    current_talos_version = talosctl.get_current_talos_version(**config_arg)
    node_name_rsrc = talosctl.get_talos_resource("nodename")
    node_name = node_name_rsrc["spec"]["nodename"]
    print(f"Selected talos node for the upgrade: {node_name}")
    print(f"Selected installer image for the upgrade: '{TALOS_INSTALLER}'")

    print()
    print(f"Current talos version: {current_talos_version}")
    print(f"New talos version: {TALOS_VERSION}")
    print()

    remote_exts = talosctl.get_remote_talos_extension_versions(**config_arg)
    common.print_talos_extension_changes(TALOS_EXTENSIONS, remote_exts)
    if remote_exts == TALOS_EXTENSIONS:
        print("Current extensions remote and local:")
        print("~"*75)
        for name, vers in TALOS_EXTENSIONS.items():
            print(f"  - {name}: {vers}")
        print("~"*75)
        print()
        print("There aren't any diffs between remote and local talos system extensions.")
        print("They are synced.")
        print()

    upgrade_arg = {"image": TALOS_INSTALLER, "preserve": preserve, "stage": stage}
    if not use_current_context:
        upgrade_arg["talosconfig"] = TALOS_CONFIG_PROJECT.resolve()
    if verbose:
        upgrade_arg["wait"] = True
        upgrade_arg["debug"] = True
    else:
        upgrade_arg["wait"] = False

    should_upgrade = common.check_user_choice("Start upgrading? [y/n]\n")

    if should_upgrade:
        print()
        print("It takes a while (~ 5 min) before the machine can be reconnected.")
        print("It's necessary to restart the invoke connect-task.")
        talosctl.upgrade_talos(**upgrade_arg)
