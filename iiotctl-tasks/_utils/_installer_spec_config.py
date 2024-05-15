from dataclasses import dataclass
from typing import Dict, List

import typer
from yaml import safe_load

from ._common import print_error
from ._config import REPO_ROOT, TALOS_INSTALLED_EXTENSIONS

_INSTALLER_IMAGES_FILE = REPO_ROOT / "iiotctl-tasks" / "installer-images.yaml"


@dataclass
class MetaData:
    name: str
    revision: int
    talos_version: str
    installer_image_repo: str


@dataclass
class Extension:
    name: str
    version: str
    image_repo: str
    image_tag: str


@dataclass
class InstallerImage:
    id: int
    extensions: List[str]
    name: str = None


@dataclass
class InstallerSpecs:
    version: str
    metadata: MetaData
    extensions: List[Extension]
    images: List[InstallerImage]

    def __post_init__(self):
        if self.version != "v1":
            print_error(f"Schema version {self.version} in {_INSTALLER_IMAGES_FILE} isn't supported")
            raise typer.Abort()
        self.metadata = MetaData(**self.metadata)
        self.extensions = [Extension(**ext) for ext in self.extensions]
        self.images = [InstallerImage(**im) for im in self.images]


def _load_installer_specs():
    with open(_INSTALLER_IMAGES_FILE, "r") as f:
        installer_specs_raw = safe_load(f)
    return InstallerSpecs(**installer_specs_raw)


def load_repo_extension_versions() -> Dict[str, str]:
    """load the versions of the extensions which are specified in the repo"""
    installer_specs = _load_installer_specs()
    available_exts = {
        ext.name: list_id for list_id, ext in enumerate(installer_specs.extensions)
    }

    repo_extension_versions = {}
    for ext_name in TALOS_INSTALLED_EXTENSIONS:
        extension_id = available_exts.get(ext_name)
        if extension_id is None:
            print_error(f"Extension {ext_name} isn't defined in in {_INSTALLER_IMAGES_FILE}")
            raise typer.Abort()
        extension = installer_specs.extensions[extension_id]
        repo_extension_versions[ext_name] = extension.version
    return repo_extension_versions


def load_repo_installer_image_ref() -> str:
    """load the full installer image specified by the extensions in the repo"""
    installer_specs = _load_installer_specs()
    for image in installer_specs.images:
        if set(image.extensions) == set(TALOS_INSTALLED_EXTENSIONS):
            repo = installer_specs.metadata.installer_image_repo
            version = installer_specs.metadata.talos_version
            revision = installer_specs.metadata.revision
            return f"{repo}:{version}-{revision}-{image.id}"
    print_error(f"Can't load an installer image for the extensions {TALOS_INSTALLED_EXTENSIONS}")
    raise typer.Abort()
