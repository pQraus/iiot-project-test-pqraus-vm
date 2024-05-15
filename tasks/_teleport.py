import json
import subprocess as sp
import sys
import tempfile
from pathlib import Path

from ._config import BOX_NAME, ENCODING, TELEPORT_PROXY_URL


def create_local_cert(ttl):
    """create a teleport cert which can be used for local access via tctl

    ensure that the user is logged in to teleport"""

    status_cmd = sp.run(["tsh", "status", "-f", "json"], capture_output=True)
    if status_cmd.returncode:  # exit when status cmd fails
        print("Can't get the current status of your teleport profile:", file=sys.stderr)
        print(status_cmd.stderr.decode(ENCODING), file=sys.stderr)
        exit(1)

    tsh_status = json.loads(status_cmd.stdout.decode(ENCODING))
    username = tsh_status["active"]["username"]

    # tmpdir is required because tctl can only write the certs to a file
    with tempfile.TemporaryDirectory("telport-crt") as td:
        tmp_dir = Path(td)
        cert_files = tmp_dir / "telport-cert"
        sp.check_output(
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
            ],
        )
        # load the cert and key as vars
        cert_file = cert_files.with_suffix(".crt")
        with open(cert_file, "rb") as f_cert:
            cert = f_cert.read()
        key_file = cert_files.with_suffix(".key")
        with open(key_file, "rb") as f_key:
            key = f_key.read()
    return cert, key


def login():
    """log in an user to teleport"""

    init_status_cmd = sp.run(["tsh", "status"], capture_output=True)
    if not init_status_cmd.returncode:  # the user is already logged in
        return
    else:  # can't get the current user status -> try if a login can fix that problem
        print(f"Login to teleport cluster '{TELEPORT_PROXY_URL}':\n")

        login_cmd = sp.run(
            [
                "tsh",
                "login",
                "--auth",
                "github",
                "--proxy",
                TELEPORT_PROXY_URL,
            ]
        )
        if login_cmd.returncode:
            exit(1)

    # try to get the status again (after login)
    login_status_cmd = sp.run(["tsh", "status"], capture_output=True)
    if login_status_cmd.returncode:
        print("Can't get the current status of your teleport profile:", file=sys.stderr)
        err_msg = login_status_cmd.stderr.decode(ENCODING)
        print(err_msg, file=sys.stderr)
        exit(1)


def login_app(app_name):
    """log in to a teleport app

    ensure that the user is logged in to teleport"""

    login_cmd = sp.run(["tsh", "app", "login", app_name], capture_output=True)
    if login_cmd.returncode:
        print("Can't login to the teleport app:", file=sys.stderr)
        print(login_cmd.stderr.decode(ENCODING))
        exit(1)


def login_k8s():
    """log in to a k8s cluster via teleport

    ensure that the user is logged in to teleport"""

    print(f"Try to connect to the k8s-api of {BOX_NAME} ...")

    login = sp.run(
        [
            "tsh",
            "kube",
            "login",
            BOX_NAME,
            "--set-context-name",
            "{{.KubeName}}"
        ],
        capture_output=True
    )

    if login.returncode:
        print("Can't login to the k8s cluster:", file=sys.stderr)
        print(login.stderr.decode(ENCODING))
        exit(1)

    print("Connected")


def proxy_app(app_name, local_port: int):
    """proxy a teleport app to *local_port*

    before this action you must login to the app
    """

    proxy_cmd = sp.run(
        ["tsh", "proxy", "app", "-p", str(local_port), app_name],
        capture_output=True,
    )
    if proxy_cmd.returncode:
        print(proxy_cmd.stderr.decode(ENCODING))
        exit(1)
