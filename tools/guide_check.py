#!/usr/bin/env python3
"""Validate a how-to guide by doing exactly what it says, in a fresh container.

  guide_check.py <run-dir>      reads <run-dir>/public/guide.md and <run-dir>/brief.json
                                writes <run-dir>/guide-check.json; exit 0 only if the guide works

Only the guide's "## Steps" section runs, top to bottom: ```bash blocks are run as commands, and
```file:/work/<path> blocks are written as files. Then the run's own hidden success check runs. If any
step fails or the check fails, the guide isn't drafted. A guide that "only contains commands from the
transcript" isn't enough: an exploratory install the writer left out would make it fail on a clean
machine, and this catches that.
"""
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

BOX = shlex.split(os.environ.get("CAUI_BOX", "sudo -n -u caui-tester /usr/local/bin/caui-box"))


def box(*args, stdin=None, timeout=1000):
    p = subprocess.run(BOX + list(args), input=stdin, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace")[-6000:], p.stderr.decode("utf-8", "replace")[-2000:]


def steps(md):
    m = re.search(r"^## Steps\s*$(.*?)(?=^## |\Z)", md, re.M | re.S)
    if not m:
        return None
    out = []
    for info, body in re.findall(r"^```([^\n]*)\n(.*?)^```", m.group(1), re.M | re.S):
        info = info.strip()
        if info in ("bash", "sh", "shell", "console"):
            cmd = "\n".join(l[2:] if l.startswith("$ ") else l for l in body.rstrip("\n").splitlines())
            out.append(("run", cmd))
        elif info.startswith("file:"):
            out.append(("file", info[5:].strip(), body))
    return out


def main(run):
    run = Path(run).expanduser().resolve()
    guide = (run / "public/guide.md").read_text()
    brief = json.loads((run / "brief.json").read_text())
    rec = {"guide_sha256": hashlib.sha256(guide.encode()).hexdigest(), "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "steps": [], "passed": False}
    st = steps(guide)
    if not st:
        rec["error"] = "no runnable steps under '## Steps'"
    else:
        cid = re.sub(r"[^a-z0-9-]", "-", f"{run.name.lower()}-guide")[-90:].strip("-")
        rc, image, err = box("start", cid)
        rec["image"] = image.strip()
        try:
            ok = rc == 0
            for s in st:
                if not ok:
                    break
                if s[0] == "run":
                    rc, out, err = box("exec", cid, "900", s[1])
                    rec["steps"].append({"run": s[1][:2000], "exit": rc, "output_tail": out[-1500:]})
                else:
                    rc, out, err = box("put", cid, s[1], stdin=s[2].encode())
                    rec["steps"].append({"file": s[1], "exit": rc})
                ok = rc == 0
            if ok:
                box("exec", cid, "20", "kill -9 -1 2>/dev/null; true")
                rc, out, _ = box("exec", cid, "180", brief["check"]["command"])
                passed = rc == brief["check"]["expect_exit"] and re.search(brief["check"]["stdout_regex"], out, re.M) is not None
                rec["check"] = {"exit": rc, "passed": passed, "output_tail": out[-1500:]}
                rec["passed"] = passed
            else:
                rec["error"] = f"step {len(rec['steps'])} failed"
        finally:
            box("rm", cid)
    (run / "guide-check.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(f"guide {'WORKS' if rec['passed'] else 'FAILED'}: {len(rec['steps'])} steps" + (f", {rec.get('error')}" if rec.get("error") else ""))
    sys.exit(0 if rec["passed"] else 1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
