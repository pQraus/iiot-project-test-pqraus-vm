from ._invoke_version import check_version

check_version()

from invoke import Collection

from . import lowlevel_tasks
from ._common import print_deprecated_warning
from .highlevel_tasks import (connection, initial_tasks, sealed_secrets,
                              setup_tools, synchronizing, upgrade)

namespace = Collection()
namespace.add_collection(initial_tasks, name="init")
namespace.add_collection(lowlevel_tasks, name="lowlevel")

namespace.add_task(connection.connect_talos)
namespace.add_task(connection.connect_argo)
namespace.add_task(connection.connect_traefik)
namespace.add_task(connection.connect_k8s)
namespace.add_task(connection.disconnect_from_box)

namespace.add_task(connection.port_forward_argo)  # DEPRECATED
namespace.add_task(connection.port_forward_traefik)  # DEPRECATED
namespace.add_task(connection.set_k8s_context)  # DEPRECATED
namespace.add_task(connection.unset_contexts)  # DEPRECATED

namespace.add_task(setup_tools.setup_tools)

namespace.add_task(sealed_secrets.seal_secret)

namespace.add_task(synchronizing.seal_mc)
namespace.add_task(synchronizing.status)
namespace.add_task(synchronizing.sync)

namespace.add_task(upgrade.upgrade_k8s)
namespace.add_task(upgrade.upgrade_talos)

print_deprecated_warning()
