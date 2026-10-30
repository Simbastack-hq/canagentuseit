#!/usr/bin/env python3
"""Hidden acceptance check for the doc-search job. Never shown to the agent: the harness copies it
into the box only after the agent has stopped. Stdlib only.

  check.py <chroma|lancedb|pgvector>            run every step on fresh random data, print a report;
                                                last line is CHECK_JSON {...}; exit 0 only if all pass
  check.py --fixtures <dir>                     write the sample data the agent gets (seed 1)

The steps follow JOB.md: cold start on an empty /work/data, add, count, cosine top-k, category
filter, replace by id, delete (with unknown ids), clean restart, hard kill, add after restart, and
proof that the named product holds the data.
"""
import json
import math
import os
import random
import signal
import subprocess
import sys
import time
from pathlib import Path

DIM, N, CATS = 64, 300, ["news", "docs", "blog", "faq"]
WORK, DATA, TMP = Path("/work"), Path("/work/data"), Path("/tmp/check")
CMD_TIMEOUT = 180


def gen_docs(rng, n, start=0):
    docs = []
    for i in range(start, start + n):
        v = [rng.gauss(0, 1) for _ in range(DIM)]
        s = rng.choice([0.2, 0.5, 1, 3, 8])  # varied norms: cosine and L2 rank differently
        docs.append({"id": f"doc-{i:05d}", "text": f"document {i} {rng.choice(['alpha', 'beta', 'gamma', 'delta'])}",
                     "category": rng.choice(CATS), "vector": [round(x * s, 6) for x in v]})
    return docs


def cos(a, b):
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def exact(store, q, k=5, cat=None):
    scored = sorted(((cos(d["vector"], q), i) for i, d in store.items() if cat is None or d["category"] == cat), reverse=True)
    return [i for _, i in scored[:k]], {i: s for s, i in scored}


def near(rng, v, noise=0.15):
    return [round(x + rng.gauss(0, noise * (math.sqrt(sum(y * y for y in v)) / math.sqrt(DIM))), 6) for x in v]


def sh(cmd, timeout=CMD_TIMEOUT):
    t = time.time()
    try:
        p = subprocess.run(["bash", "-lc", cmd], cwd=WORK, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr, round(time.time() - t, 1)
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout", timeout


def write_jsonl(name, docs):
    p = TMP / name
    p.write_text("".join(json.dumps(d) + "\n" for d in docs))
    return p


def write_vec(name, v):
    p = TMP / name
    p.write_text(json.dumps(v))
    return p


def ancestors():
    out, pid = {os.getpid()}, os.getpid()
    while pid > 1:
        try:
            pid = int(next(l for l in open(f"/proc/{pid}/status") if l.startswith("PPid:")).split()[1])
        except (OSError, StopIteration):
            break
        out.add(pid)
    return out


def kill_others():
    """Everything of ours outside this check's own process chain: what a reboot or crash does."""
    keep, n = ancestors(), 0
    for p in Path("/proc").iterdir():
        if p.name.isdigit() and int(p.name) > 1 and int(p.name) not in keep:
            try:
                if p.stat().st_uid == os.getuid():
                    os.kill(int(p.name), signal.SIGKILL)
                    n += 1
            except OSError:
                pass
    time.sleep(1)
    return n


class Check:
    def __init__(self, product):
        self.product, self.steps, self.store, self.rng = product, [], {}, random.Random()

    def step(self, name, ok, detail):
        self.steps.append({"step": name, "passed": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)
        return ok

    def run(self, args):
        rc, out, err, t = sh(f"./docsearch {args}")
        return rc, out, err, t

    def ids_out(self, out):
        return [l.strip() for l in out.splitlines() if l.strip() in self.known]

    def count(self):
        rc, out, err, _ = self.run("count")
        nums = [int(w) for w in out.split() if w.isdigit()]
        return (nums[-1] if rc == 0 and nums else None), rc, err

    def queries(self, label, k=5, cat=None, n=8, vecs=None):
        """Near-copies of stored vectors as queries; each must recall >= 4 of the exact top-5 and
        put one of the exact top-2 first."""
        bad, times, results = [], [], {}
        pool = [i for i, d in self.store.items() if cat is None or d["category"] == cat]
        vecs = vecs or [near(self.rng, self.store[i]["vector"]) for i in self.rng.sample(pool, min(n, len(pool)))]
        for j, q in enumerate(vecs):
            f = write_vec(f"q-{label}-{j}.json", q)
            rc, out, err, t = self.run(f"query {f} --k {k}" + (f" --category {cat}" if cat else ""))
            times.append(t)
            got = self.ids_out(out)
            want, _ = exact(self.store, q, k, cat)
            results[j] = got
            recall = len(set(got[:k]) & set(want)) / max(1, len(want))
            if rc != 0 or recall < 0.8 or not got or got[0] not in want[:2] or (cat and any(self.store.get(g, {}).get("category") != cat for g in got)):
                bad.append({"q": j, "exit": rc, "got": got[:k], "want": want, "stderr": err[-300:]})
        return bad, times, results, vecs

    def probe(self, probe_id, since):
        """The named product holds the data: its storage under /work/data, written after `since`."""
        files = [p for p in DATA.rglob("*") if p.is_file()] if DATA.exists() else []
        def has_bytes(paths):
            b = probe_id.encode()
            for p in paths:
                try:
                    if b in p.read_bytes():
                        return True
                except OSError:
                    pass
            return False
        if self.product == "chroma":
            db = [p for p in files if p.name.startswith("chroma.sqlite3")]
            return bool(db) and has_bytes(db), f"chroma.sqlite3 files: {len(db)}"
        if self.product == "lancedb":
            tables = {p for f in files for p in f.parents if p.suffix == ".lance"}
            fresh = [f for f in files if any(t in f.parents for t in tables) and f.stat().st_mtime >= since]
            return bool(tables) and bool(fresh), f".lance tables: {len(tables)}, files written since the add: {len(fresh)}"
        if self.product == "pgvector":
            roots = {p.parent for p in files if p.name == "PG_VERSION" and p.parent.joinpath("global").exists()}
            pgf = [f for f in files if any(r in f.parents for r in roots)]
            return bool(roots) and has_bytes(pgf), f"Postgres data dirs: {len(roots)}"
        return False, "unknown product"

    def main(self):
        TMP.mkdir(parents=True, exist_ok=True)
        ok = self.step("files present", (WORK / "docsearch").exists() and (WORK / "start.sh").exists() and (WORK / "stop.sh").exists(),
                       "docsearch, start.sh, stop.sh")
        if not ok:
            return
        # Cold start: the agent's own test data goes aside; start.sh must cope with an empty /work/data.
        sh("bash ./stop.sh", 120)
        kill_others()
        if DATA.exists():
            DATA.rename(TMP / f"agent-data-{int(time.time())}")
        rc, out, err, t = sh("bash ./start.sh", 300)
        if not self.step("cold start", rc == 0, f"start.sh on an empty /work/data exited {rc} in {t}s {err[-200:]}"):
            return
        docs = gen_docs(self.rng, N)
        self.known = {d["id"] for d in docs} | {f"doc-{i:05d}" for i in range(N, N + 100)}
        probe = f"doc-{self.rng.randrange(N):05d}"
        t_add = time.time() - 2
        rc, out, err, t = self.run(f"add {write_jsonl('docs.jsonl', docs)}")
        self.store = {d["id"]: d for d in docs}
        c, crc, _ = self.count()
        self.step("add and count", rc == 0 and c == N, f"add {N} docs exited {rc} in {t}s; count says {c}")
        bad, times, before, vecs = self.queries("base")
        self.step("cosine top-5", not bad, f"{8 - len(bad)}/8 queries right; slowest {max(times)}s" + (f"; first miss {bad[0]}" if bad else ""))
        cat = self.rng.choice(CATS)
        bad, times, _, _ = self.queries("cat", cat=cat, n=5)
        self.step("category filter", not bad, f"--category {cat}: {5 - len(bad)}/5 right" + (f"; first miss {bad[0]}" if bad else ""))
        # Replace by id: same ids, new vectors and categories; no duplicates.
        upd = self.rng.sample(sorted(self.store), 30)
        new = []
        for i in upd:
            d = dict(self.store[i])
            d["vector"] = [round(self.rng.gauss(0, 1) * 2, 6) for _ in range(DIM)]
            d["category"] = self.rng.choice([c for c in CATS if c != d["category"]])
            new.append(d)
        rc, out, err, t = self.run(f"add {write_jsonl('update.jsonl', new)}")
        for d in new:
            self.store[d["id"]] = d
        c, _, _ = self.count()
        miss = []
        for d in new[:6]:
            f = write_vec(f"u-{d['id']}.json", d["vector"])
            _, o, _, _ = self.run(f"query {f} --k 3")
            _, oc, _, _ = self.run(f"query {f} --k 3 --category {d['category']}")
            g, gc = self.ids_out(o), self.ids_out(oc)
            if not g or g[0] != d["id"] or not gc or gc[0] != d["id"]:
                miss.append({"id": d["id"], "got": g, "got_in_new_category": gc})
        self.step("replace by id", rc == 0 and c == N and not miss,
                  f"re-added 30 ids exited {rc}; count {c} (want {N}); new vectors and categories found: {6 - len(miss)}/6" + (f"; first miss {miss[0]}" if miss else ""))
        # Delete, including two ids that never existed.
        dels = self.rng.sample(sorted(self.store), 40)
        rc, out, err, t = self.run("delete " + " ".join(dels + ["doc-99998", "nope-1"]))
        gone_vecs = [self.store[i]["vector"] for i in dels[:6]]
        for i in dels:
            self.store.pop(i)
        c, _, _ = self.count()
        back = []
        for j, v in enumerate(gone_vecs):
            _, o, _, _ = self.run(f"query {write_vec(f'd-{j}.json', v)} --k 10")
            back += [g for g in self.ids_out(o) if g in dels]
        self.step("delete", rc == 0 and c == N - 40 and not back,
                  f"deleting 40 ids + 2 unknown exited {rc} {err[-200:]}; count {c} (want {N - 40}); deleted ids still returned: {sorted(set(back))[:5]}")
        bad, _, before, vecs = self.queries("pre-restart")
        # Clean restart.
        rc1, _, e1, _ = sh("bash ./stop.sh", 120)
        n = kill_others()
        rc2, _, e2, t2 = sh("bash ./start.sh", 300)
        c, _, _ = self.count()
        bad2, _, after, _ = self.queries("post-restart", vecs=vecs)
        same = sum(before[j][:5] == after[j][:5] for j in before)
        self.step("clean restart", rc1 == 0 and rc2 == 0 and c == N - 40 and not bad2,
                  f"stop.sh {rc1}, {n} leftover processes killed, start.sh {rc2} in {t2}s; count {c} (want {N - 40}); queries right {8 - len(bad2)}/8, identical to before {same}/8")
        # Hard kill: no stop.sh.
        n = kill_others()
        rc, _, err, t = sh("bash ./start.sh", 300)
        c, _, _ = self.count()
        bad3, _, _, _ = self.queries("post-kill", n=4)
        self.step("hard kill", rc == 0 and c == N - 40 and not bad3,
                  f"killed {n} processes without stop.sh; start.sh {rc} in {t}s {err[-200:]}; count {c} (want {N - 40}); queries right {4 - len(bad3)}/4")
        extra = gen_docs(self.rng, 10, start=N)
        rc, _, err, _ = self.run(f"add {write_jsonl('extra.jsonl', extra)}")
        for d in extra:
            self.store[d["id"]] = d
        c, _, _ = self.count()
        bad4, _, _, _ = self.queries("after-add", n=4)
        self.step("add after restart", rc == 0 and c == N - 30 and not bad4, f"add 10 exited {rc}; count {c} (want {N - 30}); queries right {4 - len(bad4)}/4")
        if probe not in self.store:
            probe = next(iter(self.store))
        ok, detail = self.probe(probe, t_add)
        self.step(f"{self.product} holds the data", ok, detail)


def fixtures(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(1)
    docs = gen_docs(rng, 20)
    store = {d["id"]: d for d in docs}
    (out / "docs.jsonl").write_text("".join(json.dumps(d) + "\n" for d in docs))
    lines = []
    for j in range(3):
        q = near(rng, rng.choice(docs)["vector"])
        (out / f"query-{j}.json").write_text(json.dumps(q))
        want, _ = exact(store, q, 5)
        lines.append(f"$ ./docsearch query job/fixtures/query-{j}.json\n" + "\n".join(want))
    want, _ = exact(store, json.loads((out / "query-0.json").read_text()), 3, "docs")
    lines.append("$ ./docsearch query job/fixtures/query-0.json --k 3 --category docs\n" + "\n".join(want))
    (out / "expected.txt").write_text("\n\n".join(lines) + "\n")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--fixtures"] and len(a) == 2:
        fixtures(a[1])
    elif len(a) == 1 and a[0] in ("chroma", "lancedb", "pgvector"):
        c = Check(a[0])
        try:
            c.main()
        except Exception as e:
            c.step("check crashed", False, repr(e))
        passed = bool(c.steps) and all(s["passed"] for s in c.steps)
        print("CHECK_JSON " + json.dumps({"product": a[0], "passed": passed, "steps": c.steps}))
        sys.exit(0 if passed else 1)
    else:
        sys.exit(__doc__)
