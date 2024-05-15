# Changes here will be overwritten by Copier; DO NOT EDIT MANUALLY

# main patch for the 'cluster' section
# the additional (project specific) configuration will be merged with the cluster object

import "machine/globals" as globals;
import "machine/config/k8s/additional-config" as additional;

.cluster.controlPlane.endpoint = "https://" + globals::name + ":6443" |
.cluster.clusterName = globals::name |
.cluster.allowSchedulingOnControlPlanes = true |
.cluster.discovery.enabled = false |
.cluster.network.cni.name = "flannel" |

# delete succeeded / failed pods
.cluster.controllerManager.extraArgs."terminated-pod-gc-threshold" = "20" |

# merge the additional configuration:
.cluster |= . * additional::additional_config |

# ensure that there aren't any extra args for kubelet (in old base version server rotation was enabled)
del(.machine.kubelet.extraArgs)
