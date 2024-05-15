# ntp configuration

# this file is individually for the project and will not be updated by copier
# the returned object will be patched into 'machine.time'

def ntp_config:
  # must return a json object
  {
    "bootTimeout": "0m30s",  # continue the boot process without a ntp-sync
    "servers": [    # ntp-servers
      "pool.ntp.org"
    ]

    # to disable the ntp sync:
    # "disabled": true 
};
