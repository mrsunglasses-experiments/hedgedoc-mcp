# hedgedoc-mcp

An [MCP](https://modelcontextprotocol.io) server that lets AI agents — Claude Code, Codex, Hermes, or any MCP-compatible client — read and write notes on a **self-hosted HedgeDoc 1.x** instance.

HedgeDoc 1.x has no API token system, so this server handles the real auth model (session cookies from email/password login) and exposes it as a clean, agent-friendly toolset.

---

## Why this exists

[HedgeDoc](https://hedgedoc.org) is a great self-hosted, open-source, collaborative markdown editor. But if you want an AI agent to write notes to it programmatically, you hit a wall immediately: **HedgeDoc 1.x has no API tokens.** Every write endpoint (`POST /new`, etc.) requires an authenticated browser-style session, tracked via the Express session cookie configured by the instance (normally `connect.sid`).

This project does the unglamorous work of handling that correctly — login, cookie storage, automatic re-authentication on expiry — and wraps it in an MCP server so any agent can just call `hedgedoc_create_note` and not think about any of it.

## Features

- 🔐 **Handles HedgeDoc 1.x's real auth model** (session cookies, not tokens)
- 🔁 **Auto re-login on session expiry** — no manual cookie refresh needed
- 🛠️ **6 MCP tools**: create, read, update (reported as unsupported), info, whoami, history
- 🐍 **Standalone Python client** (`hedgedoc_mcp.client.HedgeDocClient`) usable outside MCP too
- ✅ **Fully tested** — mocked HTTP, no live server required to run the test suite
- 📦 **Works with any MCP client**: Claude Code, Codex, Hermes, Cursor, custom clients

## Quick start

### 1. Install

**With [uv](https://docs.astral.sh/uv/) (recommended — no venv management needed):**

```bash
# Run directly without installing (uvx downloads + caches automatically)
uvx hedgedoc-mcp

# Or install as a persistent tool
uv tool install hedgedoc-mcp
```

> **Not yet on PyPI?** Run straight from GitHub instead — same zero-install experience:
> ```bash
> uvx --from git+https://github.com/mrsunglasses-experiments/hedgedoc-mcp hedgedoc-mcp
> ```
> Use this exact form in the agent config examples below (as `args`) until the package is published.

**With pip:**

```bash
pip install hedgedoc-mcp
```

**From source:**

```bash
git clone https://github.com/mrsunglasses-experiments/hedgedoc-mcp.git
cd hedgedoc-mcp
uv pip install -e .          # or: pip install -e .
```

### 2. Get a session cookie

HedgeDoc 1.x has no API tokens, so you authenticate once via the login endpoint and reuse the resulting session cookie:

```bash
hedgedoc-mcp-login --url https://md.example.com \
  --email you@example.com --password 'your-password' \
  --write-env .env
```

This prints (and optionally saves) `HEDGEDOC_SESSION_COOKIE=...`.

Alternatively, set `HEDGEDOC_EMAIL` + `HEDGEDOC_PASSWORD` directly and the server will log in automatically on first use, re-authenticating whenever the session expires — no manual refresh needed.

### 3. Configure environment variables

```bash
export HEDGEDOC_URL=https://md.example.com
export HEDGEDOC_SESSION_COOKIE=s%3A...          # from step 2, OR:
export HEDGEDOC_SESSION_COOKIE_NAME=connect.sid  # only when your instance uses another name
export HEDGEDOC_EMAIL=you@example.com            # for auto re-login
export HEDGEDOC_PASSWORD=your-password
```

At minimum you need `HEDGEDOC_URL` plus either the cookie or the email+password pair. Setting both is recommended — the cookie is used as a fast path, and email/password is the automatic fallback whenever it expires.

`HEDGEDOC_SESSION_COOKIE_NAME` defaults to `connect.sid`. Set it to the valid cookie name configured by your HedgeDoc instance (for example, `hedgedoc.sid`) so both login and manually supplied cookies use the right session.

### 4. Wire it into your agent

<details>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add hedgedoc -- uvx hedgedoc-mcp
```

Or add to `.claude/mcp.json`:

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

</details>

<details>
<summary><b>Codex CLI</b></summary>

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.hedgedoc]
command = "uvx"
args = ["hedgedoc-mcp"]
env = { HEDGEDOC_URL = "https://md.example.com", HEDGEDOC_EMAIL = "you@example.com", HEDGEDOC_PASSWORD = "your-password" }
```

</details>

<details>
<summary><b>Hermes</b></summary>

Add an MCP server entry in your Hermes config with `command: uvx`, `args: [hedgedoc-mcp]`, and the same environment variables. See the [Hermes MCP docs](https://docs.hermes.dev) for the exact config location on your install.

</details>

<details>
<summary><b>Any other MCP client</b></summary>

This is a standard stdio MCP server. Point your client at `uvx hedgedoc-mcp` (or the installed `hedgedoc-mcp` executable) with the environment variables above set, and it will discover the 6 tools automatically via the standard MCP `list_tools` handshake. Using `uvx` means the client never needs a separate install step — `uv` downloads and caches the package on first run.

</details>

## Available tools

| Tool | Description |
|---|---|
| `hedgedoc_create_note` | Create a new note (optionally with a custom URL alias). Returns the note ID and URL. |
| `hedgedoc_read_note` | Fetch a note's raw markdown content by ID or alias. |
| `hedgedoc_update_note` | Reports that HedgeDoc 1.x HTTP note updates are unsupported; it does not modify the note. |
| `hedgedoc_note_info` | Get a note's title, description, view count, and timestamps. |
| `hedgedoc_whoami` | Verify the session is valid and show the logged-in user. |
| `hedgedoc_list_history` | List the logged-in user's recently viewed/pinned notes. |

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

pytest                 # run tests (fully mocked, no live server needed)
ruff check .            # lint
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the auth flow and MCP layer fit together, and [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

MIT — see [LICENSE](LICENSE).
