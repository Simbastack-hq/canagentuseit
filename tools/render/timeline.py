#!/usr/bin/env python3
"""Build a video timeline from a run: keyframes of what's on screen, plus captions and markers.

  timeline.py <run-dir> <out-dir>     reads <run-dir>/result.json + attempt-*/events.jsonl
                                      writes timeline.json, captions.srt, markers.csv

Video time is real time with the waiting squeezed out: any gap over IDLE_MAX seconds plays as
IDLE_TO seconds with an on-screen "⏩ skipped N s" marker. Each keyframe is a full screen state; the
renderer draws it and holds it until the next one. Stdlib only.
"""
import json
import sys
from pathlib import Path

IDLE_MAX, IDLE_TO = 5.0, 1.0
READ_PER_LINE, READ_MAX = 0.12, 4.0   # after output appears, hold long enough to read it
TYPE_S, TYPE_STEPS = 0.6, 6       # commands "type in" over 0.6 s; output appears as a block
TITLE_S, CARD_S, BETWEEN_S = 3.0, 5.0, 2.5
MAX_LINES, MAX_OUT_LINES = 80, 18


def jl(p):
    try:
        return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def short(s, n, keep_space=False):
    s = str(s) if keep_space else (" ".join(str(s).split()) if "\n" not in str(s) else str(s))
    return s if len(s) <= n else s[: n - 1] + "…"


def out_lines(text):
    lines = [l.rstrip() for l in str(text).replace("\r", "").splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    if lines and lines[-1].startswith("[exit code"):
        code = lines.pop()
    else:
        code = None
    if len(lines) > MAX_OUT_LINES:
        lines = lines[:6] + [f"… {len(lines) - 12} more lines …"] + lines[-6:]
    return [short(l, 160, keep_space=True) for l in lines], code


def mmss(s):
    s = int(max(0, s))
    return f"{s // 60:02d}:{s % 60:02d}"


def tc(v, fps=30):
    f = int(round(v * fps))
    return f"{f // (3600 * fps):02d}:{f // (60 * fps) % 60:02d}:{f // fps % 60:02d}:{f % fps:02d}"


def srt_time(v):
    ms = int(round(v * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def build(run):
    run = Path(run)
    res = json.loads((run / "result.json").read_text())
    head = {"tool": res["tool"]["name"], "version": res["version"]["pinned"], "date": res["date"],
            "task": res["task"].split("\n\nDocs:")[0]}
    frames, captions, markers, timemap = [], [], [], []
    v = 0.0
    state = {"head": head, "lines": [], "caption": "", "counter": {}, "overlay": None}

    def push(dur, **over):
        nonlocal v
        s = json.loads(json.dumps(state))
        s.update(over)
        frames.append({"v": round(v, 3), "state": s})
        v += dur

    # Title card
    push(TITLE_S, overlay={"kind": "title", "title": f"Can an agent use {head['tool']} {head['version']}?",
                           "sub": head["task"], "date": head["date"]})
    first = {"command": None, "error": None, "fix": None}
    for ai, att in enumerate(res["attempts"]):
        evs = jl(run / f"attempt-{att['n']}" / "events.jsonl")
        if not evs:
            continue
        label = f"Attempt {att['n']} · {att['agent']} · {att['model']}"
        push(BETWEEN_S, overlay={"kind": "attempt", "title": label,
                                 "sub": "Only tools: run, write_file, read_file, fetch_url (inside a fresh container)"})
        state.update(lines=[], caption="", overlay=None)
        t0 = next((e["t"] for e in evs if e.get("t")), 0)
        last_t, calls, steps = t0, 0, 0
        pending_err = False
        for e in evs:
            t = e.get("t") or last_t
            gap = t - last_t
            if gap > IDLE_MAX:
                state["counter"] = {"label": label, "elapsed": mmss(last_t - t0 + IDLE_MAX), "calls": calls,
                                    "skip": f"⏩ {int(gap)} s skipped"}
                timemap.append((v, t - gap))
                push(IDLE_TO)
                state["counter"].pop("skip", None)
            elif gap > 0:
                # hold the previous state, ticking the clock once a second
                held = 0.0
                while held + 1.0 < gap:
                    state["counter"] = {"label": label, "elapsed": mmss(last_t - t0 + held), "calls": calls}
                    push(1.0)
                    held += 1.0
                state["counter"] = {"label": label, "elapsed": mmss(last_t - t0 + held), "calls": calls}
                push(gap - held)
            last_t = t
            timemap.append((v, t))
            el = mmss(t - t0)
            k = e["kind"]
            if k == "text":
                state["caption"] = short(e["text"], 260)
                captions.append((v, e["text"], t))
                state["counter"] = {"label": label, "elapsed": el, "calls": calls}
                push(0.8)
            elif k == "call":
                calls += 1
                tool, inp = e["tool"], e.get("input") or {}
                state["counter"] = {"label": label, "elapsed": el, "calls": calls}
                if tool == "run":
                    cmd = inp.get("command", "")
                    first_line = cmd.splitlines()[0] if cmd else ""
                    extra = len(cmd.splitlines()) - 1
                    if first["command"] is None:
                        first["command"] = v
                        markers.append((v, "first command", short(first_line, 80), t))
                    base = list(state["lines"])
                    for i in range(1, TYPE_STEPS + 1):
                        part = first_line[: max(1, len(first_line) * i // TYPE_STEPS)]
                        state["lines"] = (base + [{"k": "cmd", "s": "$ " + part}])[-MAX_LINES:]
                        push(TYPE_S / TYPE_STEPS)
                    tail = [{"k": "cmd2", "s": "  " + short(l, 150, keep_space=True)} for l in cmd.splitlines()[1:9]]
                    if extra > 8:
                        tail.append({"k": "meta", "s": f"  … {extra - 8} more lines"})
                    state["lines"] = (base + [{"k": "cmd", "s": "$ " + short(first_line, 150)}] + tail)[-MAX_LINES:]
                    push(0.3)
                elif tool == "write_file":
                    body = (inp.get("content") or "").splitlines()
                    shown = [{"k": "file", "s": "  " + short(l, 150, keep_space=True)} for l in body[:10]]
                    if len(body) > 10:
                        shown.append({"k": "meta", "s": f"  … {len(body) - 10} more lines"})
                    state["lines"] = (state["lines"] + [{"k": "cmd", "s": f"✎ write {inp.get('path')} ({len(body)} lines)"}] + shown)[-MAX_LINES:]
                    push(0.6)
                elif tool in ("fetch_url", "WebFetch"):
                    state["lines"] = (state["lines"] + [{"k": "cmd", "s": f"⤓ fetch {short(inp.get('url', ''), 140)}"}])[-MAX_LINES:]
                    push(0.5)
                else:
                    state["lines"] = (state["lines"] + [{"k": "cmd", "s": f"▸ {tool} {short(json.dumps(inp), 120)}"}])[-MAX_LINES:]
                    push(0.4)
            elif k == "result":
                lines, code = out_lines(e.get("output", ""))
                is_err = e.get("error") or (code and code != "[exit code 0]")
                if is_err and first["error"] is None and code:
                    first["error"] = v
                    markers.append((v, "first error", short(lines[-1] if lines else code, 80), t))
                    pending_err = True
                elif not is_err and pending_err and code == "[exit code 0]" and first["fix"] is None:
                    first["fix"] = v
                    markers.append((v, "fix", "first clean run after the first error", t))
                    pending_err = False
                kind = "err" if is_err else "out"
                add = [{"k": kind, "s": l} for l in lines]
                if code:
                    add.append({"k": "err" if is_err else "meta", "s": code})
                if len(lines) > 60 and kind == "out":
                    add = add[:4] + [{"k": "meta", "s": f"… {len(lines)} lines of output"}]
                state["lines"] = (state["lines"] + add)[-MAX_LINES:]
                state["counter"] = {"label": label, "elapsed": el, "calls": calls}
                push(min(READ_MAX, 0.7 + READ_PER_LINE * len(add)))
            elif k == "done":
                state["counter"] = {"label": label, "elapsed": el, "calls": calls}
                ok = att["check"]["passed"]
                state["lines"] = (state["lines"] + [{"k": "ok" if ok else "err",
                                                      "s": f"■ agent stopped ({e.get('stop')}) · hidden check {'PASSED' if ok else 'failed'}"}])[-MAX_LINES:]
                if ok:
                    markers.append((v, "success", "hidden check passed", t))
                push(1.5)
    t = res["totals"]
    push(CARD_S, overlay={"kind": "verdict", "verdict": res["verdict"], "reason": res["verdict_reason"],
                          "minutes": t.get("minutes_to_success"), "wall": t.get("wall_minutes"),
                          "usd": t.get("api_equiv_usd"),
                          "agents": [f"{a['agent']} · {a['model']}" for a in res["attempts"]],
                          "tool": head["tool"], "version": head["version"], "date": head["date"]})
    return {"duration": round(v, 3), "frames": frames, "timemap": timemap}, captions, markers


def main(run, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tl, caps, marks = build(run)
    (out / "timemap.csv").write_text("video_seconds,wall_clock_unix\n" + "".join(f"{v:.3f},{t:.3f}\n" for v, t in tl["timemap"]))
    (out / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False))
    srt = []
    for i, (v, text, _t) in enumerate(caps):
        end = caps[i + 1][0] if i + 1 < len(caps) else min(v + 6, tl["duration"])
        end = min(end, v + 8)
        srt.append(f"{i + 1}\n{srt_time(v)} --> {srt_time(max(end, v + 1.5))}\n{text.strip()}\n")
    (out / "captions.srt").write_text("\n".join(srt))
    (out / "markers.csv").write_text("video_seconds,timecode_30fps,wall_clock_unix,event,detail\n" + "".join(
        f"{v:.2f},{tc(v)},{t:.3f},{ev},\"{d.replace(chr(34), chr(39))}\"\n" for v, ev, d, t in marks))
    print(f"{len(tl['frames'])} keyframes, {tl['duration']:.1f} s of video, {len(caps)} captions, {len(marks)} markers")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
