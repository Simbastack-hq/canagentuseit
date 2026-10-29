#!/usr/bin/env python3
"""Agent transcripts in one shape, whatever the agent.

  transcript.py normalize claude|codex <raw.jsonl> <events.jsonl>   raw agent stream -> normalized events
  transcript.py md <events.jsonl>        readable markdown (plain: SlopIt drops raw HTML)
  transcript.py facts <events.jsonl>     JSON: model, agent, cost, turns, stop, final text, URLs fetched

Raw lines carry `_t` (wall-clock seconds) added by the harness as they arrive. Normalized events:
  {"t", "kind": "init", "model", "agent"}
  {"t", "kind": "text", "text"}                         the agent talking (narration, captions)
  {"t", "kind": "call", "id", "tool", "input"}          a tool call (run, write_file, fetch_url, WebFetch…)
  {"t", "kind": "result", "id", "output", "error"}      its result
  {"t", "kind": "done", "stop", "turns", "cost_usd", "tokens", "final"}
Stdlib only.
"""
import json
import re
import sys

URL_RE = re.compile(r"https?://[^\s'\"<>)\]}`]+")


def jl(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def short_tool(name):
    return name.split("__")[-1] if name and name.startswith("mcp__") else name


def content_text(c):
    if isinstance(c, list):
        return "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
    return str(c or "")


def norm_claude(raw):
    for ev in raw:
        t, typ = ev.get("_t"), ev.get("type")
        if typ == "system" and ev.get("subtype") == "init":
            yield {"t": t, "kind": "init", "model": ev.get("model"), "agent": f"Claude Code {ev.get('claude_code_version', '?')}"}
        elif typ == "assistant":
            for b in (ev.get("message") or {}).get("content") or []:
                if b.get("type") == "text" and b.get("text", "").strip():
                    yield {"t": t, "kind": "text", "text": b["text"].strip()}
                elif b.get("type") == "tool_use":
                    yield {"t": t, "kind": "call", "id": b.get("id"), "tool": short_tool(b.get("name")), "input": b.get("input") or {}}
        elif typ == "user":
            c = (ev.get("message") or {}).get("content")
            for b in c if isinstance(c, list) else []:
                if b.get("type") == "tool_result":
                    yield {"t": t, "kind": "result", "id": b.get("tool_use_id"), "output": content_text(b.get("content")), "error": bool(b.get("is_error"))}
        elif typ == "result":
            sub = ev.get("subtype", "")
            stop = {"success": "done", "error_max_turns": "max_turns", "error_max_budget_usd": "budget"}.get(sub, sub or "error")
            if ev.get("terminal_reason") == "api_error" or (ev.get("is_error") and stop == "done"):
                stop = "api_error"
            u = ev.get("usage") or {}
            yield {"t": t, "kind": "done", "stop": stop, "turns": ev.get("num_turns"), "cost_usd": ev.get("total_cost_usd"),
                   "tokens": (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0) + (u.get("cache_read_input_tokens") or 0),
                   "final": (ev.get("result") or "")[:4000]}


def norm_codex(raw, model=None, version=""):
    calls, tokens, last_text, done, init, t = 0, 0, "", False, False, None
    for ev in raw:
        t, typ = ev.get("_t"), ev.get("type", "")
        if not init and typ in ("thread.started", "turn.started"):
            init = True
            yield {"t": t, "kind": "init", "model": model, "agent": f"Codex CLI {version}".strip()}
        item = ev.get("item") or {}
        it = item.get("type", "")
        if typ == "item.completed" and it == "agent_message" and item.get("text", "").strip():
            last_text = item["text"].strip()
            yield {"t": t, "kind": "text", "text": last_text}
        elif typ == "item.started" and it == "mcp_tool_call":
            calls += 1
            yield {"t": t, "kind": "call", "id": item.get("id"), "tool": item.get("tool"), "input": item.get("arguments") or {}}
        elif typ == "item.completed" and it == "mcp_tool_call":
            res = item.get("result") or {}
            out = content_text(res.get("content")) if isinstance(res, dict) else str(res)
            err = item.get("error")
            yield {"t": t, "kind": "result", "id": item.get("id"), "output": out or (json.dumps(err) if err else ""),
                   "error": bool(err) or item.get("status") == "failed"}
        elif typ == "item.completed" and it in ("command_execution", "web_search", "file_change"):
            # Codex's own shell/web/patch tools are switched off; if one ever runs, it shows up loudly.
            yield {"t": t, "kind": "call", "id": item.get("id"), "tool": f"codex:{it}", "input": item}
        elif typ == "turn.completed":
            u = ev.get("usage") or {}
            tokens += (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
        elif typ in ("turn.failed", "error") and not done:
            done = True
            yield {"t": t, "kind": "done", "stop": "api_error", "turns": calls, "cost_usd": None, "tokens": tokens,
                   "final": json.dumps(ev.get("error") or ev)[:2000]}
    if not done:
        yield {"t": t, "kind": "done", "stop": "done" if init else "error", "turns": calls,
               "cost_usd": None, "tokens": tokens, "final": last_text[:4000]}


def clip(s, n):
    s = str(s).rstrip()
    return s if len(s) <= n else s[:n] + f"\n… ({len(s) - n} more chars)"


def call_summary(tool, inp):
    if tool in ("run", "Bash"):
        return inp.get("command", "")
    if tool == "write_file":
        return f"{inp.get('path')}\n---\n{inp.get('content', '')}"
    if tool in ("read_file", "Read"):
        return inp.get("path") or inp.get("file_path", "")
    if tool in ("fetch_url", "WebFetch"):
        return inp.get("url", "")
    return json.dumps(inp)[:600]


def md(path):
    out, t0 = [], None
    for e in jl(path):
        if t0 is None and e.get("t"):
            t0 = e["t"]
        ts = f"[{int(e['t'] - t0) // 60:02d}:{int(e['t'] - t0) % 60:02d}] " if e.get("t") and t0 else ""
        k = e["kind"]
        if k == "init":
            out.append(f"_{e.get('agent')}, model `{e.get('model')}`_\n")
        elif k == "text":
            out.append(f"{ts}**Agent:** {e['text']}\n")
        elif k == "call":
            lang = "bash" if e["tool"] in ("run", "Bash") else "text"
            out.append(f"{ts}`{e['tool']}`\n```{lang}\n{clip(call_summary(e['tool'], e['input']), 2500).replace('```', 'ʼʼʼ')}\n```\n")
        elif k == "result":
            txt = clip(e.get("output", ""), 1500)
            if txt:
                out.append(f"_{'error' if e.get('error') else 'output'}:_\n```text\n{txt.replace('```', 'ʼʼʼ')}\n```\n")
        elif k == "done":
            cost = f", ${e['cost_usd']}" if e.get("cost_usd") is not None else ""
            out.append(f"{ts}_Stopped: {e.get('stop')}, {e.get('turns')} turns{cost}_\n")
    print("\n".join(out))


def facts(path):
    f_ = {"model": None, "agent": None, "cost_usd": None, "turns": None, "tokens": None, "stop": "error",
          "final_text": "", "urls_fetched": [], "transcript_ok": False, "tool_calls": 0, "t_start": None, "t_end": None}
    urls = []
    try:
        for e in jl(path):
            f_["t_start"] = f_["t_start"] or e.get("t")
            f_["t_end"] = e.get("t") or f_["t_end"]
            if e["kind"] == "init":
                f_.update(model=e.get("model"), agent=e.get("agent"), transcript_ok=True)
            elif e["kind"] == "call":
                f_["tool_calls"] += 1
                inp = e.get("input") or {}
                if e["tool"] in ("fetch_url", "WebFetch") and inp.get("url"):
                    urls.append(inp["url"])
                elif e["tool"] in ("run", "Bash"):
                    urls += URL_RE.findall(inp.get("command", ""))
            elif e["kind"] == "done":
                f_.update(cost_usd=e.get("cost_usd"), turns=e.get("turns"), tokens=e.get("tokens"),
                          stop=e.get("stop"), final_text=e.get("final") or "")
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
    a = sys.argv[1:]
    if a[:1] == ["normalize"] and len(a) in (4, 5, 6):
        raw = list(jl(a[2]))
        evs = norm_claude(raw) if a[1] == "claude" else norm_codex(raw, *(a[4:6]))
        with open(a[3], "w") as f:
            for e in evs:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    elif a[:1] == ["md"] and len(a) == 2:
        md(a[1])
    elif a[:1] == ["facts"] and len(a) == 2:
        facts(a[1])
    else:
        sys.exit(__doc__)
