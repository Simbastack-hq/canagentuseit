# Proposal: sandbox v2, brain outside, container as the only shell (2026-10-30)

NJ's call: no API key anywhere near the sandbox. The agent's brain runs on the lab host as the
existing `claude` Linux user with its logged-in Claude CLI (and Codex CLI for the retry). Its only
way to act is a throwaway container.

## Shape
- `caui-tester`: a separate Linux user, rootless podman, no secrets at all, no sudo, no docker.
  Egress filter by uid (nftables): internet yes; the host's own addresses, tailnet 100.64/10,
  docker/private ranges, link-local, loopback (except DNS stub) rejected.
- `sandbox/caui-box`: root-owned wrapper in /usr/local/bin. sudoers lets `claude` run exactly
  `sudo -u caui-tester /usr/local/bin/caui-box ...` and nothing else as that user. Verbs: start
  (fixed flags: --cap-drop ALL, no-new-privileges, 2 CPU, 4 GB, 1024 pids, pasta --no-map-gw),
  exec (timeout 1-900 s, bash -lc as `dev` in /work), put/get (paths under /work or /tmp only),
  tarwork, rm, docswalk (separate Playwright container), build, reap (>2h).
- `tools/sandbox_mcp.py`: stdio MCP server on the host exposing run / write_file / read_file /
  fetch_url, each implemented as a caui-box call. No host file or shell access in the server.
- Attempt 1, Claude Code (host, user `claude`): `claude -p <task> --model claude-sonnet-5-5
  --permission-mode dontAsk --strict-mcp-config --mcp-config <sandbox only>
  --allowedTools mcp__sandbox__* WebFetch --disallowedTools Bash Read Write Edit Glob Grep
  NotebookEdit WebSearch Task --setting-sources project` in an empty per-run scratch dir, so none
  of NJ's CLAUDE.md, memory, skills, hooks or other MCP servers load. A fixed appended system
  prompt says the work happens on a remote box reachable only via these tools.
- Attempt 2 (retry, different model family, only if attempt 1 fails the check): Codex CLI
  `codex exec --json -m gpt-6-astra -s read-only --disable shell_tool --disable unified_exec
  --disable view_image -c mcp_servers.sandbox=...` in an empty scratch dir. Its own shell is off;
  only the sandbox MCP tools remain (fetch_url covers docs since Codex web search is broken on
  the lab).
- Success check, version probe and must_reference run through caui-box after the agent stops; the
  agent never sees the check.
- Everything raw (timestamped stream-json / codex JSON, MCP call log with wall-clock start/end,
  check output, /work tarball, docs-walk video) lands in ~/caui-runs/<run>/ on the lab, outside
  the repo. A redaction pass makes <run>/public/; the writer only reads public/. Nothing reaches
  the public repo's results/ until NJ approves the post.

## Known trade-offs
- The agent is no longer stock Claude Code: its shell is an MCP tool, and file edits go through
  write_file/run. Results must say "Claude Code <ver> (sandbox tools)" and the method page must say
  so. Claude keeps WebFetch (host-side fetch of public pages; its context holds no secrets).
- Host-side brain: a prompt-injected agent could try to use WebFetch to leak what's in its context
  (the task, docs, command output). No credentials are in that context.
- Codex on a ChatGPT login: cost per run isn't metered; we record tokens.
