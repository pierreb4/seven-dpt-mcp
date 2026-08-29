#!/usr/bin/env python3
"""Stated-prior calibration audit (seven-dpt #2, spark #22). arc logs, seven-dpt analyses.

Reads arc's launch/prior-ledger.jsonl -- the high-throughput calibration testbed: two immutable
JSONL lines per probe, a numeric P(clears the pre-registered rule) at pre-registration and an
outcome at resolution (prior-calibration-protocol.md). Secondarily lists seven-dpt's own store
sparks that carry a stated `prior` and a terminal status (same audit, slower accrual).

PAIRING RULES (learned from the live ledger, not just the protocol):
  * prior line  = has "prior"; outcome line = has "outcome"; grouped by id, file order kept.
  * cleared/failed -> resolved. If an id has SEVERAL terminal lines (a retry adjudicated under
    the same pre-registration), the LAST one is the verdict -- "record the final adjudication"
    -- and the id is flagged in the exclusions report so the choice is visible.
  * relabel                -> a LATER relabel line supersedes the terminal it follows: the audit
                              re-graded the verdict NULL-EQUIVALENT (adoption-bar-restated,
                              2026-08-02), so the pair leaves the curve. A terminal appended
                              after the relabel (re-adjudicated on a new run) re-scores it.
  * void                   -> logged, excluded from the curve (protocol).
  * amended-before-running -> pre-registration superseded before any run; excluded (immutability
                              starts when the run starts).
  * correction             -> corrects a resolution NOTE, never a verdict by itself; ignored.
  * prior with no outcome  -> in-flight; counted, excluded.

OUTPUT (text; at this n the binned table IS the reliability curve):
  1. reliability table   equal-count prior bins vs realized cleared-rate, Wilson 95% CIs
  2. headline stats      base rate, mean stated prior, bias, Brier + skill vs base-rate ref, log-loss,
                         CORP decomposition (Brier = MCB - DSC + UNC, bin-free via PAV) with R = DSC/UNC
  3. de-bias map         intercept-only log-odds shift (headline) + Platt (a,b); --json persists it
  4. drift check         first half vs second half by pre-registration time
  5. exclusions report   voids / amended / in-flight / correction / multi-terminal ids
  6. scope stamp         claimType composition of scored pairs -- scoring is scope-blind by
                         construction (a frame-null counts as a claim-failure), so unstamped
                         existentials are the visible residual risk (scope-leak census 2026-08-01)
  7. era split           --split YYYY-MM-DD partitions by prereg ts (spark #31: a model upgrade
                         is a changepoint -- re-price, don't pool across it); per-era bias/skill/shift

--json writes the de-bias map for reservation_value_bayes.py to consume. It lands in the XDG
data dir next to store.json (runtime-derived state, NOT repo content):
    ~/.local/share/seven-dpt/calibration.json          (env CALIBRATION_JSON overrides)

Run:  python3 analysis/calibration.py [--json] [--split YYYY-MM-DD]
Env:  ARC_PRIOR_LEDGER (default ~/projects/arc-agi-3/launch/prior-ledger.jsonl)
      SEVEN_DPT_DB, CALIBRATION_JSON, BINS (default 4)
"""
import json, math, os, re, sys

LEDGER = os.path.expanduser(os.environ.get("ARC_PRIOR_LEDGER",
         "~/projects/arc-agi-3/launch/prior-ledger.jsonl"))
STORE  = os.environ.get("SEVEN_DPT_DB") or os.path.join(
         os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
         "seven-dpt", "store.json")
OUTJSON = os.environ.get("CALIBRATION_JSON") or os.path.join(
          os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
          "seven-dpt", "calibration.json")
BINS = int(os.environ.get("BINS", 4))
TERMINAL = ("cleared", "failed")
SPLIT = sys.argv[sys.argv.index("--split") + 1] if "--split" in sys.argv else None

def logit(p):   return math.log(p / (1.0 - p))
def sigmoid(x): return 1.0 / (1.0 + math.exp(-x))

# ---- ledger dialects --------------------------------------------------------------------------
# v1 (2026-07-21..08-04): two lines/probe — {prior, criterion, why} then {outcome, note}.
# v2 (2026-08-05..):      {kind, status: open|partial|closed, prior_p_<target>, why, result};
#                         desk items are born-and-closed in ONE line; the verdict is either an
#                         explicit `outcome` word or the RESULT'S LEADING WORD. Only an exact
#                         whitelist is scored — CAUTION/MIXED/PARTIAL heads stay excluded,
#                         visibly, rather than guessed.
# v3 (2026-08-07.., shared-launch file): prereg carries the prior as a bare `p_<target>` key
#                         and `date` instead of `ts`; resolutions are `resolution: <word>` lines
#                         echoing the prior as `p_*_was` (never a prior source). Scored words:
#                         cleared/failed only; `void*` → void; held/stop/parked stay non-terminal
#                         (parked-with-wake reads as in-flight — the wake owns reopening).
# v3.1 (2026-08-08.., absorbed 2026-08-11): event lines. {"event":"resolution","status":<WORD>}
#                         is the verdict channel; the status HEAD maps: FAILED*→0, CLEARED*→1,
#                         VOID*/*PREPUSH*→void, GRAY*→terminal-non-scored (pre-declared power
#                         statement), SUBSTRATE-*→terminal-non-scored (feasibility answer). A
#                         prereg with kind="substrate" NEVER scores (measurement draw, not a
#                         lever gate) whatever its status says. Non-resolution events (migration,
#                         status-update) are bookkeeping — ignored — except *KILLED*/*PREPUSH*
#                         event values, which read void. A resolution status no head rule maps
#                         stays in-flight HERE; ledger_invariants.py owns the ALERT (tripwire).
def event_class(l):
    """None if l is not an event line; else 'cleared'/'failed' (scoreable), 'void',
    'nonscored' (terminal but never on the curve), 'ignore' (bookkeeping), 'unknown'."""
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

def prior_of(l):
    if "prior" in l: return l["prior"]
    for k in l:
        if k.startswith("prior_p_"): return l[k]
        if k.startswith("p_") and not k.endswith("_was"): return l[k]
    return None

_HEADS = {"CLEARED": 1, "FAILED": 0, "DEAD": 0, "KILLED": 0}
def verdict_of(l):
    ec = event_class(l)
    if ec is not None:
        return {"cleared": 1, "failed": 0}.get(ec)
    # BOTH fields, same precedence as ledger_invariants (2026-08-13). Reading only the first
    # present one made this return None for {"resolution":"cleared","outcome":"positive-below-
    # threshold"} — a cleared bet silently off the curve. `refuted-by-run` is arc's token for
    # ran-and-lost, minted so a completed negative is not filed as a walk-away.
    # result_field: third carrier, kind=resolution lines only (2026-08-18).
    for w in (l.get("outcome"), l.get("resolution"), result_field(l)):
        lw = str(w or "").lower()
        if lw.startswith("cleared"): return 1
        if lw.startswith(("failed", "refuted-by-run")): return 0
    if l.get("status") == "closed":
        head = ((l.get("result") or "").split() or [""])[0].strip(".,;:—-*")
        return _HEADS.get(head)
    return None

VOID_WORDS = ("void", "instrument-inadequate")   # instrument-inadequate: arrived 2026-08-12
                                                 # paired with resolution "void" — could not
                                                 # measure, so no information either way.

def is_void(l):
    return any(str(w or "").lower().startswith(VOID_WORDS)
               for w in (l.get("outcome"), l.get("resolution"), result_field(l))) \
        or event_class(l) == "void"

NONSCORED_WORDS = ("gray", "inconclusive", "ran-and-grayed", "ran-and-inconclusive")

def is_nonscored(l):
    """THE MIDDLE WORLD in word form (2026-08-14). Mirrors
    ledger_invariants.OUTCOME_DECLARED[...]='nonscored'. RAN, instrument worked, result does
    not adjudicate — so terminal and counted, but there is no y to score a prior against.
    Word-form twin of the event-form GRAY* head, which this file already routes to
    event_nonscored; the same concept arriving in a different dialect must land in the same
    bucket or the curve depends on which way arc happened to write it.

    NOTE the deliberate asymmetry with ledger_invariants: THERE verdict_of returns "gray" so
    pair() counts a grayed run as a completed attempt (a family that grayed three times has
    attempted three times); HERE verdict_of must keep returning None so it never reaches
    `resolved`. Same word, two correct answers, because the two files measure different
    things."""
    return any(str(w or "").lower().startswith(NONSCORED_WORDS)
               for w in (l.get("outcome"), l.get("resolution"), result_field(l))) \
        or event_class(l) == "nonscored"

SPLIT_WORDS = ("split",)

def is_split(l):
    """One run, several pre-declared questions, DIFFERENT verdicts (2026-08-16). Mirrors
    ledger_invariants.OUTCOME_DECLARED['split']='unscorable'. Terminal — the run happened —
    but never scoreable: two answers cannot be graded against one prior, and on the first
    line of this shape there is no prior at all.

    Checked on `resolution` and `outcome` alike, but note what protects the curve here: the
    compound word is "SEAM CLEARED / LEVER BELOW BAND", and verdict_of only fires on a
    startswith, so the embedded CLEARED is not read as a verdict today. That is luck of word
    order, not a guarantee — a future line reading "CLEARED on the seam / BELOW BAND on the
    lever" WOULD score 1 against a single prior on an id that has one. If that shape appears,
    is_split has to move ahead of verdict_of in last_disposition rather than beside it."""
    return any(str(w or "").lower().startswith(SPLIT_WORDS)
               for w in (l.get("outcome"), l.get("resolution"), result_field(l)))

STATUS_HEADS = {"WITHDRAWN": "withdrawn"}   # mirrors ledger_invariants.STATUS_HEADS

def status_class(l):
    """Terminal disposition on a bare `status` — no event, no outcome/resolution. Narrow by
    design: only declared heads classify (see ledger_invariants for the full rationale)."""
    if l.get("event") or l.get("outcome") or l.get("resolution"): return None
    s = str(l.get("status") or "").upper()
    for head, cls in STATUS_HEADS.items():
        if s.startswith(head): return cls
    return None

def is_declined(l):
    """Mirrors ledger_invariants.OUTCOME_DECLARED['declined'] (option 4, 2026-08-12):
    decided WITHOUT running. Terminal and counted, but never scoreable — the run never
    happened, so there is no ground truth to grade the stated prior against. Under the
    register-then-refuse protocol these ids DO carry a prior, so without this branch they
    would read in-flight forever.

    2026-08-22: `no-arm` and `withdrawn-at-adversary` join, the latter on arc's own answer to
    the brief (they minted it for the MECHANISM, not the class). Matched on the FULL word, never
    a bare `withdrawn` prefix: the three unpriced kills of the same night carry
    {"outcome":"void","result":"withdrawn"} and a prefix rule would silently pull them out of
    void, which is arc's call to make, not ours."""
    return any(str(w or "").lower().startswith(("refused", "declined", "premise-refuted",
                                                "no-arm", "withdrawn-at-adversary"))
               for w in (l.get("outcome"), l.get("resolution"), result_field(l)))

def last_disposition(ls):
    """Last readable disposition on an id — the ledger is append-only, so a later line
    supersedes an earlier one. Needed because `shapeid-rot-rung` (2026-08-12) refuses and
    then AMENDS that refusal to void 80 minutes later: an any()-style declined check would
    freeze it at the refusal and disagree with ledger_invariants, which takes last-wins."""
    d = None
    for l in ls:
        # VERDICT IS CHECKED FIRST. A line can carry a verdict word and a refusal word at once
        # — {"resolution":"refused","outcome":"refuted-by-run"} is arc's ran-and-lost — and a
        # completed run filed as a walk-away would drop off the curve entirely.
        if verdict_of(l) is not None:        d = "verdict"
        elif is_nonscored(l):                d = "nonscored"   # ran, did not adjudicate
        elif is_declined(l):                 d = "declined"
        elif is_void(l):                     d = "void"
        elif l.get("outcome") == "relabel":  d = "relabel"
        elif status_class(l) == "withdrawn": d = "withdrawn"   # registered, never ran
        elif is_split(l):                    d = "split"       # ran, answered several questions
    return d

def kind_tokens(l):
    return {t for t in re.split(r"[+/,;\s]+", str(l.get("kind") or "").lower()) if t}

SUBSTRATE_SCORES_SINCE = "2026-08-24"   # arc's classification annotation, 2026-08-24T15:10Z
# ts caveat (dialect-3, 7c64878, 2026-08-29): `ts` is a HAND-STAMPED NOMINAL event time with
# a proven day-typo class — authority order is file append order, then git-blame arrival,
# then ts as label only. This gate reads ts and is the ONE load-bearing consumer: a boundary
# id (resolution ts within a typo's reach of 2026-08-24) must be resolved by git-blame
# arrival before trusting the comparison below. Every substrate terminal to date sits days
# clear of the boundary; the invariants ts-disorder tripwire surfaces any new typo, so a
# silent flip requires a typo the tripwire missed AND a boundary-adjacent arm — check blame
# by hand if both ever coincide.

def is_substrate(l):
    """Mirrors ledger_invariants.py. `kind` is TOKENISED, not compared whole: a compound
    value (`substrate+pilot`, 2026-08-12) must still hit the substrate rule, or a
    measurement draw scores as an ordinary forecast — which it did, silently."""
    return "substrate" in kind_tokens(l)

def result_field(l):
    """Mirrors ledger_invariants.py. `result` as a verdict carrier, ONLY on kind=resolution
    lines (declared 2026-08-18, arc's kind-dialect-semantics-2: 'classing rides the `result`
    word'). Everywhere else `result` stays v2 prose, read solely under status=closed via the
    _HEADS whitelist — opening it on every line would let free text score."""
    return l.get("result") if "resolution" in kind_tokens(l) else None

def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 1.0)
    p = k / n; z2 = z * z
    mid = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return (max(0.0, mid - half), min(1.0, mid + half))

# ---- parse the ledger -------------------------------------------------------------------------
by_id, order = {}, []
for line in open(LEDGER):
    line = line.strip()
    if not line: continue
    rec = json.loads(line)
    if rec["id"] not in by_id:
        by_id[rec["id"]] = []
        order.append(rec["id"])
    by_id[rec["id"]].append(rec)

resolved, voids, amended, inflight, corrections, multi_terminal, void_then_adjudicated = \
    [], [], [], [], [], [], []
relabeled, closed_unscorable, event_nonscored, declined = [], [], [], []
withdrawn = []   # 2026-08-14: registered, never run, replaced by a redesign (sb26-animfeedback-
                 # draw1). Its own bucket, NOT folded into declined — arc's line says "Not a
                 # verdict on the lever", and the DECLINED face asks whether we were right to
                 # walk away from bets we rated well. A bet nobody walked away from would be a
                 # wrong answer to that question, in the flattering direction.
split_unscorable = []   # 2026-08-16: ran, answered several pre-declared questions with different
                        # verdicts (ship-animfeedback-draw1). Terminal, counted, never scored.
for pid in order:
    lines = by_id[pid]
    priors    = [l for l in lines if prior_of(l) is not None]
    outs      = [l for l in lines if "outcome" in l or "resolution" in l or l.get("status") == "closed"
                 or "event" in l or result_field(l) is not None]
    terminals = [l for l in outs if verdict_of(l) is not None]
    verdicts  = [l for l in outs if verdict_of(l) is not None or l.get("outcome") == "relabel"]
    substrate = any(is_substrate(l) for l in lines)
    corrections += [pid for l in outs if l.get("outcome") == "correction"]
    if last_disposition(lines) == "declined":
        declined.append(pid); continue   # terminal WITH OR WITHOUT a prior. Checked before the
                                         # no-prior guard on purpose: the register-then-refuse
                                         # protocol asks for a prior, but a refusal that skipped
                                         # it is still a refusal, and dropping it here would make
                                         # this header disagree with the invariants DECLINED face
                                         # (it did: `declined 0` vs `DECLINED 1`, 2026-08-12).
    if last_disposition(lines) == "split":
        split_unscorable.append(pid); continue
        # BEFORE the no-prior guard, on purpose. ship-animfeedback-draw1 has no prereg at all,
        # so the guard below would `continue` past every branch and the id would land in NO
        # bucket — invisible here while ledger_invariants prints a SPLIT RESULT face for it.
        # That is exactly the 2026-08-12 cross-layer drift (`declined 0` vs `DECLINED 1`), where
        # a no-prior guard ate a class before its branch could run. The standing lesson from
        # that one is the reason this line sits where it does: walk a NEW CLASS through every
        # layer's early exits before believing the branch you wrote is the branch that runs.
    if not priors:
        continue  # outcome-only id (shouldn't happen; visible via line-count check below)
    prior = priors[-1]
    if verdicts and verdicts[-1].get("outcome") == "relabel":
        relabeled.append(pid)
    elif terminals and substrate and (terminals[-1].get("ts") or "") < SUBSTRATE_SCORES_SINCE:
        event_nonscored.append(pid)  # measurement draw: a scoreable word still never scores
        # ^ ...BEFORE 2026-08-24 only. Arc's 15:10Z classification annotation (lora-conv-
        # l3o-train, instrument: prior-calibration-protocol) sets the standing rule: a
        # substrate arm's prior is a REAL FORECAST of its own clauses clearing and SCORES on
        # resolution — `substrate` says what the bet is ABOUT (the rig, not the lever), never
        # whether it counts; the genuinely non-scored class is an UNPRICED substrate
        # registration. Gated on the RESOLUTION date so the rule reads forward: the seven
        # substrate terminals resolved before 08-24 were settled non-scored under the old
        # mapping (colab-mtp genus 08-11, v32b substrate-terminal 08-18) and history is not
        # rewritten; l3o-train (resolved 08-24T11:30, the arm the annotation names) scores at
        # its last pre-resolution price, 0.55. No id literals — the day boundary implements
        # the named instruction, and every future priced substrate resolution scores by rule.
        # Arc CONFIRMED prospective-only (08-24) with the reason that makes it a law, not a
        # preference: extending the rule backward would be an OUTCOME-CONTAMINATED choice —
        # all seven results are known, so retroactivity would move the curve by up to 7
        # points in a direction the forecaster can already compute (peek-then-add-samples),
        # and the older priors' intent (true P(clears) vs loose confidence tag) can no
        # longer be certified. A calibration curve must never let its subject do that.
    elif terminals:
        if len(terminals) > 1: multi_terminal.append(pid)
        if any(is_void(l) for l in outs): void_then_adjudicated.append(pid)
        resolved.append({"id": pid, "ts": prior.get("ts") or prior.get("date"), "p": float(prior_of(prior)),
                         "y": verdict_of(terminals[-1]),
                         "ct": prior.get("claimType") or prior.get("scope")})
    elif any(is_void(l) for l in outs):                                   voids.append(pid)
    elif any(is_nonscored(l) for l in outs) or \
         (substrate and any(l.get("event") == "resolution" for l in outs)):
        event_nonscored.append(pid)  # GRAY power-statement / substrate answer — terminal, off the
                                     # curve. is_nonscored (2026-08-14) widens this from the
                                     # event-form GRAY* head to the word form too, so `gray` and
                                     # `inconclusive` land here rather than reading in-flight
                                     # forever and holding n back with them.
    elif any(status_class(l) == "withdrawn" for l in lines):
        withdrawn.append(pid)        # registered, never ran, superseded by a redesign
    elif any(l.get("outcome") == "amended-before-running" for l in outs): amended.append(pid)
    elif any(l.get("status") == "closed" or l.get("outcome") == "closed" for l in lines):
        closed_unscorable.append(pid)  # closed without a whitelisted verdict word
    else:                                                             inflight.append(pid)

resolved.sort(key=lambda r: r["ts"])
n  = len(resolved)
ps = [r["p"] for r in resolved]
ys = [r["y"] for r in resolved]

print("seven-dpt #2  stated-prior calibration  (arc prior-ledger testbed)")
print("=" * 86)
print(f"  ledger: {LEDGER}")
print(f"  ids: {len(by_id)} | resolved {n} | void {len(voids)} | amended-pre-run {len(amended)}"
      f" | in-flight {len(inflight)} | relabel-superseded {len(relabeled)}"
      f" | event-non-scored {len(event_nonscored)} | declined {len(declined)}")
if n < 10:
    print(f"\n  only {n} resolved -- below any useful curve. Come back at >=20."); sys.exit(0)

# ---- headline stats ---------------------------------------------------------------------------
base = sum(ys) / n
mp   = sum(ps) / n
brier      = sum((p - y) ** 2 for p, y in zip(ps, ys)) / n
brier_ref  = sum((base - y) ** 2 for y in ys) / n           # always-say-base-rate reference
skill      = 1.0 - brier / brier_ref if brier_ref > 0 else float("nan")
logloss    = -sum(y * math.log(p) + (1 - y) * math.log(1 - p) for p, y in zip(ps, ys)) / n
lo, hi = wilson(sum(ys), n)
print("-" * 86)
print(f"  base rate {sum(ys)}/{n} = {base:.2f}  (Wilson 95% [{lo:.2f},{hi:.2f}])"
      f"  |  mean stated prior {mp:.2f}")
bias = mp - base
verdict = ("UNDERconfident (stated too low)" if bias < 0 else "OVERconfident (stated too high)")
inside = lo <= mp <= hi
print(f"  bias (mean prior - base rate) = {bias:+.2f} -> point-estimate {verdict}")
print(f"    ...but mean prior {'SITS INSIDE' if inside else 'FALLS OUTSIDE'} the base-rate CI at n={n}"
      f" -> {'compatible with calibrated; treat the de-bias as a lean, not a law' if inside else 'a real shift'}")
print(f"  Brier {brier:.3f} vs base-rate ref {brier_ref:.3f} -> skill {skill:+.2f}"
      f"  ({'priors beat' if skill > 0 else 'priors LOSE to'} always-saying-{base:.2f})"
      f"  |  log-loss {logloss:.3f}")

# ---- CORP decomposition (bin-free) -------------------------------------------------------------
# Spark #33 prereg 2026-08-01, meter parked at the MDE wall; spark #34 gate (n>=50) tripped
# 2026-08-19 at n=55 and the erasure-power probe booked CONTINUE (S(0.5)=2.48) — this block is
# that prereg's shipped action. Math mirrors corp_meter_power.py: PAV isotonic fit, then
# Brier = MCB - DSC + UNC exactly; R = DSC/UNC is the share of achievable resolution the
# stated priors actually capture (0 = no ordering signal, 1 = all of it).
def pav_fit(ps_, ys_):
    idx = sorted(range(len(ps_)), key=lambda k: ps_[k])
    blocks = []
    for k in idx:
        blocks.append([ys_[k], 1.0])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s, c = blocks.pop(); blocks[-1][0] += s; blocks[-1][1] += c
    flat = [s / c for s, c in blocks for _ in range(int(round(c)))]
    q = [0.0] * len(ps_)
    for pos, k in enumerate(idx): q[k] = flat[pos]
    return q

_bpav = sum((qi - y) ** 2 for qi, y in zip(pav_fit(ps, ys), ys)) / n
unc = base * (1 - base)
dsc = unc - _bpav                      # discrimination: what the isotonic re-map recovers
mcb = brier - _bpav                    # miscalibration: what the re-map removes
assert abs(brier - (mcb - dsc + unc)) < 1e-12, "CORP identity failed"
corp_r = dsc / unc if unc > 0 else float("nan")
print(f"  CORP  Brier {brier:.3f} = MCB {mcb:.3f} - DSC {dsc:.3f} + UNC {unc:.3f}"
      f"  ->  R = DSC/UNC = {corp_r:.3f}"
      f"  ({'priors ORDER outcomes' if corp_r > 0 else 'NO ordering signal'})")

# ---- reliability table (equal-count bins) -----------------------------------------------------
srt = sorted(resolved, key=lambda r: r["p"])
bins = [srt[round(i * n / BINS): round((i + 1) * n / BINS)] for i in range(BINS)]
print("-" * 86)
print(f"  {'stated range':>14}  {'n':>3}  {'mean p':>6}  {'cleared':>8}  {'rate':>5}  {'Wilson 95%':>13}  curve")
for b in bins:
    if not b: continue
    bp = [r["p"] for r in b]; k = sum(r["y"] for r in b); bn = len(b)
    blo, bhi = wilson(k, bn)
    bar = lambda v: "#" * round(v * 20)
    print(f"  {min(bp):>6.2f}-{max(bp):<7.2f} {bn:>3}  {sum(bp)/bn:>6.2f}  {k:>4}/{bn:<3}  {k/bn:>5.2f}"
          f"  [{blo:.2f},{bhi:.2f}]  p:{bar(sum(bp)/bn):<20} y:{bar(k/bn)}")

# ---- de-bias map ------------------------------------------------------------------------------
def shift_for_base(ps, target):        # intercept-only: mean(sigmoid(logit(p)+d)) = target
    f = lambda d: sum(sigmoid(logit(p) + d) for p in ps) / len(ps) - target
    lo_, hi_ = -5.0, 5.0
    for _ in range(80):
        mid = (lo_ + hi_) / 2.0
        lo_, hi_ = (mid, hi_) if f(mid) < 0 else (lo_, mid)
    return (lo_ + hi_) / 2.0

def platt(ps, ys, iters=100):          # Newton ascent on Bernoulli log-lik of sigmoid(a + b*logit p)
    xs = [logit(p) for p in ps]; a, b = 0.0, 1.0
    for _ in range(iters):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in zip(xs, ys):
            m = sigmoid(a + b * x); w = m * (1 - m)
            ga += y - m; gb += (y - m) * x
            haa += w; hab += w * x; hbb += w * x * x
        det = haa * hbb - hab * hab
        if det < 1e-12: break
        da = (hbb * ga - hab * gb) / det; db = (-hab * ga + haa * gb) / det
        a += da; b += db
        if abs(da) + abs(db) < 1e-10: break
    return a, b

delta = shift_for_base(ps, base)
pa, pb = platt(ps, ys)
print("-" * 86)
print(f"  de-bias (intercept-only): log-odds shift {delta:+.2f}"
      f"   e.g. stated 0.30->{sigmoid(logit(.30)+delta):.2f}"
      f"  0.50->{sigmoid(logit(.50)+delta):.2f}  0.70->{sigmoid(logit(.70)+delta):.2f}")
print(f"  Platt (a{pa:+.2f}, b {pb:.2f}): cal(p) = sigmoid(a + b*logit p)"
      f"   0.30->{sigmoid(pa+pb*logit(.30)):.2f}  0.50->{sigmoid(pa+pb*logit(.50)):.2f}"
      f"  0.70->{sigmoid(pa+pb*logit(.70)):.2f}"
      f"   (b{'<1: priors under-resolve, map flattens' if pb < 1 else '>=1: priors resolve, map steepens'})")
print(f"  at n={n} prefer the intercept-only shift; Platt's slope needs more data to trust.")

# ---- drift check ------------------------------------------------------------------------------
h1, h2 = resolved[: n // 2], resolved[n // 2:]
print("-" * 86)
for tag, h in (("first half", h1), ("second half", h2)):
    hb = sum(r["y"] for r in h) / len(h); hp = sum(r["p"] for r in h) / len(h)
    hlo, hhi = wilson(sum(r["y"] for r in h), len(h))
    print(f"  drift {tag:>11} (n={len(h)}, {h[0]['ts'][:10]}..{h[-1]['ts'][:10]}): "
          f"mean prior {hp:.2f} vs rate {hb:.2f} [{hlo:.2f},{hhi:.2f}]  bias {hp - hb:+.2f}")
print(f"  halves of {n} are noise-dominated; read drift as direction only, not magnitude.")

# ---- exclusions report ------------------------------------------------------------------------
print("-" * 86)
def _lst(xs): return ", ".join(xs) if xs else "-"
print(f"  excluded  void: {_lst(voids)}")
print(f"            amended-before-running: {_lst(amended)}")
print(f"            in-flight: {_lst(inflight)}")
if relabeled:
    print(f"            relabel-superseded (audit re-graded NULL-EQUIVALENT; off the curve): {_lst(relabeled)}")
if closed_unscorable:
    print(f"            closed-unscorable (no whitelisted verdict word — CAUTION/MIXED/etc.): {_lst(closed_unscorable)}")
if event_nonscored:
    print(f"            ran-but-did-not-adjudicate (GRAY/inconclusive/substrate measurement): {_lst(event_nonscored)}")
if withdrawn:
    print(f"            withdrawn-unrun (registered, never ran, superseded by a redesign): {_lst(withdrawn)}")
if split_unscorable:
    print(f"            split-result (ran, several questions, different verdicts, one prior at most): {_lst(split_unscorable)}")
if corrections:    print(f"  note-corrections seen (verdict untouched): {_lst(corrections)}")
if multi_terminal: print(f"  multi-terminal ids (LAST adjudication used): {_lst(multi_terminal)}")
if void_then_adjudicated:
    print(f"  void run then adjudicated on retry (resolution wins, void line absorbed): "
          f"{_lst(void_then_adjudicated)}")

# ---- scope stamp (0.1.5): scoring is scope-blind by construction -------------------------------
n_u  = sum(1 for r in resolved if r["ct"] == "universal")
n_e  = sum(1 for r in resolved if r["ct"] and r["ct"] != "universal")
n_un = n - n_u - n_e
print("-" * 86)
print(f"  scope stamp: {n_u} universal / {n_e} existential-bounded / {n_un} unstamped of {n} scored")
print(f"    a frame-null scores as a claim-failure here (scope-blind); stamp prereg lines with"
      f" claimType so a frame-kill is never read as a lever-kill.")

# ---- era split (--split): a model upgrade is a changepoint; re-price, don't pool (spark #31) ---
era_out = None
if SPLIT:
    eras = (("pre", [r for r in resolved if r["ts"][:10] < SPLIT]),
            ("post", [r for r in resolved if r["ts"][:10] >= SPLIT]))
    print("-" * 86)
    print(f"  era split at {SPLIT} (by pre-registration ts)")
    era_out = {"date": SPLIT}
    for tag, h in eras:
        if len(h) < 6:
            print(f"    {tag:>4}: n={len(h)} -- too few to read (needs >=6 per era)")
            era_out[tag] = {"n": len(h)}
            continue
        hn = len(h); hk = sum(r["y"] for r in h)
        hb = hk / hn; hp = sum(r["p"] for r in h) / hn
        hlo, hhi = wilson(hk, hn)
        hbrier = sum((r["p"] - r["y"]) ** 2 for r in h) / hn
        href = sum((hb - r["y"]) ** 2 for r in h) / hn
        hskill = 1 - hbrier / href if href > 0 else float("nan")
        hd = shift_for_base([r["p"] for r in h], hb) if 0 < hb < 1 else float("nan")
        era_out[tag] = {"n": hn, "base": round(hb, 4), "mean_prior": round(hp, 4),
                        "bias": round(hp - hb, 4), "skill": round(hskill, 4), "shift": round(hd, 4)}
        print(f"    {tag:>4} (n={hn}, {h[0]['ts'][:10]}..{h[-1]['ts'][:10]}): rate {hb:.2f} [{hlo:.2f},{hhi:.2f}]"
              f"  mean prior {hp:.2f}  bias {hp - hb:+.2f}  skill {hskill:+.2f}  shift {hd:+.2f}")
    if all(isinstance(era_out.get(t), dict) and era_out[t].get("n", 0) >= 6 for t in ("pre", "post")):
        print(f"    bias delta (post - pre) = {era_out['post']['bias'] - era_out['pre']['bias']:+.2f}"
              f"  |  shift delta = {era_out['post']['shift'] - era_out['pre']['shift']:+.2f}"
              f"  -- at these n read as DIRECTION unless the era base-rate CIs are disjoint.")

# ---- seven-dpt's own store (the eventual consumer; accrues too slowly to curve) ---------------
try:
    d = json.load(open(STORE))
    own = [s for s in d.get("sparks", []) if isinstance(s.get("prior"), (int, float))
           and (s.get("status") or "").lower() in ("worked", "failed")]
    if own:
        print("-" * 86)
        print(f"  seven-dpt store: {len(own)} resolved spark(s) with stated priors (listed, not curved):")
        for s in own:
            hit = (s.get("value") or 0) > 0
            print(f"    #{s['id']}: prior {s['prior']:.2f} -> {s['status']}"
                  f" (value {s.get('value')})  {'hit' if hit else 'miss'}")
except FileNotFoundError:
    pass

# ---- persist for reservation_value_bayes ------------------------------------------------------
if "--json" in sys.argv:
    out = {"source": LEDGER, "n": n, "base_rate": round(base, 4), "mean_prior": round(mp, 4),
           "bias": round(bias, 4), "bias_inside_ci": inside, "brier": round(brier, 4),
           "skill": round(skill, 4), "logodds_shift": round(delta, 4),
           "corp": {"mcb": round(mcb, 4), "dsc": round(dsc, 4), "unc": round(unc, 4),
                    "R": round(corp_r, 4)},
           "platt": {"a": round(pa, 4), "b": round(pb, 4)},
           "scope": {"universal": n_u, "existential_bounded": n_e, "unstamped": n_un},
           # Buckets are persisted so self_check.py can hold this layer against
           # ledger_invariants: the two disagreed twice in two days (declined 0 vs DECLINED 1,
           # then a withdrawn refusal counted here and not there) and both times a human
           # reading two screens caught it. Machine-checkable beats attentive.
           "buckets": {"resolved": [r["id"] for r in resolved], "in_flight": inflight,
                       "declined": declined, "void": voids, "relabeled": relabeled,
                       "event_nonscored": event_nonscored, "amended": amended,
                       "closed_unscorable": closed_unscorable, "withdrawn": withdrawn,
                       "split_unscorable": split_unscorable},
           "last_resolved_ts": resolved[-1]["ts"],
           # 2026-08-23: `instrument` stamp (asked 08-22, arc adopted same night). This layer
           # does not READ the field — an instrument verdict never moves a bucket or a score —
           # it only persists which ids carry one, so self_check can hold ledger_invariants'
           # INSTRUMENT face (the layer that parses the `path (verdict); path` shape) to the
           # same citing set. Independent walk, same ledger, same discipline as `buckets`.
           "instrument_cited": sorted(pid for pid, ls in by_id.items()
                                      if any(l.get("instrument") for l in ls))}
    if era_out: out["split"] = era_out
    os.makedirs(os.path.dirname(OUTJSON), exist_ok=True)
    json.dump(out, open(OUTJSON, "w"), indent=2)
    print("-" * 86)
    print(f"  wrote {OUTJSON}  (consumed by reservation_value_bayes.py; intercept-only is the headline)")
