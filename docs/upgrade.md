# Upgrade the project base (system-upgrade)
This guide shows how to upgrade a project repo to the current (project) base (system-upgrade).

- [General](#general)
- [Upgrade v2](#upgrade-v2)
- [Upgrade v1 --> v2](#upgrade-v1-to-v2)

## General

![](/../../../../SchulzSystemtechnik/iiot-base-box/blob/main/docs-base/pics/upgrade.drawio.svg)

In general, there are two steps of an upgrade:
1. [upgrade the project repo with copier](#upgrade-the-project-repo-with-copier) to the current version of the base repo (this can be performed without affecting the running system), this means that the machine config patches and / or k8s-manifests of the system apps are upgraded
2. [the new config / manifests are applied / deployed](#apply-the-upgrade-to-the-box) (via iiotctl, ArgoCD)
    - In most cases, a short downtime is to be expected.

Before upgrading:
- ensure you can pull images from dockerhub and our registry
- you can access the box via teleport

### What are the the things which can be affected by a system-upgrade?
- Talos Installer Image upgrade
    - requires a reboot of the system (and a time slot in which user apps can pause)
    - during the upgrade process all talos images and system extensions will be pulled from the internet
- Talos machine config upgrade
    - It depends on which parts of the configuration are changed. In some cases a reboot is necessary, sometimes the new configuration can be applied directly.
- Kubernetes upgrade
    - no reboot is necessary, but the user apps are down for a moment
    - during the upgrade process all k8s images will be pulled from the internet
- System-App (k8s) upgrades
    - in most cases, this is done in the background; sometimes it is necessary that the user apps stop briefly

## Upgrade v2
### Upgrade the project repo with iiotctl
1. change to project repo (`cd <project-repo>`)
2. upgrade  with iiotctl:
    ```bash
    iiotctl base update --skip-answered
    ```
3. look at the dialog and just answer new questions (skip the "old" questions with *ENTER*)
    - follow the additional instructions at the end of the dialog
4. ensure that there aren't any git merge conflicts. Try to resolve the conflicts.
5. upgrade local project repo directory files:
    ```bash
    iiotctl project upgrade
    ```
6. seal the machine config for the first time:
    ```bash
    iiotctl connect talos
    iiotctl machine seal-config
    ```
7. commit the changes in a **new branch**
    ```bash
    git switch -c feature/update-base && \
    git add . && \
    git commit -m "feat: update project base to vXXXX"
    ```
    Don't merge the branch directly into main. Otherwise the new system apps will be upgraded immediately by ArgoCD.

### Apply the upgrade to the box
The following steps will depend on what things the copier upgrade has changed in the project. 

- on every upgrade you should run the status task ([talos connection](/docs/interaction-talos.md) is required)
    ```bash
    iiotctl machine status
    ```
- differences in the machine configuration: synchronize the configuration (in the proper apply mode)
    ```
    iiotctl machine sync
    ```
    - talos installeri mage upgrade: `--apply-mode staged`
        - use the `--force` flag to skip the version conflict
    - no talos upgrade, some machine config changes which require a reboot: `--apply-mode staged` or `--apply-mode reboot`
        - apply change **on next reboot (--mode=staged)**: change is staged to be applied after a reboot, but node is not rebooted
        - apply change **with a reboot (--mode=reboot)**: update configuration, reboot Talos node to apply configuration change
    - in all other cases use the default mode
    - **when a new talos installer image is used, a talos upgrade is always required**
- talos / k8s version upgrade
    - **Generally you should run a talos upgrade before kubernetes upgrade!!!**
    - When upgrading Kubernetes, make sure that you do not skip any minor versions, as this can lead to errors.
        - :x: From 1.26.x to 1.28.x causes errors
        - :heavy_check_mark: From 1.26.x to 1.27.x to 1.28.x is the correct way
        - Set the kubernetes version in `tasks/tasks_config.json`
    ```bash
    iiotctl machine upgrade-talos
    iiotctl machine upgrade-k8s
    ```
- merge the update branch into main

- differences in the system-app manifests (`system-apps` dir):
    - the changes will applied automatically by default when the branch is merged into main (via argo)
    - you can also "try" the upgrade by setting the branch of an system app in argo to the upgrade branch ([interacting with k8s](/docs/interaction-k8s.md))
    - when everything has been upgraded by argo, you should check the applications to see if everything is working properly and delete old resources

---

## Upgrade v1 to v2
Supported upgrade path: **v1.x.x -->  v1.2.3 --> v2.2.0**

When you upgrade a project to v2.x.x follow these steps:

1. create a new update branch
    ```
    git switch -c feature/update-base-v2
    ```
2. upgrade your repo to v1.2.3 (therefore copier v6.2.0 is required):
    - first get the right copier version:
    ```bash
    pipx install --force git+https://github.com/SchulzSystemtechnik/iiot-misc-copier-dist.git@v1
    ```
    - then start the copier update:
    ```bash
    copier --vcs-ref v1.2.3 update
    ```
3. commit the changes, it isn't required to upload the changes to the box
4. The upgrade includes a Talos upgrade to v1.5.4, too. These upgrade can affect the network interface assignments. Therefore it is necessary to add the `deviceSelector` to your configured network interfaces. Make sure that you remove or commend the interface key, both are not vaild.

    info: To get the MAC address you can use `talosctl get links`.

    ```json
    {
        "deviceSelector": {
            "hardwareAddr": "00:14:..." # MAC address
        },
        # "interface": "eth1", # Interface with static IP
        "addresses": ["192.168.50.20/24"],   # static ip with subnetlength
        "routes": [ { ... } ]
        ...
    }
    ```

5. upgrade the `copier-dist` to the current version:
    ```bash
    pipx install --force git+https://github.com/SchulzSystemtechnik/iiot-misc-copier-dist.git@v2
    ```
6. update the project-repo to v2.x.x
    ```bash
    iiotctl base update
    ```
    the most answers should be valid
7. commit the changes (in the update branch)
8. upgrade the project files:
    ```
    iiotctl project upgrade
    ```
9. create a token for the new schulz registry
    ```
    iiotctl project create-token --schulz-registry
    ```

10. (optional, when remote monitoring is enabled or you need sealed secrets) create a public key for secret sealing
    ```
    iiotctl connect k8s
    iiotctl project seal-secret --init
    ```
11. (optional, when remote monitoring is enabled) create a grafana token
    ```
    iiotctl project create-token --grafana
    ```
12. seal the machine config for the first time:
    ```bash
    iiotctl connect talos
    iiotctl machine seal-config
    ```
13. commit the changes (in the update branch)
14. upgrade the machine config (for Talos 1.5), this should be done in staged mode to apply the changes with the talos upgrade together in the next step.

    info: for step 7-10 and the next steps make sure, that `iiotctl connect talos` is running.

    ```bash
    iiotctl machine sync --apply-mode staged
    ```
15. run `iiotctl machine upgrade-talos` and wait until everything (k8s, talos services) is ready
    info: after a reboot `iiotctl connect talos` must be executed again.
    ```bash
    iiotctl machine upgrade-talos
    ```
16. upgrade k8s, this must be done in two steps: 1.26.X -> 1.27.4 -> 1.28.X

    change the k8s version in `iiotctl-taks/task_config.json` and start the first upgrade: `iiotctl machine upgrade-k8s`, after this run the second k8s upgrade
    ```bash
    iiotctl machine upgrade-k8s
    ```
17. maybe there are are some little changes in the machine config, apply them (in no-reboot mode):
    ```bash
    iiotctl machine sync
    ```
18. (commit changes), push branch to github, merge it into main and look at the argo ui.
    - remove the old teleport app
    - sync the apps when they are degraded
