#!/usr/bin/env python3
"""Attach and verify the blog's custom domain on SlopIt (Pro only; subdomains only, so www).

  domain.py attach [www.canagentuseit.com]   prints the CNAME and TXT records to add at Namecheap
  domain.py verify [www.canagentuseit.com]   checks DNS and switches the blog to the domain
  domain.py status

Key and blog id from ~/.config/caui/ (never printed).
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

CFG = Path.home() / ".config/caui"
API = "https://slopit.io/api"


def call(method, path, payload=None):
    key = (CFG / "slopit-key").read_text().strip()
    req = urllib.request.Request(f"{API}{path}", method=method,
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "Accept": "application/json", "User-Agent": "caui-domain/1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")


if __name__ == "__main__":
    a = sys.argv[1:]
    blog = (CFG / "slopit-blog-id").read_text().strip()
    host = a[1] if len(a) > 1 else "www.canagentuseit.com"
    if a[:1] == ["attach"]:
        print(json.dumps(call("POST", f"/blogs/{blog}/custom-domain", {"hostname": host}), indent=2))
    elif a[:1] == ["verify"]:
        print(json.dumps(call("POST", f"/blogs/{blog}/custom-domain/verify"), indent=2))
    elif a[:1] == ["status"]:
        print(json.dumps(call("GET", f"/blogs/{blog}/custom-domain"), indent=2))
    else:
        sys.exit(__doc__)
