# Changes here will be overwritten by Copier; DO NOT EDIT MANUALLY

import "machine/config/disk/disk-selector" as disk;

del(.machine.install.disk) | # exchanged with the disk selector
.machine.install.diskSelector = disk::disk_selector
