#!/usr/bin/env python3
"""Line up every run of one comparison job: which check steps passed, time, cost, turns, docs read.

  compare.py <job-run-dir>      reads <job-run-dir>/<product>-<agent>/run.json (public/ copies when
                                present), writes compare.json and compare.md next to them
"""
import json
import sys
from pathlib import Path


def load(d):
    for p in (d / "public/run.json", d / "run.json"):
        if p.exists():
            return json.loads(p.read_text())


def main(root):
    root = Path(root)
    runs = [r for r in (load(d) for d in sorted(root.iterdir()) if d.is_dir()) if r and "check" in r]
    steps = []
    for r in runs:
        for s in r["check"]["steps"]:
            if s["step"] not in steps:
                steps.append(s["step"])
    cols = [f"{r['product_name']} · {r['agent'].split()[0]}" for r in runs]
    md = ["| check step | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for st in steps:
        cells = []
        for r in runs:
            s = next((x for x in r["check"]["steps"] if x["step"] == st), None)
            cells.append("—" if s is None else ("pass" if s["passed"] else "**fail**"))
        md.append(f"| {st} | " + " | ".join(cells) + " |")
    md.append("| minutes | " + " | ".join(f"{r['wall_seconds'] / 60:.1f}" for r in runs) + " |")
    md.append("| cost | " + " | ".join(f"${r['api_equiv_usd']:.2f}" if r.get("api_equiv_usd") is not None else
                                        f"{(r.get('tokens') or 0) // 1000}k tokens" for r in runs) + " |")
    md.append("| turns / tool calls | " + " | ".join(f"{r.get('turns')} / {r.get('tool_calls')}" for r in runs) + " |")
    md.append("| valid run | " + " | ".join("yes" if r["valid"] else f"no ({r['invalid_reason']})" for r in runs) + " |")
    summary = [{"product": r["product"], "agent": r["agent"], "model": r["model"], "valid": r["valid"],
                "passed_all": r["check"]["passed"], "passed": sum(s["passed"] for s in r["check"]["steps"]),
                "steps": len(r["check"]["steps"]), "failed": [s for s in r["check"]["steps"] if not s["passed"]],
                "minutes": round(r["wall_seconds"] / 60, 1), "api_equiv_usd": r.get("api_equiv_usd"),
                "tokens": r.get("tokens"), "urls_fetched": r.get("urls_fetched"), "agent_said": r.get("agent_said")}
               for r in runs]
    total = sum(r.get("api_equiv_usd") or 0 for r in runs)
    (root / "compare.json").write_text(json.dumps({"runs": summary, "claude_api_equiv_usd": round(total, 2)}, indent=2, ensure_ascii=False))
    (root / "compare.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nClaude API-equivalent total: ${total:.2f}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
