# Can an Agent Use It?

canagentuseit.com. For each notable AI dev launch (SDK, model API, MCP server, CLI, agent framework), an agent follows the official quickstart in a fresh sandbox, using only the docs, and we publish what happened: worked or not, where it broke, minutes and dollars to first success, and the full transcript.

- **[SPEC.md](SPEC.md)**: what a test is, verdicts, wording, evidence and abstain rules, sponsors. Binding on everything else here.
- **[WATCHLIST.md](WATCHLIST.md)**: where the scout looks and what's eligible.
- **[schema/](schema/)**: the test card (scout output) and the result (harness output).
- **[prompts/](prompts/)**: scout, tester (what the agent gets, which is almost nothing) and writer.
- **[sandbox/](sandbox/)**: the test image, the in-container entry point, the host-side harness `run-card.sh`, and the docs-walk recorder.
- **[tools/](tools/)**: `cards.py` (validate, dedupe, next, brief), `transcript.py`, `verdict.py` (mechanical verdicts), `post_draft.py` (SlopIt drafts).
- **cards/**: `queue/`, `done/`, `skipped/`. One JSON per card.
- **results/**: one folder per run: `result.json`, `brief.json`, `task.txt`, and per attempt the stream-json transcript, a readable `transcript.md`, the asciinema `terminal.cast`, the check output and the version probe. Videos and `/work` tarballs stay on the lab (gitignored). This history, same tool across versions and dates, is the point.

## Pipeline

```
caui-scout (12h) ──cards/queue──▶ caui-test ──brief only──▶ sandbox (fresh container, test key only)
                                     │                         attempt 1 Sonnet 5.5, retry Opus 5.5
                                     ◀────────── results/<run>/ ◀─┘
caui-write ──▶ SlopIt DRAFT on canagentuseit ──▶ Telegram preview link ──▶ NJ approves (first ~10)
```

The jobs run on NJ's lab box; their wiring and the sandbox's isolation live in the private infra repo, not here.

## Run one card by hand

```bash
python3 tools/cards.py validate cards/queue/<id>.json
python3 tools/cards.py brief cards/queue/<id>.json > /tmp/brief.json
CAUI_ENGINE=podman CAUI_IMAGE=caui-sandbox:<tag> sandbox/run-card.sh /tmp/brief.json results/$(date -u +%Y-%m-%dT%H%MZ)-<id>
```

Blog: https://canagentuseit.slopit.io (custom domain www.canagentuseit.com once DNS is in). Reader email capture comes with the SlopIt newsletter feature.
