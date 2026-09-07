#!/usr/bin/env python3
"""Effort trial harvest (2026-09-07): seven-dpt desk sessions run at effortLevel=medium
(project .claude/settings.json), every other project stays at the global high.

PRE-REGISTERED READ (harvest on 2026-09-14 or once medium has >= 200 turns, whichever first):
  thinking share = thinking_tokens / output_tokens, per assistant turn, grouped by
  (effort, model). Also turns per session (does medium need MORE turns to finish?)
  and resident context (cache_read) per turn — the actual bill.
  CLEARS if medium's thinking share is lower AND turns/session did not rise > 1.3x.
  Quality is Pierre's read, not this script's — it prints the mechanism, not a verdict
  on correctness.
Scans main transcripts AND <session>/subagents/agent-*.jsonl (the 09-06 blind spot).
"""
import glob, json, os, statistics as st, sys, collections
ROOT = os.path.expanduser('~/.claude/projects/-home-pierre-projects-seven-dpt-mcp')
SINCE = sys.argv[1] if len(sys.argv) > 1 else '2026-08-31'
rows = []
for p in glob.glob(f'{ROOT}/*.jsonl') + glob.glob(f'{ROOT}/*/subagents/*.jsonl'):
    for line in open(p, errors='replace'):
        try: d = json.loads(line)
        except Exception: continue
        if d.get('type') != 'assistant' or d.get('timestamp', '') < SINCE: continue
        u = d['message'].get('usage') or {}
        out = u.get('output_tokens', 0)
        if not out: continue
        th = (u.get('output_tokens_details') or {}).get('thinking_tokens')
        rows.append((d.get('effort', '?'), d['message'].get('model', '?'), d.get('sessionId'),
                     out, th, u.get('cache_read_input_tokens', 0), '/subagents/' in p))
g = collections.defaultdict(list)
for r in rows: g[(r[0], r[1].replace('claude-', ''))].append(r)
print(f'seven-dpt assistant turns since {SINCE}: {len(rows)}  (effort x model)')
print(f'{"effort":8}{"model":16}{"turns":>7}{"sess":>6}{"turns/sess":>11}{"think/turn":>11}{"out/turn":>9}{"think%":>8}{"resident/turn":>14}{"agent%":>7}')
for (e, m), rs in sorted(g.items(), key=lambda kv: -len(kv[1])):
    sess = len({r[2] for r in rs}); th = [r[4] for r in rs if r[4] is not None]
    outs = [r[3] for r in rs]
    share = (sum(th) / sum(r[3] for r in rs if r[4] is not None)) if th else float('nan')
    print(f'{e:8}{m:16}{len(rs):7}{sess:6}{len(rs)/sess:11.1f}'
          f'{(st.mean(th) if th else float("nan")):11.0f}{st.mean(outs):9.0f}{100*share:7.1f}%'
          f'{st.mean(r[5] for r in rs):14.0f}{100*sum(r[6] for r in rs)/len(rs):6.0f}%')
med = [r for r in rows if r[0] == 'medium']
print(f'\nmedium turns so far: {len(med)}  (harvest at >= 200 or on 2026-09-14)')
