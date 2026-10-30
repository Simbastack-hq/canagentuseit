# 0003: Dry run, 3 tools (2026-10-29/30)

**Outcome:** FastMCP 4.1.4, Chroma 1.5.9 and LanceDB 0.41.0 all passed on Claude Code's first attempt (0.6, 1.7 and 0.7 minutes; API-equivalent $0.05, $0.08, $0.06). Three verdict posts are SlopIt drafts; their guides are withheld until guide validation can run. Nothing published.

**Run conditions (disclosed in each draft):** the standard sandbox wasn't installed yet (it needs NJ's one root step), so these ran in a fallback: the agent's brain on NJ's Mac with only the four sandbox tools (inventory asserted), the container under Docker on the lab's default network without the egress filter. The container was fresh and held no credentials. When this was flagged, new container starts were blocked mid-run: no Codex retry, re-run or B-roll for Chroma ran outside the sandbox.

**What the dry run caught (all fixed):**
- `fetch_url` returned up to 60k characters; Claude Code saved it to a host file the agent (no Read tool, by design) couldn't open, so it fell back to `curl`. Tool output is now paged at 20k with `offset`.
- Redaction ate the `n` of a JSON `\n` (broken JSON), and missed Claude Code's dashed project-key paths. JSON is now redacted and scanned by value; the dashed forms are covered. The leftover check refused to send all three drafts until they were clean.
- The writer job's tool permissions didn't match how the model called things; it now needs one script (`post_draft.py --pending` / `<run>`).
- `public/` copied in rendered media and bookkeeping files; excluded.

**Astra's review (`0003-astra-review.md`) and what we did:**

| Astra said | Decision |
|---|---|
| Successes are credible; posts overclaim the method (sandbox, "only the docs") | **Adopted.** Fallback note in each draft from `result.json.fallback`; "with no outside reference material in the log" replaces "using only the docs" (prior knowledge can't be excluded). |
| Regex checks accept fabricated output; untouched-box decoy is a minimal control | **Adopted.** New cards need `check.decoy_script`, a plausible but wrong `run.sh` the check must reject; the scout tightens checks until it can write one. The three dry-run checks predate this and are flagged as weak. |
| Process-cleanup claim isn't evidenced in the logs | **Adopted.** The cleanup step now logs process counts before and after (`cleanup.out`). |
| Guide text claims clean-machine validation it didn't get; post.json said "steps failed" | **Adopted.** Status now reads "sandbox unavailable, guide not checked yet"; guides stay withheld, and that line only becomes true once `guide_check.py` passes. |
| Preview links carry tokens | **Noted.** They live only in `post.json` on the test machine (excluded from `public/` and the repo) and in NJ's Telegram. |
| Three Python quickstarts are a weak opening slate | **Adopted.** Scout slate rule until the first 10 posts: ≤ 3 of one kind, ≥ 2 non-Python, ≥ 2 crossing a process boundary, ≥ 1 needing state across a restart; no manufactured difficulty, no picking for failure. |
| Approve these only as labelled fallback observations, or re-run in the real sandbox | **NJ's call.** Recommendation: re-run all three in the real sandbox once the root step is done (same cards, ~5 minutes total), and publish those instead. |
