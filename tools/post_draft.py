#!/usr/bin/env python3
"""Save results/<run>/post.md to the canagentuseit SlopIt blog as a DRAFT and record it in result.json.

  post_draft.py <result-dir>             create the draft, or update the same draft on a re-run
  post_draft.py <result-dir> --publish   publish it (only with CAUI_ALLOW_PUBLISH=1; NJ's call)

The key is read from $CAUI_SLOPIT_KEY_FILE (default ~/.config/caui/slopit-key) and its blog id from
$CAUI_SLOPIT_BLOG_ID or ~/.config/caui/slopit-blog-id. The key is never printed.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("CAUI_SLOPIT_API", "https://slopit.io/api")
CFG = Path.home() / ".config/caui"


def frontmatter(text):
    if not text.startswith("---\n"):
        sys.exit("post.md must start with YAML frontmatter")
    head, body = text[4:].split("\n---\n", 1)
    meta = {}
    for line in head.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
        else:
            v = v.strip("\"'")
        meta[k.strip()] = v
    return meta, body.lstrip("\n")


def call(method, path, key, payload=None):
    req = urllib.request.Request(
        f"{API}{path}", method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "caui-writer/1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"SlopIt {method} {path}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:400]}")


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    rdir = Path(args[0])
    publish = "--publish" in args
    if publish and os.environ.get("CAUI_ALLOW_PUBLISH") != "1":
        sys.exit("refusing to publish: set CAUI_ALLOW_PUBLISH=1 (NJ approves publishing)")
    key = Path(os.environ.get("CAUI_SLOPIT_KEY_FILE", CFG / "slopit-key")).read_text().strip()
    blog = os.environ.get("CAUI_SLOPIT_BLOG_ID") or (CFG / "slopit-blog-id").read_text().strip()
    meta, body = frontmatter((rdir / "post.md").read_text())
    res_p = rdir / "result.json"
    res = json.loads(res_p.read_text())
    post = {
        "title": meta["title"], "body": body, "slug": meta.get("slug"),
        "excerpt": meta.get("excerpt"), "seoDescription": meta.get("seoDescription"),
        "tags": meta.get("tags") or [], "author": "Can an Agent Use It? (agent-written)",
    }
    post = {k: v for k, v in post.items() if v}
    prev = res.get("post") or {}
    if prev.get("post_id"):
        if not publish:
            post.pop("slug", None)  # slug is immutable on PATCH
            post["status"] = "draft"
        else:
            post = {"status": "published"}
        out = call("PATCH", f"/blogs/{blog}/posts/{prev['post_id']}", key, post)
    else:
        post["status"] = "published" if publish else "draft"
        out = call("POST", f"/blogs/{blog}/posts", key, post)
    p = out.get("post", out)
    rec = {
        "status": "published" if publish else "draft",
        "post_id": str(p.get("slug") or p.get("id")),
        "slug": p.get("slug"),
        "preview_url": out.get("preview_url") or p.get("preview_url") or prev.get("preview_url"),
        "post_url": out.get("post_url") or p.get("post_url"),
        "drafted_at": prev.get("drafted_at") or __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
    }
    res["post"] = rec
    res_p.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if v}, indent=2))


if __name__ == "__main__":
    main()
