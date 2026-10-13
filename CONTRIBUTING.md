# Contributing to hedgedoc-mcp

Thanks for considering a contribution! This is a small, focused project —
here's how to get productive quickly.

## Setup

```bash
git clone https://github.com/mrsunglasses-experiments/hedgedoc-mcp.git
cd hedgedoc-mcp
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Running tests

```bash
pytest                 # all tests, against an in-process fake HedgeDoc
pytest -v               # verbose
ruff check .            # lint
ruff format --check .   # formatting
```

All tests should pass with zero network access. If you add a new
`HedgeDocClient` method, teach `tests/fake_hedgedoc.py` the endpoint
(following HedgeDoc 1.x's real behaviour) and add a test in
`tests/test_client.py` that uses the `hedgedoc` fixture.

## Project structure

```
src/hedgedoc_mcp/
  client.py    # HTTP client, zero MCP dependencies — the reusable core
  auth.py      # env var config + cookie-first/login-fallback auth policy
  server.py    # FastMCP server: 5 tools, thin adapter over client.py
tests/
  fake_hedgedoc.py  # in-process fake HedgeDoc 1.x server used by the tests
  conftest.py       # `hedgedoc` fixture that runs the fake server
  test_client.py    # client.py against the fake server
  test_auth.py      # config parsing, auth fallback logic, login CLI
  test_server.py    # MCP tool calls through the real request handler
docs/
  ARCHITECTURE.md   # how the three layers fit together
  LIMITATIONS.md     # what HedgeDoc 1.x genuinely can't do over HTTP
```

## Guidelines

- **Keep `client.py` MCP-free.** It should always be usable as a
  standalone Python client with zero knowledge of the `mcp` package. If
  you're adding MCP-specific logic, it belongs in `server.py`.
- **New client methods need tests.** See the existing tests for the
  pattern — no live HedgeDoc instance required to contribute.
- **Match HedgeDoc's real API.** If you're not sure an endpoint exists,
  check the [official OpenAPI spec](https://docs.hedgedoc.org/dev/api/)
  first. Don't invent endpoints that don't exist in HedgeDoc 1.x — update
  `docs/LIMITATIONS.md` instead if something genuinely isn't possible.
- **New MCP tools need a precise docstring.** FastMCP uses it as the tool
  description, and agents decide whether to call a tool based on that alone —
  be specific about what it does and does not do (see
  `hedgedoc_create_note`'s note that content can't be edited afterwards).
  Describe each parameter with `Annotated[..., Field(description=...)]`.

## Reporting HedgeDoc version incompatibilities

This project was built and tested against HedgeDoc **1.11.1**. If you hit
a real difference on another 1.x version, please include:

- Your HedgeDoc version (`docker exec <container> cat package.json | grep version`, or check `/status`)
- The exact request/response that differs from what `client.py` expects
- Whether the issue is in `POST /new`, `GET /{note}/download`,
  `GET /{note}/info`, `/me`, `/history`, or `/login`

## Adding support for a new agent client

If you've wired this server into an agent not covered in the README (only
Claude Code, Codex, and Hermes are documented today), a PR adding a
`<details>` block with that agent's config format is very welcome — no
code changes needed, just documentation.

## Code of conduct

Be respectful, be constructive, assume good faith. That's it.
