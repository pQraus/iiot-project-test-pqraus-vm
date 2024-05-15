import subprocess as sp
import sys
from difflib import unified_diff
from functools import wraps
from ipaddress import IPv4Address
from pathlib import Path
from typing import Dict, List, Optional

from ._config import BOX_NAME, ENCODING


def check_dependency(tool: str, version_cmd: str, expected_version: Optional[str] = None):
    def inner(func):
        @wraps(func)
        def wrapper_check_dependency(*args, **kwargs):
            """check if a (tool) dependency is installed (in the expected version)"""
            version_cmd_splitted = version_cmd.split(" ")  # create a list for subprocess
            check_cmd = [tool] + version_cmd_splitted
            try:
                version = sp.check_output(check_cmd).decode(sys.stdout.encoding)
            except FileNotFoundError:
                print(
                    f"Have you installed {tool}?",
                    f"Can't execute '{check_cmd}'. ",
                    file=sys.stderr,
                )
                exit(1)
            # version check
            if expected_version and (expected_version not in version):
                print(
                    f"Current version of {tool} is:\n {version}",
                    file=sys.stderr,
                )
                print(
                    f"Expect that version {expected_version} is installed",
                    file=sys.stderr,
                )
                exit(1)
            func(*args, **kwargs)

        return wrapper_check_dependency

    return inner


def diffs_mc(mc1: bytes, mc2: bytes, out_diff: Optional[str] = None):
    diffs = unified_diff(
        mc1.decode(ENCODING).splitlines(keepends=True),
        mc2.decode(ENCODING).splitlines(keepends=True),
        fromfile="current-mc.json",
        tofile="new-mc.json",
    )
    diff_text = "".join(diffs)
    if out_diff:
        with open(out_diff, "x") as f:
            f.write(diff_text)
    return diff_text


def glob_files(root: Path, *glob_pattern: str):
    """glob the files from *root* and sort them (alphabetically)"""
    files: List[Path] = []
    for pattern in glob_pattern:
        files += list(root.glob(pattern))

    return sorted(files, key=lambda file: str(file.relative_to(root)))


def patch_json(json_input: bytes, jq_patch_file: Path, jq_modules_dir: Path):
    """patch the *json_input* with a *jq_patch_file*

    exit 1 when jq can't apply the patch
    """
    cmd_result = sp.run(
        ["jq", "-S", "-L", jq_modules_dir, "-f", jq_patch_file],
        capture_output=True,
        input=json_input,
    )
    if cmd_result.returncode:
        print(f"Can't apply the patch '{jq_patch_file.resolve()}':\n", file=sys.stderr)
        print(cmd_result.stderr.decode(sys.stdout.encoding), file=sys.stderr)
        exit(1)
    return cmd_result.stdout


def print_if(text: str, check: bool):
    """print *text* if *check*"""
    if check:
        print(text)


def validate_ip(ip: str):
    """check if *ip* is in a valid address format"""
    try:
        IPv4Address(ip)
        return True
    except ValueError as verr:
        print("Invalid ip address:", verr)
        return False


def check_user_choice(prompt: str):
    """
    return user console input as (bool) answer to given prompt

    'y' => True, 'n' => False
    """
    while True:
        choice = input(prompt)
        if choice == "y":
            return True
        elif choice == "n":
            return False
        else:
            print("Invalid input!")


def check_k8s_connection() -> bool:
    try:
        context = sp.check_output(["kubectl", "config", "current-context"], text=True).strip()
        if context == BOX_NAME:
            return True
    except Exception:
        return False
    return False


def print_talos_extension_changes(local_exts: Dict[str, str], remote_exts: Dict[str, str]):
    """
    prints out console overview showing differences between
    talos extension versions locally and the remote machine
    """

    if local_exts == remote_exts:
        return

    print("Changes to talos system extensions:")
    print("~"*75)

    for ext, vers in local_exts.items():
        if ext not in remote_exts:
            print(f"Added:   '{ext}' ({vers})")

    for ext in local_exts:
        if ext in remote_exts and (local_exts[ext] != remote_exts[ext]):
            print(f"Changed: '{ext}': {remote_exts[ext]} ===> {local_exts[ext]}")

    for ext, vers in remote_exts.items():
        if ext not in local_exts:
            print(f"Removed: '{ext}' ({vers})")

    print("~"*75)
    print()


def print_deprecated_warning():
    pipx_install = "pipx install git+https://github.com/SchulzSystemtechnik/iiot-misc-iiotctl-dist.git"
    print("DEPRECATED")
    print(f"Use CLI tool 'iiotctl' instead of invoke! Install with: '{pipx_install}'")
    print()
