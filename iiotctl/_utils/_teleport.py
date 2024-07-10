import json
import tempfile
from pathlib import Path

from rich import print

from ._common import Command


def create_local_cert(ttl: str):
    """create a teleport cert which can be used for local access via tctl

    ensure that the user is logged in to teleport"""

    status = Command.check_output(
        cmd=["tsh", "status", "-f", "json"],
        additional_error_msg="Can't get the current status of your teleport profile."
    )

    tsh_status = json.loads(status)
    username = tsh_status["active"]["username"]

    # tmpdir is required because tctl can only write the certs to a file
    with tempfile.TemporaryDirectory("teleport-crt") as td:
        tmp_dir = Path(td)
        cert_files = tmp_dir / "teleport"
        Command.check_output(
            [
                "tctl",
                "auth",
                "sign",
                "--out",
                cert_files.resolve(),
                "--format",
                "tls",
                "--user",
                username,
                "--ttl",
                ttl,
            ]
        )
        # load the cert and key as vars
        cert_file = cert_files.with_suffix(".crt")
        with open(cert_file, "rb") as f_cert:
            cert = f_cert.read()
        key_file = cert_files.with_suffix(".key")
        with open(key_file, "rb") as f_key:
            key = f_key.read()

    return cert, key


def login(proxy_url: str):
    """log in an user to teleport"""

    logged_in = Command.check(cmd=["tsh", "status"])
    if logged_in:  # the user is already logged in
        return

    # can't get the current user status -> try if a login can fix that problem
    print(f"Login to teleport cluster '{proxy_url}':\n")
    Command.check_output(cmd=["tsh", "login", "--auth", "github", "--proxy", proxy_url], capture_output=False)

    # try to get the status again (after login)
    Command.check_output(
        cmd=["tsh", "status"],
        additional_error_msg="Can't get the current status of your teleport profile."
    )


def login_app(app_name: str):
    """log in to a teleport app

    ensure that the user is logged in to teleport"""

    Command.check_output(
        cmd=["tsh", "app", "login", app_name],
        additional_error_msg="Can't login to the teleport app."
    )


def login_k8s(cluster: str):
    """log in to a k8s cluster via teleport

    ensure that the user is logged in to teleport"""

    print(f"Try to connect to the k8s-api of {cluster} ...")

    Command.check_output(
        cmd=[
            "tsh",
            "kube",
            "login",
            cluster,
            "--set-context-name",
            "{{.KubeName}}"
        ],
        additional_error_msg="Can't login to the k8s cluster."
    )

    print("Connected")
    print()


def proxy_app(app_name: str, local_port: int):
    """proxy a teleport app to *local_port*

    before this action you must login to the app
    """

    Command.check_output(cmd=["tsh", "proxy", "app", "-p", str(local_port), app_name], capture_output=False)
