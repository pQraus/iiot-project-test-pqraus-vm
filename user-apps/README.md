# User Apps
For each user app create a subdirectory. Manifests in your user app's `/argo` directory will be deployed automatically by *argocd*. 

## Global Config App
To share configmaps / secrets in different argo applications, it's recommended to create a global config app:
```
user-apps
|-- global-config
    |-- argo
        |-- configmap-1.yaml
        |-- sealed-secret-1.yaml
```

## Example
```
user-apps
|-- my-user-app-1
    |-- argo
        |-- manifest.yaml
```
