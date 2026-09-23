#!/usr/bin/env python3
"""Credit reality check (2026-09-23): which per-token weighting predicts the usage page?

The meters (tokmeter.py, budget.py) price tokens at API list rates, but what binds is the
plan's weekly pools as the usage page reports them (budget/spend.jsonl readings: all-models
% and the Fable %). API $ are only worth quoting if they move WITH those percentages, so
each weighting hypothesis is scored against the readings, not against a price table.

Model: inside one weekly window the pool starts at 0 at (reset - 168h), so a reading's
pct = cumulative weighted burn since window start / K. K is fit per window through the
origin; a weighting that tracks reality gives a high R^2 inside each window AND a K that
holds across windows (the pool size has no reason to move week to week absent a launch).

Usage is deduplicated on (message.id, requestId), keep-max per field: a transcript writes
one line per content block, each repeating the usage (budget.py _iter_usage, checked vs
ccusage). The raw/dedup ratio is printed: tokmeter did NOT dedup until 09-23 (fixed there).

  credit_reality.py            fit + table

INCREMENT FIT: R^2 on cumulative curves cannot separate the hypotheses (every monotone
weighting scores >= 0.99), so the weights are also fit FREE on the increments between
consecutive readings (6h cadence since 09-14): d_pct = a*cr + b*cw + c*out, each field
in $ at the family's BASE input rate (so API list = cr 0.1, cw 1.25-2, out 5 -> cr/out
0.02; the skill's fable-5-1 row = 0.005). Non-negative LS; bootstrap over increments for
the interval, because a ratio off ~40 integer-rounded readings is noise until shown not.
"""
import glob, json, os, collections, datetime as dt
import numpy as np
from scipy.optimize import nnls

LEDGER = os.path.expanduser('~/.claude/budget/spend.jsonl')
GLOBS = ['~/.claude/projects/*/*.jsonl', '~/.claude/projects/*/*/subagents/*.jsonl',
         '~/.claude/projects/*/*/subagents/workflows/*/agent-*.jsonl']
SINCE = '2026-09-06T00:00:00Z'
F = ('in', 'cw5', 'cw1', 'cr', 'out')

def iso(t): return dt.datetime.strptime(t[:19], '%Y-%m-%dT%H:%M:%S')

def load_usage():
    best, raw = {}, collections.Counter()
    for g in GLOBS:
        for p in glob.glob(os.path.expanduser(g)):
            if os.path.getmtime(p) < iso(SINCE).timestamp() - 86400: continue
            for line in open(p, errors='replace'):
                if '"usage"' not in line: continue
                try: o = json.loads(line)
                except Exception: continue
                m = o.get('message') or {}; u = m.get('usage') or {}
                ts = str(o.get('timestamp', ''))
                if not u or ts < SINCE: continue
                cw = u.get('cache_creation_input_tokens', 0)
                cw5 = (u.get('cache_creation') or {}).get('ephemeral_5m_input_tokens', 0)
                v = dict(zip(F, (u.get('input_tokens', 0), cw5, cw - cw5,
                                 u.get('cache_read_input_tokens', 0), u.get('output_tokens', 0))))
                mdl = str(m.get('model', '?')).replace('claude-', '')
                for k in F: raw[k] += v[k]
                key = (m.get('id'), o.get('requestId'))
                if not all(key): key = (p, ts, len(best))
                if key in best:
                    b = best[key][2]
                    for k in F: b[k] = max(b[k], v[k])
                else:
                    best[key] = (ts, mdl, v)
    ev = sorted(best.values(), key=lambda e: e[0])
    ded = collections.Counter()
    for _, _, v in ev:
        for k in F: ded[k] += v[k]
    return ev, raw, ded

def readings():
    rows = [json.loads(l) for l in open(LEDGER) if l.strip()]
    void = {t for r in rows if r.get('event') == 'reading-void' for t in r.get('ts_voided', [])}
    out = []
    for r in rows:
        if r.get('lane') != 'claude' or r['ts'] in void or r['ts'] < SINCE: continue
        if r.get('weekly_resets_in_h') is None or r.get('weekly_all_pct') is None: continue
        reset = iso(r['ts']) + dt.timedelta(hours=r['weekly_resets_in_h'])
        reset = reset.replace(minute=0, second=0) + dt.timedelta(hours=reset.minute >= 30)
        out.append((r['ts'], reset, r['weekly_all_pct'], r['weekly_model_pct']))
    return out

def fam(m):
    for f in ('fable-5-1', 'fable', 'opus-5-5', 'opus', 'sonnet', 'haiku'):
        if f in m: return f
    return 'other'

# $/MTok per field (in, cw5m, cw1h, cr, out). API = list rates as tokmeter carries them.
def api(b, cr=None): return (b, b * 1.25, b * 2, b * 0.1 if cr is None else cr, b * 5)
API = {'fable-5-1': api(10), 'fable': api(10), 'opus-5-5': api(4, 0.2), 'opus': api(5),
       'sonnet': api(2), 'haiku': api(1), 'other': api(5)}
HYP = {
    'H0 api, fable-5-1 cr 1.00 (tokmeter to 09-23)': API,
    'H1 api, fable-5-1 cr 0.25 (pricing page)': {**API, 'fable-5-1': api(10, 0.25)},
    'H2 cache reads FREE (cr 0)': {k: v[:3] + (0,) + v[4:] for k, v in API.items()},
    'H3 output only': {k: (0, 0, 0, 0, v[4]) for k, v in API.items()},
    'H4 budget.py uniform (1,1.25,1.25,0.1,5)': {k: (1, 1.25, 1.25, 0.1, 5) for k in API},
}

def cum(ev, t0, t1, keep):
    agg = collections.defaultdict(collections.Counter)
    for ts, m, v in ev:
        if ts < t0: continue
        if ts >= t1: break
        f = fam(m)
        if keep(f):
            for k in F: agg[f][k] += v[k]
    return agg

def cost(agg, rates):
    return sum(agg[f][k] * rates[f][i] for f in agg for i, k in enumerate(F)) / 1e6

def fit(pts):
    """pct = c / K through the origin -> (K, R^2 about zero-intercept line, rmse pct)."""
    sxx = sum(c * c for c, _ in pts); sxy = sum(c * y for c, y in pts)
    if not sxx: return None
    a = sxy / sxx
    res = [y - a * c for c, y in pts]
    tot = sum((y - sum(p for _, p in pts) / len(pts)) ** 2 for _, y in pts) or 1
    return 1 / a, 1 - sum(r * r for r in res) / tot, (sum(r * r for r in res) / len(res)) ** .5

def main():
    ev, raw, ded = load_usage()
    print(f"usage since {SINCE}: {len(ev)} deduped responses")
    print("raw/dedup (tokmeter-style overcount): " +
          "  ".join(f"{k} x{raw[k] / ded[k]:.2f}" for k in F if ded[k]))
    rs = readings()
    wins = collections.defaultdict(list)
    for ts, reset, a, m in rs: wins[reset].append((ts, a, m))
    wins = {w: v for w, v in wins.items() if len(v) >= 3}
    tf = lambda t: t.strftime('%Y-%m-%dT%H:%M:%SZ')
    pools = [('FABLE pool', 3, lambda f: f.startswith('fable')), ('ALL-MODELS pool', 2, lambda f: True)]
    table = {}
    for w, rr in sorted(wins.items()):
        t0 = tf(w - dt.timedelta(hours=168))
        agg = cum(ev, t0, tf(w), lambda f: True)
        mix = {f: round(cost({f: agg[f]}, API)) for f in agg}
        print(f"\nWINDOW {t0[:13]} -> {tf(w)[:13]}  {len(rr)} readings  H0-$ by family: {mix}")
        fb = agg.get('fable-5-1', {}); f5 = agg.get('fable', {})
        print(f"  fable-5-1 cr {fb.get('cr', 0) / 1e6:.0f}M  fable-5 cr {f5.get('cr', 0) / 1e6:.0f}M")
        for pname, col, keep in pools:
            pts_by_h = {h: [] for h in HYP}
            for ts, a, m in rr:
                y = (None, None, a, m)[col]
                if y is None: continue
                c = cum(ev, t0, ts, keep)
                for h, rates in HYP.items(): pts_by_h[h].append((cost(c, rates), y))
            for h, pts in pts_by_h.items():
                r = fit(pts)
                if r: table.setdefault((pname, h), []).append((t0[:10], *r, len(pts)))
    increments(ev, wins, pools, tf)
    for pname, _, _ in pools:
        print(f"\n{pname}: K = weighted $ per 1% (per window), R^2, rmse in pct points")
        for h in HYP:
            rows = table.get((pname, h), [])
            ks = [k for _, k, *_ in rows]
            spread = (max(ks) / min(ks)) if ks and min(ks) > 0 else float('nan')
            cells = "  ".join(f"{d}: K={k:7.1f} R2={r2:.3f} rmse={e:4.1f} n={n}" for d, k, r2, e, n in rows)
            print(f"  {h:44} K max/min x{spread:4.2f} | {cells}")

BASE = {'fable-5-1': 10, 'fable': 10, 'opus-5-5': 4, 'opus': 5, 'sonnet': 2, 'haiku': 1, 'other': 5}

def feats(agg):
    """(cr, cw, out) in $-at-base-input-rate; input tokens ride with cw (both prompt-side, <0.5%)."""
    x = np.zeros(3)
    for f, a in agg.items():
        b = BASE[f] / 1e6
        x += b * np.array([a['cr'], a['cw5'] + a['cw1'] + a['in'], a['out']])
    return x

def increments(ev, wins, pools, tf):
    rng = np.random.default_rng(0)
    for pname, col, keep in pools:
        X, Y, W = [], [], []
        for w, rr in sorted(wins.items()):
            t_prev, y_prev = tf(w - dt.timedelta(hours=168)), 0
            for ts, a, m in sorted(rr):
                y = (None, None, a, m)[col]
                if y is None: continue
                X.append(feats(cum(ev, t_prev, ts, keep))); Y.append(y - y_prev); W.append(t_prev[:10])
                t_prev, y_prev = ts, y
        X, Y = np.array(X), np.array(Y, float)
        coef, _ = nnls(X, Y)
        pred = X @ coef
        boot = []
        for _ in range(2000):
            i = rng.integers(0, len(Y), len(Y))
            c, _ = nnls(X[i], Y[i])
            if c[2] > 0: boot.append(c[0] / c[2])
        lo, med, hi = np.percentile(boot, [5, 50, 95])
        sh = X.sum(0) / X.sum()
        print(f"\n{pname} INCREMENT FIT  n={len(Y)} increments  rmse {np.sqrt(np.mean((Y - pred) ** 2)):.2f} pct")
        print(f"  pct per $-at-base: cr {coef[0]:.4f}  cw {coef[1]:.4f}  out {coef[2]:.4f}")
        print(f"  cr/out = {coef[0] / coef[2] if coef[2] else float('nan'):.4f}  (boot 90%: {lo:.4f} .. {hi:.4f}, median {med:.4f})"
              f"   API list 0.0200 · skill fable-5-1 0.0050")
        print(f"  cw/out = {coef[1] / coef[2] if coef[2] else float('nan'):.3f}   API list 0.25 (5m) .. 0.40 (1h)")
        print(f"  field share of base-$ volume: cr {sh[0]:.2f} cw {sh[1]:.2f} out {sh[2]:.2f}")

if __name__ == '__main__':
    main()
