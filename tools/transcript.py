#!/usr/bin/env python3
"""Claude Code stream-json transcripts: live rendering, markdown, and facts.

  transcript.py live                 stdin stream-json -> readable terminal lines (what asciinema records)
  transcript.py md <jsonl>           -> readable markdown transcript on stdout
  transcript.py facts <jsonl>        -> JSON: model, agent version, cost, turns, stop reason, final text, URLs fetched

Stdlib only, so it runs inside the sandbox image and on the host.
"""
import json
import re
import sys

URL_RE = re.compile(r"https?://[^\s'\"<>)\]}`]+")
DIM, BOLD, CYAN, YEL, RED, RST = "\033[2m", "\033[1m", "\033[36m", "\033[33m", "\033[31m", "\033[0m"


def events(lines):
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def blocks(ev):
    msg = ev.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content or []


def tool_input_summary(name, inp):
    if name == "Bash":
        return inp.get("command", "")
    if name in ("Read", "Write", "Edit", "NotebookEdit"):
        return inp.get("file_path", "")
    if name == "WebFetch":
        return inp.get("url", "")
    if name in ("Glob", "Grep"):
        return inp.get("pattern", "")
    return json.dumps(inp)[:300]


def result_text(block):
    c = block.get("content")
    if isinstance(c, list):
        c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
    return str(c or "")


def clip(s, n):
    s = s.rstrip()
    return s if len(s) <= n else s[:n] + f"\n… ({len(s) - n} more chars)"


def live():
    for ev in events(sys.stdin):
        t = ev.get("type")
        if t == "system" and ev.get("subtype") == "init":
            print(f"{DIM}# {ev.get('model')} · claude-code {ev.get('claude_code_version', '?')} · cwd {ev.get('cwd')}{RST}", flush=True)
        elif t == "assistant":
            for b in blocks(ev):
                if b.get("type") == "text" and b.get("text", "").strip():
                    print(f"\n{BOLD}● {b['text'].strip()}{RST}", flush=True)
                elif b.get("type") == "tool_use":
                    print(f"\n{CYAN}▸ {b.get('name')}{RST} {clip(tool_input_summary(b.get('name'), b.get('input', {})), 400)}", flush=True)
        elif t == "user":
            for b in blocks(ev):
                if b.get("type") == "tool_result":
                    color = RED if b.get("is_error") else DIM
                    out = clip(result_text(b), 1200)
                    if out:
                        print(color + "\n".join("  " + l for l in out.splitlines()) + RST, flush=True)
        elif t == "result":
            cost = ev.get("total_cost_usd")
            print(f"\n{YEL}■ {ev.get('subtype')} · {ev.get('num_turns')} turns · ${cost if cost is not None else '?'} · {round((ev.get('duration_ms') or 0) / 1000)}s{RST}", flush=True)


def md(path):
    out = []
    with open(path) as f:
        for ev in events(f):
            t = ev.get("type")
            if t == "system" and ev.get("subtype") == "init":
                out.append(f"_Model `{ev.get('model')}`, Claude Code {ev.get('claude_code_version', '?')}_\n")
            elif t == "assistant":
                for b in blocks(ev):
                    if b.get("type") == "text" and b.get("text", "").strip():
                        out.append(f"**Agent:** {b['text'].strip()}\n")
                    elif b.get("type") == "tool_use":
                        name = b.get("name")
                        summary = tool_input_summary(name, b.get("input", {}))
                        lang = "bash" if name == "Bash" else ""
                        out.append(f"`{name}`\n```{lang}\n{clip(summary, 2000)}\n```\n")
            elif t == "user":
                for b in blocks(ev):
                    if b.get("type") == "tool_result":
                        txt = clip(result_text(b), 1500)
                        tag = "error" if b.get("is_error") else "output"
                        if txt:
                            # Plain markdown only: SlopIt drops raw HTML, and the post embeds this file.
                            out.append(f"_{tag}:_\n```text\n{txt.replace('```', 'ʼʼʼ')}\n```\n")
            elif t == "result":
                out.append(f"_Stopped: {ev.get('subtype')}, {ev.get('num_turns')} turns, ${ev.get('total_cost_usd')}_\n")
    print("\n".join(out))


def facts(path):
    f_ = {"model": None, "agent": None, "cost_usd": None, "turns": None, "stop": "error",
          "final_text": "", "urls_fetched": [], "transcript_ok": False}
    urls = []
    try:
        with open(path) as f:
            for ev in events(f):
                t = ev.get("type")
                if t == "system" and ev.get("subtype") == "init":
                    f_["model"] = ev.get("model")
                    f_["agent"] = f"claude-code {ev.get('claude_code_version', '?')}"
                    f_["transcript_ok"] = True
                elif t == "assistant":
                    for b in blocks(ev):
                        if b.get("type") == "tool_use":
                            inp = b.get("input", {})
                            if b.get("name") == "WebFetch" and inp.get("url"):
                                urls.append(inp["url"])
                            elif b.get("name") == "Bash":
                                urls += URL_RE.findall(inp.get("command", ""))
                elif t == "result":
                    f_["cost_usd"] = ev.get("total_cost_usd")
                    f_["turns"] = ev.get("num_turns")
                    sub = ev.get("subtype", "")
                    f_["stop"] = {"success": "done", "error_max_turns": "max_turns",
                                  "error_max_budget_usd": "budget"}.get(sub, sub or "error")
                    f_["final_text"] = (ev.get("result") or "")[:4000]
                    # An API failure (bad key, overload, rate limit) is ours, not the tool's.
                    if ev.get("is_error") and f_["stop"] == "done" or ev.get("terminal_reason") == "api_error":
                        f_["stop"] = "api_error"
    except FileNotFoundError:
        pass
    seen = []
    for u in urls:
        u = u.rstrip(".,;:")
        if u not in seen:
            seen.append(u)
    f_["urls_fetched"] = seen
    print(json.dumps(f_, indent=2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "live":
        live()
    elif cmd == "md" and len(sys.argv) == 3:
        md(sys.argv[2])
    elif cmd == "facts" and len(sys.argv) == 3:
        facts(sys.argv[2])
    else:
        sys.exit(__doc__)
