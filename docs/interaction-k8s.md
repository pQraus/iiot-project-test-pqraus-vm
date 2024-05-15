# Interaction with Kubernetes
This file explains some workflows on how to interact with Kubernetes on an IIoT-Box and manage the different apps. In general all workflows require a connection to the Kubernetes api of the box.


**General Requirements:**
- all steps require the proper setup of the tools / dev-machine (`iiotctl`, `asdf`, `gh`, ...): [Confluence: tool setup dev pc](https://schulz.atlassian.net/wiki/spaces/SCHU/pages/2480701465)
- the right versions of the tools (for this project):
    ```bash
    cd <project-repo>
    iiotctl project setup-tools
    ```
    This task ensures that `iiotctl` can use the versions of the tools which are currently specified in the project-repository.

**Explained workflows:**
- [Connect to Kubernetes](#connect-to-kubernetes)
- [Connect to ArgoCD](#connect-to-argocd)
- [Update Kubernetes manifests](#update-kubernetes-manifests)

---

## Connect to Kubernetes
![](/../../../../SchulzSystemtechnik/iiot-base-box/blob/main/docs-base/pics/access-methods.drawio.svg)

There are serval ways to access kubernetes (remote or local) as shown in the picture. 

Choose one method:
- **recommended** [remote access via teleport](#remote-access-via-teleport)
- [local access](#local-access)
- [remote access via VPN-Router](#remote-access-via-vpn-router) (fallback method)


To handle Kubernetes contexts:
```bash
kubectl config get-contexts
kubectl config use-context <context-name>
```

### Remote access via teleport
1. change to project repo (`cd <project-repo>`)
2. execute the iiotctl task:
    ```bash
    iiotctl connect k8s
    ```
    This command uses teleport to login to the k8s cluster and sets the global k8s context.
3. run some `kubectl` commands

### Local access
**Requirements:**
- connection to the talos api (look at [interaction with talos](/docs/interaction-talos.md))

**Steps:**
1. load the kubeconfig with `talosctl`:
    ```bash
    talosctl kubeconfig
    ```
2. open `~/.kube/config` in a editor and search the cluster, replace the cluster url with the ip address of the box:
    ```yaml
    apiVersion: v1
    ...
    clusters:
    ...
    - cluster:
        certificate-authority-data: ...
        server: https://demo-machine:6443
    name: demo-machine
    ```
    change it to:
    ```yaml
    apiVersion: v1
    ...
    clusters:
    ...
    - cluster:
        certificate-authority-data: ...
        server: https://123.123.123.1:6443 # the IP of the box
      name: demo-machine
    ```
    This is required because the talos doesn't send the hostname of the machine to the router.
3. check if you have selected the right context (otherwise switch)
    ```bash
    kubectl config get-contexts
    kubectl config use-context admin@MACHINE-NAME
    ```
4. run some `kubectl` commands

### Remote access via VPN-Router
1. connect to the VPN-Router
2. follow tht steps from [local access to Kubernetes](#local-access)
---

## Connect to ArgoCD
1. change to project repo (`cd <project-repo>`)
2. execute the iiotctl task:
    ```bash
    iiotctl connect argo
    ```
This command by default uses teleport to login to the k8s cluster and port forward argo. The global k8s context will be modified! You can however use the argument --use-current-context if you created a local cert (see [Local access via auth-proxy](/docs/interaction-talos.md#local-access-via-auth-proxy)) to port forward argo via auth-proxy => k8s API, without using teleport.

---

## Update Kubernetes manifests
**Requirements:**
- [ArgoCD access](#connect-to-argocd)

**Workflows:**
- In general you can modify the manifest and commit + push the changes to GitHub. ArgoCD observes the manifests (by default) from the main branch and applies / synchronizes the resources automatically.
- For development purposes, it may be useful to disable the auto-sync option (you don't need a commit for every typo ;) ). If everything is ok, you should enable the auto sync option again.
    1. open the specific application in the argo UI:
        ![](/../../../../SchulzSystemtechnik/iiot-base-box/blob/media/docs-base/pics/argo-select-app.png)

    2. open the *app details* and disable the auto synchronization:
        ![](/../../../../SchulzSystemtechnik/iiot-base-box/blob/media/docs-base/pics/argo-disable-auto-sync.png)

    3. development and manual app deployment
    4. activate auto sync (*app details* menu)
        ![](/../../../../SchulzSystemtechnik/iiot-base-box/blob/media/docs-base/pics/argo-enable-auto-sync.png)

- Argo can also observes an app from another branch (this should only be activated during development):
    1. open the specific application in the argo UI:
        ![](/../../../../SchulzSystemtechnik/iiot-base-box/blob/media/docs-base/pics/argo-select-app.png)

    2. open the *app details* and and *edit* the application:
        ![](/../../../../SchulzSystemtechnik/iiot-base-box/blob/media/docs-base/pics/argo-edit-app.png)

    3. change to another branch and *save* the app:
        ![](/../../../../SchulzSystemtechnik/iiot-base-box/blob/media/docs-base/pics/argo-change-target-revision.png)

    4. development (pushing some stuff into the new branch)
    5. switch to the main branch (*app details* menu)
        ![](/../../../../SchulzSystemtechnik/iiot-base-box/blob/media/docs-base/pics/argo-change-target-revision.png)

---

## Upgrade Kubernetes
A kubernetes upgrade means that the container of the k8s-system (kube-api, kuber-proxy ...) are upgraded (download + redeploy). To check if an update is required run `iiotctl machine status`.
**Requirements:**
- [Kubernetes access](#connect-to-kubernetes)
- [Talos access](/docs/interaction-talos.md)

A connection to talos and k8s is required to upgrade k8s. During the upgrade, the user applications will be temporarily unavailable.

**Steps:**
1. change to project repo (`cd <project-repo>`)
2. upgrade k8s:
    ```
    iiotctl machine upgrade-k8s
    ```
    (You can use the current contexts with the `--use-current-contexts` flags)