# Implementation plan

PR-sized milestones, ~40 h of code total, targeting 4 working baselines in
3–4 weeks at ~15 h/week. Architecture and rationale live in
[DESIGN.md](DESIGN.md); labeling rules in [LABELING.md](LABELING.md).

## Decisions already made

- Mixed-language corpus repo: **getsentry/sentry**
- Agentic default model: **claude-sonnet-5** (configurable)
- corpus.yaml SHAs: fetched via `git ls-remote` at M3 time (latest release
  tag, else default-branch HEAD), then pinned
- Dev machine is Windows without `make`/`rg`/`uv` (git 2.52, Python 3.14,
  Ollama present): the Makefile is a thin wrapper over `uv run grey-bench …`;
  install `uv` and `ripgrep` via winget before M1

## Milestones

| # | Milestone | Est | Week | Status |
|---|---|---|---|---|
| M0 | git init, DESIGN.md, LABELING.md, PLAN.md, initial commit | 1h | 1 | **done** |
| M1 | Scaffold: pyproject (uv), package layout, CLI skeleton, ruff + pytest, CI lint+test, README with results-table placeholder | 3h | 1 | |
| M2 | Query schema + JSONL validator + two-pass consistency checker + tests | 4h | 1 | |
| M3 | corpus.yaml with real pinned SHAs + `corpus` command + `make corpus` | 3h | 1–2 | |
| M4 | Adapter interface (`base.py`) + ripgrep adapter + tests on fixture repo | 4h | 2 | |
| M5 | Metrics module (recall@k, MRR, span overlap + IoU, percentiles) + tests vs hand-computed values | 4h | 2 | |
| M6 | Runner + results.json + markdown report + index caching + `make bench` — end-to-end with ripgrep | 5h | 2–3 | |
| M7 | CI smoke bench on itsdangerous + committed starter query set (~5 queries) | 2h | 3 | |
| M8 | ck adapter (timed index step, parse `--jsonl`) | 3h | 3 | |
| M9 | grepai adapter (pinned Ollama embedding model, parse JSON) | 3h | 3 | |
| M10 | Agentic adapter: tool-use loop (grep/read/list + mandatory final_answer), iteration cap, token accounting | 6h | 4 | |
| M11 | grey stub adapter + README/docs polish + first full bench run | 2h | 4 | |

Labeling (150–250 queries, two passes per LABELING.md) is separate
person-time, running in parallel from week 2 once M2 lands. Dataset freeze
(`dataset-v1` tag) happens before grey is ever benchmarked.

## Verification per milestone

- **M0**: initial commit on `main` contains the three docs and `.gitignore`.
- **M1–M5**: `uv run pytest` green, `uv run ruff check` clean, each new CLI
  subcommand runs against the fixture repo.
- **M6**: `uv run grey-bench bench --adapters ripgrep --repos itsdangerous`
  produces a well-formed `results.json` and readable `report.md`.
- **M7+**: CI green on GitHub; every new adapter is benched on itsdangerous
  before the full corpus.

## Sequencing notes

- M2 before M3: the validator's corpus-dependent checks are stubbed until the
  corpus command exists; schema checks work immediately so labeling can start.
- M4 + M5 + M6 form the day-one vertical slice: one baseline, real metrics,
  real report.
- M10 is last among adapters because it is the most expensive to iterate on
  (API costs); the harness is proven on free adapters first.
