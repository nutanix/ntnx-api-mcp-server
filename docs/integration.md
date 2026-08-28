# Integration — Nutanix V4 API MCP Server

Connect your AI client to the Nutanix V4 API MCP Server. Each section below is self-contained. Read only the section for your client.

> **Do not run `nutanix-mcp serve-stdio` manually** when using Cursor, Claude Desktop, or any other AI client configured with an `mcp.json` / `claude_desktop_config.json` entry. The client launches the server process automatically via that config. Running it separately creates a second process on the same stdio pipe and causes the client to fail with a duplicate-process or handshake error.
>
> Use `serve-stdio` manually **only** when debugging with MCP Inspector or building a custom client (see those sections below).

> New to MCP? See the [README](../README.md) for an overview of what this server does and how it works.

---

## Cursor

**Config file location:**
- macOS: `~/.cursor/mcp.json` (global) or `<workspace>/.cursor/mcp.json` (project-scoped)
- Windows: `%APPDATA%\Cursor\mcp.json`
- Linux: `~/.cursor/mcp.json`

Open the config file and add the `nutanix-v4-mcp` entry inside `"mcpServers"`. Create the file if it does not exist.

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "/absolute/path/.venv/bin/nutanix-mcp",
      "args": ["serve-stdio"],
      "env": {
        "PC_HOST": "10.1.1.10",
        "PC_PORT": "9440",
        "PC_USERNAME": "admin",
        "PC_PASSWORD": "your_password",
        "PC_INSECURE": "false",
        "ARTIFACTS_DIR": "/absolute/path/artifacts"
      }
    }
  }
}
```

Replace `/absolute/path/.venv/bin/nutanix-mcp` with the absolute path to the `nutanix-mcp` binary, and `/absolute/path/artifacts` with the absolute path to your artifacts directory. Both **must be absolute paths** — Cursor does not resolve relative paths from the config file location.

```bash
which nutanix-mcp   # prints the full binary path  (use for "command")
pwd                  # prints the project root      (append /artifacts for ARTIFACTS_DIR)
```

To authenticate with an API key instead of username/password, replace `PC_USERNAME` and `PC_PASSWORD` with a single `PC_API_KEY` key:

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "/absolute/path/.venv/bin/nutanix-mcp",
      "args": ["serve-stdio"],
      "env": {
        "PC_HOST": "10.1.1.10",
        "PC_PORT": "9440",
        "PC_API_KEY": "your-api-key",
        "PC_INSECURE": "false",
        "ARTIFACTS_DIR": "/absolute/path/artifacts"
      }
    }
  }
}
```

**Verification:**

1. Save the config file.
2. Open Cursor → **Settings** → **MCP** (or press `Cmd+Shift+P` and search "MCP").
3. The server list should show `nutanix-v4-mcp` with a green status indicator.
4. In any Composer or Chat session, the server name appears as **`nutanix-v4-mcp-server`** in the tool list. You should see tools including `listOperations`, `getOperationSchema`, `getCodeSample`, `getOperationPermissions`, and one `*_execute` tool per downloaded namespace (e.g. `prism_execute`, `lifecycle_execute`).
5. Ask the agent: _"List available Nutanix operations"_ — it should call `listOperations` and return results.

**Client-specific notes:**

- Cursor requires an **absolute path** for `command`. A relative path or bare `nutanix-mcp` will fail silently if the binary is not on Cursor's `PATH`.
- The project-scoped config (`<workspace>/.cursor/mcp.json`) takes precedence over the global config for that workspace. If the server appears twice, check both locations.
- After editing the config file, reload MCP servers from **Settings → MCP → Reload** rather than restarting Cursor entirely.
- Artifacts must be downloaded before Cursor launches the server. Run `nutanix-mcp init` in your terminal once before adding the config. If `ARTIFACTS_DIR` is empty, the server process starts but immediately exits with `RuntimeError: No YAML artifacts found`, and Cursor will show the server as disconnected.
- If the server fails to connect with a TLS error, set `PC_INSECURE` to `"true"` in the `env` block. This is required for Prism Central instances using self-signed certificates (common in lab deployments). See [TLS handshake error](#tls-handshake-error-on-startup) for details.

---

## Claude Desktop

**Config file location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: not applicable — Claude Desktop does not have a supported Linux release

Open the config file and add the `nutanix-v4-mcp` entry inside `"mcpServers"`. Create the file if it does not exist.

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "/absolute/path/.venv/bin/nutanix-mcp",
      "args": ["serve-stdio"],
      "env": {
        "PC_HOST": "10.1.1.10",
        "PC_PORT": "9440",
        "PC_USERNAME": "admin",
        "PC_PASSWORD": "your_password",
        "PC_INSECURE": "false",
        "ARTIFACTS_DIR": "/absolute/path/artifacts"
      }
    }
  }
}
```

To authenticate with an API key instead of username/password, replace `PC_USERNAME` and `PC_PASSWORD` with a single `PC_API_KEY` key:

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "/absolute/path/.venv/bin/nutanix-mcp",
      "args": ["serve-stdio"],
      "env": {
        "PC_HOST": "10.1.1.10",
        "PC_PORT": "9440",
        "PC_API_KEY": "your-api-key",
        "PC_INSECURE": "false",
        "ARTIFACTS_DIR": "/absolute/path/artifacts"
      }
    }
  }
}
```

**Verification:**

1. Save the config file.
2. **Exit completely and relaunch** Claude Desktop — it only reads the config on startup.
3. Open a new conversation. Click the **hammer icon** (tools) in the message composer.
4. The tool list should include `nutanix-v4-mcp-server` as a connected server with tools `listOperations`, `getOperationSchema`, `getCodeSample`, `getOperationPermissions`, and namespace executor tools (e.g. `prism_execute`).
5. Ask: _"List available Nutanix operations"_ — Claude should invoke `listOperations`.

**Client-specific notes:**

- Claude Desktop requires a **full restart** (exit completely, not just close the window) to pick up config changes. Reload is not available.
- On macOS, `~/Library/Application Support/` is hidden in Finder. Use `Cmd+Shift+G` in Finder or `open ~/Library/Application\ Support/Claude/` in Terminal.
- The `command` path must be absolute. If you installed into a system Python or pyenv environment, confirm the exact path with `which nutanix-mcp` while that environment is active.
- If the server fails to connect with a TLS error, set `PC_INSECURE` to `"true"` in the `env` block. Required for Prism Central instances using self-signed certificates. See [TLS handshake error](#tls-handshake-error-on-startup) for details.

---

## MCP Inspector

MCP Inspector is a browser-based debugging tool for MCP servers. It does not require a config file — the server is launched directly from the command line.

Run this command from the project root with your virtual environment activated:

```bash
npx @modelcontextprotocol/inspector .venv/bin/nutanix-mcp serve-stdio
```

Pass credentials as environment variables before the command:

```bash
PC_HOST=10.1.1.10 \
PC_USERNAME=admin \
PC_PASSWORD=Admin1234! \
PC_INSECURE=false \
npx @modelcontextprotocol/inspector .venv/bin/nutanix-mcp serve-stdio
```

**Verification:**

1. Inspector opens at `http://localhost:5173`.
2. The **Server** panel shows connection status. A green indicator means the stdio handshake completed.
3. Click **Tools** — you should see all registered tools: `listOperations`, `getOperationSchema`, `getCodeSample`, `getOperationPermissions`, and namespace executor tools.
4. Select `listOperations`, click **Run** with no arguments — results appear in the response panel.

---

## Human-in-the-Loop (HITL) confirmation

Many Nutanix write operations (create, update, delete, failover) are irreversible or have broad blast radius. It is strongly recommended to configure your AI client to pause and ask for explicit confirmation before executing any non-read operation.

### Cursor

Cursor's built-in HITL is controlled by the agent's **approval mode** setting. With approval mode enabled, Cursor asks the user to approve each tool call before it is executed.

To enable it globally, open Cursor Settings → **Agent** and set **Tool Approval Mode** to `"require approval"`.

Alternatively, instruct the agent in your system prompt or at the start of each session:

```
Before calling any Nutanix operation that creates, modifies, or deletes a resource
(any POST, PUT, PATCH, or DELETE), stop and ask me for confirmation. Show me the
exact parameters you intend to send and wait for my explicit "yes" before proceeding.
```

### Claude Desktop

Claude Desktop does not expose a built-in HITL toggle. Use a persistent system prompt in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "/absolute/path/.venv/bin/nutanix-mcp",
      "args": ["serve-stdio"],
      "env": { "..." : "..." }
    }
  },
  "systemPrompt": "Before calling any Nutanix MCP operation that creates, modifies, or deletes a resource (POST, PUT, PATCH, DELETE), always show me the operation name and parameters and wait for explicit confirmation before executing."
}
```

> **Note:** The `systemPrompt` key may not be present in all Claude Desktop versions. Consult the Claude Desktop release notes if it does not take effect.

### MCP tool annotations

All namespace executor tools (`vmm_execute`, `networking_execute`, etc.) carry standard [MCP tool annotations](https://modelcontextprotocol.io/specification/2025-11-25/server/tools):

- `readOnlyHint: false` — these tools can modify state
- `destructiveHint: true` — mutations may be irreversible
- `openWorldHint: true` — calls reach an external system (Prism Central)

MCP clients that surface these hints (Cursor, Claude Desktop, custom clients) will apply their native confirmation UX for write operations without requiring a custom system prompt. Consult your client's documentation for how it handles `destructiveHint`.

`READ_ONLY_MODE` defaults to `true` — the server rejects all non-GET operations server-side regardless of client behavior. To allow write operations, set `READ_ONLY_MODE=false` explicitly in your environment config.

---

## Custom API clients

For local client integrations, the server communicates over **stdio** (standard input / standard output). Containerized gateway deployments can use `nutanix-mcp serve-http`, which exposes MCP streamable HTTP for platforms such as NAI.

To call the server programmatically, launch it as a subprocess and communicate using the MCP stdio transport. The example below uses the Python `mcp` SDK:

```python
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="/absolute/path/.venv/bin/nutanix-mcp",
    args=["serve-stdio"],
    env={
        "PC_HOST": "10.1.1.10",
        "PC_USERNAME": "admin",
        "PC_PASSWORD": "your_password",
        "PC_INSECURE": "false",
    },
)

async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List all available operations
            result = await session.call_tool("listOperations", {})
            print(json.dumps(result.content[0].text, indent=2))

asyncio.run(main())
```

Install the SDK with `pip install mcp`. The `mcp` package is already a dependency of this server and will be present in the same virtual environment.

---

## Multi-cluster setup

Connecting to multiple Prism Central clusters simultaneously is not yet supported. Each server process is bound to a single `PC_HOST` value for its lifetime. Hot-reload of connection settings without restart is also not implemented.

Multi-cluster support is planned for a future release.

---

## Connection troubleshooting

### Server process exits immediately on client startup

**Symptom:** The AI client shows the server as disconnected immediately after attempting to connect; no tools appear.

**Cause:** No artifacts are present in `ARTIFACTS_DIR`. The server exits with `RuntimeError: No YAML artifacts found in runtime or bundled directories.`

**Fix:** Run `nutanix-mcp init` once before configuring the client. Confirm `ARTIFACTS_DIR` in the client config matches the directory where `init` wrote files.

---

### Tool calls return `execution_error` with a connection message

**Symptom:** Discovery tools (`listOperations`, etc.) work, but namespace executor tools return `{"ok": false, "error": {"code": "execution_error", "detail": "..."}}` mentioning a connection refused or timeout.

**Cause:** `PC_HOST` is unreachable from the machine running the server — firewall, VPN, or wrong IP.

**Fix:** Verify connectivity with `curl -k https://10.1.1.10:9440/api` from the same machine. Correct `PC_HOST` in the client config and restart the server.

---

### Tool calls return `execution_error` with HTTP 401 or 403

**Symptom:** The server starts and tools appear, but all `_execute` calls fail with an HTTP 401 or 403 error in the detail field.

**Cause:** Credentials in `PC_USERNAME`/`PC_PASSWORD` or `PC_API_KEY` are wrong or the account lacks permission.

**Fix:** Validate credentials by running `nutanix-mcp run --validate-only` in a terminal with the same environment variables set. If validation fails, update the credentials in the client config and restart the server. For permission requirements: [authentication and security guide](authentication.md).

---

### TLS handshake error on startup

**Symptom:** The startup probe fails with `TLS validation failed during startup probe. Check certificate trust or PC_INSECURE setting.`

**Cause:** `PC_INSECURE` is set to `false` and the Prism Central certificate is self-signed or issued by a CA not trusted by the system.

**Fix:** Set `PC_INSECURE=true` in the client config `env` block to disable certificate verification. For production environments, install the Prism Central CA certificate into the system trust store and keep `PC_INSECURE=false`. Custom CA bundle paths are not supported. Support for a configurable CA bundle path is planned for a future release.

---

### Server binary not found — client reports spawn error

**Symptom:** The client logs show a spawn or file-not-found error; the server never starts.

**Cause:** The `command` path in the config points to a non-existent location, or a relative path was used.

**Fix:** Use the absolute path to the `nutanix-mcp` binary. With your virtual environment activated, run `which nutanix-mcp` to get the exact path and paste it as the `command` value. On Windows, use `where nutanix-mcp` and ensure backslashes are escaped (`\\`) or use forward slashes in JSON.

---

More issues: [troubleshooting guide](troubleshooting.md).
