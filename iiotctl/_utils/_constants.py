from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
MACHINE_DIR = REPO_ROOT / "machine"
REPO_README = REPO_ROOT / "README.md"
JQ_MODULES_DIR = MACHINE_DIR / "jq-utils"
TALOS_CONFIG_PROJECT = MACHINE_DIR / "talosconfig-teleport"
TALOS_CONFIG_USER = Path.home() / ".talos" / "config"
K8S_CONFIG_USER = Path.home() / ".kube" / "config"
TASKS_TMP_DIR = REPO_ROOT / ".tasks"
PATCH_LOCATIONS = ["machine/config/*/_*.jq", "system-apps/*/machine-patches/_*.jq"]
EXCLUDE_SYNC_PATCHES = ["**/_*.boot.jq"]
DEFAULT_MACHINE_CONFIG_ID = "v1alpha1"

TASK_CONFIG_PATH = Path(__file__).parent.parent / "tasks_config.json"
ASDF_CONFIG_PATH = REPO_ROOT / ".tool-versions"
