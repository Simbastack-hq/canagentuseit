#!/usr/bin/env python3
"""Throwaway vendor keys for keyed comparison jobs (decision 0004). Read as data, never sourced.

Keys live in ~/.config/caui/keys/<vendor>.env on the test machine: the directory 0700 and each file
0600, both owned by the harness user, no symlinks, KEY=VALUE lines (# comments allowed). A job's
product names the vendors it needs ("keys": ["vercel"]); only those files are read, for that run.

  keys.py check <vendor>...     validate the files and print the variable names (never the values)
"""
import os
import re
import stat
import sys
from pathlib import Path

DIR = Path(os.environ.get("CAUI_KEYS_DIR", Path.home() / ".config/caui/keys"))
VENDOR = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")
NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def _private(p, mode):
    st = os.lstat(p)
    if stat.S_ISLNK(st.st_mode):
        raise SystemExit(f"keys: {p} is a symlink")
    if st.st_uid != os.getuid():
        raise SystemExit(f"keys: {p} isn't owned by this user")
    if stat.S_IMODE(st.st_mode) & ~mode:
        raise SystemExit(f"keys: {p} must be mode {oct(mode)} or tighter")


def load(vendors):
    """{vendor: {NAME: value}} for the declared vendors only."""
    out = {}
    if vendors:
        _private(DIR, 0o700)
    for v in vendors:
        if not VENDOR.match(v):
            raise SystemExit(f"keys: bad vendor name {v!r}")
        f = DIR / f"{v}.env"
        if not f.exists():
            raise SystemExit(f"keys: no key file for {v} (NJ writes {f.name} into the keys folder)")
        _private(f, 0o600)
        kv = {}
        for n, line in enumerate(f.read_text().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, sep, val = line.partition("=")
            name, val = name.strip(), val.strip()
            if not sep or not NAME.match(name) or not val:
                raise SystemExit(f"keys: {f.name} line {n} isn't NAME=value")
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
                val = val[1:-1]
            kv[name] = val
        out[v] = kv
    return out


def env_file(kv):
    """The file the agent gets: plain NAME=value lines, safe to `set -a; . file` or parse."""
    return "".join(f"{k}={v}\n" for k, v in kv.items())


def secret_values(vendors):
    """Every value worth redacting, with the forms it could show up in."""
    import base64
    from urllib.parse import quote
    vals = set()
    for kv in load(vendors).values():
        for v in kv.values():
            if len(v) >= 8:
                vals |= {v, quote(v, safe=""), base64.b64encode(v.encode()).decode().rstrip("=")}
    return sorted(vals, key=len, reverse=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["check"] and len(a) > 1:
        for v, kv in load(a[1:]).items():
            print(f"{v}: {', '.join(kv)}")
    else:
        sys.exit(__doc__)
