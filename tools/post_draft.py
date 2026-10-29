#!/usr/bin/env python3
"""Save a run's verdict post (and guide, if any) to the canagentuseit SlopIt blog as DRAFTS.

  post_draft.py <run-dir>              create the drafts, or update the same drafts on a re-run
  post_draft.py <run-dir> --publish    publish the post and its guide (only with CAUI_ALLOW_PUBLISH=1; NJ's call)
  post_draft.py --pending              list runs that have a redacted result and no drafts yet (oldest first)

Reads <run-dir>/public/post.md and public/guide.md (redacted copies only), records what it did in
<run-dir>/post.json. Key from $CAUI_SLOPIT_KEY_FILE (default ~/.config/caui/slopit-key), blog id from
$CAUI_SLOPIT_BLOG_ID or ~/.config/caui/slopit-blog-id. The key is never printed.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("CAUI_SLOPIT_API", "https://slopit.io/api")
CFG = Path.home() / ".config/caui"
HERE = Path(__file__).resolve().parent
AUTHOR = "Can an Agent Use It? (agent-written)"


def frontmatter(text):
    if not text.startswith("---\n"):
        sys.exit("post must start with YAML front matter")
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
                 "Accept": "application/json", "User-Agent": "caui-writer/2"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"SlopIt {method} {path}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:400]}")


def get_post(blog, slug, key):
    req = urllib.request.Request(f"{API}/blogs/{blog}/posts/{slug}", headers={
        "Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": "caui-writer/2"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
            return d.get("post", d)
    except urllib.error.HTTPError:
        return None


def guide_ok(run):
    """A guide is only drafted once its own steps have worked in a fresh container (guide_check.py)."""
    import hashlib
    g = (run / "public/guide.md").read_bytes()
    rec_p = run / "guide-check.json"
    rec = json.loads(rec_p.read_text()) if rec_p.exists() else {}
    if rec.get("guide_sha256") != hashlib.sha256(g).hexdigest():
        subprocess.run([sys.executable, HERE / "guide_check.py", run])
        rec = json.loads(rec_p.read_text()) if rec_p.exists() else {}
    return bool(rec.get("passed")), rec


def save(kind, src, prev, key, blog, publish):
    meta, body = frontmatter(src.read_text())
    if publish:
        body = body.rstrip() + f"\n\n_Reviewed by a human on {dt.date.today().isoformat()} before publishing._\n"
    # Last line of defence: the redaction patterns must find nothing in what we're about to send.
    chk = subprocess.run([sys.executable, HERE / "redact.py", "--check", src], capture_output=True, text=True)
    if chk.returncode != 0:
        sys.exit(f"{src.name} still matches redaction patterns, not sending:\n{chk.stdout[:600]}")
    replaces = prev.get("replaces")
    if kind == "guide" and not prev.get("slug") and meta.get("slug"):
        # One guide per tool and task, updated in place: if it's already live, draft the new version
        # beside it and swap the body in on publish.
        live = get_post(blog, meta["slug"], key)
        if live and live.get("status") == "published":
            replaces = meta["slug"]
            meta["slug"] = f"{meta['slug']}-next-{dt.date.today().strftime('%Y%m%d')}"
    if publish and replaces:
        out = call("PATCH", f"/blogs/{blog}/posts/{replaces}", key, {
            "title": meta["title"], "body": body, "excerpt": meta.get("excerpt"), "seoDescription": meta.get("seoDescription")})
        if prev.get("slug") and prev["slug"] != replaces:
            call("DELETE", f"/blogs/{blog}/posts/{prev['slug']}", key)
        p = out.get("post", out)
        return {"kind": kind, "status": "published", "slug": replaces, "title": meta["title"],
                "tested_on": meta.get("tested_on"), "tested_version": meta.get("tested_version"),
                "post_url": out.get("post_url") or p.get("post_url"),
                "saved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    if prev.get("slug"):
        payload = {"status": "published", "body": body} if publish else {
            "title": meta["title"], "body": body, "excerpt": meta.get("excerpt"),
            "seoDescription": meta.get("seoDescription"), "tags": meta.get("tags") or [], "status": "draft"}
        out = call("PATCH", f"/blogs/{blog}/posts/{prev['slug']}", key, {k: v for k, v in payload.items() if v})
    else:
        payload = {"title": meta["title"], "body": body, "slug": meta.get("slug"), "excerpt": meta.get("excerpt"),
                   "seoDescription": meta.get("seoDescription"), "tags": meta.get("tags") or [], "author": AUTHOR,
                   "status": "published" if publish else "draft"}
        out = call("POST", f"/blogs/{blog}/posts", key, {k: v for k, v in payload.items() if v})
    p = out.get("post", out)
    return {
        "kind": kind, "status": "published" if publish else "draft", "slug": p.get("slug") or prev.get("slug"),
        "replaces": replaces,
        "title": meta["title"], "tested_on": meta.get("tested_on"), "tested_version": meta.get("tested_version"),
        "preview_url": out.get("preview_url") or p.get("preview_url") or prev.get("preview_url"),
        "post_url": out.get("post_url") or p.get("post_url"),
        "saved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


RUNS = Path(os.environ.get("CAUI_RUNS", Path.home() / "caui-runs"))


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args == ["--pending"]:
        for r in sorted(RUNS.glob("*/public/result.json")):
            run = r.parent.parent
            if not (run / "post.json").exists():
                print(run)
        return
    run = Path(args[0]).expanduser()
    publish = "--publish" in args
    if publish and os.environ.get("CAUI_ALLOW_PUBLISH") != "1":
        sys.exit("refusing to publish: set CAUI_ALLOW_PUBLISH=1 (NJ approves publishing)")
    key = Path(os.environ.get("CAUI_SLOPIT_KEY_FILE", CFG / "slopit-key")).read_text().strip()
    blog = os.environ.get("CAUI_SLOPIT_BLOG_ID") or (CFG / "slopit-blog-id").read_text().strip()
    rec_p = run / "post.json"
    rec = json.loads(rec_p.read_text()) if rec_p.exists() else {}
    for kind, name in (("post", "post.md"), ("guide", "guide.md")):
        src = run / "public" / name
        if not src.exists():
            continue
        if kind == "guide":
            ok, chk = guide_ok(run)
            if not ok:
                why = chk.get("error") or "check failed"
                rec["guide"] = {"kind": "guide", "status": "withheld",
                                "reason": why if why.startswith("sandbox unavailable") else f"its own steps didn't work in a fresh container: {why}"}
                continue
        rec[kind] = save(kind, src, rec.get(kind) or {}, key, blog, publish)
    if not rec:
        sys.exit(f"no public/post.md in {run}")
    rec_p.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: {f: v[f] for f in ("status", "slug", "preview_url", "post_url", "replaces", "reason") if v.get(f)} for k, v in rec.items()}, indent=2))


if __name__ == "__main__":
    main()
