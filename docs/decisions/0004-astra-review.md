# 0004: Astra's review (gpt-6-astra, 2026-10-30)

Asked: the four questions in `0004-proposal-comparisons-and-keys.md`, reading the proposal, JOB.md, check.py, the decoy, SPEC.md, run_card.py and redact.py. Verbatim answer:

The proposal measures a useful job, but the check and harness need fixes before results support a comparison.

**Must-fix — 1. Does the check measure the job fairly?**

- **Output validation is unsound.** In `check.py`, `ids_out()` silently discards unknown IDs and noise. I verified in memory that queries returning only four IDs, duplicate IDs, misordered lower ranks, or extra stdout all pass. Require exactly `min(k, eligible_count)` distinct, eligible IDs, no other stdout, and descending similarity. Parse `count` strictly too. State any ANN recall tolerance in `JOB.md`; it currently promises the most similar documents.
- **Mutation checks miss failures.** Update/delete verification ignores query exit codes; deletion queries can fail with empty output and pass. Updates never change or verify text, inspect only six updated IDs, and never verify removal from old categories. After-restart queries may miss all ten newly added documents. Use targeted assertions for changed, deleted, and newly inserted records, including after both restarts.
- **Restart evidence is incomplete.** The pre-restart `bad` result is discarded; identical answers are reported but not required. Decide whether correctness within the stated tolerance or identical answers is the contract. Recheck filtered queries after restart.
- **Product-use evidence is unequal and inadequate.** Chroma/Postgres require an ID’s bytes somewhere in storage; LanceDB requires only a recently written `.lance` file. None proves native similarity search. Use product-native inspection of IDs, text, vectors, categories, and counts, plus review of the executed search path. Add decoys that store genuine product data but search JSON, alongside wrong-metric, stale-update, and broken-delete decoys.
- **Control the comparison inputs.** `random.Random()` generates different hidden workloads per run. Use the same recorded hidden seed and workload across all six runs. Resolve `@PGVECTOR@` and record the actual extension version. PostgreSQL is preinstalled but needs server initialization; the others require package installation. That is defensible for this local deployment scenario, but separate installation, service setup, and implementation time.

**Must-fix — 2. Is one run per agent/product enough?**

Enough for an explicitly exploratory six-run case study; insufficient for reliability percentages or broad product rankings.

First fix the machinery: `run_card.py` stops after the first passing agent, defaults to 20 minutes/80 turns, and applies its turn limit only to Claude. Its outer check timeout is 180 seconds, shorter than even one permitted 300-second startup. It also expects the old brief/check format. Implement unconditional six-run scheduling, comparable enforced caps, sufficient check time, and actual installation/execution of the new check and decoys.

Update `SPEC.md` beyond rule 6: quickstart scope, deliverables, attempts, caps, verdicts, guides, and publishing rules all conflict with the proposal.

**Must-fix — 3. Key-design holes**

- Parse key files as data; never shell-source them. Allowlist vendor names, reject symlinks, verify ownership/modes, and enforce host directories `0700`, files `0600`, and equivalent container permissions. Current `put` and run-directory creation do not enforce these modes.
- Cleanup cannot live only at the check’s end. Use harness-owned cleanup in `finally`, an independently recorded resource inventory, retries, and an orphan sweeper. Cover agent failure, check timeout, and harness interruption; revoke credentials after cleanup.
- `redact.py` currently lacks declared-value handling. Include derived credentials issued during runs. Scan every publishable text file, including extensionless files and filenames; current leftover scanning covers only `TEXT` suffixes. Binary images/video are copied unchanged. Withhold unreviewed binaries, build public output atomically, and make publication fail closed. Exact-value/base64/URL matching is useful, but cannot guarantee removal of arbitrary transformations.

**Should-fix — 2 and 4. Sampling and editorial value**

Predeclare repeat rules, rotate run order, and repeat all cells if stronger comparative claims matter; retain every valid attempt.

Each post should contain the builder’s decision, workload and exclusions, six-run step matrix, setup/time/token measurements, decisive transcript excerpts and doc links, and explanations distinguishing agent mistakes, documentation gaps, and product constraints. Link code, versions, seed, checks, and redacted evidence. Make “fits which need” conclusions traceable to observations; explicitly exclude production-scale performance claims from this 300-document exercise.
