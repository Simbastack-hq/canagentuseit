#!/usr/bin/env bash
# Runs one test brief in fresh containers and writes the result folder. Never sees the scout's notes:
# its only input is a brief (tools/cards.py brief), which is the card minus the scout block.
#
# Usage: run-card.sh <brief.json> <result-dir>
# Env:
#   CAUI_ENGINE        podman (production, rootless as caui-tester) | docker (dry run)   [podman]
#   CAUI_IMAGE         sandbox image tag                                                  [caui-sandbox:latest]
#   CAUI_RECORDER      Playwright image for the docs walk                                 [caui-recorder:latest]
#   CAUI_KEY_ENV       env file holding ANTHROPIC_API_KEY=… for the test agent (0600)     [~/.config/caui/agent.env]
#   CAUI_VENDOR_KEYS   folder of <ENV_NAME> files for vendor keys a card lists            [~/.config/caui/vendor-keys]
#   CAUI_NETWORK       network for the container                                          [podman: pasta, docker: bridge]
#   CAUI_MODELS        primary and retry model                                            ["claude-sonnet-5-5 claude-opus-5-5"]
set -uo pipefail
BRIEF="$(realpath "${1:?brief.json}")"; OUT="${2:?result dir}"
HERE="$(cd "$(dirname "$0")" && pwd)"; TOOLS="$HERE/../tools"
ENGINE="${CAUI_ENGINE:-podman}"
IMAGE="${CAUI_IMAGE:-caui-sandbox:latest}"
RECORDER="${CAUI_RECORDER:-caui-recorder:latest}"
KEY_ENV="${CAUI_KEY_ENV:-$HOME/.config/caui/agent.env}"
VENDOR_KEYS="${CAUI_VENDOR_KEYS:-$HOME/.config/caui/vendor-keys}"
read -r -a MODELS <<<"${CAUI_MODELS:-claude-sonnet-5-5 claude-opus-5-5}"
TIME_LIMIT_S="${CAUI_TIME_LIMIT_S:-1200}"; BUDGET_USD="${CAUI_BUDGET_USD:-3}"; MAX_TURNS="${CAUI_MAX_TURNS:-80}"
if [ "$ENGINE" = podman ]; then NET="${CAUI_NETWORK:-pasta:--no-map-gw}"; else NET="${CAUI_NETWORK:-bridge}"; fi
[ -r "$KEY_ENV" ] || { echo "no agent key env file at $KEY_ENV" >&2; exit 2; }
mkdir -p "$OUT"; OUT="$(realpath "$OUT")"
j() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2], {}, {"d": d}))' "$BRIEF" "$1"; }

RUN_ID="$(basename "$OUT")"
cp "$BRIEF" "$OUT/brief.json"
j 'd["task_text"]' >"$OUT/task.txt"
CHECK_CMD="$(j 'd["check"]["command"]')"
PROBE_CMD="$(j 'd["check"]["version_probe"]')"
# Vendor keys this card needs (names only on the card; values from files NJ placed)
VENDOR_ARGS=()
for name in $(j '" ".join(d["brief"].get("env", []))'); do
  [ -r "$VENDOR_KEYS/$name" ] || { echo "card needs $name, not provisioned" >&2; exit 3; }
  VENDOR_ARGS+=(--env "$name=$(cat "$VENDOR_KEYS/$name")")
done

attempt() {  # attempt <n> <model>
  local n="$1" model="$2" dir="$OUT/attempt-$1" c="caui-${RUN_ID,,}-a$1"
  c="${c//[^a-z0-9-]/-}"; mkdir -p "$dir"
  local started; started="$(date -u +%FT%TZ)"; local t0; t0="$(date +%s)"
  "$ENGINE" rm -f "$c" >/dev/null 2>&1
  "$ENGINE" run -d --name "$c" --hostname sandbox --network "$NET" \
    --memory 4g --cpus 2 --pids-limit 1024 --cap-drop ALL --security-opt no-new-privileges \
    --env-file "$KEY_ENV" "${VENDOR_ARGS[@]}" \
    -e CAUI_MODEL="$model" -e CAUI_TIME_LIMIT_S="$TIME_LIMIT_S" -e CAUI_BUDGET_USD="$BUDGET_USD" -e CAUI_MAX_TURNS="$MAX_TURNS" \
    "$IMAGE" sleep infinity >/dev/null || { echo "container start failed" >"$dir/harness-error.txt"; return; }
  "$ENGINE" cp "$OUT/task.txt" "$c:/caui/task.txt"
  # The run itself, recorded. Outer timeout is a backstop for the agent's own.
  timeout --kill-after=30 $((TIME_LIMIT_S + 180)) \
    "$ENGINE" exec -u dev "$c" asciinema rec -q --overwrite --cols 110 --rows 32 -c /caui/agent.sh /out/terminal.cast \
    >"$dir/harness.log" 2>&1
  local wall=$(( $(date +%s) - t0 ))
  # The success check: written before the run, never shown to the agent.
  "$ENGINE" exec -u dev -w /work "$c" timeout 180 bash -lc "$CHECK_CMD" >"$dir/check.out" 2>&1; local check_exit=$?
  "$ENGINE" exec -u dev -w /work "$c" timeout 120 bash -lc "$PROBE_CMD" >"$dir/version.out" 2>&1
  local refs; refs="$(python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["check"]["must_reference"]))' "$BRIEF")"
  "$ENGINE" exec -u dev "$c" grep -rIlF --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git \
    -e "$refs" /work >"$dir/references.out" 2>/dev/null
  "$ENGINE" cp "$c:/out/." "$dir/" 2>/dev/null
  "$ENGINE" exec -u dev "$c" tar czf - -C /work --exclude=node_modules --exclude=.venv --exclude=.git . 2>/dev/null \
    | head -c 20000000 >"$dir/work.tgz"
  "$ENGINE" rm -f "$c" >/dev/null 2>&1
  python3 "$TOOLS/transcript.py" md "$dir/transcript.jsonl" >"$dir/transcript.md" 2>/dev/null
  python3 "$TOOLS/transcript.py" facts "$dir/transcript.jsonl" >"$dir/facts.json"
  python3 "$TOOLS/verdict.py" attempt "$BRIEF" "$dir" "$n" "$model" "$IMAGE" "$started" "$wall" "$check_exit"
}

attempt 1 "${MODELS[0]}"
if ! python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["check"]["passed"] else 1)' "$OUT/attempt-1/attempt.json"; then
  attempt 2 "${MODELS[1]}"
fi

# Docs walk for video: the docs pages the agent actually fetched, in order, in a separate browser container.
URLS="$(python3 -c '
import json, sys, glob
from urllib.parse import urlparse
b = json.load(open(sys.argv[1])); docs_host = urlparse(b["docs_url"]).hostname
urls = [b["docs_url"]]
for p in sorted(glob.glob(sys.argv[2] + "/attempt-*/facts.json")):
    for u in json.load(open(p))["urls_fetched"]:
        if urlparse(u).hostname == docs_host and u not in urls: urls.append(u)
print("\n".join(urls[:8]))' "$BRIEF" "$OUT")"
if "$ENGINE" image exists "$RECORDER" 2>/dev/null || "$ENGINE" image inspect "$RECORDER" >/dev/null 2>&1; then
  mkdir -p "$OUT/video"
  USERFLAG=(); [ "$ENGINE" = docker ] && USERFLAG=(--user "$(id -u):$(id -g)")
  "$ENGINE" run --rm "${USERFLAG[@]}" --network "$NET" --memory 2g --cpus 2 --cap-drop ALL --security-opt no-new-privileges \
    -e URLS="$URLS" -v "$OUT/video:/video" "$RECORDER" >"$OUT/video/docs-walk.log" 2>&1 \
    || echo "docs walk failed (see video/docs-walk.log)" >&2
fi

python3 "$TOOLS/verdict.py" result "$BRIEF" "$OUT"
