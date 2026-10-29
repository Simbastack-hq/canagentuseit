# What a test is

*Can an Agent Use It? (canagentuseit.com). This file is the contract every scout card, test run and post follows. If a prompt or a script disagrees with it, this file wins and the other gets fixed. Why each rule exists: `docs/decisions/`.*

## One test

A test is **one documented first task, one pinned version, one agent setup, one date.**

1. **The task is the tool's own first task.** Whatever the official quickstart walks you through first (install, hello world, first tool call, first local example). The scout restates it in a few sentences, as a builder would ask their agent. It adds nothing the quickstart doesn't say: no hints, no workarounds, no links beyond the docs.
2. **The success check is written before the run, and is hidden.** A command the harness runs after the agent stops, plus what its output must show. The agent sees the goal the task states, never the check.
3. **The check must be able to fail.** Before any agent starts, the harness runs the check on an untouched box (the *decoy*). If the decoy passes, the check can't tell success from an error message: the run is `inconclusive` and the card goes back for a better check. Checks should exercise behaviour (call the thing with an input, read its answer), not just look for a word.
4. **Everything is pinned and recorded.** Tool version, sandbox image tag, agent and model for each attempt, date. A verdict is about that combination only. There is no universal "works with agents" badge.
5. **Docs only.** The agent gets the task text and the docs URL. Nothing from the scout's research reaches it (why the tool is notable, launch claims, forum threads). It may fetch any page (a real agent would), but has no web search. Every URL it fetched is in the result, and a pass where it never opened the docs is reported as prior knowledge.
6. **Fresh, credential-free sandbox.** Each attempt starts a new container from the pinned image with an empty `/work`. The container holds no credentials of any kind, and can't reach the host or private networks.
7. **The agent's brain runs outside.** The agent runs on the host with its own login, and its only way to act is four sandbox tools: `run` (a shell command in the container), `write_file`, `read_file`, `fetch_url` (fetched from inside the container). It has no host shell, no host files, no host web fetch, and none of the operator's settings, memory, skills or other tools. The harness checks the agent's tool inventory at start and voids the attempt if anything else is there. Posts say so: "Claude Code 2.1.x (sandbox tools only)".
8. **Hard caps.** Per attempt: 20 minutes wall clock, 80 turns, 900 s per command, 1 MB of output per command. Per card: two agents, plus one re-run if our side failed. Per day: 3 cards (`MAX_TESTS_PER_DAY`).

## Deliverable contract

Every task ends with one sentence the harness adds:

> When you're done, leave a script at /work/run.sh that runs the result end to end from a fresh shell and exits 0.

Before the check runs, the harness kills every process the agent left running, so a background server can't make an incomplete `run.sh` pass.

## Attempts

- **Attempt 1:** Claude Code with `claude-sonnet-5-5`.
- **Attempt 2, only if attempt 1 failed the check:** Codex CLI with `gpt-6-astra`, a different model family, in a fresh container, same task, same tools.
- An attempt that died for **our** reasons (API error, harness error, tool inventory not sandbox-only, the agent never ran a tool) is *invalid*: it's re-run once with the same agent and never counts for or against the tool.

## Verdicts

| Verdict | When |
|---|---|
| **works** | The first valid attempt passed the check, with sound evidence. |
| **partly** | The first agent failed and the second passed, or the first passed only after leaving the docs (issue trackers, Q&A sites, forums). |
| **couldn't** | Two agents from different model families both made valid attempts and both failed the check. Provisional: the writer must point to the step where they got stuck, with the quote, or it becomes inconclusive. |
| **inconclusive** | Everything else: the decoy passed, no valid attempt, a pass without sound evidence, or not enough valid attempts for a failure. |

**Sound evidence for a pass:** the check passed, the pinned version is installed in the box (the card's probe or the installed package metadata shows it), and files in `/work` reference the tool. Failures don't need those (a tool that won't install has no installed version); they need a real transcript, the agent stopping on its own or at a cap, and the check having run.

**The writer can only move a verdict toward inconclusive, never up.** Publishing "inconclusive" is fine and expected. Guessing is not.

## Cost and time

- Minutes to success: wall clock from the first attempt's start to the passing attempt's end.
- Dollars: Claude Code reports an API-equivalent cost for its run; we print it as that. Codex runs on a ChatGPT login and reports tokens, not dollars; we print tokens. Never a made-up dollar figure.

## Wording

- "An agent couldn't…", "Claude Code with Sonnet 5.5 got stuck at…". Never "it's broken", "the docs are wrong", "don't use it".
- Name the step, quote the error, link the doc page. Separate what the docs said from what the agent did.
- If the agent made the mistake (misread a clear step), say so. Blaming docs for agent errors kills the publication.

## Publishing and the record

- Raw runs stay on the test machine, outside this repo. A redaction pass (keys, tokens, emails, home paths, host names, private addresses) makes the public copy, and the writer only ever reads that.
- Nothing about a run is committed here until NJ approves its post. Then the redacted result goes into `results/` (CC BY 4.0), and the post and how-to guide go live.
- The first ~10 posts are approved one by one. After that, `works` / `partly` / `couldn't` may auto-publish under the abstain rules; `inconclusive` goes into a weekly roundup.

## Corrections and independence

- Vendors and readers request corrections by opening an issue here (template: "Correction request"). NJ owns every correction and dispute. A correction re-runs the test on the stated version and adds a dated note to the post; the old result stays in `results/`.
- Sponsors never touch selection, tests, verdicts or wording. A sponsor's tools aren't tested while they sponsor. No tested vendor is ever a sponsor.
