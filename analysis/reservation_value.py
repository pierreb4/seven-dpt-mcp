#!/usr/bin/env python3
"""Pandora's-Box / Gittins reservation-value index for seven-dpt #2 (background-problem budget).

Each open problem is a "box": cost_i = effort to chase one spark to a verdict, reward X_i = the
graded payoff (heavy-tailed: mostly ~0, rare windfalls). The reservation value z_i solves
    cost_i = E[max(X_i - z_i, 0)]
and you pursue problems in DESCENDING z, stopping the instant a result in hand beats every
remaining reservation. For independent projects advanced one-at-a-time under discounting, z_i
coincides with the GITTINS INDEX, so greedy-on-reservation is provably optimal — not a heuristic.

HONEST BY CONSTRUCTION: audits the spark->outcome history first and GATES on data sufficiency.
With too little history it prints INSUFFICIENT DATA + the exact gap and refuses to emit z (which
would be ~100% prior / 0% data). It flips to a real ranking automatically once enough resolved
sparks carry a cost AND a value. Progress is measured in resolved-outcome COUNT, not wall-clock.

Run:  python3 analysis/reservation_value.py
"""
import json, os, sys
from collections import defaultdict

STORE = os.environ.get("SEVEN_DPT_DB") or os.path.join(
    os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "seven-dpt", "store.json")
MIN_USABLE_PER_PROBLEM = 5  # resolved sparks WITH cost+value needed to estimate a reward dist

d = json.load(open(STORE))
problems = {p["id"]: p for p in d.get("problems", []) if p.get("status") == "open"}
byp = defaultdict(list)
for s in d.get("sparks", []):
    byp[s.get("problemId")].append(s)

def resolved(s):  # reached a terminal verdict
    return (s.get("status") or "").lower() in ("worked", "failed")

def usable(s):    # resolved AND carries both reward-channel numbers
    return resolved(s) and isinstance(s.get("cost"), (int, float)) and isinstance(s.get("value"), (int, float))

print("seven-dpt #2  reservation-value (Gittins/Pandora) index")
print("=" * 60)
usable_by_p, any_failure = {}, False
for pid in sorted(problems):
    sp = byp.get(pid, [])
    res = [s for s in sp if resolved(s)]
    use = [s for s in sp if usable(s)]
    usable_by_p[pid] = use
    if any((s.get("status") == "failed") or (s.get("value") == 0) for s in use):
        any_failure = True
    print(f"  #{pid} {problems[pid]['title'][:42]:42} sparks={len(sp):2d} resolved={len(res)} usable={len(use)}")
print("-" * 60)
total_usable = sum(len(v) for v in usable_by_p.values())
print(f"  usable (resolved with cost AND value): {total_usable}")

# ---- data-sufficiency gate ----
gaps = []
under = [pid for pid, v in usable_by_p.items() if len(v) < MIN_USABLE_PER_PROBLEM]
if under:
    gaps.append(f">={MIN_USABLE_PER_PROBLEM} usable (resolved + cost + value) sparks per problem; "
                f"under-filled: {under}.")
if total_usable and not any_failure:
    gaps.append("no FAILURES (status=failed or value=0) yet — 'most bets fail' is the premise, so "
                "the reward distribution's lower mass is unestimated; log the misses too.")

if gaps:
    print("\nVERDICT: INSUFFICIENT DATA — reservation values NOT estimable.")
    print("Emitting z_i now would be ~100% prior / 0% data (false precision). Refusing.\n")
    print("Restore the gradient — keep logging cost + value (incl. failures) on update_spark:")
    for g in gaps:
        print("  •", g)
    print("\nCold-start meanwhile: a fresh box's uninformative prior has a HIGH reservation value,")
    print("so 'no data' correctly says EXPLORE ~uniformly — the index earns its keep once data lands.")
    sys.exit(0)

# ---- real computation (reached once data is sufficient) ----
def reservation_value(rewards, cost):
    """Solve mean(max(x - z, 0)) = cost for z (monotone decreasing in z) by bisection."""
    xs = list(rewards)
    g = lambda z: sum(max(x - z, 0.0) for x in xs) / len(xs)
    lo, hi = min(xs) - 1.0, max(xs)
    if g(hi) >= cost:  # even at the top the expected excess covers the cost
        return hi
    if g(lo) <= cost:
        return lo
    for _ in range(64):
        mid = (lo + hi) / 2.0
        if g(mid) > cost:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0

print("\nsufficient data — reservation values (pursue in DESCENDING z):\n")
ranked = []
for pid, use in usable_by_p.items():
    rewards = [float(s["value"]) for s in use]
    cost_i = sum(float(s["cost"]) for s in use) / len(use)
    z = reservation_value(rewards, cost_i)
    ranked.append((z, pid, cost_i, sum(rewards) / len(rewards)))
ranked.sort(reverse=True)
for z, pid, cost_i, mean_r in ranked:
    print(f"  z={z:+7.2f}  #{pid} {problems[pid]['title'][:40]:40}  (cost~{cost_i:.2f}, mean reward~{mean_r:.2f})")
print("\nPursue the top z first; STOP the moment a result in hand beats every remaining z.")
