# Can an Agent Use It?

**[canagentuseit.com](https://www.canagentuseit.com)** · For each notable AI dev launch (SDK, MCP server, CLI, agent framework, model runtime), a coding agent follows the official quickstart in a fresh sandbox, using only the docs, and we publish what happened: whether it worked, where it broke, how long it took, and the full transcript.

Everything that decides a result is in this repo: the rules, the selection, the harness, the prompts, and every approved run.

## The method, short

- **The tool's own first task.** Whatever the quickstart walks you through first. Pinned version, recorded.
- **Docs only.** The agent gets the task and the docs URL. Nothing else: no notes on why the tool matters, no forum threads, no web search.
- **A fresh, credential-free sandbox.** A new container per attempt, empty `/work`, no keys or logins inside, no access to the host or private networks. The agent's brain runs outside; its only way to act is four tools that run inside the container (`run`, `write_file`, `read_file`, `fetch_url`).
- **The success check is fixed before the run, and hidden.** The agent sees the goal, never the check. The check also runs on an untouched box first and must fail there, so it can't mistake an error message for success.
- **Two model families before any failure.** Claude Code first; if it fails, Codex in a fresh container. A "couldn't" needs both to fail. Anything we can't pin on the tool is "inconclusive", and we publish those too.
- **Careful wording.** "An agent couldn't…", never "it's broken". If the agent misread a clear step, the post says so.

The full contract is [SPEC.md](SPEC.md). What gets tested, and why, is [WATCHLIST.md](WATCHLIST.md). The reasoning behind each rule, including an outside review by GPT, is in [docs/decisions/](docs/decisions/).

## What's here

| Path | What |
|---|---|
| [SPEC.md](SPEC.md) | What a test is, verdicts, evidence and abstain rules, wording, corrections, sponsors |
| [WATCHLIST.md](WATCHLIST.md) | Where the scout looks, eligibility, balance rules, the backlog |
| [cards/](cards/) | Test cards: `queue/` (upcoming, public on purpose), `done/`, `skipped/` (with reasons) |
| [results/](results/) | One folder per approved run: result, task, per-attempt transcripts and tool-call logs (CC BY 4.0) |
| [schema/](schema/) | The test card and result formats |
| [prompts/](prompts/) | Scout, tester (what the agent gets, which is almost nothing) and writer |
| [sandbox/](sandbox/) | The test image, `caui-box` (the only door into a container), the docs B-roll recorder |
| [tools/](tools/) | `run_card.py` (the harness), `sandbox_mcp.py`, `verdict.py` (mechanical verdicts), `redact.py`, `cards.py`, `post_draft.py`, `render/` (video from a run) |

## Reproduce a run

You need Docker or Podman, Python 3.11+, and Claude Code and/or Codex CLI logged in on your machine (the brain runs on your machine; nothing of yours goes into the container).

```bash
git clone https://github.com/Simbastack-hq/canagentuseit && cd canagentuseit
# build the sandbox image (tagged caui-sandbox:YYYYMMDD; every result records the tag)
CAUI_ENGINE=docker CAUI_HARNESS=$PWD ./sandbox/caui-box build
# one card: decoy check, Claude Code, then Codex if Claude fails, then the verdict
python3 tools/cards.py brief cards/done/<card-id>.json > /tmp/brief.json
CAUI_BOX="env CAUI_ENGINE=docker $PWD/sandbox/caui-box" python3 tools/run_card.py /tmp/brief.json /tmp/runs/$(date -u +%Y-%m-%dT%H%MZ)-<card-id>
```

The run folder has the raw agent stream, normalized events, every sandbox call with timings, the check output and `result.json`. `tools/redact.py <run-dir>` makes the shareable copy. Your result will differ from ours if the tool, the model or the date differs; that's why they're pinned.

## Corrections

Think a result is wrong, unfair, or fixed in a newer version? [Open a correction request](https://github.com/Simbastack-hq/canagentuseit/issues/new?template=correction.yml). A person reads every one. We re-run the same task on the version you name and add a dated note to the post; the original result stays in `results/`. Suggest a tool to test with [Nominate a tool](https://github.com/Simbastack-hq/canagentuseit/issues/new?template=nominate.yml).

## Independence

Sponsors never touch selection, tests, verdicts or wording, and no tested vendor is ever a sponsor. Results are about one agent, one version, on one date. There is no "works with agents" badge.

## Licences

- Code, prompts, spec and docs: [MIT](LICENSE).
- Results (`results/`: verdict JSON, transcripts, tool-call logs): [CC BY 4.0](results/LICENSE). Cite with a link to the post or the run folder.

## Contributing

Run `git config core.hooksPath .githooks` once: the pre-commit hook blocks secrets and machine details (gitleaks if installed, plus the redaction patterns). Never commit a raw run; only `tools/promote.py` puts redacted, approved runs into `results/`.
