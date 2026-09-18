#!/usr/bin/env python3
"""Spark #82 PRICE, run before any build (2026-09-18): can a 2^(6-2) screen of the six
SessionStart injections (16 cells x >=3 sessions = 48) resolve a main effect on its outcomes?
Prints, per outcome, the between-session spread since 08-31 and the minimum detectable main
effect at 48 sessions (24 v 24, 2.8 se), next to the MECHANICAL ceiling on resident/turn:
the total SessionStart injection size, which is all the static carry that toggling can remove.
First read: all six injections together ~9.9k chars (~2.5k tok) against an MDE of ~34k tok on
resident/turn — ceiling 14x under the bar; think share MDE 8.0 pts (the effort level itself
moved 14.4); turns/session MDE 119 > the mean 117. REWORK died with the effort trial (d9003cd).
Main transcripts only; sessions with < 5 assistant turns dropped.
"""
import glob, json, os, statistics as st, collections
ROOT = os.path.expanduser('~/.claude/projects/-home-pierre-projects-seven-dpt-mcp')
S = collections.defaultdict(lambda: dict(turns=0, out=0, th=0, thout=0, res=[], first=None, inj=0))
for p in glob.glob(f'{ROOT}/*.jsonl'):
    for line in open(p, errors='replace'):
        try: d = json.loads(line)
        except Exception: continue
        ts = d.get('timestamp', '')
        if ts < '2026-08-31': continue
        sid = d.get('sessionId'); s = S[sid]
        if s['first'] is None or ts < s['first']: s['first'] = ts
        # SessionStart injection size: hook attachments / additionalContext
        if d.get('type') in ('attachment', 'system') or 'hook' in json.dumps(d.get('attachment', ''))[:200].lower():
            a = d.get('attachment') or {}
            if 'SessionStart' in json.dumps(a)[:400] or a.get('hookEvent') == 'SessionStart':
                s['inj'] += len(json.dumps(a.get('content', a)))
        if d.get('type') != 'assistant': continue
        u = d['message'].get('usage') or {}
        out = u.get('output_tokens', 0)
        if not out: continue
        s['turns'] += 1; s['out'] += out
        th = (u.get('output_tokens_details') or {}).get('thinking_tokens')
        if th is not None: s['th'] += th; s['thout'] += out
        s['res'].append(u.get('cache_read_input_tokens', 0))
ss = [v for v in S.values() if v['turns'] >= 5]
print('sessions (>=5 turns) since 08-31:', len(ss), ' of', len(S))
days = collections.Counter(v['first'][:10] for v in ss)
print('sessions/day: median', st.median(days.values()), ' active days', len(days), ' span', min(days), max(days))
def desc(name, xs):
    xs = [x for x in xs if x is not None]
    m, sd = st.mean(xs), st.stdev(xs)
    q = st.quantiles(xs, n=4)
    print(f'{name:16} n={len(xs):3} mean={m:10.1f} sd={sd:10.1f} cv={sd/m:5.2f}  q1/med/q3={q[0]:.1f}/{q[1]:.1f}/{q[2]:.1f}   MDE(48 sess, 24v24, 2.8se)={2.8*sd*(4/48)**.5:10.1f}')
desc('resident/turn', [st.median(v['res']) for v in ss])
desc('think share %', [100*v['th']/v['thout'] if v['thout'] else None for v in ss])
desc('turns/session', [v['turns'] for v in ss])
inj = [v['inj'] for v in ss if v['inj']]
if inj: desc('SessionStart inj chars', inj)
else: print('no SessionStart attachment sizes found in transcripts')
