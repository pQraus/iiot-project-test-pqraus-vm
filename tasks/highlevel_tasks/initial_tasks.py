import json
import os
import subprocess as sp
import tempfile
from pathlib import Path
from subprocess import CalledProcessError
from typing import Optional

from invoke import task

from .. import _common as common
from .. import _mc_sealer as mc_sealer
from .. import _talosctl as talosctl
from .. import _teleport as teleport
from .. import _tokens
from .._config import (BOX_NAME, DEP_GH, DEP_GPG, DEP_TALOSCTL, DEP_TCTL,
                       DEP_TSH, DEP_YQ, ENCODING, PATCH_LOCATIONS,
                       PROJECT_REPO, REPO_ON_GITHUB, REPO_ROOT,
                       TALOS_CONFIG_PROJECT, TALOS_INSTALLER, TASKS_TMP_DIR,
                       TELEPORT_ENABLED)


@task(
    optional=["out_talosconfig"],
    help={
        "target": "(required) IP-address of the box which should be bootstrapped",
        "out_talosconfig": f"output file for the talosconfig (default: {(TASKS_TMP_DIR / 'talosconfig').relative_to(REPO_ROOT)})",
        "out_mc": "output file for the generated machine config",
        "dry_run": "bootstrap without applying to the machine",
        "force": "overwrite <out-mc> & <out-talosconfig> when they already exist",
        "verbose": "verbose status messages",
    },
)
@common.check_dependency(*DEP_GPG)
@common.check_dependency(*DEP_TALOSCTL)
@common.check_dependency(*DEP_YQ)
def bootstrap(
    c,
    target: str,
    out_talosconfig=str((TASKS_TMP_DIR / "talosconfig").absolute()),
    out_mc: Optional[str] = None,
    dry_run=False,
    force=False,
    verbose=False,
):
    """
    bootstrap a new box with the talos machine config from the repo

    EXAMPLES:

    Call without optional arguments to create a new talos machine config and apply it to the machine with the given IP:
    >>> invoke init.bootstrap 192.168.23.2

    Call with argument '--dry-run' to create a machine config locally without applying it to the machine:
    >>> invoke init.bootstrap 192.168.23.2 --dry-run

    Call with argument '--out-mc' to also write the new machine config in a local file given by name:
    >>> invoke init.bootstrap 192.168.23.2 --out-mc "mc.json"
    """

    if not common.validate_ip(target):
        exit(1)

    patch_files = common.glob_files(REPO_ROOT, *PATCH_LOCATIONS)

    initial_mc, talosconfig = talosctl.generate_mc(
        BOX_NAME, install_image=TALOS_INSTALLER
    )

    print()
    if out_talosconfig and Path(out_talosconfig).exists() and not force:
        print(f"Talosconfig ({out_talosconfig}) already exist")
        print("Delete the file or run the command with the '--force' flag")
        exit(1)

    if out_mc and Path(out_mc).exists() and not force:
        print(f"Machine config ({out_mc}) already exist")
        print("Delete the file or run the command with the '--force' flag")
        exit(1)

    if out_talosconfig:
        # add the ip address into the talosconfig
        node_update = f'.contexts."{BOX_NAME}".nodes = ["{target}"]'
        endpoint_update = f'.contexts."{BOX_NAME}".endpoints = ["{target}"]'

        # add the '-local' suffix to the context name
        new_context_name = f"{BOX_NAME}-local"
        current_context_update = f'.context = "{new_context_name}"'
        new_context = f'.contexts."{new_context_name}" =.contexts."{BOX_NAME}"'
        del_old_context = f'del(.contexts."{BOX_NAME}")'

        updated_talosconfig = sp.check_output(
            [
                "yq",
                f"{node_update} | "
                + f"{endpoint_update} | "
                + f"{current_context_update} | "
                + f"{new_context} | "
                + f"{del_old_context}",
            ],
            input=talosconfig,
        )

        with open(out_talosconfig, "wb") as f_config:
            f_config.write(updated_talosconfig)

    common.print_if("Create a initial machine config with patches ...", verbose)
    initial_mc = talosctl.patch_mc(initial_mc, patch_files, verbose)

    if out_mc:
        with open(out_mc, "wb") as f_mc:
            f_mc.write(initial_mc)

    # if dry_run skip applying and talosconfig-teleport updating
    if dry_run:
        print("Bootstrapping in dry-run mode finished successfully")
        print("When the created config is used, you should seal the mc with 'invoke seal-mc'")
        return

    common.print_if("", verbose)
    common.print_if("Config creation finished successfully", verbose)
    print(f"Applying the initial config to the machine ({target})...")

    talosctl.apply_mc(initial_mc, insecure=True, nodes=target)

    print("Seal the initial config")
    mc_sealer.seal_mc(initial_mc)
    print("Patch talosconfig-teleport")
    root_ca = sp.check_output(["jq", ".machine.ca.crt"], input=initial_mc)
    replace_ca_filter = f".contexts.*.ca |= {root_ca.decode(ENCODING)}"
    # patch the project talosconfig inplace
    sp.check_output(["yq", "-i", replace_ca_filter, TALOS_CONFIG_PROJECT])


@task(
    optional=["expiration_time"],
    help={"expiration_time": "time in which join tokens are valid (e.g. 30m, 3h, 5h ..., default: 1h)"},
)
@common.check_dependency(*DEP_TCTL)
@common.check_dependency(*DEP_TSH)
@common.check_dependency(*DEP_YQ)
def configure_teleport_token(c, expiration_time="1h"):
    """
    Obtain teleport join token; add token into box setup secrets

    EXAMPLES:

    Call without optional arguments to request teleport join token (by default 1h valid) and add it to
    box setup secrets:
    >>> invoke init.configure-teleport-token

    Call with argument '-e' to increase the time the to-be-obtained teleport join token should be valid:
    >>> invoke init.configure-teleport-token -e 3h
    """

    if not TELEPORT_ENABLED:
        print(f"Access to teleport cluster is according to box configuration not required ({TELEPORT_ENABLED=}).")
        return

    PATH_JOIN_TOKEN = Path("initial-secrets/join-token.yaml")
    PATH_TELEPORT_CONFIGURATOR_PATCHES = REPO_ROOT / "system-apps/teleport-configurator/machine-patches"
    token_add_bash_cmd = ["tctl", "tokens", "add", "--type=app,kube", "--format=json", "--ttl", expiration_time]

    sp.check_output(["tsh", "logout"])

    # log into teleport cluster referenced by url in '/tasks/tasks_config.json' + get join token
    teleport.login()
    new_token = sp.check_output(token_add_bash_cmd, encoding="utf-8")
    new_token = json.loads(new_token)["token"]

    sp.check_output(["tsh", "logout"])
    print("Successfully obtained teleport join token.")

    # patch token into box secrets
    sp.check_output(
        [
            "yq",
            f'.stringData.join-token = "{new_token}"',
            "-i",
            PATH_TELEPORT_CONFIGURATOR_PATCHES / PATH_JOIN_TOKEN
        ]
    )

    # add secrets into initial manifests
    with open(PATH_TELEPORT_CONFIGURATOR_PATCHES / PATH_JOIN_TOKEN) as f:
        token = f.read()
        token = token.rstrip()

    with open(PATH_TELEPORT_CONFIGURATOR_PATCHES / "join-token-manifest.jq.temp") as f:
        manifest = f.read()
        manifest = manifest.replace("JOIN_TOKEN", token)

    with open(PATH_TELEPORT_CONFIGURATOR_PATCHES / "_initial-join-token-manifest.boot.jq", "w") as f:
        f.write(manifest)

    print("Successfully configured box teleport access manifests.")


def _create_git_credential_boot_manifest(credential_src_file: Path, template_file: Path, credential_dst_file: Path):
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


@task(
    optional=["commit_msg"],
    help={
        "initial_commit": "git add and commit all local repo changes, then push 'main' origin (default: False)",
        "commit_msg": "git commit message (default: 'Initial commit')",
        "override": "override remote repo initial commit and/or the deploy key"
    },
)
@common.check_dependency(*DEP_GH)
@common.check_dependency(*DEP_YQ)
def configure_remote_repository(c, initial_commit=False, commit_msg="Initial commit", override=False):
    """
    Set up GitHub repository; configure box repository access via deploy key

    EXAMPLES:

    Call without optional arguments to create GitHub repo, add deploy key to it and the respective private key into
    box setup secrets:
    >>> invoke init.configure-remote-repository

    Call with argument '-i' to also add, commit and push all changes to the to-be-created remote repository:
    >>> invoke init.configure-remote-repository -i

        This initial GitHub commit can only be done once. By default it is named "Initial commit".

    Call with arguments '-i' and '-c' to make initial commit with custom commit message:
    >>> invoke init.configure-remote-repository -i -c "Your commit message"

    Call with arguments '-i' and '-o' to first add and commit all local 'main' branch changes as 'Initial commit' and
    then force-push 'main' to override the already existing remote repository 'main'. Also renew the 'argo' deploy key:
    >>> invoke init.configure-remote-repository -i -o

        Useful if you did reset a talos vm, cleared out your local repo directory and copied a new base box version
        into it, but can't test the setup of this new base box repo version on the vm because there are still the files
        of the previous base box repo version committed in the github repo.
    """

    MACHINE_PATCHES_DIR = REPO_ROOT / "system-apps/cluster-administration/machine-patches"
    PATH_GITHUB_CREDENTIALS_SRC = MACHINE_PATCHES_DIR / "initial-secrets/github-credentials.yaml"
    PATH_LOCAL_GIT_CREDENTIALS_SRC = MACHINE_PATCHES_DIR / "initial-secrets/local-git-credentials.yaml"
    PATH_INITIAL_MANIFEST_TEMP = MACHINE_PATCHES_DIR / "git-credential-manifest.jq.temp"
    PATH_INITIAL_BOOT_MANIFEST_DST = MACHINE_PATCHES_DIR / "_initial-git-credential-manifest.boot.jq"

    if not REPO_ON_GITHUB:
        # create initial boot manifest with local git credentials
        _create_git_credential_boot_manifest(
            PATH_LOCAL_GIT_CREDENTIALS_SRC,
            PATH_INITIAL_MANIFEST_TEMP,
            PATH_INITIAL_BOOT_MANIFEST_DST
        )
        return

    try:
        status = sp.check_output(["gh", "auth", "status"], encoding="UTF-8")
    except CalledProcessError:
        print("You have to be logged in with the GitHub CLI tool 'gh'.")
        exit(1)

    if "gho_" not in status:
        print("To execute this task, you have to be logged into the tool 'gh' via browser, not via PAT.")
        exit(1)

    # create remote GitHub repo if nonexistent
    if not sp.check_output(["gh", "search", "repos", PROJECT_REPO]):
        sp.run(["gh", "repo", "create", PROJECT_REPO, "--private"], check=True)
    elif not override:
        print(f"Repository {PROJECT_REPO} already exists! To override github repository use flag '--override'.")
        exit(1)

    os.chdir(REPO_ROOT)

    # initialize git locally
    if not common.glob_files(REPO_ROOT, ".git"):
        sp.check_output(["git", "init"])
        print("Successfully initialized local git repository.")

    # add remote repo as origin
    if not "origin" == sp.check_output(["git", "remote"], encoding="UTF-8").rstrip():
        repo_url = f"https://github.com/{PROJECT_REPO}.git"
        sp.check_output(["git", "remote", "add", "origin", repo_url])
        print(f"Successfully added remote repo {repo_url} as origin.")

    # commit all files + push 'main' branch to remote repo
    if initial_commit:
        sp.run(["git", "add", "."], capture_output=True)
        sp.run(["git", "commit", "-m", commit_msg], capture_output=True)

        if any("* master" in br for br in sp.check_output(["git", "branch"], encoding="UTF-8").split("\n")):
            sp.check_output(["git", "branch", "-M", "main"])

        if override:
            sp.run(["git", "push", "-u", "origin", "main", "-f"], check=True, capture_output=True)
            print("Successfully force pushed main branch to origin.")
        else:
            sp.run(["git", "push", "-u", "origin", "main"], check=True, capture_output=True)
            print("Successfully pushed main branch to origin.")

    # list and pair up deploy key names + ids
    keys = sp.check_output(["gh", "repo", "deploy-key", "list", "-R", PROJECT_REPO], encoding="UTF-8").split("\n")[:-1]
    keys = dict(reversed(key.split("\t")[:2]) for key in keys)

    # handle already existing deploy key 'argo' (replace / persist)
    key_exists = bool("argo" in keys)
    if key_exists and not override:
        msg = "Deploy key 'argo' already exists. Do you want to replace it ? [y/n] (if not >> new key not added) "
        replace = common.check_user_choice(msg)
        if not replace:
            print(f"Skip: adding deploy key to {PROJECT_REPO}.")
            print("Skip: configuring github credential manifests.")
            return

    if key_exists:
        sp.run(["gh", "repo", "deploy-key", "delete", keys["argo"], "-R", PROJECT_REPO], check=True)

    # generate ssh key pair + add public key as deploy key to GitHub repo
    with tempfile.TemporaryDirectory() as td:
        print("Generating ssh key pair ...")

        key_files = td + "/" + "key"
        sp.check_output(["ssh-keygen", "-t", "ed25519", "-C", "", "-N", "", "-f", key_files])

        with open(key_files) as rd:
            private_key = rd.read()

        sp.run(
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
            ],
            check=True
        )

    # patch private ssh key into box secret
    sp.check_output(["yq", f'.stringData.sshPrivateKey = "{private_key}"', "-i", PATH_GITHUB_CREDENTIALS_SRC])

    # create initial boot manifest with github credentials
    _create_git_credential_boot_manifest(
        PATH_GITHUB_CREDENTIALS_SRC,
        PATH_INITIAL_MANIFEST_TEMP,
        PATH_INITIAL_BOOT_MANIFEST_DST
    )


@task(
    help={
        "docker": "Create a token for docker",
        "grafana": "Create a token for grafana",
        "schulz_registry": "Create a token for the schulz-registry"}
)
@common.check_dependency(*DEP_TSH)
def create_token(
        _,
        grafana=False,
        docker=False,
        schulz_registry=False):
    """
    Create tokens for docker, schulz-registry and grafana

    EXAMPLE:

    Call with at least one provider specified to create a token
    box setup secrets:
    >>> invoke init.create-token --docker --schulz-registry
    """

    selected_provider = []
    selected_provider += (["grafana"] if grafana else [])
    selected_provider += (["docker"] if docker else [])
    selected_provider += (["schulz_registry"] if schulz_registry else [])

    if not len(selected_provider) > 0:
        print("Choose at least one token provider")
        return

    _tokens.create_tokens(selected_provider)
