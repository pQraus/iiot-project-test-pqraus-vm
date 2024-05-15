# Changes here will be overwritten by Copier; DO NOT EDIT MANUALLY

# this patch will redirect the image pull requests from:
# quay, ghcr, registry.k8s and ghcr to our pull-through registry
# docker images will be pulled directly from dockerhub
# see: https://www.talos.dev/v1.5/talos-guides/configuration/pull-through-cache/

import "machine/config/registry-endpoints/additional-endpoints" as additional;

.machine.registries.mirrors = {
  "registry-1.docker.io": {
    "endpoints": ["https://registry-1.docker.io"]
  },
  "quay.io": {
    "endpoints": ["https://registry.schulzdevcloud.com/v2/quay"],
    "overridePath": true
  },
  "ghcr.io": {
    "endpoints": ["https://registry.schulzdevcloud.com/v2/github"],
    "overridePath": true
  },
  "registry.k8s.io": {
    "endpoints": ["https://registry.schulzdevcloud.com/v2/kubernetes"],
    "overridePath": true
  },
  "gcr.io": {
    "endpoints": ["https://registry.schulzdevcloud.com/v2/google"],
    "overridePath": true
  },
  "nvcr.io": {
    "endpoints": ["https://registry.schulzdevcloud.com/v2/nvidia"],
    "overridePath": true
  }
} |

# merge the additional endpoints configuration:
.machine.registries.mirrors |= . * additional::additional_endpoints