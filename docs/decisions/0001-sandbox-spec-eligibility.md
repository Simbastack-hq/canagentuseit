# 0001: Sandbox v2, verdict rules, v1 eligibility (2026-10-30)

**Decided:** the agent's brain runs on the lab host with the CLI logins it already has (NJ: no API key anywhere near the sandbox); its only shell is a throwaway, credential-free container reached through a fixed wrapper. Retry uses a different model family (Codex). v1 tests credential-free quickstarts only.

Inputs: NJ's instructions (via the parent session), the proposal (`0001-proposal-sandbox-v2.md`), GPT Astra's review (`0001-astra-review.md`, gpt-6-astra via `codex exec`, read-only, same day).

## Astra's points and what we did

| Astra said | Decision | How |
|---|---|---|
| `--allowedTools` controls permission, not availability; an empty dir + `--setting-sources project` doesn't prove the tool set | **Adopted** | Claude runs with `--tools ""` (no built-ins at all), `--strict-mcp-config` with only the sandbox server. The harness reads the init event's tool list and MCP servers and kills the attempt (invalid) if anything besides the four sandbox tools is there. We saw why: without `--tools ""` the CLI exposed ~15 extra tools (Artifact, PushNotification, RemoteTrigger…). |
| Codex: three disabled features don't prove "only sandbox MCP"; read-only stops writes, not reads | **Adopted** | The harness disables every non-essential feature the installed Codex has (shell_tool, unified_exec, view_image, apps, plugins, multi_agent, browser/computer use, skills, hooks, goals, …), turns web search off, and voids the attempt on any non-sandbox tool event (command_execution, web_search, file_change, another MCP server). Verified on 0.160: a run used only `fetch_url`, `run`, `write_file`. Lab has no user `config.toml`, so no inherited MCP servers. |
| WebFetch on the host bypasses the tester's egress firewall (SSRF into the tailnet, exfil) | **Adopted** | Host WebFetch removed. Both agents fetch through `fetch_url`, which runs `curl` inside the container, under the uid egress filter. |
| caui-box trusts `CAUI_ENGINE`/`CAUI_CONF`/`CAUI_HARNESS` and the image file | **Adopted** | Under sudo the wrapper ignores the caller's environment: `/usr/bin/podman`, HOME from passwd, fixed paths, PATH reset; image tags must match `caui-(sandbox|recorder):YYYYMMDD`. sudo's `env_reset` already drops them; this makes it not depend on that. |
| Recorder could plant a symlink at the video path | **Adopted** | `docswalk` refuses a symlink or non-regular file and caps the read at 300 MB. |
| Unbounded output can exhaust host memory; processes outlive limits | **Adopted (partly)** | `exec` output capped at 1 MB inside the wrapper (exit code preserved, tested); the MCP server reads at most 2 MB; container lifetime 2 h + `reap`; agent processes are killed before the check. **Not done:** per-container disk quota (needs XFS project quotas on the host). Residual risk: a run filling the lab disk; mitigated by the 2 h lifetime and `reap`. |
| Brain on a secrets-bearing account; move it to a dedicated account or VM | **Rejected for now** | NJ chose the existing `claude` login. With no built-in tools and an asserted inventory, the brain has no path to host files or shell; the remaining path is a bug in the CLI's tool gating. Revisit if we ever widen the tool set, or if a CLI update changes the init inventory (the harness will catch that and void runs). A dedicated user would need two fresh CLI logins from NJ. |
| `must_reference` proves text, not execution; regex rewards imitation | **Adopted (partly)** | Decoy run: the check runs on an untouched box first; if it passes there the card is void. Scout prompt now asks for checks on values the tool computes, not words from the task. Full behavioural checks with independent inputs are a scout-quality goal, reviewed in the first 10 posts. |
| Installed-version evidence erases real install failures | **Adopted** | Failures no longer need version/reference evidence; they need a valid attempt (real transcript, agent stopped on its own or at a cap, check ran). Pass evidence still needs version + reference. |
| `evidence_ok` true when nothing passed; `couldnt` skipped evidence | **Adopted** | Rewritten: `evidence_ok` means the evidence for *this* verdict holds. `couldnt` now needs two valid failures from two model families. |
| Infra outage then success becomes `partly` | **Adopted** | Invalid attempts (API/harness/inventory/never ran a tool) don't count and are re-run once with the same agent. `partly` only follows a valid failure. |
| Reading quickstart-linked source shouldn't count as leaving the docs; MCP fetches were missed | **Adopted** | Off-docs = issue trackers, PRs, Q&A sites, forums only. URLs from `fetch_url` and `curl` in commands are now captured. |
| Leftover processes can mask an incomplete run.sh | **Adopted** | `kill -9 -1` as `dev` before the check. |
| No docs fetched = prior knowledge | **Adopted** | `prior_knowledge` flag in the result; the writer must say it. |
| Subscription cost isn't a dollar figure | **Adopted** | Claude's figure is printed as "API-equivalent"; Codex shows tokens. No invented dollars. |
| SPEC still said Sonnet → Opus | **Fixed** | SPEC rewritten: Claude Code → Codex. |
| Scout eligibility is incumbent-biased; 4/4 first cards were key-blocked | **Adopted** | v1 = credential-free quickstarts; keyed launches are coverage data, never tested with substitutes. Three routes to "notable" (launch, backlog, nomination), max 2 cards per vendor per week, age not vendor sets priority, skipped cards public. |
| Freeze the brain's config / pin image digests | **Partly** | Image tags are dated and recorded per attempt; digest pinning is a follow-up. Claude/Codex versions are recorded per attempt from their own output. |

## Still open
- Egress filter and sudoers are untested until NJ runs `setup-root.sh` (its self-check covers internet, tailnet, this box, docker host; IPv6 rules are in but not self-checked).
- Disk quota per container.
