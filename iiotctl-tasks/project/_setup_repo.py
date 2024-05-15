import tempfile
from pathlib import Path

import typer
from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils._common import Command, print_error
from .._utils._config import DEP_GH, PROJECT_REPO, REPO_ON_GITHUB, REPO_ROOT


def _create_git_credential_boot_manifest(credential_src_file: Path, template_file: Path, credential_dst_file: Path):
    """read in git credentials from yaml; insert git credentials in manifest template; create boot manifest file"""

    # read in git credentials from yaml
    with open(credential_src_file) as f:
        credentials = f.read()
        credentials = credentials.rstrip()
        credentials.replace("\"", "'")

    # read in manifest template + insert git credentials
    with open(template_file) as f:
        git_credentials = f.read()
        git_credentials = git_credentials.replace("GITHUB_CREDENTIALS", credentials)

    # write git credential boot manifest into new file
    with open(credential_dst_file, "w") as f:
        f.write(git_credentials)

    print("Successfully configured git credential manifests.")


def _check_gh_status():
    """check if logged into gh via webbrowser not PAT"""
    status = Command.check_output(
        cmd=["gh", "auth", "status"],
        additional_error_msg="You have to be logged in with the GitHub CLI tool 'gh'."
    )

    if "gho_" not in status:
        print_error("To execute this task, you have to be logged into the tool 'gh' via browser, not via PAT.")
        raise typer.Abort()


def _create_github_repo(override: bool):
    """create github repo if nonexistent"""
    if not Command.check_output(cmd=["gh", "search", "repos", PROJECT_REPO]):
        Command.check_output(cmd=["gh", "repo", "create", PROJECT_REPO, "--private"])
    elif not override:
        print_error(f"Repository {PROJECT_REPO} already exists! To override github repository use flag '--override'.")
        raise typer.Abort()


def _init_local_git():
    """initialize git locally"""
    if not common.glob_files(REPO_ROOT, ".git"):
        Command.check_output(cmd=["git", "init"], cwd=REPO_ROOT)
        print("Successfully initialized local git repository.")


def _add_remote_origin():
    """add live repo as remote origin"""
    if not "origin" == Command.check_output(cmd=["git", "remote"], cwd=REPO_ROOT).rstrip():
        repo_url = f"https://github.com/{PROJECT_REPO}.git"
        Command.check_output(cmd=["git", "remote", "add", "origin", repo_url], cwd=REPO_ROOT)
        print(f"Successfully added github repo {repo_url} as origin.")


def _initialize_github_repo(commit_msg: str, override: bool):
    """add, commit all files + push 'main' branch to github repo"""
    Command.check_output(cmd=["git", "add", "."], cwd=REPO_ROOT)
    Command.check_output(cmd=["git", "commit", "-m", commit_msg], cwd=REPO_ROOT)

    branches = Command.check_output(cmd=["git", "branch"], cwd=REPO_ROOT).split("\n")
    if any(["master" in br for br in branches]):
        Command.check_output(cmd=["git", "switch", "master"], cwd=REPO_ROOT)
        Command.check_output(cmd=["git", "branch", "-M", "main"], cwd=REPO_ROOT)

    if override:
        Command.check_output(cmd=["git", "push", "-u", "origin", "main", "-f"], cwd=REPO_ROOT)
        print("Successfully force pushed main branch to origin.")
    else:
        Command.check_output(cmd=["git", "push", "-u", "origin", "main"], cwd=REPO_ROOT)
        print("Successfully pushed main branch to origin.")


def _choose_deploy_key_handling():
    """user chooses how to handle already existing deploy key 'argo' (replace / persist)"""
    msg = "Deploy key 'argo' already exists. Do you want to replace it ? [y/n] (if not >> new key not added) "
    replace = typer.confirm(msg)
    if not replace:
        print(f"Skip: adding deploy key to {PROJECT_REPO}.")
        print("Skip: configuring github credential manifests.")
        raise typer.Exit(0)


def _configure_deploy_key_access(path_github_credentials_file: Path):
    """generate ssh key pair + add public key as deploy key to GitHub repo; patch private ssh key into box secrets"""

    # generate ssh key pair + add public key as deploy key to GitHub repo
    with tempfile.TemporaryDirectory() as td:
        print("Generating ssh key pair ...")

        key_files = td + "/" + "key"
        Command.check_output(cmd=["ssh-keygen", "-t", "ed25519", "-C", "", "-N", "", "-f", key_files])

        with open(key_files) as rd:
            private_key = rd.read()

        Command.check_output(
            [
                "gh",
                "repo",
                "deploy-key",
                "add",
                key_files + ".pub",
                "-t",
                "argo",
                "-R",
                PROJECT_REPO
            ]
        )

    # patch private ssh key into box secret
    with common.patch_yaml_file(file_path=path_github_credentials_file) as secret:
        secret["stringData"]["sshPrivateKey"] = private_key


@check.dependency(*DEP_GH)
def configure_github_repository(initialize: bool, commit_msg: str, override: bool):

    MACHINE_PATCHES_DIR = REPO_ROOT / "system-apps/cluster-administration/machine-patches"
    PATH_GITHUB_CREDENTIALS_SRC = MACHINE_PATCHES_DIR / "initial-secrets/github-credentials.yaml"
    PATH_LOCAL_GIT_CREDENTIALS_SRC = MACHINE_PATCHES_DIR / "initial-secrets/local-git-credentials.yaml"
    PATH_INITIAL_MANIFEST_TEMP = MACHINE_PATCHES_DIR / "git-credential-manifest.jq.temp"
    PATH_INITIAL_BOOT_MANIFEST_DST = MACHINE_PATCHES_DIR / "_initial-git-credential-manifest.boot.jq"

    # create initial boot manifest with local git credentials
    if not REPO_ON_GITHUB:
        _create_git_credential_boot_manifest(
            PATH_LOCAL_GIT_CREDENTIALS_SRC,
            PATH_INITIAL_MANIFEST_TEMP,
            PATH_INITIAL_BOOT_MANIFEST_DST
        )
        return

    _check_gh_status()
    _create_github_repo(override)
    _init_local_git()
    _add_remote_origin()

    if initialize:
        _initialize_github_repo(commit_msg, override)

    # list and pair up deploy key names + ids
    keys = Command.check_output(cmd=["gh", "repo", "deploy-key", "list", "-R", PROJECT_REPO]).split("\n")[:-1]
    keys = dict(reversed(key.split("\t")[:2]) for key in keys)

    key_exists = bool("argo" in keys)
    if key_exists and not override:
        _choose_deploy_key_handling()

    if key_exists:
        Command.check_output(cmd=["gh", "repo", "deploy-key", "delete", keys["argo"], "-R", PROJECT_REPO])

    _configure_deploy_key_access(PATH_GITHUB_CREDENTIALS_SRC)

    # create initial boot manifest with github credentials
    _create_git_credential_boot_manifest(
        PATH_GITHUB_CREDENTIALS_SRC,
        PATH_INITIAL_MANIFEST_TEMP,
        PATH_INITIAL_BOOT_MANIFEST_DST
    )
