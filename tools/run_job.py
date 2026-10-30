#!/usr/bin/env python3
"""Run one product of a comparison job with one agent: same spec, same box, same caps for every product.

  run_job.py <job-dir> <product-key> <claude|codex> <run-dir>

The agent gets jobs/<id>/JOB.md (filled in for the product) and the fixtures in /work/job/. When it
stops, the harness kills its processes and only then copies the hidden check into the box and runs
it. Before that, the check must fail on an untouched box and on the job's decoy (right behaviour, no
product), or the run stops: a check that can't tell those apart measures nothing.

Writes to <run-dir>: brief.json, task.txt, decoy.json, attempt-1/ (raw.jsonl, events.jsonl,
box-log.jsonl, transcript.md, facts.json, check.out, check.json, version.out, references.out,
work.tgz, work-files/), run.json. Raw stays on this machine; tools/redact.py makes public/.
"""
import json
import os
import re
import shlex
import shutil
import sys
import tempfile
import time
from pathlib import Path

JOB = json.loads((Path(sys.argv[1]) / "job.json").read_text()) if len(sys.argv) == 5 else None
if JOB:  # caps are per job and identical for every product; run_card reads them at import
    os.environ["CAUI_TIME_LIMIT_S"] = str(JOB["caps"]["minutes"] * 60)
    os.environ["CAUI_MAX_TURNS"] = str(JOB["caps"]["turns"])
import run_card as rc  # noqa: E402  (tools/ is on sys.path when run as a script)
import subprocess  # noqa: E402

CHECK_TIMEOUT = "900"


def render(job_dir, p):
    t = (job_dir / JOB["spec"]).read_text()
    for k, v in {"product": p["product"], "version": p["version"]["pinned"], "docs_url": p["docs_url"],
                 "setup_note": p.get("setup_note", "")}.items():
        t = t.replace("{" + k + "}", v)
    return t


def put_dir(cid, src, dest):
    for f in sorted(Path(src).rglob("*")):
        if f.is_file():
            rc.box("put", cid, f"{dest}/{f.relative_to(src).as_posix()}", stdin=f.read_bytes())


def run_check(cid, job_dir, p):
    rc.box("put", cid, "/tmp/check/check.py", stdin=(job_dir / JOB["check"]).read_bytes())
    # Same seed for every run of the job: every product and agent faces the same hidden workload.
    code, out, _ = rc.box("exec", cid, CHECK_TIMEOUT, f"python3 /tmp/check/check.py {p['key']} {JOB['check_seed']} "
                          f"{shlex.quote(p['version']['pinned'])}", timeout=1000)
    res = next((json.loads(l[11:]) for l in reversed(out.splitlines()) if l.startswith("CHECK_JSON ")), None)
    return code, out, res or {"passed": False, "steps": [], "error": "check printed no result"}


def decoys(job_dir, p, run_dir):
    out = []
    for kind in ["untouched box"] + [f"decoy: {m}" for m in JOB.get("decoy_modes", ["json"])]:
        cid = re.sub(r"[^a-z0-9-]", "-", f"{run_dir.name.lower()}-decoy{len(out)}")[-90:].strip("-")
        rc.box("start", cid)
        try:
            put_keys(cid, p)
            if kind.startswith("decoy"):
                put_dir(cid, job_dir / JOB["decoy"], "/work")
                rc.box("exec", cid, "30", f"chmod +x /work/docsearch /work/start.sh /work/stop.sh && echo {kind[7:]} > /work/.decoy_mode")
            code, text, res = run_check(cid, job_dir, p)
        finally:
            rc.box("rm", cid)
        out.append({"kind": kind, "exit": code, "passed": res["passed"],
                    "failed_steps": [s["step"] for s in res["steps"] if not s["passed"]], "tail": text[-800:]})
    return {"passed": any(d["passed"] for d in out), "decoys": out}


def put_keys(cid, p):
    """Throwaway keys the product declares, into this run's box only (decision 0004). Never the brain's env."""
    if not p.get("keys"):
        return
    import keys
    for v, kv in keys.load(p["keys"]).items():
        rc.box("put", cid, f"/tmp/keys/{v}.env", stdin=keys.env_file(kv).encode())
    rc.box("exec", cid, "20", "chmod 700 /tmp/keys && chmod 600 /tmp/keys/*.env")


def probe_version(cid, p):
    v = p["version"]
    if v["source"] == "pypi":
        return rc.box("exec", cid, "60", rc.generic_probe(v))[1]
    if p["key"] == "pgvector":
        return rc.box("exec", cid, "30", "grep default_version /usr/share/postgresql/17/extension/vector.control; "
                                         "dpkg -s postgresql-17-pgvector | grep ^Version")[1]
    return ""


def main():
    job_dir, key, agent, run_dir = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3], Path(sys.argv[4]).resolve()
    p = next(x for x in JOB["products"] if x["key"] == key)
    run_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(run_dir, 0o700)
    spec = render(job_dir, p)
    task = (f"Do the job described in /work/job/JOB.md, using {p['product']} {p['version']['pinned']}. "
            f"Docs: {p['docs_url']}")
    brief = {"job": JOB["id"], "job_title": JOB["title"], "product": p, "agent": agent, "task_text": task,
             "caps": JOB["caps"], "spec": spec}
    (run_dir / "brief.json").write_text(json.dumps(brief, indent=2))
    (run_dir / "task.txt").write_text(task + "\n\n--- /work/job/JOB.md ---\n" + spec)

    dec = decoys(job_dir, p, run_dir)
    (run_dir / "decoy.json").write_text(json.dumps(dec, indent=2))
    if dec["passed"]:
        (run_dir / "run.json").write_text(json.dumps({"error": "a decoy passed the check; fix the check", **brief}, indent=2))
        print("ABORT: decoy passed")
        return

    d = run_dir / "attempt-1"
    d.mkdir(exist_ok=True)
    cid = re.sub(r"[^a-z0-9-]", "-", f"{run_dir.name.lower()}-a1")[-90:].strip("-")
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()
    code, image, err = rc.box("start", cid)
    if code != 0:
        (d / "harness-error.txt").write_text(f"container start failed: {err}")
        return
    scratch = Path(tempfile.mkdtemp(prefix="caui-scratch-"))
    try:
        put_keys(cid, p)
        rc.box("put", cid, "/work/job/JOB.md", stdin=spec.encode())
        put_dir(cid, job_dir / JOB["fixtures"], "/work/job/fixtures")
        if agent == "claude":
            arc, timed_out = rc.run_claude(task, cid, d, scratch)
            model = rc.CLAUDE_MODEL
        else:
            arc, timed_out = rc.run_codex(task, cid, d, scratch)
            model = rc.CODEX_MODEL
        wall = time.time() - t0
        _, kout, _ = rc.box("exec", cid, "20", "echo before: $(ps -u dev -o pid= | wc -l) processes; kill -9 -1 2>/dev/null; sleep 1; echo after: $(ps -u dev -o pid= | wc -l) processes")
        (d / "cleanup.out").write_text(kout)
        ccode, cout, cres = run_check(cid, job_dir, p)
        (d / "check.out").write_text(cout)
        (d / "check.json").write_text(json.dumps(cres, indent=2))
        (d / "version.out").write_text(probe_version(cid, p))
        pats = " ".join(f"-e {shlex.quote(s)}" for s in p["must_reference"])
        (d / "references.out").write_text(rc.box("exec", cid, "60", f"grep -rIlF --exclude-dir=node_modules --exclude-dir=.venv "
                                                 f"--exclude-dir=.git --exclude-dir=data --exclude-dir=job {pats} /work || true")[1])
        # Data dirs (a Postgres cluster, a Chroma db) would swamp the work tarball; keep only the code.
        rc.box("exec", cid, "60", "rm -rf /work/data")
        _, tgz, _ = rc.box("tarwork", cid, binary=True)
        (d / "work.tgz").write_bytes(tgz)
        rc.unpack_text(d / "work.tgz", d / "work-files")
    finally:
        rc.box("rm", cid)
        shutil.rmtree(scratch, ignore_errors=True)
    with open(d / "transcript.md", "w") as f:
        subprocess.run([sys.executable, rc.HERE / "transcript.py", "md", d / "events.jsonl"], stdout=f)
    with open(d / "facts.json", "w") as f:
        subprocess.run([sys.executable, rc.HERE / "transcript.py", "facts", d / "events.jsonl"], stdout=f)
    facts = json.loads((d / "facts.json").read_text() or "{}")
    stop = "timeout" if timed_out else facts.get("stop", "error")
    invalid = (d / "invalid.txt").read_text().strip() if (d / "invalid.txt").exists() else ""
    if not invalid and stop in ("api_error", "error"):
        invalid = f"agent stopped with {stop}"
    if not invalid and not facts.get("tool_calls"):
        invalid = "the agent never ran a tool"
    run = {
        "job": JOB["id"], "product": key, "product_name": p["product"], "version": p["version"], "agent": facts.get("agent") or agent,
        "model": model, "image": image.strip(), "started_at": started, "wall_seconds": int(wall),
        "valid": not invalid, "invalid_reason": invalid or None, "stop_reason": stop,
        "api_equiv_usd": facts.get("cost_usd"), "tokens": facts.get("tokens"), "turns": facts.get("turns"),
        "tool_calls": facts.get("tool_calls"), "urls_fetched": facts.get("urls_fetched", []),
        "check": {"passed": cres.get("passed"), "exit": ccode, "steps": cres.get("steps", [])},
        "version_seen": (d / "version.out").read_text().strip()[-300:],
        "references_product": bool((d / "references.out").read_text().strip()),
        "decoy": dec, "agent_said": (facts.get("final_text") or "")[:3000],
    }
    (run_dir / "run.json").write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n")
    passed = sum(s["passed"] for s in run["check"]["steps"])
    print(f"{key} / {agent}: {passed}/{len(run['check']['steps'])} check steps, {int(wall)}s, "
          f"${run['api_equiv_usd'] or 0:.2f}{' INVALID: ' + invalid if invalid else ''}")


if __name__ == "__main__":
    if not JOB:
        sys.exit(__doc__)
    main()
