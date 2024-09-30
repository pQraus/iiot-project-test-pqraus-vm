# Cluster Administration
This app applies stuff for administration, e.g.:
- argo applicationsets
- argo projects
- repo secrets

## Argo Settings
- There are two applicationsets. One for the `system-apps` and the other for the `user-apps`
- Two argo projects (`system` and `user`) to filter the apps in argo

## Own Repo Secret(s)
You can set up an own secret to access the project repository on another Git-server . This secret can be found in the cluster-administation app: `machine-patches/initial-secrets/`.
For the initial setup, you should call `iiotctl project configure-github-repo` to render the secrets into the initial machine config. If you configure the secret later, it must applied manually with `kubectl`.
