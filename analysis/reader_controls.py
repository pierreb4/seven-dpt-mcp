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
import concurrent.futures as cf, json, os, subprocess, sys, tempfile

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
        name="ACKNOWLEDGED alert class stands down, and is COUNTED",
        why="2026-09-01, arc's dialect-11. Two alerts named a remedy their recipient could not "
            "perform (5 ids unpriceable under the peek prohibition, one split result already "
            "resolved), so both would have fired on every sweep forever — which is how an alert "
            "channel decays into noise. The structured channel ends that. Stand-down, never "
            "silence: if an acknowledged alert simply stopped printing, the alert set would "
            "shrink for a reason indistinguishable from the record improving.",
        expect="pass",
        plant=[{"ts": "2026-09-01T12:00:00Z", "id": "PC-uwack-ack", "kind": "desk", "result": "withdrawn", "note": "synthetic control: unpriced walk-away specimen"},
               {"ts": "2026-09-01T12:01:00Z", "id": "PC-ack-line", "kind": "scoring-note",
                "alert_class": "unpriced-walk-away", "acknowledges": ["PC-uwack-ack"],
                "note": "synthetic control: structured acknowledgement"}],
        probe=lambda t, inv: (
            not any("PC-uwack-ack" in a for a in inv.get("alerts") or [])
            and any(r.get("face") == "unpriced-walk-away" and r.get("id") == "PC-uwack-ack"
                    and "PC-ack-line" in (r.get("via") or [])
                    for r in inv.get("acknowledgement_standdowns") or [])),
    ),
    dict(
        name="an id OUTSIDE the acknowledges array still ALERTS",
        why="Arc's own second limit on dialect-11, and the control that keeps the whole channel "
            "honest: an acknowledgement discharges the response obligation for the ids it "
            "NAMES and nothing else. Without this, a single acknowledgement line could quietly "
            "become a blanket amnesty for a class — the rewarded misuse of every "
            "acknowledgement rule, which is the next specimen hiding behind the standing line.",
        expect="pass",
        plant=[{"ts": "2026-09-01T12:00:00Z", "id": "PC-uwack-ack", "kind": "desk", "result": "withdrawn", "note": "synthetic control: unpriced walk-away specimen"}, {"ts": "2026-09-01T12:00:00Z", "id": "PC-uwack-live", "kind": "desk", "result": "withdrawn", "note": "synthetic control: unpriced walk-away specimen"},
               {"ts": "2026-09-01T12:01:00Z", "id": "PC-ack-line", "kind": "scoring-note",
                "alert_class": "unpriced-walk-away", "acknowledges": ["PC-uwack-ack"],
                "note": "synthetic control: acknowledges ONE of the two"}],
        probe=lambda t, inv: any(
            "PC-uwack-live" in a and "PC-uwack-ack" not in a
            for a in inv.get("alerts") or []),
    ),
    dict(
        name="UNKNOWN alert_class raises its own alert",
        why="The historical specimen, replayed verbatim: arc's first dialect-11 line carried "
            "`unpriced-walkaway` against this file's `unpriced-walk-away`. Under equality "
            "matching that stands nothing down while both parties believe the class "
            "acknowledged — a phrasing-keyed read with a silent no-match, inside the channel "
            "built to escape phrasing-keyed reads. The fix is a closed vocabulary, NOT lenient "
            "matching: normalising the hyphen would make every future near-miss invisible.",
        expect="pass",
        plant=[{"ts": "2026-09-01T12:02:00Z", "id": "PC-badkey", "kind": "scoring-note",
                "alert_class": "unpriced-walkaway", "acknowledges": ["PC-whatever"],
                "note": "synthetic control: composed key, off by one hyphen"}],
        probe=lambda t, inv: any(
            "ack-channel" in a and "unpriced-walkaway'" in a and "NO check" in a
            for a in inv.get("alerts") or []),
    ),
    dict(
        name="a REAL but UNWIRED alert_class is reported INERT",
        why="The third way an acknowledgement fails to land, and the least visible: the class "
            "exists, the key is spelt right, and the alert site simply never consults the "
            "channel. Nothing is wrong with the ledger, so a quiet reader would leave the "
            "writer believing a stand-down happened while the alert fires at full strength. "
            "An acknowledgement the reader never reads must be as loud as one that is misspelt.",
        expect="pass",
        plant=[{"ts": "2026-09-01T12:03:00Z", "id": "PC-unwired", "kind": "scoring-note",
                "alert_class": "ts-disorder", "acknowledges": ["PC-whatever"],
                "note": "synthetic control: legal class, site not wired"}],
        probe=lambda t, inv: any(
            "ack-channel" in a and "ts-disorder" in a and "INERT" in a
            for a in inv.get("alerts") or []),
    ),
    dict(
        name="HALF an acknowledgement alerts rather than passing quietly",
        why="`alert_class` without `acknowledges` looks like an acknowledgement to a human "
            "reader and is invisible to the parser — the absent-vs-unread conflation this "
            "whole layer exists for, arriving in the acknowledgement channel itself. A "
            "non-list `acknowledges` is the same defect: one id written as a bare string "
            "silences nothing while reading correctly.",
        expect="pass",
        plant=[{"ts": "2026-09-01T12:04:00Z", "id": "PC-halfack", "kind": "scoring-note",
                "alert_class": "unpriced-walk-away",
                "note": "synthetic control: no `acknowledges` array"}],
        probe=lambda t, inv: any(
            "ack-channel" in a and "PC-halfack" in a and "half an acknowledgement" in a
            for a in inv.get("alerts") or []),
    ),
    dict(
        name="an acknowledged id matching NO specimen alerts",
        why="The last silent path: correct class, correct shape, and an id that matches nothing "
            "— a typo in the id, or a defect already gone. It stands nothing down and counts as "
            "nothing, so without this the acknowledgement is a no-op that looks discharged in "
            "the record. Every other way of getting this wrong is loud; this one has to be too.",
        expect="pass",
        plant=[{"ts": "2026-09-01T12:05:00Z", "id": "PC-ghostack", "kind": "scoring-note",
                "alert_class": "unpriced-walk-away", "acknowledges": ["PC-no-such-id"],
                "note": "synthetic control: acknowledges an id that does not exist"}],
        probe=lambda t, inv: any(
            "ack-channel" in a and "PC-no-such-id" in a and "matched NO specimen" in a
            for a in inv.get("alerts") or []),
    ),
    dict(
        name="a RESTATED acknowledgement supersedes its predecessor",
        why="2026-09-01. An acknowledgement goes stale when the check it answers is sharpened: "
            "ids that used to be specimens stop being them, and the stand-down silences nothing "
            "— the phantom class, at the scale of a whole class rather than one range. It "
            "happened within the hour: adding `resolution` to the carriers this reader consults "
            "took undeclared-disposition from 16 specimens to 0, stranding all 16 "
            "acknowledgements. Append-only means the line cannot be withdrawn, so restatement "
            "is the only correction that exists — the same answer as the kind-dialect fix and "
            "the same one dialect-3 already gives 153 of 234 ids. An empty array retires it.",
        expect="pass",
        plant=[{"ts": "2026-09-01T12:00:00Z", "id": "PC-uwack-restated", "kind": "desk", "result": "withdrawn", "note": "synthetic control: walk-away specimen"},
               {"ts": "2026-09-01T14:00:00Z", "id": "PC-restate-ack", "kind": "scoring-note",
                "alert_class": "unpriced-walk-away", "acknowledges": ["PC-uwack-restated"],
                "note": "synthetic control: the original acknowledgement"},
               {"ts": "2026-09-01T14:01:00Z", "id": "PC-restate-ack", "kind": "scoring-note",
                "alert_class": "unpriced-walk-away", "acknowledges": [],
                "amends": "PC-restate-ack",
                "note": "synthetic control: retired — the id is no longer a specimen"}],
        probe=lambda t, inv: any("PC-uwack-restated" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="a ts disorder on a MARKED line is a FAULT and resists acknowledgement",
        why="The rewarded misuse of the era boundary. `ts-correction-<a>-<b>` and the prose "
            "acknowledgement channel were both built for HAND typos; on a machine-stamped line "
            "the same disorder means the clock, the timezone, or the helper is wrong. If the "
            "typo channel could still silence it, the first real clock bug would be waved "
            "through by a rule written for a different genus — the acknowledgement channel's "
            "rewarded misuse arriving through an era boundary rather than a careless waiver. "
            "This control acknowledges the id in the normal way and requires the alert anyway.",
        expect="pass",
        plant=[{"ts": "2026-09-02T10:00:00Z", "id": "PC-clockfault", "kind": "desk",
                "note": "synthetic control: machine-stamped, later day"},
               {"ts": "2026-09-01T10:00:00Z", "id": "PC-clockfault", "kind": "desk",
                "note": "synthetic control: machine-stamped, EARLIER day on the same id"},
               {"ts": "2026-09-01T16:30:00Z", "id": "kind-dialect-semantics-PC13",
                "kind": "scoring-note",
                "note": "synthetic control: acknowledges PC-clockfault as a day-typo"}],
        probe=lambda t, inv: any(
            "stamp-fault" in a and "PC-clockfault" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="an UNMARKED line in the machine era ALERTs (helper bypass)",
        why="2026-09-01, arc's dialect-12. Every line scripts/ledger_append.py writes carries "
            "`stamp: machine`, so an unmarked line after the boundary was appended around the "
            "helper and its `ts` carries neither dialect's authority. Keyed on POSITION (the "
            "first marked line) rather than a date, so it needs no constant and cannot go "
            "stale. This control opts out of the harness's automatic marking, which is the "
            "only place in the suite that does.",
        expect="pass",
        plant=[{"ts": "2026-09-01T16:00:00Z", "id": "PC-bypass", "kind": "desk", "stamp": None,
                "note": "synthetic control: appended around the helper"}],
        probe=lambda t, inv: any(
            "stamp-bypass" in a and "PC-bypass" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="a RETIREMENT (empty array with history) is not malformed",
        why="2026-09-01. The half-pair guard was written with the dialect-11 channel; the "
            "restatement mechanism arrived hours later and nothing reconciled them. `_acks` "
            "read `acknowledges: []` as a valid retirement while `_ack_malformed` called the "
            "same line malformed — two readers in ONE file disagreeing about one word, which is "
            "mechanism (ii) of the class this file exists to catch, committed by its author on "
            "the day he wrote the taxonomy down. Arc hit it following the spec verbatim.",
        expect="pass",
        plant=[{"ts": "2026-09-01T15:00:00Z", "id": "PC-retire", "kind": "scoring-note",
                "alert_class": "unpriced-walk-away", "acknowledges": ["PC-something"],
                "note": "synthetic control: the original acknowledgement"},
               {"ts": "2026-09-01T15:01:00Z", "id": "PC-retire", "kind": "scoring-note",
                "alert_class": "unpriced-walk-away", "acknowledges": [],
                "note": "synthetic control: retirement — legal, has history"}],
        probe=lambda t, inv: not any(
            "half an acknowledgement" in a and "PC-retire" in a
            for a in inv.get("alerts") or []),
    ),
    dict(
        name="a BARE empty acknowledgement (no history) still ALERTs",
        why="The other direction, and the reason the exception is scoped rather than blanket. "
            "An empty array with nothing behind it retires nothing and is indistinguishable "
            "from a half-written line — exactly the case the guard was built for. Widening the "
            "exception to every empty array would have retired the guard to fix a disagreement, "
            "which is the symmetric-half error wearing a bugfix's clothes.",
        expect="pass",
        plant=[{"ts": "2026-09-01T15:10:00Z", "id": "PC-bare-empty", "kind": "scoring-note",
                "alert_class": "unpriced-walk-away", "acknowledges": [],
                "note": "synthetic control: empty, no prior acknowledgement under this id"}],
        probe=lambda t, inv: any(
            "half an acknowledgement" in a and "PC-bare-empty" in a
            for a in inv.get("alerts") or []),
    ),
    dict(
        name="INERT ts-correction range ALERTs",
        why="2026-09-01. A `ts-correction-<a>-<b>` id silences future-ts for that line range and "
            "nothing ever asked whether the range held a specimen. Arc acknowledged a +10-minute "
            "same-day future stamp against a check that is DAY-granular by design, so no alert "
            "had ever existed: the acknowledgement discharged nothing, counted nowhere, and left "
            "a phantom implying the detector saw a defect. The identical guard had been written "
            "four hours earlier for the dialect-11 channel, two hundred lines away — mechanism "
            "(iii) of our own recurring class, in the file that defines the taxonomy.",
        expect="pass",
        plant=[{"ts": "2026-09-01T13:00:00Z", "id": "ts-correction-99001-99001",
                "kind": "scoring-note", "note": "synthetic control: range holds no specimen"}],
        probe=lambda t, inv: any(
            "ts-correction-inert" in a and "99001" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="a ts-correction range WITH a specimen does NOT alert",
        why="The other direction, and the one that matters: 470-474 is a real acknowledgement of "
            "a real +1-day typo pair. A check that cannot tell a live range from an inert one "
            "would retire the mechanism that makes the ts channel usable. Discrimination, not "
            "detection — the pinned-green shape is a rule that fires on everything.",
        expect="pass",
        plant=[],
        probe=lambda t, inv: not any(
            "ts-correction-inert" in a and "470-474" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="UNDECLARED event value ALERTs (must-ignore is a decision)",
        why="`event_class` returns 'ignore' for every non-resolution event value, so any string "
            "arc had never used before became bookkeeping BY ACCIDENT. Ignoring is the right "
            "behaviour and was the wrong way to reach it: the distributed-systems rule is that "
            "ignoring is safe only for elements DECLARED ignorable, because otherwise a reader "
            "cannot distinguish 'known irrelevant' from 'never seen'.",
        expect="pass",
        plant=[{"ts": "2026-09-01T13:10:00Z", "id": "PC-newevent", "event": "synthetic-new-event",
                "note": "synthetic control: undeclared event value"}],
        probe=lambda t, inv: any(
            "event-dialect" in a and "synthetic-new-event" in a and "UNDECLARED" in a
            for a in inv.get("alerts") or []),
    ),
    dict(
        name="a DECLARED event value does not alert",
        why="Discrimination for the control above. 31 values are declared and all 31 are in live "
            "use; a tripwire that fired on them too would be a rule that cannot pass, which is "
            "the same vacuity as one that cannot fail.",
        expect="pass",
        plant=[{"ts": "2026-09-01T13:11:00Z", "id": "PC-oldevent", "event": "launched",
                "note": "synthetic control: declared annotation-genus event"}],
        probe=lambda t, inv: not any(
            "event-dialect" in a and "PC-oldevent" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="UNDECLARED disposition head on `result` ALERTs",
        why="The must-understand half of the genus split. A head word on a declared disposition "
            "carrier that contains no declared token reads as a verdict to a human and scores on "
            "no face — the silent-no-match this layer exists for, on the one field where silence "
            "is never safe.",
        expect="pass",
        plant=[{"ts": "2026-09-01T13:20:00Z", "id": "PC-undisp", "kind": "desk",
                "result": "SPLENDID — the lever did everything we hoped",
                "note": "synthetic control: verdict-shaped word nobody declared"}],
        probe=lambda t, inv: any(
            "undeclared-disposition" in a and "PC-undisp" in a for a in inv.get("alerts") or []),
    ),
    dict(
        name="prose on `status` does NOT count as an undeclared disposition",
        why="The must-IGNORE half, and the reason this rule is scoped to outcome/result. Arc "
            "writes `status` as prose by design and only its WITHDRAWN head is read, so "
            "demanding a declared word there would fire on 60+ lines of correct practice — the "
            "symmetric completion that looks tidy and outlaws the counterparty's own convention.",
        expect="pass",
        plant=[{"ts": "2026-09-01T13:21:00Z", "id": "PC-statusprose", "kind": "desk",
                "status": "characterized the wall as a token-budget effect, not a lever effect",
                "note": "synthetic control: status prose"}],
        probe=lambda t, inv: not any(
            "undeclared-disposition" in a and "PC-statusprose" in a
            for a in inv.get("alerts") or []),
    ),
    dict(
        name="a declared word PLUS a suffix is understood, not flagged",
        why="`failed-as-blind-bfs`, `instrument-void-lever-did-not-fire` and four more are "
            "compounds of a declared token. They ARE understood by result_field, so flagging "
            "them would be the check disagreeing with the reader it is meant to protect — two "
            "statements of one fact, which is the genus underneath every bite in this file.",
        expect="pass",
        plant=[{"ts": "2026-09-01T13:22:00Z", "id": "PC-compound", "kind": "desk",
                "result": "failed-as-synthetic-compound",
                "note": "synthetic control: declared token + suffix"}],
        probe=lambda t, inv: not any(
            "undeclared-disposition" in a and "PC-compound" in a
            for a in inv.get("alerts") or []),
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
        name="TERMINAL and STATUS_HEADS are the SAME OBJECT in both parsers",
        why="The three-constant tidy, 2026-09-01. Both were declared twice with identical "
            "literals, one carrying the comment \"mirrors ledger_invariants.STATUS_HEADS\" — a "
            "comment asserting an equality nothing enforced, which is the shape every drift in "
            "this pair has taken (22 of 42 parser commits touched exactly one side). Identity, "
            "not equality: two equal tuples today are two tuples tomorrow.",
        expect="pass",
        code = """
import sys, json, io, contextlib
sys.path.insert(0, %r)
import ledger_invariants as L
with contextlib.redirect_stdout(io.StringIO()):   # calibration reports at import time
    import calibration as C
print(json.dumps({"terminal": C.TERMINAL is L.TERMINAL,
                  "status_heads": C.STATUS_HEADS is L.STATUS_HEADS,
                  "redeclared": [n for n in ("TERMINAL", "STATUS_HEADS")
                                 if open(C.__file__).read().count(chr(10) + n + " = ")]}))
""",
        probe=lambda r: (r.get("terminal") is True and r.get("status_heads") is True
                         and r.get("redeclared") == []),
    ),
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
    # PARALLEL, NOT PRUNED (2026-09-01). The hook had crept 5.0s -> 14.7s and the obvious
    # move was to tag more controls `slow` and drop them from the push path. Measuring first
    # refused that: cost is FLAT at 0.33-0.36s across all 40, because each control is one full
    # parser subprocess over the whole ledger. There is no slow subset to cut — tagging would
    # have removed coverage at random and called it optimisation, and the FAST path's whole
    # discipline is that a skipped control is announced rather than counted as passing.
    #
    # The controls are already independent: separate temp dirs, separate ledgers, separate
    # INVARIANTS_JSON, no shared state. So they run concurrently and the hook keeps ALL of
    # them. Deliberately NOT batched into fewer parser runs: plants would then share a ledger
    # and could stand each other's specimens down — reader interaction is the exact thing these
    # controls exist to detect, so making them share a reader would corrupt the instrument to
    # speed it up. Results are collected and printed in DECLARATION order, so the output is
    # byte-identical to the serial version and a diff of two sweeps still means something.
    def _run_one(c):
        lines = [c["strip"](l) for l in base] if c.get("strip") else list(base)
        lines += [({"stamp": "machine", **pl} if "stamp" not in pl else
                   {k: v for k, v in pl.items() if not (k == "stamp" and v is None)})
                  for pl in c["plant"]]
        with tempfile.TemporaryDirectory() as tmp:
            try:
                text, inv = run(lines, tmp)
                return bool(c["probe"](text, inv)), text, inv
            except Exception as e:
                return False, f"{type(e).__name__}: {e}", {}

    _workers = max(1, min(int(os.environ.get("CONTROLS_JOBS") or 6),
                          (os.cpu_count() or 2) - 1, len(CONTROLS) or 1))
    with cf.ThreadPoolExecutor(max_workers=_workers) as _ex:
        _results = list(_ex.map(_run_one, CONTROLS))

    for c, (dissented, text, inv) in zip(CONTROLS, _results):
        lines = [c["strip"](l) for l in base] if c.get("strip") else list(base)
        # Plants land at the END of the ledger, i.e. inside the machine-stamped era (dialect-12,
        # boundary line 509). A line appended NOW would go through scripts/ledger_append.py and
        # carry `stamp: machine`, so marking plants is the FAITHFUL simulation; leaving them
        # unmarked simulates a helper bypass, which is not what these controls are testing and
        # which broke six negative probes the hour the era check landed. A control that wants to
        # test the bypass opts out by setting "stamp": None explicitly.
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
