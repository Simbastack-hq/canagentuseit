**1. Sandbox v2: sound direction; insufficient isolation to trust on a secrets-bearing account.**

**Sound:** The tester container gets no host mounts or credentials. Rootless Podman, dropped capabilities, and fixed execution flags help. MCP uses argument arrays; commands execute inside the container. Run IDs cannot inject Podman options, and `shlex.quote()` protects fetch URLs against shell injection. I found no direct host-shell injection through these MCP arguments.

**Wrong/risky:**

- The host brain is the weak boundary. Claude’s `--allowedTools` controls permission, not tool availability; use `--tools ""` with the sandbox MCP. An empty directory and `--setting-sources project` do not establish that every customization is absent. [Claude CLI reference](https://code.claude.com/docs/en/cli-reference).
- Codex’s three disabled features do **not** establish “only sandbox MCP remains.” Locally installed CLI 0.160.1 reports apps, plugins, and multi-agent enabled. Inherited MCP servers, skills, memories, web tools, and delegated agents need explicit exclusion. `read-only` protects against writes, not secret reads. Current documentation also says user opt-outs of `unified_exec` are ignored—verify the pinned binary’s actual tool inventory. [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
- WebFetch bypasses the tester UID’s firewall. An injected page can request another URL through the host-side fetch path. Whether private destinations are blocked is an unverified dependency; public exfiltration remains possible. Remove it and use the container fetcher.
- Root ownership does not neutralize `CAUI_ENGINE`, `CAUI_CONF`, `CAUI_HARNESS`, runtime configuration, or executable lookup. If sudo preserves attacker-controlled overrides, `CAUI_ENGINE=/path/to/program` executes that program as `caui-tester`; an attacker-controlled image setting can enter Podman’s option parser. These are conditional deployment vulnerabilities, not demonstrated MCP exploits.
- `put/get` follow symlinks outside `/work`; those remain container paths without host mounts. However, a compromised recorder could place a host-targeting symlink at `/video/docs-walk.webm`, which the wrapper subsequently reads on the host.
- `capture_output=True` buffers unlimited output **before** truncation: `yes` can exhaust host memory. Disk usage and detached processes also outlive the claimed per-command limits.

**Change:** Move the brain to a dedicated account or VM containing only its necessary login. Freeze its configuration and assert the exposed tool inventory. Use an environment-scrubbed, absolute-path wrapper with immutable image digests; separate administrative verbs from execution privileges. Stream bounded output, enforce disk quotas and whole-container deadlines, and safely export artifacts. Commit and test the actual sudoers/firewall rules—including IPv6, DNS, redirects, host addresses, and recorder traffic. `--no-map-gw` alone is not an egress policy. I cannot certify deployed isolation from the supplied files.

**2. Test and verdict rules: good editorial discipline; weak measurement.**

**Sound:** Predetermined goals, fresh attempts, retained transcripts, independent retries, abstention, and a writer unable to upgrade outcomes are strong foundations.

**Wrong/risky:**

- `must_reference` proves text exists, not execution. A comment containing the package name plus `echo` can pass. Output regexes reward imitation; a wrong regex rejects valid behavior.
- Universal installed-version/reference requirements erase genuine installation failures: the tool cannot install, therefore evidence fails, therefore no `couldnt`.
- The implementation already contradicts the contract: [`verdict.py`](../../tools/verdict.py) permits `couldnt` using `hard()`, omitting version/reference checks; `evidence_ok` checks only successful attempts and becomes true when none succeeded.
- A network outage followed by success becomes `partly`, penalizing the tool for infrastructure. `partly` also conflates model sensitivity with external assistance. SPEC still names Sonnet→Opus, contradicting the proposed second-family retry.
- Official quickstarts often link source examples. Reading those should not automatically count as leaving the docs. Conversely, URL-pattern detection misses downloaded source, redirects, and MCP fetches; the current transcript parser misses the new MCP calls.
- The hidden check must test the stated outcome, not an unstated filename, exact wording, or dependency layout. Running in the same container also permits leftover processes to mask an incomplete `run.sh`.
- Not fetching docs means you measured prior model knowledge, not necessarily quickstart usability.

**Change:** Validate each checker against a known-good implementation and deliberately fake output. Check observable behavior with independent inputs. Separate evidence integrity from stage-specific failure evidence; record infrastructure invalidation, each model’s outcome, and assistance separately. Define permitted documentation sources, preserve fetched content and image digests, and report prior-knowledge successes explicitly. Reconcile schema, harness, and spec; record subscription cost as unknown. Keep downgrade-only writing, with human-reviewed checker corrections.

**3. Scout eligibility: transparent, but structurally incumbent-biased.**

**Sound:** Published constraints, explicit waiting states, and selection separated from testing.

**Wrong/risky:** Watched vendors qualify automatically and jump the queue; smaller projects need popularity. Stars/points invite gaming. Launch-only selection misses useful mature tools and consequential patch/docs changes. Four key-blocked launches demonstrate a mismatch between discovery and execution—not four tool failures.

**Change:** Make v1 explicitly **credential-free quickstarts**. Keep `needs_key` as coverage data, without verdicts; never substitute a fake API call. Add a documented mature-tool backlog, smaller-project nominations, category/vendor quotas, and aging priority. Publish exclusions. Later introduce separately labelled pre-provisioned-credential tests, reconciling that policy with v2’s no-secrets promise.

**Must fix before the first 10 posts:**

1. Isolate the brain and verify its complete tool inventory.
2. Harden wrapper/environment/artifact handling; test firewall boundaries and resource exhaustion.
3. Replace imitation-friendly checks and repair evidence/verdict contradictions.
4. Freeze retry, documentation, provenance, and cost-reporting rules.
5. Declare credential-free v1 scope and publish selection/exclusion records.
