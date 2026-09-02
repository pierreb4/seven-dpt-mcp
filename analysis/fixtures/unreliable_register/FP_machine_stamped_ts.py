"""FALSE-POSITIVE CONTROL — a ts the PROGRAM writes, then reads back.

The register's whole claim rests on this frame. An entry that says "ts is unreliable"
without a discriminator is a ban on a field, and a register that flags a legitimate use
gets ignored — which is worse than not having one. The rule being tested is "avoid a
HAND-STAMPED ts", not "avoid ts", and the only thing that separates them is whether a
human or a clock produced the value. MUST NOT FLAG.

The live control is arc's scripts/budget.py, which has exactly this shape (it setdefaults
`ts` from the clock on every appended record, then compares those ts to project a horizon)
and scores clean out of tree. It is NOT vendored here: this repo has a public remote and
that file carries spend and account detail the 2026-08-30 memory audit flagged. The shape
is what the meta-test needs; the sibling file is the belt-and-braces run, and
`unreliable_register.py --selftest` picks it up automatically when it is present on disk.
"""
import datetime as dt
import json


def log(rec, path):
    # the stamp is MACHINE-generated at append time — dialect-12's marked era
    rec.setdefault("ts", dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


def read_log(path):
    return [json.loads(x) for x in open(path) if x.strip()]


def horizon(path, window_start):
    rows = read_log(path)
    # every comparison below keys on a ts this module wrote itself
    recent = [r for r in rows if r["ts"] >= window_start]
    if len(recent) < 2:
        return None
    first, last = recent[0], recent[-1]
    t0 = dt.datetime.strptime(first["ts"], "%Y-%m-%dT%H:%M:%SZ")
    t1 = dt.datetime.strptime(last["ts"], "%Y-%m-%dT%H:%M:%SZ")
    stale = (dt.datetime.utcnow() - t1).total_seconds() > 3600
    return {"span_h": (t1 - t0).total_seconds() / 3600, "stale": stale}
