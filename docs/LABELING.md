# Labeling protocol

This document is the contract for the spelunk-bench ground truth. Every query in
`queries/final/` was produced by following it; disputes about labels should
argue from this text (and are welcome as PRs or issues).

The dataset is labeled by a single person in **two independent passes on
different days**, machine-checked for consistency, then manually reconciled.
The reconciled `queries/final/` set is **frozen and checksummed before any
run that includes spelunk** — see "Freezing" below.

## 1. What a query is

A query is a natural-language question a developer unfamiliar with the
codebase would plausibly type into a search tool, of the shape
*"where is X implemented / handled / defined?"*.

Authoring rules:

1. **Write from the outside in.** Source queries from README features,
   documentation, changelogs, and issue titles — not from browsing the code
   first and reverse-engineering a question that a favorite tool would ace.
   (Finding the answer obviously requires reading code; *choosing the
   question* must not.)
2. **Natural phrasing.** Ask the way a person asks: "where does the session
   cookie get signed?", not `sign(session_cookie)`. Copying an identifier
   verbatim from the code into the query is allowed only for `easy` queries,
   where lexical match is the point.
3. **Answerable at the pinned SHA.** Every query is verified by opening the
   gold file(s) at the pinned commit; line numbers come from that commit and
   no other.
4. **One intent per query.** "Where is retry logic and how is backoff
   configured?" is two queries.
5. **No tool-informed selection.** Queries are never added, dropped, or
   reworded because of how any adapter — especially spelunk — performs on them.
   After the freeze this is enforced by the checksum; before the freeze it is
   a rule of conduct, stated here so readers can hold the author to it.

Target: 150–250 queries total, roughly 20–30 per corpus repo, with a spread
of difficulties per repo (aim ≥ 5 of each difficulty where the repo allows).

## 2. What counts as a correct location

A gold location is the **primary implementation** of the thing the query asks
about: the function, method, or class body that does the work.

- **Span rule:** the span is the *smallest enclosing definition* — the whole
  function/method including its signature and decorators, or the whole class
  when the behavior is genuinely the class (not one method of it). Never the
  whole file, never a single expression.
- **Included:** the definition doing the work; for behavior implemented via a
  decorator/middleware/hook, the decorator or hook implementation itself.
- **Excluded:** call sites, re-exports, imports, interface/type declarations,
  tests, documentation, generated files, and vendored dependencies — *unless
  the query explicitly asks for them* ("where is X registered", "where is X
  configured", "where is X tested" make the registration/config/test site the
  answer).
- **Dispatch chains:** when a public entry point immediately delegates
  (`def foo(): return _foo_impl()`), the gold is the implementation, not the
  shim. If the entry point contains real logic of its own, it may be a second
  gold location (making the query `multi`).

## 3. Single vs multi, and partial credit

- `answer_type: single` — one location a reasonable engineer would give as
  *the* answer. `answers` has exactly one element.
- `answer_type: multi` — the implementation is genuinely split: parallel
  implementations (per-language, per-backend), a base class plus the concrete
  override that does the work, or cooperating halves of one mechanism. List
  **every** location a reasonable engineer would accept; if two candidate
  locations feel interchangeable rather than jointly necessary, pick the
  primary one and stay `single`.

Partial credit is **mechanical, not judged**: recall@k is the fraction of
gold locations covered (see DESIGN.md §6). File-level vs span-level scoring
is likewise computed, not labeled — every label always carries exact spans,
and the metrics layer derives the file-level view.

## 4. Difficulty rubric

Assigned per query, judged against the gold file at the pinned SHA:

- **easy** — a distinctive query term appears verbatim in or near the gold
  span (function name, error string). A grep for the obvious keyword finds it
  on the first page.
- **medium** — requires synonym or concept mapping: the query says
  "authentication check" and the code says `verify_credentials`. Keyword
  search finds related noise but not the span without reading.
- **hard** — the vocabulary of the query is essentially absent from the gold
  code, the answer is split across locations, or heavy indirection
  (decorators, DI, codegen, convention-over-configuration) separates the
  concept from the implementation.

When torn between two levels, pick the harder one and say why in `notes`.

## 5. Two-pass process

1. **Pass 1** (`queries/pass1/{repo}.jsonl`): author queries and label
   answers, spans, `answer_type`, and difficulty.
2. **Wait ≥ 1 day.**
3. **Pass 2** (`queries/pass2/{repo}.jsonl`): re-label the *same query
   strings* from scratch — fresh answers, spans, and difficulty, without
   looking at pass 1.
4. **Consistency check** — `spelunk-bench consistency` compares passes per query
   id and flags:
   - answer-set mismatch (paths differ between passes),
   - span drift: same path but boundaries differ by more than 10 lines on
     either end,
   - `answer_type` mismatch,
   - difficulty mismatch,
   - ids present in one pass only.
5. **Reconcile** every flagged query manually into
   `queries/final/{repo}.jsonl`, recording a one-line rationale in `notes`
   (e.g. `"pass2 span kept; pass1 included the caller"`). Unflagged queries
   copy through with pass-1 labels. A query that cannot be reconciled — the
   two passes reveal the question is ambiguous — is **dropped**, and that is
   the correct outcome, not a failure.

The consistency report (counts of each flag type, per repo) is committed
alongside the dataset as a labeling-quality statement.

## 6. Validation

`spelunk-bench validate` must pass on every dataset file before it is committed:

- schema: required fields, `{repo}-NNNN` unique ids, known `repo`,
  `difficulty` ∈ {easy, medium, hard}, `answer_type` consistent with
  `len(answers)`, `1 ≤ start_line ≤ end_line`;
- against a cloned corpus: every gold path exists at the pinned SHA and every
  span lies within the file's line count.

## 7. Freezing

When labeling is complete, `queries/final/` is frozen:

1. `spelunk-bench validate` and the consistency report are clean/committed.
2. The dataset gets a git tag (`dataset-v1`) and its SHA-256 checksum is
   recorded; every benchmark report includes the checksum of the query set it
   ran against.
3. The freeze happens **before spelunk is benchmarked for the first time**.
   Any later dataset change (new queries, label fixes from disputes) bumps
   the tag (`dataset-v1.1`), and results across different dataset versions
   are never mixed in one table.
