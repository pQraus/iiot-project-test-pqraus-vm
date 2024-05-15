from importlib.metadata import version as get_version

PIPX_COMMAND = "pipx install git+https://github.com/SchulzSystemtechnik/iiot-misc-invoke-dist.git"

try:
    from packaging.version import parse as parse_version
except ImportError:
    if get_version("invoke_dist") == "0.1.0":
        print(f"Update invoke-dist using the following command: '{PIPX_COMMAND} --force'")
        exit(1)
    raise

DESIRED_VERSION = parse_version("1.0.0")


def check_version():
    current_version = parse_version(get_version("invoke_dist"))

    if current_version.major > DESIRED_VERSION.major:
        print(f"Downgrade to {DESIRED_VERSION} using the following command: '{PIPX_COMMAND}@{DESIRED_VERSION} --force'")
        exit(1)
    if DESIRED_VERSION > current_version:
        print(f"Upgrade to {DESIRED_VERSION} using the following command: '{PIPX_COMMAND}@{DESIRED_VERSION} --force'")
        exit(1)
