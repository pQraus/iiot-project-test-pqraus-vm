from typing import Dict, List, Tuple

import questionary
from rich import print
from rich.table import Table
from rich.text import Text

from .._utils import _check as check
from .._utils import _common as common
from .._utils import _talosctl as talosctl
from .._utils._common import TyperAbort
from .._utils._constants import MACHINE_DIR, REPO_ROOT, TALOS_CONFIG_PROJECT

_DISK_SELECTOR_TEMP = """# This file was created by 'iiotctl machine resources' task and should not be manually changed

def disk_selector:
{{
  "model": "{model}",
  {second_identifier}
}};
"""

_DISK_SELECTOR_PATCHFILE = MACHINE_DIR / "config" / "disk" / "disk-selector.jq"


def _print_resource_overview(table_name: str, columns: Tuple[str], datasets: Dict[str, Dict[str, str]]):
    table = Table(title=table_name, show_lines=True)
    table.add_column("NAME")
    for clm in columns:
        table.add_column(clm)
    for name, data in datasets.items():
        table.add_row(name, *[Text(data[clm]) for clm in columns])  # use rich 'Text' => don't render unicode emojis
    print(table)
    print()


def _render_disk_selector_patch(model: str, second_identifier: str):
    with open(_DISK_SELECTOR_PATCHFILE, "w") as file:
        file.write(_DISK_SELECTOR_TEMP.format(model=model, second_identifier=second_identifier))
    print(f"Rendered file: {_DISK_SELECTOR_PATCHFILE.relative_to(REPO_ROOT)}")
    print()


def _parse_ethernet_datasets(links: List[Dict]) -> Dict[str, Dict[str, str]]:
    eth_datasets = {}
    for eth in links:
        spec = eth["spec"]
        if not (spec["kind"] == "" and spec["type"] == "ether"):
            continue
        hardware_addr, product = spec["hardwareAddr"], spec["product"]
        eth_datasets.update({eth["metadata"]["id"]: {"HARDWARE_ADDRESS": hardware_addr, "PRODUCT": product}})
    return eth_datasets


def _determine_talos_kwargs(machine_ip: str | None, use_current_context: bool):
    if use_current_context:
        return {}
    elif machine_ip is not None:
        return {"insecure": "true", "nodes": machine_ip}
    else:
        return {"talosconfig": TALOS_CONFIG_PROJECT.resolve()}


def resources(machine_ip: str | None, patch: bool, use_current_context: bool):
    if machine_ip is not None:
        check.ip(machine_ip)

    common.print_if(
        "Ensure that 'iiotctl connect talos' is running", not use_current_context
    )
    config_kwargs = _determine_talos_kwargs(machine_ip, use_current_context)

    eth_links = talosctl.get(resource="links", **config_kwargs)
    eth_datasets = _parse_ethernet_datasets(eth_links)
    _print_resource_overview("Ethernet Interfaces (talosctl get links)", ("HARDWARE_ADDRESS", "PRODUCT"), eth_datasets)

    disk_datasets = talosctl.disks(**config_kwargs)
    _print_resource_overview("Disks (talosctl disks)", ("MODEL", "SIZE"), disk_datasets)

    if not patch:
        return

    disk_name: str = questionary.select(
        "Select disk to be used for talos installation:",
        choices=disk_datasets.keys()
    ).unsafe_ask()

    model = disk_datasets[disk_name].get("MODEL")
    if model is None:
        raise TyperAbort(f"Missing 'MODEL' data for disk: {disk_name}.")
    wwid = disk_datasets[disk_name].get("WWID")
    bus_path = disk_datasets[disk_name].get("BUS_PATH")
    if (wwid is None) and (bus_path is None):
        raise TyperAbort(f"Data of at least 'WWID' or 'BUS_PATH required for disk: {disk_name}.")

    second_identifier = f'"busPath": "{bus_path}"' if wwid is None else f'"wwid": "{wwid}"'
    _render_disk_selector_patch(model, second_identifier)
