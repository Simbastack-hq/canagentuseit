#!/usr/bin/env python3
"""Test-card plumbing. Stdlib only (schema validation uses `jsonschema` if it's importable).

  cards.py validate <card.json>...    schema + rule checks; exit 1 on any error
  cards.py known                      one line per card/result already on file (scout dedupe)
  cards.py next                       path of the next eligible queued card, or nothing (respects the daily cap)
  cards.py brief <card.json>          the tester's input: card minus everything the scout researched
  cards.py mark <card.json> <status> [reason]   set status; done/skipped cards move to cards/done|skipped
"""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE, DONE, SKIPPED, RESULTS = ROOT / "cards/queue", ROOT / "cards/done", ROOT / "cards/skipped", ROOT / "results"
MAX_TESTS_PER_DAY = int(os.environ.get("MAX_TESTS_PER_DAY", "3"))
KEYS = ROOT / "keys.json"
CONTRACT = "When you're done, leave a script at /work/run.sh that runs the result end to end from a fresh shell and exits 0."
# Fields the tester may see. Everything else on the card (scout, eligibility) never leaves the host.
BRIEF_FIELDS = ("id", "tool", "version", "docs_url", "brief", "check")


def load(p):
    with open(p) as f:
        return json.load(f)


def save(p, d):
    tmp = Path(str(p) + ".tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(p)


def validate(path):
    errs = []
    try:
        card = load(path)
    except Exception as e:
        return [f"not JSON: {e}"]
    try:
        import jsonschema
        schema = load(ROOT / "schema/test-card.schema.json")
        for e in jsonschema.Draft202012Validator(schema).iter_errors(card):
            errs.append(f"schema: {'/'.join(map(str, e.path))}: {e.message}")
    except ImportError:
        for k in ("id", "tool", "version", "docs_url", "brief", "check", "eligibility", "scout"):
            if k not in card:
                errs.append(f"missing {k}")
    if errs:
        return errs
    v = card["version"]["pinned"]
    if v.lower() in ("latest", "main", "head", "*", ""):
        errs.append("version.pinned must be exact, not 'latest'")
    task = card["brief"]["task"]
    if v not in task:
        errs.append(f"brief.task must name the pinned version {v!r}")
    if CONTRACT.split(",")[0] in task:
        errs.append("brief.task must not include the run.sh contract; the harness adds it")
    for u in re.findall(r"https?://\S+", task):
        if u.rstrip(".,)") != card["docs_url"]:
            errs.append(f"brief.task links {u}; only docs_url may appear (or none)")
    if not card["check"].get("decoy_script") and card["created_at"] >= "2026-10-30":
        errs.append("check.decoy_script is required: a plausible but wrong run.sh the check must reject")
    try:
        re.compile(card["check"]["stdout_regex"])
    except re.error as e:
        errs.append(f"check.stdout_regex doesn't compile: {e}")
    el = card["eligibility"]
    if not (el["public_docs"] and el["agent_builder_relevant"] and el["runnable_in_sandbox"]) or el["needs_signup"]:
        if card["status"] not in ("skipped",):
            errs.append("ineligible card must have status 'skipped' with skip_reason")
    if el.get("needs_key") and card["status"] == "queued" and el["needs_key"] not in provisioned_keys():
        errs.append(f"needs key {el['needs_key']} that isn't in keys.json: status must be 'needs_key'")
    if Path(path).stem != card["id"]:
        errs.append(f"file name must be <id>.json ({card['id']}.json)")
    return errs


def provisioned_keys():
    return set(load(KEYS).keys()) if KEYS.exists() else set()


def all_cards():
    for d in (QUEUE, DONE, SKIPPED):
        for p in sorted(d.glob("*.json")):
            yield p


def known():
    for p in all_cards():
        c = load(p)
        print(f"{c['status']}\t{c['tool']['name']}\t{c['version']['package']}\t{c['version']['pinned']}\t{c['created_at'][:10]}\t{p.relative_to(ROOT)}")
    for r in sorted(RESULTS.glob("*/result.json")):
        res = load(r)
        print(f"result:{res['verdict']}\t{res['tool'].get('name')}\t{res['version'].get('package')}\t{res['version'].get('pinned')}\t{res['date']}\t{r.parent.relative_to(ROOT)}")


def tests_today():
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    return sum(1 for r in RESULTS.glob(f"{today}*/result.json"))


def next_card():
    if tests_today() >= MAX_TESTS_PER_DAY:
        return
    keys = provisioned_keys()
    queued = []
    for p in sorted(QUEUE.glob("*.json")):
        c = load(p)
        if c["status"] == "needs_key" and c["eligibility"].get("needs_key") in keys:
            c["status"] = "queued"
            save(p, c)
        if c["status"] == "queued" and not validate(p):
            queued.append((c["created_at"], p))
    if queued:
        print(min(queued)[1])


def brief(path):
    c = load(path)
    b = {k: c[k] for k in BRIEF_FIELDS}
    b["task_text"] = f"{c['brief']['task'].strip()}\n\nDocs: {c['docs_url']}\n\n{CONTRACT}"
    print(json.dumps(b, indent=2, ensure_ascii=False))


def mark(path, status, reason=None):
    p = Path(path)
    c = load(p)
    c["status"] = status
    if reason:
        c["skip_reason"] = reason
    save(p, c)
    dest = {"done": DONE, "skipped": SKIPPED}.get(status)
    if dest and p.parent != dest:
        dest.mkdir(parents=True, exist_ok=True)
        p.replace(dest / p.name)
        print(dest / p.name)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["validate"] and len(a) > 1:
        bad = 0
        for p in a[1:]:
            errs = validate(p)
            print(f"{'OK ' if not errs else 'BAD'} {p}" + "".join(f"\n    - {e}" for e in errs))
            bad += bool(errs)
        sys.exit(1 if bad else 0)
    elif a == ["known"]:
        known()
    elif a == ["next"]:
        next_card()
    elif a[:1] == ["brief"] and len(a) == 2:
        brief(a[1])
    elif a[:1] == ["mark"] and len(a) in (3, 4):
        mark(*a[1:])
    else:
        sys.exit(__doc__)
