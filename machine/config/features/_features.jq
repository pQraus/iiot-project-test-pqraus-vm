# Changes here will be overwritten by Copier; DO NOT EDIT MANUALLY

# main patch for the 'machine.features' section

# disable the extended key usage check of client certificates
# this is currently needed because the auth proxy create a client cert with additional keys
.machine.features.apidCheckExtKeyUsage = false