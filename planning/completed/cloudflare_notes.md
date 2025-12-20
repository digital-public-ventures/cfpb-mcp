# Cloudflare Tunnel

This workspace exposes the FastAPI service over HTTPS using a Cloudflare Tunnel. The tunnel runs as a dedicated Docker Compose service (`cloudflared`) and forwards the public hostname to the internal `api` service.

The intended public deployment uses a stable hostname (example from this repo): `https://api.jimmoffet.me`.

There are two supported ways to manage the tunnel:

1. **Token-based tunnel (default)**: Cloudflare dashboard manages the public hostname; Compose runs `cloudflared` using `TUNNEL_TOKEN`.
2. **File-managed tunnel (optional / config-as-code)**: This repo contains `cloudflared/config.yml`; Compose runs `cloudflared` using `TUNNEL_ID` plus a local `credentials.json` file.

Choose **one** approach (dashboard-managed token *or* file-managed config). Do not mix both.

***

## Dependencies

* **Docker + Docker Compose** (this repo uses Compose to run `api`, `cloudflared`, etc.)
* **Cloudflare Tunnel** via the container image `cloudflare/cloudflared:latest` (no local `cloudflared` install required to run the tunnel)

Prereqs (from this repo’s setup guidance):

* A **Cloudflare account** with your domain onboarded (nameservers pointing to Cloudflare)
* A **Cloudflare Tunnel** created in Cloudflare Zero Trust, with hostname routing configured

Optional (only if you want to *create/manage* tunnels locally rather than via the dashboard):

* `cloudflared` CLI installed on your machine (used to `login`, `tunnel create`, and obtain the credentials file)

***

## Default: Token-based tunnel (recommended)

### How it works

* The `cloudflared` container runs `cloudflared tunnel run`.
* Authentication is provided via the environment variable `TUNNEL_TOKEN`.
* The hostname routing is managed in the Cloudflare dashboard.

### One-time Cloudflare dashboard setup

In Cloudflare Dashboard → Zero Trust → Tunnels:

1. Create a tunnel (type: **Cloudflared**)
2. Add a **Public Hostname**:

* Hostname: `api.yourdomain.com`
* Service type: **HTTP**
* URL: `http://api:8000`

`api` is the Docker Compose service name, and `8000` is the port Uvicorn listens on inside the container.

### Compose configuration

From `compose.yaml`:

```yaml
cloudflared:
  image: cloudflare/cloudflared:latest
  restart: unless-stopped
  command: tunnel run
  environment:
    - TUNNEL_TOKEN=${TUNNEL_TOKEN}
  depends_on:
    - api
```

### Required env vars

* `TUNNEL_TOKEN` — Cloudflare Tunnel connector token (created in Cloudflare Zero Trust)

***

## Optional: File-managed tunnel (config-as-code)

This mode uses the repo’s `cloudflared/config.yml` and a credentials file mounted into the container.

### Required files

* `cloudflared/config.yml` (tracked in git)
* `cloudflared/credentials.json` (NOT tracked; you create/copy this locally)

The credentials file is created when you create a tunnel (or download credentials for an existing tunnel). The repo’s `cloudflared/config.yml` expects the file to exist at `/etc/cloudflared/credentials.json` inside the container.

### Required env vars

* `TUNNEL_ID` — the tunnel UUID

### `cloudflared/config.yml`

Current template in this workspace:

```yaml
tunnel: ${TUNNEL_ID}
credentials-file: /etc/cloudflared/credentials.json

ingress:
  - hostname: api.yourdomain.com
    service: http://api:8000
  - service: http_status:404
```

Notes:

* Replace `api.yourdomain.com` with your real hostname.
* `service: http://api:8000` targets the Compose service name `api` on the internal Docker network.

### Compose configuration (file-managed)

In `compose.yaml` there is a commented-out alternative `cloudflared` service definition. It mounts `./cloudflared` into the container and runs with `--config`:

```yaml
cloudflared:
  image: cloudflare/cloudflared:latest
  restart: unless-stopped
  command: tunnel --config /etc/cloudflared/config.yml run
  environment:
    - TUNNEL_ID=${TUNNEL_ID}
  volumes:
    - ./cloudflared:/etc/cloudflared
  depends_on:
    - api
```

To switch to file-managed mode:

1. Add `cloudflared/credentials.json` (from your Cloudflare tunnel) into this repo locally.
2. Set `TUNNEL_ID` in your `.env`.
3. Update `cloudflared/config.yml` with the correct `hostname`.
4. In `compose.yaml`, replace the token-based `cloudflared` service with the file-managed one (uncomment it and comment/remove the token-based service).

***

## What the tunnel forwards to

* The tunnel forwards the public hostname to the internal service `http://api:8000`.
* The API container does not need a host port exposed for public access; Cloudflare Tunnel connects from inside the Docker network.

If you want to test locally *without* Cloudflare Tunnel, you can uncomment the `ports:` mapping in `compose.yaml` under the `api` service.

***

## Operational notes

* **No port-forwarding**: public access comes from the tunnel; you typically don’t publish a host port.
* **Portability**: this is lift-and-shift portable if you keep the `api` service name and container port `8000` consistent (or update the Cloudflare hostname mapping).
* **Secrets**: treat `TUNNEL_TOKEN` like a secret and rotate it if compromised.
