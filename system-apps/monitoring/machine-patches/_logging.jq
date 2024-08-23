.machine.logging.destinations |= [
  {
    "endpoint": "tcp://10.96.0.80:5000",
    "format": "json_lines"
  }
] |
.machine.install.extraKernelArgs |= ["talos.logging.kernel=tcp://10.96.0.80:6000"]
