"""Config for the iiotctl tasks

Module loads, provides the config for the iiotctl tasks
"""

from typing import Dict, List

from ._constants import ASDF_CONFIG_PATH, TASK_CONFIG_PATH
from ._loaders import get_config_entry, load_asdf_plugins, load_configuration

# config from task config file
TASK_CONFIG = load_configuration(TASK_CONFIG_PATH)

BOX_NAME: str = get_config_entry(TASK_CONFIG, "box_name")
BASE_REPO_VERSION: str = get_config_entry(TASK_CONFIG, "base_repo_version")
K8S_VERSION: str = get_config_entry(TASK_CONFIG, "k8s_version")
LOCAL_K8S_ACCESS: bool = get_config_entry(TASK_CONFIG, "local_k8s_access")
PROJECT_REPO: str = get_config_entry(TASK_CONFIG, "project_repo")
REPO_ON_GITHUB: bool = get_config_entry(TASK_CONFIG, "repo_on_github")
TALOS_VERSION: str = get_config_entry(TASK_CONFIG, "talos_version")
TALOS_INSTALLED_EXTENSIONS: List[str] = get_config_entry(TASK_CONFIG, "talos_installed_extensions")
TELEPORT_ENABLED: bool = get_config_entry(TASK_CONFIG, "teleport_enabled")
TELEPORT_PROXY_URL: str = get_config_entry(TASK_CONFIG, "teleport_proxy_url")
IS_DEV_ENV: bool = get_config_entry(TASK_CONFIG, "is_dev_env")
CONTAINER_REGISTRIES: List[str] = get_config_entry(TASK_CONFIG, "container_registries")
REMOTE_MONITORING: bool = get_config_entry(TASK_CONFIG, "remote_monitoring")

# read from asdf .tool-versions file
ASDF_PLUGINS: Dict[str, Dict[str, str]] = load_asdf_plugins(ASDF_CONFIG_PATH)

DEP_GH = ["gh", "version", get_config_entry(ASDF_PLUGINS["gh"], "version")]
DEP_GPG = ["gpg", "--version"]
DEP_HELM = ["helm", "version", get_config_entry(ASDF_PLUGINS["helm"], "version")]
DEP_JQ = ["jq", "--version", get_config_entry(ASDF_PLUGINS["jq"], "version")]
DEP_KUBECTL = ["kubectl", "version -o yaml --client", get_config_entry(ASDF_PLUGINS["kubectl"], "version")]
DEP_TALOSCTL = ["talosctl", "version --client", get_config_entry(ASDF_PLUGINS["talosctl"], "version")]
DEP_TCTL = ["tctl", "version"]
DEP_TSH = ["tsh", "version", get_config_entry(ASDF_PLUGINS["teleport-community"], "version")]
DEP_KUBESEAL = ["kubeseal", "--version", get_config_entry(ASDF_PLUGINS["kubeseal"], "version")]