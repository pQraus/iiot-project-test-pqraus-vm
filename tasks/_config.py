"""Config for the invoke tasks

Module loads, provides the config for the invoke tasks
"""
import json
import sys
from pathlib import Path
from typing import Dict


def _load_configuration(config_file: Path):
    try:
        with open(config_file, "r") as f:
            configuration = json.load(f)
    except FileNotFoundError:
        print(
            f"Can't find the task configuration file: {config_file.resolve()}",
            file=sys.stderr,
        )
        exit(1)
    except json.JSONDecodeError as e:
        print(
            f"Can't decode the task configuration ({config_file.resolve()}):",
            file=sys.stderr,
        )
        print("\t", e, file=sys.stderr)
        exit(1)
    if type(configuration) is not dict:
        print("What are you doing??")
        exit(1)
    return configuration


def _load_asdf_plugins(asdf_file: Path):
    with open(asdf_file, "r") as rd:
        plugins = rd.read().split("\n")[1:-1]

    asdf_plugins = {}

    for p in plugins:
        tmp = p.split("#")
        src = tmp[1].split(" ")[-1]
        tool, vers = tmp[0].rstrip().split(" ")
        asdf_plugins.update({tool: {"version": vers, "source": src}})

    return asdf_plugins


def _get_config_entry(config: dict, entry_name: str):
    try:
        value = config[entry_name]
    except KeyError:
        print(
            f"Can't get the '{entry_name}' entry from the given dictionary",
            file=sys.stderr,
        )
        exit(1)
    return value


REPO_ROOT = (Path(__file__).parent / "..").resolve()
MACHINE_DIR = REPO_ROOT / "machine"
JQ_MODULES_DIR = MACHINE_DIR / "jq-utils"
TALOS_CONFIG_PROJECT = MACHINE_DIR / "talosconfig-teleport"
TALOS_CONFIG_USER = Path.home() / ".talos" / "config"
K8S_CONFIG_USER = Path.home() / ".kube" / "config"
TASKS_TMP_DIR = REPO_ROOT / ".tasks"
PATCH_LOCATIONS = ["machine/config/*/_*.jq", "system-apps/*/machine-patches/_*.jq"]
EXCLUDE_SYNC_PATCHES = ["**/_*.boot.jq"]
DEFAULT_MACHINE_CONFIG_ID = "v1alpha1"

# system encoding
ENCODING = sys.stdout.encoding

# config from task config file
_config_file = Path(__file__).parent / "tasks_config.json"
_config = _load_configuration(_config_file)

BOX_NAME = _get_config_entry(_config, "box_name")
K8S_VERSION = _get_config_entry(_config, "k8s_version")
LOCAL_K8S_ACCESS = _get_config_entry(_config, "local_k8s_access")
PROJECT_REPO = _get_config_entry(_config, "project_repo")
REPO_ON_GITHUB = _get_config_entry(_config, "repo_on_github")
TALOS_VERSION = _get_config_entry(_config, "talos_version")
TALOS_INSTALLER = _get_config_entry(_config, "talos_installer")
TALOS_EXTENSIONS: Dict[str, str] = _get_config_entry(_config, "talos_extensions")
TELEPORT_ENABLED = _get_config_entry(_config, "teleport_enabled")
TELEPORT_PROXY_URL = _get_config_entry(_config, "teleport_proxy_url")
CONTAINER_REGISTIRES = _get_config_entry(_config, "container_registries")

# read from asdf .tool-versions file
ASDF_PLUGINS: dict = _load_asdf_plugins(REPO_ROOT / ".tool-versions")

DEP_GH = ["gh", "version", _get_config_entry(ASDF_PLUGINS["gh"], "version")]
DEP_GPG = ["gpg", "--version"]
DEP_HELM = ["helm", "version", _get_config_entry(ASDF_PLUGINS["helm"], "version")]
DEP_JQ = ["jq", "--version", _get_config_entry(ASDF_PLUGINS["jq"], "version")]
DEP_KUBECTL = ["kubectl", "version -o yaml --client", _get_config_entry(ASDF_PLUGINS["kubectl"], "version")]
DEP_TALOSCTL = ["talosctl", "version --client", _get_config_entry(ASDF_PLUGINS["talosctl"], "version")]
DEP_TCTL = ["tctl", "version"]
DEP_TSH = ["tsh", "version", _get_config_entry(ASDF_PLUGINS["teleport-community"], "version")]
DEP_YQ = ["yq", "--version", _get_config_entry(ASDF_PLUGINS["yq"], "version")]
DEP_KUBESEAL = ["kubeseal", "--version", _get_config_entry(ASDF_PLUGINS["kubeseal"], "version")]