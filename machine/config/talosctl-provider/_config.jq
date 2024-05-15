# Changes here will be overwritten by Copier; DO NOT EDIT MANUALLY

# write the root ca and config files to the disk, required for the talosctl provider extension

include "upsert";

def ca_crt_file(ca_crt):
{
"content": ca_crt,
"permissions": 384,
"path": "/var/extension-data/talosctl-provider/ca.b64.crt",
"op": "create"
};

def ca_key_file(ca_key):
{
"content": ca_key,
"permissions": 384,
"path": "/var/extension-data/talosctl-provider/ca.b64.key",
"op": "create"
};

# cert ttl = 30 days (30 * 24 * 60 * 60)
# renewal interval = 1 h (60 * 60 )
def config_file_content:
"{
    \"cert_ttl_sec\": 2592000,
    \"renewal_interval_sec\": 3600
}";

def config_file:
{
    "content": config_file_content,
    "permissions": 384,
    "path": "/var/extension-data/talosctl-provider/config.json",
    "op": "create"
};

.machine.ca.crt as $ca_crt | 
.machine.ca.key as $ca_key |
ca_crt_file($ca_crt) as $crt_patch |
ca_key_file($ca_key) as $key_patch |
.machine.files |= upsert("path"; $crt_patch) |
.machine.files |= upsert("path"; $key_patch) |
.machine.files |= upsert("path"; config_file)