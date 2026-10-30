#!/usr/bin/env python3
"""Put an approved run into the public record: <repo>/results/<run>/ (CC BY 4.0).

  promote.py <run-dir>

Only after NJ approved the post (post.json says the post is published). Copies the redacted
public/ copy only, never the raw run, and leaves video out of git (the media kit stays on the test
machine and goes to the editing Mac). Re-checks the redaction patterns on everything it copies.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KEEP = {".json", ".jsonl", ".md", ".txt", ".out"}
DROP = {"post.md", "guide.md"}   # those live on the blog; the result links to them


def main(run):
    run = Path(run).expanduser().resolve()
    rec = json.loads((run / "post.json").read_text()) if (run / "post.json").exists() else {}
    if (rec.get("post") or {}).get("status") != "published":
        sys.exit("not promoting: the post isn't published (NJ approves first)")
    pub = run / "public"
    dest = REPO / "results" / run.name
    if dest.exists():
        shutil.rmtree(dest)
    files = [p for p in pub.rglob("*") if p.is_file() and p.suffix in KEEP and p.name not in DROP and "video" not in p.parts]
    chk = subprocess.run([sys.executable, REPO / "tools/redact.py", "--check", *files], capture_output=True, text=True)
    if chk.returncode != 0:
        sys.exit(f"redaction check failed, not promoting:\n{chk.stdout[:800]}")
    for p in files:
        out = dest / p.relative_to(pub)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
    res = json.loads((dest / "result.json").read_text())
    res["post"] = {k: {f: v.get(f) for f in ("slug", "post_url", "tested_on", "tested_version")} for k, v in rec.items()}
    (dest / "result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    print(f"promoted {len(files)} files to {dest.relative_to(REPO)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
