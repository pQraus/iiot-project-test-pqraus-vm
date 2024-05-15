# Changes here will be overwritten by Copier; DO NOT EDIT MANUALLY

include "upsert";

def openebs_extra_mount:
{
  "destination": "/var/openebs/local",
  "type": "bind",
  "source": "/var/openebs/local",
  "options": [
    "bind",
    "rshared",
    "rw"
  ]
};

.machine.kubelet.extraMounts |= upsert("destination"; openebs_extra_mount)