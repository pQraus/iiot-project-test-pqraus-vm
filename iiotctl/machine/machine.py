from typing import List

import typer
from typing_extensions import Annotated

from .._utils._constants import (DEFAULT_MACHINE_CONFIG_ID, REPO_ROOT,
                                 TASKS_TMP_DIR)
from . import _bootstrap, _status, _sync, _talos_config, _upgrade

app = typer.Typer(name="machine", help="Interact with live machine via established connection.")


@app.command()
def bootstrap(
    machine_ip: Annotated[str, typer.Argument(help="IP address of the box which should be bootstrapped")],
    out_mc: Annotated[str, typer.Option("--out-mc", help="output file path for the generated machine config")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-d", help="bootstrap without applying to the machine")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="verbose status messages")] = False,
    out_talosconfig: Annotated[
        str,
        typer.Option("--out-talosconfig", help="output file path for the talosconfig")
    ] = str((TASKS_TMP_DIR / "talosconfig").relative_to(REPO_ROOT)),
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="overwrite <out-mc> & <out-talosconfig> when they already exist")
    ] = False
):
    """
    bootstrap a new machine with the talos machine config from the repo

    EXAMPLES:

    Call without optional arguments to create a new talos machine config and apply it to the machine with the given IP:
    >>> iiotctl machine bootstrap 192.168.23.2

    Call with argument '--dry-run' to create a machine config locally without applying it to the machine:
    >>> iiotctl machine bootstrap 192.168.23.2 --dry-run

    Call with argument '--out-mc' to also write the new machine config in a local file given by name:
    >>> iiotctl machine bootstrap 192.168.23.2 --out-mc "mc.json"
    """

    _bootstrap.bootstrap(machine_ip, out_talosconfig, out_mc, dry_run, force, verbose)


@app.command()
def status(
    out_diff: Annotated[str, typer.Option("--out-diff", help="output file path for machine config diffs")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="verbose status messages")] = False,
    use_current_context: Annotated[
        bool,
        typer.Option(
            "--use-current-context",
            "-u",
            help="use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used"
        )
    ] = False
):
    """
    check the current state of the live machine in comparison to this repo

    EXAMPLES:

    Call without optional arguments to see the differences between repo and live machine config printed in the console:
    >>> iiotctl machine status

    Call with argument '--out-diff' to export differences between repo and live machine config to file:
    >>> iiotctl machine status --out-diff "diffs.txt"
    """

    _status.status(out_diff, use_current_context, verbose)


@app.command()
def sync(
    out_diff: Annotated[str, typer.Option("--out-diff", help="output file path for machine config diffs")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="verbose status messages")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-d", help="sync without applying the new config")] = False,
    apply_mode: Annotated[
        str,
        typer.Option(
            "--apply-mode",
            "-a",
            help="mode for applying the machine config (see talosctl apply-config -h)",
        )
    ] = "no-reboot",
    use_current_context: Annotated[
        bool,
        typer.Option(
            "--use-current-context",
            "-u",
            help="use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used"
        )
    ] = False,
    out_backup: Annotated[
        str,
        typer.Option(
            "--out-backup",
            help="output file path to save the live machine config at"
        )
    ] = str((TASKS_TMP_DIR / 'mc-backup.json').relative_to(REPO_ROOT)),
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="ignore version conflicts for talos and k8s between repo and live machine"
        )
    ] = False
):
    """
    sync the machine with the config from this repo

    EXAMPLES:

    Call without optional arguments to see the differences between repo and live machine config printed in the console
    and then choose if the repo machine config changes should be applied to the box:
    >>> iiotctl machine sync

    Call with argument '--out-diff' to export differences between repo and live machine config to file:
    >>> iiotctl machine sync --out-diff "diffs.txt"

    Call with argument '--apply-mode' to specify a mode used by talosctl to apply the repo machine config
    to the box and then reboot talos on it:
    >>> iiotctl machine sync --apply-mode reboot

        Other apply modes are: [auto, interactive, staged, try, (default:) no-reboot]
    """

    _sync.sync(force, out_backup, out_diff, apply_mode, dry_run, use_current_context, verbose)


@app.command()
def upgrade_talos(
    no_preserve: Annotated[bool, typer.Option("--no-preserve", help="don't preserve data on disk")] = False,
    no_stage: Annotated[
        bool, typer.Option("--no-stage", help="don't stage the upgrade to perform it after a reboot")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="verbose status messages")] = False,
    use_current_context: Annotated[
        bool,
        typer.Option(
            "--use-current-context",
            "-u",
            help="use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used"
        )
    ] = False
):
    """
    upgrade talos to the version which is specified in the repo

    Call with argument '--use-current-context' to connect via the currently selected talos context.
    >>> iiotctl machine upgrade-talos --use-current-context

        Useful if you want to connect via local talos cert and context, without teleport.
    """

    _upgrade.upgrade_talos(use_current_context, not no_preserve, not no_stage, verbose)


@app.command()
def upgrade_k8s(
    dry_run: Annotated[bool, typer.Option("--dry-run", "-d", help="execute the upgrade in dry-run mode")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="verbose status messages")] = False,
    preload: Annotated[
        bool, typer.Option("--preload", help="preload k8s images onto live machine for later update")
    ] = False,
    use_current_contexts: Annotated[
        bool,
        typer.Option(
            "--use-current-context",
            "-u",
            help="use the currently selected talos and k8s context instead of config from the repo"
        )
    ] = False
):
    """
    upgrade k8s to the version which is specified in the repo

    EXAMPLES:

    Call with argument '--use-current-contexts' to connect to the machine's talos and k8s APIs via the currently
    selected contexts. Not with the live machine's contexts via teleport:
    >>> iiotctl machine upgrade-k8s --use-current-contexts

        Useful if you want to connect via local k8s + talos certs and contexts, without teleport.
    """

    _upgrade.upgrade_k8s(use_current_contexts, preload, dry_run, verbose)


@app.command()
def patch_config(
    fetch: Annotated[
        bool,
        typer.Option(
            "--fetch", "-f", help="fetch live mc from machine before patching it"
        )
    ] = False,
    generate: Annotated[
        bool,
        typer.Option(
            "--generate", "-g", help="generate blank mc instead of fetching it from machine before patching it"
        )
    ] = False,
    patch_file_pattern: Annotated[
        List[str],
        typer.Option("--patch-file-pattern", "-p", help="glob pattern(s) to find the local patch files to patch with")
    ] = [],
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="verbose status messages")] = False,
    id: Annotated[
        str, typer.Option("--id", help="id of machine config on live machine", rich_help_panel="Fetch utils")
    ] = DEFAULT_MACHINE_CONFIG_ID,
    use_current_context: Annotated[
        bool,
        typer.Option(
            "--use-current-context",
            "-u",
            help="use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used",
            rich_help_panel="Fetch utils"
        )
    ] = False
):
    """
    patch machine config with jq patch files

    EXAMPLES:

    Call with argument '--fetch' while connected to talos machine to get the machine mc and patch it with
    non-boot-related jq patch files. Pipe the resulting mc into a json file for better readability:
    >>> iiotctl machine patch-config > mc.json

    Call with arguments '--fetch' and '--use-current-context' to connect and then fetch the mc via the currently
    selected talos context:
    >>> iiotctl machine patch-config --fetch --use-current-context

        Useful if you want to connect via local talos cert and context, without teleport.

    Call with argument '--generate' to generate a blank mc before patching it with all local jq patch files.
    Pipe the resulting mc into a json file for better readability:
    >>> iiotctl machine patch-config --generate > mc.json

    Call with the to-be-patched content of the machine config piped into STDIN and use argument '--patch-file-pattern'
    to specify via filename pattern which patch files should be used to patch the machine config. Pipe the resulting mc
    into a json file for better readability:
    >>> cat mc.json | iiotctl machine patch-config --patch-file-pattern "machine/config/*/_*.jq" --patch-file-pattern
    "system-apps/*/machine-patches/_*.jq"
    """

    _talos_config.patch_config(fetch, generate, patch_file_pattern, verbose, id, use_current_context)


@app.command()
def fetch_config(
    id: Annotated[str, typer.Option("--id", help="id of machine config on live machine")] = DEFAULT_MACHINE_CONFIG_ID,
    use_current_context: Annotated[
        bool,
        typer.Option(
            "--use-current-context",
            "-u",
            help="use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used"
        )
    ] = False
):
    """
    fetch a current machine config by id from the live machine

    EXAMPLES:

    Call with argument '--use-current-context' to connect via the currently selected talos context:
    >>> iiotctl machine fetch-config --use-current-context

        Useful if you want to connect via local talos cert and context, without teleport.
    """

    _talos_config.fetch_config(id, use_current_context)


@app.command()
def seal_config(
    id: Annotated[str, typer.Option("--id", help="id of machine config on live machine")] = DEFAULT_MACHINE_CONFIG_ID,
    use_current_context: Annotated[
        bool,
        typer.Option(
            "--use-current-context",
            "-u",
            help="use the current selected talos context, otherwise the machine/talosconfig-teleport file will be used"
        )
    ] = False
):
    """
    seal the live machine config and save it in the repo

    EXAMPLES:

    Call without optional arguments to seal and hash the live machine config (only when there is a hash diff):
    >>> iiotctl machine seal-config

    Call with argument '--use-current-context' to connect via the currently selected talos context:
    >>> iiotctl machine fetch-config --use-current-context

        Useful if you want to connect via local talos cert and context, without teleport.
    """

    _talos_config.seal_config(id, use_current_context)
