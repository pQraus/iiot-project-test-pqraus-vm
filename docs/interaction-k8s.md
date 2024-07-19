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
- **recommended** [Remote access via teleport](#remote-access-via-teleport)
- [Remote access via VPN-Router](#remote-access-via-vpn-router) (fallback method)
- [Local access via auth-proxy](#local-access-via-auth-proxy)
- [Local access via talosctl](#local-access-via-talosctl) (fallback method)


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

### Remote access via VPN-Router
1. connect to the VPN-Router
2. follow the steps from [local access via auth-proxy](#local-access-via-auth-proxy)
    - fallback: [Local access via talosctl](#local-access-via-talosctl)

### Local access via auth-proxy
For this step you will create a short-lived teleport certificate via the teleport server. This certificate is used to authenticate against k8s (via the auth-proxy). **For the creation of this certificate you need (internet) access to the teleport server.** The created certificate is stored in a k8s-context on your local pc. Therefore, it is possible to access the box in a local network while your pc and / or the IIoT-box isn't connected to the public internet / teleport.

1. find out the IP address of the box (via router, documentation ...)
2. create the certificates / kubeconfig via teleport-server **(this step requires an internet connection)**; it adds a new kubeconfig entry into the `~/.kube/config` file
    ```bash
    iiotctl connect k8s --machine-ip <BOX-IP> --ttl 5h
    ```
    - replace `<BOX-IP>` with the real IP address of the box

    It's also possible that you perform these step before you can research which IP the box has, e.g. when there is no internet connection on the local network. In this case you can fake the IP address when you execute the iiotctl task. When you know the real address you can update the created config (`~/.kube/config`).
3. now you can run your `kubectl` commands and interact with the kubernetes API of the IIoT-box
4. If you, later on, after you connected to other boxes, want to reconnect to the first box via the local cert you to do the following:
- check if the cert is still valid (you can configure the lifetime via `--ttl` on creation)
- set the current kubernetes context to the one that uses the local cert with:
    ```bash
    kubectl config use-context <CONTEXT>
    ```
    - replace `<CONTEXT>` with the real kubernetes context name

### Local access via talosctl
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