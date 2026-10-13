# Connecting hedgedoc-mcp to your agent

`hedgedoc-mcp` is a standard local (stdio) MCP server, so any agent that can launch
a local MCP server can use it. This page has a ready-to-paste config for each one.

- [What every client needs](#what-every-client-needs)
- [Keeping your password out of config files](#keeping-your-password-out-of-config-files)
- **Terminal agents:** [Claude Code](#claude-code) · [Codex CLI](#codex-cli) ·
  [Gemini CLI](#gemini-cli) · [GitHub Copilot CLI](#github-copilot-cli) ·
  [OpenCode](#opencode) · [Pi](#pi) · [Amp](#amp) · [Goose](#goose) ·
  [Crush](#crush) · [Hermes Agent](#hermes-agent) · [Factory Droid](#factory-droid) ·
  [Qwen Code](#qwen-code) · [Devin CLI](#devin-desktop-and-devin-cli)
- **Editors and IDEs:** [Cursor](#cursor) · [VS Code (Copilot)](#vs-code-github-copilot) ·
  [Devin Desktop (formerly Windsurf)](#devin-desktop-and-devin-cli) · [Zed](#zed) ·
  [JetBrains (AI Assistant, Junie)](#jetbrains-ides) · [Cline](#cline) ·
  [Kilo Code](#kilo-code) · [Continue](#continue) · [Kiro](#kiro)
- **Desktop apps:** [Claude Desktop](#claude-desktop) · [ChatGPT desktop](#chatgpt-desktop) ·
  [Warp](#warp) · [LM Studio](#lm-studio)
- [Clients that can't run local servers](#clients-that-cant-run-local-servers)
- [Testing with MCP Inspector](#testing-with-mcp-inspector)
- [Choosing and updating the version](#choosing-and-updating-the-version)
- [Troubleshooting](#troubleshooting)

Config formats change often. Each section links to the client's own docs; these
snippets were checked against them in October 2026. If one has drifted, please
open an issue or PR.

## What every client needs

| Setting | Value |
|---|---|
| Transport | stdio (sometimes called "local" or "command") |
| Command | `uvx` (from [uv](https://docs.astral.sh/uv/)) |
| Arguments | `hedgedoc-mcp` |
| Environment | `HEDGEDOC_URL`, plus `HEDGEDOC_EMAIL` + `HEDGEDOC_PASSWORD` and/or `HEDGEDOC_SESSION_COOKIE` (see the [README](../README.md#2-choose-your-credentials)) |

**Put the variables in the client's config, not just in your shell.** Most
clients start MCP servers with a minimal environment (`PATH`, `HOME`, and a few
others) plus whatever the server's `env` block lists. The official MCP SDKs, Codex,
Hermes, and GitHub Copilot CLI all work this way, so `export HEDGEDOC_URL=...` in
your shell profile is not enough.

**If the client says `uvx` can't be found**, use the absolute path from `which uvx`
(macOS/Linux) or `where uvx` (Windows) as the command. The uv installer puts it in
`~/.local/bin/uvx` by default. Apps launched from the Dock, Start menu, or a desktop
launcher often don't see your shell's `PATH`.

## Keeping your password out of config files

Most clients can read a value from your environment instead of storing it in the
config file. This matters most for project-level files (`.mcp.json`,
`.cursor/mcp.json`, …) that get committed. Each client uses its own syntax:

| Client | Reference syntax |
|---|---|
| Claude Code (`.mcp.json`), Pi, Amp, GitHub Copilot CLI, Factory Droid, Qwen Code, Hermes Agent, Kiro, Crush | `${HEDGEDOC_PASSWORD}` |
| Gemini CLI | `$HEDGEDOC_PASSWORD` or `${HEDGEDOC_PASSWORD}` |
| Cursor, VS Code (`.vscode/mcp.json`) | `${env:HEDGEDOC_PASSWORD}` |
| OpenCode, Kilo Code | `{env:HEDGEDOC_PASSWORD}` |
| Continue | `${{ secrets.HEDGEDOC_PASSWORD }}` |
| Codex CLI, ChatGPT desktop | list the name in `env_vars` to forward it |
| Goose | list the name in `env_keys` (resolved from env or the system keyring) |
| VS Code | `${input:...}` prompts once and stores the value securely |
| Zed, Cline, JetBrains, Claude Desktop | none: keep the value in the user-level config only |

The variable must be set in the environment the client runs in. For terminal
agents that's your shell; desktop apps may not see shell exports.

The examples below use a reference wherever the client supports one. To hardcode
a value instead, replace the reference with the literal string.

---

## Terminal agents

### Claude Code

```bash
claude mcp add hedgedoc --scope user \
  -e HEDGEDOC_URL=https://md.example.com \
  -e HEDGEDOC_EMAIL=you@example.com \
  -e HEDGEDOC_PASSWORD='your-password' \
  -- uvx hedgedoc-mcp
```

Put the server name **before** the `-e` flags: `-e` accepts several values, so a
name after it is read as another `KEY=value`. `--scope` is `local` (default: this
project, just you), `user` (all your projects), or `project` (writes `.mcp.json`
for your team). Check with `claude mcp list` or `/mcp` in a session.

To share it with your team, commit a `.mcp.json` at the repo root that references
each person's own credentials. A `${VAR:-default}` form is also supported:

```json
{
  "mcpServers": {
    "hedgedoc": {
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "${HEDGEDOC_URL:-https://md.example.com}",
        "HEDGEDOC_EMAIL": "${HEDGEDOC_EMAIL}",
        "HEDGEDOC_PASSWORD": "${HEDGEDOC_PASSWORD}"
      }
    }
  }
}
```

Claude Code asks each person to approve project servers the first time.
Docs: <https://code.claude.com/docs/en/mcp>

### Codex CLI

`~/.codex/config.toml` (or `.codex/config.toml` in a trusted project):

```toml
[mcp_servers.hedgedoc]
command = "uvx"
args = ["hedgedoc-mcp"]
env_vars = ["HEDGEDOC_EMAIL", "HEDGEDOC_PASSWORD"]  # forwarded from your environment

[mcp_servers.hedgedoc.env]
HEDGEDOC_URL = "https://md.example.com"
```

Or from the command line; this writes literal values to the global config:

```bash
codex mcp add hedgedoc --env HEDGEDOC_URL=https://md.example.com \
  --env HEDGEDOC_EMAIL=you@example.com --env HEDGEDOC_PASSWORD='your-password' \
  -- uvx hedgedoc-mcp
```

Codex does not pass your shell environment to servers: a variable reaches the
server only if it's in `env` or listed in `env_vars`.
Docs: <https://learn.chatgpt.com/docs/extend/mcp?surface=cli>

### Gemini CLI

`~/.gemini/settings.json` (user) or `.gemini/settings.json` (project):

```json
{
  "mcpServers": {
    "hedgedoc": {
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "$HEDGEDOC_EMAIL",
        "HEDGEDOC_PASSWORD": "$HEDGEDOC_PASSWORD"
      }
    }
  }
}
```

Or: `gemini mcp add -s user -e HEDGEDOC_URL=https://md.example.com -e 'HEDGEDOC_EMAIL=$HEDGEDOC_EMAIL' -e 'HEDGEDOC_PASSWORD=$HEDGEDOC_PASSWORD' hedgedoc uvx hedgedoc-mcp`

- `--scope` defaults to `project`, so pass `-s user` for a personal setup.
- Gemini removes inherited variables whose names contain `PASSWORD`, `TOKEN`,
  `SECRET`, and similar. `HEDGEDOC_PASSWORD` must therefore be listed in `env`, as
  above.
- `gemini mcp add -e` cuts the value at the first `=`. If your password contains
  `=`, edit `settings.json` directly.
- In folders you haven't trusted, project servers show as "Disconnected". Run
  `gemini trust` to fix that.

Docs: <https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md>

### GitHub Copilot CLI

```bash
copilot mcp add hedgedoc --env HEDGEDOC_URL=https://md.example.com \
  --env 'HEDGEDOC_EMAIL=${HEDGEDOC_EMAIL}' --env 'HEDGEDOC_PASSWORD=${HEDGEDOC_PASSWORD}' \
  -- uvx hedgedoc-mcp
```

This writes `~/.copilot/mcp-config.json`. For a project, use `.mcp.json` or
`.github/mcp.json`; these are loaded once you trust the folder.

```json
{
  "mcpServers": {
    "hedgedoc": {
      "type": "local",
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "${HEDGEDOC_EMAIL}",
        "HEDGEDOC_PASSWORD": "${HEDGEDOC_PASSWORD}"
      },
      "tools": ["*"]
    }
  }
}
```

Only `PATH` is inherited from your environment; everything else must be in `env`.
Docs: <https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers>

### OpenCode

`~/.config/opencode/opencode.json` (global) or `opencode.json` in the project root:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "hedgedoc": {
      "type": "local",
      "command": ["uvx", "hedgedoc-mcp"],
      "enabled": true,
      "environment": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "{env:HEDGEDOC_EMAIL}",
        "HEDGEDOC_PASSWORD": "{env:HEDGEDOC_PASSWORD}"
      }
    }
  }
}
```

OpenCode's format differs from most clients:
- `command` is one array that includes the arguments.
- The env key is `environment`.
- `type: "local"` is required.

`opencode mcp add` is an interactive wizard.
Docs: <https://opencode.ai/docs/mcp-servers>

### Pi

Pi has built-in MCP support since v0.99 (package `@earendil-works/pi-coding-agent`).
You no longer need an adapter extension.

```bash
pi mcp add hedgedoc --env HEDGEDOC_URL=https://md.example.com \
  --env 'HEDGEDOC_EMAIL=${HEDGEDOC_EMAIL}' --env 'HEDGEDOC_PASSWORD=${HEDGEDOC_PASSWORD}' \
  -- uvx hedgedoc-mcp
```

This writes `~/.pi/agent/mcp.json`. Add `--local` to write the project file
`.pi/mcp.json` instead; Pi reads it once you trust the project. The file format is:

```json
{
  "mcpServers": {
    "hedgedoc": {
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "${HEDGEDOC_EMAIL}",
        "HEDGEDOC_PASSWORD": "${HEDGEDOC_PASSWORD}"
      }
    }
  }
}
```

- Run `pi mcp list` to check the connection, and `/reload` in a running session.
- `env` values can also be `!command`, e.g. `"!op read op://vault/hedgedoc/password"`.
- By default Pi exposes MCP tools through its `codemode` tool. Add
  `"exposure": "direct"` to the server entry to expose `hedgedoc_*` as regular tools.

Docs: [`packages/coding-agent/docs/mcp.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md)

### Amp

```bash
amp mcp add hedgedoc --env HEDGEDOC_URL=https://md.example.com \
  --env 'HEDGEDOC_EMAIL=${HEDGEDOC_EMAIL}' --env 'HEDGEDOC_PASSWORD=${HEDGEDOC_PASSWORD}' \
  -- uvx hedgedoc-mcp
```

This writes `~/.config/amp/settings.json`. Add `--workspace` to use
`.amp/settings.json`; workspace servers then need `amp mcp approve hedgedoc`.
Note the dotted key:

```json
{
  "amp.mcpServers": {
    "hedgedoc": {
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "${HEDGEDOC_EMAIL}",
        "HEDGEDOC_PASSWORD": "${HEDGEDOC_PASSWORD}"
      }
    }
  }
}
```

`amp mcp doctor` diagnoses connection problems.
Docs: <https://ampcode.com/docs/customize/mcp>

### Goose

Run `goose configure` → **Add Extension** → **Command-line Extension**. Use the name
`hedgedoc` and the command `uvx hedgedoc-mcp`, and add the three variables when
asked. Goose stores the values in your system keyring. To edit
`~/.config/goose/config.yaml` (Windows: `%APPDATA%\Block\goose\config\config.yaml`)
by hand instead:

```yaml
extensions:
  hedgedoc:
    name: hedgedoc
    type: stdio
    enabled: true
    cmd: uvx
    args: ["hedgedoc-mcp"]
    envs:
      HEDGEDOC_URL: "https://md.example.com"
    env_keys: ["HEDGEDOC_EMAIL", "HEDGEDOC_PASSWORD"]  # from your env or the keyring
    timeout: 300
```

Goose uses `cmd` and `envs` where other clients use `command` and `env`.
Docs: <https://goose-docs.ai>

### Crush

Crush's preferred config is a `crushrc` script (`~/.config/crush/crushrc`, or
`.crushrc` in the project). The `--env` flag takes the key and value as two
arguments, not `KEY=VALUE`:

```bash
mcp add hedgedoc --command uvx --args hedgedoc-mcp \
  --env HEDGEDOC_URL https://md.example.com \
  --env HEDGEDOC_EMAIL "${HEDGEDOC_EMAIL:?set HEDGEDOC_EMAIL}" \
  --env HEDGEDOC_PASSWORD "${HEDGEDOC_PASSWORD:?set HEDGEDOC_PASSWORD}"
```

The older `crush.json` format still works:

```json
{
  "$schema": "https://charm.land/crush.json",
  "mcp": {
    "hedgedoc": {
      "type": "stdio",
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "$HEDGEDOC_EMAIL",
        "HEDGEDOC_PASSWORD": "$HEDGEDOC_PASSWORD"
      }
    }
  }
}
```

Docs: <https://github.com/charmbracelet/crush>

### Hermes Agent

`~/.hermes/config.yaml`. Hermes also loads `${VAR}` values from `~/.hermes/.env`,
which is a good place for the password:

```yaml
mcp_servers:
  hedgedoc:
    command: uvx
    args: ["hedgedoc-mcp"]
    env:
      HEDGEDOC_URL: "https://md.example.com"
      HEDGEDOC_EMAIL: "${HEDGEDOC_EMAIL}"
      HEDGEDOC_PASSWORD: "${HEDGEDOC_PASSWORD}"
    enabled: true
```

You can also use `hermes mcp add hedgedoc --command uvx --env HEDGEDOC_URL=https://md.example.com --args hedgedoc-mcp`.
`--env` accepts several `KEY=VALUE` pairs, and `--args` must come last.
Hermes connects to the server first, then asks which tools to enable.
Run `/reload-mcp` in a session after editing.
Docs: <https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp>

### Factory Droid

`~/.factory/mcp.json` (user) or `.factory/mcp.json` (project):

```json
{
  "mcpServers": {
    "hedgedoc": {
      "type": "stdio",
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "${HEDGEDOC_EMAIL}",
        "HEDGEDOC_PASSWORD": "${HEDGEDOC_PASSWORD}"
      }
    }
  }
}
```

Or: `droid mcp add hedgedoc "uvx hedgedoc-mcp" --type stdio --env HEDGEDOC_URL=https://md.example.com --env 'HEDGEDOC_EMAIL=${HEDGEDOC_EMAIL}' --env 'HEDGEDOC_PASSWORD=${HEDGEDOC_PASSWORD}'`

An unset `${VAR}` makes the connection fail with an error naming the variable.
Docs: <https://docs.factory.com/cli/configuration/mcp>

### Qwen Code

`~/.qwen/settings.json` (user) or `.qwen/settings.json` (project). The format is the
same as Gemini CLI, and env values accept `$VAR` or `${VAR}`. The command line puts
flags before the name:

```bash
qwen mcp add -e HEDGEDOC_URL=https://md.example.com \
  -e 'HEDGEDOC_EMAIL=${HEDGEDOC_EMAIL}' -e 'HEDGEDOC_PASSWORD=${HEDGEDOC_PASSWORD}' \
  hedgedoc uvx hedgedoc-mcp
```

Restart Qwen Code after adding a server.
Docs: <https://qwenlm.github.io/qwen-code-docs/en/users/features/mcp/>

---

## Editors and IDEs

### Cursor

`~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (this project):

```json
{
  "mcpServers": {
    "hedgedoc": {
      "type": "stdio",
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "${env:HEDGEDOC_EMAIL}",
        "HEDGEDOC_PASSWORD": "${env:HEDGEDOC_PASSWORD}"
      }
    }
  }
}
```

Instead of `env`, you can use `"envFile": "${workspaceFolder}/.env"`. Make sure
that `.env` is gitignored. Server logs are in the Output panel under **MCP Logs**.
Docs: <https://cursor.com/docs/context/mcp>

### VS Code (GitHub Copilot)

Add it from the command line. This writes your user profile; the single quotes stop
your shell from expanding `${...}`:

```bash
code --add-mcp '{"name":"hedgedoc","type":"stdio","command":"uvx","args":["hedgedoc-mcp"],"env":{"HEDGEDOC_URL":"https://md.example.com","HEDGEDOC_EMAIL":"${env:HEDGEDOC_EMAIL}","HEDGEDOC_PASSWORD":"${env:HEDGEDOC_PASSWORD}"}}'
```

For a workspace, `.vscode/mcp.json` can prompt for the credentials once and store
them securely. Note the top-level key is `servers`, not `mcpServers`:

```json
{
  "inputs": [
    { "type": "promptString", "id": "hedgedoc-email", "description": "HedgeDoc email" },
    { "type": "promptString", "id": "hedgedoc-password", "description": "HedgeDoc password", "password": true }
  ],
  "servers": {
    "hedgedoc": {
      "type": "stdio",
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "${input:hedgedoc-email}",
        "HEDGEDOC_PASSWORD": "${input:hedgedoc-password}"
      }
    }
  }
}
```

Recent VS Code versions also read the portable `.mcp.json` format shown under
[GitHub Copilot CLI](#github-copilot-cli). Use that format if you want one file
for both. It uses `${VAR}` references; `${input:...}`, `${env:...}`, and
`envFile` don't work there.

Servers that use `${input:...}` aren't available to sessions run by VS Code's
Agent Host. Workspace servers are disabled in Restricted Mode.
Docs: <https://code.visualstudio.com/docs/copilot/customization/mcp-servers>

### Devin Desktop and Devin CLI

Windsurf was renamed **Devin Desktop** in June 2026. Its default agent (Devin
Local) and the Devin CLI share one config:

```bash
devin mcp add -s user -e HEDGEDOC_URL=https://md.example.com \
  -e HEDGEDOC_EMAIL=you@example.com -e HEDGEDOC_PASSWORD='your-password' \
  hedgedoc -- uvx hedgedoc-mcp
```

This writes `~/.config/devin/mcp_config.json` (Windows:
`%APPDATA%\devin\mcp_config.json`) in the usual `mcpServers` format. For a
project, keep credentials in the gitignored `.devin/mcp_config.local.json`, not in
the shared `.devin/mcp_config.json`. The legacy Cascade agent also supports
`${env:VAR}` references.
Docs: <https://docs.devin.ai/cli/extensibility/mcp/configuration>

### Zed

Settings → AI → MCP Servers → **Add Server**, or edit `~/.config/zed/settings.json`
(Windows: `%APPDATA%\Zed\settings.json`):

```json
{
  "context_servers": {
    "hedgedoc": {
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "you@example.com",
        "HEDGEDOC_PASSWORD": "your-password"
      }
    }
  }
}
```

Zed doesn't expand variable references. Keep credentials in your user settings, not
in `.zed/settings.json`. Older guides show a `"source": "custom"` field or a nested
`command` object; neither is needed now.
Docs: <https://zed.dev/docs/ai/mcp>

### JetBrains IDEs

- **AI Assistant:** Settings → Tools → AI Assistant → Model Context Protocol (MCP)
  → **Add**. Paste the JSON below and choose global or project level. **Import from
  Claude** copies servers from Claude Desktop.
- **Junie** (IDE plugin and CLI): `~/.junie/mcp/mcp.json` (user) or
  `.junie/mcp/mcp.json` (project).

```json
{
  "mcpServers": {
    "hedgedoc": {
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "you@example.com",
        "HEDGEDOC_PASSWORD": "your-password"
      }
    }
  }
}
```

Neither expands variable references, so don't commit credentials in the project
file. MCP logs are under Help → Show Log, in the `mcp` folder.
Docs: <https://www.jetbrains.com/help/ai-assistant/mcp.html>,
<https://junie.jetbrains.com/docs/junie-plugin-mcp-settings.html>

### Cline

Cline's VS Code, JetBrains, and CLI versions all share
`~/.cline/data/settings/cline_mcp_settings.json`. Open it from Cline's MCP Servers
panel:

```json
{
  "mcpServers": {
    "hedgedoc": {
      "type": "stdio",
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "you@example.com",
        "HEDGEDOC_PASSWORD": "your-password"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

There is no project-level file and no variable expansion. Add read-only tools such as
`"hedgedoc_read_note"` to `autoApprove` to skip their confirmation prompts.
Docs: <https://docs.cline.bot/mcp/configuring-mcp-servers>

Roo Code shut down in May 2026. Its users can move to Cline, or to Kilo Code below.

### Kilo Code

Kilo Code now uses the same format as OpenCode, in `~/.config/kilo/kilo.jsonc` (or
`kilo.json`). Its VS Code extension and the `kilo` CLI share this file:

```json
{
  "mcp": {
    "hedgedoc": {
      "type": "local",
      "command": ["uvx", "hedgedoc-mcp"],
      "environment": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "{env:HEDGEDOC_EMAIL}",
        "HEDGEDOC_PASSWORD": "{env:HEDGEDOC_PASSWORD}"
      },
      "enabled": true
    }
  }
}
```

`{env:...}` references are only allowed in the global file; project configs reject
them. Older `mcp_settings.json` files are migrated automatically.
Docs: <https://kilo.ai/docs/features/mcp/using-mcp-in-kilo-code>

### Continue

Add a block file such as `.continue/mcpServers/hedgedoc.yaml`, or put the list item
under `mcpServers:` in `~/.continue/config.yaml`:

```yaml
name: HedgeDoc MCP
version: 0.0.1
schema: v1
mcpServers:
  - name: hedgedoc
    type: stdio
    command: uvx
    args:
      - hedgedoc-mcp
    env:
      HEDGEDOC_URL: https://md.example.com
      HEDGEDOC_EMAIL: ${{ secrets.HEDGEDOC_EMAIL }}
      HEDGEDOC_PASSWORD: ${{ secrets.HEDGEDOC_PASSWORD }}
```

Continue reads secrets from `~/.continue/.env`, a workspace `.continue/.env`, or a
workspace `.env`. Editor extensions can't see variables exported in your shell. MCP
tools are available only in agent mode.
Docs: <https://docs.continue.dev/customize/deep-dives/mcp>

### Kiro

`~/.kiro/settings/mcp.json` (user) or `.kiro/settings/mcp.json` (workspace):

```json
{
  "mcpServers": {
    "hedgedoc": {
      "command": "uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "${HEDGEDOC_EMAIL}",
        "HEDGEDOC_PASSWORD": "${HEDGEDOC_PASSWORD}"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

The Kiro IDE only expands variables you've approved, either through the warning
prompt or the **Mcp Approved Env Vars** setting. Saving the file reloads the server.
Docs: <https://kiro.dev/docs/mcp/configuration>

---

## Desktop apps

### Claude Desktop

Settings → Developer → **Edit Config** opens `claude_desktop_config.json`. That's
`~/Library/Application Support/Claude/` on macOS and `%APPDATA%\Claude\` on
Windows. Use the absolute path to `uvx` (from `which uvx`), because the app doesn't
see your shell's `PATH`:

```json
{
  "mcpServers": {
    "hedgedoc": {
      "command": "/Users/you/.local/bin/uvx",
      "args": ["hedgedoc-mcp"],
      "env": {
        "HEDGEDOC_URL": "https://md.example.com",
        "HEDGEDOC_EMAIL": "you@example.com",
        "HEDGEDOC_PASSWORD": "your-password"
      }
    }
  }
}
```

Fully quit and reopen the app after editing; closing the window isn't enough. Logs
are in `~/Library/Logs/Claude/mcp-server-hedgedoc.log` on macOS and
`%APPDATA%\Claude\logs` on Windows.
Docs: <https://modelcontextprotocol.io/docs/develop/connect-local-servers>

### ChatGPT desktop

The ChatGPT desktop app, Codex CLI, and the Codex IDE extension share
`~/.codex/config.toml`. Use the [Codex CLI](#codex-cli) config, or add it as a
STDIO server in the app's MCP settings.
Docs: <https://learn.chatgpt.com/docs/extend/mcp>

### Warp

Settings → Agents → MCP servers → **+ Add**, then paste the `mcpServers` JSON from
[Claude Desktop](#claude-desktop) with `"command": "uvx"`. Warp can also pick up
servers you've already configured for Claude Code or Codex. Enable **Auto-spawn
servers from third-party agents** for that.
Docs: <https://docs.warp.dev/agents/capabilities/mcp>

### LM Studio

Requires LM Studio 0.3.17 or later. Program tab → Install → **Edit mcp.json**, then
add the `mcpServers` entry from [Claude Desktop](#claude-desktop). LM Studio uses
Cursor's `mcp.json` format. Tool calls ask for confirmation.
Docs: <https://lmstudio.ai/docs/app/mcp>

---

## Clients that can't run local servers

claude.ai on the web and mobile, Claude Cowork, and ChatGPT on the web connect to
MCP servers from the vendor's cloud. They can't start a program on your machine. To
use hedgedoc-mcp there, you'd need to run it behind an HTTP bridge or tunnel that
the service can reach. That's outside this project's scope, and the bridge would be
exposed to the internet.

## Testing with MCP Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) checks the
server outside any agent. That's useful to tell a config problem from a client
problem. It needs Node.js:

```bash
# Interactive web UI
npx @modelcontextprotocol/inspector \
  -e HEDGEDOC_URL=https://md.example.com \
  -e HEDGEDOC_EMAIL=you@example.com -e HEDGEDOC_PASSWORD='your-password' \
  uvx hedgedoc-mcp

# One-shot check from the terminal: should print your HedgeDoc profile
npx @modelcontextprotocol/inspector --cli uvx hedgedoc-mcp \
  -e HEDGEDOC_URL=https://md.example.com \
  -e HEDGEDOC_EMAIL=you@example.com -e HEDGEDOC_PASSWORD='your-password' \
  --method tools/call --tool-name hedgedoc_whoami
```

In `--cli` mode the server command comes first, then `-e` and the other flags.

## Choosing and updating the version

`uvx` caches the packages it downloads, so with plain `hedgedoc-mcp` in your
arguments you may keep getting a previously cached version. To control which
version runs, change the arguments:

| Arguments | Behavior |
|---|---|
| `["hedgedoc-mcp"]` | Latest version, but may reuse a cached copy |
| `["hedgedoc-mcp@latest"]` | Checks PyPI for the newest version on each start |
| `["hedgedoc-mcp@0.2.0"]` | Exactly that version, for reproducible setups (change the number to upgrade) |

To force a fresh download, run `uv cache clean hedgedoc-mcp` and restart your
agent. If you installed it with `uv tool install` and point the client at the
`hedgedoc-mcp` executable, `uvx` isn't involved: upgrade with
`uv tool upgrade hedgedoc-mcp`.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `HEDGEDOC_URL is not set` or `No credentials available` | The client isn't passing the variables. Put them in the server's `env` block, or use the client's reference syntax ([above](#keeping-your-password-out-of-config-files)). Exporting them in your shell usually isn't enough. |
| `uvx: command not found`, `spawn uvx ENOENT`, or the server never starts | The client can't find `uvx`. Use the absolute path from `which uvx` as the command. |
| `Login failed. Check that the credentials are correct...` | Wrong email/password, or email login is disabled on the instance (`CMD_EMAIL=true`). The password reaches the server exactly as written in the config; check for quoting problems and stray spaces. |
| `...redirected to its home page, which means the session is missing or expired` | Only a session cookie is set and it expired. Run `hedgedoc-mcp-login` again, or also set `HEDGEDOC_EMAIL`/`HEDGEDOC_PASSWORD` so the server can log in again automatically. |
| `unexpected redirect to '...'. Check that HEDGEDOC_URL matches...` | `HEDGEDOC_URL` differs from the instance's configured URL, for example `http://` vs `https://`. Copy the URL from your browser's address bar. |
| `Could not create note with alias ...: forbidden` | Custom aliases need `CMD_ALLOW_FREEURL=true` on the HedgeDoc server. Omit `alias` to get a random ID. |
| `hedgedoc_*` tools don't appear | Restart or reload the agent. Project-level configs often need approval or folder trust first (Claude Code, Gemini CLI, Copilot CLI, Pi, Amp, VS Code). |
| Behavior doesn't match the latest release | `uvx` is running a cached older version; see [Choosing and updating the version](#choosing-and-updating-the-version). |

If you're stuck, run the [Inspector check](#testing-with-mcp-inspector) with the same
values. If that works, the problem is in the agent's config.
