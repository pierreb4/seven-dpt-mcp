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


# ═══════════════════════════════════════════════════════════════════════════════
# SECOND COLUMN — REWORK (pre-registered 2026-09-09, BEFORE the 09-14 harvest)
# ═══════════════════════════════════════════════════════════════════════════════
"""Does a lower effort level cost correctness, not just thinking tokens?

WHY GIT AND NOT THE TRANSCRIPT
The first design counted an Edit-tool call that rewrote a line an earlier Edit-tool call in
the same session had written. It is unbuildable in this project: since 2026-08-25 there are
2418 Bash calls against 47 Edit and 42 Write, because auto mode makes edits with heredocs and
sed. A counter keyed on the Edit tool would have had a denominator of ~40 over three weeks.
Git sees every edit whatever tool made it, so the unit moves to the DELIVERED line.

THE UNIT
  REWORK LINE — a line added by commit A and removed or rewritten by a later commit B, where
  B lands within WINDOW days of A. A line that dies young is work that had to be done twice.
  rate(A) = rework lines / lines A added.

TURN-CLASS RESTRICTION (fixed now, not after seeing the numbers)
  Code only: *.py, *.sh. Markdown is excluded — prose is rewritten as a matter of course and
  its churn is not a defect, so including it would measure how much prose each arm wrote.
  This is the class that occurs at BOTH effort levels; commits outside it are not counted.

SURVIVORSHIP (the trap this design exists to avoid)
  The trial started 09-07, so on 09-14 a medium line has had days to die while a high line has
  had weeks. Comparing raw death rates would measure calendar, not effort. So every commit is
  given the SAME fixed exposure: only commits at least WINDOW days old are eligible, and only
  deaths within WINDOW days of birth count. Commits younger than WINDOW are excluded and
  reported, never partially credited.

ATTRIBUTION
  commit -> the assistant turn whose Bash command contains the commit subject -> that turn's
  `effort` field. Measured 84% (31/37) over the last two weeks. Unattributed commits are
  DROPPED AND PRINTED; they are never folded into either arm.

PRE-REGISTERED GATE — the reading is INSUFFICIENT unless each arm has >= MIN_COMMITS eligible
attributed commits AND >= MIN_LINES added code lines. Below that floor the output is "not
yet", never a rate. Above it, the ONLY pattern that counts as evidence effort buys correctness
is medium's rework rate exceeding high's by >= EFFECT x with non-overlapping 80% bootstrap
intervals over commits. Anything else reads NO DIFFERENCE. Effort is not randomized here —
the arms are a before/after inside one project, which holds task mix roughly but not exactly
constant; a difference that clears the gate is evidence, not proof.
"""
WINDOW = 3          # days of equal exposure given to every commit
MIN_COMMITS = 30    # per arm, eligible + attributed
MIN_LINES = 300     # per arm, added code lines
EFFECT = 1.5        # medium/high rework-rate ratio that counts
CODE = ('*.py', '*.sh')
REPO = os.path.expanduser('~/projects/seven-dpt-mcp')
import subprocess, datetime, random, re


def _git(*a):
    return subprocess.run(('git', '-C', REPO) + a, capture_output=True, text=True).stdout


def _blame_map(sha, path, _cache={}):
    """line number in <sha>:<path> -> commit that introduced that line."""
    key = (sha, path)
    if key not in _cache:
        m, cur = {}, None
        for ln in _git('blame', '--porcelain', sha, '--', path).split('\n'):
            h = re.match(r'^([0-9a-f]{40}) \d+ (\d+)', ln)
            if h: m[int(h.group(2))] = h.group(1)[:12]
        _cache[key] = m
    return _cache[key]


def rework(since):
    now = datetime.datetime.now(datetime.timezone.utc)
    commits = []                                  # (sha, when, subject)
    for ln in _git('log', '--no-merges', f'--since={since}', '--format=%H|%cI|%s',
                   '--', *CODE).strip().split('\n'):
        if ln:
            h, ci, sub = ln.split('|', 2)
            commits.append((h, datetime.datetime.fromisoformat(ci), sub))
    born = {h: 0 for h, _, _ in commits}          # added code lines, by commit
    died = collections.Counter()                  # rework lines charged to the commit that wrote them
    for sha, t, _ in commits:
        parent = sha + '^'
        path, old = None, 0
        for ln in _git('show', '-M', '--unified=0', '--format=', sha,
                       '--', *CODE).split('\n'):
            if ln.startswith('--- '):
                # blame runs on the PARENT, so the parent-side path is the one that matters;
                # a new file is `--- /dev/null` and has no parent line to charge anything to.
                path = ln[6:] if ln.startswith('--- a/') else None
            elif ln.startswith('@@'):
                m = re.match(r'@@ -(\d+)', ln)
                old = int(m.group(1)) if m else 0
            elif ln.startswith('+') and not ln.startswith('+++'):
                born[sha] += 1
            elif ln.startswith('-') and not ln.startswith('---') and path:
                src = _blame_map(parent, path).get(old)
                old += 1
                if src:
                    for h2, t2, _ in commits:     # charge only if the dead line was young
                        if h2.startswith(src) and 0 <= (t - t2).days < WINDOW:
                            died[h2] += 1
                            break
    # effort per commit, via the turn that ran the commit
    turns = []
    for p in glob.glob(f'{ROOT}/*.jsonl'):
        for line in open(p, errors='replace'):
            try: d = json.loads(line)
            except Exception: continue
            if d.get('type') != 'assistant': continue
            for b in d['message'].get('content', []):
                if isinstance(b, dict) and b.get('type') == 'tool_use' and b['name'] == 'Bash' \
                   and 'git commit' in b['input'].get('command', ''):
                    turns.append((d.get('effort'), b['input']['command']))
    arms, unattributed, young = collections.defaultdict(list), 0, 0
    for sha, t, sub in commits:
        if (now - t).days < WINDOW:
            young += 1; continue                  # not yet fully exposed — never half-credited
        eff = next((e for e, c in turns if e and sub[:40] in c), None)
        if not eff:
            unattributed += 1; continue
        arms[eff].append((born[sha], died[sha]))

    def rate(rs):
        b = sum(x for x, _ in rs)
        return (sum(y for _, y in rs) / b) if b else float('nan')

    def ci(rs, n=2000):
        if not rs: return (float('nan'), float('nan'))
        s = sorted(rate([random.choice(rs) for _ in rs]) for _ in range(n))
        return s[int(.10 * n)], s[int(.90 * n)]

    print(f'\nREWORK  code lines ({"/".join(CODE)}) added by a commit and killed within '
          f'{WINDOW}d, by authoring effort')
    print(f'{"effort":8}{"commits":>9}{"added":>8}{"rework":>8}{"rate":>8}{"80% CI":>16}')
    for eff, rs in sorted(arms.items(), key=lambda kv: -len(kv[1])):
        lo, hi = ci(rs)
        print(f'{eff:8}{len(rs):9}{sum(x for x, _ in rs):8}{sum(y for _, y in rs):8}'
              f'{100 * rate(rs):7.1f}%{f"{100*lo:.1f}-{100*hi:.1f}%":>16}')
    print(f'  excluded: {young} commit(s) younger than {WINDOW}d (not yet exposed), '
          f'{unattributed} with no attributable turn')
    m, h = arms.get('medium', []), arms.get('high', [])
    short = [f'{e}: {len(a)}c/{sum(x for x,_ in a)}L' for e, a in (('medium', m), ('high', h))
             if len(a) < MIN_COMMITS or sum(x for x, _ in a) < MIN_LINES]
    if short:
        print(f'  VERDICT: INSUFFICIENT — floor is {MIN_COMMITS} commits and {MIN_LINES} '
              f'added lines per arm; short: {", ".join(short)}. Not a rate. Wait.')
    else:
        mlo, mhi = ci(m); hlo, hhi = ci(h)
        diff = rate(m) >= EFFECT * rate(h) and mlo > hhi
        print(f'  VERDICT: {"DIFFERENCE" if diff else "NO DIFFERENCE"} — medium/high = '
              f'{rate(m)/rate(h):.2f}x (gate: >= {EFFECT}x AND disjoint 80% intervals)')


# Rework reads FURTHER BACK than the thinking-share table on purpose: every commit gets the
# same fixed exposure either way, so extra history only adds fully-exposed commits to the
# high arm. It cannot flatter medium, which cannot predate the 09-07 switch.
rework('2026-07-15')
