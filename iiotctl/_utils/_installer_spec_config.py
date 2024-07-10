from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from yaml import safe_load

from ._common import TyperAbort

_INSTALLER_IMAGES_FILE = Path(__file__).parent.parent / "installer-images.yaml"


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
            raise TyperAbort(f"Schema version {self.version} in {_INSTALLER_IMAGES_FILE} isn't supported")
        self.metadata = MetaData(**self.metadata)
        self.extensions = [Extension(**ext) for ext in self.extensions]
        self.images = [InstallerImage(**im) for im in self.images]


def _load_installer_specs(specs_file: Path = _INSTALLER_IMAGES_FILE):
    with open(specs_file, "r") as f:
        installer_specs_raw = safe_load(f)
    return InstallerSpecs(**installer_specs_raw)


def load_repo_extension_versions(required_extensions: List[str]) -> Dict[str, str]:
    """load the versions of the extensions which are specified in the repo"""
    installer_specs = _load_installer_specs()
    available_exts = {
        ext.name: list_id for list_id, ext in enumerate(installer_specs.extensions)
    }

    repo_extension_versions = {}
    for ext_name in required_extensions:
        extension_id = available_exts.get(ext_name)
        if extension_id is None:
            raise TyperAbort(f"Extension {ext_name} isn't defined in {_INSTALLER_IMAGES_FILE}")
        extension = installer_specs.extensions[extension_id]
        repo_extension_versions[ext_name] = extension.version
    return repo_extension_versions


def load_repo_installer_image_ref(required_extensions: List[str]) -> str:
    """load the full installer image specified by the extensions in the repo"""
    installer_specs = _load_installer_specs()
    for image in installer_specs.images:
        if set(image.extensions) == set(required_extensions):
            repo = installer_specs.metadata.installer_image_repo
            version = installer_specs.metadata.talos_version
            revision = installer_specs.metadata.revision
            return f"{repo}:{version}-{revision}-{image.id}"
    raise TyperAbort(f"Can't load an installer image for the extensions {required_extensions}.")
