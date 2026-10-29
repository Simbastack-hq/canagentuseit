#!/usr/bin/env python3
"""Attempt records and verdicts. Mechanical on purpose: no model decides a verdict here (SPEC.md).

  verdict.py attempt <brief.json> <attempt-dir> <n> <model> <image> <started_at> <wall_s> <check_exit>
  verdict.py result  <brief.json> <run-dir>

Attempt validity is separate from the tool's outcome. An attempt is *invalid* (never counts for or
against the tool) when our side failed: the API or harness errored, the tool inventory wasn't
sandbox-only, or the agent never got going. A *valid failure* needs a real transcript, the agent
stopping on its own or at a cap, and the check having run.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Reading these to get unstuck means the agent left the docs. Source code and examples the docs link to don't count.
OFF_DOCS = re.compile(r"(github\.com/[^/]+/[^/]+/(issues|discussions|pull)|stackoverflow\.com|reddit\.com|discord\.(gg|com)|news\.ycombinator\.com)")


def read(p, default=""):
    try:
        return Path(p).read_text(errors="replace")
    except FileNotFoundError:
        return default


def site(host):
    return ".".join((host or "").split(".")[-2:])


def attempt(brief_p, d, n, model, image, started, wall, check_exit):
    b = json.loads(read(brief_p))
    d = Path(d)
    f = json.loads(read(d / "facts.json", "{}") or "{}")
    out = read(d / "check.out")
    check_exit = int(check_exit)
    passed = check_exit == b["check"]["expect_exit"] and re.search(b["check"]["stdout_regex"], out, re.M) is not None
    ver = read(d / "version.out")
    pinned = b["version"]["pinned"]
    docs_site = site(urlparse(b["docs_url"]).hostname)
    urls = f.get("urls_fetched", [])
    stop = "timeout" if read(d / "agent.exit").strip() == "124" else f.get("stop", "error")
    invalid = read(d / "invalid.txt").strip() or read(d / "harness-error.txt").strip()
    if not invalid and stop in ("api_error", "error"):
        invalid = f"agent stopped with {stop}"
    if not invalid and not f.get("transcript_ok"):
        invalid = "no transcript"
    if not invalid and (f.get("tool_calls") or 0) == 0:
        invalid = "the agent never ran a tool"
    evidence = {
        "transcript_ok": bool(f.get("transcript_ok")),
        "version_seen": ver.strip()[-300:] or None,
        "version_ok": re.search(rf"(?<![\d.]){re.escape(pinned)}(?![\d])", ver) is not None,
        "references_tool": bool(read(d / "references.out").strip()),
        "fetched_docs": any(site(urlparse(u).hostname) == docs_site for u in urls),
        "left_docs": [u for u in urls if OFF_DOCS.search(u)],
        "check_ran": check_exit not in (125, 126) and (check_exit != 127 or "No such file" in out),
    }
    rec = {
        "n": int(n), "model": model, "agent": f.get("agent") or "?", "image": image,
        "started_at": started, "wall_seconds": int(wall),
        "api_equiv_usd": f.get("cost_usd"),  # Claude Code's own estimate; None for Codex (ChatGPT login)
        "tokens": f.get("tokens"), "turns": f.get("turns"), "tool_calls": f.get("tool_calls"),
        "stop_reason": stop, "valid": not invalid, "invalid_reason": invalid or None,
        "agent_said": (f.get("final_text") or "")[:1500],
        "check": {"ran": evidence["check_ran"], "exit": check_exit, "passed": passed, "output_tail": out[-1500:]},
        "evidence": evidence,
        "urls_fetched": urls,
        "files": {k: f"attempt-{n}/{v}" for k, v in {
            "raw": "raw.jsonl", "events": "events.jsonl", "box_log": "box-log.jsonl",
            "transcript_md": "transcript.md", "work": "work.tgz"}.items() if (d / v).exists()},
    }
    (d / "attempt.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(f"attempt {n} ({model}): check {'PASSED' if passed else 'failed'} exit={check_exit} "
          f"{rec['tool_calls']} calls {wall}s stop={stop}{' INVALID: ' + invalid if invalid else ''}")


def result(brief_p, rdir):
    b = json.loads(read(brief_p))
    rdir = Path(rdir)
    atts = [json.loads(read(p)) for p in sorted(rdir.glob("attempt-*/attempt.json"), key=lambda p: int(p.parent.name.split("-")[1]))]
    decoy = json.loads(read(rdir / "decoy.json", "{}") or "{}")
    valid = [a for a in atts if a["valid"]]
    sound_pass = lambda a: a["check"]["passed"] and a["evidence"]["version_ok"] and a["evidence"]["references_tool"]
    valid_fail = lambda a: not a["check"]["passed"] and a["evidence"]["check_ran"]
    needs_review, evidence_ok = False, False
    first_pass = next((i for i, a in enumerate(valid) if a["check"]["passed"]), None)
    if decoy.get("passed"):
        verdict, why = "inconclusive", "the success check passed on an untouched box (decoy), so it can't tell success from failure; card needs a better check"
    elif not valid:
        verdict, why = "inconclusive", "no valid attempt (API, harness or tool-inventory failure): " + "; ".join(a.get("invalid_reason") or "" for a in atts)
    elif first_pass is not None:
        a = valid[first_pass]
        if not sound_pass(a):
            miss = [k for k in ("version_ok", "references_tool") if not a["evidence"][k]]
            verdict, why = "inconclusive", f"check passed but evidence failed ({', '.join(miss)}): can't confirm the pinned tool did the work"
        elif first_pass > 0:
            prior = valid[0]
            verdict, why = "partly", f"the first agent ({prior['agent']}, {prior['model']}) didn't get there; the retry ({a['agent']}, {a['model']}) did"
            evidence_ok = True
        elif a["evidence"]["left_docs"]:
            verdict, why = "partly", "passed on the first attempt after leaving the docs: " + ", ".join(a["evidence"]["left_docs"][:3])
            evidence_ok = True
        else:
            verdict, why = "works", "the first agent passed the check"
            evidence_ok = True
    elif len(valid) >= 2 and all(valid_fail(a) for a in valid) and len({a["agent"].split()[0] for a in valid}) >= 2:
        verdict, why = "couldnt", "two agents from different model families both failed the check (provisional: the writer must name the blocker)"
        needs_review, evidence_ok = True, True
    else:
        verdict, why = "inconclusive", "not enough valid attempts for a failure verdict (need two agents from different families)"
    walls = [a["wall_seconds"] for a in atts]
    mins = None
    for i, a in enumerate(atts):
        if a["valid"] and a["check"]["passed"]:
            mins = round(sum(walls[: i + 1]) / 60, 1)
            break
    usd = [a["api_equiv_usd"] for a in atts if a.get("api_equiv_usd") is not None]
    res = {
        "card_id": b["id"], "run_id": rdir.name, "date": rdir.name[:10],
        "tool": b["tool"], "version": b["version"], "docs_url": b["docs_url"], "task": b["task_text"],
        "decoy": decoy, "attempts": atts, "verdict": verdict, "verdict_reason": why, "needs_review": needs_review,
        "evidence_ok": evidence_ok,
        "prior_knowledge": first_pass is not None and not valid[first_pass]["evidence"]["fetched_docs"],
        "totals": {"api_equiv_usd": round(sum(usd), 4) if usd else None,
                   "tokens": sum(a.get("tokens") or 0 for a in atts),
                   "minutes_to_success": mins, "wall_minutes": round(sum(walls) / 60, 1)},
        "video": sorted(str(p.relative_to(rdir)) for p in rdir.glob("video/*.webm")),
        # Set when a run didn't use the standard sandbox; the post must say so up front.
        "fallback": read(rdir / "fallback.txt").strip() or None,
    }
    old = rdir / "result.json"
    if old.exists():
        res["post"] = json.loads(read(old)).get("post")
    old.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    print(f"VERDICT {verdict}: {why} · {res['totals']['wall_minutes']} min")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["attempt"] and len(a) == 9:
        attempt(*a[1:])
    elif a[:1] == ["result"] and len(a) == 3:
        result(*a[1:])
    else:
        sys.exit(__doc__)
