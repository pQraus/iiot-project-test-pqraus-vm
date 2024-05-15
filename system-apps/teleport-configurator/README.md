# Teleport Configurator

The k8s job configures the `teleport-agent` system extension. The initial join token will be deployed via bootstrap extension.

More information: https://github.com/SchulzSystemtechnik/iiot-app-teleport-configurator

## How an update is triggered
The configurator job will process the teleport update. This job is declared as a Post-Sync-Job and will only run when argo executes a synchronization on the teleport-configurator app. To start a synchronization on this app, the teleport config(map) must be changed. This is the only reason why the configmap contains a key-value pair of the teleport version.
