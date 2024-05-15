# Changes here will be overwritten by Copier; DO NOT EDIT MANUALLY

# write localhost and 127.0.0.1 to the talos api certs, required for the talosctl provider extension

include "upsert";

.machine.certSANs |= append_unique("127.0.0.1") |
.machine.certSANs |= append_unique("localhost")