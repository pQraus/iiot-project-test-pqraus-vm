# Traefik

Traefik serves as the ingress controller of the machine. It's purpose is to handle all kinds of access to applications running in k8s on the machine.

With the help of traefik we do declare different `entrypoints`. Each of them functions as a gateway to a certain selection of k8s apps. This way we can categorize access to a group of k8s apps.

By default is the entrypoint **private** during IIoT-Box-Setup configured. The entrypoints **public** and **nodeport** are optionals.

Entrypoints:
- **private:** access via task `iiotctl connect traefik` (Developer)
- **public:** access via teleport (Cloud API)
- **nodeport:** access via talos external port from local network of machine (Customer/User)

*...system-apps/traefik/argo-template/**kustomization.yaml**:*
```yaml
...
ports:
  private:           # <-- name of entrypoint
    port: 8180       # <-- port which traefik pod opens (entrypoint)
    exposedPort: 80  # <-- talos internal port of traefik service other apps can access entrypoint by
    expose: true     # <-- bind traefik pod entrypoint port to traefik service
  public:
    port: 8280
    expose: false
  nodeport:
    port: 8380
    expose: false

service:
  type: ClusterIP
  spec:
    clusterIP: "10.96.0.100"
...
```

The **private** entrypoint is the only of the three thats accessible via the actual traefik service. For the other two (if chosen) are separate services that route to the respective port of the traefik pod (to the entrypoint) created by copier:

*...system-apps/traefik/argo-template/resources/**public-service.yaml***
```yaml
apiVersion: v1
kind: Service
metadata:
  name: traefik-public
spec:
  type: ClusterIP
  clusterIP: 10.96.0.101
  selector:
    app.kubernetes.io/instance: traefik-traefik
    app.kubernetes.io/name: traefik
  ports:
  - name: public
    port: 80  # <-- port to forward to
    targetPort: 8280
```

*...system-apps/traefik/argo-template/resources/**nodeport-service.yaml***
```yaml
apiVersion: v1
kind: Service
metadata:
  name: traefik-nodeport
spec:
  type: NodePort
  selector:
    app.kubernetes.io/instance: traefik-traefik
    app.kubernetes.io/name: traefik
  ports:
  - name: nodeport
    port: 80  # <-- port to forward to
    targetPort: 8380
    nodePort: 30080  # <-- talos external port to access entrypoint by (has to be between 30000 - 32767)
```

For both the **private** and (if chosen) the **public** entrypoint will be automatically teleport apps configured during the copier setup of the repository:

*.../system-apps/teleport-configurator/argo/config/**config.yaml***
```yaml
...
app_service:
  enabled: true
  apps:
    - name: talos-foobar
      uri: tcp://localhost:51002
      labels:
        usage: iiot
        kind: talos
    - name: private-foobar
      uri: http://10.96.0.100:80  # <-- IP of traefik service + port to access entrypoint 'private' by via teleport
      labels:
        usage: iiot
        kind: ingress-private
    # optionally added by copier:
    - name: public-foobar
      uri: http://10.96.0.101:80  # <-- IP of traefik-public service + port to access entrypoint 'private' by via teleport
      labels:
        usage: iiot
        kind: ingress-public
...
```

## Usage

To configure under which subdomain and/or path and via which entrypoint you can reach your application, you have to create an `IngressRoute` - a traefik-own k8s resource type.

`IMPORTANT:` to see which ingress routes are already configured and what entrypoints, subdomains and paths they use visit the traefik dashboard via port-forward the exposed traefik service port 80 (access to **private** entrypoint) to your local port 3000:

```bash
kubectl port-forward -n traefik services/traefik 3000:80
```

--> afterwards visit `traefik.localhost:3000` in your local browser and go into the menu -> HTTP

### Example

You want to access a webserver you deployed in k8s on an IIoT-Box using the default **private** entrypoint, via your local browser with one of the following URLs:
- `webserver.localhost:3000/foo`
- `webserver.localhost:3000/bar`

#### Step 1.:

Create the manifest for the IngressRoute in your user-apps /argo/resources or /argo-template/resources folder. Deploy it.

*.../user-apps/webserver/argo/resources/**ingress.yaml*** or *.../user-apps/webserver/argo-template/resources/**ingress.yaml***
```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: webserver-route
  namespace: webserver-namespace
spec:
  entryPoints:
  - private
  # - public  <-- you can list multiple entrypoints through which someone can access your app
  # - nodeport
  routes:
  # define via which subdomain and/or path someone can access your app
  - match: HostRegexp(`{subdomain:webserver}.{*}`) && (PathPrefix(`/foo`) || PathPrefix(`/bar`))
    kind: Rule
    services:
    - name: webserver-service  # <-- name of the service of your app
      port: 80
```

#### Step 2.:

Port-forward to the **private** entrypoint (the services that lead to this and the **public** entrypoint are both accessible via the port 80):

```bash
kubectl port-forward -n traefik services/traefik 3000:80
```

#### Step 3.:

Visit the browser URLs: `webserver.localhost:3000/foo` and `webserver.localhost:3000/bar`.
