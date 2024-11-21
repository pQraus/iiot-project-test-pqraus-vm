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

## Activate Space Quota for existing PVCs
- PVCs that were created before the space quota feature was activated can't use this function.
- existing PVCs should be recreated

Steps to recreate a pvc:
1. look for the manifest of the pvc that should be recreated, into the manifest change the name of the pvc
2. apply the updated pvc manifest (`kubectl apply -f <pvc-manifest>`)
3. deploy the following pod to move the data into the new pv (update the pvc volume names before)
  ```yaml
  apiVersion: v1
  kind: Pod
  metadata:
    name: pvc-transfer
    labels:
      name: pvc-transfer
      namespace: <NAMESPACE>
  spec:
    containers:
    - name: pvc-transfer
      image: alpine:latest
      command: ["tail", "-f", "/dev/null"]
      volumeMounts:
        - name: old-pv
          mountPath: /oldpv
        - name: new-pv
          mountPath: /newpv
    volumes:
      - name: old-pv
        persistentVolumeClaim:
          claimName: <OLD-PVC-NAME>
      - name: new-pv
        persistentVolumeClaim:
          claimName: <NEW-PVC-NAME>
  ```
4. "exec" into the pod and move the files
    ```
    kubectl exec -it pvc-transfer -- sh

    mv /oldpv/<MY-DATA> /newpv/<MY-DATA>
    ```
5. restart the app that uses the pvc (update the pvc name!)
6. delete the old pvc and the `pvc-transfer` pod

