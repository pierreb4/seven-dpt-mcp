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
  2. headline stats      base rate, mean stated prior, bias, Brier + skill vs base-rate ref, log-loss
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
import json, math, os, sys

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
relabeled = []
for pid in order:
    lines = by_id[pid]
    priors    = [l for l in lines if "prior" in l]
    outs      = [l for l in lines if "outcome" in l]
    terminals = [l for l in outs if l["outcome"] in TERMINAL]
    verdicts  = [l for l in outs if l["outcome"] in TERMINAL or l["outcome"] == "relabel"]
    corrections += [pid for l in outs if l["outcome"] == "correction"]
    if not priors:
        continue  # outcome-only id (shouldn't happen; visible via line-count check below)
    prior = priors[-1]
    if verdicts and verdicts[-1]["outcome"] == "relabel":
        relabeled.append(pid)
    elif terminals:
        if len(terminals) > 1: multi_terminal.append(pid)
        if any(l["outcome"] == "void" for l in outs): void_then_adjudicated.append(pid)
        resolved.append({"id": pid, "ts": prior["ts"], "p": float(prior["prior"]),
                         "y": 1 if terminals[-1]["outcome"] == "cleared" else 0,
                         "ct": prior.get("claimType") or prior.get("scope")})
    elif any(l["outcome"] == "void" for l in outs):                   voids.append(pid)
    elif any(l["outcome"] == "amended-before-running" for l in outs): amended.append(pid)
    else:                                                             inflight.append(pid)

resolved.sort(key=lambda r: r["ts"])
n  = len(resolved)
ps = [r["p"] for r in resolved]
ys = [r["y"] for r in resolved]

print("seven-dpt #2  stated-prior calibration  (arc prior-ledger testbed)")
print("=" * 86)
print(f"  ledger: {LEDGER}")
print(f"  ids: {len(by_id)} | resolved {n} | void {len(voids)} | amended-pre-run {len(amended)}"
      f" | in-flight {len(inflight)} | relabel-superseded {len(relabeled)}")
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
           "platt": {"a": round(pa, 4), "b": round(pb, 4)},
           "scope": {"universal": n_u, "existential_bounded": n_e, "unstamped": n_un},
           "last_resolved_ts": resolved[-1]["ts"]}
    if era_out: out["split"] = era_out
    os.makedirs(os.path.dirname(OUTJSON), exist_ok=True)
    json.dump(out, open(OUTJSON, "w"), indent=2)
    print("-" * 86)
    print(f"  wrote {OUTJSON}  (consumed by reservation_value_bayes.py; intercept-only is the headline)")
