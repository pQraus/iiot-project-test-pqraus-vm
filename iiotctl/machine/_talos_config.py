import json
import sys
from datetime import datetime
from hashlib import sha256
from typing import List

from rich import print, print_json

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _talosctl as talosctl
from .._utils._common import Command, TyperAbort
from .._utils._config import BOX_NAME, TALOS_INSTALLED_EXTENSIONS
from .._utils._constants import (DEP_GPG, DEP_JQ, DEP_TALOSCTL,
                                 EXCLUDE_SYNC_PATCHES, JQ_MODULES_DIR,
                                 MACHINE_DIR, PATCH_LOCATIONS, REPO_ROOT,
                                 TALOS_CONFIG_PROJECT)
from .._utils._installer_spec_config import load_repo_installer_image_ref

CONFIG_SEALED_DIR = MACHINE_DIR / "config-sealed"
CONFIG_HASH_FILE = CONFIG_SEALED_DIR / "config.hash"
CONFIG_SEALED_FILE = CONFIG_SEALED_DIR / "config-sealed.asc"
KEY_ID = "CE5C2A48F2FD3B6F748F39D35C573EF25CB0F87E"
PUBLIC_KEY_FILE = CONFIG_SEALED_DIR / "public-key.gpg"


def is_mc_hash_diff(mc: bytes):
    """check if saved hash in repo is unequal to the live mc hash"""
    if CONFIG_HASH_FILE.is_file():  # check if hash is already present
        with open(CONFIG_HASH_FILE, "r") as f:
            repo_sealed_mc_hash = f.read().splitlines()[0]
    else:
        repo_sealed_mc_hash = ""
    live_sealed_mc_hash = sha256(mc).hexdigest()
    return repo_sealed_mc_hash != live_sealed_mc_hash


def seal(mc: bytes):
    """seal the mc with the public key in repo and update the hash file"""
    CONFIG_SEALED_FILE.unlink(True)
    Command.check_output(
        [
            "gpg",
            "--no-default-keyring",  # use temp keyring
            "--primary-keyring",
            PUBLIC_KEY_FILE,
            "--encrypt",
            "--recipient",
            KEY_ID,
            "-o",
            CONFIG_SEALED_FILE,
            "--trust-model",
            "always",  # trust key without signing
            "--armor",
            "--batch"  # disable interactive mode
        ],
        in_bytes=True,
        input=mc
    )

    mc_hash = sha256(mc).hexdigest()
    with open(CONFIG_HASH_FILE, "w") as f:
        f.write(mc_hash)
        f.write("\n")
        f.write(f"Created at: {datetime.now()}")


@check.dependency(*DEP_GPG)
@check.dependency(*DEP_TALOSCTL)
def seal_config(id: str, use_current_context: bool):

    common.print_if(
        "Ensure that 'iiotctl connect talos' is running", not use_current_context
    )
    config_arg = (
        {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )

    live_mc = talosctl.fetch_mc(id, **config_arg)
    if is_mc_hash_diff(live_mc):
        print("Create new hash and sealed mc")
        seal(live_mc)
    else:
        print("There isn't a diff between the repo and the live machine config hash.")
        print("Nothing to do.")


@check.dependency(*DEP_JQ)
@check.dependency(*DEP_TALOSCTL)
def fetch_config(id: str, use_current_context: bool):

    config_arg = (
        {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
    )
    mc = talosctl.fetch_mc(id, **config_arg)
    print_json(data=json.loads(mc))


@check.dependency(*DEP_JQ)
@check.dependency(*DEP_TALOSCTL)
def patch_config(
    fetch: bool, generate: bool, patch_file_pattern: List[str], verbose: bool, id: str, use_current_context: bool
):

    if generate and fetch:
        raise TyperAbort("Invalid flags. 'Generate' and 'fetch' are mutually exclusive.")

    patch_files = common.glob_files(REPO_ROOT, *patch_file_pattern) if patch_file_pattern else []

    if generate:
        image_ref = load_repo_installer_image_ref(required_extensions=TALOS_INSTALLED_EXTENSIONS)
        mc, _ = talosctl.generate_mc(BOX_NAME, ttl_years=100, install_image=image_ref)
        if not patch_file_pattern:
            patch_files = common.glob_files(REPO_ROOT, *PATCH_LOCATIONS)
    elif fetch:
        config_arg = (
            {} if use_current_context else {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}
        )
        mc = talosctl.fetch_mc(id, **config_arg)
        if not patch_file_pattern:
            exc_patch_files = common.glob_files(REPO_ROOT, *EXCLUDE_SYNC_PATCHES)
            patch_files = [f for f in common.glob_files(REPO_ROOT, *PATCH_LOCATIONS) if f not in exc_patch_files]
    else:
        mc = sys.stdin.buffer.read()  # read piped-in file content (cat mc.json | iiotctl machine patch_config)
        talosctl.validate_mc(mc)

    if not patch_files:
        raise TyperAbort("No patch files found.")

    if verbose:
        print(file=sys.stderr)
        print("Create machine config with patches ...", file=sys.stderr)

    for patch in patch_files:
        if verbose:
            print(f"   patch: {patch.relative_to(REPO_ROOT)}", file=sys.stderr)
        mc = common.patch_json(mc, patch, JQ_MODULES_DIR)
        talosctl.validate_mc(mc)

    print_json(data=json.loads(mc))
