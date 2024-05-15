# network interfaces configuration

# this file is individually for the project and will not be updated by copier
# the returned list will be patched into 'machine.network.interfaces'

def interfaces:
  # must return a json list
  [
    # example config for an interface which uses DHCP:
    { 
      "interface": "ens0", 
      # "deviceSelector": {
      #   "hardwareAddr": "0a:34:12:56" # mac-address can also be used to configure an interface
      # }
      "dhcp": true,
      "dhcpOptions" : {
        "routeMetric": 0  # optional metric / priority of the DHCP routes, 0: default value = 1024
      },
      "mtu": 1500   # 'package' size, ethernet = 1500
    }

    # example config for an interface with static ip:
    # ,
    #{
    #  "interface": "eth1", # Interface with static IP
    #  "addresses": ["192.168.50.20/24"],   # static ip with subnetlength
    #  "routes": [
    #    {
    #      "network": "0.0.0.0/0",     # destination, in this case the default route
    #      "gateway": "192.168.50.1",  # normally the address of the router
    #      "metric": 1024              # optional metric / priority of this route
    #    }                             # large number --> low priority
    #  ],
    #  "dhcp": false,
    #  "mtu": 1500  # 'package' size, ethernet = 1500
    #}
  ];
  