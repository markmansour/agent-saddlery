.PHONY: diagrams

diagrams:
	cd backend && uv run python scripts/gen_diagrams.py
