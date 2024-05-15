# Setup an IIoT-Box
The `iiotctl` tool is used to create the (unique) machine configuration files and to build and upload the config to the machine. It's like a `make` script / task for python. Before these steps, it's necessary to collect some information about your new IIoT-Box.

This manual will show you how to create a new project or how to setup an IIoT-Box from an existing repository.

**General Requirements:**
- all steps require the proper setup of the tools / dev-machine (`iiotctl`, `asdf`, `gh`, ...): [Confluence: system requirements development environment](https://schulz.atlassian.net/wiki/spaces/SCHU/pages/2480701465)
- you are logged in with `gh` to a github account which was added to the Schulz Organization (you must log in via web-browser, not PAT)
- you are in the github team ...
- a teleport account (with access to: https://prod.teleport.schulzdevcloud.com)


## Setup workflows:

For all steps the `box-setup-infos` file is required!

**New project:**

1. [Prepare the machine](#1-prepare-a-bare-metal-box--virtual-machine)
2. [Create the repo with copier](#2-create-the-repo-with-copier)
3. [Build machine config with iiotctl](#3-build-machine-configuration-with-iiotctl-tasks)

**Recreating from an existing project:**
1. [Prepare the machine](#1-prepare-a-bare-metal-box--virtual-machine)
2. [Create machine config from an existing repository](#2b-create-machine-config-from-an-existing-repository)
3. [Build machine config with iiotctl](#3-build-machine-configuration-with-iiotctl-tasks)


## 1. Prepare a bare metal box / virtual machine
**Requirements:**
- the new machine is connected to the network
- the new machine is connected to a monitor and a keyboard
- boot talos on the new machine: https://github.com/SchulzSystemtechnik/iiot-base-box/blob/main/docs-base/booting-talos.md

1. startup the machine
    - boot (via UEFI/BIOS) the talos iso (from the stick on bare metal), this will take some minutes

    At this point talos is running in the RAM (maintenance mode) and it's possible to apply the machine config.
2. find out the ip-address of the box
    - look at the connected monitor / output of the vm, you should see the ip address at the top right corner of the screen, like shown in the following picture:
        ![talos-summary-screen](/../media/docs-base/pics/talos-summary-screen.png)

    - alternatively you should also see a log entry which looks like the entries in the following picture:
        ![talos-boot-screen](/../media/docs-base/pics/talos-boot-screen.png)

        (the IP address after the `--nodes` flag is the IP of the box)
    - (you can also look at your router config / web-ui to get the ip address)
    - note the ip address for later use
3. The last step before creating the machine configuration, is to write down the name / path of the disk and the name of the network interfaces. For this purpose `talosctl` (on your machine) can be used:
    ```console
    talosctl apply-config --insecure --mode interactive --nodes <box-ip-adress>
    ```
    - the diskname is printed on the first page:
        ![talosctl-diskname](/../media/docs-base/pics/talosctl-diskname.png)
    - note the disk name / path
    - to get the right names of the interfaces look at the `Network-Config` section:
        ![talosctl-network-interfaces](/../media/docs-base/pics/talosctl-network-interfaces.png)
    - note the network interface (en...) (only the ones you wish to configure)
    - when you have noticed all the things, exit the command with *STRG + C*

## 2. Create the repo with `iiotctl`
For the creation of the machine config `iiotctl` will be used. The `box-setup-infos` file is used to answer the copier questions.

1. use iiotctl to create a new project (repo):
    ```bash
    iiotctl base init
    ```
---
2. answer the dialog questions (for most answers you can use the filled `box-setup-infos` file):
    - choose a preset type for the machine (IIoT, GPU)
    - disable the advanced mode (if no special requirements)
    - choose a box-name (best-practice: repo name on github without the 'iiot-project' prefix)
    - enter owner and name of the remote git repository in the format [OWNER]/[REPO_NAME]
    - choose additional system apps
        - remote monitoring requires a grafana token (can be created later via `iiotctl`)
---
3. follow the additional printed instructions (e.g. modify certain machine configuration files)
    - in these files the noted infos (disk-name, network-interface name) are used:
    ![copier-copy-machine-patches](/../media/docs-base/pics/copier-copy-machine-patches.png)
    - e.g. change the disk name in `machine/config/disk`:
        ```python
        # disk configuration

        # this file is individually for the project and will not be updated by copier
        # the disk name will be patched at 'machine.install.disk'


        def disk_name:
        # must return a string
        "<THE-PATH-OF-YOUR-DISK>"; # <---
        ```

## 3. Build machine configuration with `iiotctl tasks`
The iiotctl tasks are wrapper functions using different cli-tools to make it easy to manage and build the configuration for a box. The tasks are like `make` scripts for python.

**Requirements**
- For the next steps ensure that you are in the project repo
    ```bash
    cd <path-new-project-repo>
    ``````

**Steps**
1. Install / update all the necessary tools with specific versions required by the project on your development machine
2. Generate all-encompassing deployment manifest for each system-app in its respective /argo directory by typing the following command
3. Setup the encryption key for sealed-secrets
4. Setup access tokens for image registries (only for production) & acquire teleport join token (valid for 3 hours) and add it into the box setup secrets
5. Setup token for remote-monitoring (if installed)
6. Set up local git repository, make initial commit (-i), push to newly created github repo, add deployment key

- To execute step 1-6 run:
```bash
iiotctl project setup
```
7. Create the machine config and apply it directly to the machine:
    ```bash
    iiotctl machine bootstrap <ip-of-the-box>
    ```
    > use the --dry-run flag for testing

    The box will restart some times. After this the box should be connected to teleport and argo should manage the system apps. It can take about 15 min before everything works.

    If not, use the created config file (`<path-new-project-repo>/.tasks/talosconfig`). Look at [interaction with talos](/docs/interaction-talos.md) to see how to connect locally with talos.

8. wait until the new box is ready and connected to teleport
  
    **VM ESX-server:** When the machine is ready you must upgrade the machine because the ova-image is already a complete talos installation and the extensions aren't installed automatically:
    ```
    talosconfig merge .tasks/talosconfig
    iiotctl upgrade-talos
    ```
9. push the updated `talosconfig-teleport` and the created `config-sealed.asc`, `config.hash` files to github:
    ```bash
    git add . && \
    git commit -m "feat: update config files" && \
    git push origin main
    ```
10. interacting with Talos or Kubernetes via teleport:
    - [interaction with talos](/docs/interaction-talos.md)
    - [interaction with k8s](/docs/interaction-k8s.md)
11. save the root credentials for the box, the bootstrap task should have created the `<project-dir>/.tasks/talosconfig` file, this file should be stored in a safe place
12. cleanup your local repo from uncommitted secret files
    - delete the uncommitted files, they aren't needed anymore
13. look at argo and sync the argocd-application again
    ```
    iiotctl connect argo
    ```
    Currently required because the ingress resource can't be applied when traefik isn't running (`IngressRoute` is defined by a traefik CRD).
14. Now you can add a user-app in the `user-apps` dir ([add an user app](/user-apps/README.md))
15. For a production machine you should look at the checklist: `checklist` file from: https://github.com/SchulzSystemtechnik/iiot-base-box/blob/main/docs-base/

**Finished !**


## 2B. Create machine config from an existing repository
The next steps are pretty much identical to those from the [create the repo with iiotctl](#2-create-the-repo-with-iiotctl) section. Therefore, only the differences will be described now.

1. clone the existing project repository to your machine
2. to update the machine config with the new credentials / settings run a `iiotctl base update` (instead of a creation):
    ```bash
    cd <project-repo> && \
    iiotctl base update --skip-answered
    ```
3. answer the dialog questions:
    - most answers should already be correct
4. follow the additional instructions (see step 3 in [create the repo with iiotctl](#2-create-the-repo-with-iiotctl)) to verify that the disk path and network settings match, too
5. & 6. Install / update all the necessary tools with specific versions required by the project on your development machine & Generate all-encompassing deployment manifest for each system-app in its respective /argo directory by typing the following command:
    ```bash
    iiotctl project upgrade
    ```
7. Setup the encryption key for sealed-secrets (if not yet existent):
    ```bash
    iiotctl project seal-secret --init
    ```
8. Setup not yet configured access tokens for image registries via the **box token provider**:
    - e.g. if schulz-registry access not yet configured:
    ```bash
    iiotctl project create-token --schulz-registry
    ```
    - e.g. if dockerhub access not yet configured:
    ```bash
    iiotctl project create-token --docker
    ```
    - add `--grafana` if you enabled remote monitoring during `iiotctl base update`
9. now follow steps 8-13 of [build machine configuration with iiotctl tasks](#3-build-machine-configuration-with-iiotctl-tasks))


## Nice to know
- it's possible to configure the initial iso with some kernel arguments to get a "initial image" with a static ip https://www.talos.dev/v1.5/reference/kernel/

### GPU Setup
- after the first config has been applied it's ok that there is an `error loading module gpu`

### Bootstrap the machine manually
1. Install / update all the necessary tools with specific versions required by the project on your machine:
    ```python
    iiotctl project setup-tools
    ```
2. Generate all-encompassing deployment manifest for each system-app in its respective /argo directory by typing the following command:
    ```python
    iiotctl project render-argo-manifests
    ```
3. Setup the encryption key for sealed-secrets:
    ```python
    iiotctl project seal-secret --bootstrap
    ```
4. Setup access tokens for image registries & remote monitoring:
    ```python
    iiotctl project create-token --schulz-registry --docker --teleport --grafana --dev
    ```
5. Set up local git repository, make initial commit, push to newly created github repo, add deployment key:
    ```python
    iiotctl project configure-github-repo --initialize
    ```

6. Now create the initial machine config with local patch files (all patches are templated at this time)
    ```bash
    cd <project-repo>/machine && \
    iiotctl machine patch-config --gen --patch-file-pattern ... > new_mc.json
    ```
    - use patch-file-patterns to reference the patch files to be used (e.g. ... -p "foo*" -p "*bar" ...)
7. Apply the machine config
    ```bash
    talosctl apply-config --insecure --nodes <box-ip-address> -f <new-mc.json>
    ```
    The box will restart some times, after this the box should be connected to teleport and argo should manage the system apps.

    If not, use the created `machine/talosconfig` to connect to the device [connect to talos](/docs/connect-talos.md).
8. Connect with Talos or Kubernetes (see other docs)
9. Rewrite the `machine/talosconfig-teleport`:
    - ```bash
      cd <project-repo>/machine
      ```
    - open the generated `talosconfig` file and copy the value of the `ca` key
    - paste the value into `talosconfig-teleport` (`ca: ` field) 
10. Commit and push the `talosconfig-teleport` and the sealed secrets into the repository

