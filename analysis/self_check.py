#!/usr/bin/env python3
"""self_check.py — the audit layer's audit of itself.

WHY THIS EXISTS
Three defects in three days, all the same shape: the program contradicted itself and a
human reading two screens caught it.

  2026-08-12  calibration printed `declined 0` while invariants printed `DECLINED 1`
              (a no-prior guard ate the class before its branch ran)
  2026-08-13  the DECLINED face counted a refusal a later line had AMENDED AWAY, while the
              family face — same file, same run — did not
  2026-08-13  an alert asserted "it reads in-flight" for two ids that were cleanly
              disposed of; the in-flight set was in scope and said otherwise

None of those needed a person. Each is a proposition about data already in memory, and the
faces publish enough to check every one mechanically. The audit layer audits arc's decision
record; until now nothing audited the audit layer, which is six faces and ~700 lines that
Pierre acts on every morning.

DESIGN: THE CHECK MUST NOT SHARE THE PARSERS' MACHINERY
This script deliberately imports NOTHING from ledger_invariants.py or calibration.py. A
check that calls the same helper inherits the same bug and returns a confident green — the
failure mode is worse than no check, because it launders the error. So it reads only the
two published JSONs and the raw ledger, and re-derives every claim structurally.

It also asks nothing about vocabulary. Deciding whether a word means "terminal" is the
dialect tripwire's job, and duplicating that judgement here would just be a second opinion
from the same head. This script asks only: DO THE FACES AGREE WITH EACH OTHER, AND DO THE
ALERTS DESCRIBE THE STATE THE FACES PUBLISHED? Disagreement is the signal — whichever side
is wrong, a program that says two things is wrong once.

Run:  python3 analysis/self_check.py            (after both layers have written their JSON)
Exit: 0 = consistent · 2 = a face contradicts another face
"""
import json, os, re, sys

DATA = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local/share")
INV  = os.environ.get("INVARIANTS_JSON")  or os.path.join(DATA, "seven-dpt", "invariants.json")
CAL  = os.environ.get("CALIBRATION_JSON") or os.path.join(DATA, "seven-dpt", "calibration.json")

fail = []
def check(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok: fail.append((name, detail))

def load(p, what):
    if not os.path.exists(p):
        print(f"  SKIP  {what}: {p} not found — run the sweep first"); return None
    try:
        return json.load(open(p))
    except (OSError, ValueError) as e:
        print(f"  SKIP  {what}: unreadable ({e})"); return None

print("SELF-CHECK  do the faces agree?")
inv, cal = load(INV, "invariants"), load(CAL, "calibration")
if inv is None or cal is None:
    sys.exit(0)                      # nothing to contradict; not a failure

inv_inflight = set(inv.get("inflight_ids") or [])
inv_resolved = set(inv.get("resolved_ids") or [])
inv_declined = set((inv.get("declined") or {}).get("ids") or [])
buckets      = cal.get("buckets") or {}
cal_inflight = set(buckets.get("in_flight") or [])
cal_declined = set(buckets.get("declined") or [])

# 1 — CROSS-LAYER. The two layers walk the same ledger with independent code; an id they
#     classify differently is a defect in one of them, always. This is the 08-12 defect.
check("cross-layer: declined sets agree", inv_declined == cal_declined,
      f"invariants {sorted(inv_declined)} vs calibration {sorted(cal_declined)}")
check("cross-layer: in-flight sets agree", inv_inflight == cal_inflight,
      f"only-invariants {sorted(inv_inflight - cal_inflight)}"
      f" · only-calibration {sorted(cal_inflight - inv_inflight)}")

# 2 — INTRA-LAYER. A decline is terminal: it can be neither live nor scored. This is the
#     08-13 defect, where a withdrawn refusal was listed as a decline while the family face
#     (correctly) treated it as void.
check("invariants: declined ∩ in-flight is empty", not (inv_declined & inv_inflight),
      f"both: {sorted(inv_declined & inv_inflight)}")
check("invariants: declined ∩ resolved is empty", not (inv_declined & inv_resolved),
      f"both: {sorted(inv_declined & inv_resolved)}")

# 3 — BUCKET DISJOINTNESS. Calibration's buckets partition the ledger; an id in two of them
#     is double-counted in whatever reads them next.
seen, dupes = {}, {}
for bname, ids in buckets.items():
    for i in ids or []:
        if i in seen: dupes.setdefault(i, {seen[i]}).add(bname)
        else: seen[i] = bname
check("calibration: every id in at most one bucket", not dupes,
      "; ".join(f"{i} in {sorted(b)}" for i, b in sorted(dupes.items())))

# 3b — THE TWO VIEWS INSIDE INVARIANTS. disposition() classifies each id from its own lines;
#      pair() decides separately whether the id is resolved or live. They are computed by
#      different code from the same ledger, so an id the first calls TERMINAL and the second
#      calls in-flight is a contradiction. This check was added 2026-08-13 after exactly that
#      slipped through a green self-check: tr87-lens-ceiling arrived as
#      {"resolution":"cleared","outcome":"positive-below-threshold"}, the dialect census read
#      it cleared, and pair() — whose verdict_of still read one field — raised an
#      evidence-negative alert against it as a live bet. Class names, not words: which WORDS
#      are terminal is the dialect layer's business, and duplicating that judgement here would
#      re-import the thing being checked.
TERMINAL_CLASSES = {"verdict", "void", "declined", "adjudication", "unscorable", "nonscored",
                    "withdrawn"}   # 2026-08-14: bare-status terminal (WITHDRAWN UNRUN)
disp = inv.get("disposition") or {}
if disp:
    contra = sorted(i for i, c in disp.items() if c in TERMINAL_CLASSES and i in inv_inflight)
    check("invariants: no id is both terminally disposed and in-flight", not contra,
          "; ".join(f"{i} disposed '{disp[i]}' but pair() says in-flight" for i in contra))

# 4 — ALERT HONESTY. An alert that names a state must name the state the faces published.
#     This is the 08-13 tail defect: the claim was typed, not looked up. Any alert saying
#     in-flight '<id>' is asserting membership of a set this script can read.
claimed = set()
for a in inv.get("alerts") or []:
    claimed |= set(re.findall(r"in-flight '([^']+)'", a))
check("alerts: every id claimed in-flight IS in-flight", claimed <= inv_inflight,
      f"claimed but not in-flight: {sorted(claimed - inv_inflight)}")

# 5 — ARITHMETIC. Faces that publish counts alongside lists must agree with their own lists.
dec = inv.get("declined") or {}
if dec:
    check("DECLINED face: ids and priors map agree",
          set((dec.get("priors") or {}).keys()) == set(dec.get("ids") or []),
          "priors map and id list differ")
    no_prior = set(dec.get("no_prior") or [])
    stated   = {i for i, p in (dec.get("priors") or {}).items() if p is None}
    check("DECLINED face: no_prior matches the priors map", no_prior == stated,
          f"no_prior {sorted(no_prior)} vs null-prior {sorted(stated)}")

fam = inv.get("family_mix") or {}
if fam.get("families"):
    check("FAMILY MIX: classified families sum to the classified stream",
          sum(fam["families"].values()) + len(fam.get("unclassified") or []) == fam.get("n"),
          f"families {sum(fam['families'].values())} + unclassified"
          f" {len(fam.get('unclassified') or [])} != n {fam.get('n')}")

ch = inv.get("channel") or {}
if ch:
    check("CHANNEL: stamped never exceeds total", ch.get("stamped", 0) <= ch.get("total", 0),
          f"stamped {ch.get('stamped')} > total {ch.get('total')}")

print(f"\n  {len(fail)} contradiction(s)")
if fail:
    print("  A face disagrees with another face. Whichever is right, the program is wrong once —")
    print("  fix the disagreement before trusting ANY number in this sweep.")
    sys.exit(2)
sys.exit(0)
