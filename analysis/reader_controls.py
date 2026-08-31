#!/usr/bin/env python3
"""reader_controls.py — can each reader still DISSENT?

WHY THIS EXISTS
Every expensive defect in this layer has had the same shape: a reader keyed on ONE phrasing
or ONE field, every other phrasing became invisible to it, and the empty match set was
printed as a fact about the world instead of a failure to understand. Six bites in three
weeks (alert-honesty regex pinned green; unknown event head vetoing a line's own verdict
word; a non-unique lookup key; a flat `;` split dropping an instrument stamp; CONTINUE
REASON heard only from `note`; acknowledgement by bare substring).

The project's answer each time was a positive control written at the point of the fix: plant
a synthetic specimen, confirm the reader can see it. That discipline works — and it was
being applied ONE ALERT AT A TIME, at the moment of writing, by the person least able to
imagine the phrasing they had just failed to imagine. Run as a SUITE over every reader at
once (2026-08-31) it found three holes in a single pass, two of them live.

So this is the discipline made standing rather than occasional. It is the mutation-testing
move: a check that cannot fail is not a passing check, and the only way to know a reader can
say "no" is to hand it something it should say "no" to.

DESIGN
Controls run the REAL sweep path — a temp ledger (the live composite + planted lines) through
ledger_invariants.py as a subprocess, exactly as sweep_composite.sh runs it. Nothing is
imported from the parsers: a control that calls the helper it is testing inherits the helper's
bug and returns a confident green, which is the failure mode this file exists to prevent.

EXPECTED-FAIL IS A FIRST-CLASS RESULT. Two controls are known blind spots with a stated
reason, and they are marked xfail rather than left red. A suite that is permanently red gets
ignored — this project has already recorded that an alert whose remedy the reader cannot
perform is decorative, and the only stable response is to stop reading it. An xfail that
starts PASSING is reported as loudly as a pass that starts failing: both mean the dialect
moved under a documented assumption.

Run:  python3 analysis/reader_controls.py [--verbose]
Env:  LEDGER_A / LEDGER_B (same defaults as sweep_composite.sh)
Exit: 0 = every reader behaved as declared · 2 = a reader lost (or gained) the ability to dissent
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.expanduser(os.environ.get("LEDGER_A", "~/projects/arc-agi-3/launch/prior-ledger.jsonl"))
B = os.path.expanduser(os.environ.get("LEDGER_B", "~/projects/launch/prior-ledger.jsonl"))
VERBOSE = "--verbose" in sys.argv

# ── the planted specimens ────────────────────────────────────────────────────
# Each control: what is planted, and what the faces MUST say about it. `expect` is the
# declared outcome — "pass" (the reader dissents) or "xfail" (a known blind spot, with the
# reason it is accepted rather than fixed). `probe(text, inv)` returns True iff the reader
# dissented; it is deliberately written against the OUTPUT, never the parser internals.
CONTROLS = [
    dict(
        name="fresh unpriced draw ALERTs",
        why="Baseline liveness of the unpriced-draw channel. If this cannot fire, every "
            "control below that depends on it is measuring nothing.",
        expect="pass",
        plant=[{"ts": "2026-08-31T10:00:00Z", "id": "PC-fresh-draw", "kind": "hidden-draw",
                "note": "synthetic control: measurement draw, band 1.0-2.0, no prior"}],
        probe=lambda t, inv: "PC-fresh-draw" in inv.get("unpriced_measurement_draws", [])
                             and any("PC-fresh-draw" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="exactly-named draw STANDS DOWN",
        why="The negative direction of the same channel — proof the acknowledgement path "
            "still works after the lexer was tightened. Without this, 'no false "
            "acknowledgements' could be bought by breaking acknowledgement entirely.",
        expect="pass",
        plant=[{"ts": "2026-08-31T10:01:00Z", "id": "PC-acked-draw", "kind": "hidden-draw",
                "note": "synthetic control: unpriced draw"},
               {"ts": "2026-08-31T10:02:00Z", "id": "kind-dialect-semantics-PC1",
                "kind": "scoring-note",
                "note": "Acknowledging PC-acked-draw as a known unscoreable specimen."}],
        probe=lambda t, inv: not any("PC-acked-draw" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="PREFIX-COLLIDING id is NOT acknowledged",
        why="The rewarded misuse of every acknowledgement rule: the next specimen hiding "
            "behind the standing line. Before the 2026-08-31 lexer fix this control FAILED "
            "— `id in ' '.join(notes)` absorbed a fresh specimen because a note named a "
            "LONGER id containing it, and the ALERT silently became a STANDING line.",
        expect="pass",
        plant=[{"ts": "2026-08-31T10:03:00Z", "id": "PC-collide", "kind": "hidden-draw",
                "note": "synthetic control: unpriced draw, never acknowledged"},
               {"ts": "2026-08-31T10:04:00Z", "id": "kind-dialect-semantics-PC2",
                "kind": "scoring-note",
                "note": "Acknowledging PC-collide-EXTENDED as a known unscoreable specimen."}],
        probe=lambda t, inv: any("PC-collide" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="undeclared kind token ALERTs",
        why="The closed-vocabulary tripwire — the one remedy in this layer that has held "
            "since it was built. Controlled so it stays held.",
        expect="pass",
        plant=[{"ts": "2026-08-31T10:05:00Z", "id": "PC-weird-kind",
                "kind": "synthetic-undeclared-kind", "note": "synthetic control"}],
        probe=lambda t, inv: "synthetic-undeclared-kind" in t,
    ),
    dict(
        name="`confirmed` on a PRICED entry ALERTs",
        why="dialect-4's legality condition is what made the word absorbable: `confirmed` on "
            "a priced arm reads as a pass while scoring nothing. A declared rule nothing "
            "executes decays into prose.",
        expect="pass",
        plant=[{"ts": "2026-08-31T10:06:00Z", "id": "PC-priced-confirmed", "kind": "ab",
                "prior": 0.5, "why": "synthetic control"},
               {"ts": "2026-08-31T10:07:00Z", "id": "PC-priced-confirmed", "kind": "resolution",
                "result": "confirmed", "note": "synthetic control: illegal on a priced entry"}],
        probe=lambda t, inv: any("PC-priced-confirmed" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="dead extractor rule ALERTs",
        why="Positive control for the RULE LIVENESS face itself: a rule that matches nothing "
            "cannot fail, so its green is vacuous. Planted by asking the face to judge a "
            "corpus with no instrument stamps at all — the `instrument stamp` extractor then "
            "matches 0 lines and must say so.",
        expect="pass",
        strip=lambda l: {k: v for k, v in l.items() if k != "instrument"},
        plant=[],
        probe=lambda t, inv: any(r["rule"] == "instrument stamp" and r["dead"]
                                 for r in inv.get("rule_liveness") or [])
                             and any("dead-rule" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="walk-away declared ONLY in `note`",
        why="KNOWN BLIND SPOT, accepted. `stage3-eval-r3` (2026-08-19) states 'WITHDRAWN AT "
            "ROUND 11, never registered' in `note` alone; its disposition is None and the "
            "unpriced-walk-away face reports 4 where the truth is 5 (verified: moving that "
            "same fact onto a declared carrier takes the count to 5). NOT fixed by adding "
            "`note` as a carrier — `criterion` and `void_conditions` carry CONDITIONAL heads "
            "('CLEARED iff the draw lands in [1.33, 1.95]'), so widening the carrier set "
            "buys false verdicts to cure a missed one. The fix belongs on arc's side: state "
            "a disposition on a declared carrier. Tracked here so the gap has a number.",
        expect="xfail",
        plant=[{"ts": "2026-08-31T10:08:00Z", "id": "PC-note-only-walkaway", "kind": "eval",
                "note": "WITHDRAWN at the adversary round, never registered, zero GPU spent."}],
        probe=lambda t, inv: any("PC-note-only-walkaway" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="terminal head on a bare `status`",
        why="KNOWN BLIND SPOT, accepted. STATUS_HEADS maps only WITHDRAWN, so "
            "`status: 'DEAD at the gate, never registered'` (real: `memseed-draw1`) is read "
            "by nothing — while `DEAD` IS a verdict word to verdict_of. The same word means "
            "different things to different readers of this layer. Deliberately narrow: the "
            "bare-status population is mostly prose and state (OPEN, PRE-RUN, STAGED), and "
            "alerting on prose is what makes a tripwire get ignored. Tracked, not widened.",
        expect="xfail",
        plant=[{"ts": "2026-08-31T10:09:00Z", "id": "PC-bare-dead", "kind": "adversary-block",
                "status": "DEAD at the gate, never registered", "why": "synthetic control"}],
        probe=lambda t, inv: any("PC-bare-dead" in a for a in inv.get("alerts") or []),
    ),
]


def base_lines():
    seen, out = set(), []
    for p in (A, B):
        if not os.path.exists(p):
            print(f"  SKIP  ledger not found: {p}"); return None
        for raw in open(p):
            if raw in seen: continue
            seen.add(raw)
            try: out.append(json.loads(raw))
            except ValueError: pass
    return out


def run(lines, tmp):
    led, outj = os.path.join(tmp, "l.jsonl"), os.path.join(tmp, "i.json")
    with open(led, "w") as f:
        for l in lines: f.write(json.dumps(l) + "\n")
    env = dict(os.environ, ARC_PRIOR_LEDGER=led, INVARIANTS_JSON=outj, STORE_STRICT="1")
    r = subprocess.run([sys.executable, os.path.join(HERE, "ledger_invariants.py"), "--json"],
                       capture_output=True, text=True, env=env)
    inv = json.load(open(outj)) if os.path.exists(outj) else {}
    return r.stdout + r.stderr, inv


def main():
    print("READER CONTROLS  can each reader still dissent?")
    base = base_lines()
    if base is None: return 0
    bad = []
    for c in CONTROLS:
        lines = [c["strip"](l) for l in base] if c.get("strip") else list(base)
        lines += c["plant"]
        with tempfile.TemporaryDirectory() as tmp:
            try:
                text, inv = run(lines, tmp)
                dissented = bool(c["probe"](text, inv))
            except Exception as e:                       # a control that crashes is a control
                text, inv, dissented = f"{type(e).__name__}: {e}", {}, False
        want = c["expect"] == "pass"
        ok = dissented == want
        tag = ("ok  " if ok else "FAIL") if want else ("xfail" if not dissented else "XPASS")
        print(f"  {tag:5s} {c['name']}")
        if not ok:
            bad.append((c, dissented))
            print(f"        expected {'dissent' if want else 'the known blind spot'},"
                  f" got {'dissent' if dissented else 'silence'}")
            print(f"        {c['why']}")
        elif VERBOSE:
            print(f"        {c['why']}")

    n_x = sum(1 for c in CONTROLS if c["expect"] == "xfail")
    print(f"\n  {len(CONTROLS) - len(bad)}/{len(CONTROLS)} as declared"
          f"  ({n_x} tracked blind spot(s) — see --verbose)")
    if bad:
        print("  A reader stopped behaving as declared. Either it lost the ability to see a")
        print("  specimen it used to see (silence where dissent was declared — the pinned-green")
        print("  shape), or a documented blind spot closed and the note that describes it is now")
        print("  wrong. Both mean the dialect moved: fix the reader or restate the control.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
