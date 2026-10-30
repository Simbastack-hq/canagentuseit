#!/usr/bin/env bash
# Run a comparison job: every product with each agent. One agent's three products run side by side
# (same load for each), then the next agent. Then the public copies and the comparison table.
#   tools/run_job_all.sh <job-id> [out-dir]
set -uo pipefail
cd "$(dirname "$0")/.."
JOB="jobs/$1"; OUT="${2:-$HOME/caui-runs/jobs/$(date -u +%Y-%m-%d)-$1}"
mkdir -p "$OUT"; chmod 700 "$OUT"
products=$(python3 -c 'import json,sys;print(" ".join(p["key"] for p in json.load(open(sys.argv[1]))["products"]))' "$JOB/job.json")
agents=$(python3 -c 'import json,sys;print(" ".join(json.load(open(sys.argv[1]))["agents"]))' "$JOB/job.json")
for a in $agents; do
  for p in $products; do
    python3 tools/run_job.py "$JOB" "$p" "$a" "$OUT/$p-$a" >"$OUT/$p-$a.log" 2>&1 &
  done
  wait
done
for d in "$OUT"/*/; do python3 tools/redact.py "$d" || echo "redaction refused for $d"; done
python3 tools/compare.py "$OUT"
