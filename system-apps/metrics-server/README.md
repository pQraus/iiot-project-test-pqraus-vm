# Metrics Server (k8s)
metric server to monitor the k8s workloads [(GitHub)](https://github.com/kubernetes-sigs/metrics-server)
Metrics Server enables use of the Horizontal Pod Autoscaler and Vertical Pod Autoscaler. It does this by gathering metrics data from the kubelets in a cluster. By default, the certificates in use by the kubelets will not be recognized by the metrics-server. Therefore it is custom configured to do no validation of the TLS certificates: [(see patch-file)](argo-template/patches/container-patches.yaml).

## Usage
```
kubectl top node --show-capacity 
kubectl top pod
```
