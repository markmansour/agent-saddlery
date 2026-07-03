.PHONY: diagrams

diagrams:
	cd core && uv run python scripts/gen_diagrams.py
