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
# CONTROLS_FAST=1 skips controls tagged `slow` — used by the pre-push hook, where the whole
# suite is ~17s and ONE control (the reader-path census regression) is 12s of it. The daily
# sweep runs everything. Skipped controls are ANNOUNCED, never silently dropped: a suite that
# quietly runs fewer checks than its banner implies is the pinned-green shape one level up.
FAST = os.environ.get("CONTROLS_FAST") == "1"

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
        name="acknowledgement stand-down is COUNTED, not just silent",
        why="Arc writes the ledger AND the kind-dialect-semantics lines that silence our "
            "tripwires — in-band, on the same append-only file. `no-mistakes` refuses that "
            "shape by default (execution-bearing config is read only from the trusted default "
            "branch); we cannot, since arc's ledger is the only channel there is, so we measure "
            "the channel instead. Before this, a stand-down printed a STANDING line and was "
            "counted by nothing, so the question that matters — is the alert set shrinking "
            "because the RECORD improved or because it was ACKNOWLEDGED — had no number. This "
            "plants a specimen AND its acknowledgement and requires the stand-down to appear in "
            "the published denominator, attributed to the declaration that caused it.",
        expect="pass",
        plant=[{"ts": "2026-08-31T15:00:00Z", "id": "PC-standdown-draw", "kind": "hidden-draw",
                "note": "synthetic control: unpriced draw, would alert on its own"},
               {"ts": "2026-08-31T15:01:00Z", "id": "kind-dialect-semantics-PC4",
                "kind": "scoring-note",
                "note": "Acknowledging PC-standdown-draw as a known unscoreable specimen."}],
        probe=lambda t, inv: any(
            r.get("id") == "PC-standdown-draw"
            and "kind-dialect-semantics-PC4" in (r.get("via") or [])
            for r in inv.get("acknowledgement_standdowns") or []),
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
        name="RESTATEMENT stands an undeclared kind down, and is COUNTED",
        why="2026-09-01. The ledger is append-only, so an undeclared token can never leave the "
            "line that carries it — the only correction available to the writer is to append a "
            "restatement. This check ignored those, so its printed remedy was 'extend "
            "KIND_TOKENS', the single action both sides had correctly refused: arc restated two "
            "ids exactly as dialect-3's latest-wins convention prescribes and the alert did not "
            "move. That is the defect we had criticised in arc's dialect-8 the day before — an "
            "alert whose recipient cannot clear it by doing the right thing — sitting in our own "
            "face. Stand-down, not silence: it must land in the acknowledgement denominator.",
        expect="pass",
        plant=[{"ts": "2026-09-01T09:00:00Z", "id": "PC-restated",
                "kind": "synthetic-restated-kind", "note": "synthetic control: undeclared"},
               {"ts": "2026-09-01T09:01:00Z", "id": "PC-restated", "kind": "desk-probe",
                "amends": "PC-restated", "note": "synthetic control: class restated"}],
        probe=lambda t, inv: (
            "synthetic-restated-kind" in ((inv.get("kind_census") or {}).get("superseded") or {})
            and not any("synthetic-restated-kind" in a for a in inv.get("alerts") or [])
            and any(r.get("id") == "PC-restated"
                    for r in inv.get("acknowledgement_standdowns") or [])),
    ),
    dict(
        name="a RESOLUTION line does NOT supersede an undeclared kind",
        why="The rewarded misuse of the restatement rule. A resolution line lands after almost "
            "every registration, usually within the hour, and carries `amends` naming the same "
            "id — so if any later declared kind counted as a restatement, the tripwire would be "
            "stood down as a matter of routine by the very line that resolves the bet. This is "
            "what _ROLE_KINDS exists to prevent, and prose saying so is what a later reader "
            "tidies away.",
        expect="pass",
        plant=[{"ts": "2026-09-01T09:10:00Z", "id": "PC-role-guard",
                "kind": "synthetic-roleguard-kind", "note": "synthetic control: undeclared"},
               {"ts": "2026-09-01T09:11:00Z", "id": "PC-role-guard", "kind": "resolution",
                "amends": "PC-role-guard", "result": "cleared",
                "note": "synthetic control: a role line, NOT a restatement"}],
        probe=lambda t, inv: any("synthetic-roleguard-kind" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="a later declared kind WITHOUT `amends` does not stand down",
        why="Restatement is a deliberate act and must say so. Without the marker, any later "
            "registration reusing an id would clear the tripwire by accident — the silent "
            "no-match failure this whole layer was built for, arriving through the remedy.",
        expect="pass",
        plant=[{"ts": "2026-09-01T09:20:00Z", "id": "PC-noamends",
                "kind": "synthetic-noamends-kind", "note": "synthetic control: undeclared"},
               {"ts": "2026-09-01T09:21:00Z", "id": "PC-noamends", "kind": "desk-probe",
                "note": "synthetic control: declared kind but NO amends marker"}],
        probe=lambda t, inv: any("synthetic-noamends-kind" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="alert remedies name the REAL edit sites",
        why="Three alerts told the operator to 'extend X in BOTH parsers'. Two were stale — the "
            "OUTCOME_DECLARED one within hours of that constant being single-sourced, the "
            "KIND_TOKENS one for WEEKS (recorded as stale in project memory, alert text never "
            "touched). An alert whose remedy names an architecture that no longer exists sends "
            "the reader to edit a file with nothing to edit. The text is now COMPUTED from "
            "which files actually define the name; this control plants an undeclared kind token "
            "and requires the resulting alert to name ledger_invariants ONLY — it goes red if "
            "anyone re-hardcodes 'both parsers', and it also goes red (correctly, wanting the "
            "text updated) if KIND_TOKENS is ever genuinely duplicated again.",
        expect="pass",
        plant=[{"ts": "2026-08-31T16:00:00Z", "id": "PC-editsite", "kind": "synthetic-editsite-kind",
                "note": "synthetic control: undeclared kind token"}],
        probe=lambda t, inv: any(
            "Extend KIND_TOKENS in ledger_invariants.py ONLY" in a
            for a in inv.get("alerts") or []),
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


# ── vocabulary controls ─────────────────────────────────────────────────────
# A different shape from the planted-specimen controls above: these assert a property of the
# READERS THEMSELVES rather than of a ledger line, so they cannot be expressed as a plant.
# They run in a SUBPROCESS, which is what lets this file keep importing neither parser — the
# no-import rule exists so a control cannot inherit the bug it is testing, and shelling out
# preserves that while still letting the check reach inside the modules.
VOCAB_CONTROLS = [
    dict(
        name="dialect vocabulary reaches BOTH parsers",
        why="Until 2026-08-31 calibration.py re-encoded subsets of OUTCOME_DECLARED as literal "
            "tuples. Measured then: `is_declined`'s tuple missed nothing ONLY because prefix "
            "matching happens to catch `refused-by-evidence`, and DECLARED_RESULT_WORDS missed "
            "TEN declared words outright. Both latent, neither guarded. The dialect grows by "
            "absorption — 20+ words since 08-05 — so 'latent' is a schedule, not a state. This "
            "adds a synthetic word to the shared vocabulary and requires BOTH parsers to see "
            "it; a future re-literalisation of either list turns it red.",
        # THE ORDER OF THESE IMPORTS IS THE WHOLE CONTROL. The first cut re-derived
        # C.DECLINED_WORDS inside the probe — which tested THIS FILE'S re-derivation, not
        # calibration's, and passed with calibration's old literal tuple restored. A control
        # pinned green while auditing pinned-green readers; caught only by running the
        # meta-test. Instead: extend the shared vocabulary BEFORE calibration is imported, so
        # calibration's own module-level derivation is what gets exercised. Re-literalise that
        # list and this goes red, which is the property being bought.
        code = """
import sys, io, json, contextlib
sys.path.insert(0, %r)
import ledger_invariants as L
probe = "synthetic-declined-probe"
L.OUTCOME_DECLARED[probe] = "declined"
L._DECL_ORDER = sorted(L.OUTCOME_DECLARED, key=len, reverse=True)   # import-time list
with contextlib.redirect_stdout(io.StringIO()):
    import calibration as C          # derives its own words HERE, from the extended vocabulary
line = {"id": "X", "outcome": probe}
print(json.dumps({"inv": bool(L.is_declined(line)), "cal": bool(C.is_declined(line))}))
""",
        probe=lambda r: r.get("inv") is True and r.get("cal") is True,
    ),
    dict(
        name="reader-path census names the known hidden gate",
        slow=True,   # runs the tracer over the whole ledger: ~12s, most of the suite's cost
        why="Regression control on the instrument built to find bite 7. The UNPRICED WALK-AWAY "
            "face names outcome/resolution/result/status in its own source but ALSO reads "
            "`event`, via event_class — the veto reader that discarded arc's correct "
            "restatement. The census must keep naming it. Discrimination was verified by hand "
            "when the census was built: remove the veto and the `event` row DISAPPEARS, so this "
            "is tracking a real path rather than listing every field.",
        code = """
import sys, io, json, contextlib, collections
sys.path.insert(0, %r)
import reader_paths as RP, ledger_invariants as L
RP._PARSER_FILE = __import__("os").path.abspath(L.__file__)
RP._FACES = RP.load_faces(RP._PARSER_FILE)
L.json = RP._JsonShim(json)
with contextlib.redirect_stdout(io.StringIO()):
    old, L.OUTJSON = L.OUTJSON, "/tmp/reader_paths_control.json"
    try: L.main()
    except SystemExit: pass
    finally: L.OUTJSON = old
byface = collections.defaultdict(set)
for k, path, face in RP.ACCESS:
    if path: byface[face].add((k, path[0]))
hit = any("WALK-AWAY" in f and ("event", "event_class") in v for f, v in byface.items())
print(json.dumps({"names_hidden_gate": hit, "faces": len(byface)}))
""",
        probe=lambda r: r.get("names_hidden_gate") is True and (r.get("faces") or 0) > 5,
    ),
]


def run_vocab(c):
    """Run one vocabulary control in a subprocess; return its parsed JSON (or {})."""
    r = subprocess.run([sys.executable, "-c", c["code"] % HERE],
                       capture_output=True, text=True)
    for ln in reversed((r.stdout or "").strip().split("\n")):
        try: return json.loads(ln)
        except ValueError: continue
    return {}


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

    skipped = 0
    for c in VOCAB_CONTROLS:
        if FAST and c.get("slow"):
            skipped += 1; continue
        try: ok = bool(c["probe"](run_vocab(c)))
        except Exception as e: ok = False
        print(f"  {'ok  ' if ok else 'FAIL'} {c['name']}")
        if not ok:
            bad.append((c, False)); print(f"        {c['why']}")
        elif VERBOSE: print(f"        {c['why']}")

    n_x = sum(1 for c in CONTROLS if c["expect"] == "xfail")
    if skipped:
        print(f"  ....  {skipped} slow control(s) SKIPPED (CONTROLS_FAST=1) — not run, not passing")
    print(f"\n  {len(CONTROLS) + len(VOCAB_CONTROLS) - skipped - len(bad)}/{len(CONTROLS) + len(VOCAB_CONTROLS) - skipped} as declared"
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
