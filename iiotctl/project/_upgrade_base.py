import re
from typing import List

import typer
from rich import print

from .._utils._common import Command, TyperAbort
from .._utils._config import (ADDITIONAL_SYSTEM_APPS, BASE_REPO_VERSION,
                              BOX_NAME, K8S_VERSION, TALOS_VERSION,
                              TELEPORT_ENABLED, TRAEFIK_ENDPOINTS)
from .._utils._constants import (MACHINE_DIR, PUBLIC_SEALED_SECRETS_KEY,
                                 REPO_README)
from ._render_manifests import render_argo_manifests
from ._setup_tools import setup_tools

_README_HEADER = f"# iiot-project-{BOX_NAME}"


class _StaticBadge:
    badge_text = "![Static Badge](https://img.shields.io/badge/{content}-{color}?label={label})"

    def __init__(self, content: str, color: str, label: str, link=None):
        updated_content, updated_label = self._replace_special_chars(content, label)
        self.content = updated_content
        self.label = updated_label
        self.color = color
        self.link = link

    @staticmethod
    def _replace_special_chars(content: str, label: str):
        updated_content = content.replace("-", "--")  # render dashes
        updated_content = updated_content.replace("_", "$TMP$")  # prepare underscore rendering with placeholder
        updated_content = updated_content.replace(" ", "_")  # render content whitespaces
        updated_content = updated_content.replace("$TMP$", "__")  # render underscores
        updated_label = label.replace(" ", "%20")  # render label whitespaces
        return updated_content, updated_label

    def __str__(self) -> str:
        rendered_badge = self.badge_text.format(
            content=self.content,
            color=self.color,
            label=self.label
        )
        if self.link is None:
            return rendered_badge

        badge_with_link = f"[{rendered_badge}]({self.link})"
        return badge_with_link

    def regex_pattern(self) -> str:
        badge_repr = r"!\[Static Badge\]\(https://img.shields.io/badge/[\w._-]*-[\w._-]*\?label=" + self.label + r"\)"
        line_ending = r"[\n]{0,1}"
        if self.link is None:
            return badge_repr + line_ending
        badge_link_repr = r"[" + badge_repr + r"\]\(.*\)" + line_ending
        return badge_link_repr


def _create_badges():
    badges = [
        _StaticBadge(BASE_REPO_VERSION, "orange", "Base"),
        _StaticBadge("v" + TALOS_VERSION, "red", "Talos"),
        _StaticBadge("v" + K8S_VERSION, "blue", "Kubernetes"),
    ]
    if not (TELEPORT_ENABLED and ("private" in TRAEFIK_ENDPOINTS)):
        return badges
    teleport_url = f"https://private-{BOX_NAME}.prod.teleport.schulzdevcloud.com/argocd"
    badges.append(_StaticBadge("via Teleport", "purple", "ArgoCD", teleport_url))
    if "local_monitoring" in ADDITIONAL_SYSTEM_APPS:
        teleport_url = f"https://private-{BOX_NAME}.prod.teleport.schulzdevcloud.com/monitor"
        badges.append(_StaticBadge("via Teleport", "purple", "Local Monitoring", teleport_url))
    return badges


def update_repo_readme():
    """update repo readmes' static badges with new important repo tool versions"""

    with open(REPO_README, "r+") as file:
        content = file.read()
        file.seek(0)

        # remove former static badges with old versions
        # add badge string to the badge section
        badge_strs = []
        for badge in _create_badges():
            match = re.search(badge.regex_pattern(), content)
            if match:
                part1, part2 = content.split(match.group(0))
                content = "".join((part1.rstrip(), "\n\n", part2.lstrip()))
            badge_strs.append(str(badge))

        badge_section = "\n".join(badge_strs)
        headers: List[str] = re.findall(r"(?<!#)#(?!#) .*?\n", content, re.MULTILINE)

        if headers:
            before, header, after = content.partition(headers[0])
            new_content = before + header.rstrip() + "\n\n" + badge_section
            new_content += "\n" if after.strip() == "" else "\n\n" + after.lstrip()
        else:
            badge_section = _README_HEADER + "\n\n" + badge_section
            new_content = badge_section + "\n\n" + content

        file.write(new_content)
        file.truncate()


def create_repo_readme():
    """create repo readme with repo name + important repo tool versions as static badges"""
    with open(REPO_README, "x") as file:
        file.write(_README_HEADER + "\n\n")
        for badge in _create_badges():
            file.write(str(badge) + "\n")


def _has_uncommitted_changes():
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
            raise TyperAbort(
                f"Update branch '{update_branch}' already exists.")

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

    if create_update_branch and _has_uncommitted_changes():
        Command.check_output(["git", "add", "."])
        Command.check_output(["git", "commit", "-m", "feat: update base repo version"])

    if set_up_tooling:
        typer.secho("\nSet up / update repo tooling:\n", bold=True)
        setup_tools(setup_required=False)
    if render_manifests:
        typer.secho("\nRe-render all argo manifests:\n", bold=True)
        render_argo_manifests(["*"])
        if create_update_branch and _has_uncommitted_changes():
            Command.check_output(["git", "add", "."])
            Command.check_output(["git", "commit", "-m", "feat: update argo manifests"])

    print("\n")
    # special v3 -> v4 migration
    disk_selector_file = MACHINE_DIR / "config" / "disk" / "disk-selector.jq"
    if not disk_selector_file.exists():
        typer.secho(
            "Now execute 'iiotctl machine resources --patch' to ensure you have the right disk selected.",
            fg="yellow"
        )

    if not PUBLIC_SEALED_SECRETS_KEY.exists():
        typer.secho(
            "Now execute 'iiotctl project seal-secret --init' while connected to the machine,"
            " to ensure k8s secrets of the repository can be sealed by it.",
            fg="yellow"
        )

    typer.secho(
        "\nExecute 'iiotctl machine status/sync' to ensure everything is in-sync with the machine.", fg="green"
    )
