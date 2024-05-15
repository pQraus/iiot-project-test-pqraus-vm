import json
import subprocess as sp
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx

from . import _teleport as teleport
from ._config import BOX_NAME, CONTAINER_REGISTIRES, REPO_ROOT
from ._sealed_secrets import check_if_sealing_possible, seal_secret

TELEPORT_APP_NAME = "box-token-provider"

REGISTRY_ACCESS_FILE = REPO_ROOT / "machine/config/registry-credentials/_registry-access.jq"
DOCKER_REGISTRY_URL = "registry-1.docker.io"
DOCKER_REGISTRY_ACCESS_FILE = REPO_ROOT / "machine/config/registry-credentials/docker-access.jq"
SCHULZ_REGISTRY_URL = "registry.schulzdevcloud.com"
SCHULZ_REGISTRY_ACCESS_FILE = REPO_ROOT / "machine/config/registry-credentials/schulz-registry-access.jq"

REMOTE_MONITORING = REPO_ROOT / "system-apps/monitoring/argo/remote"
GRAFANA_SECRET = REMOTE_MONITORING / "victoria-metrics-agent/plain-secret/secret.yaml"
GRAFANA_SEALED_SECRET = REMOTE_MONITORING / "victoria-metrics-agent/sealed-secret.yaml"


REGISTRY_ACCESS_CONTENT = """# This file was created by 'invoke init.create-token' and should not be changed

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


def docker_validator() -> bool:
    if 'docker' not in CONTAINER_REGISTIRES:
        print("Docker is not activated. If needed, use 'copier update --trust' to add it")
        return False
    if not REGISTRY_ACCESS_FILE.exists():
        print("Registry access jq file does not exist. Use 'copier update --trust -A' to fetch the neccessary files")
        return False
    return True


def schulz_registry_validator() -> bool:
    if 'schulz_registry' not in CONTAINER_REGISTIRES:
        print("Schulz registry is not activated. If needed, use 'copier update --trust' to add it")
        return False
    if not REGISTRY_ACCESS_FILE.exists():
        print("Registry access jq file does not exist. Use 'copier update --trust -A' to fetch the neccessary files")
        return False
    return True


def grafana_validator() -> bool:
    if not Path(REMOTE_MONITORING).exists():
        print("Remote monitoring is not installed and therefore the token is not required")
        return False
    if not check_if_sealing_possible():
        return False
    return True


def write_registry_access(provider: str, access_file: Path, registry_url: str, token: Token):
    parent = access_file.parent
    if not parent.exists():
        print(f"Folder for registry credentials does not exist ({parent})")
        return

    content = REGISTRY_ACCESS_CONTENT.format(
        provider=provider,
        registry=registry_url,
        username=token.username,
        password=token.token)

    with open(access_file, "w") as file:
        file.write(content)


def write_docker_token_to_file(token: Token):
    write_registry_access(
        "docker",
        DOCKER_REGISTRY_ACCESS_FILE,
        DOCKER_REGISTRY_URL,
        token)


def write_schulz_registry_token_to_file(token: Token):
    write_registry_access(
        "schulz_registry",
        SCHULZ_REGISTRY_ACCESS_FILE,
        SCHULZ_REGISTRY_URL,
        token)


def write_grafana_token_to_file(token: Token):
    if not Path(GRAFANA_SECRET).exists():
        print(f"Secret file for grafana token does not exist ({GRAFANA_SECRET})")
    sp.check_output(["yq", f'.stringData.GRAFANA_TOKEN = "{token.token}"', "-i", GRAFANA_SECRET])
    seal_secret(str(GRAFANA_SECRET), str(GRAFANA_SEALED_SECRET))


BOX_TOKEN_PROVIDER_CONF = {
    "docker": {
        "api_path": "/api/v1/tokens/registry/docker",
        "file_writer": write_docker_token_to_file,
        "validator": docker_validator,
        "post_message": "Run 'invoke sync -a reboot' to sync the new token (The box will reboot!)"
    },
    "schulz_registry": {
        "api_path": "/api/v1/tokens/registry/schulz",
        "file_writer": write_schulz_registry_token_to_file,
        "validator": schulz_registry_validator,
        "post_message": "Run 'invoke sync -a reboot' to sync the new token (The box will reboot!)"
    },
    "grafana": {
        "api_path": "/api/v1/tokens/grafana",
        "file_writer": write_grafana_token_to_file,
        "validator": grafana_validator,
        "post_message": "Commit & push the changed file to use the created token"
    }
}


def create_tokens(providers: list[Provider]):

    print("Connecting to teleport app ...")
    teleport.login()
    teleport.login_app(TELEPORT_APP_NAME)

    app_config = AppConfig(**json.loads(sp.check_output(["tsh", "app", "config", TELEPORT_APP_NAME, "--format=json"])))

    with httpx.Client(base_url=app_config.uri, cert=(app_config.cert, app_config.key)) as client:
        for provider in providers:
            provider_conf = BOX_TOKEN_PROVIDER_CONF[provider]
            if not provider_conf["validator"]():
                continue
            try:
                print(f"\n--- {provider} ---")
                print("Requesting token ...")
                token = request_token(client, provider_conf)
                print("Sucessfully received token")
                print("Writing tokens into file...")
                provider_conf["file_writer"](token)
                print("Successfilly written token")
                print(provider_conf["post_message"])
            except httpx.HTTPStatusError as ex:
                if ex.response.status_code == httpx.codes.CONFLICT:
                    print("Token already exists. Contact an admin to get it removed before creating a new one")
                    continue
                print(f"Error while requesting token: {str(ex)}: {ex.response.text}")
            except Exception as ex:
                print(f"Error while creating token: {type(ex)}; {str(ex)}")

    sp.check_output(["tsh", "app", "logout"])


def request_token(client: httpx.Client, provider_conf: dict) -> Token:
    response = client.post(
        provider_conf["api_path"],
        params={"box_name": BOX_NAME})
    response.raise_for_status()

    return Token(**response.json())
