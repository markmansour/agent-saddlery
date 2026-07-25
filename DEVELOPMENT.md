# Development

Starting the app (backend, TUI) is in the root [`README.md`](README.md#quick-start).

## Running checks

### Backend

From `backend/`:

```bash
uv run pytest tests/ -v      # tests
uv run ruff check .          # lint
uv run ruff format --check . # format (dry-run)
uv run ty check              # type checking — note: `ty`, not `py` or `mypy`/`pyright`
```

### TUI

From `frontend/tui/`:

```bash
npm run test:run    # tests (vitest, run once — `npm test` runs in watch mode)
npm run lint        # eslint
npm run type-check  # tsc --noEmit
npm run format      # prettier --write src
```

If `npm run lint` throws `TypeError: Cannot read properties of undefined (reading 'recommended')`,
`node_modules/eslint-plugin-react` is stale (pre-7.33, before flat-config support was added) even
though `package.json`/`package-lock.json` specify a newer version — run `npm ci` to reinstall from
the lockfile.

## Testing tool calls

Tool-calling tests live in `backend/tests/`:

- `test_read_file.py` — `FileReadTool` safety and edge cases (path traversal, missing file,
  permission errors, non-UTF-8 content).
- `test_agent.py` — the `Agent.run()` round-trip: tool call → execution → result appended → loop
  continues; unknown tool name; `max_tool_iterations` exceeded.
- `test_fake_provider.py` — `FakeProvider` can script a sequence of tool calls without hitting the
  real Anthropic API, which is what makes the round-trip tests above deterministic.
- `test_anthropic_provider.py` — a live smoke test against the real API, skipped unless
  `ANTHROPIC_API_KEY` is set.

To exercise the round-trip manually against the real API (needs `ANTHROPIC_API_KEY` — see the
root [`README.md`](README.md#quick-start) for the `.env` setup):

```bash
echo "Some file content" > /tmp/demo.txt
cd backend
uv run python -m saddlery.cli.main --json-input <<'EOF'
Read /tmp/demo.txt and tell me what it says in one sentence.
EOF
```

Expect a `tool_call` event (`tool_name: "read_file"`) followed by a `tool_result` event
(`is_error: false`, `content` = the file's text). Whether the model actually calls the tool
depends on its judgment — there's no way to force a tool call through the real provider without
network access; use `FakeProvider` for deterministic tests instead.

## Debugging tool calls

See [`docs/tools/README.md`](docs/tools/README.md#debugging-tool-calls) for where tool-call
logging lands (`tui.log`, `core.log`) and what's not yet instrumented (execution timing inside
the agent loop).

## Inspecting API traffic with a proxy

`AnthropicProvider` constructs a bare `anthropic.AsyncAnthropic()` (no explicit proxy/client
config), so it inherits standard proxy env vars via `httpx`. Any MITM proxy works the same way:
route traffic through it with `HTTPS_PROXY`, then trust its root cert via `SSL_CERT_FILE` so
`httpx` doesn't reject the intercepted TLS handshake.

### mitmproxy (free, open source)

```bash
brew install mitmproxy
mitmproxy   # or `mitmweb` for a browser UI, `mitmdump` for headless/CLI — all listen on :8080 by default
```

The cert is generated on first run at `~/.mitmproxy/mitmproxy-ca-cert.pem` — no export step needed.

```bash
export HTTPS_PROXY=http://localhost:8080
export SSL_CERT_FILE=~/.mitmproxy/mitmproxy-ca-cert.pem
cd backend && uv run saddlery
```

### Charles Proxy (paid, GUI-first alternative)

Default port 8888. In Charles: **Proxy → SSL Proxying Settings** → enable, and add
`api.anthropic.com:443` to the include list (Charles won't decrypt HTTPS for a host unless it's
listed). Export the root cert via **Help → SSL Proxying → Save Charles Root Certificate** (or from
Keychain Access, "Charles Proxy CA", as `.pem`), then:

```bash
export HTTPS_PROXY=http://localhost:8888
export SSL_CERT_FILE=/path/to/charles-cert.pem
cd backend && uv run saddlery
```

Either way, `SSL_CERT_FILE` is required — without it, `httpx` fails TLS verification because the
proxy presents its own cert in place of Anthropic's real one. Both env vars are inherited by the
TUI's spawned backend subprocess too, so the same export works whether you run the backend
directly or via `npm run dev`.

## Diagrams

Regenerate the Mermaid diagrams under `docs/diagrams/` after changing `saddlery.events` or
`saddlery.messages`:

```bash
make diagrams
```

This re-runs pyreverse (class/package diagrams) and the ER generator
(`backend/scripts/gen_diagrams.py`) — do not hand-edit the generated files. Hand-authored
sequence diagrams (e.g. `tool-round-trip-sequence.md`) are edited directly.
