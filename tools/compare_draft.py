#!/usr/bin/env python3
"""Save a comparison job's post to the canagentuseit SlopIt blog as a DRAFT (NJ approves publishing).

  compare_draft.py <job-run-dir>              create the draft from <job-run-dir>/post.md, or update it
  compare_draft.py <job-run-dir> --publish    publish it (only with CAUI_ALLOW_PUBLISH=1; NJ's call)

post.md has the same front matter as single-run posts (title, slug, excerpt, seoDescription, tags).
Records what it did in <job-run-dir>/post.json. Key and blog id as in post_draft.py; never printed.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import post_draft as pd  # noqa: E402


def main(run, publish):
    run = Path(run)
    src = run / "post.md"
    meta, body = pd.frontmatter(src.read_text())
    chk = subprocess.run([sys.executable, pd.HERE / "redact.py", "--check", src], capture_output=True, text=True)
    if chk.returncode != 0:
        sys.exit(f"post.md still matches redaction patterns, not sending:\n{chk.stdout[:600]}")
    if publish and os.environ.get("CAUI_ALLOW_PUBLISH") != "1":
        sys.exit("publishing needs CAUI_ALLOW_PUBLISH=1 (NJ's go)")
    key = Path(os.environ.get("CAUI_SLOPIT_KEY_FILE", pd.CFG / "slopit-key")).read_text().strip()
    blog = os.environ.get("CAUI_SLOPIT_BLOG_ID") or (pd.CFG / "slopit-blog-id").read_text().strip()
    rec_p = run / "post.json"
    prev = json.loads(rec_p.read_text()) if rec_p.exists() else {}
    fields = {"title": meta["title"], "body": body, "excerpt": meta.get("excerpt"),
              "seoDescription": meta.get("seoDescription"), "tags": meta.get("tags") or [],
              "status": "published" if publish else "draft"}
    if prev.get("slug"):
        out = pd.call("PATCH", f"/blogs/{blog}/posts/{prev['slug']}", key, {k: v for k, v in fields.items() if v})
    else:
        out = pd.call("POST", f"/blogs/{blog}/posts", key, {**{k: v for k, v in fields.items() if v}, "slug": meta.get("slug")})
    p = out.get("post") or out
    rec = {"slug": p.get("slug") or prev.get("slug"), "status": fields["status"], "title": meta["title"],
           "preview_url": out.get("preview_url") or p.get("preview_url") or prev.get("preview_url"),
           "post_url": out.get("post_url") or p.get("url") if publish else None}
    rec_p.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if v}, indent=2))


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) in (1, 2) and (len(a) == 1 or a[1] == "--publish"):
        main(a[0], len(a) == 2)
    else:
        sys.exit(__doc__)
