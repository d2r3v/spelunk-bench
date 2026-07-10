# spelunk-bench

spelunk-bench measures how well code retrieval tools answer natural-language
*"where is X implemented?"* queries against real open-source repositories,
scored against hand-labeled ground truth.

See [docs/DESIGN.md](docs/DESIGN.md) for the full design, [docs/LABELING.md](docs/LABELING.md)
for the labeling protocol, and [docs/PLAN.md](docs/PLAN.md) for the milestone plan.

## Status

Early scaffolding — no adapters or runner yet. See [docs/PLAN.md](docs/PLAN.md)
for what's done and what's next.

## Results

_(placeholder — populated by `spelunk-bench report` / `make bench` once the
harness and adapters land)_

## About

Built and maintained by Dhruv Bhardwaj. Query labels were hand-annotated by
the author; the labeling protocol is documented in
[docs/LABELING.md](docs/LABELING.md).

The author also develops spelunk, one of the tools evaluated; the harness,
labels, and metrics are tool-agnostic and reproducible via `make bench`.

## License

MIT — see [LICENSE](LICENSE).
