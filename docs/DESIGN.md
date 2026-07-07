# grey-bench design

grey-bench measures how well code retrieval tools answer natural-language
*"where is X implemented?"* queries against real open-source repositories,
scored against hand-labeled ground truth.

It exists to evaluate [grey](https://github.com/) (the author's retrieval
tool), but it is built as a neutral benchmark first: every design choice below
is justified by fairness or reproducibility, not by what any particular tool
is good at. The threats-to-validity section states plainly where author bias
could enter and what the benchmark does about it.

## 1. Goals

1. **Comparable numbers** across fundamentally different retrieval approaches:
   keyword search (ripgrep), hybrid lexical/semantic indexes (ck, grepai), and
   an agentic LLM loop (Claude with grep/read tools).
2. **Reproducible runs**: pinned repo SHAs, pinned tool and model versions,
   one command (`make bench`) from clean checkout to markdown report.
3. **Credible labels**: manually authored queries, two-pass labeling with a
   consistency check, published protocol, dataset frozen before grey is
   measured.

### Non-goals

No web UI, no database, no leaderboard site, no more than 8 corpus repos, and
no LLM-generated queries — labels are manual because the benchmark's value is
its ground truth, and generated labels would launder one model's opinion into
the gold standard.

## 2. System overview

```
corpus.yaml ──► corpus command ──► corpus/{repo}/ @ pinned SHA
                                        │
queries/final/*.jsonl ──► runner ───────┤
                            │           ▼
                            │    adapter.index(repo)   (timed, cached)
                            │    adapter.search(query, repo, k=10)
                            ▼
                 results/{run_id}/results.json      (raw: every hit, every timing)
                            │
                            ▼
                 results/{run_id}/report.md         (comparison tables + pins)
```

Everything downstream of `results.json` is derived; the JSON is the record of
truth for a run, so reports can be regenerated and metrics recomputed without
re-running tools.

## 3. Corpus

Eight repositories, pinned by exact commit SHA in `corpus.yaml`. The mix
covers the languages and project shapes a code-search tool meets in practice,
while staying small enough for one person to label meaningfully.

| slot | repo | language | why this one |
|---|---|---|---|
| Python framework | fastapi/fastapi | Python | heavily decorated, DI-style indirection stresses non-literal retrieval |
| Django application | wagtail/wagtail | Python | large app-shaped codebase, Django conventions (implicit wiring) |
| Express-based TS | nestjs/nest | TypeScript | decorator/DI architecture on top of Express |
| Next.js application | shadcn-ui/taxonomy | TypeScript | app-shaped, file-system routing, moderate size |
| Go framework | gin-gonic/gin | Go | compact idiomatic Go, plain naming |
| Go CLI | cli/cli | Go | command-tree structure, real-world CLI patterns |
| Large mixed | getsentry/sentry | Python + TS | scale test; cross-language queries possible |
| Small | pallets/itsdangerous | Python | CI smoke target; full bench runs in seconds |

`corpus.yaml` schema:

```yaml
repos:
  - name: fastapi
    url: https://github.com/fastapi/fastapi
    sha: <40-char commit>
    language: python
    size_class: medium        # small | medium | large
```

**Clone strategy** (`grey-bench corpus`, wrapped by `make corpus`): per repo,
`git init && git fetch --depth 1 origin <sha> && git checkout FETCH_HEAD` into
`corpus/{name}/`. Shallow (sentry would otherwise be gigabytes of history),
exact (no branch drift), idempotent (skips when HEAD already equals the pinned
SHA). `corpus/` is gitignored.

SHAs are chosen once at scaffold time (latest release tag where the project
tags releases, otherwise default-branch HEAD) and then never advance silently;
bumping a SHA invalidates that repo's labels and requires relabeling, so it is
a deliberate, versioned event.

## 4. Query dataset

JSONL, one query per line, under `queries/`:

```json
{"id": "fastapi-0001",
 "repo": "fastapi",
 "query": "where is the OAuth2 password flow token extracted from the request?",
 "answers": [{"path": "fastapi/security/oauth2.py", "start_line": 120, "end_line": 168}],
 "answer_type": "single",
 "difficulty": "medium",
 "notes": ""}
```

- `id`: `{repo}-{4 digits}`, unique across the dataset.
- `repo`: must name a `corpus.yaml` entry.
- `answers`: one or more gold locations; paths are repo-relative with forward
  slashes; lines are 1-indexed and inclusive; spans are the smallest enclosing
  definition (see `LABELING.md`).
- `answer_type`: `single` | `multi` — must agree with `len(answers)`.
- `difficulty`: `easy` | `medium` | `hard` per the rubric in `LABELING.md`.

**Layout**: `queries/pass1/` and `queries/pass2/` hold the two independent
labeling passes; `queries/final/` holds the reconciled dataset the benchmark
actually runs. `grey-bench validate` enforces the schema plus, when the corpus
is cloned, that every gold path exists at the pinned SHA and every span is
within the file. `grey-bench consistency` diffs pass1 against pass2 (details
in `LABELING.md`).

Target: 150–250 queries, roughly 20–30 per repo, mixed difficulty.

## 5. Adapters

One interface, implemented in `src/grey_bench/adapters/`:

```python
@dataclass
class SearchHit:
    path: str            # repo-relative, forward slashes
    start_line: int      # 1-indexed inclusive; file-level tools may return 1..file_len
    end_line: int
    score: float         # adapter-native, higher is better; used only for ordering

@dataclass
class SearchResponse:
    hits: list[SearchHit]     # ranked best-first, at most k
    latency_s: float          # wall clock for this search() call
    metadata: dict            # adapter-specific (tokens, iterations, argv, ...)

@dataclass
class IndexStats:
    build_time_s: float
    size_bytes: int           # on-disk size of the index artifacts

class Adapter(ABC):
    name: str
    def version(self) -> str: ...                                  # pinned into the report
    def index(self, repo_path: Path) -> IndexStats | None: ...     # None = indexless
    def search(self, query: str, repo_path: Path, k: int = 10) -> SearchResponse: ...
```

### 5.1 ripgrep (`ripgrep.py`) — the floor

Deliberately naive keyword baseline: lowercase the query, drop stopwords and
question-words ("where", "is", "implemented", …), OR the remaining terms into
one `rg --json` invocation, group matches by file, rank files by distinct
terms matched then total match count. Hits are returned at the line of the
best match, extended ±0 lines (it is effectively a file+line pointer, which
is exactly what a grep gives you). No index; `index()` returns `None`.

This adapter is intentionally not tuned. It answers "what do you get for
free with grep?" — the floor every real tool must beat.

### 5.2 ck (`ck.py`) and grepai (`grepai.py`) — off-the-shelf hybrids

Both shell out to the installed CLI and parse structured output:

- **ck** ([BeaconBay/ck](https://github.com/BeaconBay/ck)): `ck --index` for
  the build step (timed as `IndexStats`), `ck --sem/--hybrid ... --jsonl` for
  search.
- **grepai** ([yoanbernabeu/grepai](https://github.com/yoanbernabeu/grepai)):
  `grepai index`, then `grepai search --json`. Requires a local embedding
  provider; the benchmark pins Ollama with a specific embedding model, named
  in the report.

Rules for both: configuration files are committed to this repo (no hidden
tuning), CLI version and embedding model are recorded per run, and a missing
binary causes the adapter to be *skipped with a visible warning*, never a
silent zero score.

### 5.3 agentic (`agentic.py`) — LLM tool-use loop

Claude (default `claude-sonnet-5`, configurable) in a tool-use loop over the
repo with three read-only tools: `grep(pattern)`, `read(path, start, end)`,
`list(path)`. The system prompt is fixed and committed. The loop is capped at
N iterations (default 10, configurable); the model must finish by calling a
mandatory `final_answer` tool with up to k ranked locations, which map
directly to `SearchHit`s. Hitting the cap without a `final_answer` counts as
an unanswered query (empty hit list), not an error.

`metadata` records per query: input tokens, output tokens, iterations used,
and whether `final_answer` was reached. Temperature 0. The exact model ID and
iteration cap are pinned in the report.

The agentic adapter is the ceiling analogue of ripgrep's floor: expensive and
slow, but a measure of what an LLM with basic tools achieves — including its
token cost, which is a first-class metric, not a footnote.

### 5.4 grey (`grey_stub.py`)

Same interface, raises `NotImplementedError` with a pointer, registered but
excluded from runs until it exists. Grey gets no hooks the other adapters
lack: when it lands, it implements the same three methods and is subject to
the same frozen dataset.

### 5.5 Fairness rules

These are the contract that makes cross-adapter numbers meaningful:

1. Every adapter receives the **identical query string**. No per-adapter query
   rewriting; whatever transformation an adapter does internally (ripgrep's
   stopword stripping, the agent's reasoning) is part of the tool under test.
2. All adapters are asked for **k = 10** hits.
3. **Index build time is excluded from search latency** and reported
   separately, together with index size. Searches run against a warm,
   prebuilt index.
4. Indexes are cached under `results/.index-cache/{adapter}/{repo}@{sha}/`
   keyed by adapter version + repo SHA; a version or SHA change rebuilds.
5. All adapters in a run execute on the same machine in the same session;
   hardware (CPU, RAM, OS) is recorded in the report.
6. Process-spawn overhead for CLI adapters is *included* in latency, because
   that is what a user of the CLI experiences. This is stated in the report.

## 6. Metrics

For a query with gold set `G` and ranked hits `R = [h_1 … h_k]`:

**Matching.** A hit `h` matches a gold `g` at:
- **file level** — `h.path == g.path` (exact string, repo-relative, forward
  slashes);
- **span level** — same path *and* the line ranges overlap by ≥ 1 line.
  A stricter IoU ≥ 0.5 variant (`|h ∩ g| / |h ∪ g|` over line sets) is
  computed as a secondary column to show how much scores depend on span
  generosity.

Each gold is *covered* by the highest-ranked hit that matches it; one hit may
cover several golds, several hits covering the same gold count once.

**Per-query scores**, each computed at both file and span level:
- `recall@k` (k ∈ {5, 10}) = covered golds in top-k / |G|. For
  `answer_type: single` this is 0/1; for `multi` it is fractional — that is
  the partial-credit mechanism, there is no labeler-assigned partial credit.
- `MRR` = 1 / rank of the first hit matching any gold; 0 if no hit matches.
- `success@10` = 1 if any gold is covered in the top 10 (used for the agentic
  success rate and headline comparisons).

**Aggregation**: macro-average over queries (every query counts equally,
regardless of repo size). The report tables slice overall / per-repo /
per-difficulty, with `n` shown for every cell so small slices aren't
over-read.

**Cost and speed**, per adapter:
- search latency p50 / p95 across all queries (warm index, spawn included);
- index build time and index size on disk, per repo (indexless adapters show
  "—");
- agentic only: success rate, mean and p50 total tokens (input + output) per
  query, and **tokens-to-correct-answer** = mean tokens over queries where
  `success@10 = 1`.

Metric implementations live in `metrics.py` with unit tests against
hand-computed values — the numbers people will quote must be the module's
most-tested code.

## 7. Runner, results, report

`grey-bench bench [--adapters a,b] [--repos r1,r2] [--queries path]`
(wrapped by `make bench`; `make smoke` = ripgrep on itsdangerous only):

1. Verify corpus checkouts match pinned SHAs (refuse to run on drift).
2. Load and validate `queries/final/`.
3. Per adapter × repo: ensure index (cache hit or timed build), then run every
   query, capturing hits, latency, and metadata. Adapter exceptions are
   recorded per query and surfaced in the report — a crashing adapter shows
   up as failures, not as absence.
4. Write `results/{run_id}/results.json`: run manifest (timestamp, git SHA of
   grey-bench itself, corpus SHAs, adapter versions, model IDs, hardware,
   query-set checksum) + raw per-query records.
5. `grey-bench report` renders `report.md` from `results.json`: headline
   comparison table, per-repo and per-difficulty tables, cost/latency table,
   and the full pin manifest. Regenerable without re-running.

`run_id` = UTC timestamp + short random suffix. Determinism: everything
except the agentic adapter is deterministic given pinned versions; the
agentic adapter runs at temperature 0 and its residual nondeterminism is
disclosed in the report (a `--trials n` flag is future work, not promised).

## 8. Threats to validity

Stated here because a benchmark that hides its weaknesses invites fair
dismissal.

1. **Author bias** — the benchmark author also builds grey. Mitigations: the
   query dataset is frozen and tagged (checksum recorded in every report)
   *before* grey is ever benchmarked; queries are authored from repo
   documentation and issues, not from knowledge of any tool's strengths; the
   labeling protocol is published and label disputes via PR are welcome.
2. **Training-data contamination** — all corpus repos are public and almost
   certainly in LLM and embedding training data. The agentic adapter may
   partially *remember* rather than *retrieve*. Mitigation is honesty plus a
   structural check: answers must cite line spans valid at the pinned SHA,
   which stale memorization tends to get wrong. Reports carry this caveat.
3. **Single labeler** — no inter-annotator agreement is possible. Proxy:
   two labeling passes on different days with an automated disagreement
   report (`grey-bench consistency`), reconciliation notes kept in the data.
4. **Small n** — 20–30 queries per repo means per-repo slices are noisy.
   Tables always show `n`; claims belong at the overall level.
5. **Hardware sensitivity** — latency numbers are machine-relative. The
   report records hardware; cross-run latency comparisons are only valid on
   the same machine.

## 9. CI

GitHub Actions on ubuntu-latest, every push and PR:

1. `ruff check` + `ruff format --check`
2. `pytest` (unit tests only — fixture repo, no network)
3. Smoke bench: clone itsdangerous at its pinned SHA, run the ripgrep adapter
   over a small committed starter query set, assert the pipeline produces a
   well-formed `results.json` and `report.md`.

The agentic, ck, and grepai adapters are excluded from CI (API key / binary /
Ollama dependencies); they run locally. CI proves the harness, not the tools.

## 10. Repository layout

```
grey-bench/
├── pyproject.toml            # uv-managed; runtime deps: pyyaml (+ anthropic extra)
├── Makefile                  # thin wrappers over `uv run grey-bench …`
├── corpus.yaml
├── README.md
├── docs/
│   ├── DESIGN.md             # this file
│   ├── LABELING.md           # labeling protocol
│   └── PLAN.md               # milestone plan
├── queries/
│   ├── pass1/  pass2/  final/
├── src/grey_bench/
│   ├── cli.py                # subcommands: corpus, validate, consistency, bench, report
│   ├── corpus.py  queries.py  consistency.py  metrics.py  runner.py  report.py
│   └── adapters/
│       ├── base.py  ripgrep.py  ck.py  grepai.py  agentic.py  grey_stub.py
├── tests/                    # incl. tests/fixtures/ tiny synthetic repo
├── results/                  # gitignored
└── .github/workflows/ci.yml
```

Windows note: the development machine is Windows; `make` is optional. Every
Makefile target is one `uv run grey-bench …` command, documented in the
README, so the Makefile is convenience for CI and Unix users, never the only
path.
