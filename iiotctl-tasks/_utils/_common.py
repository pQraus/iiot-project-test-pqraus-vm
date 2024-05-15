import math
import subprocess as sp
import sys
from contextlib import contextmanager
from difflib import unified_diff
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import typer
import yaml
from rich import print
from rich.table import Table

from ._config import ENCODING


class PrintStyle(str, Enum):
    BOLD = "bold"
    UNDERLINE = "underline"


def print_style(msg: str, style: PrintStyle, **kwargs: Dict):
    """print message with given style"""
    print(f"[{style}]{msg}[/]", **kwargs)


def print_error(*msgs: Iterable[str], **kwargs: Dict):
    """print message colored red, prefixed with: '[ERROR]:' ..."""
    for msg in msgs:
        if msg != "":
            print(f"[bold red][ERROR]: {msg}[/]", file=sys.stderr, **kwargs)


class Command:

    @staticmethod
    def check_output(
        cmd: List[str], in_bytes=False, ignore_error=False, additional_error_msg="", capture_output=True, **args
    ) -> str | bytes:
        """execute given subprocess command; return resulting stdout; raise error by default"""
        result: sp.CompletedProcess = sp.run(cmd, text=not in_bytes, capture_output=capture_output, **args)

        if result.returncode and not ignore_error:
            error = result.stderr.decode() if isinstance(result.stderr, bytes) else result.stderr
            print_error(error)
            print_error(additional_error_msg)
            raise typer.Abort()
        elif result.returncode and additional_error_msg:
            print_error(additional_error_msg)

        return result.stdout

    @staticmethod
    def check(cmd: List[str], in_bytes=False, ignore_error_msg=True, additional_error_msg="", **args) -> bool:
        """execute given subprocess command; return bool if successful or not; don't raise error by default"""
        result: sp.CompletedProcess = sp.run(cmd, text=not in_bytes, capture_output=True, **args)

        if result.returncode and not ignore_error_msg:
            error = result.stderr.decode() if isinstance(result.stderr, bytes) else result.stderr
            print_error(error)
            print_error(additional_error_msg)
        elif result.returncode and additional_error_msg:
            print_error(additional_error_msg)

        return not bool(result.returncode)


def diffs_mc(mc1: bytes, mc2: bytes, out_diff: Optional[str] = None):
    diffs = unified_diff(
        mc1.decode(ENCODING).splitlines(keepends=True),
        mc2.decode(ENCODING).splitlines(keepends=True),
        fromfile="live-mc.json",
        tofile="repo-mc.json",
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

    patched_json: bytes = Command.check_output(
        cmd=["jq", "-S", "-L", jq_modules_dir, "-f", jq_patch_file],
        additional_error_msg=f"Can't apply the patch '{jq_patch_file.resolve()}'",
        input=json_input,
        in_bytes=True
    )

    return patched_json


def dump_yaml(input: Dict, as_bytes=False):
    """
    dump given content dict in yaml format; return as str or as bytes (as_bytes=True)

    Usage:

    ```python
    content_dict = yaml.safe_load(yaml_str_or_bytes)

    content_dict["stringData"]["data1"] = "new_data1"
    content_dict["stringData"]["data2"] = "new_data2"

    dumped_yaml_content = dump_yaml(content_dict)
    ```
    """

    yaml_content = yaml.safe_dump(input, indent=2, sort_keys=False, width=math.inf)
    return bytes(yaml_content, ENCODING) if as_bytes else yaml_content


@contextmanager
def patch_yaml_file(file_path: Path = None):
    """
    patch yaml file via altering content yielded as dict

    Usage:

    replace the value of 'data1' and 'data2' in the following yaml file:
    ```yaml
    apiVersion: v1
    kind: Secret
    metadata:
        name: some-secret
        namespace: some-app
    stringData:
        data1: foo
        data2: bar
    ```
    via this code:
    ```python
    with yq_patch("path-to-file") as file:
        file["stringData"]["data1"] = "new_data1"
        file["stringData"]["data2"] = "new_data2"
    ```
    """

    file_path: Path = Path(file_path)
    if not file_path.exists():
        print_error(f"Unable to yq patch file at '{file_path}'! Doesn't exist.")
        raise typer.Abort()

    with open(file_path, "r+") as file:
        content_dict = yaml.safe_load(file.read())
        yield content_dict
        file.seek(0)
        file.write(yaml.safe_dump(content_dict, indent=2, sort_keys=False, width=math.inf))
        file.truncate()


def print_if(text: str, check: bool):
    """print *text* if *check*"""
    if check:
        print(text)


def print_talos_extension_changes(repo_exts: Dict[str, str], live_exts: Dict[str, str]):
    """
    prints out console overview, showing differences between talos extension versions in repo and live on the machine
    """

    if repo_exts == live_exts:
        return

    table = Table(title="Extensions Overview", show_lines=True)
    table.add_column("Synced", justify="center")
    table.add_column("Extension")
    table.add_column("Repo")
    table.add_column("Live")

    all_exts = set(repo_exts.keys()).union(live_exts.keys())
    for ext in all_exts:
        in_repo = bool(ext in repo_exts)
        on_live = bool(ext in live_exts)
        table.add_row(
            ":white_heavy_check_mark:" if (in_repo and on_live) and (repo_exts[ext] == live_exts[ext]) else ":x:",
            ext,
            f"v{repo_exts[ext]}" if in_repo else "-",
            f"v{live_exts[ext]}" if on_live else "-"
        )

    print(table)
    print()
