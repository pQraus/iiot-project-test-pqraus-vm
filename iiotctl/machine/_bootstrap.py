import json
from pathlib import Path
from typing import Dict

import yaml
from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _talosctl as talosctl
from .._utils._common import TyperAbort, print_if
from .._utils._config import (BOX_NAME, DEP_GPG, DEP_JQ, DEP_TALOSCTL,
                              TALOS_INSTALLED_EXTENSIONS)
from .._utils._constants import (PATCH_LOCATIONS, REPO_ROOT,
                                 TALOS_CONFIG_PROJECT)
from .._utils._installer_spec_config import load_repo_installer_image_ref
from . import _talos_config as talos_config


def _update_talosconfig(ip: str, talosconfig: bytes):
    """patch together new talosconfig"""

    updated_talosconfig: Dict = yaml.safe_load(talosconfig)
    # add the ip address into the talosconfig
    updated_talosconfig["contexts"][BOX_NAME]["nodes"] = [ip]
    updated_talosconfig["contexts"][BOX_NAME]["endpoints"] = [ip]

    # add the '-local' suffix to the context name
    new_context_name = f"{BOX_NAME}-local"
    updated_talosconfig["context"] = new_context_name
    updated_talosconfig["contexts"][new_context_name] = updated_talosconfig["contexts"][BOX_NAME]
    updated_talosconfig["contexts"].pop(BOX_NAME)

    return common.dump_yaml(updated_talosconfig)


@check.dependency(*DEP_JQ)
@check.dependency(*DEP_GPG)
@check.dependency(*DEP_TALOSCTL)
def bootstrap(
    machine_ip: str,
    out_talosconfig: str,
    out_mc: str,
    dry_run: bool,
    force: bool,
    verbose: bool,
):

    check.ip(machine_ip)
    patch_files = common.glob_files(REPO_ROOT, *PATCH_LOCATIONS)

    installer_image = load_repo_installer_image_ref(required_extensions=TALOS_INSTALLED_EXTENSIONS)
    print_if(f"Using talos installer image: {installer_image}", verbose)

    initial_mc, talosconfig = talosctl.generate_mc(
        BOX_NAME, install_image=installer_image
    )

    print()
    if out_talosconfig and Path(out_talosconfig).exists() and not force:
        raise TyperAbort(
            f"Talosconfig ({out_talosconfig}) already exist",
            "Delete the file or run the command with the '--force' flag"
        )

    if out_mc and Path(out_mc).exists() and not force:
        raise TyperAbort(
            f"Machine config ({out_mc}) already exist", "Delete the file or run the command with the '--force' flag"
        )

    if out_talosconfig:
        updated_talosconfig = _update_talosconfig(machine_ip, talosconfig)
        with open(out_talosconfig, "w") as f_config:
            f_config.write(updated_talosconfig)

    common.print_if("Create a initial machine config with patches ...", verbose)
    initial_mc = talosctl.patch_mc(initial_mc, patch_files, verbose=verbose)

    if out_mc:
        with open(out_mc, "wb") as f_mc:
            f_mc.write(initial_mc)

    # if dry_run skip applying and talosconfig-teleport updating
    if dry_run:
        print("Bootstrapping in dry-run mode finished successfully")
        print("When the created config is used, you should seal the mc with 'iiotctl machine seal-mc'")
        return

    common.print_if("", verbose)
    common.print_if("Config creation finished successfully", verbose)
    print(f"Applying the initial config to the machine ({machine_ip})...")

    talosctl.apply_mc(initial_mc, insecure=True, nodes=machine_ip)

    print("Seal the initial config")
    talos_config.seal(initial_mc)

    print("Patch talosconfig-teleport")
    root_ca = json.loads(initial_mc)["machine"]["ca"]["crt"]

    # patch the project talosconfig inplace
    with common.patch_yaml_file(file_path=TALOS_CONFIG_PROJECT) as config:
        config["contexts"][BOX_NAME]["ca"] = root_ca
