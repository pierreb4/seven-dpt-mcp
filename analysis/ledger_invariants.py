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
  POWER-v2      (spark #35, 2026-08-11) unit-agnostic and needs NO banked noise model: a
                prereg that states its own arm SE in criterion text ("SE ~3.2pp") with a
                bar below 2*SE is a COIN-FLIP-GATE — the verdict is a coin toss as
                designed (ksearch-draw1 is the exemplar the unit-bound check missed).
                In-flight ALERTs; historical tallied. Unitless SE mentions are counted
                but not judged (no bar-matching without a unit token) — reported, so the
                check's own blind spot is visible.
  CHANNEL STAMP a lever should name the channel it acts through and that channel's measured
                liveness (`channel` [+ `liveness`] fields on the prereg line, or on ANY later
                line of the id — retro kind=channel-stamp amendments count, 2026-08-17) — the
                discipline that prevents optimizing a channel that is 0% of the live path.
                Coverage is reported; missing stamps WARN (ALERT with CHANNEL_STRICT=1).
  FAMILY MIX    (spark #45, 2026-08-11; Leek temperature-zero) the ledger is SELF-CENSORED
                data — it holds only the probes we chose, so calibration measures prediction
                of our own choices, never coverage of the lever space. This face audits the
                CHOICE STREAM: every prereg (voids included — the choice was made) classified
                into an idea-family (explicit `family` field wins; else retro id/criterion
                rules; coverage reported). Emits exploration share (new-family preregs),
                top-family concentration, and RE-ENTRY-WITHOUT-A-POSITIVE episodes: a family
                reaching >=FAMILY_K preregs across >=2 levers with zero positives (walked in
                file order, so the flag is dated to the prereg that crossed the bar — the
                completion trio must flag before its last arm opened). An IN-FLIGHT prereg
                sitting in such a family ALERTs: close it or state the continue reason.
                Measures first; any exploration QUOTA (Leek's ~20%) is a Pierre/arc policy
                call to be made on this meter's numbers, not shipped inside it.
  EVENT DIALECT v3.1 event lines ABSORBED 2026-08-11 (fired same morning: keyframe-stage1-reader
                FAILED-BY-BARS was the first scoreable event-terminal). {"event":"resolution",
                "status":..} is the verdict channel — heads FAILED*/CLEARED* score, VOID*/
                *PREPUSH* read void, GRAY*/SUBSTRATE-* are terminal-non-scored (power
                statement / feasibility answer), kind="substrate" preregs never scored BEFORE 2026-08-24; arc's 15:10Z classification annotation makes a PRICED substrate resolution score from that day (the prior is a real forecast of the arm's own clauses; unpriced substrate stays the non-scored class).
                Non-resolution events are bookkeeping (ignored) except *KILLED*/*PREPUSH*
                event values (void). The tripwire remains armed for the NEXT drift: a
                resolution status no head rule maps ALERTs — extend event_class in BOTH
                parsers (calibration.py mirrors) and re-check wake sparks #34/#41 patterns.
  ORPHANED-EXISTENTIAL (seven-dpt store): a parked spark with a wakeCondition but no
                `exhaustion` statement can revive but never die — unfalsifiable-in-practice
                spend (scope-leak census 2026-08-01: L=12.8-20.5%, gate cleared). Universal
                claims are exempt (their death IS a null). WARN; ALERT with STORE_STRICT=1.

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

# ── ledger dialects (mirrors calibration.py) ─────────────────────────────────
# v1: two lines/probe — {prior, criterion} then {outcome, note}.
# v2 (2026-08-05..): {kind, status, prior_p_<target>, why, result}; desk items born-and-closed
# in one line; verdict = explicit outcome word OR the result's leading word (strict whitelist).
def prior_of(l):
    if "prior" in l: return l["prior"]
    for k in l:
        if k.startswith("prior_p_"): return l[k]
        if k.startswith("p_") and not k.endswith("_was"): return l[k]   # v3 (see calibration.py)
    return None

def event_class(l):
    """v3.1 event lines (mirrors calibration.py). None if l is not an event line; else
    'cleared'/'failed' (scoreable), 'void', 'nonscored' (terminal power statement /
    feasibility answer), 'ignore' (bookkeeping), 'unknown' (tripwire territory)."""
    ev = l.get("event")
    if not ev: return None
    if ev != "resolution":
        return "void" if ("KILLED" in ev or "PREPUSH" in ev) else "ignore"
    s = (l.get("status") or "").upper()
    if s.startswith("VOID") or "PREPUSH" in s: return "void"
    if s.startswith("GRAY") or s.startswith("SUBSTRATE"): return "nonscored"
    if s.startswith("FAILED"): return "failed"
    if s.startswith("CLEARED"): return "cleared"
    return "unknown"

_HEADS = {"CLEARED": "cleared", "FAILED": "failed", "DEAD": "failed", "KILLED": "failed"}
def verdict_of(l):
    ec = event_class(l)
    if ec in ("cleared", "failed"): return ec
    if ec == "nonscored": return "gray"   # terminal; PARK-STREAK classifies from the note
    if ec == "unknown":
        pass   # 2026-08-30: an UNRECOGNISED status head must not veto the line's own declared
               # verdict word. ship38p1-hidden-draw-2 arrived {"status": "BAND FAILED (2.23 >
               # 1.95 upper bound)...", "outcome": "failed"} — the head is "BAND", so
               # event_class said 'unknown' and this returned None, holding a squarely
               # resolved bet in-flight while the disposition face read it as a verdict (the
               # self-check caught the disagreement). That is the FOURTH bite of the
               # read-one-carrier bug the comment below was written for, this time with an
               # unparseable head as the vetoing carrier. Falling through does NOT guess: the
               # loop demands an explicitly DECLARED verdict word, and the event-dialect
               # tripwire still fires on the unmapped head, so the head gets fixed AND the
               # bet keeps counting meanwhile. Precedence twin of "verdict anywhere beats
               # gray anywhere" below.
    elif ec is not None: return None      # void / ignore
    # BOTH fields, in the same precedence disposition() uses. Reading only the first present
    # field is the bug that has now bitten three separate functions: tr87-lens-ceiling arrived
    # as {"resolution":"cleared","outcome":"positive-below-threshold"} and this returned None,
    # so pair() called a CLEARED bet in-flight while the dialect census called it cleared —
    # one file, two answers.
    # result_field: third carrier, kind=resolution lines only (2026-08-18).
    for w in (l.get("outcome"), l.get("resolution"), result_field(l)):
        if not w: continue
        v = _verdict_word(w)
        if v: return v
    # Word-form GRAY (2026-08-14). Mirrors `ec == "nonscored"` above: terminal, counted as a
    # completed run, never scored. Deliberately a SECOND pass, not folded into the loop above:
    # a verdict on EITHER field must win over a non-scoring word on the other, or a line like
    # {"resolution":"failed","outcome":"ran-and-grayed"} would read gray and drop a real
    # failure off the curve. Verdict anywhere beats gray anywhere.
    for w in (l.get("outcome"), l.get("resolution"), result_field(l)):
        if w and outcome_class(str(w)) == "nonscored": return "gray"
    if l.get("status") == "closed":
        head = ((l.get("result") or "").split() or [""])[0].strip(".,;:—-*")
        return _HEADS.get(head)
    return None

# ── OUTCOME / KIND DIALECT (word-form channel; sibling of the v3.1 event tripwire) ──
# Built 2026-08-12 after `refused-by-evidence` (lora-run3-phaseC) and `substrate+pilot`
# (lora-run3-AB) both passed through every parser silently on the same night. The event
# tripwire watches `event:` lines ONLY — these arrived on outcome/resolution words and on
# `kind`, so that whole class of drift was unalerted BY CONSTRUCTION, not by regression.
# The DECLARED vocabulary and how the parsers treat each word. A word listed here never
# alerts; a word in neither map is new dialect and alerts until someone declares it. Per-id
# disposition deliberately does NOT drive the alert — the first cut of this tripwire flagged
# "unmapped word on a registered bet with no mapped terminal" and both hits were benign
# (repeatnote-draw1 voids on a later line; hidden-replication's `progress` is a day-blocked
# run mid-flight). Structure cannot separate "interim note" from "terminal we can't read";
# the vocabulary can, and declaring it is a human act — same contract as the event tripwire.
OUTCOME_DECLARED = {
    "cleared": "verdict", "failed": "verdict",
    "void": "void", "amended-before-running": "void",
    "relabel": "adjudication", "correction": "bookkeeping", "closed": "unscorable",
    # Non-scoring ledger annotations, declared 2026-08-12 from the live census. Declaring
    # changes NO count (verdict_of already returns None for all of them) — it only keeps
    # the tripwire quiet so a genuinely new word stands out instead of drowning.
    # `confirmed` — kind-dialect-semantics-4 (2026-08-30, be19d83): FACT ESTABLISHED,
    # non-scored, counting on no calibration face. Arc gave it a STRUCTURAL legality
    # condition rather than a stylistic one, which is what makes it absorbable at all:
    # confirmed is legal ONLY on an entry carrying NO prior — a priced entry must use
    # cleared/failed/void. So it can never quietly stand in for `cleared`. The corollary
    # arc stated and this file enforces: if a question of that shape deserves a score, the
    # fix is to PRICE IT AT REGISTRATION, never to score a `confirmed` after the fact —
    # that is a post-hoc prior wearing a different token. The condition is checked below
    # (confirmed-on-a-priced-entry alert); a declaration whose legality condition nothing
    # tests is a comment, not a rule.
    "confirmed": "nonscored",
    "protocol": "annotation", "parked": "annotation", "held": "annotation",
    "stop": "annotation", "amended-before-resolution": "annotation",
    "progress": "in-progress",
    # DECLINED (2026-08-12): decided WITHOUT running. Never scores — the run never
    # happened, so there is no ground truth to grade a prior against — but it is TERMINAL
    # and it is COUNTED. A ledger that records what it ran and not what it declined can
    # never audit its own refusals, and on a programme where running is the expensive move
    # that is where much of the value lives. Protocol (option 4, Pierre 2026-08-12):
    # REGISTER the prereg with the prior you intended, THEN refuse — the prior survives,
    # so "we thought p=0.4 and declined; were we right?" stays answerable later.
    "refused-by-evidence": "declined", "refused": "declined", "declined": "declined",
    # 2026-08-12 overnight, declared 08-13 from arc's own pairing (each appeared WITH the
    # declared verdict that fixes its meaning, so this is absorption, not interpretation):
    # premise-refuted arrived on `resolution":"refused"` — the premise died, so the probe was
    # never run; instrument-inadequate on `resolution":"void"` — the instrument could not
    # measure, so no information. Declared so each stays readable if it ever appears ALONE.
    # NOT declared: `amends …` (shapeid-rot-rung) — arc must say whether amending a refusal
    # VOIDS the bet or REOPENS it; it reads void today only because that line says so.
    "premise-refuted": "declined", "instrument-inadequate": "void",
    # 2026-08-13, arc: RAN-AND-LOST vs WALKED-AWAY is the distinction they need preserved, and
    # they minted a token rather than lose it. tr87-pair-x-rot-joint is 3 arms x 15 tr87 passes
    # on real GPU — a scoreable NEGATIVE, not a refusal. It arrived as
    # {"resolution":"refused","outcome":"refuted-by-run"}, and `refused` alone would have filed
    # a completed run under `declined`: off the curve, and uncounted as evidence in its family.
    # Declared here so the reason word WINS over the verdict field (outcome is checked first),
    # and taught to verdict_of below so it actually scores as a failure.
    "refuted-by-run": "verdict",
    # 2026-08-14 overnight — THE MIDDLE WORLD ARRIVES AS VOCABULARY. The §5 taxonomy we sent
    # arc (evidence-negative / no-scoreable-result / unresolved) came back written INTO the
    # ledger as first-class verdicts: `gray` (ran, in-band, no capability move) and
    # `inconclusive` (ran, CI does not discriminate). Both are RAN-AND-DID-NOT-ADJUDICATE:
    # terminal, counted as a completed attempt, NEVER scored — there is no ground truth to
    # grade a prior against when the run could not tell the two hypotheses apart. This is the
    # word-form of the event-form GRAY* head that has existed since v3.1, and it MUST classify
    # identically or the same concept gets two answers depending on which dialect it arrived
    # in — the exact failure the tripwire exists to catch. The two parsers then diverge ON
    # PURPOSE, mirroring what they already do for event-form GRAY: invariants counts it as a
    # completed run (a family that grayed three times HAS attempted three times), calibration
    # keeps it off the curve (a gray has no y to score). Reason words declared alongside so
    # each stays readable alone.
    "gray": "nonscored", "inconclusive": "nonscored",
    "ran-and-grayed": "nonscored", "ran-and-inconclusive": "nonscored",
    # 2026-08-16 — ONE RUN, TWO PRE-DECLARED QUESTIONS, TWO DIFFERENT VERDICTS.
    # ship-animfeedback-draw1 arrived as {"resolution":"split",
    # "outcome":"SEAM CLEARED / LEVER BELOW BAND"} with `seam_result` and `lever_result` as
    # separate fields and arc's own instruction on the line: "These must not be conflated."
    # The layer's whole model is one id -> one disposition, so it had no way to read this and
    # the census reported the head word `SEAM` as undeclared vocabulary.
    # Declared on `resolution` and NOT on `SEAM`, deliberately. A `"seam": "verdict"` entry
    # would let longest-prefix match collapse "SEAM CLEARED / LEVER BELOW BAND" to a single
    # CLEARED — performing exactly the conflation the line forbids, and booking a positive for
    # a half that was never registered. `split` names the shape instead of picking a winner.
    # UNSCORABLE is the honest class: the run happened (terminal, counted as an attempt), but
    # there is no single prior to grade two answers against — and on this id there is no prior
    # at all, since it never registered a prereg. See the SPLIT RESULT face below, which keeps
    # the id named out loud rather than letting a headline result rest quietly in a bucket.
    "split": "unscorable",
    # 2026-08-22, arc's 08-21 kill wave — NINE arms stopped before GPU in one day.
    # `withdrawn-at-adversary`  THE GOOD CASE, and it was reading as a bug. Four arms
    #                (licpred-l2-train 0.40, servelaw-draw1 0.15, actedness-reorder-delivery
    #                0.45, lora-conv-l2-fidelity-train 0.55) arrived as kind=withdrawn WITH
    #                the prior the arm would have carried — register-then-refuse executed
    #                exactly as the 08-17 protocol asks, unprompted. Because the word was
    #                undeclared, NO field on those lines was readable and all four sat in
    #                IN-FLIGHT: dead arms counted as live bets (in-flight 5 -> 9). The layer
    #                was penalising the only four kills that did it right.
    #                CLASS = `declined`, ANSWERED BY ARC 2026-08-22 in reply to the brief:
    #                "your read is right and mine was the lazier word — I minted it to name the
    #                MECHANISM (killed at the adversary gate), not to assign a class." The
    #                existing `withdrawn` class means "registered, never run, REPLACED BY A
    #                REDESIGN", and none of these was; an adversary verdict is a verdict on
    #                whether the arm as specified could answer its own question, which is a
    #                spend decision. Banked conservatively as `withdrawn` for one commit
    #                (5efffac) rather than guessed at — the asked-first contract, and it cost
    #                one line to move once arc answered.
    # `no-arm`      patheff-sizing: a desk measurement REFUTED THE PREMISE, so no arm was ever
    #                registered ("no arm registered"). Same shape as the declared
    #                `premise-refuted`, so it takes the same class. It carries no prior, which
    #                is the right consequence: it lands on the DECLINED face and trips that
    #                face's existing NO-PRIOR warn, naming itself out loud instead of
    #                vanishing.
    "withdrawn-at-adversary": "declined", "no-arm": "declined",
    # NOT declared, deliberately: `amends …`. Arc's rule (2026-08-13) is SUPERSEDE — the latest
    # line carrying a declared verdict is the disposition, earlier ones are superseded, and an
    # amendment closes the old bet AT THE AMENDING VERDICT rather than reopening it. So `amends`
    # is a reason word whose class is whatever it amends TO; fixing it to one class would be
    # wrong the first time something is amended to `cleared`. Alone on a line it is meaningless
    # and SHOULD alert. The rule itself lives in final_cls (last readable disposition wins).
}

# Words that carry a scoreable verdict, checked against BOTH fields (see verdict_of).
def _verdict_word(w):
    lw = str(w).lower()
    if lw.startswith("cleared"): return "cleared"
    if lw.startswith(("failed", "refuted-by-run")): return "failed"
    return None
_DECL_ORDER = sorted(OUTCOME_DECLARED, key=len, reverse=True)   # longest prefix wins

def outcome_class(w):
    lw = w.lower()
    for k in _DECL_ORDER:
        if lw.startswith(k): return OUTCOME_DECLARED[k]
    return "NEW"

# VERDICT + REASON (arc convention, first seen 2026-08-12). A resolution line may now carry
# BOTH fields: `resolution` the declared verdict token, `outcome` the specific reason —
# {"resolution":"refused","outcome":"premise-refuted"}. Historically only ONE field ever
# appeared and it held the verdict, so precedence never mattered; all 5 dual-field lines put
# the declared word in `resolution`. The old rule (`outcome or resolution`, first wins) read
# the REASON and discarded the VERDICT, so a refused probe read in-flight and drove a false
# "live bet" alert. Rule now: the disposition is the first field yielding a DECLARED class.
# A field left undeclared alongside a declared one is free-text reason, NOT new vocabulary —
# censusing it would flag prose forever ("amends the 2026-08-12T22:20:00Z 'refused'
# resolution" is a sentence, not a word). A line where NEITHER field is declared is the real
# tripwire condition: genuinely unreadable, and that is what now alerts.
def disposition(l):
    """-> (word, class). class 'NEW' means no field on the line was readable."""
    cand = [str(w).strip() for w in (l.get("outcome"), l.get("resolution"), result_field(l)) if w]
    for w in cand:
        c = outcome_class(w)
        if c != "NEW": return w, c
    return (cand[0] if cand else ""), "NEW"

def outcome_word(l):
    return disposition(l)[0]

def has_reason(l):
    """True when the line carries a declared verdict AND a second, free-text reason field."""
    return len([w for w in (l.get("outcome"), l.get("resolution"), result_field(l)) if w]) > 1 \
        and disposition(l)[1] != "NEW"

def is_declined(l):
    return disposition(l)[1] == "declined"

# Registration kinds seen in the live ledger 2026-08-12. Kind is TOKENISED, not compared
# whole: `substrate+pilot` must still hit the substrate rule, or a measurement draw scores
# as an ordinary forecast (it did — it was one of the two entries that took n 40→42).
KIND_TOKENS = {"substrate", "pilot", "instrument", "lever", "desk-probe",
               "protocol", "kernel-arm", "control", "probe",
               "kernel-ab",   # 2026-08-13: A/B kernel run (tr87-pair-x-rot-joint). Carries a
                              # real prior on a real lever, so scoring it as an ordinary
                              # forecast is correct — it is NOT a measurement draw.
               # 2026-08-14: SIX AT ONCE, and they are a THIRD GENUS. Every kind until now
               # answered "what IS this bet?" — a lever, a desk probe, a measurement draw.
               # These answer "what is this LINE doing to a bet that already exists?": a lane
               # note, a hygiene fix, a withdrawal, a re-priced prior, a changed selection
               # rule, a refined channel. They are annotations, and the arrival of six in one
               # night says arc now stamps `kind` on every line rather than only registrations.
               # Declaring them changes NO count — none is `substrate`, so none suppresses
               # scoring, which is correct: a `lane-note` on a live bet must not silently take
               # that bet off the curve. If a future annotation SHOULD suppress scoring it has
               # to say `substrate`; that is the one rule this genus must not quietly acquire.
               "withdrawal", "prior-amendment", "selection-rule-amendment",
               "lane-note", "ledger-hygiene", "channel-refinement",
               # 2026-08-16, both on untried-action-completion, both the same genus as the six
               # above — they act on a bet that already exists and neither resolves it.
               # `mechanism-fix`  the lever's implementation changed pre-run (v3 builds `tried`
               #                  from EXECUTED actions, not REQUESTED); registration, game,
               #                  endpoint, MDE and criterion all unchanged.
               # `smoke-result`   a gated cheap pass run BEFORE the arms are allowed to spend.
               # Neither says `substrate`, so neither suppresses scoring — right in both cases:
               # a pre-run mechanism fix must not take a live bet off the curve, and a smoke
               # pass measures the INSTRUMENT (did the lever fire at all?), not the endpoint,
               # so it leaves the registered forecast standing to be scored on its own terms.
               # Worth noting what the smoke line bought, because the ledger now shows it: 12
               # minutes returned the mechanism after three full runs had returned nothing.
               "mechanism-fix", "smoke-result",
               # 2026-08-16 evening, arc's hygiene wave (they now stamp kind on every line):
               # `adversary-block`  pre-push kill by the adversary rider (memlens-nowipe) —
               #                    the bet's FATE travels on the paired pre-run relabel line,
               #                    which pair() reads; the status prose here stays unparsed.
               # `parked`           bet shelved to ride a future arm (memlens-rider); same
               #                    division of labour as adversary-block.
               # `channel-stamp`    pre-run amendment restoring a lapsed channel field —
               #                    arc adopting the 08-16 morning ask, same day.
               # `scoring-note`     meta note on scorability (ship-animfeedback: accepted
               #                    one-question-one-id-one-prior). Annotation, never a bet.
               # None says `substrate`, so none suppresses scoring — correct for all four.
               "adversary-block", "parked", "channel-stamp", "scoring-note",
               # 2026-08-17, semantics from arc's own ledger line (id kind-dialect-semantics,
               # commit e21349b) — asked-first per the 08-12 tripwire lesson:
               # `hidden-draw`  SCORED forecast about a MEASUREMENT quantity: the prior prices
               #                P(same-build hidden draw lands in the declared band). Never a
               #                lever bet — a below-band outcome scores the FORECAST wrong
               #                without killing any lever (§9.397 precedent: below-band means
               #                investigate the backend, not change adoptions). Scoring as an
               #                ordinary forecast is therefore correct; no substrate.
               # `eval`         SCORED forecast, prior prices P(PROCEED); the VOID-on-substrate
               #                carve-out travels on outcome words at resolution, same as
               #                kernel-ab. No substrate in the KIND.
               # `amendment`    annotation genus, generic parent — arc left the vocabulary
               #                economy to this layer; one parent beats minting a species per
               #                correction (the instance was a draw-COUNT fix). Same genus
               #                rule: it does not say substrate, so it never suppresses scoring.
               # `register-then-refuse`  the kind on an option-4 declined registration (prior
               #                + resolution "refused" on one line); the declined classing
               #                travels on the RESOLUTION word, declared 2026-08-12 — the kind
               #                is the protocol's label, not a class of its own.
               "hidden-draw", "eval", "amendment", "register-then-refuse",
               # 2026-08-18, semantics from arc's kind-dialect-semantics-2 (commit c1069e7),
               # asked-first again:
               # `decision`    NON-SCORED ANNOTATION recording an owner directive; never
               #               carries a prior, never resolves — citable provenance for later
               #               registrations (type specimen opus-trace-corpus-decision). No
               #               prior means pair() never sees the id; declaring only quiets
               #               the tripwire.
               # `resolution`  a TAG on resolution lines; the verdict rides the `result`
               #               word (cleared/failed/void) — generic-parent pattern, like
               #               amendment. Never a registration. Unlike every kind above,
               #               this one needs PLUMBING, not just declaration: the tagged
               #               line carries its verdict in a field no scanner read
               #               (lora-conv-v32b-opus-train sat in-flight with `result:
               #               cleared` on the ledger) — see result_field().
               "decision", "resolution",
               # 2026-08-20, tripwire's first TRUE new token since it was built (the 08-12
               # maiden hits were both false positives):
               # `ab`  a bare A/B lever draw (inertguard-draw1/draw2) — the same animal as the
               #       already-declared `kernel-ab`, minus the kernel qualifier. Real prior on
               #       a real lever, no `substrate`, so it scores as an ordinary forecast and
               #       declaring it moves NO count. Not asked-first: unlike hidden-draw/eval,
               #       nothing here is ambiguous enough to spend arc's attention on.
               "ab",
               # 2026-08-22: `desk` — arrived 08-20 and owned 08-21 (13 of that day's 18 lines,
               # a kind that did not exist 48h earlier). ZERO-GPU work: a measurement or
               # analysis run at the desk, resolving with `outcome: protocol` or `correction`.
               # Annotation genus, same rule as the 08-14 six — no `substrate`, so it suppresses
               # no scoring, and none of the 14 ids carries a prior, so declaring moves NO count.
               # Recorded because the census is the only place the shift is visible: the day
               # this kind took over is the day scored resolutions went to zero.
               "desk",
               # 2026-08-22: `withdrawn` — the kind arc stamps on a pre-GPU adversary kill that
               # states its prior (see OUTCOME_DECLARED["withdrawn-at-adversary"]). Distinct
               # from the already-declared `withdrawal`, which arc uses for a pre-launch
               # withdrawal pending re-registration (stage3-eval-r7). No `substrate`, so it
               # suppresses no scoring — correct: these lines carry a real prior, and where
               # they land is decided by the outcome word, not the kind.
               "withdrawn",
               # 2026-08-24: `correction` as a KIND (was only an outcome word, bookkeeping
               # class). First use corrects a same-id amendment (opt_steps=0, not ~8) —
               # annotation, no counts move.
               "correction",
               # 2026-08-24: `annotation` — arc's 15:10Z classification line (the one that SET
               # the substrate-scores rule) arrived on a kind the vocabulary had never seen.
               # Annotation genus: carries no prior, no verdict word; no `substrate`, so it
               # suppresses nothing.
               "annotation",
               # 2026-08-28: `submission` — the kind on a HIDDEN-RERUN submission draw
               # (q38-hidden-draw-1, prior 0.6, family 'hidden draw (9.137 instrument)').
               # Same animal as `hidden-draw`: a scored forecast about a measurement
               # quantity on the hidden set; a below-band outcome scores the FORECAST
               # wrong without killing any lever. It scored failed at 0.6 exactly as an
               # ordinary forecast should — no `substrate`, declaring moves NO count.
               "submission"}

# ── STATUS-ONLY TERMINALS (2026-08-14) ───────────────────────────────────────
# A third channel, found the hard way: sb26-animfeedback-draw1 was WITHDRAWN UNRUN with zero
# GPU spent, and the line carries neither `event` nor `outcome`/`resolution` — the disposition
# is in a bare `status`. Both the event tripwire (needs `event`) and the word tripwire (needs
# outcome/resolution) are blind to it BY CONSTRUCTION, so the bet read live forever and no
# alert fired. Deliberately NARROW: only declared heads classify, everything else returns None
# and the line stays invisible exactly as before. Censusing all of `status` was rejected —
# "PRE-RUN — zero GPU spent…", "STAGED", "NAMED-not-staged" are prose, and alerting on prose
# is what makes a tripwire get ignored.
STATUS_HEADS = {"WITHDRAWN": "withdrawn"}

def status_class(l):
    """Terminal disposition arriving on a bare `status` (no event, no outcome/resolution)."""
    if l.get("event") or l.get("outcome") or l.get("resolution"): return None
    s = str(l.get("status") or "").upper()
    for head, cls in STATUS_HEADS.items():
        if s.startswith(head): return cls
    return None

def kind_tokens(l):
    return {t for t in re.split(r"[+/,;\s]+", str(l.get("kind") or "").lower()) if t}

def is_substrate(l):
    return "substrate" in kind_tokens(l)

def result_field(l):
    """`result` as a verdict carrier, ONLY on kind=resolution lines (declared 2026-08-18,
    arc's kind-dialect-semantics-2: 'classing rides the `result` word'). Everywhere else
    `result` stays v2 prose, read solely under status=closed via the _HEADS whitelist —
    opening it on every line would let free text score."""
    return l.get("result") if "resolution" in kind_tokens(l) else None

def crit_of(pre):
    return pre.get("criterion") or pre.get("why") or ""

def classify(outcome, note):
    if outcome == "relabel": return "inside_noise"    # the relabel convention (2026-08-02) IS a
                                                      # re-grade to NULL-EQUIVALENT — by construction
    t = (note or "").replace("−", "-").replace("–", "-")
    if "NULL-EQUIVALENT" in t: return "inside_noise"  # audit's own token: sub-MDE by definition —
                                                      # checked BEFORE the decisive regex (spark #35:
                                                      # ksearch's KILL-leg prose read as decisive and
                                                      # broke a streak the program itself calls a wall)
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
        priors = [l for l in ls if prior_of(l) is not None]
        substrate = any(is_substrate(l) for l in ls)     # token-matched: compound kinds count
        terms = [l for l in ls if verdict_of(l) is not None
                 or (substrate and l.get("event") == "resolution"
                     and event_class(l) != "void")]   # measurement draw: any resolution is terminal
        # relabel-supersede mirror (calibration.py, spark #35): a later relabel line is the
        # LAST adjudication — its NULL-EQUIVALENT note is what the streak should read, not
        # the superseded terminal's prose.
        verdictish = [l for l in ls if l in terms or l.get("outcome") == "relabel"]
        if terms:
            resolved.append({"id": i, "pre": priors[0] if priors else {}, "res": verdictish[-1]})
        elif any(l.get("outcome") in ("void", "amended-before-running")
                 or (l.get("resolution") or "").lower().startswith("void")
                 or str(result_field(l) or "").lower().startswith("void")
                 or event_class(l) == "void" for l in ls):
            continue                                   # no information / superseded — out of every invariant
        elif any(is_declined(l) for l in ls):
            continue                                   # decided WITHOUT running: terminal, never
                                                       # scoreable, counted on its own DECLINED face
        elif any(status_class(l) == "withdrawn" for l in ls):
            continue                                   # WITHDRAWN UNRUN (2026-08-14): registered,
                                                       # never run, replaced by a redesign. Kept
                                                       # SEPARATE from declined on purpose — arc's
                                                       # line says "Not a verdict on the lever", so
                                                       # folding it into DECLINED would corrupt that
                                                       # face's question (were we right to WALK AWAY
                                                       # from bets we rated well?) with bets nobody
                                                       # walked away from.
        elif any(l.get("status") == "closed" or l.get("outcome") == "closed" for l in ls):
            continue                                   # closed without a whitelisted verdict — unscorable, out
        elif (rl := [k for k, l in enumerate(ls) if l.get("outcome") == "relabel"]) and \
             not any(prior_of(l) is not None for l in ls[rl[-1] + 1:]):
            continue                                   # PRE-RUN RELABEL (2026-08-16, memlens pair):
                                                       # every earlier relabel FOLLOWED a verdict and
                                                       # is handled by the supersede mirror above;
                                                       # this one closes a bet that never ran (arc:
                                                       # "closing and re-opening is the append-only
                                                       # ledger's only honest correction path"). NOT
                                                       # an attempt — nothing ran — so out of both
                                                       # sets, mirroring calibration's relabeled
                                                       # bucket. A registration line AFTER the last
                                                       # relabel REOPENS the id (arc's re-register
                                                       # path; their new convention stamps `ts` on
                                                       # re-registrations so the composite dedupe
                                                       # cannot eat a byte-identical line).
        elif priors:
            inflight.append({"id": i, "pre": priors[0]})
    return resolved, inflight

# ── family classification (FAMILY MIX, spark #45) ────────────────────────────
# Explicit `family` field wins. Retro rules are ordered, id-first with criterion
# fallback, written against the live ledger 2026-08-11; unmatched ids stay "?"
# VISIBLY (coverage is reported) rather than guessed into a bucket.
FAMILY_RULES = [
    (re.compile(r"untried|action7map|statearm|action-completion", re.I), "completion"),
    (re.compile(r"keyframe|animserve|cortex|animtrace", re.I),           "animation-serving"),
    (re.compile(r"colab-mtp|specdecode|ship-mtp", re.I),                 "substrate-serving"),
    (re.compile(r"\blora", re.I),                                        "training"),
    (re.compile(r"tfcal|corp-meter|scope-leak|aa-calib", re.I),          "instrument-calibration"),
    (re.compile(r"^ship-", re.I),                                        "ship"),
    (re.compile(r"verifier|objrepair", re.I),                            "verifier-repair"),
    (re.compile(r"punctalpha|prefixtape", re.I),                         "prompt-compression"),
    (re.compile(r"upscale", re.I),                                       "upscale"),
    (re.compile(r"pheromone|blackboard|ksearch|cotick|repeatnote|coactor|^k\d-|frontier-tool", re.I), "kernel-prompt"),
    (re.compile(r"allocator", re.I),                                     "allocator"),
    (re.compile(r"bestofk", re.I),                                       "sampling"),
    (re.compile(r"reaudit|surrogate-endpoint|score-law|hidden-sd", re.I), "desk-audit"),
    (re.compile(r"tr87|targetceiling|followup-conversion", re.I),        "game-diagnosis"),
    (re.compile(r"seed-determinism|harness-refit|hidden-replication|baseline-shift|seam-isolation|framework-seam", re.I), "harness-validity"),
]
LEVER_SUFFIX = re.compile(r"(-draw\d+|-pooled\d*|-stage[A-Za-z0-9]+|-tier\d+|-v\d+|-iter\d+.*|"
                          r"-rerun.*|-p\d+|-probe|-hidden|-2026-\d\d-\d\d)+$")
# Support families are validation/measurement SPEND, not idea bets: a validity probe that
# fails resolved exactly as priced is the instrument WORKING, so "0 positives" carries no
# concentration signal there. They stay in the shares (real spend) but never episode/ALERT.
SUPPORT_FAMILIES = {"ship", "desk-audit", "instrument-calibration", "harness-validity",
                    "game-diagnosis"}

def lever_of(pid):
    return LEVER_SUFFIX.sub("", pid)

def family_of(pid, pre):
    if pre.get("family"): return str(pre["family"])
    for rx, fam in FAMILY_RULES:          # id first — criteria cite OTHER probes
        if rx.search(pid): return fam     # (cortex's criterion names the verifier
    crit = crit_of(pre)[:200]             # comparator; id rules must exhaust first)
    for rx, fam in FAMILY_RULES:
        if rx.search(crit): return fam
    return "?"

# ── gate extraction for the power check ──────────────────────────────────────
NUM = re.compile(r"(-?\d+(?:\.\d+)?)")
def gate_of(pre, noise):
    if isinstance(pre.get("gate"), (int, float)):
        u = pre.get("unit") or (noise[0]["unit"] if noise else "")
        return abs(float(pre["gate"])), u, "explicit"
    crit = crit_of(pre).replace("−", "-")
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
    crit = crit_of(pre)
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
        if asof and (l.get("ts") or l.get("date") or "") > asof: continue
        lines.append(l)
    resolved, inflight = pair(lines)
    noise = load_noise()
    # ids (not just counts) are published so self_check.py can hold this layer against
    # calibration.py and against this layer's OWN alert text — see that script's header.
    alerts, out = [], {"asof": asof, "n_resolved": len(resolved), "n_inflight": len(inflight),
                       "inflight_ids": [r["id"] for r in inflight],
                       "resolved_ids": [r["id"] for r in resolved]}
    print(f"ledger: {LEDGER}" + (f"  (as of {asof})" if asof else ""))
    print(f"resolved {len(resolved)} · in-flight {len(inflight)}\n")
    if not resolved and not inflight:
        print("nothing to check."); return 0

    # ── PARK-STREAK ──
    pool = [r for r in resolved if on_class(r["pre"], noise)] if noise else resolved
    off_class = len(resolved) - len(pool)
    seq = [(r["id"], classify(verdict_of(r["res"]) or r["res"].get("outcome"), r["res"].get("note") or r["res"].get("result") or r["res"].get("observed")), r["res"].get("ts") or r["res"].get("date", "")) for r in pool]
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
        out["power"] = {"historical_weak": len(weak_hist), "unparsed": len(unparsed),
                        "predetermined": [{"id": i, "gate": g, "mde": m} for i, g, m in weak_hist],
                        "unparsed_ids": unparsed}

    # ── POWER-v2: SELF-STATED SE (spark #35 — needs no banked noise model) ──
    # A prereg that states its own arm SE has priced its noise; a bar below 2*SE makes
    # the verdict a coin toss BY DESIGN. Judged only when the SE carries a unit token the
    # bar can be matched on; unitless mentions are counted, not judged — visible blind spot.
    SE_RX = re.compile(r"SE\s*[~≈=]?\s*\+?/?-?\s*([0-9]+(?:\.[0-9]+)?)\s*(pp|/game)?", re.I)
    cfg_hist, cfg_unitless = [], []
    for bucket, rows in (("in-flight", inflight), ("resolved", resolved)):
        for r in rows:
            crit = crit_of(r["pre"]).replace("−", "-")
            m = SE_RX.search(crit)
            if not m: continue
            se, unit = float(m.group(1)), m.group(2)
            best = None
            if unit:
                for g in re.finditer(r"([0-9]+(?:\.[0-9]+)?)\s*" + re.escape(unit), crit):
                    if m.start() <= g.start() < m.end() + 2: continue   # the SE phrase itself
                    v = abs(float(g.group(1)))
                    if 0 < v < 100 and (best is None or v < best): best = v
            if best is None:
                cfg_unitless.append(r["id"]); continue
            if best < 2 * se:
                if bucket == "in-flight":
                    alerts.append(f"ALERT coin-flip-gate: in-flight '{r['id']}' bar {best}{unit} < 2*SE = {2*se:.1f}{unit} (self-stated) — unresolvable as designed; widen the bar or pool more draws before running")
                else:
                    cfg_hist.append((r["id"], best, se, unit))
    if cfg_hist or cfg_unitless:
        print(f"  POWER-v2 (self-stated SE): {len(cfg_hist)} historical coin-flip gates"
              + (f" ({', '.join(i for i, _, _, _ in cfg_hist[:5])}{'…' if len(cfg_hist) > 5 else ''})" if cfg_hist else "")
              + (f" · SE stated but bar unmatchable (unitless): {len(cfg_unitless)}" if cfg_unitless else ""))
    out["power_v2"] = {"coin_flip_hist": [{"id": i, "bar": b, "se": s, "unit": u} for i, b, s, u in cfg_hist],
                       "unitless": cfg_unitless}

    # ── CHANNEL STAMP ──
    # Denominator is EVERY prereg, not the paired ones. pair() drops voids and declines, so
    # under the old denominator a prereg that was stamped and THEN voided or was refused
    # vanished from numerator and denominator alike: on 2026-08-13 arc had stamped 5 of 5 new
    # preregs and this face reported 2/63 — it told them the adoption had not happened. A
    # compliance face that under-reports compliance is worse than no face; it teaches the
    # reader their effort went unseen. History can never be stamped, so overall coverage is
    # reported for context but only a LAPSE SINCE ADOPTION warns.
    preregs, seen_pre = [], set()
    for l in lines:
        pid = l.get("id")
        if pid is None or pid in seen_pre or prior_of(l) is None: continue
        seen_pre.add(pid); preregs.append(l)

    # Stamps arrive as append-only AMENDMENTS as often as prereg fields: arc's 2026-08-17
    # retro wave put `channel`/`family` on kind=channel-stamp lines, and this face — reading
    # only the prereg line — kept WARNing on ids that had already complied. Same lesson as
    # the denominator note above: a compliance face that cannot see append-only compliance
    # teaches the reader their effort went unseen. So stamps are per-ID, from ANY line;
    # FIRST value wins (a registration-time declaration beats a later retro stamp).
    id_stamps = {"channel": {}, "family": {}}
    for l in lines:
        pid = l.get("id")
        if pid is None: continue
        for f in ("channel", "family"):
            if l.get(f) and pid not in id_stamps[f]:
                id_stamps[f][pid] = (str(l.get("ts") or ""), str(l.get(f)))

    # FINAL disposition per id — computed ONCE here and used by every face below. The ledger is
    # append-only, so a later line supersedes an earlier one: shapeid-rot-rung (2026-08-12)
    # refuses, then AMENDS that refusal to void 80 minutes later. A per-line `any(is_declined)`
    # freezes it at the refusal and reports a decline that was withdrawn — which is what the
    # DECLINED face did on 08-13 while the family face, using this map, got it right. One map,
    # every face; a disposition computed twice is a disposition that will disagree with itself.
    # Reads BOTH dialects: word-form (outcome/resolution) and v3.1 event-form. A word-only map
    # would call every event-resolved prereg unresolved — 10 of them here — and the family
    # face would then read live families as stalled ones.
    _EV_CLS = {"cleared": "verdict", "failed": "verdict", "void": "void",
               "nonscored": "nonscored"}
    final_cls = {}
    for l in lines:
        pid = l.get("id")
        if pid is None: continue
        c = disposition(l)[1]
        if c == "NEW":
            c = _EV_CLS.get(event_class(l) or "", "NEW")
        if c == "NEW":
            c = status_class(l) or "NEW"    # third channel: bare-status terminals (WITHDRAWN)
        if c != "NEW": final_cls[pid] = c
    out["disposition"] = final_cls      # published so self_check can hold this view against
                                        # pair()'s: on 08-13 they disagreed about tr87-lens-
                                        # ceiling (cleared here, in-flight there) and nothing
                                        # noticed, because the two views were never compared.

    def stamp_face(field):
        """-> (n_stamped, missing_ids, since_ts, recent, recent_missing_ids)
        Reads id_stamps (any line of the id), not the prereg line. `since` = the earliest
        stamp ACT on a registered id — inline prereg ts or amendment ts, whichever wrote the
        first stamp — so a retro wave over old ids cannot drag adoption earlier than the
        practice actually began, and prereg recency stays registration-time."""
        sm   = id_stamps[field]
        st   = [l for l in preregs if l.get("id") in sm]
        miss = [l.get("id") for l in preregs if l.get("id") not in sm]
        since = min((sm[l.get("id")][0] for l in st), default="")
        recent = [l for l in preregs if since and str(l.get("ts") or "") >= since] if st else []
        rmiss  = [l.get("id") for l in recent if l.get("id") not in sm]
        return len(st), miss, since, recent, rmiss

    n_ch, ch_miss, ch_since, ch_recent, ch_rmiss = stamp_face("channel")
    print(f"\nCHANNEL STAMP  {n_ch}/{len(preregs)} preregs name their channel"
          + (f" · since adoption {ch_since[:10]}: {len(ch_recent) - len(ch_rmiss)}/{len(ch_recent)}"
             if n_ch else "")
          + (f" · missing (recent): {', '.join(i for i in ch_miss[-6:] if i)}" if ch_miss else ""))
    if ch_miss and os.environ.get("CHANNEL_STRICT"):
        alerts.append(f"ALERT channel: {len(ch_miss)} preregs carry no channel stamp under CHANNEL_STRICT")
    elif n_ch == 0:
        print("  WARN: unstamped levers can optimize a dead channel undetected — add `channel` (+`liveness`) at registration")
    elif ch_rmiss:
        print(f"  WARN: adoption lapsed — {len(ch_rmiss)} prereg(s) since {ch_since[:10]} carry no"
              f" `channel`: {', '.join(i for i in ch_rmiss if i)}")
    out["channel"] = {"stamped": n_ch, "total": len(preregs), "since": ch_since,
                      "recent": len(ch_recent), "recent_missing": ch_rmiss}

    # ── FAMILY MIX (spark #45): audit the CHOICE STREAM the ledger censors everything else by ──
    # Walk raw lines in file order (append-only ledger = chronological): preregs arrive,
    # resolutions accrue evidence. Voids stay in the stream — the choice was spent. A family
    # crossing >=FAMILY_K preregs / >=2 levers / 0 positives is a concentration episode; an
    # in-flight prereg still sitting in one ALERTs (close it or state the continue reason).
    fam_k = int(os.environ.get("FAMILY_K", 3))

    # "0 positives" hides three different worlds, and they carry OPPOSITE prescriptions.
    # Measured 2026-08-13: `completion` had 4 bets, 3 of them terminal-but-NON-SCORING and 1
    # live — zero scoreable results ever — while the face called it evidence-negative and
    # advised retiring it. Retiring is right when levers were tried and lost; it is wrong when
    # the instrument cannot produce a score (fix the instrument) and wrong again when nothing
    # has finished (close the bets). The episode still FIRES in all three cases — no signal is
    # dropped — but it now says which world it is.
    def fam_shape(st):
        if st["verdicts"]:  return "evidence-negative"   # tried, scored, never won
        if st["completed"]: return "no-scoreable-result" # ran to terminal, nothing scoreable
        return "unresolved"                              # nothing has finished at all
    # A DECLINE IS NOT EVIDENCE (2026-08-13). "re-entry-without-a-positive" means we went back
    # into a family and it gave us nothing. A prereg we registered and then REFUSED never ran,
    # so it produced no evidence for or against — counting it made "0 positives" trivially
    # true and inverted the prescription: an unexplored family got reported as an exhausted
    # one. Live on 08-13: `perception` fired the episode on 3 preregs of which 2 were refused
    # before running, raising two ALERTs on a family we had barely tried. This is the cost of
    # register-then-refuse landing in a face built before the class existed — the shares below
    # still count every prereg (that face audits the CHOICE stream, and a refusal IS a choice),
    # but the EPISODE now counts only attempts. Disposition is precomputed because the
    # chronological walk cannot know at registration time how a prereg will end (final_cls
    # is built once, above).
    seen_prereg, fam_stat, episodes, stream = set(), {}, [], []
    stamped_fam = 0
    for l in lines:
        pid = l.get("id")
        if pid is None: continue
        if prior_of(l) is not None and pid not in seen_prereg:
            seen_prereg.add(pid)
            # explicit family from ANY line of the id (retro stamps included) beats retro rules
            fam = (id_stamps["family"].get(pid) or (None, None))[1] or family_of(pid, l)
            if pid in id_stamps["family"]: stamped_fam += 1
            lev = lever_of(pid)
            st = fam_stat.setdefault(fam, {"preregs": 0, "levers": set(), "pos": 0,
                                           "flagged": False, "attempts": 0, "alevers": set(),
                                           "declined": 0, "verdicts": 0, "completed": 0})
            st["preregs"] += 1; st["levers"].add(lev)
            fc = final_cls.get(pid)
            if fc == "declined":
                st["declined"] += 1
            else:
                st["attempts"] += 1; st["alevers"].add(lev)
                if fc is not None:        st["completed"] += 1
                if fc == "verdict":       st["verdicts"] += 1
            new_fam = st["preregs"] == 1
            stream.append({"id": pid, "ts": l.get("ts") or l.get("date") or "", "family": fam,
                           "new_family": new_fam})
            if (fam != "?" and fam not in SUPPORT_FAMILIES and not st["flagged"]
                    and st["attempts"] >= fam_k and len(st["alevers"]) >= 2 and st["pos"] == 0):
                st["flagged"] = True
                episodes.append({"family": fam, "at": pid, "preregs": st["attempts"],
                                 "levers": len(st["alevers"]), "declined": st["declined"],
                                 "shape": fam_shape(st)})
        elif pid in seen_prereg:
            fam = next((s["family"] for s in stream if s["id"] == pid), None)
            if fam and verdict_of(l) == "cleared":
                fam_stat[fam]["pos"] += 1
    n_stream = len(stream)
    if n_stream:
        classified = [s for s in stream if s["family"] != "?"]
        cov = len(classified) / n_stream
        fams = {}
        for s in classified: fams[s["family"]] = fams.get(s["family"], 0) + 1
        top_fam, top_n = (max(fams.items(), key=lambda kv: kv[1]) if fams else ("-", 0))
        def share(rows):
            rows = [s for s in rows if s["family"] != "?"]
            return (sum(1 for s in rows if s["new_family"]) / len(rows)) if rows else 0.0
        pre_era  = [s for s in stream if (s["ts"][:10] or "9999") < "2026-08-07"]
        post_era = [s for s in stream if (s["ts"][:10]) >= "2026-08-07"]
        n_fm, fm_miss, fm_since, fm_recent, fm_rmiss = stamp_face("family")
        print(f"\nFAMILY MIX  {n_stream} preregs · coverage {cov:.0%} ({len(fams)} families"
              f" · top: {top_fam} {top_n/max(1,len(classified)):.0%})"
              f" · family stamps {stamped_fam}/{n_stream}"
              + (f" · since adoption {fm_since[:10]}: {len(fm_recent) - len(fm_rmiss)}/{len(fm_recent)}"
                 if n_fm else ""))
        print(f"  exploration (new-family share): overall {share(stream):.0%}"
              f" · pre-era {share(pre_era):.0%} · post-era {share(post_era):.0%}"
              f" · last-10 {share(stream[-10:]):.0%}")
        for e in episodes:
            later = fam_stat[e["family"]]["pos"] > 0
            e["later_cleared"] = later
            print(f"  re-entry-without-a-positive ({e['shape']}): {e['family']} crossed"
                  f" {e['preregs']} attempts/{e['levers']} levers/0 positives at '{e['at']}'"
                  + (f" ({e['declined']} refused before running, not counted)" if e.get("declined") else "")
                  + (" — family later cleared" if later else ""))
        if n_fm == 0:
            print("  WARN: no `family` stamps — retro classification only; add `family` at registration (protocol ask)")
        elif fm_rmiss:
            print(f"  WARN: adoption lapsed — {len(fm_rmiss)} prereg(s) since {fm_since[:10]} carry no"
                  f" `family`: {', '.join(i for i in fm_rmiss if i)}")
        # ── CONTINUE REASON / STOP RULE (2026-08-26, trip persistence same day) ── The alert
        # has always demanded "state the continue reason on the ledger" — and until today had
        # NO path to hear one: the check promised a second verdict it could not report (the
        # same class we audit arc's instruments for). Read rule, same head discipline as
        # STATUS_HEADS: a line for the id whose note BEGINS with the uppercase head
        # "CONTINUE REASON" states it; "STOP RULE" anywhere in that note states a falsifier.
        # Presence checks only — the face never parses the prose. Records are computed for ALL
        # continue-reason lines regardless of in-flight status, because the first cut emitted
        # the record only while the stating arm was in flight — so the stop rule VANISHED from
        # the JSON at the exact moment it tripped (self-live-persistence resolved failed and
        # family_mix_continue read None). A stop rule TRIPS when its stating id resolves with
        # any verdict other than cleared; the trip is a standing fact of the family, printed
        # every sweep, and any LATER in-flight arm in that family gets the sharpened alert —
        # clearable by the same CONTINUE REASON mechanism, whose text is on the author to make
        # answer the tripped rule (the layer cannot verify a "changed recipe class"; it can
        # make the commitment un-forgettable, which is all it ever does).
        _res_by_id = {r["id"]: r for r in resolved}
        continue_recs = []
        for l in lines:
            # 2026-08-29: hear the head in `why` too, not only `note`. The v3 prereg dialect
            # carries a registration's rationale in `why`, and opsdv2-live-rider answered the
            # tripped behavioural-rider rule there — the alert kept demanding a CONTINUE
            # REASON that was already on the ledger. Same class as the 08-26 FAMILY MIX fix
            # (an alert promising a verdict it had no path to hear), one field over.
            crtxt = next((str(l.get(f)) for f in ("note", "why")
                          if str(l.get(f, "")).startswith("CONTINUE REASON")), None)
            if crtxt is None: continue
            cid = l.get("id")
            cfam = next((s["family"] for s in stream if s["id"] == cid), "?")
            has_stop = "STOP RULE" in crtxt
            rec = {"id": cid, "family": cfam, "ts": l.get("ts"),
                   "stop_rule_stated": has_stop, "tripped": False}
            r = _res_by_id.get(cid)
            if r is not None:
                rec["resolved"] = verdict_of(r["res"])
                rec["tripped"] = bool(has_stop and rec["resolved"]
                                      and rec["resolved"] != "cleared")
            continue_recs.append(rec)
        out["family_mix_continue"] = continue_recs
        tripped_fams = {c["family"] for c in continue_recs
                        if c["tripped"] and c["family"] != "?"}
        out["family_mix_stop_ruled"] = sorted(tripped_fams)
        for tf in sorted(tripped_fams):
            trip = next(c for c in continue_recs if c["family"] == tf and c["tripped"])
            print(f"  STOP RULE TRIPPED: family '{tf}' — '{trip['id']}' stated a stop rule and"
                  f" resolved {trip['resolved']}; any further in-flight arm here alerts until"
                  f" its own continue-reason answers the rule")
        for s in stream:
            fam = s["family"]
            if fam == "?" or not fam_stat[fam]["flagged"]: continue
            # `flagged` is sticky by design (the episode is a historical fact), but the ALERT is
            # a claim about NOW. A family that has since produced a positive is no longer a
            # family with no evidence of working, and the whole rationale — "close it or justify
            # continuing" — evaporates. On 2026-08-13 perception cleared tr87-lens-ceiling and
            # this still told arc their next arm sat in an evidence-negative family. The count
            # was a LITERAL "0 positives" in the string, which is why it could go stale at all.
            if fam_stat[fam]["pos"] > 0: continue
            if any(r["id"] == s["id"] for r in inflight):
                creason = next((c for c in continue_recs if c["id"] == s["id"]), None)
                if creason:
                    st = fam_stat[fam]
                    print(f"  continue-reason stated: '{s['id']}' rides in 0-positive family"
                          f" '{fam}' ({st['attempts']} attempts) justified on-ledger"
                          f" {str(creason.get('ts') or '')[:10]}"
                          + (" · stop rule stated" if creason["stop_rule_stated"]
                             else " · NO stop rule")
                          + (" · AFTER a tripped stop rule — the reason must answer it"
                             if fam in tripped_fams else ""))
                    continue
                if fam in tripped_fams:
                    trip = next(c for c in continue_recs if c["family"] == fam and c["tripped"])
                    alerts.append(
                        f"ALERT stop-rule: '{s['id']}' is in flight in family '{fam}' whose"
                        f" stop rule TRIPPED ('{trip['id']}' resolved {trip['resolved']} after"
                        f" committing to no further arm without a changed recipe class) — close"
                        f" it, or state the CONTINUE REASON that answers the tripped rule")
                    continue
                st, shape = fam_stat[fam], fam_shape(fam_stat[fam])
                head = (f"ALERT family-mix: in-flight '{s['id']}' sits in family '{fam}' with"
                        f" {st['attempts']} attempts/{len(st['alevers'])} levers/{st['pos']} positives")
                if shape == "evidence-negative":
                    tail = (" — a live bet in an evidence-negative family: close it or state the"
                            " continue reason on the ledger")
                elif shape == "no-scoreable-result":
                    live = st["attempts"] - st["completed"]
                    tail = (f" — all {st['completed']} completed run(s) came back NON-SCOREABLE"
                            + (f" and {live} {'is' if live == 1 else 'are'} still in flight" if live else "")
                            + ", so nothing here has ever tested a lever: the instrument is what has"
                            " failed, not the idea. Fix the measurement or state why this bet will score")
                else:
                    tail = (f" — none of the {st['attempts']} bets in this family has EVER resolved:"
                            " this is a stall, not an exhausted idea. Close them or state the continue reason")
                alerts.append(head + tail)
        out["family_mix"] = {"n": n_stream, "coverage": round(cov, 2), "families": fams,
                             "top": top_fam, "stamps": stamped_fam,
                             "exploration_share": {"overall": round(share(stream), 3),
                                                   "pre": round(share(pre_era), 3),
                                                   "post": round(share(post_era), 3),
                                                   "last10": round(share(stream[-10:]), 3)},
                             "episodes": episodes,
                             "unclassified": [s["id"] for s in stream if s["family"] == "?"]}

    # ── EVENT-DIALECT TRIPWIRE (v3.1 ABSORBED 2026-08-11; the alert now guards the NEXT drift) ──
    # event:"resolution" is the verdict channel and event_class maps its status heads;
    # kind=substrate preregs never scored before 2026-08-24 (priced substrate resolutions score since arc's 15:10Z rule); other event types are bookkeeping. A resolution
    # status no rule maps is the moment the dialect has drifted again — a scoreable
    # terminal the parsers cannot see would silently stick calibration n and starve the
    # #34/#41 wake greps. ALERT and extend event_class in BOTH parsers before trusting n.
    subst_ids = {l.get("id") for l in lines if is_substrate(l)}
    ev_types, ev_classes, ev_unknown = {}, {}, []
    for l in lines:
        ev = l.get("event")
        if not ev: continue
        ev_types[ev] = ev_types.get(ev, 0) + 1
        if ev != "resolution": continue
        ec = event_class(l)
        if ec == "unknown" and l.get("id") in subst_ids: ec = "nonscored-kind"
        ev_classes[ec] = ev_classes.get(ec, 0) + 1
        if ec == "unknown":
            ev_unknown.append((l.get("id") or "?", l.get("status") or ""))
    if ev_types:
        classes = " ".join(f"{k}:{v}" for k, v in sorted(ev_classes.items()))
        others = " ".join(f"{k}:{v}" for k, v in sorted(ev_types.items()) if k != "resolution")
        print(f"\nEVENT DIALECT  {ev_types.get('resolution', 0)} resolutions ({classes})"
              + (f" · other events: {others}" if others else "")
              + (f" · UNKNOWN STATUS: {len(ev_unknown)}" if ev_unknown else " · all mapped"))
    # The consequence clause is COMPUTED, not asserted (2026-08-30). It used to state
    # flatly that "the id reads in-flight, calibration n sticks" — true when written, and
    # made false the same hour by the unknown-head fallthrough fix, which lets a declared
    # `outcome` on the same line carry the verdict. An alert whose stated consequence has
    # stopped happening trains the reader to discount it; the "0 positives" literal in the
    # FAMILY MIX alert went stale exactly this way. So ask the reader we actually run.
    for i, s in ev_unknown:
        rescued = verdict_of(next(l for l in lines if l.get("id") == i
                                  and (l.get("status") or "") == s))
        alerts.append(
            f"ALERT event-dialect: '{i}' resolved event-style with status '{s}' — no head "
            f"rule maps it (FAILED*/CLEARED*/VOID*/GRAY*/SUBSTRATE-*/*PREPUSH*; kind="
            f"substrate non-scored only pre-2026-08-24). "
            + (f"A declared verdict word on the same line carries it ({rescued}), so the id "
               f"still resolves and n is intact — the DIALECT is the gap, not the count: "
               f"extend event_class (both parsers) or have the ledger restate the head."
               if rescued else
               f"Nothing else on the line carries a verdict, so the id reads IN-FLIGHT and "
               f"calibration n sticks; the #34/#41 wake patterns may miss it. Extend "
               f"event_class in calibration.py + ledger_invariants.py and re-check the wake "
               f"patterns before trusting n."))
    out["event_dialect"] = {"n": ev_types.get("resolution", 0), "classes": ev_classes,
                            "types": ev_types, "unknown": [i for i, _ in ev_unknown]}

    # ── OUTCOME-DIALECT TRIPWIRE (built 2026-08-12) ──
    # Verdicts also arrive as plain `outcome`/`resolution` words, and the v3.1 event
    # tripwire watches `event:` lines only — so word-form drift was unalerted by
    # construction. Fires on UNDECLARED vocabulary (see OUTCOME_DECLARED), reporting for
    # each new word whether the ledger has any handled disposition for that id, which is
    # what separates "a bet we can no longer score" from "a note on the meta channel".
    prior_ids = {l.get("id") for l in lines if prior_of(l) is not None}
    handled   = {l.get("id") for l in lines
                 if verdict_of(l) is not None or event_class(l) == "void"
                 or outcome_class(outcome_word(l)) in ("void", "adjudication", "unscorable")}
    w_cls, w_new, n_reason = {}, {}, 0
    for l in lines:
        w, cls = disposition(l)
        if not w: continue
        if has_reason(l): n_reason += 1     # verdict+reason line: the reason is prose, not vocabulary
        head = w.split()[0][:34]
        w_cls.setdefault(cls, {}); w_cls[cls][head] = w_cls[cls].get(head, 0) + 1
        if cls == "NEW": w_new.setdefault(head, []).append(l.get("id"))
    if w_cls:
        order = ["verdict", "void", "adjudication", "unscorable", "bookkeeping",
                 "in-progress", "annotation", "NEW"]
        parts = [f"{c}[{' '.join(f'{k}:{v}' for k, v in sorted(w_cls[c].items(), key=lambda kv: -kv[1]))}]"
                 for c in order if c in w_cls]
        print(f"\nOUTCOME DIALECT  {sum(sum(d.values()) for d in w_cls.values())} words · "
              + " ".join(parts)
              + (f" · {n_reason} verdict+reason" if n_reason else "")
              + ("" if w_new else " · all declared"))
    # The tail VERIFIES the id's disposition instead of inferring it. The first cut of this
    # tripwire inferred, and shipped two false positives; the second inferred one level in —
    # it fixed the trigger but left "it reads in-flight" asserted in the tail, which on
    # 2026-08-13 was false for 2 of 3 alerts. Membership of `inflight` is knowable here, so
    # check it. An id that another line already disposed of is a census gap, not a stuck bet.
    for k, ids in sorted(w_new.items()):
        who   = sorted(set(i for i in ids if i))
        stuck = [i for i in who if any(r["id"] == i for r in inflight)]
        reg   = [i for i in who if i in prior_ids]
        if stuck:
            tail = (f"sits on prereg(s) {', '.join(stuck)} that READ IN-FLIGHT because no field on"
                    " the line is readable — the bet is stuck and calibration n sticks with it")
        elif reg:
            tail = (f"sits on registered prereg(s) {', '.join(reg)} that a later line already"
                    " disposed of — nothing is stuck; the census just cannot name this outcome")
        else:
            tail = (f"appears only on id(s) {', '.join(who)} that never registered a prior"
                    " — a programme DECISION with no home in the audit layer (it scores nothing and is counted nowhere)")
        alerts.append(f"ALERT outcome-dialect: '{k}' is undeclared vocabulary and {tail}. Declare it in OUTCOME_DECLARED (both parsers) with the class it should carry, or have the ledger restate the line with a declared word")

    # ── UNPRICED-ONLY VOCABULARY (2026-08-30, kind-dialect-semantics-4) ──
    # Some declared words are legal only on an entry carrying NO prior, because their whole
    # point is that no forecast was graded. `confirmed` is the first: it means the fact was
    # established, not that a bet landed. Left untested, that legality condition would decay
    # into prose — and the decay is silent and one-directional, because the tempting misuse
    # (stamping `confirmed` on a priced arm whose result came in good) reads as a pass while
    # scoring nothing. This is the same shape as the post-hoc prior the ts tripwire guards.
    UNPRICED_ONLY = {"confirmed"}
    illegal = []
    for pid in dict.fromkeys(l.get("id") for l in lines if l.get("id")):
        ls = [l for l in lines if l.get("id") == pid]
        if not any(prior_of(l) is not None for l in ls): continue
        for l in ls:
            for w in (l.get("outcome"), l.get("resolution"), result_field(l)):
                head = str(w or "").lower().split()[0].strip(".,;:—-*") if w else ""
                if head in UNPRICED_ONLY:
                    illegal.append({"id": pid, "word": head}); break
    out["unpriced_only_violations"] = illegal
    if illegal:
        named = ", ".join(f"{r['id']} ('{r['word']}')" for r in illegal)
        alerts.append(
            f"ALERT vocabulary-legality: {named} — this word is declared legal ONLY on an "
            f"entry with NO prior (kind-dialect-semantics-4: it means a fact was ESTABLISHED, "
            f"not that a forecast landed), but the id carries one. A priced entry must "
            f"resolve cleared/failed/void; both parsers currently file this terminal-but-"
            f"UNSCORED, so the prior silently escapes the curve rather than being graded. "
            f"Restate the resolution with a verdict word — never leave a priced bet resolved "
            f"in unpriced vocabulary")
    out["outcome_dialect"] = {"classes": {c: sum(d.values()) for c, d in w_cls.items()},
                              "words": {c: d for c, d in w_cls.items()},
                              "new": {k: sorted(set(v)) for k, v in w_new.items()}}

    # ── DECLINED (option 4, 2026-08-12) ──
    # A decline never scores (the run never happened — no ground truth), but the PRIOR is
    # the whole audit. Comparing priors-on-declined against priors-on-run answers the
    # question the ledger could not previously ask: are we systematically walking away
    # from bets we rated well, or correctly killing the ones we rated badly? A decline
    # with no prior is uncountable in that comparison, so it raises the protocol ask.
    # final_cls, not per-line is_declined: a refusal that a later line AMENDS away is not a
    # decline, and listing it here would both overstate the count and drag the mean prior.
    dec_ids = []
    for l in lines:
        pid = l.get("id")
        if final_cls.get(pid) == "declined" and pid not in dec_ids:
            dec_ids.append(pid or "?")
    if dec_ids:
        dec_p = {}
        for i in dec_ids:
            pr = [prior_of(l) for l in lines if l.get("id") == i and prior_of(l) is not None]
            dec_p[i] = pr[0] if pr else None
        named = ", ".join(f"{i} (p={dec_p[i]})" if dec_p[i] is not None else f"{i} (NO PRIOR)"
                          for i in dec_ids)
        print(f"\nDECLINED  {len(dec_ids)} decided without running · {named}")

        # KILL REASON (2026-08-22) — arc's adaptation, offered unprompted in reply to the brief
        # and adopted the same evening. Their caveat, which is the reason this exists: all four
        # of the 08-21 adversary kills were stopped on PREMISE or DESIGN faults, never on
        # cost-benefit judgement. In arc's words, "these are not four good bets I walked away
        # from; they are four prices I put on broken designs." The conditional those priors
        # forecast — P(clears | the arm runs AS SPECIFIED) — never obtained, because the arm as
        # specified was incoherent. That is MORE informative, not less, but it measures DESIGN
        # QUALITY, and this face's question is BET SELECTION. Pooling them makes the headline
        # mean answer neither question, which is the failure this whole layer exists to catch.
        # Read per-id from ANY line, first-wins: the 08-17 stamp lesson — append-only compliance
        # arrives as a later amendment far more often than on the registration line.
        KILL_REASONS = {"premise": "design", "power": "design",
                        "already-answered": "design", "cost": "judgement"}
        kr = {}
        for i in dec_ids:
            v = [str(l.get("kill_reason")).strip().lower() for l in lines
                 if l.get("id") == i and l.get("kill_reason")]
            if v: kr[i] = v[0]
        bad_kr = sorted({v for v in kr.values() if v not in KILL_REASONS})
        if bad_kr:
            alerts.append(f"ALERT kill-reason-dialect: {', '.join(bad_kr)} is not declared "
                          f"vocabulary (premise/power/already-answered/cost) — the DECLINED split "
                          f"cannot place it, so it falls in with the unstamped. Declare it or "
                          f"restate the line")

        withp = [p for p in dec_p.values() if p is not None]
        ranp  = [float(prior_of(r["pre"])) for r in resolved if prior_of(r.get("pre") or {}) is not None]
        if withp and ranp:
            print(f"  mean prior — declined {sum(withp)/len(withp):.2f} vs run {sum(ranp)/len(ranp):.2f}"
                  f" (n {len(withp)}/{len(ranp)}): declining ABOVE the run mean is the shape worth explaining")
            grp = {"judgement": [], "design": [], "unstamped": []}
            for i in dec_ids:
                if dec_p[i] is None: continue
                grp[KILL_REASONS.get(kr.get(i, ""), "unstamped")].append(float(dec_p[i]))
            if grp["judgement"] or grp["design"]:
                parts = [f"{g} {sum(v)/len(v):.2f} (n {len(v)})"
                         for g, v in grp.items() if v]
                print(f"    split by kill_reason — {' · '.join(parts)}")
                print(f"    only the JUDGEMENT arm answers 'were we right to walk away from bets we"
                      f" rated well?'; DESIGN kills price an arm that could not have run as specified")
            # THE EMPTY ARM (2026-08-22). The first thing the split reported, on the evening it
            # was built, was that its own headline question has never been sampled: every stamped
            # decline is a design/premise/power kill, none is `cost`. Arc said it first, in the
            # message carrying the stamps — "none of the four is cost; I have not yet declined
            # anything on judgement, which is itself the finding your split now makes visible."
            # That matters more than the mean. This face has printed a number since 08-12 under a
            # caption implying it answers 'were we right to walk away from bets we rated well?',
            # and the arm that would answer it is empty. A statistic standing in for a question it
            # has never sampled is the exact illusion this whole layer exists to catch, so the
            # face now says so instead of leaving the caption to imply otherwise.
            if grp["design"] and not grp["judgement"]:
                print(f"    JUDGEMENT ARM EMPTY (n=0): no decline on record was made on"
                      f" cost-benefit — every stamped one is an arm that could not have run as"
                      f" specified. The mean above measures DESIGN QUALITY; the question this"
                      f" face was built to ask has not been sampled yet")
            if grp["unstamped"]:
                print(f"  CAVEAT: {len(grp['unstamped'])}/{len(withp)} priced declines carry no"
                      f" `kill_reason`, so the mean above POOLS bets declined on judgement with arms"
                      f" killed as incoherent — two different questions. Stamp"
                      f" premise/power/already-answered/cost (any later line; read per-id, first-wins)"
                      f" and this caveat clears itself")
        miss = [i for i in dec_ids if dec_p[i] is None]
        if miss:
            print(f"  WARN: no prior on {', '.join(miss)} — per the register-then-refuse protocol,"
                  f" register the prereg with the prior you intended and THEN refuse; without it the"
                  f" decline is counted but 'were we right to decline?' stays unanswerable")
        out["declined"] = {"ids": dec_ids, "priors": dec_p,
                           "mean_prior": round(sum(withp)/len(withp), 3) if withp else None,
                           "no_prior": miss, "kill_reason": kr,
                           "unstamped_kill_reason": [i for i in dec_ids
                                                     if dec_p[i] is not None and i not in kr]}

    # ── UNPRICED WALK-AWAY (2026-08-22) ──
    # The DECLINED face above can only see refusals that CLASSIFY as declined. On 08-21 arc
    # killed four arms before any GPU — v5-throughput-smoke at the precedent gate, then
    # thinkbank-calibration / v5-live-persistence / lora-conv-l1-train, their own eleventh
    # through fourteenth — and not one landed where that face could reach it. Three arrived as
    # {"outcome": "void", "result": "withdrawn"}: void wins the classification, and void means
    # COULD NOT MEASURE, not CHOSE NOT TO SPEND. The fourth arrived as a bare `protocol`
    # annotation. None of the four ever carried a prior, so pair() drops them at the no-prior
    # guard and calibration never sees them — classed, counted on no face, and invisible to the
    # single question they are evidence for.
    #
    # This face deliberately does NOT re-classify: arc's words keep meaning what arc wrote.
    # It raises the missing ASK. A walk-away with no prior is uncountable, and the protocol
    # that fixes it — register-then-refuse, adopted 2026-08-17 — already exists and is already
    # in use elsewhere in this ledger. Corroboration that the gap is felt on both sides: the
    # same wave's `outcome-learnability-probe` carries "prior": null, the slot opened and left
    # empty.
    #
    # Base rate measured BEFORE building: 5 such ids out of 159, four of them from one day —
    # narrow enough that the alert stays credible instead of becoming wallpaper. Vocabulary is
    # a CLOSED set matched on word prefix and on the FIRST TOKEN of `status`; prose is never
    # scanned, per the tripwire lesson above. Ids whose disposition rides the event channel are
    # skipped (untried-draw1, KILLED-BY-ADVERSARY-PREPUSH): those are already read and counted,
    # and this face is for the ones no channel reaches.
    WALKAWAY_WORDS = ("withdrawn", "refused", "declined", "killed")
    RTR_ADOPTED = "2026-08-17"     # register-then-refuse. History can never be re-registered,
                                   # so older ids print as context and only a LAPSE SINCE
                                   # ADOPTION alerts — same contract as CHANNEL STAMP.

    def _walk_word(l):
        for w in (result_field(l), l.get("result"), l.get("outcome"), l.get("resolution")):
            lw = str(w or "").lower()
            if lw.startswith(WALKAWAY_WORDS): return lw.split()[0]
        head = (str(l.get("status") or "").split() or [""])[0].lower().strip(".,;:—-*")
        return head if head.startswith(WALKAWAY_WORDS) else None

    unpriced = []
    for pid in dict.fromkeys(l.get("id") for l in lines if l.get("id")):
        if pid in dec_ids: continue                       # already named by the DECLINED face
        ls = [l for l in lines if l.get("id") == pid]
        if any(prior_of(l) is not None for l in ls): continue      # priced -> countable already
        hits = [(l.get("ts") or "", l) for l in ls if _walk_word(l)]
        if not hits: continue
        if any(event_class(l) is not None for _, l in hits): continue
        ts, l0 = sorted(hits, key=lambda h: h[0])[0]
        unpriced.append({"id": pid, "ts": ts[:10], "word": _walk_word(l0),
                         "classed_as": final_cls.get(pid) or "nothing"})
    if unpriced:
        unpriced.sort(key=lambda r: (r["ts"], r["id"]))
        named = ", ".join(f"{r['id']} ({r['word']} -> counted as {r['classed_as']})"
                          for r in unpriced)
        print(f"\nUNPRICED WALK-AWAY  {len(unpriced)} walked away from with no prior ever · {named}")
        fresh = [r for r in unpriced if r["ts"] >= RTR_ADOPTED]
        out["unpriced_walkaway"] = {"ids": [r["id"] for r in unpriced],
                                    "since_adoption": [r["id"] for r in fresh]}
        if fresh:
            classes = "/".join(sorted({r["classed_as"] for r in fresh}))
            alerts.append(
                f"ALERT unpriced-walk-away: {len(fresh)} id(s) killed or withdrawn without ever "
                f"registering a prior, since register-then-refuse was adopted {RTR_ADOPTED} "
                f"({', '.join(r['id'] for r in fresh)}) — each one IS classed ({classes}), but a "
                f"class is not a price: it counts on no face, and the DECLINED question 'were we "
                f"right to walk away from bets we rated well?' cannot reach it. Register the "
                f"prereg with the prior you intended and THEN refuse")

    # ── UNPRICED MEASUREMENT DRAW (2026-08-29, ship38p1-hidden-draw) ──
    # The `submission` absorption (2026-08-28, q38-hidden-draw-1) classed measurement draws as
    # SCORED FORECASTS about a hidden quantity — q38 registered 0.6 before its draw and scored
    # failed like any forecast. A draw with NO prior anywhere breaks that genus: it counts on
    # no face, and a pre-stated band frame, however honest, cannot enter the Brier curve.
    # Pricing after the fact is outcome-contaminated (arc's own 08-24 peek prohibition), so a
    # tripped specimen is unscoreable forever; the alert exists for the NEXT draw.
    # An id NAMED in a kind-dialect-semantics line is an ACKNOWLEDGED specimen: the
    # declaration vehicle (arc's ask-first channel — e21349b, c1069e7, dialect-3 7c64878)
    # has ruled on it, so it prints as a standing fact; the ALERT form is reserved for
    # specimens the dialect has not seen. Presence check only (id string in the note),
    # the same discipline as the head reads.
    _dialect_notes = " ".join(str(l.get("note", "")) for l in lines
                              if str(l.get("id", "")).startswith("kind-dialect-semantics"))
    DRAW_KINDS = {"submission", "hidden-draw"}
    updraws = []
    for pid in dict.fromkeys(l.get("id") for l in lines if l.get("id")):
        if pid in dec_ids: continue
        ls = [l for l in lines if l.get("id") == pid]
        if not any(kind_tokens(l) & DRAW_KINDS for l in ls): continue
        if any(prior_of(l) is not None for l in ls): continue
        updraws.append(pid)
    out["unpriced_measurement_draws"] = updraws
    if updraws:
        _acked = [i for i in updraws if i in _dialect_notes]
        _fresh = [i for i in updraws if i not in _dialect_notes]
        if _acked:
            print(f"\nUNPRICED DRAW  acknowledged unscoreable (dialect-3: draws are priced"
                  f" BEFORE the submit click; no retro-prior): {', '.join(_acked)}")
        if _fresh:
            alerts.append(
                f"ALERT unpriced-draw: {', '.join(_fresh)} — measurement draw(s) (kind "
                f"submission/hidden-draw) with no prior ever registered, AFTER dialect-3 "
                f"declared the standing rule (every *-hidden-draw registers prior + band "
                f"before the submit click; 'if an outcome will arrive as a number we will "
                f"cite, it gets a prior first'). Unscoreable forever — pricing now would be "
                f"outcome-contaminated. Acknowledge on a kind-dialect-semantics line, and "
                f"price the next one first")

    # ── TS-DISORDER TRIPWIRE (2026-08-29, qwen38-swap) ──
    # `ts` is NOT a reliable arrival clock: qwen38-swap's registration entered git 2026-08-26
    # (blame 8b75576c, three lines BEFORE its resolution) yet is stamped 2026-08-29T11:30Z —
    # read by ts it is a post-hoc prior on a known outcome; read by file order it is an
    # ordinary honest bet. FILE ORDER is the append-only ledger's only honest clock; ts is
    # advisory. But ts is load-bearing in one place — the substrate-scores-since 2026-08-24
    # resolution-date gate — so a disordered stamp must become visible, never trusted.
    # Presence check only, first trip per id: a line whose ts precedes a ts already seen on
    # the same id.
    # DAY granularity on purpose: same-day time-of-day wobble is batching, and date-only
    # stamps ("2026-08-09") would false-positive against full timestamps under a raw string
    # compare. The load-bearing consumer (the substrate gate) is a day boundary too.
    ts_disorder, _ts_seen = [], {}
    for l in lines:
        pid, ts = l.get("id"), str(l.get("ts") or l.get("date") or "")[:10]
        if not pid or len(ts) < 10: continue
        prev = _ts_seen.get(pid)
        if prev and ts < prev and pid not in {r["id"] for r in ts_disorder}:
            ts_disorder.append({"id": pid, "ts": ts, "after": prev})
        _ts_seen[pid] = ts if prev is None or ts > prev else prev
    out["ts_disorder"] = ts_disorder
    if ts_disorder:
        # dialect-3 (7c64878) declared the semantics this tripwire asked for: ts is a
        # HAND-STAMPED NOMINAL event time — a display label with a proven day-typo class.
        # Authority order: (a) file append order, (b) git-blame arrival, (c) ts as label
        # only; time-keyed gates resolve boundary cases by git-blame arrival, and a
        # registration is valid iff it ARRIVES before its arm's results are known. The
        # check now runs AS the declaration's check: named specimens stand, new ones alert.
        _acked = [r for r in ts_disorder if r["id"] in _dialect_notes]
        _fresh = [r for r in ts_disorder if r["id"] not in _dialect_notes]
        if _acked:
            print(f"TS-DISORDER  acknowledged day-typos (dialect-3: ts is a nominal label;"
                  f" file order, then git blame, is the clock): "
                  + ", ".join(f"{r['id']} ({r['ts']} vs {r['after']})" for r in _acked))
        if _fresh:
            named = ", ".join(f"{r['id']} ({r['ts']} after {r['after']})" for r in _fresh)
            alerts.append(
                f"ALERT ts-disorder: {len(_fresh)} id(s) carry a line whose `ts` DAY precedes "
                f"a day already stamped on the same id ({named}). dialect-3 declares ts a "
                f"hand-stamped nominal label with a known day-typo class — so this is a "
                f"probable NEW typo. It matters only where time is load-bearing (the "
                f"substrate-scores-since 2026-08-24 gate): boundary cases resolve by "
                f"git-blame arrival, never ts. Acknowledge it on a kind-dialect-semantics "
                f"line (id named) and it becomes a standing fact")

    # ── INSTRUMENT (2026-08-23) ──
    # Asked 08-22 (the ledger records decision + prior but never WHICH INSTRUMENT certified the
    # decision, so a retracted instrument had no path back to the decisions resting on it);
    # arc adopted it the same night, on the registration line, unprompted. Their shape is NOT a
    # bare name: a `;`-separated list of paths, each with an optional parenthetical VERDICT —
    #   "duck/invariants.py (insufficient — reads no prompt content); duck/layers_regression.py (new, all 12 layers)"
    # and in the first three stamps the instrument minted to close the case was indicted twice
    # in five hours (new -> UNSOUND -> VACUOUS). So, unlike kill_reason, the read is LATEST-WINS
    # per instrument: a later verdict supersedes. Per-id, any line (amendments carry `id`).
    # The face answers one question: which decisions cited an instrument AS SOUND that a later
    # line retracted? Self-indicting citations ("X (UNSOUND ...)") are the decision KNOWING, and
    # never alert. Closed verdict vocabulary; anything else is printed verbatim as unclassified
    # and left alone — declared vocabulary drives alerting, never per-id disposition.
    INSTR_BAD = ("unsound", "vacuous", "retired", "insufficient", "retracted", "broken",
                 "wrong-unit", "cannot-fail")

    def _instruments(l):
        raw = l.get("instrument")
        if not raw: return []
        if isinstance(raw, list): parts = [str(x) for x in raw]
        else:
            # Split on `;` at paren depth 0 ONLY. Arc's 08-23 amendment carried
            # "(... 14/14 clean-and-fire; re-run on this arm's own corpus ...)" and a flat
            # split dropped the whole repaired-instrument stamp without a sound.
            parts, buf, depth = [], "", 0
            for ch in str(raw):
                if ch == "(": depth += 1
                elif ch == ")": depth = max(0, depth - 1)
                if ch == ";" and depth == 0: parts.append(buf); buf = ""
                else: buf += ch
            parts.append(buf)
            parts = [x for x in parts if x.strip()]
        outp = []
        for x in parts:
            # 2026-08-24: names are FREE TEXT, not paths. The guard's first live firing (one
            # day after it was built) caught "k11 first-run log (gates PASS, training OOM)",
            # "stage_v5_live serving stack (proven)", "[trace] memory instrument" — all dropped
            # by a space-free-token rule. Name = everything before the FINAL parenthetical,
            # trimmed; every previously-parsing stamp reads identically.
            m = re.match(r"\s*(.+?)\s*(?:\(([^()]*(?:\([^()]*\)[^()]*)*)\))?\s*$", x.strip())
            if not m or not m.group(1): continue
            path, verdict = m.group(1).strip(), (m.group(2) or "").strip()
            # A name that OPENS a parenthetical it never closes is a malformed stamp, not an
            # instrument — without this the widened regex would swallow it silently and the
            # unparsed guard (built for exactly that silence) would never fire again.
            if path.count("(") != path.count(")"): continue
            # Bad word ANYWHERE in the verdict, not the head: arc's third stamp reads
            # "result-coherence VACUOUS after the layer-16 fix" — the head is the check's name.
            words = {w.lower().strip(".,;:—-()") for w in verdict.split()}
            outp.append((path, verdict, any(w.startswith(INSTR_BAD) for w in words)))
        return outp

    cites = []                                           # (ts, id, path, verdict, bad)
    unparsed = []                                        # stamp present, nothing read = the
    for l in lines:                                      # face's own zero-denominator case
        if not l.get("id"): continue
        if not l.get("instrument"): continue
        got = _instruments(l)
        if not got: unparsed.append((l["id"], str(l["instrument"])[:80])); continue
        for path, verdict, bad in got:
            cites.append((l.get("ts") or "", l["id"], path, verdict, bad))
    if unparsed:
        # 2026-08-23: the flat `;` split dropped arc's re-certification stamp SILENTLY and the
        # face kept showing a stale VACUOUS — no alert, because nothing was examined. Arc named
        # it: silent-drop-on-parse is the audit layer's vacuous check. A stamp that parses to
        # nothing is now a reported event, never a quiet absence.
        alerts.append("ALERT instrument-unparsed: " + "; ".join(f"'{i}' carries an `instrument` "
                      f"stamp this parser read NOTHING from ({v!r})" for i, v in unparsed)
                      + " — the face below is silent about these ids, not clear on them")
    if cites:
        cites.sort(key=lambda c: c[0])
        latest = {}                                      # path -> (ts, id, verdict, bad)
        # A bare citation ("duck/invariants.py", no parenthetical) is a USE, not a verdict: it
        # must not wash an earlier "(insufficient ...)" back to sound. Only verdict-bearing
        # citations move the latest state.
        for ts, i, path, verdict, bad in cites:
            if verdict or path not in latest: latest[path] = (ts, i, verdict, bad)
        by_path = {}
        for ts, i, path, verdict, bad in cites: by_path.setdefault(path, []).append(i)
        print(f"\nINSTRUMENT  {len(cites)} citation(s) · {len(latest)} instrument(s) stamped"
              f" · ids citing: {len({c[1] for c in cites})}/{len(dec_ids)} declined")
        rests_on_retracted = []
        for path, (ts, i, verdict, bad) in sorted(latest.items()):
            state = "RETRACTED" if bad else "sound"
            print(f"  {path:<28} latest {state:<9} {ts[:10]} @ {i}"
                  + (f"  ({verdict})" if verdict else "")
                  + f" · cited by {len(dict.fromkeys(by_path[path]))}")
            if not bad: continue
            for cts, ci, cpath, cverdict, cbad in cites:
                if cpath != path or cbad or cts >= ts or not cverdict: continue   # bare = use, not certification
                rests_on_retracted.append((ci, path, cts[:10], verdict))
        if rests_on_retracted:
            print(f"  RESTS ON A RETRACTED INSTRUMENT: "
                  + " · ".join(f"{ci} cited {path} as sound on {cts}" for ci, path, cts, _ in rests_on_retracted))
            alerts.append(
                "ALERT instrument-retracted: "
                + "; ".join(f"'{ci}' cited {path} as sound ({cts}) and a later line retracted it "
                            f"({v})" for ci, path, cts, v in rests_on_retracted)
                + " — the decision was certified by an instrument that no longer stands; "
                  "re-derive it or stamp the id with the instrument that now certifies it")
        out["instrument"] = {"latest": {p: {"ts": v[0], "id": v[1], "verdict": v[2], "retracted": v[3]}
                                        for p, v in latest.items()},
                             "rests_on_retracted": [{"id": a, "instrument": b, "cited": c}
                                                    for a, b, c, _ in rests_on_retracted]}

    # ── SPLIT RESULT (2026-08-16) ──
    # One run, several pre-declared questions, DIFFERENT verdicts. `split` classifies as
    # unscorable so nothing is booked against a prior that does not exist — but a bucket is
    # where a result goes to be forgotten, and the first line of this shape carried the
    # programme's most notable positive of the week (the framework seam scored, against an
    # 0-for-7 record) beside a negative on the other half. Both halves are real; neither is
    # scoreable as filed. So the face NAMES it every sweep instead of letting `unscorable`
    # absorb it silently. It reports each half from the ledger's own `*_result` fields rather
    # than re-reading the compound outcome string, because parsing "A CLEARED / B BELOW BAND"
    # into halves would be the layer inventing a verdict per half — which is the conflation
    # the `split` declaration exists to refuse.
    split_ids = [i for i in dict.fromkeys(l.get("id") for l in lines)
                 if any(l.get("id") == i and str(disposition(l)[0]).lower().startswith("split")
                        for l in lines)]
    if split_ids:
        rows = []
        for i in split_ids:
            ls    = [l for l in lines if l.get("id") == i]
            halves = sorted({f[:-len("_result")] for l in ls for f in l
                             if f.endswith("_result") and l.get(f)})
            has_p = i in prior_ids
            rows.append((i, halves, has_p))
            print(f"\nSPLIT RESULT  {i} — {len(halves) or '?'} question(s) answered on one line"
                  f"{' (' + ', '.join(halves) + ')' if halves else ''} ·"
                  f" {'prior registered' if has_p else 'NO PREREG — no prior on any half'}")
        unreg = [i for i, _, p in rows if not p]
        if unreg:
            alerts.append(
                f"ALERT split-result: {', '.join(unreg)} resolved SEVERAL pre-declared questions"
                " with different verdicts and registered no prior, so every half scores nothing"
                " and counts nowhere. A split result is only auditable if each question is its"
                " own id with its own prior — register the halves that are still live SEPARATELY"
                " before the next draw; the ones already resolved cannot be scored after the fact")
        out["split_result"] = {"ids": split_ids,
                               "halves": {i: h for i, h, _ in rows},
                               "unregistered": unreg}

    # ── KIND CENSUS ── kind is tokenised, so a compound value still hits its rules; an
    # unrecognised token is the moment a new registration class appears, and if it means
    # "measurement draw" without saying `substrate` it will score as an ordinary bet.
    kinds, kind_unknown = {}, {}
    for l in lines:
        kv = str(l.get("kind") or "").strip()
        if not kv: continue
        kinds[kv] = kinds.get(kv, 0) + 1
        if kind_tokens(l) - KIND_TOKENS:
            kind_unknown.setdefault(kv, []).append(l.get("id"))
    if kinds:
        ks = " ".join(f"{k}:{v}" for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]))
        comp = [k for k in kinds if len(kind_tokens({"kind": k})) > 1]
        print(f"KIND  {ks}" + (f" · compound (token-matched): {', '.join(comp)}" if comp else ""))
    for kv, ids in sorted(kind_unknown.items()):
        new = ", ".join(sorted(kind_tokens({"kind": kv}) - KIND_TOKENS))
        tail = ("it already token-matches `substrate`, so it correctly does NOT score — confirm that is intended"
                if is_substrate({"kind": kv}) else
                "it will SCORE as an ordinary forecast; if it names a measurement draw the value must contain `substrate`")
        alerts.append(f"ALERT kind-dialect: kind '{kv}' carries unknown token(s) [{new}] on {', '.join(sorted(set(i for i in ids if i)))} — {tail}. Extend KIND_TOKENS in both parsers")
    out["kind_census"] = {"values": kinds, "unknown": {k: sorted(set(v)) for k, v in kind_unknown.items()}}

    # ── ORPHANED EXISTENTIALS (seven-dpt store, if present) ──
    store_p = os.environ.get("SEVEN_DPT_DB") or os.path.join(
        os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "seven-dpt", "store.json")
    if os.path.exists(store_p):
        try:
            sdb = json.load(open(store_p))
        except ValueError:
            sdb = None
        if sdb:
            parked = [s for s in sdb.get("sparks", [])
                      if s.get("wakeCondition") and s.get("status") not in ("worked", "failed")]
            owned = [s for s in parked if s.get("exhaustion")]
            orphaned = [s for s in parked if s.get("claimType") != "universal" and not s.get("exhaustion")]
            print(f"\nSTORE (seven-dpt)  parked-with-wake {len(parked)} · exhaustion stated {len(owned)}"
                  f" · ORPHANED-EXISTENTIAL {len(orphaned)}"
                  + (f" · ids: {', '.join('#' + str(s['id']) for s in orphaned[:10])}" if orphaned else ""))
            if orphaned:
                msg = (f"{len(orphaned)} parked spark(s) can revive but never die — "
                       f"state `exhaustion` via update_spark (write-once)")
                if os.environ.get("STORE_STRICT"):
                    alerts.append("ALERT orphaned-existential: " + msg)
                else:
                    print("  WARN: " + msg)
            out["store"] = {"parked": len(parked), "orphaned": len(orphaned)}

    out["alerts"] = alerts
    print()
    # Standing stop-rule state prints HERE, at the bottom next to the alerts, because the
    # sweep view reads `| tail -40` and the FAMILY MIX section (where the trip prints) had
    # scrolled above the window as the instrument face grew — a standing fact promised
    # "printed every sweep" that prints where the view no longer reaches is not printed
    # (2026-08-29; the same decay class the ts-disorder alert names: a view correlate
    # quietly stopped covering the thing it was cut to show).
    for tf in out.get("family_mix_stop_ruled") or []:
        _trip = next((c for c in out.get("family_mix_continue", [])
                      if c["family"] == tf and c.get("tripped")), {})
        _riders = [c["id"] for c in out.get("family_mix_continue", [])
                   if c["family"] == tf and not c.get("tripped") and "resolved" not in c]
        print(f"STANDING stop-rule TRIPPED: family '{tf}' ('{_trip.get('id', '?')}' resolved"
              f" {_trip.get('resolved', '?')})"
              + (f" · in-flight continue-reason heard: {', '.join(_riders)}"
                 if _riders else ""))
    for a in alerts: print(a)
    if not alerts: print("no alerts.")
    if "--json" in argv:
        os.makedirs(os.path.dirname(OUTJSON), exist_ok=True)
        json.dump(out, open(OUTJSON, "w"), indent=1)
        print(f"json -> {OUTJSON}")
    return 1 if alerts else 0

if __name__ == "__main__":
    sys.exit(main())
