import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List

import httpx
import typer
from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _teleport
from .._utils._common import Command, TyperAbort, print_error
from .._utils._config import BOX_NAME, CONTAINER_REGISTRIES, DEP_TCTL, DEP_TSH
from .._utils._constants import REPO_ROOT
from ._seal_secret import _check_if_sealing_possible, _seal_secret

TELEPORT_APP_NAME = "box-token-provider"

REGISTRY_ACCESS_FILE = REPO_ROOT / "machine/config/registry-credentials/_registry-access.jq"
DOCKER_REGISTRY_URL = "registry-1.docker.io"
DOCKER_REGISTRY_ACCESS_FILE = REPO_ROOT / "machine/config/registry-credentials/docker-access.jq"
SCHULZ_REGISTRY_URL = "registry.schulzdevcloud.com"
SCHULZ_REGISTRY_ACCESS_FILE = REPO_ROOT / "machine/config/registry-credentials/schulz-registry-access.jq"

REMOTE_MONITORING = REPO_ROOT / "system-apps/monitoring/argo/remote"
GRAFANA_SECRET = REMOTE_MONITORING / "victoria-metrics-agent/plain-secret/secret.yaml"
GRAFANA_SEALED_SECRET = REMOTE_MONITORING / "victoria-metrics-agent/sealed-secret.yaml"


REGISTRY_ACCESS_CONTENT = """# This file was created by 'iiotctl project create-token' and should not be changed

def {provider}_access:
{{
  "{registry}": {{
    "auth": {{
      "username": "{username}",
      "password": "{password}"
    }}
  }}
}};
"""


class Provider(str, Enum):
    DOCKER = "docker"
    SCHULZ_REGISTRY = "schulz_registry"
    GRAFANA = "grafana"


@dataclass
class AppConfig:
    name: str
    uri: str
    ca: str
    cert: str
    key: str
    curl: str


@dataclass
class Token:
    username: str
    token: str


def _docker_validator() -> bool:
    if 'docker' not in CONTAINER_REGISTRIES:
        print_error("Docker is not activated. If needed, use 'copier update --trust' to add it")
        return False
    if not REGISTRY_ACCESS_FILE.exists():
        print_error(
            "Registry access jq file does not exist. Use 'copier update --trust -A' to fetch the necessary files"
        )
        return False
    return True


def _schulz_registry_validator() -> bool:
    if 'schulz_registry' not in CONTAINER_REGISTRIES:
        print_error("Schulz registry is not activated. If needed, use 'copier update --trust' to add it")
        return False
    if not REGISTRY_ACCESS_FILE.exists():
        print_error(
            "Registry access jq file does not exist. Use 'copier update --trust -A' to fetch the necessary files"
        )
        return False
    return True


def _grafana_validator() -> bool:
    if not Path(REMOTE_MONITORING).exists():
        print_error("Remote monitoring is not installed and therefore the token is not required")
        return False
    if not _check_if_sealing_possible():
        return False
    return True


def _write_registry_access(provider: str, access_file: Path, registry_url: str, token: Token):
    parent = access_file.parent
    if not parent.exists():
        print_error(f"Folder for registry credentials does not exist ({parent})")
        return

    content = REGISTRY_ACCESS_CONTENT.format(
        provider=provider,
        registry=registry_url,
        username=token.username,
        password=token.token)

    with open(access_file, "w") as file:
        file.write(content)


def _write_docker_token_to_file(token: Token):
    _write_registry_access(
        "docker",
        DOCKER_REGISTRY_ACCESS_FILE,
        DOCKER_REGISTRY_URL,
        token)


def _write_schulz_registry_token_to_file(token: Token):
    _write_registry_access(
        "schulz_registry",
        SCHULZ_REGISTRY_ACCESS_FILE,
        SCHULZ_REGISTRY_URL,
        token)


def _write_grafana_token_to_file(token: Token):
    if not Path(GRAFANA_SECRET).exists():
        print_error(f"Secret file for grafana token does not exist ({GRAFANA_SECRET})")
    with common.patch_yaml_file(file_path=GRAFANA_SECRET) as secret:
        secret["stringData"]["GRAFANA_TOKEN"] = token.token

    _seal_secret(str(GRAFANA_SECRET), str(GRAFANA_SEALED_SECRET))


BOX_TOKEN_PROVIDER_CONF = {
    "docker": {
        "api_path": "/api/v1/tokens/registry/docker",
        "file_writer": _write_docker_token_to_file,
        "validator": _docker_validator,
        "post_message": "Run 'iiotctl machine sync -a reboot' to sync the new token (The box will reboot!)"
    },
    "schulz_registry": {
        "api_path": "/api/v1/tokens/registry/schulz",
        "file_writer": _write_schulz_registry_token_to_file,
        "validator": _schulz_registry_validator,
        "post_message": "Run 'iiotctl machine sync -a reboot' to sync the new token (The box will reboot!)"
    },
    "grafana": {
        "api_path": "/api/v1/tokens/grafana",
        "file_writer": _write_grafana_token_to_file,
        "validator": _grafana_validator,
        "post_message": "Commit & push the changed file to use the created token"
    }
}


def _request_token(client: httpx.Client, provider_conf: dict) -> Token:
    response = client.post(
        provider_conf["api_path"],
        params={"box_name": BOX_NAME})
    response.raise_for_status()

    return Token(**response.json())


def _create_provider_tokens(providers: List[Provider]):
    print("Connecting to teleport app ...")
    _teleport.login_app(TELEPORT_APP_NAME)

    app_config = AppConfig(
        **json.loads(Command.check_output(cmd=["tsh", "app", "config", TELEPORT_APP_NAME, "--format=json"]))
    )

    with httpx.Client(base_url=app_config.uri, cert=(app_config.cert, app_config.key)) as client:
        for provider in providers:
            provider_conf = BOX_TOKEN_PROVIDER_CONF[provider]
            if not provider_conf["validator"]():
                continue
            try:
                print(f"\n--- {provider} ---")
                print("Requesting token ...")
                token = _request_token(client, provider_conf)
                print("Sucessfully received token")
                print("Writing tokens into file...")
                provider_conf["file_writer"](token)
                print("Successfilly written token")
                print(provider_conf["post_message"])
            except httpx.HTTPStatusError as ex:
                if ex.response.status_code == httpx.codes.CONFLICT:
                    print_error("Token already exists. Contact an admin to get it removed before creating a new one")
                    continue
                print_error(f"While requesting token: {str(ex)}: {ex.response.text}")
            except Exception as ex:
                print_error(f"While creating token: {type(ex)}; {str(ex)}")


def _configure_developer_tokens(providers: List[Provider]):

    typer.secho(
        "Configure Schulz Dockerhub, Container Registry and Grafana access via custom usernames and access tokens:",
        underline=True
    )
    print()
    for provider in providers:
        provider_conf = BOX_TOKEN_PROVIDER_CONF[provider]
        if not provider_conf["validator"]():
            raise TyperAbort()
        try:
            name = input(f"Enter '{provider}' developer username:\n") if provider != Provider.GRAFANA else ""
            token = input(f"Enter developer '{provider}' access token:\n")
            print(50*"~")
            provider_conf["file_writer"](Token(name, token))
        except Exception as ex:
            raise TyperAbort(f"While creating token:", f"{type(ex)}: {str(ex)}")

    print("Successfully rendered access token manifests.")


def _create_teleport_token(expiration_time: str):

    PATH_JOIN_TOKEN = Path("initial-secrets/join-token.yaml")
    PATH_TELEPORT_CONFIGURATOR_PATCHES = REPO_ROOT / "system-apps/teleport-configurator/machine-patches"
    token_add_bash_cmd = ["tctl", "tokens", "add", "--type=app,kube", "--format=json", "--ttl", expiration_time]

    # log into teleport cluster referenced by url in '/tasks/tasks_config.json' + get join token
    new_token = Command.check_output(token_add_bash_cmd)
    new_token = json.loads(new_token)["token"]

    print("Successfully obtained teleport join token.")

    # patch token into box secrets
    with common.patch_yaml_file(file_path=PATH_TELEPORT_CONFIGURATOR_PATCHES / PATH_JOIN_TOKEN) as secret:
        secret["stringData"]["join-token"] = new_token

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


@check.config_parameter("TELEPORT_ENABLED", True)
@check.dependency(*DEP_TSH)
@check.dependency(*DEP_TCTL)
def create_token(
    grafana: bool,
    docker: bool,
    schulz_registry: bool,
    teleport: bool,
    ttl: str,
    dev: bool
):

    selected_provider = []
    selected_provider += ([Provider.GRAFANA] if grafana else [])
    selected_provider += ([Provider.DOCKER] if docker else [])
    selected_provider += ([Provider.SCHULZ_REGISTRY] if schulz_registry else [])

    if not len(selected_provider) > 0:
        print_error("Choose at least one token to be created")
        return

    if not dev or teleport:
        Command.check_output(["tsh", "logout"])
        _teleport.login()

        if teleport:
            _create_teleport_token(ttl)
            print()

    if dev:
        _configure_developer_tokens(selected_provider)
    else:
        _create_provider_tokens(selected_provider)
