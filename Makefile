# Thin wrappers over `uv run spelunk-bench …`. Every target is one command you
# can also run by hand (see README); the Makefile is convenience, not the only
# path.

.PHONY: install lint fmt test corpus bench smoke

install:
	uv sync --all-extras

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .

test:
	uv run pytest

corpus:
	uv run spelunk-bench corpus

bench:
	uv run spelunk-bench bench

smoke:
	uv run spelunk-bench bench --adapters ripgrep --repos itsdangerous
