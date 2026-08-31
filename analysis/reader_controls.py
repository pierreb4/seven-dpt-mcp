#!/usr/bin/env python3
"""reader_controls.py — can each reader still DISSENT?

WHY THIS EXISTS
Every expensive defect in this layer has had the same shape: a reader keyed on ONE phrasing
or ONE field, every other phrasing became invisible to it, and the empty match set was
printed as a fact about the world instead of a failure to understand. Six bites in three
weeks (alert-honesty regex pinned green; unknown event head vetoing a line's own verdict
word; a non-unique lookup key; a flat `;` split dropping an instrument stamp; CONTINUE
REASON heard only from `note`; acknowledgement by bare substring) — and a SEVENTH the day
after this file was written, when arc restated a disposition on a declared carrier exactly
as asked and the count did not move, because a DIFFERENT reader (`event_class` -> 'ignore')
vetoed the line before its carrier was ever consulted. That one is why the suite now carries
regression controls on real lines, not only planted ones.

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

EXPECTED-FAIL IS A FIRST-CLASS RESULT. A known blind spot ships as an xfail carrying its
reason rather than as a red light or a silent gap. A suite that is permanently red gets
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
        name="acknowledgement on a NON-`note` field stands the specimen down",
        why="The 8th bite, on a reader that had just been fixed. `_ack_tokens` was corrected "
            "from SUBSTRING to TOKEN matching earlier the same day and left SINGLE-FIELD "
            "(`note`); arc then acknowledged searchsolver-probe on a field called "
            "`specimen_ack` and the alert kept firing — correct write, correct token "
            "discipline, wrong field. Two axes on one reader, fixed hours apart. This control "
            "pins the second axis so the next declaration field (arc has already used "
            "`dead_semantics`, `void_exclusion`, `specimen_ack`) does not reopen it.",
        expect="pass",
        plant=[{"ts": "2026-08-31T14:00:00Z", "id": "PC-ackfield-draw", "kind": "hidden-draw",
                "note": "synthetic control: unpriced draw"},
               {"ts": "2026-08-31T14:01:00Z", "id": "kind-dialect-semantics-PC3",
                "kind": "scoring-note", "note": "Unrelated prose that names no specimen.",
                "specimen_ack": "Acknowledging PC-ackfield-draw as a known unscoreable specimen."}],
        probe=lambda t, inv: not any("PC-ackfield-draw" in a for a in inv.get("alerts") or []),
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
        name="stage3-eval-r3 IS counted (dialect-7 restatement lands)",
        why="Regression control on a REAL line, not a planted one. Arc restated the "
            "disposition on `result` per dialect-7 — and the count still read 4, because "
            "`event: head-restatement` classes as 'ignore' and the unpriced face vetoed on "
            "ANY event class, discarding the carrier the restatement existed to supply. 6th "
            "bite of unknown-head-vetoes-the-carrier; the identical fix shipped for "
            "verdict_of in 0eeba5b and this face was never revisited. If this goes red the "
            "veto has crept back.",
        expect="pass",
        plant=[],
        probe=lambda t, inv: "stage3-eval-r3" in
                             ((inv.get("unpriced_walkaway") or {}).get("since_adoption") or []),
    ),
    dict(
        name="never-registered + FAILED head reads WALK-AWAY",
        why="Arc's requested both-ways test, direction 1 (dialect-7 dead_semantics). The "
            "discriminator is REGISTRATION, not the verb: 'never registered' in a status head "
            "marks the walk-away genus whatever verdict word accompanies it. FAILED is used "
            "here precisely because it is the word that would otherwise read as a calibration "
            "verdict.",
        expect="pass",
        plant=[{"ts": "2026-08-31T12:00:00Z", "id": "PC-neverreg-failed",
                "kind": "adversary-block",
                "status": "FAILED at the gate, never registered", "why": "synthetic control"}],
        probe=lambda t, inv: "PC-neverreg-failed" in
                             ((inv.get("unpriced_walkaway") or {}).get("ids") or []),
    ),
    dict(
        name="REGISTERED id is never flattened to a walk-away",
        why="Arc's requested both-ways test, direction 2 — the sharp version. A PRICED id "
            "whose status head ALSO carries the phrase must NOT read as a walk-away: "
            "registration state outranks the phrase, which is the whole content of 'the "
            "discriminator is REGISTRATION, not the verb'. Flattening here would inject a "
            "non-event into prior calibration — the exact harm arc declined to risk by "
            "refusing to let us wire DEAD as a word.",
        expect="pass",
        plant=[{"ts": "2026-08-31T12:01:00Z", "id": "PC-registered-dead", "kind": "ab",
                "prior": 0.4, "why": "synthetic control"},
               {"ts": "2026-08-31T12:02:00Z", "id": "PC-registered-dead", "kind": "resolution",
                "status": "DEAD at the gate, never registered", "result": "failed",
                "note": "synthetic control: priced, so registration state must win"}],
        probe=lambda t, inv: "PC-registered-dead" not in
                             ((inv.get("unpriced_walkaway") or {}).get("ids") or []),
    ),
    dict(
        name="prose on `result` does NOT score",
        why="Guards the dialect-7 widening of `result_field`. 17 live lines carry a `result` "
            "outside kind=resolution and most are instrument PROSE — 'FAILED — no candidate "
            "beats levels'. The bare-token condition is what keeps opening `result` from "
            "reopening the hole dialect-2's gate was closed against; without this control that "
            "condition could be relaxed by anyone and nothing would say so.",
        expect="pass",
        plant=[{"ts": "2026-08-31T12:03:00Z", "id": "PC-prose-result", "kind": "instrument",
                "result": "FAILED — synthetic control prose, must not read as a verdict"}],
        probe=lambda t, inv: (inv.get("disposition") or {}).get("PC-prose-result") != "verdict",
    ),
    dict(
        name="walk-away on `outcome` of an unpriced id ALERTs",
        why="Positive control for the dialect-7 carrier-legality face. Zero live violations, so "
            "without a planted specimen the check is indistinguishable from a rule that cannot "
            "fire — the pinned-green shape. Only the `outcome` half is wired: the mirror rule "
            "collides with dialect-2 (17 priced lines carry cleared/failed on `result` as "
            "correct practice) and is an open question back to arc.",
        expect="pass",
        plant=[{"ts": "2026-08-31T12:04:00Z", "id": "PC-miscarried", "kind": "eval",
                "outcome": "withdrawn", "note": "synthetic: walk-away on the wrong carrier"}],
        probe=lambda t, inv: any("PC-miscarried" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="calibration word on a NEVER-REGISTERED id ALERTs",
        why="dialect-7-scope's load-bearing invariant: a verdict with no prior behind it "
            "grades nothing, so the line reads like a resolution and scores on no face.",
        expect="pass",
        plant=[{"ts": "2026-08-31T13:00:00Z", "id": "PC-genus-unpriced", "kind": "eval",
                "outcome": "cleared", "note": "synthetic: calibration word, never priced"}],
        probe=lambda t, inv: any("PC-genus-unpriced" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="REGISTER-THEN-REFUSE does NOT fire",
        why="THE GUARD ON THE INVARIANT WE REFUSED TO WIRE. Arc's paired rule — 'a walk-away "
            "word on a PRICED id fires' — has 20 historical hits that are register-then-refuse "
            "WORKING AS DESIGNED: 14 of the 16 ids on the DECLINED face carry a prior, and RTR "
            "(2026-08-17) requires pricing first and refusing second. Wiring it would outlaw "
            "arc's own protocol. This control is what makes that refusal durable rather than a "
            "comment: if a later reader 'completes' the pair, this goes red immediately.",
        expect="pass",
        plant=[{"ts": "2026-08-31T13:01:00Z", "id": "PC-rtr", "kind": "ab", "prior": 0.35,
                "why": "synthetic control: priced first, per register-then-refuse"},
               {"ts": "2026-08-31T13:02:00Z", "id": "PC-rtr", "kind": "resolution",
                "resolution": "refused", "note": "synthetic: correctly refused AFTER pricing"}],
        probe=lambda t, inv: not any("PC-rtr" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="`void` on an unpriced id does NOT fire",
        why="Guards the one refinement made to arc's rule. Arc named cleared/failed/void; "
            "`void` is excluded because on an unpriced line it scores nothing by construction, "
            "and including it fires 4 alerts whose only remedy is retro-pricing — which arc's "
            "own 08-24 peek prohibition forbids. If someone restores `void` to the tuple, this "
            "control says so.",
        expect="pass",
        plant=[{"ts": "2026-08-31T13:03:00Z", "id": "PC-void-unpriced", "kind": "eval",
                "outcome": "void", "note": "synthetic: void on an unpriced line is legal"}],
        probe=lambda t, inv: not any("PC-void-unpriced" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="every STANDING line is inside the tail -40 view",
        why="The sweep reads `| tail -40` and invariants prints ~170 lines, so a standing fact "
            "emitted at its own face lands ~140 lines from the bottom and is not in the view "
            "at all. Recorded as a decay class on 2026-08-29 and fixed for the stop-rule trip "
            "ONLY — the two acknowledged-specimen prints were left behind and a third was "
            "added on 2026-08-31 before anyone noticed. Three instances of a rule that was "
            "already written down is what a prose rule is worth; this makes it executable.",
        expect="pass",
        plant=[],
        probe=lambda t, inv: all(
            (len(t.rstrip().split("\n")) - i) <= 40
            for i, ln in enumerate(t.rstrip().split("\n"))
            if ln.startswith("STANDING")),
    ),
    dict(
        name="walk-away declared ONLY in `note`",
        why="STILL A TRACKED GAP, but the reason changed. The specimen that motivated it "
            "(stage3-eval-r3) is CURED — arc restated it on `result` per dialect-7 — so this no "
            "longer costs a live number. What remains is the class: `note` is not a carrier and "
            "will not become one, because `criterion` and `void_conditions` carry CONDITIONAL "
            "heads ('CLEARED iff the draw lands in [1.33, 1.95]') and widening buys false "
            "verdicts to cure a missed one. Post-dialect-7 a note-only disposition is a "
            "WRITER-side violation rather than a reader gap. Kept xfail so that stays visible; "
            "an XPASS here would mean someone widened the carrier set.",
        expect="xfail",
        plant=[{"ts": "2026-08-31T12:05:00Z", "id": "PC-note-only-walkaway", "kind": "eval",
                "note": "WITHDRAWN at the adversary round, never registered, zero GPU spent."}],
        probe=lambda t, inv: any("PC-note-only-walkaway" in a for a in inv.get("alerts") or []),
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
