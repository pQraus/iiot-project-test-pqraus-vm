# Changes here will be overwritten by Copier; DO NOT EDIT MANUALLY

# (HAproxy) configuration file for the auth-proxy extension

include "upsert";

def config_content:
"defaults
    mode tcp
    timeout connect 1h
    timeout client 1h
    timeout server 1h
frontend insecure_talos_api
    bind :51002 interface lo ssl crt /extension-data/secrets/talos/server/server.pem
    default_backend talos_api
frontend secure_talos_api
    bind :51001 ssl crt /extension-data/secrets/talos/server/server.pem ca-file /extension-data/auth-proxy/teleport_ca.pem verify required
    default_backend talos_api
backend talos_api
    server talos_api :50000 ssl crt /extension-data/secrets/talos/admin/client.pem ca-file /extension-data/secrets/talos/ca/ca.crt
";

def auth_proxy_config_file:
{
"content": config_content,
"permissions": 384,
"path": "/var/extension-data/auth-proxy/ha_config.cfg",
"op": "create"
};

# the teleport ca files are created with: `tctl auth export --type tls-user`
# 1. ca: prod.teleport.schulzdevcloud
# 2. ca: staging.teleport.schulzdevcloud
def teleport_ca_content:
"-----BEGIN CERTIFICATE-----
MIID3jCCAsagAwIBAgIQU96o0nEdVmOPVcm8PdDF9TANBgkqhkiG9w0BAQsFADCB
iDEpMCcGA1UEChMgcHJvZC50ZWxlcG9ydC5zY2h1bHpkZXZjbG91ZC5jb20xKTAn
BgNVBAMTIHByb2QudGVsZXBvcnQuc2NodWx6ZGV2Y2xvdWQuY29tMTAwLgYDVQQF
EycxMTE0ODIwMzc2NzA0Nzc1NjM1NzkzNDYyNjQyMDAyNzQwMzYyMTMwHhcNMjMw
NTAyMDczNDU5WhcNMzMwNDI5MDczNDU5WjCBiDEpMCcGA1UEChMgcHJvZC50ZWxl
cG9ydC5zY2h1bHpkZXZjbG91ZC5jb20xKTAnBgNVBAMTIHByb2QudGVsZXBvcnQu
c2NodWx6ZGV2Y2xvdWQuY29tMTAwLgYDVQQFEycxMTE0ODIwMzc2NzA0Nzc1NjM1
NzkzNDYyNjQyMDAyNzQwMzYyMTMwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQDq8g6+loKyY/0dhad69F5zuFBRlefMvrgKrt001EFSeEfbDd154Sfg7Qtj
1eKJEiNSoCxHvbtDlrb4UDHRCIFZjswNG1dC2Ym/xpPhov39CWZKJU45GpT+GVD1
7oHGeA+G2Jjsy/hc6w5fufK94uBFS/4S2P9TuSkvSFUk4U4ECUkb4Z7+K3/B5qEz
9eaUgsxbX/sYrUcKKus5WO0noaKM/rfxNzPNQ/lbfjkLn2Nmj8YuJ5PJzKPliYOo
OkhiU28xnSPs0iQYQPy2FEP2732PBXhmNUGE/V5dwKhHqAdlnIZYthUGbJWPOaV9
REDQSXen0XQ+QkhMQvTUMDQOELLZAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBpjAP
BgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBRfqgvsbO3Hru+Bvta4yEnojKU4BjAN
BgkqhkiG9w0BAQsFAAOCAQEAbuJjs/cJv8Fg3ZiYo9QkH3YUOGMbArGQSWgtmX9W
GSREHoZlBhpCtWApa08kht8UfEIPmva2tTiBvlpQs7PcBwWoLYEcIW/aCCQeUqxi
oJ+lp++XYWCadM0Us2QFkZ1I/QUCKn9jdDhHeKKt7PrS27drkH2Scg2V9u6DmGLZ
nW2Z2anAmD6zAJDFc9PNzj9pXw8a0LByECFfJqmUe5m1UWUh/+U7ThEhhPEDnhH2
qOZuQx5sDVWLa53T7DvOfHlo2Ur4is8l2tpVcCzM/Qja3u7rzqoCxWgMSHzbYb/e
NmVmVIvg+nGEZDDfBCVbQ9L+QdiwVedO/WAzRAhqlbt6sQ==
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIID6zCCAtOgAwIBAgIRAN+AGuqFfOmG7JgaWz6e4tIwDQYJKoZIhvcNAQELBQAw
gY4xLDAqBgNVBAoTI3N0YWdpbmcudGVsZXBvcnQuc2NodWx6ZGV2Y2xvdWQuY29t
MSwwKgYDVQQDEyNzdGFnaW5nLnRlbGVwb3J0LnNjaHVsemRldmNsb3VkLmNvbTEw
MC4GA1UEBRMnMjk3MDgzMDAyOTgxMjgwOTM2NzgzNDYwNjI1NTIxNTU0OTQwNjI2
MB4XDTIzMDQyNTExNTEzMVoXDTMzMDQyMjExNTEzMVowgY4xLDAqBgNVBAoTI3N0
YWdpbmcudGVsZXBvcnQuc2NodWx6ZGV2Y2xvdWQuY29tMSwwKgYDVQQDEyNzdGFn
aW5nLnRlbGVwb3J0LnNjaHVsemRldmNsb3VkLmNvbTEwMC4GA1UEBRMnMjk3MDgz
MDAyOTgxMjgwOTM2NzgzNDYwNjI1NTIxNTU0OTQwNjI2MIIBIjANBgkqhkiG9w0B
AQEFAAOCAQ8AMIIBCgKCAQEAxsqD3PzYYBfL9QgdaL+g7CiwbF/865awXnpt4tTu
l5EBoTqlvXAqH0JumDEGq0OpMUR7SNli7e1BKZjmxKlQZUSre3nOB8FreAog27O0
ZmKOiS96sHVpKGPx2Dabw+8qkcJhpFwlhpykNo6Th2hjhD/sOX8T5qZm3CUZPnSK
7iJYgsIRSpfo75jZhAsw9EEwXh7uRKgI32UfuQZ25sc8Km5cD01YvRXEP74yDsw9
Gj3EPBhykD3EY50qlHWy2okqLS1aabD0NOmMUXesr/a/F6o1FQY3gfN8RrPLLz8R
FFyfM+O2ILOOsNruCYY6kaqMJRHnhhxohBMPymW4viWbdQIDAQABo0IwQDAOBgNV
HQ8BAf8EBAMCAaYwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQU9zHkaZXz73ox
P/9xy9UVkBL3ufswDQYJKoZIhvcNAQELBQADggEBAA3FWKSjhleAAX0TWSjKYaNS
qupbMR93xYGSlkXTSeLNG+pA/OIUQrXJtACmrOSTHDaBHf/UPVPOhM4huGDj1jYL
P9Vtym95kXCtE+7R45nf2f0BksPeM2zjaLlSm3z/Qq4IgV62T0lPa57PZHZLAbss
9v22poqHUe4S598C4A82/P9h7EbaBqWaFKCsWfypb97YJuHQYKdixgxnwQ5yFRmX
3PS5I4qlWH2QuLjn5iSVUzAFsTOacaVR2zjARVKNdBSUaf40DxyPPC6wl1l947hn
oRIINIq+MB6OdbyYeS42d/eohm66m0LLTluRn1xNXu6WAjdXckA03WMIdcfQmnA=
-----END CERTIFICATE-----";

def teleport_ca_file:
{
"content": teleport_ca_content,
"permissions": 384,
"path": "/var/extension-data/auth-proxy/teleport_ca.pem",
"op": "create"
};

# reload every 30 minutes -> 60 * 30
def reload_time_sec_file:
{
"content": "1800",
"permissions": 384,
"path": "/var/extension-data/auth-proxy/reload_time_sec",
"op": "create"
};

.machine.files |= upsert("path"; auth_proxy_config_file) |
.machine.files |= upsert("path"; teleport_ca_file) |
.machine.files |= upsert("path"; reload_time_sec_file) |

# remove old file patches
.machine.files |= delete_elements("path"; "^\/var\/lib\/auth-proxy")
