# hedgedoc-mcp

An [MCP](https://modelcontextprotocol.io) server that lets AI agents — Claude Code, Codex, Cursor, VS Code, OpenCode, Pi, or [any other MCP client](docs/CLIENTS.md) — read and write notes on a **self-hosted HedgeDoc 1.x** instance.

HedgeDoc 1.x has no API token system, so this server handles the real auth model (session cookies from email/password login) and exposes it as a clean, agent-friendly toolset.

---

## Why this exists

[HedgeDoc](https://hedgedoc.org) is a great self-hosted, open-source, collaborative markdown editor. But if you want an AI agent to write notes to it programmatically, you hit a wall immediately: **HedgeDoc 1.x has no API tokens.** Every write endpoint (`POST /new`, etc.) requires an authenticated browser-style session, tracked via the Express session cookie configured by the instance (normally `connect.sid`).

This project does the unglamorous work of handling that correctly — login, cookie storage, automatic re-authentication on expiry — and wraps it in an MCP server so any agent can just call `hedgedoc_create_note` and not think about any of it.

## Features

- 🔐 **Handles HedgeDoc 1.x's real auth model** (session cookies, not tokens)
- 🔁 **Auto re-login on session expiry** — no manual cookie refresh needed
- 🛠️ **5 MCP tools**: create, read, info, whoami, history
- 🐍 **Standalone Python client** (`hedgedoc_mcp.client.HedgeDocClient`) usable outside MCP too
- ✅ **Fully tested** — against an in-process fake HedgeDoc server; no live instance required
- 📦 **Works with any MCP client** — [setup guides for 20+ agents](docs/CLIENTS.md): Claude Code, Codex, Cursor, VS Code, OpenCode, Pi, Gemini CLI, Goose, Zed, and more

## Quick start

### 1. Install uv

Your agent starts the server for you with [`uvx`](https://docs.astral.sh/uv/guides/tools/), which downloads and caches `hedgedoc-mcp` from PyPI on first use. You only need [uv installed](https://docs.astral.sh/uv/getting-started/installation/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # macOS / Linux
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

You don't run `uvx hedgedoc-mcp` yourself: it's a stdio server, so it just waits for an agent to talk to it.

<details>
<summary>Other ways to install</summary>

```bash
uv tool install hedgedoc-mcp     # persistent install; point your agent at the `hedgedoc-mcp` executable
pip install hedgedoc-mcp          # into an existing environment

# Unreleased changes from the main branch:
uvx --from git+https://github.com/mrsunglasses-experiments/hedgedoc-mcp hedgedoc-mcp
```

</details>

### 2. Choose your credentials

The server is configured entirely through environment variables:

| Variable | Required | Description |
|---|---|---|
| `HEDGEDOC_URL` | Yes | Your instance's URL as shown in the browser, e.g. `https://md.example.com` |
| `HEDGEDOC_EMAIL` + `HEDGEDOC_PASSWORD` | One of these two options | Email/password login. The server logs in on first use and again whenever the session expires. |
| `HEDGEDOC_SESSION_COOKIE` | One of these two options | A session cookie from `hedgedoc-mcp-login` (below). Saves a login round-trip; when it expires, the server falls back to email/password if those are set. |
| `HEDGEDOC_SESSION_COOKIE_NAME` | No | Only if your instance uses a session cookie name other than `connect.sid` |

**Recommended:** set `HEDGEDOC_EMAIL` and `HEDGEDOC_PASSWORD`. That's all you need, and you never have to refresh anything. Email login must be enabled on the instance (`CMD_EMAIL=true`, the default).

**Set these in your agent's MCP config (step 3), not just in your shell.** Most agents start MCP servers with a minimal environment, so variables you `export` usually don't reach the server.

<details>
<summary>Optional: get a session cookie with <code>hedgedoc-mcp-login</code></summary>

```bash
uvx --from hedgedoc-mcp hedgedoc-mcp-login --url https://md.example.com --email you@example.com
```

It prompts for your password (or reads `HEDGEDOC_PASSWORD`; avoid `--password`, which lands in your shell history) and prints `HEDGEDOC_SESSION_COOKIE=...` for your agent's config. With `--write-env .env`, it also saves the value to a file readable only by you. The server doesn't read `.env` files itself.

</details>

### 3. Connect your agent

For **Claude Code**:

```bash
claude mcp add hedgedoc --scope user \
  -e HEDGEDOC_URL=https://md.example.com \
  -e HEDGEDOC_EMAIL=you@example.com \
  -e HEDGEDOC_PASSWORD='your-password' \
  -- uvx hedgedoc-mcp
```

Most other agents take the same three pieces of information: command `uvx`, argument `hedgedoc-mcp`, and the environment variables above. Config files and formats differ, though. **[docs/CLIENTS.md](docs/CLIENTS.md)** has a ready-to-paste config for each of these clients:

| | |
|---|---|
| **Terminal agents** | [Claude Code](docs/CLIENTS.md#claude-code) · [Codex CLI](docs/CLIENTS.md#codex-cli) · [Gemini CLI](docs/CLIENTS.md#gemini-cli) · [GitHub Copilot CLI](docs/CLIENTS.md#github-copilot-cli) · [OpenCode](docs/CLIENTS.md#opencode) · [Pi](docs/CLIENTS.md#pi) · [Amp](docs/CLIENTS.md#amp) · [Goose](docs/CLIENTS.md#goose) · [Crush](docs/CLIENTS.md#crush) · [Hermes Agent](docs/CLIENTS.md#hermes-agent) · [Factory Droid](docs/CLIENTS.md#factory-droid) · [Qwen Code](docs/CLIENTS.md#qwen-code) · [Devin CLI](docs/CLIENTS.md#devin-desktop-and-devin-cli) |
| **Editors and IDEs** | [Cursor](docs/CLIENTS.md#cursor) · [VS Code (Copilot)](docs/CLIENTS.md#vs-code-github-copilot) · [Devin Desktop (Windsurf)](docs/CLIENTS.md#devin-desktop-and-devin-cli) · [Zed](docs/CLIENTS.md#zed) · [JetBrains](docs/CLIENTS.md#jetbrains-ides) · [Cline](docs/CLIENTS.md#cline) · [Kilo Code](docs/CLIENTS.md#kilo-code) · [Continue](docs/CLIENTS.md#continue) · [Kiro](docs/CLIENTS.md#kiro) |
| **Desktop apps** | [Claude Desktop](docs/CLIENTS.md#claude-desktop) · [ChatGPT desktop](docs/CLIENTS.md#chatgpt-desktop) · [Warp](docs/CLIENTS.md#warp) · [LM Studio](docs/CLIENTS.md#lm-studio) |

The guide also covers keeping passwords out of config files that get committed, plus [troubleshooting](docs/CLIENTS.md#troubleshooting).

### 4. Try it

Ask your agent something like *"Create a HedgeDoc note summarizing this conversation"* or *"Which HedgeDoc account are you logged in as?"*. If the tools don't show up, check the setup with [MCP Inspector](docs/CLIENTS.md#testing-with-mcp-inspector), which runs the server outside any agent.

## Available tools

| Tool | Description |
|---|---|
| `hedgedoc_create_note` | Create a new note (optionally with a custom URL alias). Returns the note ID and URL. |
| `hedgedoc_read_note` | Fetch a note's raw markdown content by ID or alias. |
| `hedgedoc_note_info` | Get a note's title, description, view count, and timestamps. |
| `hedgedoc_whoami` | Verify the session is valid and show the logged-in user. |
| `hedgedoc_list_history` | List the logged-in user's recently viewed/pinned notes. |

There is no update tool: HedgeDoc 1.x has no HTTP endpoint for editing a note (see [Known limitations](#known-limitations)), so write a note's full content when creating it.

## Using the Python client directly

You don't need MCP to use this — the underlying client is a normal Python class:

```python
from hedgedoc_mcp.client import HedgeDocClient

client = HedgeDocClient("https://md.example.com")
client.login(email="you@example.com", password="your-password")

result = client.create_note("# Research notes\n\nSome findings...")
print(result.url)

content = client.read_note(result.note_id)
info = client.note_info(result.note_id)
```

## Known limitations

HedgeDoc 1.x's HTTP API is genuinely limited compared to newer forks — see [docs/LIMITATIONS.md](docs/LIMITATIONS.md) for the full rundown, including:

- No API tokens (session-cookie auth only)
- No HTTP note-update endpoint
- No delete endpoint over HTTP

These are constraints of the HedgeDoc 1.x server itself, not this client — the docs explain the workarounds this project uses and what genuinely isn't possible.

## Development

```bash
git clone https://github.com/mrsunglasses-experiments/hedgedoc-mcp.git
cd hedgedoc-mcp
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

pytest                 # run tests (against an in-process fake HedgeDoc; no live server needed)
ruff check .            # lint
ruff format --check .   # formatting
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the auth flow and MCP layer fit together, and [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

MIT — see [LICENSE](LICENSE).
