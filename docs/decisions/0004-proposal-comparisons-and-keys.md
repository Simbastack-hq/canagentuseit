# 0004 (proposal, before Astra's review): one job, three products; throwaway keys

Date: 2026-10-30. Status: proposal. Astra's review and what we changed go in `0004-comparisons-and-keys.md`.

## Why

NJ read the four dry-run drafts: "works, first try in 15 s" hello-worlds help nobody. Astra's round-3
review (NJ-life Edge-Bets #57) named the drift: credential-free became the editorial scope, success
shrank to the quickstart's first checkable step, the backlog padded the slate, every run published.
NJ's call: comparisons of one real job across three products, plus a keyed track with throwaway
accounts. Pilot: three comparisons this week, at most $30 API-equivalent.

## Format

- A **job** is a small, real builder task with a fixed spec (`jobs/<id>/JOB.md`), fixtures the agent
  can test with, a **hidden** acceptance check written before any run, and a decoy implementation
  the check must reject.
- The same spec goes to every product; only the product name, version, docs URL and a one-line setup
  note differ.
- Each product is run by both agents (Claude Code, Sonnet 5.5; Codex, gpt-6-astra) once, with the
  same caps (30 min, 120 turns, same box). Six runs per job. The check runs after the agent stops, in
  the same box; the agent never sees it.
- Per run we record which check steps passed, minutes, cost (Claude) or tokens (Codex), turns, the
  errors the agent hit and the docs it read.
- **No verdict per product, no auto how-to.** One comparison post per job: what differed, which product
  fits which need, then the evidence table and links to full logs. NJ approves before publishing.
- Jobs come from a backlog of builder jobs, not from launches.
- Kill: shown to about 10 builders, fewer than 2 ask for another comparison, park CAUI.

## Job 1: doc-search (keyless)

"Document search that survives updates, deletes and a restart": Chroma 1.5.9 vs LanceDB 0.41.0 vs
pgvector (PostgreSQL 17 in the box, installed but not initialised or running; the agent has no root).
Spec: `jobs/doc-search/JOB.md`. Hidden check: `jobs/doc-search/check/check.py`, on fresh random data
(300 docs, 64-dim vectors with varied norms so cosine and L2 rank differently): cold start on an
empty `/work/data`, add + count, cosine top-5 (recall >= 4/5, first hit in exact top-2), category
filter, replace by id (30 ids, new vector + category, no duplicates), delete 40 + 2 unknown ids,
clean restart (stop.sh, kill leftovers, start.sh, same answers), hard kill (no stop.sh), add after
restart, and proof that the product holds the data (Chroma: the probe id in chroma.sqlite3; LanceDB:
a .lance table written after the add; Postgres: the probe id in the data dir files). Decoys: an
untouched box, and `decoy/` (right behaviour from a JSON file, no product) which must fail.

## SPEC rule 6 changes

From "the container holds no credentials of any kind" to: **no credentials except the throwaway ones a
job declares for a product**. Free tier, no card on file, revocable; rotated after the test.

## Key injection (keyed jobs 2 and 3)

- NJ creates the accounts and writes `~claude/.config/caui/keys/<vendor>.env` over ssh (0600,
  owned by `claude`, `KEY=VALUE` lines). Never in git, the brief, the task text or the brain's env.
- A job's product entry declares `"keys": ["vercel"]`. For that run only, the harness reads those
  files and `caui-box put`s them to `/tmp/keys/<vendor>.env` in that run's container just before the
  agent starts. JOB.md says where the file is and not to print it. The check gets the same file.
  The container is removed after the run.
- Redaction by value: `redact.py` loads the declared values (and their base64 and URL-encoded forms)
  and replaces them with `[REDACTED:<vendor>-key]`; the leftover scan includes them and refuses the
  public copy if any remain. Raw run dirs stay on the lab (0700).
- Teardown: each keyed job's check ends by deleting what the run created (projects, deployments,
  databases) with the same key, and records what it deleted.
- Accepted risk: the agent (or a prompt injection in vendor docs) could send a key anywhere the box
  can reach. Bounded by throwaway free-tier accounts, no card, rotation after the test.

## Questions for review

1. Does the doc-search check measure the job, and is anything in it unfair to one product?
2. Is "both agents, every product, once" the right sample for a comparison post, or too thin?
3. Holes in the key injection or redaction design, before the first keyed run.
4. What the comparison post must contain so it isn't another AI dump.
