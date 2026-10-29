#!/usr/bin/env python3
"""Attempt records and verdicts. Mechanical on purpose: no model decides a verdict here (SPEC.md).

  verdict.py attempt <brief.json> <attempt-dir> <n> <model> <image> <started_at> <wall_s> <check_exit>
  verdict.py result  <brief.json> <result-dir>
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Fetching any of these to get unstuck means the agent left the docs (verdict at best "partly").
OFF_DOCS = re.compile(r"(github\.com/[^/]+/[^/]+/(issues|discussions|pull)|stackoverflow\.com|reddit\.com|discord\.(gg|com)|news\.ycombinator\.com)")


def read(p, default=""):
    try:
        return Path(p).read_text(errors="replace")
    except FileNotFoundError:
        return default


def site(host):
    parts = (host or "").split(".")
    return ".".join(parts[-2:])


def attempt(brief_p, d, n, model, image, started, wall, check_exit):
    b = json.loads(read(brief_p))
    d = Path(d)
    f = json.loads(read(d / "facts.json", "{}") or "{}")
    out = read(d / "check.out")
    check_exit = int(check_exit)
    passed = check_exit == b["check"]["expect_exit"] and re.search(b["check"]["stdout_regex"], out, re.M) is not None
    ver = read(d / "version.out").strip()
    pinned = b["version"]["pinned"]
    docs_site = site(urlparse(b["docs_url"]).hostname)
    urls = f.get("urls_fetched", [])
    evidence = {
        "transcript_ok": bool(f.get("transcript_ok")),
        "version_seen": ver[-200:] or None,
        "version_ok": pinned in ver,
        "references_tool": bool(read(d / "references.out").strip()),
        "fetched_docs": any(site(urlparse(u).hostname) == docs_site for u in urls),
        "left_docs": [u for u in urls if OFF_DOCS.search(u)],
        "check_ran": check_exit not in (124, 125, 126, 127) or bool(out.strip()),
    }
    rec = {
        "n": int(n), "model": model, "agent": f.get("agent") or "claude-code ?", "image": image,
        "started_at": started, "wall_seconds": int(wall), "cost_usd": f.get("cost_usd"), "turns": f.get("turns"),
        "stop_reason": "timeout" if read(d / "agent.exit").strip() == "124" else f.get("stop", "error"),
        "agent_said": (f.get("final_text") or "")[:1500],
        "check": {"ran": evidence["check_ran"], "exit": check_exit, "passed": passed, "output_tail": out[-1500:]},
        "evidence": evidence,
        "urls_fetched": urls,
        "files": {k: f"attempt-{n}/{v}" for k, v in {
            "transcript": "transcript.jsonl", "transcript_md": "transcript.md",
            "terminal": "terminal.cast", "work": "work.tgz"}.items() if (d / v).exists()},
    }
    (d / "attempt.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(f"attempt {n} ({model}): check {'PASSED' if passed else 'failed'} exit={check_exit} "
          f"${rec['cost_usd']} {rec['turns']} turns {wall}s stop={rec['stop_reason']}")


def result(brief_p, rdir):
    b = json.loads(read(brief_p))
    rdir = Path(rdir)
    atts = [json.loads(read(p)) for p in sorted(rdir.glob("attempt-*/attempt.json"))]
    hard = lambda a: a["evidence"]["transcript_ok"] and a["evidence"]["check_ran"]
    sound = lambda a: hard(a) and a["evidence"]["version_ok"] and a["evidence"]["references_tool"]
    needs_review = False
    if not atts:
        verdict, why = "inconclusive", "no attempt ran (harness error)"
    elif atts[0]["check"]["passed"]:
        a = atts[0]
        if not sound(a):
            verdict, why = "inconclusive", "check passed but evidence failed: " + ", ".join(k for k in ("transcript_ok", "check_ran", "version_ok", "references_tool") if not a["evidence"][k])
        elif a["evidence"]["left_docs"]:
            verdict, why = "partly", "passed on the first attempt after leaving the docs: " + ", ".join(a["evidence"]["left_docs"][:3])
        else:
            verdict, why = "works", "first attempt passed the check"
    elif len(atts) > 1 and atts[1]["check"]["passed"]:
        a = atts[1]
        verdict, why = ("partly", "first attempt failed, retry with the second model passed") if sound(a) else \
            ("inconclusive", "retry passed but evidence failed")
    elif all(hard(a) for a in atts) and len(atts) > 1:
        verdict, why = "couldnt", "both attempts failed the check (provisional: the writer must name the blocker)"
        needs_review = True
    else:
        verdict, why = "inconclusive", "attempts failed without sound evidence (harness, network or transcript problem)"
    costs = [a["cost_usd"] or 0 for a in atts]
    walls = [a["wall_seconds"] for a in atts]
    mins = None
    for i, a in enumerate(atts):
        if a["check"]["passed"]:
            mins = round(sum(walls[: i + 1]) / 60, 1)
            break
    res = {
        "card_id": b["id"], "run_id": rdir.name, "date": rdir.name[:10],
        "tool": b["tool"], "version": b["version"], "docs_url": b["docs_url"], "task": b["task_text"],
        "attempts": atts, "verdict": verdict, "verdict_reason": why, "needs_review": needs_review,
        "evidence_ok": bool(atts) and all(sound(a) for a in atts if a["check"]["passed"]),
        "totals": {"cost_usd": round(sum(costs), 4), "minutes_to_success": mins, "wall_minutes": round(sum(walls) / 60, 1)},
        "video": sorted(str(p.relative_to(rdir)) for p in rdir.glob("video/*.webm")),
    }
    old = rdir / "result.json"
    if old.exists():
        res["post"] = json.loads(read(old)).get("post")
    old.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    print(f"VERDICT {verdict}: {why} · ${res['totals']['cost_usd']} · {res['totals']['wall_minutes']} min")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["attempt"] and len(a) == 9:
        attempt(*a[1:])
    elif a[:1] == ["result"] and len(a) == 3:
        result(*a[1:])
    else:
        sys.exit(__doc__)
