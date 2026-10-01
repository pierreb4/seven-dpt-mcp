"""PRIOR-UPDATE CENSUS (spark #50). Read-only over the ledger.

Counts, per arm, the priced entries in FILE ORDER (dialect-3: file order is the clock
on unmarked lines), how many DISTINCT prior values they hold, and whether the terminal is
SCOREABLE. Three bars, deliberately reported separately because each is a weaker proxy
for the next:

  >=2 priced entries   -- what a naive count sees. 08-31 read 12 here and called it 12-of-6.
  >=2 DISTINCT values  -- a restated prior carries no belief-revision signal.
  ... AND cleared/failed -- the face is a Brier of first vs last price, and a `gray`
                          terminal (kind-dialect-semantics-13) has no y to grade against.

Prices are read through ledger_invariants.prior_of(), NOT a hand-rolled `prior` lookup:
the 08-31 census read that one key, missed `p_clears` and `prior_p_scores`, and mis-shelved
a real multi-update arm as a restater. Banked as a script rather than a session because a
banked criterion plus mechanical counting is something any session should be able to finish.

2026-10-01, the spark's own wake note made mechanical (the 09-15 read used a throwaway):
  - arms keyed on amends||id, so an amendment row lands on the arm it amends;
  - a priced entry is a NON-resolution row (kind/event != resolution) with a numeric prior;
  - RESET RULE, declared before the 923-line read: a row that closes the arm WITHOUT a run
    (event_class void, or an outcome/resolution word of class void / withdrawn / declined,
    and no verdict on the same row) wipes the prices registered before it. Those forecasts
    never stood against an outcome and the ledger itself does not score them, so the face
    must not either. flashnext-expel-a-1 (0.2, VOID withdrawn-unrun, re-registered 0.15,
    failed) is therefore ONE price, not an amendment. The no-reset count prints as a
    sensitivity line only; the bar reads the reset count.
  - a growth table re-runs the census on ledger prefixes, so the re-park atom comes from the
    scoreable-arm rate on this one instrument, not from ledger rows.

Usage:  prior_update_census.py
"""
import sys, json, os
sys.path.insert(0, os.path.expanduser("~/projects/seven-dpt-mcp/analysis"))
import ledger_invariants as li

SCOREABLE = ("cleared", "failed")
NO_RUN_CLOSE = ("void", "withdrawn", "declined")


def closes_without_run(l):
    if li.verdict_of(l): return False
    if li.event_class(l) == "void": return True
    return any(w and li.outcome_class(str(w)) in NO_RUN_CLOSE for w in (l.get("outcome"), l.get("resolution")))


def census(lines, reset=True):
    arms, unparsed = {}, 0
    for i, l in enumerate(lines):
        pid = l.get("amends") or l.get("id")
        if not pid: continue
        a = arms.setdefault(pid, {"priced": [], "verdicts": [], "wiped": []})
        if reset and closes_without_run(l):
            a["wiped"] += a["priced"]
            a["priced"], a["verdicts"] = [], []
            continue
        p = li.prior_of(l)
        if p is not None and "resolution" not in (l.get("kind"), l.get("event")):
            try:
                a["priced"].append((i, float(p)))
            except (TypeError, ValueError):
                unparsed += 1
        v = li.verdict_of(l)
        if v: a["verdicts"].append((i, v))
    rows = []
    for pid, a in arms.items():
        vals = [p for _, p in a["priced"]]
        if len(vals) < 2: continue
        term = a["verdicts"][-1][1] if a["verdicts"] else None
        rows.append((pid, vals, len(set(vals)), term, [i + 1 for i, _ in a["priced"]], len(a["wiped"])))
    rows.sort(key=lambda r: (-r[2], r[0]))
    return rows, unparsed


def scoreable(rows):
    return [r for r in rows if r[2] >= 2 and r[3] in SCOREABLE]


lines = [json.loads(x) for x in open(li.LEDGER) if x.strip()]
rows, unparsed = census(lines)
mu = [r for r in rows if r[2] >= 2]
qual = scoreable(rows)
term_any = [r for r in mu if r[3]]

print(f"ledger lines: {len(lines)}   arms with >=2 PRICED entries: {len(rows)}   (non-numeric priors skipped: {unparsed})")
print(f"arms with >=2 DISTINCT priced values: {len(mu)}")
print(f"  ... of those, terminal (any verdict):     {len(term_any)}")
print(f"  ... of those, terminal AND SCOREABLE:     {len(qual)}   <-- bar is >=6")
print(f"  sensitivity, NOT the verdict -- no reset rule: {len(scoreable(census(lines, reset=False)[0]))} scoreable")
print()
print("GROWTH (scoreable arms on ledger prefixes, reset rule):")
marks = [n for n in (704, 800, 904) if n < len(lines)] + [len(lines)]
counts = [(n, len(scoreable(census(lines[:n])[0]))) for n in marks]
print("  " + "   ".join(f"{n} lines: {c}" for n, c in counts))
(n0, c0), (n1, c1) = counts[0], counts[-1]
print(f"  rate since {n0}: {c1 - c0} per {n1 - n0} lines")
print()
print("MULTI-UPDATE ARMS (>=2 distinct values; lines are 1-based ledger lines):")
for pid, vals, nd, term, at, wiped in mu:
    print(f"  {pid:38s} {str(vals):26s} distinct={nd} terminal={term} lines={at}" + (f" wiped={wiped}" if wiped else ""))
print()
print("RESTATERS (>=2 priced entries, 1 distinct value) -- carry no update signal:")
for pid, vals, nd, term, at, wiped in rows:
    if nd < 2:
        print(f"  {pid:38s} {str(vals):26s} terminal={term}")
