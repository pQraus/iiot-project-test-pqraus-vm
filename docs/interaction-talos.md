# Interaction with Talos
This file explains some workflows on how to interact with talos on an IIoT-Box. In general all workflows require a connection to the talos api of the box.


**General Requirements:**
- all steps require the proper setup of the tools / dev-machine (`iiotctl`, `asdf` ...): [Confluence: tool setup dev pc](https://schulz.atlassian.net/wiki/spaces/FE/pages/2417459201/Tool+Setup+auf+dem+Dev-PC)

**Explained workflows:**
- [Connect to talos](#connect-to-talos)
- [Synchronize / Update the machine configuration](#synchronize--update-the-machine-configuration)


## Connect to talos
![](/../../../../SchulzSystemtechnik/iiot-base-box/blob/main/docs-base/pics/access-methods.drawio.svg)

There are serval ways to access talos (remote or local) as shown in the picture. 

Choose one method:
- **recommended** [Remote access via teleport](#remote-access-via-teleport)
- [Local access via auth-proxy](#local-access-via-auth-proxy)
- [Remote access via VPN-Router](#remote-access-via-vpn-router) (fallback method)
- [Steps to connect with the created talosconfig](#steps-to-connect-with-the-created-talosconfig) (fallback method)

### Remote access via teleport
(This is the recommended method to connect a remote IIoT-Box)

1. change to project dir (`cd <project-repo>`)
2. execute the iiotctl task:
    ```bash
    iiotctl connect talos
    ```
    This command uses the committed `machine/talosconfig-teleport` file. It logs in to the talos app on teleport and forwards the talos api to a local port.
3. run your `talosctl` commands in a new window

When you have finished your work, simply abort the iiotctl connection task.

### Remote access via VPN-Router
1. Connect to the VPN-Router
2. create a local certificate to access the box: [access via auth-proxy](#local-access-via-auth-proxy)

(In case there is an error in the auth-proxy, you can also use the file './tasks/talosconfig' created during bootstrap process.)

### Local access via auth-proxy
For this step you will create a short-lived teleport certificate via the teleport server. This certificate is used to authenticate against talos (via the auth-proxy). **For the creation of this certificate you need (internet) access to the teleport server.** The created certificate is stored in a talos-context on your local pc. Therefore, it is possible to access the box in a local network while your pc and / or the IIoT-box isn't connected to the public internet / teleport.

1. find out the IP address of the box (via router, documentation ...)
2. create the certificates / talosconfig via teleport-server **(this step requires an internet connection)**; it adds a new talosconfig entry into the `~/.talos/config` file
    ```bash
    iiotctl connect talos --machine-ip <BOX-IP> --ttl 5h
    ```
    - replace `<BOX-IP>` with the real IP address of the box

    It's also possible that you perform these step before you can research which IP the box has, e.g. when there is no internet connection on the local network. In this case you can fake the IP address when you execute the iiotctl task. When you know the real address you can update the created config:
    ```bash
    # is the right context selected?
    talosctl config contexts
    # no? switch it to the right one:
    talosctl config context <BOX-NAME>-local
    
    talosctl config node <BOX-IP> && \
    talosctl endpoint <BOX-IP>
    ```
3. now you can run your `talosctl` commands and interact with the talos API of the IIoT-box


### Steps to connect with the created talosconfig
**Requirements:**
- the `talosconfig` which was created by the bootstrap iiotctl task (normally in `project-repo/.tasks/talosconfig`)
```yaml
    context: <BOX-NAME>
    contexts:
        <BOX-NAME>:
            endpoints:
                - <BOX-IP>
            nodes:
                - <BOX-IP>
            ca: ...
            crt: ...
            key: ...
```

**Steps:**
1. replace BOX-IP of the `endpoints` & `nodes` fields with the real IP in the talosconfig
2. merge the context in your talos config
    ```bash
    cd <project-repo>
    talosctl config merge .tasks/talosconfig
    ```
3. You should be connected with the machine:
    ```bash
    talosctl config contexts # should mark the merged config as activated
    # otherwise select the right context:
    talosctl config context <BOX-NAME>
    ```
4. run your `talosctl` commands

## Synchronize / Update the machine configuration
The following instructions will show you how to synchronize the machine config between the project repository and the actual machine. You should check if there are some diffs in the config after every repo update with copier.

**Requirements:**
- [talos connection to the box ](#connect-to-talos)

**Workflows:**
(For the following iiotctl tasks you can always use the `--use-current-context` argument if you want to access the box via local certificate. Then the current selected talos config will be used. Otherwise the talosconfig for teleport will be used.)
- test if the machine config is out of sync:
    ```
    iiotctl machine status
    ```
- synchronize the machine config:
    ```
    iiotctl machine sync # optional with --apply-mode reboot or staged
    ```
    Sometimes a reboot is required to apply the new config. In this case you must add the `--apply-mode` parameter to the task.
    - `no-reboot` (default): apply the changes directly
    - `reboot`: reboot immediately
    - `staged`: apply the changes after the next (manual) reboot

### Sync check machine configs
- both of these two iiotctl tasks will read in all .jq-files of the repo, patch together the machine config json file with them and then compare it with the config file from the box, checking if there are differences
- it is important to note, that some .jq-files end with **'.boot.jq'** - which signals that they won't be considered in the synchronization of the local and the box machine config
- these files will only be used once while bootstrapping the box with the very first machine config - later changes in their app directory will be updated on the box by ArgoCD, not via machine config update + box reboot

### Upgrade talos
When updating to a different talos installer image version is a talos upgrade required.
```
iiotctl machine upgrade-talos
```
**This will reboot the system when the update check has passed.**
A talos upgrade always downloads the talos installer image.
