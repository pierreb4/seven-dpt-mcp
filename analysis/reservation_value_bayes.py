#!/usr/bin/env python3
"""Bayesian reservation-value index for seven-dpt #2, with a ONE-TIME cost vs a COMPOUNDING-but-SATURATING
benefit stream (the capital-budgeting correction).

COMPANION to reservation_value.py (original untouched). Three changes from the plug-in original:

1. POSTERIOR-PREDICTIVE reward, so it emits at n=0,1,2 where the original REFUSES (<5 usable). Reward is
   0-inflated + heavy-tailed, modelled two-part:
       hit    B ~ Bernoulli(p),  p ~ Beta(a0,b0)          <- BETA-BINOMIAL, the "deemed rate" (#19)
       size   M | hit, from a POOLED magnitude posterior   <- HIERARCHICAL: 0-hit boxes borrow the global
                                                              windfall pool; own hits personalise it (#20)

2. TIME STRUCTURE. reservation_value.py compared a ONE-SHOT reward to a one-time cost -- a category error
   (that is WHY every z pinned at the floor: a 0-3 grade can't cover a 45-90 cost). Here the benefit of a
   solved problem is a STREAM: it pays M in period 1 and COMPOUNDS at g, but SATURATES at horizon T (the
   problem's situations get covered / the node ages out). Discounted at r, the present value of one hit is
       PV = M * AF(r,g,T),   AF = (1 - ((1+g)/(1+r))^T)/(r-g)      [= T/(1+r) at g=r]
   SATURATION (finite T) makes AF finite even when g>=r, so the r>g divergence guard is not needed.
   Compounding is what lets a small per-period grade legitimately justify a large one-time cost.

3. COST-TO-OPEN. Pandora's cost is the FORWARD cost to chase one more spark to a verdict, NOT realized
   spend. The `cost` field is overloaded: pending/tried sparks carry forward estimates (~2), worked/failed
   carry realized chase-cost (~60). We PREFER a problem's forward estimates, fall back to realized only if
   that is all it has, then a deemed forward cost. Using REALIZED cost INVERTS the ranking -- it penalises
   exactly the problems that have already been chased and shown a hit.

RANKING vs the ABSOLUTE BAR -- the honest split:
  * PROFITABILITY INDEX  PI = E[PV]/cost  ranks the boxes. If (r,g,T) and the value/cost base units are
    shared across problems, the global value<->cost exchange rate CANCELS from the ranking -> the ORDER is
    exchange-rate-INVARIANT and needs no unit conversion. This is the data-cheap, robust answer #2 wants.
  * The ABSOLUTE "is any box worth opening" bar (PI>1, or z's sign) DOES need the exchange rate + real g.
    Left explicit, not faked. g is drawn wide (mean GROWTH_G) = "assume saturation, refine when data lands";
    the reuse-over-volume curve (distill.sh --reuse) is the eventual empirical g.

Run:  python3 analysis/reservation_value_bayes.py
Knobs (env): DEEMED_RATE(.15) PRIOR_STRENGTH(4) VALUE_SCALE(median hit|1) MAG_PRIOR_STRENGTH(2)
             DISCOUNT_R(.10) GROWTH_G(.10, sampled wide) SAT_HORIZON(10)  N_DRAWS(20000) SEED(0)
"""
import json, os, random
from collections import defaultdict

STORE = os.environ.get("SEVEN_DPT_DB") or os.path.join(
    os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "seven-dpt", "store.json")

DEEMED_RATE        = float(os.environ.get("DEEMED_RATE", 0.15))    # prior P(a spark pays off at all)
PRIOR_STRENGTH     = float(os.environ.get("PRIOR_STRENGTH", 4))    # deemed rate's equivalent sample size
MAG_PRIOR_STRENGTH = float(os.environ.get("MAG_PRIOR_STRENGTH", 2))# pseudo-hits worth of deemed magnitude
DISCOUNT_R         = float(os.environ.get("DISCOUNT_R", 0.10))     # per-period discount rate r
GROWTH_G           = float(os.environ.get("GROWTH_G", 0.10))       # MEAN compounding rate; sampled wide
SAT_HORIZON        = int(os.environ.get("SAT_HORIZON", 10))        # T: periods before the benefit saturates
N_DRAWS            = int(os.environ.get("N_DRAWS", 20000))
SEED               = int(os.environ.get("SEED", 0))
random.seed(SEED)  # reproducible; report MC noise honestly rather than hide it

d = json.load(open(STORE))
problems = {p["id"]: p for p in d.get("problems", []) if p.get("status") == "open"}
byp = defaultdict(list)
for s in d.get("sparks", []):
    byp[s.get("problemId")].append(s)

def status(s):
    return (s.get("status") or "").lower()

def resolved(s):                     # terminal verdict -> its cost is REALIZED chase-spend
    return status(s) in ("worked", "failed")

FWD_STATUSES = ("pending", "tried")  # not chased to a verdict -> its cost is a FORWARD estimate

def val(s):  # graded payoff if the spark carries one, else None
    v = s.get("value")
    return float(v) if isinstance(v, (int, float)) else None

def costof(s):
    c = s.get("cost")
    return float(c) if isinstance(c, (int, float)) else None

def cto(s):  # explicit forward cost-to-open field (clean ground truth logged at capture), else None
    c = s.get("costToOpen")
    return float(c) if isinstance(c, (int, float)) else None

# ---- pool the cross-problem evidence (the hierarchical borrowing), keeping cost populations SEPARATE ----
POOL_MAGS       = [val(s)   for s in d.get("sparks", []) if resolved(s) and (val(s) or 0) > 0]
POOL_CTO        = [cto(s)    for s in d.get("sparks", []) if cto(s) is not None]
POOL_FWD_COSTS  = [costof(s) for s in d.get("sparks", []) if status(s) in FWD_STATUSES and costof(s) is not None]
POOL_REAL_COSTS = [costof(s) for s in d.get("sparks", []) if resolved(s) and costof(s) is not None]

DEEMED_MAG  = float(os.environ.get("VALUE_SCALE",
                    sorted(POOL_MAGS)[len(POOL_MAGS)//2] if POOL_MAGS else 1.0))
_fwd_pool = POOL_CTO or POOL_FWD_COSTS                    # prefer LOGGED cost-to-open, else inferred forward
DEEMED_COST = float(os.environ.get("COST_DEFAULT",       # deemed FORWARD cost-to-open
                    sum(_fwd_pool)/len(_fwd_pool) if _fwd_pool else 1.0))
a0, b0 = DEEMED_RATE * PRIOR_STRENGTH, (1 - DEEMED_RATE) * PRIOR_STRENGTH

def annuity_factor(r, g, T):
    """PV of 1 unit in period 1 compounding at g for T periods, discounted at r. Finite for ALL g,r>-1
    because T is finite -- that is the saturation assumption doing its job (no r>g guard needed)."""
    if abs(g - r) < 1e-9:
        return T / (1.0 + r)
    return (1.0 - ((1.0 + g) / (1.0 + r)) ** T) / (r - g)

def reservation_value(rewards, cost):
    """IDENTICAL to reservation_value.py -- solve mean(max(x-z,0))=cost for z by bisection."""
    xs = list(rewards)
    g = lambda z: sum(max(x - z, 0.0) for x in xs) / len(xs)
    lo, hi = min(xs) - 1.0, max(xs)
    if g(hi) >= cost: return hi
    if g(lo) <= cost: return lo
    for _ in range(64):
        mid = (lo + hi) / 2.0
        lo, hi = (mid, hi) if g(mid) > cost else (lo, mid)
    return (lo + hi) / 2.0

def sample_magnitude(own_hits):
    """First-period benefit M given a hit. Sources weighted by count: own hits >> pool >> deemed prior."""
    w_own, w_pool, w_prior = len(own_hits), len(POOL_MAGS), MAG_PRIOR_STRENGTH
    r = random.random() * (w_own + w_pool + w_prior)
    if r < w_own:          return random.choice(own_hits)
    if r < w_own + w_pool: return random.choice(POOL_MAGS)
    return random.expovariate(1.0 / DEEMED_MAG)

def cost_to_open(all_sp):
    """FORWARD cost to chase one more spark to a verdict. Prefer the explicit costToOpen field
    (clean ground truth, logged at capture); else infer from forward-status `cost` (pending/tried);
    else fall back to realized spend; then the deemed forward cost."""
    logged = [cto(s)    for s in all_sp if cto(s) is not None]
    fwd    = [costof(s) for s in all_sp if status(s) in FWD_STATUSES and costof(s) is not None]
    real   = [costof(s) for s in all_sp if resolved(s)             and costof(s) is not None]
    if logged: return sum(logged)/len(logged), "logged"
    if fwd:    return sum(fwd)/len(fwd),       "fwd~"
    if real:   return sum(real)/len(real),     "realized"  # last resort -- biases high (chased problems)
    return DEEMED_COST, "deemed"

af_mean = annuity_factor(DISCOUNT_R, GROWTH_G, SAT_HORIZON)
print("seven-dpt #2  reservation-value  (BAYESIAN; one-time cost vs compounding-SATURATING benefit)")
print("=" * 82)
print(f"  hit-rate Beta({a0:.2f},{b0:.2f}) [deemed {DEEMED_RATE:.0%}] | deemed windfall {DEEMED_MAG:.2f} | "
      f"deemed fwd-cost {DEEMED_COST:.2f}")
print(f"  pooled: {len(POOL_MAGS)} hits, {len(POOL_CTO)} logged / {len(POOL_FWD_COSTS)} inferred-fwd / {len(POOL_REAL_COSTS)} realized costs")
print(f"  stream: discount r={DISCOUNT_R:.0%}, growth g~{GROWTH_G:.0%} (wide), saturate T={SAT_HORIZON} "
      f"=> annuity factor ~{af_mean:.2f}x | draws {N_DRAWS} seed {SEED}")
print("-" * 82)

ranked = []
for pid in sorted(problems):
    all_sp = byp.get(pid, [])
    sp = [s for s in all_sp if resolved(s)]                       # resolved -> reward (hit/miss) side
    own_hits = [val(s) for s in sp if (val(s) or 0) > 0]
    hits, miss = len(own_hits), len(sp) - len(own_hits)
    cost_i, csrc = cost_to_open(all_sp)                           # FORWARD-preferring cost-to-open

    pv = []
    for _ in range(N_DRAWS):
        p = random.betavariate(a0 + hits, b0 + miss)              # posterior hit-rate from OWN data
        if random.random() < p:
            g = random.uniform(0.0, 2.0 * GROWTH_G)               # WIDE prior on g (refine from reuse later)
            pv.append(sample_magnitude(own_hits) * annuity_factor(DISCOUNT_R, g, SAT_HORIZON))
        else:
            pv.append(0.0)
    e_pv = sum(pv) / len(pv)
    pi   = e_pv / cost_i                                          # profitability index (ranking key)
    z    = reservation_value(pv, cost_i)                         # Pandora stop-value, now on the PV scale

    rate_prior_frac = PRIOR_STRENGTH / (PRIOR_STRENGTH + len(sp))
    mag_src = "own" if hits else ("pool" if POOL_MAGS else "prior")
    tag = ("EXPLORE(prior-led)" if not sp and not own_hits else f"prior~{rate_prior_frac:.0%} mag:{mag_src}")
    floored = z <= min(pv) - 1.0 + 1e-9
    ranked.append((pi, e_pv, z, pid, cost_i, csrc, hits, miss, tag, floored))

ranked.sort(reverse=True)                                         # by PROFITABILITY INDEX (unit-invariant)
print(f"  {'PI':>6}  {'E[PV]':>7}  {'z':>6}  {'cost':>5} {'src':>8}  {'#':>2} {'problem':32} {'h/m':>5}  domination")
for pi, e_pv, z, pid, cost_i, csrc, hits, miss, tag, floored in ranked:
    zf = f"{z:+.1f}" + ("*" if floored else "")
    print(f"  {pi:6.2f}  {e_pv:7.2f}  {zf:>6}  {cost_i:5.1f} {csrc:>8}  #{pid} {problems[pid]['title'][:32]:32} "
          f"{f'{hits}/{miss}':>5}  {tag}")
print("\n  RANK by PI (E[PV]/cost). Order is INVARIANT to the value<->cost exchange rate when (r,g,T) shared.")
print("  cost src: logged = costToOpen field | fwd~ = inferred from pending/tried | realized = fallback (biases high).")
print("  PI>1 / z-sign (absolute open-it bar) and g still need the exchange rate + reuse data to trust.")
