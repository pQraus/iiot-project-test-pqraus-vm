# Sealed Secrets
Save your (sealed) secrets in the repository

## Create a Sealed Secret
1. Create a normal k8s-secret file (e.g. with copier):
    ```yaml
    apiVersion: v1
    kind: Secret
    metadata:
      name: mysecret
      namespace: default
    type: Opaque
    # you can use the data or the stringData field
    data: # all values are base64 encoded
      password: Z2VoZWltCg== # echo "geheim" | base64
    stringData: # all values are in plaintext
      password: geheim
    ```
2. You need `kubectl` access to the cluster where the secret should be applied because only this cluster has the certs to encrypt and decrypt the sealed secret
3. Seal the secret with `kubeseal` (`kubeseal` communicates with the seal-controller of the connected cluster for sealing, the controller in located in the `sealed-secret` namespace):
    ```
    kubeseal --controller-namespace sealed-secrets -f k8s-secret.yaml -o yaml > sealed-secret.yaml 
    ```
4. Add the `sealed-secret.yaml` file into the repository

**Important Note**

The sealed secret is only valid for the namespace which is specified in the k8s-secret. If there is no namespace specified the secret is valid for the `default` namespace.


## Cert Rotation
- The operator creates every 30 days a new certificate. All new secrets will be encrypted with the new one.
- Secrets which are created with an 'old' cert can still be decrypted.
- This also applies to the certificate which is created by the `seal-secret` task. It has a validity of a year.
  - When this cert is expired you need a new one to create new sealed secrets
  - Old secrets are still be decrypted


## Some Stuff
- create your own cert for the sealed secret operator:
  ```
  openssl req -x509 -nodes -newkey rsa:4096 -keyout private_key -out cert -subj "/CN=sealed-secret/O=sealed-secret"
  ```