"""INCIDENT C, AS FIXED — the primary read is the STRUCTURED `alert_claims` channel the
alert builder writes at the point it asserts; the prose scan survives only as a fallback
whose provenance is printed unconditionally. MUST NOT FLAG.
"""
def alert_honesty(inv, inv_inflight, check):
    claimed = {c["id"] for c in (inv.get("alert_claims") or [])
               if c.get("claims") == "in-flight"}
    check("alerts: every id claimed in-flight IS in-flight", claimed <= inv_inflight,
          f"claimed but not in-flight: {sorted(claimed - inv_inflight)}")
