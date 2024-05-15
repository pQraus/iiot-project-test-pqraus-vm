# network nameservers configuration

# this file is individually for the project and will not be updated by copier
# the returned list will be patched into 'machine.network.nameservers'

def nameservers:
  # must return a json list
  [
    # default nameservers:
    "8.8.8.8",
    "1.1.1.1"
  ];
