# Development

Starting the app (backend, TUI) is in the root [`README.md`](README.md#quick-start).

## Running checks

From `backend/`:

```bash
uv run pytest tests/ -v      # tests
uv run ruff check .          # lint
uv run ruff format --check . # format (dry-run)
uv run ty check              # type checking — note: `ty`, not `py` or `mypy`/`pyright`
```

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

## Diagrams

Regenerate the Mermaid diagrams under `docs/diagrams/` after changing `saddlery.events` or
`saddlery.messages`:

```bash
make diagrams
```

This re-runs pyreverse (class/package diagrams) and the ER generator
(`backend/scripts/gen_diagrams.py`) — do not hand-edit the generated files. Hand-authored
sequence diagrams (e.g. `tool-round-trip-sequence.md`) are edited directly.
