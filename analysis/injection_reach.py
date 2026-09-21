#!/usr/bin/env python3
"""Spark #86 REACH AUDIT (successor to #82, closed unrun 2026-09-21): is each SessionStart
injection ever referenced by the session that carries it? Zero agents; reruns anywhere.

Unit = one INJECTION EVENT (a SessionStart firing: startup/resume/clear/compact) plus the main-
transcript records up to the next firing, kept when that window holds >= 5 assistant turns.
Group = the hook COMMAND on the transcript's own hook_success record (A-F are #82's six factors;
G insights-digest.py was wired 09-17, after #82 was captured).
Token = a distinctive string in the group's model-visible text: commit hash, #NN id, filename,
release/hf row id, 3+-part slug. Tokens also present in that session's instructions attachment
(CLAUDE.md + MEMORY.md) are dropped — the injection is not their only source.
CLEAN echo = the token's first appearance after the injection is in ASSISTANT output (text,
thinking, tool_use input). If a user prompt or a tool_result shows it first, it is tainted and
never counts: lower bound. ANY echo ignores taint: upper bound.
Pre-registered read (spark #86 forbids): max-min CLEAN echo rate across groups < 15 pts = the
table is flat, echo does not discriminate. Specimens (3/group, seeded) are for the hand-read:
> 1/3 coincidental of 18 abandons the mechanical frame.
AMENDED after the first run's hand-read (2026-09-21; descriptive columns, the registered read
stays on the CLEAN event rate): (1) a token carried by two groups in one event is dropped from
both — the first run's only G specimen, c7d77f6, was the handoff sheet's token; (2) tok% = clean-
echoed tokens / tokens carried, pooled, because F carries ~18 tokens an event and D ~3, so event
rates reward bulk; (3) LATE = a clean echo past the 3rd assistant turn — the opening "anything
for my attention" relay is reach to Pierre, a later echo is reach into the work.
"""
import glob, json, os, random, re, statistics as st, collections

ROOT = os.path.expanduser('~/.claude/projects/-home-pierre-projects-seven-dpt-mcp')
SINCE = '2026-08-31'
MIN_TURNS = 5
GROUPS = [('A atelier', 'announce-all.sh'), ('B watch', 'watch.sh'), ('C seven-dpt', '--digest'),
          ('D distill', 'distill.sh'), ('E distill-missed', 'distill-missed.sh'),
          ('F handoff', 'handoff-check.py'), ('G insights', 'insights-digest.py')]
TOKEN_RES = [
    re.compile(r'(?<![\w-])(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,10}(?![\w-])'),   # commit hash
    re.compile(r'(?<!\w)#\d{2,3}(?!\d)'),                                                # spark/problem id
    re.compile(r'[\w-]+\.(?:py|sh|md|jsonl|json|yaml|ts|log|timer|gz)(?![\w])'),          # filename (basename)
    re.compile(r'(?:release|hf-model|hf-dataset|arxiv|repo):[^\s,;)]+'),                  # watch row id
    re.compile(r'(?<![\w-])[a-z][a-z0-9]*(?:-[a-z0-9]+){2,}(?![\w-])'),                   # 3+-part slug
]


def group_of(cmd):
    for name, key in GROUPS[::-1]:          # distill-missed.sh before distill.sh
        if key in cmd: return name
    return None


def visible(att):
    """Model-visible text of one hook_success record: additionalContext if the hook spoke JSON, else stdout."""
    out = att.get('stdout') or att.get('content') or ''
    try:
        j = json.loads(out)
        h = j.get('hookSpecificOutput') or {}
        return h.get('additionalContext') or j.get('additionalContext') or ''
    except Exception:
        return out if isinstance(out, str) else ''


def tokens(text):
    return {m.group(0) for rx in TOKEN_RES for m in rx.finditer(text)}


def blocks(msg):
    """Yield (role_kind, text) per content block: 'a' assistant-authored, 'u' user/tool-authored."""
    c = msg.get('content')
    role = msg.get('role')
    if isinstance(c, str):
        yield ('a' if role == 'assistant' else 'u'), c; return
    for b in c or []:
        t = b.get('type')
        if t in ('text', 'thinking'): yield ('a' if role == 'assistant' else 'u'), b.get(t) or ''
        elif t == 'tool_use': yield 'a', f"{b.get('name')} " + json.dumps(b.get('input'), ensure_ascii=False)
        elif t == 'tool_result':
            r = b.get('content')
            yield 'u', r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)


events = []          # dict(sid, ts, inj={group: text}, instr=str, recs=[(kind, text)], turns=int)
for p in sorted(glob.glob(f'{ROOT}/*.jsonl')):
    cur, instr, last_tuid = None, '', None
    for line in open(p, errors='replace'):
        try: d = json.loads(line)
        except Exception: continue
        if d.get('isSidechain') or d.get('timestamp', '9') < SINCE: continue
        a = d.get('attachment') if isinstance(d.get('attachment'), dict) else {}
        if a.get('type') == 'hook_success' and a.get('hookEvent') == 'SessionStart':
            if a.get('toolUseID') != last_tuid:                 # a new firing opens a new event
                cur = dict(sid=d.get('sessionId', '')[:8], ts=d.get('timestamp', ''), inj={}, recs=[], turns=0, instr=instr)
                events.append(cur); last_tuid = a.get('toolUseID')
            g = group_of(a.get('command', ''))
            if g: cur['inj'][g] = cur['inj'].get(g, '') + visible(a)
            continue
        if a.get('type') == 'instructions':
            instr = json.dumps(a.get('files'), ensure_ascii=False)
            if cur: cur['instr'] = instr
            continue
        if cur is None or d.get('type') not in ('user', 'assistant'): continue
        if d['type'] == 'assistant': cur['turns'] += 1
        cur['recs'].extend((k, cur['turns'], b) for k, b in blocks(d.get('message') or {}))

FALLBACK = ''.join(open(os.path.expanduser(f), errors='replace').read() for f in
                   ('~/.claude/CLAUDE.md', f'{ROOT}/memory/MEMORY.md') if os.path.exists(os.path.expanduser(f)))
kept = [e for e in events if e['turns'] >= MIN_TURNS]
print(f'injection events since {SINCE}: {len(events)}; kept (>= {MIN_TURNS} assistant turns): {len(kept)} '
      f'over {len({e["sid"] for e in kept})} sessions; instructions attachment present in '
      f'{sum(1 for e in kept if e["instr"])} (else on-disk CLAUDE.md+MEMORY.md as the exclusion set)')

rows = collections.defaultdict(lambda: dict(n=0, empty=0, chars=[], ntok=[], clean=0, anyecho=0, late=0, tokhit=0, spec=[]))
for e in kept:
    excl = e['instr'] or FALLBACK
    carried = collections.Counter(t for text in e['inj'].values() for t in tokens(text))
    for g, text in e['inj'].items():
        r = rows[g]
        toks = {t for t in tokens(text) if t not in excl and carried[t] == 1}
        if not text.strip() or not toks:
            r['empty'] += 1; continue
        r['n'] += 1; r['chars'].append(len(text)); r['ntok'].append(len(toks))
        tainted, clean, anyhit, echoed, late = set(), None, False, set(), False
        for kind, turn, body in e['recs']:
            hit = [t for t in toks if t in body]
            if not hit: continue
            if kind == 'u': tainted.update(hit); continue
            anyhit = True
            fresh = [t for t in hit if t not in tainted]
            echoed.update(fresh); late = late or (bool(fresh) and turn > 3)
            if fresh and clean is None:
                t = sorted(fresh)[0]
                ln = next(l for l in body.split('\n') if t in l)
                i = ln.find(t)
                clean = (e['sid'], e['ts'][:10], t, ln[max(0, i - 70): i + 90].strip())
        r['anyecho'] += anyhit; r['late'] += late; r['tokhit'] += len(echoed)
        if clean: r['clean'] += 1; r['spec'].append(clean)

print(f'\n{"group":<18}{"events":>7}{"no-tok":>7}{"chars~":>8}{"tok~":>6}{"CLEAN":>7}{"rate":>7}{"ANY":>6}{"rate":>7}{"LATE":>6}{"rate":>7}{"tok%":>7}')
rates = {}
for name, _ in GROUPS:
    r = rows.get(name)
    if not r or not r['n']:
        print(f'{name:<18}{0:>7}{(r or {}).get("empty", 0):>7}   (no event with an eligible token)'); continue
    rates[name] = 100 * r['clean'] / r['n']
    print(f'{name:<18}{r["n"]:>7}{r["empty"]:>7}{st.median(r["chars"]):>8.0f}{st.median(r["ntok"]):>6.0f}'
          f'{r["clean"]:>7}{rates[name]:>6.0f}%{r["anyecho"]:>6}{100 * r["anyecho"] / r["n"]:>6.0f}%'
          f'{r["late"]:>6}{100 * r["late"] / r["n"]:>6.0f}%{100 * r["tokhit"] / sum(r["ntok"]):>6.0f}%')

# C's ask is an ACTION, not a token: "run the `evoke` tool ... and `capture_spark` any genuine hit"
cev = [e for e in kept if 'C seven-dpt' in e['inj']]
for tool in ('mcp__seven-dpt__evoke', 'mcp__seven-dpt__capture_spark'):
    k = sum(any(kind == 'a' and body.startswith(tool + ' ') for kind, _, body in e['recs']) for e in cev)
    print(f'C ask followed: {tool.split("__")[-1]:<14} called in {k}/{len(cev)} events ({100 * k / len(cev):.0f}%)')

rng = random.Random(86)
print('\nSPECIMENS (seeded, 3/group) — sid date token | raw echoing line')
for name, _ in GROUPS:
    sp = rows.get(name, {}).get('spec', [])
    for s in rng.sample(sp, min(3, len(sp))):
        print(f'  {name[:1]} {s[0]} {s[1]} {s[2]:<28.28} | {s[3]}')

powered = {g: v for g, v in rates.items() if rows[g]['n'] >= 10}
if len(powered) >= 2:
    spread = max(powered.values()) - min(powered.values())
    print(f'\nREAD (groups with >= 10 events: {len(powered)}): CLEAN echo spread {spread:.0f} pts '
          f'({min(powered, key=powered.get)} {min(powered.values()):.0f}% .. {max(powered, key=powered.get)} {max(powered.values()):.0f}%) '
          f'-> {"FLAT: forbidden table, echo does not discriminate" if spread < 15 else "SEPARATES: hand-read the specimens before naming a candidate"}; '
          f'kept events {len(kept)} vs floor 40 -> {"ok" if len(kept) >= 40 else "UNDER FLOOR, no verdict"}')
else:
    print('\nREAD: fewer than 2 groups with >= 10 events — no verdict')
