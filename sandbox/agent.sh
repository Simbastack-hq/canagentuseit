#!/usr/bin/env bash
# Runs INSIDE the sandbox as `dev`, under `asciinema rec`. The agent gets the task text and nothing
# else: no system prompt of ours, no settings, no MCP servers, no web search. Caps come from env.
set -uo pipefail
: "${CAUI_MODEL:?}" "${CAUI_MAX_TURNS:=80}" "${CAUI_BUDGET_USD:=3}" "${CAUI_TIME_LIMIT_S:=1200}"
cd /work
printf '\033[1m$ claude -p "<task>" --model %s\033[0m\n\n' "$CAUI_MODEL"
sed 's/^/  /' /caui/task.txt; echo
timeout --signal=INT --kill-after=30 "$CAUI_TIME_LIMIT_S" \
  claude -p "$(cat /caui/task.txt)" \
    --model "$CAUI_MODEL" \
    --output-format stream-json --verbose \
    --max-turns "$CAUI_MAX_TURNS" --max-budget-usd "$CAUI_BUDGET_USD" \
    --dangerously-skip-permissions \
    --disallowedTools WebSearch \
    --setting-sources user --strict-mcp-config \
  </dev/null 2>/out/agent.stderr | tee /out/transcript.jsonl | python3 /caui/transcript.py live
echo "${PIPESTATUS[0]}" > /out/agent.exit
