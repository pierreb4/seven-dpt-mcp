"""INCIDENT A (2026-08-31, seven-dpt-mcp) — the founding incident, RECONSTRUCTED.

The amendment-prior legality gate's first cut keyed its scope to `ts >= "2026-09-01"`,
using the one field dialect-3 declares unreliable as the authority for a legality gate.
The anchor date was itself one of five +1-day typos, so the gate was calibrated on the
exact error class it existed to police. Caught in-session by Pierre reading the clock and
fixed before commit, so there is no artifact in git history — this file reproduces the
gate VERBATIM as the fix comment in ledger_invariants.py records it.

MUST FLAG: hand-stamped-ts.
"""
def check(lines, out, alerts):
    prior_seen, flat_amend = {}, []
    for n, l in enumerate(lines):
        i, pr = l.get("id"), l.get("prior")
        if not i: continue
        if pr is None:
            prior_seen.setdefault(i, None); continue
        is_amend = bool(l.get("amends")) or l.get("kind") == "amendment"
        if (is_amend and prior_seen.get(i) is not None and pr == prior_seen[i]
                and str(l.get("ts") or "") >= "2026-09-01"):
            flat_amend.append({"id": i, "prior": pr, "line": n + 1})
        prior_seen[i] = pr
    return flat_amend
