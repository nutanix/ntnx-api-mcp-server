# Nutanix V4 API MCP Server

> Expose Nutanix V4 APIs as tools callable by AI assistants — Claude, Cursor, and any MCP-compatible client.

[![Version](https://img.shields.io/badge/version-0.8-green.svg)](CHANGELOG.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

---

## What is this?

**MCP (Model Context Protocol)** is an open standard that lets AI assistants call external tools safely and predictably. This server implements MCP over stdio transport, exposing Nutanix V4 APIs as callable tools. The V4 APIs are Nutanix's modern, versioned REST APIs for managing Prism Central — Nutanix's centralised management plane for multi-cluster infrastructure.

Once connected, an AI assistant like Claude or Cursor can discover available Nutanix operations, inspect their schemas and required permissions, and execute them against your Prism Central cluster, all from natural language.

---

## Who should read what

| You are... | Start here |
|---|---|
| Evaluating whether this covers your use case | [Feature Spotlight](docs/feature-spotlight.md) — all 19 namespace profiles and example interactions |
| A developer getting started | [Quickstart guide](docs/quickstart.md) — install, configure, and first tool call |
| An IT security reviewer | [Authentication and security guide](docs/authentication.md) — credentials, permissions, network exposure, security hardening checklist |
| Returning after an update | [Changelog](CHANGELOG.md) — what changed and whether configuration needs updating |

---

## Supported API namespaces

The server exposes one `<namespace>_execute` tool per namespace. Namespaces are fetched from your Prism Central during `nutanix-mcp init` — only namespaces that your PC version supports will have artifacts downloaded and tools registered at runtime.

| Namespace | Executor tool | Coverage |
|---|---|---|
| `aiops` | `aiops_execute` | Analysis, reporting, capacity planning, VM rightsizing, simulations |
| `clustermgmt` | `clustermgmt_execute` | Hosts, clusters, bmc, cluster profiles, SSL certificates, storage containers |
| `datapolicies` | `datapolicies_execute` | Protection policies, Disaster recovery plans and storage policies |
| `dataprotection` | `dataprotection_execute` | Consistency groups, recovery points, protection and recovery plans actions |
| `files` | `files_execute` | Virtual file servers, shares, storage provisioning, security controls |
| `iam` | `iam_execute` | Users, roles, identity providers, service accounts (API keys) and access policies |
| `licensing` | `licensing_execute` | License management, compliance, and feature entitlements |
| `lifecycle` | `lifecycle_execute` | Infrastructure, software, and firmware upgrades |
| `microseg` | `microseg_execute` | Network security policies, service groups, address groups |
| `monitoring` | `monitoring_execute` | Alerts, alert policies, events, and audits |
| `multidomain` | `multidomain_execute` | Cross-domain services across on-prem, NC2, and edge |
| `networking` | `networking_execute` | AHV networking, advanced networking configuration like BGP, vSwitch, VPC and subnet management |
| `objects` | `objects_execute` | Nutanix Object Store service |
| `opsmgmt` | `opsmgmt_execute` | Shared platform functionality for aiops, devops, secops, finops |
| `prism` | `prism_execute` | Tasks, categories, batch operations, domain managers, backup targets, external storages |
| `security` | `security_execute` | Encryption, certificates, platform hardening |
| `storage` | `storage_execute` | Storage containers, volume groups, and iSCSI client management |
| `vmm` | `vmm_execute` | VM lifecycle on Nutanix clusters |
| `volumes` | `volumes_execute` | Volume group lifecycle with iSCSI and NVMe-TCP client attachment |

> **Note:** Not all namespaces listed above are available on every Prism Central deployment. Tool availability depends on your PC version and which V4 API namespaces it exposes. Run `nutanix-mcp init` with `PC_HOST` configured — only namespaces reported by your PC will be fetched and registered as tools.

---

## Prerequisites

- **Python 3.11 or higher**
- **Git** (to clone the repository)
- **Prism Central** access with one of:
  - Username + password (`PC_USERNAME` / `PC_PASSWORD`)
  - API key (`PC_API_KEY` via `X-ntnx-api-key` header)
- Prism Central reporting a V4 API (check: `https://<PC_HOST>:9440/api/prism/unversioned/info` returns `"data": "v4.x"`)

> No Docker required. The server runs as a local Python process over stdio.

---

## Quickstart

```bash
git clone https://github.com/nutanix/ntnx-api-mcp-server
cd ntnx-api-mcp-server
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
mv .env.example .env               # edit with your PC_HOST and credentials
nutanix-mcp init
nutanix-mcp run --validate-only
```

For a step-by-step walkthrough including client connection and your first tool call: [quickstart guide](docs/quickstart.md).

---

## Configuration

Settings are read from environment variables, a `.env` file in the project root, or a config file passed via `--config-file`. CLI flags take the highest precedence.

Key variables:

- `PC_HOST` — Prism Central IP or FQDN (required for live API execution)
- `PC_USERNAME` + `PC_PASSWORD` — basic auth credentials (use one auth method, not both)
- `PC_API_KEY` — API key sent as `X-ntnx-api-key` (alternative to username/password; takes priority if both are set)
- `PC_INSECURE=false` — enforces TLS verification by default; set to `true` only for dev/lab with self-signed certificates
- `READ_ONLY_MODE=true` — blocks all non-GET operations server-side (default; set to `false` to opt in to write operations)
- `ARTIFACTS_DIR` — **must be an absolute path** when set in AI client config files

For all configuration options, defaults, and validation behavior: [configuration reference](docs/configuration.md).

### Config file support

Pass `--config-file` to `run` or `serve-stdio` to load settings from a file. Supported formats: `.json`, `.yaml`/`.yml`, `.toml`.

---

## Commands

### `nutanix-mcp init`

Downloads API YAML artifacts for all discovered (or overridden) namespaces. Uses `pc_compatible` mode when `PC_HOST` is set, or `latest_release` mode from the Nutanix developer portal when it is not.

```bash
nutanix-mcp init
```

### `nutanix-mcp refresh [--force]`

Refreshes artifacts with backup/restore safety — existing artifacts are preserved if any namespace download fails.

```bash
nutanix-mcp refresh --force
```

### `nutanix-mcp run [--validate-only]`

Runs startup checks and prints artifact loading state. Use `--validate-only` to verify config without starting the server.

```bash
nutanix-mcp run --validate-only
```

### `nutanix-mcp serve-stdio`

Starts the MCP stdio server. AI clients (Cursor, Claude Desktop) invoke this automatically via their config file — you do not run it directly. Run it manually only when using MCP Inspector or a custom programmatic client.

```bash
nutanix-mcp serve-stdio
```

---

## Connecting to AI clients

The server communicates over **stdio**. Any MCP-compatible client that supports subprocess-based stdio transport can connect by pointing its config at the `nutanix-mcp serve-stdio` command with credentials passed as environment variables.

For step-by-step config for Cursor, Claude Desktop, MCP Inspector, and custom Python clients — including exact JSON blocks, absolute path requirements, and verification steps — see the [integration guide](docs/integration.md).

For a first-time walkthrough from install to first tool call: [quickstart guide](docs/quickstart.md).

---

## Tools reference

### Discovery tools

These 4 tools are always registered regardless of which namespace artifacts are present. They query an in-memory index and make no Nutanix API calls.

| Tool | Description |
|---|---|
| `listOperations` | List available operations, optionally filtered by `namespace` or `search` text. Supports `limit` and `offset` for pagination. |
| `getOperationSchema` | Get full schema details (parameters, path, method, description) for a specific `operation` id. |
| `getCodeSample` | Get a language-specific code sample for an `operation`, by `language` (e.g. `python`, `curl`). |
| `getOperationPermissions` | Get required roles and permissions metadata for a specific `operation` id. |

`getOperationSchema`, `getCodeSample`, and `getOperationPermissions` accept an
optional `namespace`, using the value returned by `listOperations`. If an operation
name appears in multiple namespaces, pass both fields, for example
`{"operation": "getDiskById", "namespace": "vmm"}`. Omitting `namespace` for an
ambiguous name returns `ambiguous_operation` and the matching namespaces. Unique
operation names continue to work without it.

### Namespace execution tools

Each namespace has a corresponding `<namespace>_execute` tool registered at startup from the downloaded YAML artifacts. Two parameters apply to every call:

| Parameter | Type | Description |
|---|---|---|
| `operation` | string (**required**) | The operation id to call |
| `request_body` | object | JSON body for POST / PUT / PATCH payloads — omit for GET / DELETE |

List and search operations additionally accept OData query parameters:

| Parameter | Type | Description |
|---|---|---|
| `_filter` | string | OData `$filter` expression (e.g., `name eq 'my-vm'`) — see [OData filter syntax](https://www.odata.org/documentation/) |
| `_limit` | integer | Max results to return (1–100) |
| `_page` | integer | Page offset (0-based) |
| `_orderby` | string | OData `$orderby` expression |
| `_select` | string | OData `$select` expression |
| `_expand` | string | OData `$expand` expression |

---

## Example prompts

### Discovery

```
List all operations in the prism namespace
```
```
What permissions do I need to run createConsistencyGroup?
```
```
Show me the schema for listTasks and give me a Python code sample
```

### Execution

```
List the first 5 tasks in Prism Central
```
```
Get the recovery plan job details for job ID <extId>
```
```
Before creating a consistency group, show me the required roles and request body schema, then ask me to confirm before executing
```
```
For a volume group cleanup workflow: find the relevant delete operations, show permissions for each, and only execute after I explicitly confirm each write call
```

---

## Logging

Each server restart creates a new timestamped log file in `LOG_DIR` (default: `./logs`):

```
logs/nutanix-mcp-20260517-181407-382850.log
```

Set `LOG_FORMAT=json` for structured JSON output suitable for log aggregation pipelines. For all logging options: [configuration reference](docs/configuration.md).

---

## Security notes

- **At least one auth method is required** — the server fails startup if neither `PC_API_KEY` nor `PC_USERNAME`/`PC_PASSWORD` is set when `PC_HOST` is configured.
- **TLS verification** is enforced by default (`PC_INSECURE=false`). Set `PC_INSECURE=true` only for dev or lab environments running Prism Central with self-signed certificates.
- **Secrets are never logged** — `PC_PASSWORD` and `PC_API_KEY` are stored as `SecretStr` and masked in all log output.
- **Input validation** — all tool call payloads are validated against the operation contract before execution. Unknown fields are rejected with a structured error.

For the full attack surface analysis, role requirements, and security hardening checklist: [authentication and security guide](docs/authentication.md).

---

## Author

Nutanix Developer Team

---

## Links

- [Feature Spotlight](docs/feature-spotlight.md)
- [Security and vulnerability reporting](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Nutanix V4 API Developer Portal](https://developers.nutanix.com)
- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector)

---

## Technical Preview Disclaimer

This repository is an open-source project. Please note the following before using it:

* **Non-Production Only:** This project is in a tech preview state. It is **not** designed, tested, or supported for production workloads.
* **Expect Changes:** As a preview, breaking changes may occur. We encourage you to experiment, test, and share your feedback in non-production environments!
