"""INCIDENT C (self_check.py, pre-764723f) — the alert-honesty check, VERBATIM.

It recovered an alert's factual claim by regexing ONE phrasing, the 08-13 alert it was
written against. Every differently-worded alert was invisible to it, so `claimed` could
only ever be empty: the check returned a confident green for weeks while two alerts made
exactly the false claim it exists to catch. A check whose quantity is pinned by
construction is worse than absent — it points, and it points away.

MUST FLAG: prose (regex-over-prose).
"""
import re


def alert_honesty(inv, inv_inflight, check):
    claimed = set()
    for a in inv.get("alerts") or []:
        claimed |= set(re.findall(r"in-flight '([^']+)'", a))
    check("alerts: every id claimed in-flight IS in-flight", claimed <= inv_inflight,
          f"claimed but not in-flight: {sorted(claimed - inv_inflight)}")
