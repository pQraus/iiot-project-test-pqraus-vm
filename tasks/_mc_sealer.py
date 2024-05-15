import subprocess as sp
from datetime import datetime
from hashlib import sha256

from ._config import MACHINE_DIR


CONFIG_SEALED_DIR = MACHINE_DIR / "config-sealed"
CONFIG_HASH_FILE = CONFIG_SEALED_DIR / "config.hash"
CONFIG_SEALED_FILE = CONFIG_SEALED_DIR / "config-sealed.asc"
KEY_ID = "CE5C2A48F2FD3B6F748F39D35C573EF25CB0F87E"
PUBLIC_KEY_FILE = CONFIG_SEALED_DIR / "public-key.gpg"


def is_mc_hash_diff(mc: bytes):
    """check if saved hash in repo is equal to the mc hash"""
    if CONFIG_HASH_FILE.is_file():  # check if hash is already present
        with open(CONFIG_HASH_FILE, "r") as f:
            saved_hash = f.read().splitlines()[0]
    else:
        saved_hash = ""
    current_hash = sha256(mc).hexdigest()
    return saved_hash != current_hash

def seal_mc(mc: bytes):
    """seal the mc with the public key in repo and update the hash file"""
    CONFIG_SEALED_FILE.unlink(True)
    cmd = sp.run(
        [
            "gpg",
            "--no-default-keyring", # use temp keyring
            "--primary-keyring",    
            PUBLIC_KEY_FILE,
            "--encrypt",
            "--recipient",
            KEY_ID,
            "-o",
            CONFIG_SEALED_FILE,
            "--trust-model",
            "always", # trust key without signing
            "--armor",
            "--batch" # disable interactive mode
        ], 
        capture_output=True, 
        input=mc
    )
    if cmd.returncode:
        print(cmd.stderr.decode())
        exit(1)
    mc_hash = sha256(mc).hexdigest()
    with open(CONFIG_HASH_FILE, "w") as f:
        f.write(mc_hash)
        f.write("\n")
        f.write(f"Created at: {datetime.now()}")