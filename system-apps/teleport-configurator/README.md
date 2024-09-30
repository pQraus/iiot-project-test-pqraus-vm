# Teleport Configurator

The k8s job configures the `teleport-agent` system extension. The initial join token will be deployed via bootstrap extension.

More information: https://github.com/SchulzSystemtechnik/iiot-app-teleport-configurator

## How an update is triggered
The configurator cronjob will process the teleport update. The pod of the cronjob uses a tag which will point to the newest version. On every run the job checks if the image is the newest one and pull it if not. When there is no new image available, the pod detects no changes and finish without doing anything. A post-sync-job is also be executed when the complete app is updated.
