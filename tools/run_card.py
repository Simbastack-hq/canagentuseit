#!/usr/bin/env python3
"""Run one test brief: fresh container, agent brain on the host, container as its only shell.

  run_card.py <brief.json> <run-dir>

Attempt 1: Claude Code (CAUI_CLAUDE_MODEL). If the hidden success check fails, attempt 2 in a new
container: Codex CLI (CAUI_CODEX_MODEL), a different model family. Both see the same task text and
the same sandbox MCP tools (tools/sandbox_mcp.py) and nothing else: no host shell, no host files,
none of the operator's settings, memory or other MCP servers.

Writes, per attempt: raw.jsonl (agent stream, each line stamped with wall-clock `_t`), events.jsonl
(normalized), box-log.jsonl (every sandbox call with start/end), transcript.md, check.out,
version.out, references.out, work.tgz, attempt.json. Then docs-walk B-roll and result.json.
Everything stays in <run-dir>, outside any git repo; tools/redact.py makes the public copy.

Env: CAUI_BOX (how to call caui-box; default "sudo -n -u caui-tester /usr/local/bin/caui-box"),
CAUI_CLAUDE_MODEL [claude-sonnet-5-5], CAUI_CODEX_MODEL [gpt-6-astra], CAUI_TIME_LIMIT_S [1200],
CAUI_MAX_TURNS [80], CAUI_ATTEMPTS ["claude codex"].
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOX = shlex.split(os.environ.get("CAUI_BOX", "sudo -n -u caui-tester /usr/local/bin/caui-box"))
CLAUDE_MODEL = os.environ.get("CAUI_CLAUDE_MODEL", "claude-sonnet-5-5")
CODEX_MODEL = os.environ.get("CAUI_CODEX_MODEL", "gpt-6-astra")
TIME_LIMIT = int(os.environ.get("CAUI_TIME_LIMIT_S", "1200"))
MAX_TURNS = os.environ.get("CAUI_MAX_TURNS", "80")
ATTEMPTS = os.environ.get("CAUI_ATTEMPTS", "claude codex").split()
SYSTEM = (HERE.parent / "prompts/tester-system.md").read_text().strip()
TOOLS = ["mcp__sandbox__run", "mcp__sandbox__write_file", "mcp__sandbox__read_file", "mcp__sandbox__fetch_url"]
# Codex features that could give the agent anything besides the sandbox tools. Switched off when the
# installed version has them; any non-sandbox tool event still invalidates the attempt.
CODEX_OFF = ["shell_tool", "unified_exec", "unified_exec_tty", "view_image", "apps", "plugins", "multi_agent",
             "browser_use", "browser_use_external", "browser_use_full_cdp_access", "computer_use", "image_generation",
             "skill_search", "skill_mcp_dependency_install", "goals", "hooks", "tool_suggest", "sleep_tool",
             "write_stdin_approval", "worktrees", "in_app_browser", "standalone_web_search", "web_search_request"]


def box(*args, stdin=None, timeout=1000, binary=False):
    p = subprocess.run(BOX + list(args), input=stdin, capture_output=True, timeout=timeout)
    out = p.stdout if binary else p.stdout.decode("utf-8", "replace")
    return p.returncode, out, p.stderr.decode("utf-8", "replace")


def codex_version():
    try:
        return subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=30).stdout.split()[-1]
    except Exception:
        return "?"


def stream(cmd, raw_path, cwd, env, inventory=None):
    """Run cmd, stamp each stdout line with _t, kill at TIME_LIMIT. Returns (exit, timed_out, bad_tool).
    inventory(ev) returns a reason string when an event shows a tool outside the sandbox set; the run
    is killed on the spot and the attempt marked invalid."""
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=open(Path(raw_path).with_suffix(".stderr"), "w"), text=True)
    timer = threading.Timer(TIME_LIMIT, proc.kill)
    timer.start()
    with open(raw_path, "w") as f:
        for line in proc.stdout:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            ev["_t"] = round(time.time(), 3)
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            f.flush()
            bad = inventory(ev) if inventory else None
            if bad:
                proc.kill()
                Path(raw_path).with_name("invalid.txt").write_text(bad)
                break
    proc.wait()
    timed_out = not timer.is_alive() and proc.returncode != 0
    timer.cancel()
    return proc.returncode, timed_out


def mcp_env(cid, d):
    return {"CAUI_RUN": cid, "CAUI_BOX": shlex.join(BOX), "CAUI_LOG": str(d / "box-log.jsonl")}


def generic_probe(v):
    pkg = v["package"]
    if v["source"] == "pypi":
        n = re.sub(r"[-_.]+", "_", pkg).lower()
        return (f"find / -xdev -maxdepth 8 -type d -iname '{n}-*.dist-info' 2>/dev/null | grep -v '^/usr/lib/python3/' "
                f"| sed 's#.*/##' | sort -u | head")
    if v["source"] == "npm":
        return (f"find /work /home/dev -maxdepth 7 -path '*/node_modules/{pkg}/package.json' 2>/dev/null "
                f"| xargs -r -n1 sh -c 'printf \"%s \" \"$0\"; jq -r .version \"$0\"' | head")
    return "true"


def run_claude(task, cid, d, scratch):
    cfg = d / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"sandbox": {
        "command": sys.executable, "args": [str(HERE / "sandbox_mcp.py")], "env": mcp_env(cid, d)}}}))
    cmd = ["claude", "-p", task, "--model", CLAUDE_MODEL, "--output-format", "stream-json", "--verbose",
           "--max-turns", MAX_TURNS, "--permission-mode", "dontAsk", "--setting-sources", "project",
           "--strict-mcp-config", "--mcp-config", str(cfg), "--append-system-prompt", SYSTEM,
           "--tools", "", "--allowedTools", *TOOLS]
    def inventory(ev):
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            extra = sorted(set(ev.get("tools") or []) - set(TOOLS))
            servers = [m.get("name") for m in ev.get("mcp_servers") or [] if m.get("name") != "sandbox"]
            if extra or servers:
                return f"tool inventory not sandbox-only: tools={extra} mcp={servers}"
    rc, to = stream(cmd, d / "raw.jsonl", scratch, os.environ.copy(), inventory)
    subprocess.run([sys.executable, HERE / "transcript.py", "normalize", "claude", d / "raw.jsonl", d / "events.jsonl"])
    return rc, to


def run_codex(task, cid, d, scratch):
    env = mcp_env(cid, d)
    envtoml = "{" + ",".join(f'{k}="{v}"' for k, v in env.items()) + "}"
    have = subprocess.run(["codex", "features", "list"], capture_output=True, text=True).stdout.split()
    off = [x for f in CODEX_OFF if f in have for x in ("--disable", f)]
    cmd = ["codex", "exec", "--json", "-m", CODEX_MODEL, "-s", "read-only", "--skip-git-repo-check", "-C", str(scratch),
           *off, "-c", 'web_search="disabled"',
           "-c", f'mcp_servers.sandbox.command="{sys.executable}"',
           "-c", f'mcp_servers.sandbox.args=["{HERE / "sandbox_mcp.py"}"]',
           "-c", f"mcp_servers.sandbox.env={envtoml}",
           # The sandbox tools are the whole point; without this, exec mode refuses every call.
           "-c", 'mcp_servers.sandbox.default_tools_approval_mode="approve"',
           f"{SYSTEM}\n\n---\n\n{task}"]
    def inventory(ev):
        it = (ev.get("item") or {})
        if it.get("type") in ("command_execution", "web_search", "file_change", "collab_tool_call", "image_generation"):
            return f"codex used a non-sandbox tool: {it.get('type')}"
        if it.get("type") == "mcp_tool_call" and it.get("server") not in (None, "sandbox"):
            return f"codex called MCP server {it.get('server')}"
    rc, to = stream(cmd, d / "raw.jsonl", scratch, os.environ.copy(), inventory)
    subprocess.run([sys.executable, HERE / "transcript.py", "normalize", "codex", d / "raw.jsonl", d / "events.jsonl",
                    CODEX_MODEL, codex_version()])
    return rc, to


def attempt(n, agent, brief, run_dir):
    d = run_dir / f"attempt-{n}"
    d.mkdir(parents=True, exist_ok=True)
    cid = re.sub(r"[^a-z0-9-]", "-", f"{run_dir.name.lower()}-a{n}")[-90:].strip("-")
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()
    rc, image, err = box("start", cid)
    if rc != 0:
        (d / "harness-error.txt").write_text(f"container start failed: {err}")
        return None
    image = image.strip()
    scratch = Path(tempfile.mkdtemp(prefix="caui-scratch-"))
    try:
        if agent == "claude":
            arc, timed_out = run_claude(brief["task_text"], cid, d, scratch)
            model = CLAUDE_MODEL
        else:
            arc, timed_out = run_codex(brief["task_text"], cid, d, scratch)
            model = CODEX_MODEL
        wall = time.time() - t0
        if timed_out:
            (d / "agent.exit").write_text("124")
        chk = brief["check"]
        # Leftover background processes must not make an incomplete run.sh pass.
        box("exec", cid, "20", "kill -9 -1 2>/dev/null; true")
        crc, cout, _ = box("exec", cid, "180", chk["command"])
        (d / "check.out").write_text(cout)
        _, vout, _ = box("exec", cid, "120", chk["version_probe"])
        # Fallback that doesn't depend on where the agent put things: installed package metadata anywhere.
        _, gout, _ = box("exec", cid, "60", generic_probe(brief["version"]))
        (d / "version.out").write_text(f"{vout}\n--- installed metadata ---\n{gout}")
        pats = " ".join(f"-e {shlex.quote(s)}" for s in chk["must_reference"])
        _, rout, _ = box("exec", cid, "60", f"grep -rIlF --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git {pats} /work || true")
        (d / "references.out").write_text(rout)
        _, tgz, _ = box("tarwork", cid, binary=True)
        (d / "work.tgz").write_bytes(tgz)
    finally:
        box("rm", cid)
        shutil.rmtree(scratch, ignore_errors=True)
    with open(d / "transcript.md", "w") as f:
        subprocess.run([sys.executable, HERE / "transcript.py", "md", d / "events.jsonl"], stdout=f)
    with open(d / "facts.json", "w") as f:
        subprocess.run([sys.executable, HERE / "transcript.py", "facts", d / "events.jsonl"], stdout=f)
    subprocess.run([sys.executable, HERE / "verdict.py", "attempt", run_dir / "brief.json", d, str(n), model, image,
                    started, str(int(wall)), str(crc)])
    return json.loads((d / "attempt.json").read_text())


def docs_walk(brief, run_dir):
    from urllib.parse import urlparse
    host = urlparse(brief["docs_url"]).hostname
    urls = [brief["docs_url"]]
    for p in sorted(run_dir.glob("attempt-*/facts.json")):
        for u in json.loads(p.read_text())["urls_fetched"]:
            if urlparse(u).hostname == host and u not in urls:
                urls.append(u)
    (run_dir / "video").mkdir(exist_ok=True)
    rc, webm, err = box("docswalk", re.sub(r"[^a-z0-9-]", "-", run_dir.name.lower())[-80:].strip("-") + "-dw",
                        stdin="\n".join(urls[:8]).encode(), binary=True, timeout=600)
    (run_dir / "video/docs-walk.log").write_text(err)
    if rc == 0 and webm:
        (run_dir / "video/docs-broll.webm").write_bytes(webm)


def main():
    brief_p, run_dir = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    brief = json.loads(brief_p.read_text())
    shutil.copy(brief_p, run_dir / "brief.json")
    (run_dir / "task.txt").write_text(brief["task_text"])
    # Decoy: the check must FAIL on an untouched box, or it can't tell success from an error message.
    cid = re.sub(r"[^a-z0-9-]", "-", f"{run_dir.name.lower()}-decoy")[-90:].strip("-")
    box("start", cid)
    drc, dout, _ = box("exec", cid, "180", brief["check"]["command"])
    box("rm", cid)
    decoy_passed = drc == brief["check"]["expect_exit"] and re.search(brief["check"]["stdout_regex"], dout, re.M)
    (run_dir / "decoy.json").write_text(json.dumps({"exit": drc, "passed": bool(decoy_passed), "output_tail": dout[-1500:]}, indent=2))
    if decoy_passed:
        subprocess.run([sys.executable, HERE / "verdict.py", "result", run_dir / "brief.json", run_dir])
        return
    # Attempts: an attempt that died for our reasons (API, harness, tool inventory) is re-run once with the
    # same agent; it never counts against the tool.
    n, queue, reruns = 0, list(ATTEMPTS), 0
    while queue:
        agent = queue.pop(0)
        n += 1
        a = attempt(n, agent, brief, run_dir)
        if a and a["check"]["passed"]:
            break
        if (a is None or not a.get("valid", True)) and reruns < 1:
            reruns += 1
            queue.insert(0, agent)
    try:
        docs_walk(brief, run_dir)
    except Exception as e:
        (run_dir / "video").mkdir(exist_ok=True)
        (run_dir / "video/docs-walk.log").write_text(f"docs walk failed: {e}")
    subprocess.run([sys.executable, HERE / "verdict.py", "result", run_dir / "brief.json", run_dir])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main()
