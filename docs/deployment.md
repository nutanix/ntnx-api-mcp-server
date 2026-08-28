# Deployment — Nutanix V4 API MCP Server

> **Scope:** How to install, configure, and run the server in each supported environment.
> Configuration key syntax: [configuration reference](./configuration.md).
> Authentication options and security hardening: [authentication and security guide](./authentication.md).

---

## Contents

1. [Deployment options overview](#1-deployment-options-overview)
2. [Local development](#2-local-development)
3. [Docker](#3-docker)
4. [Bare metal / VM](#4-bare-metal--vm)
5. [Network configuration](#5-network-configuration)
6. [Nutanix network proximity](#6-nutanix-network-proximity)
7. [Environment hardening](#7-environment-hardening)
8. [Health checks](#8-health-checks)
9. [Updating](#9-updating)

---

## 1. Deployment options overview

| Method | Complexity | Best for | Section |
|---|---|---|---|
| Local development | Low | Ad-hoc testing, personal use, and exploratory use on a developer workstation | [§2 Local development](#2-local-development) |
| Docker | Medium | Isolated, reproducible environments; CI pipelines; teams that standardise on containers | [§3 Docker](#3-docker) |
| Bare metal / VM | Medium | Persistent service on a server or VM close to Prism Central; long-running deployments | [§4 Bare metal / VM](#4-bare-metal--vm) |

> Local MCP clients use **stdio** by launching `nutanix-mcp serve-stdio` as a subprocess. Containerized platforms and gateways such as Nutanix Enterprise AI (NAI) need a network listener instead, so the container entrypoint runs the streamable HTTP transport on port 8080 by default.

---

## 2. Local development

**Audience:** Anyone doing local testing or exploratory use on their own workstation.

### 2.1 Prerequisites

- Python **3.11 or higher** (`python3 --version`)
- Git
- Access to a Prism Central cluster, or skip `PC_HOST` to run in `latest_release` mode with publicly available API specs

### 2.2 Clone and install

```bash
git clone https://github.com/nutanix/ntnx-api-mcp-server
cd ntnx-api-mcp-server
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

### 2.3 Configure credentials

```bash
mv .env.example .env
```

Edit `.env` with your values:

```dotenv
PC_HOST=your-pc.example.com
PC_PORT=9440
PC_USERNAME=your-username
PC_PASSWORD=your-password
PC_INSECURE=false
ARTIFACTS_DIR=./artifacts
LOG_DIR=./logs
```

> Use `PC_API_KEY` instead of (or alongside) `PC_USERNAME`/`PC_PASSWORD` if your cluster uses API key auth.
> Never commit `.env` — it is already listed in `.gitignore`.
> Full credential options: [authentication and security guide](./authentication.md).
> If your Prism Central uses a self-signed certificate, set `PC_INSECURE=true`. Keep it `false` for production environments.

### 2.4 Download API artifacts

```bash
nutanix-mcp init
```

This probes Prism Central for supported API namespaces and downloads their OpenAPI YAML specs into `artifacts/`. Without `PC_HOST`, it downloads the latest published specs from the Nutanix developer portal (`latest_release` mode).

### 2.5 Verify the configuration

```bash
nutanix-mcp run --validate-only
```

Expected output (JSON to stdout):

```json
{
  "pc_host": "your-pc.example.com",
  "pc_port": 9440,
  "pc_username": "your-username",
  "pc_api_key": null,
  "pc_insecure": false,
  "read_only_mode": true,
  "log_level": "INFO",
  "log_format": "text",
  "log_dir": "<path>",
  "artifacts_dir": "<path>",
  "default_artifacts_dir": "<path>",
  "artifact_mode": "pc_compatible"
}
```

A non-zero exit code means configuration or connectivity failed. Check the error detail in the JSON. For error details: [troubleshooting guide](./troubleshooting.md).

### 2.6 Start the server

```bash
nutanix-mcp serve-stdio
```

The process blocks, reading MCP messages from stdin. Connect your MCP client to it. For client setup: [integration guide](./integration.md).

---

## 3. Docker

Use Docker when the MCP server needs to run in an isolated runtime, CI pipeline, Kubernetes cluster, or NAI local-server deployment. NAI deploys local servers as containers and performs readiness checks against a TCP port, so stdio-only execution is not sufficient there.

### 3.1 Requirements

- Docker Engine 20.10 or later
- Repository cloned locally

### 3.2 Container behavior

The committed `Dockerfile` builds a Python 3.11 image, installs the package, runs as a non-root user, and defaults to:

```bash
nutanix-mcp serve-http
```

The HTTP server listens on `0.0.0.0:${PORT:-8080}` and exposes:

- `/mcp` for MCP streamable HTTP
- `/health` for readiness and liveness checks

The container uses `/tmp/nutanix-mcp-artifacts` and `/tmp/nutanix-mcp-logs` by default so it can run on platforms with a read-only root filesystem, including NAI.

### 3.3 Build the image

```bash
docker build -t nutanix-mcp:latest .
```

### 3.4 Run the container

For HTTP/gateway deployments, run the container as a service. Pass credentials via environment variables; never bake them into the image.

Example run command for manual testing:

```bash
docker run --rm \
  -p 8080:8080 \
  -e PC_HOST=your-pc.example.com \
  -e PC_PORT=9440 \
  -e PC_USERNAME=your-username \
  -e PC_PASSWORD=your-password \
  -e PC_INSECURE=false \
  nutanix-mcp:latest
```

The entrypoint downloads API artifacts on startup when the artifact directory is empty. For faster restarts, mount a writable volume at `/tmp/nutanix-mcp-artifacts`.

### 3.5 MCP client configuration with Docker

For local stdio clients, you can still point your MCP client at `docker run` instead of `nutanix-mcp` directly. In that mode, override the container command to `serve-stdio`.

Example for Cursor (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "PC_HOST=your-pc.example.com",
        "-e", "PC_PORT=9440",
        "-e", "PC_USERNAME=your-username",
        "-e", "PC_PASSWORD=your-password",
        "-e", "PC_INSECURE=false",
        "-e", "ARTIFACTS_DIR=/tmp/nutanix-mcp-artifacts",
        "-v", "/host/path/artifacts:/tmp/nutanix-mcp-artifacts",
        "nutanix-mcp:latest",
        "serve-stdio"
      ]
    }
  }
}
```

### 3.6 Verify the container is working

Run the validate-only check inside the container before wiring it to a client:

```bash
docker run --rm \
  -e PC_HOST=your-pc.example.com \
  -e PC_USERNAME=your-username \
  -e PC_PASSWORD=your-password \
  -e PC_INSECURE=false \
  -e ARTIFACTS_DIR=/tmp/nutanix-mcp-artifacts \
  -v /host/path/artifacts:/tmp/nutanix-mcp-artifacts \
  nutanix-mcp:latest run --validate-only
```

A `"startup_ready": true` field in the JSON output confirms everything is working.

### 3.7 Nutanix Enterprise AI

NAI local servers are deployed as Kubernetes containers behind the NAI gateway. Build an image from the included Dockerfile and configure NAI to run it with no extra command arguments; the default command starts `serve-http`.

Minimum NAI settings:

```dotenv
PC_HOST=your-pc.example.com
PC_PORT=9440
PC_API_KEY=your-prism-central-api-key
PC_INSECURE=false
READ_ONLY_MODE=true
ARTIFACTS_DIR=/tmp/nutanix-mcp-artifacts
LOG_DIR=/tmp/nutanix-mcp-logs
LOG_LEVEL=INFO
LOG_FORMAT=text
```

Set the exposed port to `8080`. NAI protects the public MCP route with its MCP Connector Key; Prism Central credentials remain server-side in the container environment.

---

## 4. Bare metal / VM

**Audience:** operators running the server as a persistent service on a Linux VM or physical server, typically co-located with or near Prism Central.

> **Note:** This section assumes a Linux host. macOS users running the server locally should refer to [§2 Local development](#2-local-development) instead.

### 4.1 System requirements

| Resource | Minimum |
|---|---|
| OS | Ubuntu 22.04 LTS, RHEL 9, or any distribution with Python 3.11+ available |
| Python | 3.11 or higher |
| RAM | 256 MB (the server is lightweight; most memory is used by loaded YAML artifacts) |
| CPU | 1 vCPU (single-threaded asyncio event loop; CPU is not the bottleneck) |
| Disk | 500 MB for the repo, venv, and downloaded YAML artifacts |
| Network | Outbound HTTPS access to Prism Central on port 9440 (or configured `PC_PORT`) |

### 4.2 Install runtime

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y python3.11 python3.11-venv git

# RHEL / Rocky / AlmaLinux
sudo dnf install -y python3.11 git
```

### 4.3 Install the server

```bash
# Clone to a stable location
sudo git clone https://github.com/nutanix/ntnx-api-mcp-server /opt/nutanix-mcp
cd /opt/nutanix-mcp

# Create a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 4.4 Configure credentials

```bash
cp /opt/nutanix-mcp/.env.example /opt/nutanix-mcp/.env
# Edit with your credentials — see docs/authentication.md for all options
```

### 4.5 Download API artifacts

```bash
cd /opt/nutanix-mcp
source .venv/bin/activate
nutanix-mcp init
```

### 4.6 Verify the installation

```bash
nutanix-mcp run --validate-only
```

Confirm `"artifact_mode": "pc_compatible"` (with `PC_HOST`) or `"latest_release"` (without) in the output.

### 4.7 Configure as a systemd service

The systemd unit file below is the recommended way to manage the server as a persistent service. It runs under a dedicated non-root user, restarts on failure, and writes logs to the standard journal (in addition to per-restart log files in `LOG_DIR`).

> Create the service user first — see [§7 Environment hardening](#7-environment-hardening) for the exact `useradd` commands and file permission setup. The unit file below assumes the user `nutanix-mcp` exists.

Save the following as `/etc/systemd/system/nutanix-mcp.service`:

```ini
[Unit]
Description=Nutanix V4 API MCP Server
Documentation=https://github.com/nutanix/ntnx-api-mcp-server
After=network-online.target
Wants=network-online.target

[Service]
# --- Identity ---
User=nutanix-mcp
Group=nutanix-mcp

# --- Working directory ---
# nutanix-mcp resolves relative paths (artifacts/, logs/) from here.
WorkingDirectory=/opt/nutanix-mcp

# --- Startup command ---
# Use the absolute path to the venv binary; do NOT use shell expansion.
ExecStart=/opt/nutanix-mcp/.venv/bin/nutanix-mcp serve-stdio

# --- Environment ---
# Credentials should come from the EnvironmentFile, not be inlined here.
EnvironmentFile=/opt/nutanix-mcp/.env

# --- Restart policy ---
Restart=on-failure
RestartSec=5s

# --- stdio transport ---
# The server communicates over stdin/stdout with its MCP client.
# StandardInput must be null when running as a service without a client attached;
# the process will exit cleanly when stdin closes. Set to 'socket' or
# leave as 'null' — the MCP client is responsible for spawning this process,
# so running it as a persistent daemon is only appropriate when the client
# handles the lifecycle (e.g., a proxy or wrapper process).
StandardInput=null
StandardOutput=journal
StandardError=journal
SyslogIdentifier=nutanix-mcp

# --- Security hardening ---
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/nutanix-mcp/artifacts /opt/nutanix-mcp/logs
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

> **stdio transport note:** The MCP server communicates via stdio, meaning it is designed to be spawned by an MCP client (Cursor, Claude Desktop, a proxy process) rather than run as a standalone daemon. Using systemd here is suitable when a wrapper process or MCP proxy manages the subprocess lifecycle. If you are running without a persistent client, omit systemd and let your MCP client manage the process directly.

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable nutanix-mcp
sudo systemctl start nutanix-mcp
sudo systemctl status nutanix-mcp
```

### 4.8 Log management

**Where logs go:**

- **Journal:** `journalctl -u nutanix-mcp -f` (live tail)
- **Per-restart log files:** `LOG_DIR` (default `/opt/nutanix-mcp/logs`), one file per restart named `nutanix-mcp-<YYYYMMDD>-<HHMMSS>-<microseconds>.log`

**Log rotation for per-restart files:**

The server does not rotate its own log files — it creates a new file on each restart. Add a logrotate rule to prevent unbounded disk growth:

```
# /etc/logrotate.d/nutanix-mcp
/opt/nutanix-mcp/logs/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    create 0640 nutanix-mcp nutanix-mcp
}
```

For JSON-formatted logs suitable for forwarding to a log aggregator, set `LOG_FORMAT=json` in `.env`.

---

## 5. Network configuration

### 5.1 Port the server listens on

For local stdio deployments, **none**. `nutanix-mcp serve-stdio` does not bind to any TCP port.

For HTTP/gateway deployments, `nutanix-mcp serve-http` listens on `0.0.0.0:${PORT:-8080}`. Put this endpoint behind a trusted gateway such as NAI rather than exposing it directly.

### 5.2 Outbound connectivity required

The server makes outbound HTTPS connections to Prism Central:

| Destination | Port | Protocol | Purpose |
|---|---|---|---|
| `PC_HOST` | `PC_PORT` (default `9440`) | HTTPS | All Nutanix V4 API calls and the startup readiness probe |
| `developers.nutanix.com` | 443 | HTTPS | YAML artifact download during `init`/`refresh` (only needed at artifact download time, not at runtime) |

### 5.3 Firewall rules

For local stdio deployments, there is no inbound port to open, so firewall rules only govern outbound traffic from the host where the server runs:

```bash
# Allow outbound HTTPS to Prism Central (adjust the IP and port as needed)
sudo ufw allow out to <PC_HOST> port 9440 proto tcp

# Allow outbound HTTPS to the Nutanix developer portal (for init/refresh only)
sudo ufw allow out to any port 443 proto tcp
```

### 5.4 Run on localhost or on a trusted host

Because the server runs as a subprocess spawned by your MCP client, it is inherently local to the machine running the client. Do not expose the process or any wrapper port to the network unless you have a specific, understood use case. Running on a server co-located with or near Prism Central is fine and recommended for latency reasons (see §6); exposing a management endpoint over the internet is not.

For security rationale — attack surface, credential handling, and TLS posture: [authentication and security guide](./authentication.md).

---

## 6. Nutanix network proximity

### 6.1 Where to run the server

The server calls Prism Central's V4 REST APIs over HTTPS for every tool invocation. Latency between the host running the server and Prism Central directly affects how quickly tool calls complete and return results to the AI client.

**Recommended:** Run the server on a host in the same data center or on the same LAN segment as Prism Central. This minimises per-call latency to single-digit milliseconds.

**Acceptable:** Run on a workstation connected to the corporate network via a low-latency VPN. Most API calls complete within the 30-second request timeout even over a good WAN link, but repeated calls (e.g., listing large result sets with pagination) will feel slower.

**Not recommended:** Run on a machine with high-latency or unreliable connectivity to Prism Central (e.g., consumer internet without VPN, satellite links). The 30-second per-request timeout is hardcoded and cannot be changed via configuration. Flaky connections will cause `execution_error` responses without retry at the API-call level.

### 6.2 Latency implications

| Topology | Round-trip latency to PC | Impact |
|---|---|---|
| Same LAN / data center | < 5 ms | Negligible |
| Corporate WAN / VPN | 10–50 ms | Acceptable; occasional slow responses on large payloads |
| Cross-region internet | 100–300 ms | Noticeable; possible timeouts on slow endpoints |

The server does not pool HTTP connections — each API call opens a new connection to Prism Central. High-latency links amplify this cost because TLS handshake overhead is paid on every call.

---

## 7. Environment hardening

### 7.1 Run as a non-root user

Never run the server as `root`. Create a dedicated system account with no login shell and no home directory:

```bash
# Create the service account
sudo useradd \
  --system \
  --no-create-home \
  --shell /usr/sbin/nologin \
  --comment "Nutanix MCP Server service account" \
  nutanix-mcp
```

### 7.2 File ownership and permissions

```bash
# Set ownership of the installation directory to the service account
sudo chown -R nutanix-mcp:nutanix-mcp /opt/nutanix-mcp

# Installation directory: owner read/write/execute, no world access
sudo chmod 750 /opt/nutanix-mcp

# .env file: owner read-only, no group or world access
# This file contains credentials — restrict it tightly
sudo chmod 600 /opt/nutanix-mcp/.env

# Artifacts directory: owner read/write, no world access
sudo chmod 750 /opt/nutanix-mcp/artifacts

# Logs directory: owner read/write, no world access
sudo chmod 750 /opt/nutanix-mcp/logs

# Virtual environment: readable by owner only
sudo chmod -R 750 /opt/nutanix-mcp/.venv
```

### 7.3 What should and should not be world-readable

| Path | Recommended permissions | Reason |
|---|---|---|
| `/opt/nutanix-mcp/.env` | `600` (owner-only) | Contains `PC_PASSWORD` and/or `PC_API_KEY` in plaintext |
| `/opt/nutanix-mcp/artifacts/` | `750` (owner + group) | OpenAPI YAML specs — not secret, but no reason to be world-readable |
| `/opt/nutanix-mcp/logs/` | `750` (owner + group) | Log files may contain request metadata |
| `/opt/nutanix-mcp/.venv/` | `750` (owner + group) | Executable code; restrict to owner and group |
| `/opt/nutanix-mcp/src/` | `750` (owner + group) | Source code — not secret, but no reason to be world-readable |

> **Plaintext credentials on disk:** The `nutanix-mcp init` and `nutanix-mcp refresh` commands write credentials to `.env` on disk after execution. Ensure this file has `600` permissions immediately after creation. For the full security discussion including credential storage risks: [authentication and security guide](./authentication.md).

---

## 8. Health checks

### 8.1 HTTP health endpoint

`nutanix-mcp serve-http` exposes `/health` for container and gateway health checks.

`nutanix-mcp serve-stdio` does not expose a health endpoint; use process-level checks for local stdio deployments.

### 8.2 Process-level monitoring

Use process-level checks instead:

**With systemd:**

```bash
# Check service status
systemctl is-active nutanix-mcp

# Get detailed status and recent log lines
systemctl status nutanix-mcp

# Live log tail
journalctl -u nutanix-mcp -f
```

**Without systemd (any OS):**

```bash
# Confirm the process is running
pgrep -f "nutanix-mcp serve-stdio"

# Check that it loaded artifacts successfully at startup
# Successful startup logs this at INFO level:
grep "startup_mode" /opt/nutanix-mcp/logs/nutanix-mcp-*.log | tail -1
```

### 8.3 Pre-flight validation

Before relying on the server, run the built-in validation check:

```bash
nutanix-mcp run --validate-only
```

A successful response has `"artifact_mode"` set and no error fields. A failed response has `"startup_ready": false` and an `"error"` field explaining the problem.

### 8.4 External monitoring recommendations

For long-running deployments:

- Monitor the systemd service state with your infrastructure monitoring tool (Nagios, Prometheus `node_exporter` service state check, Datadog, etc.)
- Alert on the process exiting unexpectedly (`RestartSec=5s` in the unit file will restart it, but repeated restarts indicate a configuration problem)
- Watch log file growth in `LOG_DIR` — each restart creates a new file; abnormally high restart rates generate many files quickly

---

## 9. Updating

Before updating, review [CHANGELOG.md](../CHANGELOG.md) for changes that may require configuration updates or affect existing deployments.

### 9.1 Pull a new version

```bash
cd /opt/nutanix-mcp
sudo -u nutanix-mcp git pull origin main
```

### 9.2 Update dependencies

```bash
sudo -u nutanix-mcp /opt/nutanix-mcp/.venv/bin/pip install -e .
```

### 9.3 Refresh API artifacts

If the update includes changes to namespace support or API specs, re-run artifact download:

```bash
sudo -u nutanix-mcp /opt/nutanix-mcp/.venv/bin/nutanix-mcp refresh --force
```

`refresh --force` downloads fresh specs and backs up existing artifacts to `.refresh_backup/` first. If any download fails, existing artifacts are restored automatically.

### 9.4 Restart the service

```bash
sudo systemctl restart nutanix-mcp
sudo systemctl status nutanix-mcp
```

Confirm the process is active and the log shows a clean startup (no error JSON on stdout at startup).

### 9.5 Rollback if something goes wrong

**Step 1 — Restore the previous code version:**

```bash
cd /opt/nutanix-mcp
sudo -u nutanix-mcp git log --oneline -5     # find the previous commit hash
sudo -u nutanix-mcp git checkout <previous-commit-hash>
sudo -u nutanix-mcp /opt/nutanix-mcp/.venv/bin/pip install -e .
```

**Step 2 — Restore the previous artifacts (if `refresh --force` was run):**

```bash
# The backup created by refresh is in .refresh_backup/
sudo -u nutanix-mcp cp -r /opt/nutanix-mcp/.refresh_backup/* /opt/nutanix-mcp/artifacts/
```

**Step 3 — Restart:**

```bash
sudo systemctl restart nutanix-mcp
sudo systemctl status nutanix-mcp
```

**Step 4 — Verify:**

```bash
sudo -u nutanix-mcp /opt/nutanix-mcp/.venv/bin/nutanix-mcp run --validate-only
```

Confirm `"artifact_mode"` is present and there are no error fields before handing control back to the AI client.
