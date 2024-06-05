from typing import List

import typer
from rich import print
from typing_extensions import Annotated

from .._utils import _teleport as teleport
from .._utils._config import (CONTAINER_REGISTRIES, IS_DEV_ENV,
                              REMOTE_MONITORING, TELEPORT_ENABLED)
from .._utils._constants import REPO_README
from . import (_create_token, _render_manifests, _seal_secret, _setup_repo,
               _setup_tools, _upgrade_base)

app = typer.Typer(name="project", help="Create and configure machine repository.")


@app.command()
def setup(
    no_tooling: Annotated[bool, typer.Option("--no-tooling", help="don't install / update project tools")] = False,
    no_manifests: Annotated[bool, typer.Option("--no-manifests", help="don't render argo manifests")] = False,
    no_sealed_secret: Annotated[
        bool, typer.Option("--no-sealed-secret", help="don't bootstrap sealed secrets private key")
    ] = False,
    no_tokens: Annotated[bool, typer.Option("--no-tokens", help="don't create all required setup tokens")] = False,
    no_github_repo: Annotated[
        bool, typer.Option("--no-github-repo", help="don't create github repo & configure access")
    ] = False
):
    """
    set up new box repository

    Steps:

    1. 'Set up tools' - installing / updating tools required for managing repository
    2. 'Render argo manifests' - creating deployment-ready manifest for each app
    3. 'Bootstrap sealed secrets' - prepare private key to be bootstrapped onto new machine
    4. 'Create tokens' - create access tokens to APIs of multiple applications used by new machine
    5. 'Set up github repository' - create github repo containing local repo content
    """
    typer.confirm("Are you sure you want to start the project setup ?", default=True, abort=True)

    typer.secho("Initializing box:", bold=True)

    _upgrade_base.update_repo_readme() if REPO_README.exists() else _upgrade_base.create_repo_readme()

    if not no_tooling:
        typer.secho("\nSetup tools:\n", bold=True)
        _setup_tools.setup_tools(setup_required=True)

    teleport.login()
    print()

    if not no_manifests:
        typer.secho("\nRender manifests:\n", bold=True)
        _render_manifests.render_argo_manifests(["*"])
    if not no_sealed_secret:
        typer.secho("\nSealed secret bootstrap:\n", bold=True)
        _seal_secret.seal_secret(bootstrap=True)
    if not no_tokens:
        typer.secho("\nCreate tokens:\n", bold=True)
        _create_token.create_token(
            docker=bool("docker" in CONTAINER_REGISTRIES),
            schulz_registry=bool("schulz_registry" in CONTAINER_REGISTRIES),
            teleport=TELEPORT_ENABLED,
            grafana=REMOTE_MONITORING,
            ttl="3h",
            dev=IS_DEV_ENV
        )
    if not no_github_repo:
        typer.secho("\nSetup github repo:\n", bold=True)
        _setup_repo.configure_github_repository(initialize=True, commit_msg="Initital commit", override=False)


@app.command()
def upgrade(
    no_set_up_tooling: Annotated[
        bool, typer.Option("--no-set-up-tooling", help="don't install / update project tools")
    ] = False,
    no_render_manifests: Annotated[
        bool, typer.Option("--no-render-manifests", help="don't render helm manifests")
    ] = False,
    no_render_readme: Annotated[
        bool, typer.Option("--no-render-readme", help="don't render repo readme file")
    ] = False,
):
    """upgrade repo files after base update; create update branch + commit all changes"""

    _upgrade_base.upgrade(not no_set_up_tooling, not no_render_manifests, not no_render_readme)


@app.command(rich_help_panel="Lowlevel Commands")
def setup_tools():
    """show overview of required and installed tools; set up tools with asdf"""

    _setup_tools.setup_tools(setup_required=False)


@app.command(rich_help_panel="Lowlevel Commands")
def create_token(
    grafana: Annotated[bool, typer.Option("--grafana", help="create a token for grafana access")] = False,
    docker: Annotated[bool, typer.Option("--docker", help="create a token for docker")] = False,
    schulz_registry: Annotated[
        bool, typer.Option("--schulz-registry", help="create a token for schulz registry access")
    ] = False,
    teleport: Annotated[bool, typer.Option("--teleport", help="create a token for teleport server access")] = False,
    ttl: Annotated[
        str,
        typer.Option(
            "--ttl",
            help="time the teleport join token is valid (e.g. 8m, 23m, 7h...)",
            rich_help_panel="Teleport utils"
        )
    ] = "3h",
    dev: Annotated[bool, typer.Option("--dev", help="custom enter all access tokens via console")] = False
):
    """
    Create access tokens for docker, schulz-registry, grafana and teleport

    EXAMPLE:

    Call with at least one provider specified to create a token:
    >>> iiotctl project create-token --docker --schulz-registry

    Call with teleport as provider and the argument 'ttl' to configure the time it's join token is valid:
    >>> iiotctl project create-token --teleport --ttl 5h
    """

    _create_token.create_token(grafana, docker, schulz_registry, teleport, ttl, dev)


@app.command(rich_help_panel="Lowlevel Commands")
def configure_github_repo(
    initialize: Annotated[
        bool,
        typer.Option("--initialize", "-i", help="git add and commit all local repo changes, then push 'main' origin")
    ] = False,
    commit_msg: Annotated[
        str,
        typer.Option("--commit-msg", help="git commit message")
    ] = "Initial commit",
    override: Annotated[
        bool,
        typer.Option("--override", "-o", help="override github repo initial commit and/or the deploy key")
    ] = False
):
    """
    Set up github repository; configure box repository access via deploy key

    EXAMPLES:

    Call without optional arguments to create GitHub repo, add deploy key to it and the respective private key into
    box setup secrets:
    >>> iiotctl project configure-github-repository

    Call with argument '--initialize' to also add, commit and push all changes to the to-be-created github repository:
    >>> iiotctl project configure-github-repository --initialize

        This initial GitHub commit can only be done once. By default it is named "Initial commit".

    Call with arguments '--initialize' and '--commit-msg' to make initial commit with custom commit message:
    >>> iiotctl project configure-github-repository --initialize --commit-msg "Your commit message"

    Call with arguments '--initialize' and '--override' to first add and commit all local 'main' branch changes as
    'Initial commit' and then force-push 'main' to override the already existing github repository 'main'. Also renew
    the 'argo' deploy key:
    >>> iiotctl project configure-github-repository --initialize --override

        Useful if you did reset a talos vm, cleared out your local repo directory and copied a new base box version
        into it, but can't test the setup of this new base box repo version on the vm because there are still the files
        of the previous base box repo version committed in the github repo.
    """

    _setup_repo.configure_github_repository(initialize, commit_msg, override)


@app.command(rich_help_panel="Lowlevel Commands")
def render_argo_manifests(
    app: Annotated[
        List[str],
        typer.Option(
            "--app", "-a", help="""one or more specific system-apps or user-apps to create collective deployment
            manifests for"""
        )
    ] = ["*"]
):
    """
    create a collective deployment manifest for each system-app and user-app with 'argo-template' directory;
    output manifest at: '.../APP_NAME/argo/APP_NAME.yaml'

    EXAMPLES:

    Call without arguments to create collective deployment manifests for all system-apps and user-apps
    in their respective /argo directory using the kustomization file(s) in /argo-template:
    >>> iiotctl project kustomize-argo-templates

    Call with additional argument '--app' if you want to create collective
    deployment manifests only for certain system-apps and/or user-apps:
    >>> iiotctl project kustomize-argo-templates -app "openebs" -app "traefik
    """

    _render_manifests.render_argo_manifests(app)


@app.command(rich_help_panel="Lowlevel Commands")
def seal_secret(
    secret_file: Annotated[str, typer.Option("--secret-file", help="secret (input) file path")] = "",
    sealed_secret_file: Annotated[
        str, typer.Option("--sealed-secret-file", help="sealed-secret (output) file path")
    ] = "",
    init: Annotated[
        bool, typer.Option("--init", "-i", help="initialize the sealed secret public encryption key")
    ] = False,
    bootstrap: Annotated[
        bool, typer.Option("--bootstrap", "-b", help="create machine-patches before bootstrap")
    ] = False
):
    """
    Seal a secret

    EXAMPLES:

    Call with arguments '--secret-file' and '--sealed-secret-file' to seal a secret:
    >>> iiotctl project seal-secret --secret-file path/to/secret.yaml --sealed-secret-file path/to/sealed-secret.yaml

    Call with argument '--bootstrap' to create the machine patch with the sealed secrets private key before booting
    the box:
    >>> iiotctl project seal-secret --bootstrap

    Call with argument '--init' to initialize or renew the encryption key on a running box (needs k8s connection):
    >>> iiotctl project seal-secret --init
    """

    _seal_secret.seal_secret(secret_file, sealed_secret_file, init, bootstrap)
