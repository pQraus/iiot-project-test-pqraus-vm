import json
from pathlib import Path

from ._common import TyperAbort


def load_configuration(config_file: Path):
    try:
        with open(config_file, "r") as f:
            configuration = json.load(f)
    except FileNotFoundError as exc:
        raise TyperAbort(exc, f"Can't find the task configuration file: {config_file.resolve()}")
    except json.JSONDecodeError as exc:
        raise TyperAbort(f"Can't decode the task configuration ({config_file.resolve()}):", exc)
    if type(configuration) is not dict:
        raise TyperAbort(f"Expected dict, got: {type(configuration)}")
    return configuration


def load_asdf_plugins(asdf_file: Path):
    with open(asdf_file, "r") as rd:
        plugins = rd.read().split("\n")[1:-1]

    asdf_plugins = {}

    for p in plugins:
        tmp = p.split("#")
        src = tmp[1].split(" ")[-1]
        tool, vers = tmp[0].rstrip().split(" ")
        asdf_plugins.update({tool: {"version": vers, "source": src}})
    
    return asdf_plugins


def get_config_entry(config: dict, entry_name: str):
    try:
        value = config[entry_name]
    except KeyError:
        raise TyperAbort(f"Can't get the '{entry_name}' entry from the given dictionary")
    return value
