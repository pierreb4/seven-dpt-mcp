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
                liveness (`channel` [+ `liveness`] fields on the prereg line) — the
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
                statement / feasibility answer), kind="substrate" preregs never score.
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
    if ec is not None: return None        # void / ignore / unknown
    # BOTH fields, in the same precedence disposition() uses. Reading only the first present
    # field is the bug that has now bitten three separate functions: tr87-lens-ceiling arrived
    # as {"resolution":"cleared","outcome":"positive-below-threshold"} and this returned None,
    # so pair() called a CLEARED bet in-flight while the dialect census called it cleared —
    # one file, two answers.
    for w in (l.get("outcome"), l.get("resolution")):
        if not w: continue
        v = _verdict_word(w)
        if v: return v
    # Word-form GRAY (2026-08-14). Mirrors `ec == "nonscored"` above: terminal, counted as a
    # completed run, never scored. Deliberately a SECOND pass, not folded into the loop above:
    # a verdict on EITHER field must win over a non-scoring word on the other, or a line like
    # {"resolution":"failed","outcome":"ran-and-grayed"} would read gray and drop a real
    # failure off the curve. Verdict anywhere beats gray anywhere.
    for w in (l.get("outcome"), l.get("resolution")):
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
    cand = [str(l.get(f)).strip() for f in ("outcome", "resolution") if l.get(f)]
    for w in cand:
        c = outcome_class(w)
        if c != "NEW": return w, c
    return (cand[0] if cand else ""), "NEW"

def outcome_word(l):
    return disposition(l)[0]

def has_reason(l):
    """True when the line carries a declared verdict AND a second, free-text reason field."""
    return len([f for f in ("outcome", "resolution") if l.get(f)]) > 1 \
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
               "adversary-block", "parked", "channel-stamp", "scoring-note"}

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
        """-> (n_stamped, missing_ids, since_ts, recent, recent_missing_ids)"""
        st   = [l for l in preregs if l.get(field)]
        miss = [l.get("id") for l in preregs if not l.get(field)]
        since = min((str(l.get("ts") or "") for l in st), default="")
        recent = [l for l in preregs if since and str(l.get("ts") or "") >= since] if st else []
        rmiss  = [l.get("id") for l in recent if not l.get(field)]
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
            fam = family_of(pid, l)
            if l.get("family"): stamped_fam += 1
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
    # kind=substrate preregs never score; other event types are bookkeeping. A resolution
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
    for i, s in ev_unknown:
        alerts.append(f"ALERT event-dialect: '{i}' resolved event-style with status '{s}' — no head rule maps it (FAILED*/CLEARED*/VOID*/GRAY*/SUBSTRATE-*/*PREPUSH*; kind=substrate never scores): the id reads in-flight, calibration n sticks, and the #34/#41 wake patterns may miss it. Extend event_class in calibration.py + ledger_invariants.py and re-check the wake patterns before trusting n")
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
        withp = [p for p in dec_p.values() if p is not None]
        ranp  = [float(prior_of(r["pre"])) for r in resolved if prior_of(r.get("pre") or {}) is not None]
        if withp and ranp:
            print(f"  mean prior — declined {sum(withp)/len(withp):.2f} vs run {sum(ranp)/len(ranp):.2f}"
                  f" (n {len(withp)}/{len(ranp)}): declining ABOVE the run mean is the shape worth explaining")
        miss = [i for i in dec_ids if dec_p[i] is None]
        if miss:
            print(f"  WARN: no prior on {', '.join(miss)} — per the register-then-refuse protocol,"
                  f" register the prereg with the prior you intended and THEN refuse; without it the"
                  f" decline is counted but 'were we right to decline?' stays unanswerable")
        out["declined"] = {"ids": dec_ids, "priors": dec_p,
                           "mean_prior": round(sum(withp)/len(withp), 3) if withp else None,
                           "no_prior": miss}

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
    for a in alerts: print(a)
    if not alerts: print("no alerts.")
    if "--json" in argv:
        os.makedirs(os.path.dirname(OUTJSON), exist_ok=True)
        json.dump(out, open(OUTJSON, "w"), indent=1)
        print(f"json -> {OUTJSON}")
    return 1 if alerts else 0

if __name__ == "__main__":
    sys.exit(main())
