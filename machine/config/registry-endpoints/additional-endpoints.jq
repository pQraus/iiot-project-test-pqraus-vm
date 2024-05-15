# additional endpoint configuration

# this file is individually for the project and will not be updated by copier
# add the configuration into the function below, the returned object will be merged with the `machine.registries.mirrors` object
# see: https://www.talos.dev/v1.5/talos-guides/configuration/pull-through-cache/
# https://www.talos.dev/v1.5/reference/configuration/#registrymirrorconfig

def additional_endpoints:
  # must return a json object
  {
  #  "docker.io": {
  #    "endpoints": ["https://my-registry"]
  #  },
  #  "quay.io": {
  #    "endpoints": ["https://my-registry/v2/quay"],
  #    "overridePath": true
  #  },
  #  "ghcr.io": {
  #    "endpoints": ["https://my-registry/v2/github"],
  #    "overridePath": true
  #  },
  #  "registry.k8s.io": {
  #    "endpoints": ["https://my-registry/v2/kubernetes"],
  #    "overridePath": true
  #  },
  #  "gcr.io": {
  #    "endpoints": ["https://my-registry/v2/google"],
  #    "overridePath": true
  #  }
  };
