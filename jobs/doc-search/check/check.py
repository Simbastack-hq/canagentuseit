#!/usr/bin/env python3
"""Hidden acceptance check for the doc-search job. Never shown to the agent: the harness copies it
into the box only after the agent has stopped. Stdlib only.

  check.py <chroma|lancedb|pgvector> <seed> <version>
                                                run every step on data generated from <seed> (the same
                                                for every run of the job), print a report; last line is
                                                CHECK_JSON {...}; exit 0 only if all pass
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


PROBE = {
    # Product-native look at the stored data, run with the product's own client at the job's version.
    "chroma": ("uv run --quiet --no-project --with chromadb=={version} python -", r"""
import chromadb, json, sys
from pathlib import Path
dirs = sorted({p.parent for p in Path("/work/data").rglob("chroma.sqlite3")})
rows, ids, cats = 0, set(), {}
for d in dirs:
    c = chromadb.PersistentClient(path=str(d))
    for col in c.list_collections():
        col = c.get_collection(col.name if hasattr(col, "name") else col)
        got = col.get(include=["metadatas"])
        rows += len(got["ids"]); ids |= set(got["ids"])
        for i, m in zip(got["ids"], got["metadatas"] or []):
            cats[i] = (m or {}).get("category")
print("PROBE_JSON " + json.dumps({"stores": [str(d) for d in dirs], "rows": rows, "ids": sorted(ids), "cats": cats}))
"""),
    "lancedb": ("uv run --quiet --no-project --with lancedb=={version} python -", r"""
import lancedb, json
from pathlib import Path
dirs = sorted({p.parent for p in Path("/work/data").rglob("*.lance") if p.is_dir()})
rows, ids, cats = 0, set(), {}
for d in dirs:
    db = lancedb.connect(str(d))
    names = db.table_names() if hasattr(db, "table_names") else list(db.list_tables())
    for n in names:
        t = db.open_table(n).to_arrow().to_pylist()
        rows += len(t)
        for r in t:
            i = r.get("id") or next((v for v in r.values() if isinstance(v, str) and v.startswith("doc-")), None)
            if i is not None:
                ids.add(i); cats[i] = r.get("category")
print("PROBE_JSON " + json.dumps({"stores": [str(d) for d in dirs], "rows": rows, "ids": sorted(ids), "cats": cats}))
"""),
    "pgvector": ("python3 -", r"""
import json, subprocess
from pathlib import Path
B = "/usr/lib/postgresql/17/bin/psql"
rows, ids, cats, stores = 0, set(), {}, []
for pid in Path("/work/data").rglob("postmaster.pid"):
    lines = pid.read_text().splitlines()
    port, sock = lines[3].strip(), (lines[4].strip() or "localhost")
    q = lambda db, sql: subprocess.run([B, "-h", sock, "-p", port, "-d", db, "-AtF", "\t", "-c", sql],
                                       capture_output=True, text=True, timeout=60).stdout.splitlines()
    for db in q("postgres", "select datname from pg_database where not datistemplate"):
        for t in q(db, "select format('%I.%I', table_schema, table_name) from information_schema.columns where udt_name='vector' group by 1"):
            stores.append(f"{db}:{t}")
            cols = q(db, f"select column_name from information_schema.columns where format('%I.%I', table_schema, table_name)='{t}'")
            idc = next((c for c in cols if c.lower() in ("id", "doc_id", "external_id")), None) or next(
                (c for c in cols if q(db, f"select count(*) from {t} where {c}::text like 'doc-%'") not in ([], ["0"])), None)
            catc = next((c for c in cols if c.lower() == "category"), None)
            if not idc:
                continue
            for line in q(db, f"select {idc}, {catc or 'null'} from {t}"):
                i, c = (line.split("\t") + [""])[:2]
                rows += 1; ids.add(i); cats[i] = c or None
print("PROBE_JSON " + json.dumps({"stores": stores, "rows": rows, "ids": sorted(ids), "cats": cats}))
"""),
}


class Check:
    def __init__(self, product, seed, version):
        self.product, self.version, self.steps, self.store = product, version, [], {}
        self.rng, self.deleted, self.updated, self.added = random.Random(seed), [], [], []

    def step(self, name, ok, detail):
        self.steps.append({"step": name, "passed": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)
        return ok

    def run(self, args):
        return sh(f"./docsearch {args}")

    def count(self):
        rc, out, err, _ = self.run("count")
        o = out.strip()
        return (int(o) if rc == 0 and o.isdigit() else None), f"count printed {o[:40]!r} (exit {rc})"

    def ask(self, q, k=5, cat=None, tag="q"):
        """Run one query; return (problems, ids). Strict: exactly min(k, eligible) distinct stored ids,
        nothing else on stdout, in the given category, in non-increasing true cosine order."""
        f = write_vec(f"{tag}-{self.rng.randrange(10**9)}.json", q)
        rc, out, err, _ = self.run(f"query {f} --k {k}" + (f" --category {cat}" if cat else ""))
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        eligible = [i for i, d in self.store.items() if cat is None or d["category"] == cat]
        probs = []
        if rc != 0:
            probs.append(f"exit {rc}: {err.strip()[-200:]}")
        if len(lines) != min(k, len(eligible)):
            probs.append(f"{len(lines)} lines for k={k}")
        if len(set(lines)) != len(lines):
            probs.append("duplicate ids")
        stray = [l for l in lines if l not in self.store]
        if stray:
            probs.append(f"not a stored id: {stray[:3]}")
        if cat and any(self.store[l]["category"] != cat for l in lines if l in self.store):
            probs.append("wrong category in results")
        sims = [cos(self.store[l]["vector"], q) for l in lines if l in self.store]
        if any(b > a + 1e-6 for a, b in zip(sims, sims[1:])):
            probs.append("not ordered by cosine similarity")
        return probs, [l for l in lines if l in self.store]

    def accurate(self, n=8, cat=None, k=5, label="q"):
        """Near-copies of stored vectors: >= 4 of the exact top-5 back, first hit in the exact top-2."""
        bad = []
        pool = [i for i, d in self.store.items() if cat is None or d["category"] == cat]
        for i in self.rng.sample(pool, min(n, len(pool))):
            q = near(self.rng, self.store[i]["vector"])
            probs, got = self.ask(q, k, cat, label)
            want, _ = exact(self.store, q, k, cat)
            if not probs and (len(set(got) & set(want)) < 0.8 * len(want) or not got or got[0] not in want[:2]):
                probs.append(f"got {got}, want {want}")
            if probs:
                bad.append(probs)
        return bad

    def targeted(self, n_upd=5, n_del=5, n_add=0):
        """Changed, deleted and newly added records answer exactly as they should."""
        bad = []
        for d in self.rng.sample(self.updated, min(n_upd, len(self.updated))):
            p1, g1 = self.ask(d["vector"], 3, None, "u")
            p2, g2 = self.ask(d["vector"], 3, d["category"], "uc")
            p3, g3 = self.ask(d["old_vector"], 10, d["old_category"], "uo")
            if p1 or p2 or p3 or not g1 or g1[0] != d["id"] or not g2 or g2[0] != d["id"] or d["id"] in g3:
                bad.append(f"updated {d['id']}: {g1[:1]} / new category {g2[:1]} / still in old category: {d['id'] in g3} {p1 + p2 + p3}")
        for i, v in self.rng.sample(self.deleted, min(n_del, len(self.deleted))):
            p, g = self.ask(v, 10, None, "d")
            if p or i in g:
                bad.append(f"deleted {i}: returned={i in g} {p}")
        for d in self.added[:n_add]:
            p, g = self.ask(d["vector"], 3, None, "a")
            if p or not g or g[0] != d["id"]:
                bad.append(f"added {d['id']}: got {g[:1]} {p}")
        return bad

    def health(self, label, n=8, n_add=0):
        c, cdesc = self.count()
        bad = self.accurate(n, label=label)
        cat = self.rng.choice(CATS)
        badc = self.accurate(3, cat=cat, label=label + "c")
        tb = self.targeted(n_add=n_add)
        ok = c == len(self.store) and not bad and not badc and not tb
        return ok, (f"{cdesc} (want {len(self.store)}); queries right {n - len(bad)}/{n}, "
                    f"with --category {cat} {3 - len(badc)}/3, targeted checks failing {len(tb)}"
                    + (f"; first problem: {(bad + badc)[0] if bad or badc else tb[0]}" if not ok and (bad or badc or tb) else ""))

    def native(self):
        cmd, script = PROBE[self.product]
        rc, out, err, _ = (lambda c: sh(c, 600))(f"{cmd.format(version=self.version)} <<'PROBE_EOF'\n{script}\nPROBE_EOF")
        res = next((json.loads(l[11:]) for l in out.splitlines() if l.startswith("PROBE_JSON ")), None)
        if not res:
            return False, f"couldn't read the store with {self.product}'s own client (exit {rc}): {err.strip()[-300:]}"
        live, ids = set(self.store), set(res["ids"])
        dele = {i for i, _ in self.deleted} & ids
        wrongcat = [i for i in live & ids if res["cats"].get(i) not in (None, self.store[i]["category"])]
        ok = res["rows"] == len(live) and ids == live and not wrongcat
        return ok, (f"{len(res['stores'])} store(s); {res['rows']} rows (want {len(live)}); ids match: {ids == live}; "
                    f"deleted ids still stored: {len(dele)}; wrong stored category: {len(wrongcat)}")

    def main(self):
        TMP.mkdir(parents=True, exist_ok=True)
        if not self.step("files present", all((WORK / f).exists() for f in ("docsearch", "start.sh", "stop.sh")),
                         "docsearch, start.sh, stop.sh"):
            return
        sh("bash ./stop.sh", 120)
        kill_others()
        if DATA.exists():  # the agent's own test data goes aside: start.sh must cope with an empty /work/data
            DATA.rename(TMP / f"agent-data-{int(time.time())}")
        rc, out, err, t = sh("bash ./start.sh", 300)
        if not self.step("cold start", rc == 0, f"start.sh on an empty /work/data exited {rc} in {t}s {err.strip()[-200:]}"):
            return
        docs = gen_docs(self.rng, N)
        rc, out, err, t = self.run(f"add {write_jsonl('docs.jsonl', docs)}")
        self.store = {d["id"]: d for d in docs}
        c, cdesc = self.count()
        self.step("add and count", rc == 0 and c == N, f"add {N} docs exited {rc} in {t}s; {cdesc}")
        bad = self.accurate(8, label="base")
        self.step("cosine top-5", not bad, f"{8 - len(bad)}/8 queries right" + (f"; first problem: {bad[0]}" if bad else ""))
        cat = self.rng.choice(CATS)
        bad = self.accurate(5, cat=cat, label="cat")
        self.step("category filter", not bad, f"--category {cat}: {5 - len(bad)}/5 right" + (f"; first problem: {bad[0]}" if bad else ""))
        new = []
        for i in self.rng.sample(sorted(self.store), 30):
            d = dict(self.store[i])
            d["old_vector"], d["old_category"] = d["vector"], d["category"]
            d["vector"] = [round(self.rng.gauss(0, 1) * 2, 6) for _ in range(DIM)]
            d["category"] = self.rng.choice([c for c in CATS if c != d["category"]])
            d["text"] = d["text"] + " (revised)"
            new.append(d)
        rc, out, err, t = self.run(f"add {write_jsonl('update.jsonl', [{k: v for k, v in d.items() if not k.startswith('old_')} for d in new])}")
        for d in new:
            self.store[d["id"]] = {k: v for k, v in d.items() if not k.startswith("old_")}
        self.updated = new
        c, cdesc = self.count()
        tb = self.targeted(n_upd=10, n_del=0)
        self.step("replace by id", rc == 0 and c == N and not tb,
                  f"re-adding 30 ids exited {rc}; {cdesc} (want {N}); targeted checks failing {len(tb)}/10" + (f"; first: {tb[0]}" if tb else ""))
        dels = self.rng.sample(sorted(self.store), 40)
        rc, out, err, t = self.run("delete " + " ".join(dels + ["doc-99998", "nope-1"]))
        self.deleted = [(i, self.store.pop(i)["vector"]) for i in dels]
        self.updated = [d for d in self.updated if d["id"] in self.store]
        c, cdesc = self.count()
        tb = self.targeted(n_upd=0, n_del=10)
        self.step("delete", rc == 0 and c == N - 40 and not tb,
                  f"deleting 40 ids + 2 unknown exited {rc} {err.strip()[-200:]}; {cdesc} (want {N - 40}); targeted checks failing {len(tb)}/10" + (f"; first: {tb[0]}" if tb else ""))
        ok0, d0 = self.health("pre")
        rc1, _, _, _ = sh("bash ./stop.sh", 120)
        n = kill_others()
        rc2, _, e2, t2 = sh("bash ./start.sh", 300)
        ok, d = self.health("restart")
        self.step("clean restart", ok0 and rc1 == 0 and rc2 == 0 and ok,
                  f"before: {d0}. stop.sh {rc1}, {n} leftover processes killed, start.sh {rc2} in {t2}s. after: {d}")
        n = kill_others()
        rc, _, err, t = sh("bash ./start.sh", 300)
        ok, d = self.health("kill", n=4)
        self.step("hard kill", rc == 0 and ok, f"killed {n} processes without stop.sh; start.sh {rc} in {t}s. after: {d}")
        self.added = gen_docs(self.rng, 10, start=N)
        rc, _, err, _ = self.run(f"add {write_jsonl('extra.jsonl', self.added)}")
        for d in self.added:
            self.store[d["id"]] = d
        ok, d = self.health("after-add", n=4, n_add=10)
        self.step("add after restart", rc == 0 and ok, f"add 10 exited {rc}. {d}")
        ok, d = self.native()
        self.step(f"{self.product} holds the data", ok, d)


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
    elif len(a) == 3 and a[0] in PROBE:
        c = Check(a[0], int(a[1]), a[2])
        try:
            c.main()
        except Exception as e:
            c.step("check crashed", False, repr(e))
        passed = bool(c.steps) and all(s["passed"] for s in c.steps)
        print("CHECK_JSON " + json.dumps({"product": a[0], "passed": passed, "steps": c.steps}))
        sys.exit(0 if passed else 1)
    else:
        sys.exit(__doc__)
