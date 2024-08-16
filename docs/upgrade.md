# Upgrade an IIoT-Box
This guide shows how to upgrade a project to the current base.

**General Requirements:**
- ensure you can pull images from dockerhub and our registry
- you have access to the box via teleport

**What are the the things which can be affected by a system-upgrade?**
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

**Overview:**

![](/../../../../SchulzSystemtechnik/iiot-base-box/blob/main/docs-base/pics/upgrade.drawio.svg)


## Upgrade Workflows:

### Upgrade within a major version:
1. [Upgrade the project repo](#1-upgrade-the-project-repo-with-iiotctl-base-update)

### Upgrade the major version:
1. [Upgrade the project repo](#1-upgrade-the-project-repo-with-iiotctl-base-update)
2. [Apply to Machine`](#2-apply-the-upgrade-to-the-box-with-iiotctl-machine-sync)

**Special:**
* [Upgrade v2 to v3](#upgrade-v2-to-v3)
* [Upgrade v1 to v2](#upgrade-v1-to-v2-1)


## 1. Upgrade the project repo with `iiotctl base update`
Updating the files (machine config patches, k8s-manifests) within the project repository. This can be performed without affecting the running system.

**Requirements**
- For the next steps ensure that you are in the project repo
    ```bash
    cd <path-new-project-repo>
    ```
- check the machine status, only update when everything is ok :white_check_mark:
    ```bash
    iiotctl machine status
    ```
- no git changes in your local repository (commit or stash them)

**Steps**
1. Upgrade project with iiotctl:
    ```bash
    iiotctl base update --skip-answered
    ```
    * Only new questions will be asked
    * Follow the additional instructions at the end of the dialog
2. Ensure that there are aren't any git merge conflicts.
    ```bash
    git diff --name-status --diff-filter=U
    ```
    * when the command prints nothing: -> continue with next step
    * when the command prints some files: -> try to resolve the conflicts
3. Upgrade local project repo directory files:
    ```bash
    iiotctl project upgrade
    ```
    * The kube manifests will be rendered
    * This will create a new branch and the changes will be committed to it
    **Don't merge the branch directly into main.**
4. On every upgrade you should run the status task
    ```bash
    iiotctl connect talos
    ```
    ```bash
    iiotctl machine status
    ```
    * when the machine config hash is :x: :
      * look at the next step
    * when anything else is :x: :
      * look at 2. [Apply new config`](#2-apply-the-upgrade-to-the-box-with-iiotctl-machine-sync)
5. Seal the machine config (the reason for the (re-) sealing is that the tasks have changed)
    ```bash
    iiotctl connect talos
    ```
    ```bash
    iiotctl machine seal-config
    ```
    ```bash
    git add machine/ && \
    git commit -m "feat: seal the machine config"
    ```
6. Push the update branch
    ```bash
    git push origin update/base-$(yq '._commit' .copier-answers.yml)
    ```
7. When everything is fine (machine status) merge the update branch into main on Github
* **The new system apps will be upgraded immediately by ArgoCD!**
* Delete the branch local and remote after merge.
8. Connect to argo and check the apps
    ```bash
    iioctl connect argo
    ```

## 2. Apply the upgrade to the box with `iiotctl machine sync`
The following steps will depend on what the previous step has changed.

- Apply machine configs with `iiotctl`. **Maybe the Talos reboots (a short downtime is to be expected).**
- Apply changes in k8s-manifests with `git` and `ArgoCD`.

**Requirements**
- [talos connection](/docs/interaction-talos.md) is required
    ```bash
    iiotctl connect talos
    ``````

**Steps**

1. Differences in the machine configuration: synchronize the configuration (in the proper apply mode)
    ```bash
    iiotctl machine status
    ```
    ```
    iiotctl machine sync
    ```
    - talos installer image upgrade: `--apply-mode staged`
        - use the `--force` flag to skip the version conflict
    - no talos upgrade, some machine config changes which require a reboot: `--apply-mode staged` or `--apply-mode reboot`
        - apply change **on next reboot (--mode=staged)**: change is staged to be applied after a reboot, but node is not rebooted
        - apply change **with a reboot (--mode=reboot)**: update configuration, reboot Talos node to apply configuration change
    - in all other cases use the default mode
    - **when a new talos installer image is used, a talos upgrade is always required**
2. Talos / k8s version upgrade
    - **Generally you should run a talos upgrade before kubernetes upgrade!!!**
    - When upgrading Kubernetes, make sure that you do not skip any minor versions, as this can lead to errors.
        - :x: From 1.26.x to 1.28.x causes errors
        - :heavy_check_mark: From 1.26.x to 1.27.x to 1.28.x is the correct way
        - Set the kubernetes version in `tasks/tasks_config.json`
    ```bash
    iiotctl machine upgrade-talos
    iiotctl machine upgrade-k8s
    ```
3. Run the status task again
    ```bash
    iiotctl machine status
    ```
    * when everything is :white_check_mark: :
      * Merge the branch `feature/update-base` on Github. **The new system apps will be upgraded immediately by ArgoCD!**
      * Delete the branch local and remote after merge.
    * when anything is :x: :
      * -> Call the Experts :phone:.

    **Experts only:**
   * you can also "try" the upgrade by setting the branch of an system app in argo to the upgrade branch ([interacting with k8s](/docs/interaction-k8s.md)

4. When everything has been synced and upgraded by ArgoCD, you should check the applications to see if everything is working properly. (Maybe delete old resources in ArgoCD

---

## Upgrade v2 to v3
Supported upgrade path: **v2.x.x --> v3.0.0**

**Requirements**
- For the next steps ensure that you are in the project repo
    ```bash
    cd <path-new-project-repo>
    ```
- check the machine status, only update when everything is ok :white_check_mark:
    ```bash
    iiotctl machine status
    ```
- no git changes in your local repository (commit or stash them)

**Steps:**
1. Update project:
    ```bash
    iiotctl base update --skip-answered --vcs-ref v3.0.0
    ```
2. Upgrade project files / tools
    ```bash
    iiotctl project upgrade
    ```
3. Apply the machine config in staged mode and ignore the version change
    ```bash
    iiotctl machine sync --force --apply-mode staged
    ```
4. Execute the **Talos upgrade** (Causes Downtime :rotating_light:)
    ```bash
    iiotctl machine upgrade-talos
    ```
    ```bash
    talosctl dashboard
    ```
    - after upgrading the dashboard should show that the `STAGE` is `Running` and `READY` is `True` (it takes ~10 min)
    - when machine doesn't change in ready state -> Call the Experts :phone:  
5. Execute the **Kubernetes upgrade** (Causes Downtime :rotating_light:)
    ```bash
    iiotctl machine upgrade-k8s
    ```
    ```bash
    talosctl dashboard
    ```
    - after upgrading the dashboard should show that the `STAGE` is `Running` and `READY` is `True` (it takes ~10 min)
    - when machine doesn't change in ready state -> Call the Experts :phone: 
7. Seal the machine config (the k8s upgrade makes some changes) 
    ```bash
    iiotctl machine seal-config
    ```
8. Sync the machine config (the k8s upgrade changes some of our values)
    ```bash
    iiotctl machine sync
    ```
9. check machine status
    ```bash
    iiotctl machine status
    ```
    * when everything is :white_check_mark: :
      * continue
    * when anything is :x: :
      * -> Call the Experts :phone:.
10. commit changes (only sealed machine config should be changed)
    ```bash
    git add machine/ && \
    git commit -m "feat: seal the machine config"
    ```
11. Push the update branch
    ```bash
    git push origin update/base-$(yq '._commit' .copier-answers.yml)
    ```
12. merge the update branch into main
13. refresh all argo applications (in the argocd ui)
    ```
    iiotctl connect argo
    ```
14. upgrade finished

## Upgrade v1 to v2
Supported upgrade path: **v1.x.x -->  v1.2.3 --> v2.3.0**

When you upgrade a project to v2.x.x follow these steps:

Requirements:

* :warning: Check the Network Whitelisting in the customers firewall. https://schulz.atlassian.net/wiki/spaces/SCHU/pages/2459861010/Systemanforderungen+IIoT-Box#Netzwerkfreigabeliste-ab-Version-2.0

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
    When this error occurs when making the update `ModuleNotFoundError: No module named 'yamlinclude'`, than an additional package must be included to the pipx copier-dist env. Execute this command: `pipx inject copier-dist 'pyyaml-include<2'`
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
    pipx install --force git+https://github.com/SchulzSystemtechnik/iiot-misc-copier-dist.git@9.2.0
    ```
6. update the project-repo to v2.x.x
    ```bash
    copier update --trust
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

    change the k8s version in `iiotctl-tasks/task_config.json` and start the first upgrade: `iiotctl machine upgrade-k8s`, after this run the second k8s upgrade
    ```bash
    iiotctl machine upgrade-k8s
    ```
17. maybe there are are some little changes in the machine config, apply them (in no-reboot mode):
    ```bash
    iiotctl machine sync
    ```
18. (commit changes), push branch to github and merge the update branch into main
19. connect to the argo ui (`iiotctl connect argo`)
    - refresh all apps
    - remove the old teleport app
    - sync the apps when they are degraded (maybe there are also resources that need to be deleted)
