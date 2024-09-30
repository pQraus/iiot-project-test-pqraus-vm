from ._common import Command, parse_kwargs_to_cli_args


def apply(file: str, kubeconfig: str, **kwargs):
    Command.check_output(
        cmd=[
            "kubectl",
            "apply",
            "-f",
            file,
            "--kubeconfig",
            kubeconfig,
            *parse_kwargs_to_cli_args(**kwargs)])


def config_set(key: str, value: str, kubeconfig: str, **kwargs):
    Command.check_output(
        cmd=[
            "kubectl",
            "config",
            "set",
            key,
            value,
            "--kubeconfig",
            kubeconfig,
            *parse_kwargs_to_cli_args(**kwargs)
        ]
    )


def config_set_cluster(cluster: str, server: str, kubeconfig: str, **kwargs):
    Command.check_output(
        cmd=[
            "kubectl",
            "config",
            "set-cluster",
            cluster,
            "--server",
            server,
            "--kubeconfig",
            kubeconfig,
            *parse_kwargs_to_cli_args(**kwargs)
        ]
    )


def config_set_context(context: str, cluster: str, user: str, kubeconfig: str, **kwargs):
    Command.check_output(
        cmd=[
            "kubectl",
            "config",
            "set-context",
            context,
            "--cluster",
            cluster,
            "--user",
            user,
            "--kubeconfig",
            kubeconfig,
            *parse_kwargs_to_cli_args(**kwargs)
        ]
    )


def config_set_credentials(credentials: str, kubeconfig: str, **kwargs):
    Command.check_output(
        cmd=[
            "kubectl",
            "config",
            "set-credentials",
            credentials,
            "--kubeconfig",
            kubeconfig,
            *parse_kwargs_to_cli_args(**kwargs)
        ]
    )


def config_use_context(context: str, kubeconfig: str, **kwargs):
    Command.check_output(
        cmd=[
            "kubectl",
            "config",
            "use-context",
            context,
            "--kubeconfig",
            kubeconfig,
            *parse_kwargs_to_cli_args(**kwargs)
        ]
    )


def fetch(resource: str, format: str, kubeconfig: str, **kwargs) -> str:
    result = Command.check_output(
        cmd=[
            "kubectl",
            "get",
            resource,
            "-o",
            format,
            "--kubeconfig",
            kubeconfig,
            *parse_kwargs_to_cli_args(**kwargs)
        ],
        additional_error_msg=f"Unable to retrieve resource: '{resource}' from k8s."
    )
    return result


def get_current_context(kubeconfig: str) -> str:
    return Command.check_output(cmd=["kubectl", "config", "current-context", "--kubeconfig", kubeconfig])


def kustomize(from_file: str, to_file: str, enable_helm: bool, **kwargs):
    cmd = [
        "kubectl",
        "kustomize",
        from_file,
        "-o",
        to_file,
        *parse_kwargs_to_cli_args(**kwargs)
    ]
    if enable_helm:
        cmd.append("--enable-helm")

    Command.check_output(cmd=cmd)


def port_forward(resource: str, namespace: str, ports_from_to: str, kubeconfig: str, **kwargs):
    Command.check_output(
        cmd=[
            "kubectl",
            "port-forward",
            "-n",
            namespace,
            resource,
            ports_from_to,
            "--kubeconfig",
            kubeconfig,
            *parse_kwargs_to_cli_args(**kwargs)
        ]
    )


def rollout_restart_deployment(deployment: str, namespace: str, kubeconfig: str, **kwargs):
    Command.check_output(
        cmd=[
            "kubectl",
            "-n",
            namespace,
            "rollout",
            "restart",
            "deployment",
            deployment,
            "--kubeconfig",
            kubeconfig,
            *parse_kwargs_to_cli_args(**kwargs)
        ]
    )
