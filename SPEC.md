# What a test is

*Can an Agent Use It? (canagentuseit.com). This file is the contract every scout card, test run and post must follow. If a rule here and a prompt disagree, this file wins and the prompt gets fixed.*

## One test

A test is **one agent, one documented first task, one pinned version, one date.**

1. **The task is the tool's own first task.** Whatever the official quickstart walks you through first (install, hello world, first API call, first tool call). The scout restates it in one paragraph, as a builder would ask their agent. It adds nothing the quickstart doesn't say: no hints, no workarounds, no links beyond the docs.
2. **The success check is written before the run.** A shell command run by the harness after the agent stops, plus what its output must show. The agent never sees the check, only the goal the task states. A card without a check is not runnable.
3. **Everything is pinned.** Tool version (package version, model id, or release tag), the agent (Claude Code version + model id), the sandbox image tag, and the date. A result is about that combination only. There is no universal "works with agents" badge.
4. **Docs only.** The test agent gets the task text and the docs URL. Nothing from the scout's research reaches it: not why the tool is notable, not launch claims, not forum threads. It may follow links and fetch pages (a real agent would), but has no web search. Every URL it fetched is listed in the result.
5. **Fresh sandbox per attempt.** New container from the pinned image, empty `/work`, no secrets except the test agent's own spend-capped Anthropic key, no access to the host, the lab's other users, or private networks.
6. **Hard caps.** Per attempt: 20 minutes wall clock, $3 of API spend, 80 agent turns. Per card: 2 attempts. Per day: 3 cards (`MAX_TESTS_PER_DAY`).

## Deliverable contract (what every task ends with)

Every task text ends with the same sentence, added by the harness, not the scout:

> When you're done, leave a script at `/work/run.sh` that runs the result end to end from a fresh shell and exits 0.

The harness then runs the card's success check (usually `bash /work/run.sh`) in the same container, with a 3-minute timeout, and matches its exit code and output against the card.

## Verdicts

| Verdict | When |
|---|---|
| **works** | The first attempt passed the check. |
| **partly** | The first attempt failed and the retry with the second model passed, or the check passed only after the agent left the docs (an issue tracker, source code, a different version) to get there. |
| **couldn't** | Both attempts failed the check, the evidence checks passed, and the transcripts show a specific place where the agent got stuck. |
| **inconclusive** | Anything we can't pin on the tool: harness or network error, rate limit, a cap hit with no clear blocker, the agent quitting early, a check that turned out to be wrong. |

**Retry before failing.** No `couldn't` without a second attempt on a second model (primary `claude-sonnet-5-5`, retry `claude-opus-5-5`) in a fresh container.

**Abstain when the evidence doesn't hold.** The harness runs evidence checks on every attempt. If any fails, the verdict is `inconclusive` and the writer does not draft a verdict post:

- the transcript and the result JSON exist and parse;
- the installed tool version matches the pinned one (`version_probe` on the card);
- `/work/run.sh` references the tool (`must_reference` strings appear in `/work`), so an `echo` can't pass;
- the success check itself ran (exit code recorded).

Whether the agent opened the docs at all is recorded (`fetched_docs`) and said in the post, but isn't an abstain trigger: an agent that already knows the tool and gets it right still counts.

When both attempts fail, the harness's `couldnt` is provisional. The writer must point to the step where the agent got stuck, with the quote; if it can't, it downgrades to `inconclusive`. The writer can only move a verdict toward `inconclusive`, never up.

Publishing "inconclusive" is fine and expected. Guessing is not.

## Wording

- Always "an agent couldn't…", "Claude Code with Sonnet 5.5 got stuck at…". Never "it's broken", "the docs are wrong", "don't use it".
- Name the step, quote the error, link the doc page. Separate what the docs said from what the agent did.
- If the agent made the mistake (misread a clear step), say so. Blaming docs for agent errors kills the publication.
- Every post carries the full transcript, the pinned versions, the date, minutes and dollars.

## Money and independence

- Sponsors never touch selection, tests, verdicts or wording. A sponsor's own tools are not tested while they sponsor, and the post says so if one was tested before.
- No tested vendor is ever a sponsor.
- Vendor disputes and corrections go to NJ. A correction re-runs the test on the new version and adds a dated note to the post; the old result stays in `results/`.

## What gets published

- The first ~10 posts are drafts that NJ approves on Telegram. After that, `works` / `partly` / `couldn't` auto-publish; `inconclusive` goes into a weekly roundup, not its own post.
- `results/` keeps every run, published or not. That history (same tool, many versions, many dates) is the asset.
- Later formats, same rules: 30-day "did it hold up" revisits test the specific `launch_claims` the scout recorded (no overall score), and a weekly silent-changes roundup.
