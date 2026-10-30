# Tester: what the test agent gets

The tester is not a prompt we write per run. It's a harness (`sandbox/run-card.sh`) that starts a fresh container and runs the agent as shipped:

```
claude -p "<task text>" --model <model> --output-format stream-json --verbose \
  --max-turns 80 --max-budget-usd 3 --dangerously-skip-permissions \
  --disallowedTools WebSearch --setting-sources user --strict-mcp-config
```

inside `timeout 1200`, recorded with `asciinema rec`. No system prompt of ours, no settings, no MCP servers, no memory: Claude Code's defaults, so the result is about Claude Code + that model, not about our prompting.

The task text is built by `tools/cards.py brief`, from three things only:

```
<card.brief.task>

Docs: <card.docs_url>

When you're done, leave a script at /work/run.sh that runs the result end to end from a fresh shell and exits 0.
```

That's the whole input. The card's `scout` and `eligibility` blocks (why it's notable, launch claims, sources, notes) never enter the brief, the container or the agent's context; `cards.py` builds the brief from an allowlist of fields (`BRIEF_FIELDS`), so a new scout field can't leak by accident. The success check is in the brief file the harness reads, but it is never copied into the container before the agent stops.

Retry: if the check fails, the same brief runs again in a new container with the second model (`CAUI_MODELS`, default `claude-sonnet-5-5` then `claude-opus-5-5`).

The box: Debian 12, Python 3.11 + uv, Node 22 + npm, git, build tools, user `dev` without sudo, 2 CPUs, 4 GB RAM, outbound internet, no access to the host or private networks, and one secret: the test agent's own spend-capped Anthropic key (plus a vendor key only if the card lists one NJ provisioned).
