# OpenEBS
OpenEBS provides k8s storage-classes which can persist data of your applications

For our use-cases we only need the OpenEBS [Local PV Hostpath](https://openebs.io/docs/user-guides/localpv-hostpath) storage-class. This app set the *Local PV Hostpath* class as default storage-class.

The persistent data can be found under `/var/openebs/local` (use `talosctl list -l /var/openebs/local`).

## Usage
1. Create a `pvc.yaml`:
  ```yaml
  kind: PersistentVolumeClaim
  apiVersion: v1
  metadata:
    name: my-pvc
  spec:
    accessModes:
      - ReadWriteOnce
    resources:
      requests:
        storage: 5G 
        # requested size; currently openebs doesn't observe this for the local pv hostpath class
  ```

2. Create a deployment / pod ... which uses the Claim:
  ```yaml
  apiVersion: v1
  kind: Pod
  metadata:
    name: test
  spec:
    volumes:
    - name: local-storage
      persistentVolumeClaim:
        claimName: my-pvc
    containers:
    - name: hello-container
      image: busybox
      volumeMounts:
      - mountPath: /mnt/store # in the container
        name: local-storage
  ```

## Reuse a Persistent-Volume
https://openebs.io/docs/additional-info/kb#reuse-pv-after-recreating-sts

- add the `volumeName` field in the persistent volume claim
  ```yaml
  kind: PersistentVolumeClaim
  apiVersion: v1
  metadata:
    name: my-pvc
  spec:
    volumeName: <name-of-the-pv> # paste the name
    accessModes:
      - ReadWriteOnce
    resources:
      requests:
        storage: 5G 
  
  ```
- modify the uuid of the corresponding pvc in the persistent volume
  ```yaml
  kind: PersistentVolumeClaim
  apiVersion: v1
  metadata:
    ...
  spec:
    accessModes:
    - ReadWriteOnce
    capacity:
      storage: 5Gi
    claimRef:
      apiVersion: v1
      kind: PersistentVolumeClaim
      name: my-pvc
      namespace: default
      resourceVersion: "22777"
      uid: <uuid-of-the-pvc> # add the right uuid
  ```
