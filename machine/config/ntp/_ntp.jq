# Changes here will be overwritten by Copier; DO NOT EDIT MANUALLY

# main patch for the 'machine.time' section

import "machine/config/ntp/config" as ntp_config;


.machine.time = ntp_config::ntp_config
