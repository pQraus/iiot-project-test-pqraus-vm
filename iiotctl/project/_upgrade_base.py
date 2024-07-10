import re
from typing import List

import typer

from .._utils._common import Command, TyperAbort
from .._utils._config import (BASE_REPO_VERSION, BOX_NAME, K8S_VERSION,
                              TALOS_VERSION)
from .._utils._constants import REPO_README
from ._render_manifests import render_argo_manifests
from ._setup_tools import setup_tools

_README_HEADER = f"# iiot-project-{BOX_NAME}"
_BADGE_DATA = {
    "Base": {
        "version": BASE_REPO_VERSION.removeprefix("v").replace("-", "--"),
        "color": "orange"
    },
    "Talos": {
        "version": TALOS_VERSION,
        "color": "red"
    },
    "Kubernetes": {
        "version": K8S_VERSION,
        "color": "blue"
    }
}
_BADGE_TXT = "![Static Badge](https://img.shields.io/badge/v{version}-{color}?label={label})"
_BADGES = "\n".join(
    [_BADGE_TXT.format(label=k, version=v["version"], color=v["color"]) for k, v in _BADGE_DATA.items()]
)


def update_repo_readme():
    """update repo readmes' static badges with new important repo tool versions"""

    with open(REPO_README, "r+") as file:
        content = file.read()
        file.seek(0)

        # remove former static badges with old versions
        for label, data in _BADGE_DATA.items():
            badge_version_pattern = r"!\[Static Badge\]\(https://img.shields.io/badge/v[\w.-]+"
            badge_version_pattern += r"\-" + data['color'] + r"\?label=" + label + r"\)[\n]{0,1}"
            match = re.search(badge_version_pattern, content)
            if match:
                content = "".join(content.split(match.group(0)))

        headers: List[str] = re.findall(r"^# [a-zA-Z0-9]+[\w.-]+[\n]*", content, re.MULTILINE)

        if headers:
            # add badges underneath first main markdown header
            new_badges = headers[0].rstrip() + "\n\n" + _BADGES + "\n\n"
            content = content.replace(headers[0], new_badges, 1)
        else:
            # add main markdown header with project repo name + badges
            content = _README_HEADER + "\n\n" + _BADGES + "\n\n" + content.lstrip()

        file.write(content)
        file.truncate()


def create_repo_readme():
    """create repo readme with repo name + important repo tool versions as static badges"""
    with open(REPO_README, "x") as file:
        file.write(_README_HEADER + "\n\n")
        file.write(_BADGES)


def _check_if_uncommited_changes():
    return bool(Command.check_output(["git", "status", "-s"]))


def _create_update_branch():
    """create update branch either from main (default) or current branch if no merge conflicts """
    on_main = Command.check_output(["git", "branch", "--show-current"]).rstrip() == "main"
    if not on_main:
        typer.confirm(
            "You are currently not on the 'main' branch. Do you still want to continue with the upgrade?", abort=True
        )

    merge_conflict = Command.check_output(["git", "diff", "--name-only", "--diff-filter=U", "--relative"])
    if merge_conflict:
        raise TyperAbort(
            merge_conflict, "First resolve, but don't commit, all merge conflicts before starting upgrade process."
        )

    if on_main:
        update_branch = f"update/base-{BASE_REPO_VERSION}"
        if update_branch in Command.check_output(["git", "branch"]):
            raise TyperAbort(f"Update branch '{update_branch}' already exists.")

        print(f"Create update branch '{update_branch}' on 'main'.")
        Command.check_output(["git", "checkout", "main"])
        Command.check_output(["git", "checkout", "-b", f"update/base-{BASE_REPO_VERSION}"])


def upgrade(set_up_tooling: bool, render_manifests: bool, render_readme: bool, create_update_branch: bool):
    """creates new update branch from main; updates tools + argo manifests; commits changes"""
    if create_update_branch:
        _create_update_branch()

    if render_readme:
        if REPO_README.exists():
            print("Update README.md.")
            update_repo_readme()
        else:
            print("Initialize README.md.")
            create_repo_readme()

    if create_update_branch and _check_if_uncommited_changes():
        Command.check_output(["git", "add", "."])
        Command.check_output(["git", "commit", "-m", "feat: update base repo version"])

    if set_up_tooling:
        typer.secho("\nSet up / update repo tooling:\n", bold=True)
        setup_tools(setup_required=False)
    if render_manifests:
        typer.secho("\nRe-render all argo manifests:\n", bold=True)
        render_argo_manifests(["*"])
        if create_update_branch and _check_if_uncommited_changes():
            Command.check_output(["git", "add", "."])
            Command.check_output(["git", "commit", "-m", "feat: update argo manifests"])
