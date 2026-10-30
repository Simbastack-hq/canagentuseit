# 0004: one job, three products; throwaway keys

Date: 2026-10-30. Proposal: `0004-proposal-comparisons-and-keys.md`. Review: `0004-astra-review.md`.

## Decided

- **Format.** A comparison is one job, one fixed spec, several products. Every product is run by
  both agents (Claude Code, Sonnet 5.5; Codex, gpt-6-astra) once, with the same caps and the same box.
  No verdict per product and no automatic how-to. One post per job, which NJ approves before it goes
  live. These replace the quickstart-test rules in SPEC.md for comparison jobs (see "Comparisons" there).
- **Credentials.** SPEC rule 6 becomes: no credentials except the throwaway ones a job declares for a
  product.
- **Pilot.** Three comparisons this week, at most $30 API-equivalent: doc-search (keyless) first and
  shown to NJ before the keyed ones (deploy: Vercel/Netlify/Cloudflare; database: Supabase/Neon/Turso).
  Kill: shown to about 10 builders, fewer than 2 ask for another comparison, park CAUI.

## Astra's must-fixes and what we did

| Finding | Done |
|---|---|
| Query output parsed loosely (short, duplicate, misordered, noisy output passed) | Strict: exactly min(k, eligible) distinct stored ids, nothing else on stdout, non-increasing true cosine. The ANN tolerance is now written in JOB.md. `count` must print a bare number. |
| Update/delete checks ignored exit codes, checked few records, never checked old categories; new docs after restart unchecked | Targeted checks on 10 updated ids (new vector, new category, gone from old category), 10 deleted ids (exit 0 and absent), all 10 added ids; repeated after the clean restart and the hard kill |
| Pre-restart answers discarded; filtered queries not rechecked | Health (count, 8 queries, 3 filtered, targeted) required before and after each restart. Correct within tolerance is the contract, not identical answers. |
| Product-use evidence unequal (byte search vs file mtime) | Every product: the check opens `/work/data` with the product's own client at the job's version (chromadb and lancedb through `uv run --with`, psql for Postgres) and requires rows = live documents, the same ids, no deleted ids, right categories |
| Need more decoys | Four decoys plus an untouched box: JSON store (fails only on the product step, which proves the rest is passable), L2 metric, duplicate-on-update, no-op delete. All five fail; checked on the lab. |
| Different hidden workload per run | One seed per job (`check_seed`, recorded), so all six runs face the same data |
| Harness stops after the first pass, wrong caps, 180 s check timeout | `tools/run_job.py`: every product with every agent, caps from job.json (30 min, 120 turns), check timeout 900 s |
| Key file handling, cleanup, redaction holes | Before the first keyed run: parse key files as data with an allowlist of vendor names and mode/owner checks; harness-owned teardown in `finally` with a resource inventory and an orphan sweep; value-based redaction (plus base64/URL forms and derived tokens) over every text file including extensionless ones, binaries withheld, public copy built atomically and refused on any hit |

Not adopted:
- "Proof of native similarity search" by automation. A store with real product data but a search in
  our own code would pass the product step. We read every solution's query path before writing the
  post, and say so in it.
- More repeats per cell. The pilot is an explicitly exploratory six-run case study; the post says so
  and makes no reliability percentages or production-scale claims.

## Post must contain (Astra's should-fix, adopted)

The builder's decision first; the workload and what it excludes (300 documents, no performance
claims); the six-run step matrix; setup, time and cost; the decisive transcript moments with the docs
the agent read; which failures were the agent, the docs or the product; links to code, versions, seed,
check and the redacted logs.
