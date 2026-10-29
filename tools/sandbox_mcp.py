#!/usr/bin/env python3
"""Sandbox MCP server (stdio): the test agent's only way to act. Every tool runs inside the run's
throwaway container through caui-box; nothing here touches the host's files or shell.

Tools: run, write_file, read_file, fetch_url. Both agents (Claude Code and Codex) get the same set.

Env:
  CAUI_RUN       container run id (as given to `caui-box start`)
  CAUI_BOX       how to call caui-box, e.g. "sudo -n -u caui-tester /usr/local/bin/caui-box"
  CAUI_LOG       JSONL file: one line per tool call with wall-clock start/end, the call and its result
Stdlib only.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time

RUN = os.environ["CAUI_RUN"]
BOX = shlex.split(os.environ.get("CAUI_BOX", "caui-box"))
LOG = os.environ.get("CAUI_LOG")
MAX_OUT = 30000

TOOLS = [
    {"name": "run",
     "description": "Run a shell command on the Linux box you're working on (Debian 12, user `dev`, no sudo, cwd /work, "
                    "Python 3.11 + uv, Node 22 + npm, git, curl, outbound internet). Runs with `bash -lc`. Returns "
                    "combined stdout+stderr (last 30k chars) and the exit code. Each call is a fresh shell; files persist.",
     "inputSchema": {"type": "object", "required": ["command"], "properties": {
         "command": {"type": "string"},
         "timeout_s": {"type": "integer", "minimum": 1, "maximum": 900, "default": 300}}}},
    {"name": "write_file",
     "description": "Create or overwrite a file on the box (path under /work or /tmp).",
     "inputSchema": {"type": "object", "required": ["path", "content"], "properties": {
         "path": {"type": "string"}, "content": {"type": "string"}}}},
    {"name": "read_file",
     "description": "Read a file on the box (path under /work or /tmp, first 2 MB).",
     "inputSchema": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}}},
    {"name": "fetch_url",
     "description": "Fetch a web page or file over HTTP(S) from the box and return it as text (HTML tags stripped, first 60k chars).",
     "inputSchema": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}}}},
]


def box(*args, stdin=None, timeout=960, cap=2_000_000):
    """Call caui-box; read at most `cap` bytes of output so a flood can't fill the host's memory."""
    p = subprocess.Popen(BOX + list(args), stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if stdin is not None:
        p.stdin.write(stdin)
        p.stdin.close()
    try:
        out = p.stdout.read(cap)
        p.stdout.close()
        p.wait(timeout=timeout)
        err = p.stderr.read(20000)
    except subprocess.TimeoutExpired:
        p.kill()
        return 124, out.decode("utf-8", "replace"), "timeout"
    return p.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def html_to_text(s):
    s = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|pre)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " "), ("&amp;", "&")):
        s = s.replace(a, b)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", s).strip()


def call(name, a):
    if name == "run":
        t = int(a.get("timeout_s") or 300)
        t = max(1, min(t, 900))
        rc, out, err = box("exec", RUN, str(t), a["command"], timeout=t + 60)
        out = (out + err)
        if len(out) > MAX_OUT:
            out = f"[… {len(out) - MAX_OUT} earlier chars cut]\n" + out[-MAX_OUT:]
        if rc == 124:
            out += f"\n[timed out after {t}s]"
        return f"{out}\n[exit code {rc}]", rc
    if name == "write_file":
        rc, out, err = box("put", RUN, a["path"], stdin=a["content"].encode())
        return (f"wrote {len(a['content'])} chars to {a['path']}" if rc == 0 else f"error: {err.strip() or out.strip()}"), rc
    if name == "read_file":
        rc, out, err = box("get", RUN, a["path"])
        return (out if rc == 0 else f"error: {err.strip() or out.strip()}"), rc
    if name == "fetch_url":
        url = a["url"]
        if not re.match(r"^https?://[^\s'\"]+$", url):
            return "error: not an http(s) URL", 2
        rc, out, err = box("exec", RUN, "60", f"curl -sSL --max-time 45 -A 'Mozilla/5.0 (caui test agent)' {shlex.quote(url)} | head -c 3000000", timeout=120)
        text = html_to_text(out) if "<html" in out[:2000].lower() or "<!doctype" in out[:200].lower() else out
        return (text[:60000] or f"(empty response) {err.strip()}"), rc
    return f"unknown tool {name}", 2


def log(rec):
    if LOG:
        with open(LOG, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        mid, method = req.get("id"), req.get("method")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": req.get("params", {}).get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "sandbox", "version": "1"}}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            p = req.get("params", {})
            name, args = p.get("name"), p.get("arguments") or {}
            t0 = time.time()
            try:
                text, rc = call(name, args)
            except Exception as e:  # report, don't crash the session
                text, rc = f"sandbox error: {e}", 99
            t1 = time.time()
            log({"t_start": round(t0, 3), "t_end": round(t1, 3), "tool": name, "args": args, "rc": rc, "result": text[-8000:]})
            send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}], "isError": rc != 0}})
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"no method {method}"}})


if __name__ == "__main__":
    main()
