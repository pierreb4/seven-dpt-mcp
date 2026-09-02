"""PRIOR-UPDATE CENSUS (spark #50). Read-only over the ledger.

Counts, per arm id, the priced entries in FILE ORDER (dialect-3: file order is the clock
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

Usage:  prior_update_census.py
"""
import sys, json, os
sys.path.insert(0, os.path.expanduser("~/projects/seven-dpt-mcp/analysis"))
import ledger_invariants as li

lines = [json.loads(x) for x in open(li.LEDGER) if x.strip()]
arms = {}
for i, l in enumerate(lines):
    pid = l.get("id")
    if not pid: continue
    a = arms.setdefault(pid, {"priced": [], "verdicts": []})
    p = li.prior_of(l)
    if p is not None:
        a["priced"].append((i, float(p), l.get("kind"), l.get("amends")))
    v = li.verdict_of(l)
    if v: a["verdicts"].append((i, v))

SCOREABLE = ("cleared", "failed")
rows = []
for pid, a in arms.items():
    vals = [p for _, p, _, _ in a["priced"]]
    if len(vals) < 2: continue
    distinct = sorted(set(vals))
    term = a["verdicts"][-1][1] if a["verdicts"] else None
    rows.append((pid, vals, len(distinct), term))

rows.sort(key=lambda r: (-r[2], r[0]))
mu = [r for r in rows if r[2] >= 2]
qual = [r for r in mu if r[3] in SCOREABLE]
term_any = [r for r in mu if r[3]]

print(f"ledger lines: {len(lines)}   arms with >=2 PRICED entries: {len(rows)}")
print(f"arms with >=2 DISTINCT priced values: {len(mu)}")
print(f"  ... of those, terminal (any verdict):     {len(term_any)}")
print(f"  ... of those, terminal AND SCOREABLE:     {len(qual)}   <-- bar is >=6")
print()
print("MULTI-UPDATE ARMS (>=2 distinct values):")
for pid, vals, nd, term in mu:
    print(f"  {pid:38s} {str(vals):32s} distinct={nd} terminal={term}")
print()
print("RESTATERS (>=2 priced entries, 1 distinct value) -- carry no update signal:")
for pid, vals, nd, term in rows:
    if nd < 2:
        print(f"  {pid:38s} {str(vals):32s} terminal={term}")
