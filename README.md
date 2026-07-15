# spelunk-bench

spelunk-bench measures how well code retrieval tools answer natural-language
*"where is X implemented?"* queries against real open-source repositories,
scored against hand-labeled ground truth.

See [docs/DESIGN.md](docs/DESIGN.md) for the full design, [docs/LABELING.md](docs/LABELING.md)
for the labeling protocol, and [docs/PLAN.md](docs/PLAN.md) for the milestone plan.

## Status

Early scaffolding — the CLI skeleton plus query validation and the two-pass
consistency checker (`validate`, `consistency`) work; the corpus, adapters, and
runner do not yet. See [docs/PLAN.md](docs/PLAN.md) for what's done and next.

## Install

```sh
uv sync --all-extras   # or: make install
```

## Usage

Every `make` target is a thin wrapper over a `uv run spelunk-bench …` command:

```sh
make corpus   # uv run spelunk-bench corpus   — clone corpus repos at pinned SHAs
make bench    # uv run spelunk-bench bench     — run adapters, write results.json
make smoke    # ripgrep on itsdangerous only
make test     # uv run pytest
make lint     # uv run ruff check . && ruff format --check .
```

## Results

_Populated by `spelunk-bench report` (`make bench`) once the harness and
adapters land. Headline shape:_

| adapter | success@10 | recall@10 (file) | recall@10 (span) | MRR | latency p50 |
|---|---|---|---|---|---|
| ripgrep | — | — | — | — | — |
| spelunk | — | — | — | — | — |
| ck | — | — | — | — | — |
| grepai | — | — | — | — | — |
| agentic | — | — | — | — | — |

_Every report also carries the full pin manifest (corpus SHAs, tool/model
versions, hardware, query-set checksum) and the query-set version it ran
against._

## About

Built and maintained by Dhruv Bhardwaj. Query labels were hand-annotated by
the author; the labeling protocol is documented in
[docs/LABELING.md](docs/LABELING.md).

The author also develops [spelunk](https://github.com/d2r3v/spelunk), one of the tools evaluated; the harness,
labels, and metrics are tool-agnostic and reproducible via `make bench`.

## License

MIT — see [LICENSE](LICENSE).
