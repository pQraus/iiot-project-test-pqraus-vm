import shutil
from typing import List

from rich import print

from .._utils import _check as check
from .._utils import _common as common
from .._utils._common import Command
from .._utils._config import DEP_HELM, DEP_KUBECTL, REPO_ROOT


@check.dependency(*DEP_HELM)
@check.dependency(*DEP_KUBECTL)
def render_argo_manifests(apps: List[str]):

    # selection of argo-templates to be kustomized
    templates_locations = [f"system-apps/{app}/argo-template" for app in apps]  # templates for system-apps
    templates_locations.extend([f"user-apps/{app}/argo-template" for app in apps])  # templates for user-apps
    template_paths = common.glob_files(REPO_ROOT, *templates_locations)

    for path in template_paths:
        relative_path = str(path.relative_to(REPO_ROOT))
        absolute_path = str(path.absolute())
        manifest = "/argo/" + absolute_path.split("/")[-2] + ".yaml"

        print(f"Kustomizing template: ./{relative_path} > ./{relative_path.replace('/argo-template', manifest)} ...")

        # remove old helm chart dir to ensure usage of correct resources
        shutil.rmtree(path / "charts", ignore_errors=True)

        # if no argo directory exists in app dir >> create new one
        if not (path.parent / "argo").exists():
            (path.parent / "argo").mkdir(exist_ok=True)

        # kustomize selection of argo-templates and transfer output into /argo/APP_NAME.yaml files
        Command.check_output(
            [
                "kubectl",
                "kustomize",
                "--enable-helm",
                absolute_path,
                "-o",
                absolute_path.replace("/argo-template", manifest)
            ]
        )
