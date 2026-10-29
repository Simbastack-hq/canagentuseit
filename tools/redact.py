#!/usr/bin/env python3
"""Make the public copy of a run: <run>/public/, with secrets and machine details stripped.

  redact.py <run-dir>            writes <run-dir>/public/ (text files redacted, binaries skipped except video)
  redact.py --check <path>...    exit 1 if any file still contains something redact.py would strip
  redact.py --stdin              redact stdin to stdout

Nothing raw leaves the test machine: the writer reads only public/, and promote.py copies only
public/ into the repo. What gets stripped:
  - API keys and tokens (Anthropic, OpenAI, GitHub, Stripe, Resend, Slack, AWS, Google, HF, npm, PyPI,
    JWTs, Bearer headers, long hex/base64 secrets after key=/token=/secret=/password=)
  - email addresses (except example.com/.org and noreply addresses)
  - home paths (/home/<user>, /Users/<user>, /root) and the harness's scratch/run paths
  - host names (this lab's and anything *.ts.net / *.local), private and tailnet IPs
Extra patterns can be added per machine in $CAUI_REDACT_EXTRA (one regex per line), e.g. the lab's
public IP; that file lives outside the repo.
"""
import os
import re
import shutil
import sys
from pathlib import Path

RULES = [
    (r"sk-ant-[A-Za-z0-9_\-]{20,}", "[REDACTED:anthropic-key]"),
    (r"sk-(?:proj-|live-|test-)?[A-Za-z0-9_\-]{20,}", "[REDACTED:api-key]"),
    (r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}", "[REDACTED:github-token]"),
    (r"\bgithub_pat_[A-Za-z0-9_]{40,}", "[REDACTED:github-token]"),
    (r"\bwhsec_[A-Za-z0-9+/=]{20,}", "[REDACTED:webhook-secret]"),
    (r"\b(?:rk|pk|sk)_(?:live|test)_[A-Za-z0-9]{16,}", "[REDACTED:stripe-key]"),
    (r"\bre_[A-Za-z0-9]{8,}_[A-Za-z0-9]{16,}", "[REDACTED:resend-key]"),
    (r"\bxox[abposr]-[A-Za-z0-9\-]{10,}", "[REDACTED:slack-token]"),
    (r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", "[REDACTED:aws-key]"),
    (r"\bAIza[0-9A-Za-z_\-]{35}\b", "[REDACTED:google-key]"),
    (r"\bhf_[A-Za-z0-9]{30,}\b", "[REDACTED:hf-token]"),
    (r"\bnpm_[A-Za-z0-9]{30,}\b", "[REDACTED:npm-token]"),
    (r"\bpypi-[A-Za-z0-9_\-]{40,}", "[REDACTED:pypi-token]"),
    (r"\bkk_live_[A-Za-z0-9]{8,}", "[REDACTED:api-key]"),
    (r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", "[REDACTED:jwt]"),
    (r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._\-+/=]{12,}", r"\1[REDACTED:bearer]"),
    (r"(?i)\b((?:api[_-]?key|access[_-]?token|auth[_-]?token|secret|password|passwd|client[_-]?secret)[\"']?\s*[:=]\s*[\"']?)(?!\[REDACTED)[A-Za-z0-9._\-+/=]{12,}", r"\1[REDACTED:secret]"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", "[REDACTED:private-key]"),
    # emails (keep example domains and noreply)
    (r"\b(?![A-Za-z0-9._%+\-]*noreply)[A-Za-z0-9._%+\-]+@(?!example\.(?:com|org|net)\b)[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "[REDACTED:email]"),
    # machine details
    (r"/(?:home|Users)/(?!dev\b)[A-Za-z0-9._\-]+", "/home/[user]"),
    (r"/root\b", "/home/[user]"),
    (r"/(?:private/)?(?:tmp|var/folders)/[A-Za-z0-9._/\-]*caui-scratch-[A-Za-z0-9_]+", "[scratch]"),
    (r"\b[A-Za-z0-9\-]+\.(?:tail[a-z0-9]+\.)?ts\.net\b", "[host]"),
    (r"\bhel-lab\b|\bdev-server(?:-nj)?\b", "[host]"),
    (r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b", "[tailnet-ip]"),
    (r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|\b192\.168\.\d{1,3}\.\d{1,3}\b|\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b", "[private-ip]"),
]


def rules():
    extra = os.environ.get("CAUI_REDACT_EXTRA", str(Path.home() / ".config/caui/redact-extra.txt"))
    out = [(re.compile(p), r) for p, r in RULES]
    try:
        for line in Path(extra).read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                out.append((re.compile(line.strip()), "[REDACTED:local]"))
    except FileNotFoundError:
        pass
    return out


R = rules()


def redact(text):
    for rx, rep in R:
        text = rx.sub(rep, text)
    return text


def hits(text):
    return [(rep, m.group(0)[:12] + "…") for rx, rep in R for m in rx.finditer(text)
            if not m.group(0).startswith(("[REDACTED", "/home/[user]", "[host]", "[scratch]"))]


TEXT = {".json", ".jsonl", ".md", ".txt", ".out", ".log", ".csv", ".srt", ".cast", ".stderr", ".sh", ".py", ".js", ".ts", ".toml", ".yaml", ".yml"}
COPY_BINARY = {".webm", ".mp4", ".png"}
WORK_TEXT = {"", ".cfg", ".ini", ".env.example", ".html", ".css", ".mjs", ".cjs", ".tsx", ".jsx", ".rs", ".go", ".rb", ".lock", ".gitignore"}
SKIP = {"work.tgz", "mcp.json", "raw.stderr"}   # the work tarball is unreviewable as a blob; mcp.json holds host paths


def make_public(run):
    run = Path(run)
    pub = run / "public"
    if pub.exists():
        shutil.rmtree(pub)
    n = 0
    for p in sorted(run.rglob("*")):
        if p.is_dir() or pub in p.parents or p.name in SKIP or p.is_symlink():
            continue
        rel = p.relative_to(run)
        dest = pub / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix in TEXT or ("work-files" in rel.parts and p.suffix in WORK_TEXT):
            dest.write_text(redact(p.read_text(errors="replace")))
            n += 1
        elif p.suffix in COPY_BINARY:
            shutil.copy2(p, dest)
    left = [(str(f), h) for f in pub.rglob("*") if f.is_file() and f.suffix in TEXT for h in hits(f.read_text(errors="replace"))]
    if left:
        sys.exit(f"redaction left matches, refusing: {left[:5]}")
    print(f"{n} files redacted into {pub}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--stdin"]:
        sys.stdout.write(redact(sys.stdin.read()))
    elif a[:1] == ["--check"]:
        bad = 0
        for f in a[1:]:
            try:
                h = hits(Path(f).read_text(errors="replace"))
            except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
                continue
            for rep, sample in h:
                print(f"{f}: {rep} ({sample})")
                bad += 1
        sys.exit(1 if bad else 0)
    elif len(a) == 1:
        make_public(a[0])
    else:
        sys.exit(__doc__)
