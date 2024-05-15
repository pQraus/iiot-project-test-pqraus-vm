# Changes here will be overwritten by Copier; DO NOT EDIT MANUALLY

# main patch for the 'machine.network' section
# the additional (project specific) configuration will be merged with the network object

import "machine/globals" as globals;
import "machine/config/network/interfaces" as interfaces;
import "machine/config/network/nameservers" as nameservers;
import "machine/config/network/additional-config" as additional;


.machine.network.hostname = globals::name |

# data patches:
.machine.network.interfaces = interfaces::interfaces |
.machine.network.nameservers = nameservers::nameservers |
# merge the additional configuration:
.machine.network |= . * additional::additional_config
