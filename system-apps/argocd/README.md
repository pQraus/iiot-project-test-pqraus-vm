# ArgoCD
The self managed argo app deploys the manifests from your repository

## Usage
### Connect to ArgoCD UI
1. login to the k8s cluster
2. forward the port of argoCD server:
    ```console
    kubectl port-forward --address "0.0.0.0" -n argocd services/argocd-server <custom-port>:443
    ```
3. open `localhost:<custom-port>` in a browser

### Disable Auto-Sync
1. connect to argo UI
2. click the application you want to modify
3. click on *APP Details*
4. disable auto sync in *SYNC POLICY* field

## Delete an Applicationset
To delete an applicationset without the managed applications run:
```console
kubectl delete applicationsets.argoproj.io <Appset-Name> --cascade false
```

## Purge Resources
ArgoCD doesn't delete resources automatically (for safety reasons). But it's possible to delete resources on a manual sync. Just activate the *Prune* checkbox in sync window (this affects only the current sync).

## Addtional Topics

### TLS-Verification of another Git-Server
You can add the CA Certificate of an additional git server in the `./argo-template/patches/tls-certs-cam.yaml` file.
This file won't be updated by copier.
When you have added a certificate to this file, your application can point to a repo from another server via https.
The credential for this repository should be placed into the cluster-administration app.

### GitHub Access via SSH on Port 443
The known hosts for SSH access via port 443 are added. Often the SSH standard port 22 is blocked by the firewall. Thus, you should use SSH access via port 443. 

This is the argo specific GitHub url to access the repo with SSH on port 443:
```
ssh://git@ssh.github.com:443/SchulzSystemtechnik/project.git
```

### Auto Login
Argo is configured to enable auto login as an anonymous user with admin rights.

### Self-Managed ArgoCD
ArgoCD is observed by ArgoCD: https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/#manage-argo-cd-using-argo-cd

### ArgoCD Projects
You can define Projects in argo. We use this currently only to differ between user and system apps. But they can be also used to restrict the application access to namespaces or repositories (not needed in our use case).

