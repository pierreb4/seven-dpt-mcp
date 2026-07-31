#!/usr/bin/env python3
"""Standing invariants over a decision ledger — the deterministic layer of a project audit.

Born 2026-07-31 from the arc-agi-3 illusory-progress postmortem: fourteen pre-registered
probes each resolved honestly ("straddles zero, park") while the PROGRAM was blind — the
minimum detectable effect (+/-0.179) exceeded every effect chased (-0.14..+0.02), so every
verdict was decided by the experimental design before it ran. Each probe audited itself;
nothing audited the program. These checks look across the record, where that failure lives.

Reads the same two-line JSONL ledger as calibration.py (pre-registration lines carrying
`prior`, resolution lines carrying `outcome`) and checks three program-level invariants:

  PARK-STREAK   K consecutive terminal verdicts whose notes read "inside the noise"
                (CI straddling zero, under the bar, indistinguishable). A long streak means
                the instrument, not the ideas, is the binding constraint. ALERT at >= STREAK_K.
  POWER         a pre-registration whose gate (explicit `gate` field, else the smallest
                effect magnitude parsed near the unit in `criterion`) is below the banked
                MDE is unresolvable BEFORE it runs. ALERT for in-flight probes; historical
                ones are tallied retrodictively. Needs a noise model; skipped without one.
  CHANNEL STAMP a lever should name the channel it acts through and that channel's measured
                liveness (`channel` [+ `liveness`] fields on the prereg line) — the
                discipline that prevents optimizing a channel that is 0% of the live path.
                Coverage is reported; missing stamps WARN (ALERT with CHANNEL_STRICT=1).

Note classification is heuristic BY DESIGN and the script reports its own coverage: an
invariant running blind (many unclassified notes) says so instead of staying silent.
Protocol suggestion it will nag about: put machine-readable `gate` (+`unit`) and `channel`
fields on future prereg lines; both are backward-compatible extra JSON keys.

Alerts exit(1) and are marked "ALERT" in the --json output (default under the XDG data
dir, NOT repo content) so a hook or wakeCondition (fileMatches pattern ALERT) can gate on
them. --asof YYYY-MM-DD replays only lines with ts <= that date: retrodiction — check when
a rule WOULD have fired. (Classifier patterns were developed on the arc ledger's own note
style, so retrodiction on that ledger is in-sample; out-of-sample validity accrues as new
notes arrive.)

Retrodiction on the arc ledger (run 2026-07-31, NOISE_MDE=0.179 NOISE_UNIT=/game): POWER marks
13/32 resolved gates as predetermined and ALERTs on the in-flight lever probe by --asof
2026-07-26 — five days before the human postmortem said the same. PARK-STREAK never reached
K=6 there: decisive refutations correctly broke the runs, so POWER is the tripwire that fires
first. Precondition honesty: POWER needs a maintained noise model, and computing one is
exactly the discipline whose absence it exists to catch — the invariant's real function is
forcing that number to exist from the first pooled draws onward.

Env: ARC_PRIOR_LEDGER (path) · STREAK_K (default 6) · NOISE_MDE + NOISE_UNIT, or
     NOISE_JSON (path to {"mde":..,"unit":..} or a list of those) · INVARIANTS_JSON (out)
     · CHANNEL_STRICT=1
Usage: ledger_invariants.py [--json] [--asof YYYY-MM-DD]
"""
import json, os, re, sys

LEDGER = os.path.expanduser(os.environ.get("ARC_PRIOR_LEDGER",
         "~/projects/arc-agi-3/launch/prior-ledger.jsonl"))
OUTJSON = os.environ.get("INVARIANTS_JSON") or os.path.join(
          os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
          "seven-dpt", "invariants.json")
STREAK_K = int(os.environ.get("STREAK_K", 6))
TERMINAL = ("cleared", "failed")

def load_noise():
    p = os.environ.get("NOISE_JSON")
    if p and os.path.exists(os.path.expanduser(p)):
        d = json.load(open(os.path.expanduser(p)))
        return d if isinstance(d, list) else [d]
    if os.environ.get("NOISE_MDE"):
        return [{"mde": float(os.environ["NOISE_MDE"]), "unit": os.environ.get("NOISE_UNIT", "")}]
    return []

# ── note classifier (heuristic; coverage is reported) ────────────────────────
DECISIVE = re.compile(r"refut|clear(ed|s)? the gate|beat the bar|decisive|wrong direction|"
                      r"direction is wrong|exceed(ed|s) the (bar|gate)", re.I)
INSIDE = re.compile(r"straddl|inside the noise|within (the )?noise|under (the )?(merits |priced )?bar|"
                    r"below (the )?(mde|bar|detection)|indistinguishab|\bpark(ed|s)?\b|"
                    r"no (demonstrable|detectable) (effect|improvement|gain)|"
                    r"consistent with (zero|no effect|the null)", re.I)
CI = re.compile(r"\[\s*(-?\d+(?:\.\d+)?)\s*,\s*\+?(-?\d+(?:\.\d+)?)\s*\]")

def classify(outcome, note):
    t = (note or "").replace("−", "-").replace("–", "-")
    if DECISIVE.search(t): return "decisive"          # a refutation is information — breaks a streak
    m = CI.search(t)
    if m and float(m.group(1)) <= 0 <= float(m.group(2)): return "inside_noise"
    if INSIDE.search(t): return "inside_noise"
    if outcome == "cleared": return "decisive"        # a cleared gate resolved something
    return "unclassified"

# ── pairing (same bucket semantics as calibration.py) ────────────────────────
def pair(lines):
    by, order = {}, []
    for l in lines:
        i = l.get("id")
        if i is None: continue
        if i not in by: by[i] = []; order.append(i)
        by[i].append(l)
    resolved, inflight = [], []
    for i in order:
        ls = by[i]
        priors = [l for l in ls if "prior" in l]
        outs = [l for l in ls if "outcome" in l]
        terms = [l for l in outs if l.get("outcome") in TERMINAL]
        if terms:
            resolved.append({"id": i, "pre": priors[0] if priors else {}, "res": terms[-1]})
        elif any(l.get("outcome") in ("void", "amended-before-running") for l in outs):
            continue                                   # no information / superseded — out of every invariant
        elif priors:
            inflight.append({"id": i, "pre": priors[0]})
    return resolved, inflight

# ── gate extraction for the power check ──────────────────────────────────────
NUM = re.compile(r"(-?\d+(?:\.\d+)?)")
def gate_of(pre, noise):
    if isinstance(pre.get("gate"), (int, float)):
        u = pre.get("unit") or (noise[0]["unit"] if noise else "")
        return abs(float(pre["gate"])), u, "explicit"
    crit = (pre.get("criterion") or "").replace("−", "-")
    for nz in noise:
        u = nz.get("unit") or ""
        if not u or u not in crit: continue
        best = None
        for m in re.finditer(re.escape(u), crit):
            window = crit[max(0, m.start() - 40):m.end() + 25]
            for g in NUM.finditer(window):
                v = abs(float(g.group(1)))
                if 0 < v < 100 and (best is None or v < best): best = v
        if best is not None: return best, u, "parsed"
    return None, None, "unparsed"

def noise_for(unit, noise):
    for nz in noise:
        if (nz.get("unit") or "") and unit and nz["unit"] in unit or unit in (nz.get("unit") or ""):
            return nz
    return noise[0] if noise else None

def on_class(pre, noise):
    """A probe is on-class for the streak when its gate speaks the program's primary
    metric (the noise unit appears in its criterion). Validity gates, ship checks and
    infra probes are real work but must not dilute or break an instrument-limited streak."""
    crit = pre.get("criterion") or ""
    return any((nz.get("unit") or "") in crit for nz in noise if nz.get("unit"))

def main():
    argv = sys.argv[1:]
    asof = argv[argv.index("--asof") + 1] if "--asof" in argv else None
    if not os.path.exists(LEDGER):
        print(f"no ledger at {LEDGER} — set ARC_PRIOR_LEDGER"); return 0
    lines = []
    for raw in open(LEDGER):
        raw = raw.strip()
        if not raw: continue
        try: l = json.loads(raw)
        except ValueError: continue
        if asof and (l.get("ts") or "") > asof: continue
        lines.append(l)
    resolved, inflight = pair(lines)
    noise = load_noise()
    alerts, out = [], {"asof": asof, "n_resolved": len(resolved), "n_inflight": len(inflight)}
    print(f"ledger: {LEDGER}" + (f"  (as of {asof})" if asof else ""))
    print(f"resolved {len(resolved)} · in-flight {len(inflight)}\n")
    if not resolved and not inflight:
        print("nothing to check."); return 0

    # ── PARK-STREAK ──
    pool = [r for r in resolved if on_class(r["pre"], noise)] if noise else resolved
    off_class = len(resolved) - len(pool)
    seq = [(r["id"], classify(r["res"].get("outcome"), r["res"].get("note")), r["res"].get("ts", "")) for r in pool]
    unclassified = [i for i, c, _ in seq if c == "unclassified"]
    classified = [(i, c, t) for i, c, t in seq if c != "unclassified"]
    cur, cur_ids = 0, []
    for i, c, t in reversed(classified):
        if c != "inside_noise": break
        cur += 1; cur_ids.append(i)
    longest, run = 0, 0
    for i, c, t in classified:
        run = run + 1 if c == "inside_noise" else 0
        longest = max(longest, run)
    cov = len(classified) / len(seq) if seq else 1.0
    strip = "".join({"inside_noise": "N", "decisive": "D", "unclassified": "?"}[c] for _, c, _ in seq)
    print(f"PARK-STREAK  (K={STREAK_K})  timeline: {strip}"
          + (f"   [{len(pool)} on-class probes; {off_class} off-class excluded]" if noise else ""))
    print(f"  current {cur} · longest {longest} · note-classification coverage {cov:.0%}"
          + (f" · unclassified: {', '.join(unclassified[:6])}{'…' if len(unclassified) > 6 else ''}" if unclassified else ""))
    if cov < 0.7 and seq: print("  WARN: invariant is running part-blind — >30% of notes unclassifiable; tighten note style or patterns")
    if cur >= STREAK_K:
        alerts.append(f"ALERT park-streak: {cur} consecutive inside-noise verdicts (latest: {', '.join(cur_ids[:4])}) — audit the instrument, not the next lever")
    out["streak"] = {"current": cur, "longest": longest, "coverage": round(cov, 2), "timeline": strip}

    # ── POWER AT PRE-REGISTRATION ──
    print(f"\nPOWER  (noise model: {noise if noise else 'NONE — set NOISE_MDE/NOISE_UNIT or NOISE_JSON; check skipped'})")
    if noise:
        weak_hist, unparsed = [], []
        for bucket, rows in (("in-flight", inflight), ("resolved", resolved)):
            for r in rows:
                g, u, how = gate_of(r["pre"], noise)
                if g is None:
                    unparsed.append(r["id"]); continue
                nz = noise_for(u, noise)
                if not nz or g >= nz["mde"]: continue
                mult = (nz["mde"] / g) ** 2 if g else float("inf")
                if bucket == "in-flight":
                    alerts.append(f"ALERT power: in-flight '{r['id']}' gate {g} {u} < MDE {nz['mde']} ({how}) — unresolvable as designed; needs ~{mult:.1f}x the sample or a bigger lever")
                else:
                    weak_hist.append((r["id"], g, nz["mde"]))
        print(f"  historical: {len(weak_hist)}/{len(resolved)} resolved preregs had gates below the MDE — those verdicts were predetermined"
              + (f" ({', '.join(i for i, _, _ in weak_hist[:5])}{'…' if len(weak_hist) > 5 else ''})" if weak_hist else ""))
        if unparsed:
            print(f"  unparsed gates ({len(unparsed)}): {', '.join(unparsed[:6])}{'…' if len(unparsed) > 6 else ''} — add explicit `gate`+`unit` fields to prereg lines")
        out["power"] = {"historical_weak": len(weak_hist), "unparsed": len(unparsed)}

    # ── CHANNEL STAMP ──
    allpre = inflight + resolved
    stamped = [r for r in allpre if r["pre"].get("channel")]
    missing = [r["id"] for r in allpre if not r["pre"].get("channel")]
    print(f"\nCHANNEL STAMP  {len(stamped)}/{len(allpre)} preregs name their channel"
          + (f" · missing (recent): {', '.join(missing[-6:])}" if missing else ""))
    if missing and os.environ.get("CHANNEL_STRICT"):
        alerts.append(f"ALERT channel: {len(missing)} preregs carry no channel stamp under CHANNEL_STRICT")
    elif missing:
        print("  WARN: unstamped levers can optimize a dead channel undetected — add `channel` (+`liveness`) at registration")
    out["channel"] = {"stamped": len(stamped), "total": len(allpre)}

    out["alerts"] = alerts
    print()
    for a in alerts: print(a)
    if not alerts: print("no alerts.")
    if "--json" in argv:
        os.makedirs(os.path.dirname(OUTJSON), exist_ok=True)
        json.dump(out, open(OUTJSON, "w"), indent=1)
        print(f"json -> {OUTJSON}")
    return 1 if alerts else 0

if __name__ == "__main__":
    sys.exit(main())
