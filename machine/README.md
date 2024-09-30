# Machine Configuration
A json file is used for the configuration of a machine. This file is created with the `jq` tool (https://stedolan.github.io/jq/). The jq patches in the repository describe the relevant machine config.


The jq patches only guarantee that the config from the repo is applied. Settings which will you edit manually and aren't overwritten by the patches can't detect! 

## Patch Workflow

Use iiotctl tasks for patching:

```bash
iiotctl machine status
```

```bash
iiotctl machine sync
```

The patches should work with this workflow:
1. load the current machine config (or create a blank one for a new box)
2. patch the loaded config with the jq-patches (this will include the patches from the system-apps (`system-apps/app../machine-patches/`, too))
3. apply the patched machine config


## Patch File Naming

Only `.jq` files with a leading underscore will be used to build the machineconfig. Files without a leading Underscore are used to be import in other patches. Example:
* `machine/config/network/_network.jq` ==> will be used for build machine config
* `machine/config/network/interfaces.jq` ==> is imported from _network.jq


## Config Encryption
The `config-sealed` dir contains the (complete) sealed machine config, sha256 hash of the last encrypted config and the public key to encrypt the config. With the hash it's possible to verify that the live config is equal to the encrypted one. 

The private key is needed to encrypt the mc in repo: ask Philip Krause.


## Machine Files
Everything about `machine.files`

To update or insert a file into the config use our `upsert` function (the `upsert` module is located in this dir). It's necessary because every file is an **element** in the file list. We use the `path` key of a file object as the primary key to determinate if this file is already includes in the config.

### Permissions
Permissions of `.machine.files` must provide a permission setting. 
In `json` it's the octal number in decimal.

Read / Write file; only user (`0o600` --> `384`)
