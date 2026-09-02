#!/usr/bin/env python3
"""DECLARED-UNRELIABLE REGISTER + gate scanner (spark #54).

The founding incident: in the same hour the memory line "ts is a hand-stamped nominal
label, authority order is file order > git blame > ts" was written, a brand-new legality
gate was keyed to `ts >= "2026-09-01"` — and the anchor date was itself one of five
+1-day typos, so the gate was calibrated on the exact error class it existed to police.
Pierre caught it by reading the clock; no instrument did.

The failure is NOT ignorance. The caveat was written down, in a file loaded at session
start. What was missing is an EXECUTION PATH from a declared caveat into the moment a new
gate is authored. Problem #6's founding lesson applies: three advice-shaped remedies
failed and the structural one held, so "know your unreliable fields" only counts if
something READS the register.

Each entry names a field-class this project has already paid to learn is unreliable, AND
the discriminator that keeps the rule from degenerating into "avoid this field". That
second half is load-bearing: a register that flags arc's budget.py staleness check --
which keys on a ts the program writes at append time -- has learned "avoid ts" rather
than "avoid a HAND-STAMPED ts", which is the wrong rule and the one that gets the whole
register ignored.

Scope note (measured, not assumed): the two parsers named in spark #54's next-step hold
only ONE of the four banked incidents. The other three live in self_check.py and in
seven-dpt's own spark wakeConditions. A register scoped to where we assumed gates are
authored would have scored 1/4 and been abandoned for a scope error.

Usage:
    unreliable_register.py [paths...]     # default: analysis/*.py + the spark store
    unreliable_register.py --json
"""
import ast, json, os, sys, re

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.expanduser("~/.local/share/seven-dpt/store.json")

# ── THE REGISTER ─────────────────────────────────────────────────────────────
# Four entries, each a caveat this project has already banked. `exempt_when` is the
# discriminator; it is stated for every entry because an entry without one is a ban.
REGISTER = {
    "hand-stamped-ts": {
        "fields": {"ts", "date"},
        "why": "dialect-3: on unmarked lines `ts` is a NOMINAL LABEL typed by hand; "
               "authority order is file order > git blame > ts. Five +1-day typos on record.",
        "exempt_when": "the value is MACHINE-stamped — the reader guards on `stamp`/"
                       "is_marked()/era_boundary(), or the module writes the field itself "
                       "from a clock (arc/scripts/budget.py, ledger_append.py).",
    },
    "prose": {
        "fields": {"note", "why", "result", "observed", "criterion", "change", "status",
                   "why_held", "evidence"},
        "why": "free text. A gate keyed to prose is keyed to one author's WORDING: the "
               "alert-honesty check regexed a single phrasing and was pinned green for "
               "weeks while two alerts made the exact false claim it existed to catch.",
        "exempt_when": "the read goes through a DECLARED token — a head word checked "
                       "against STATUS_HEADS / OUTCOME_DECLARED / KIND_TOKENS, or an "
                       "explicitly structured channel (alert_claims, acknowledges).",
    },
    "entry-count-as-quantity": {
        "fields": set(),          # structural, not field-named — see scan_store/_count_gate
        "why": "an entry COUNT is a correlate of the quantity you mean, never the quantity. "
               "Spark #50 woke at 12 arms with >=2 priced entries; only 2 had ever CHANGED "
               "the prior. Spark #49 woke on curve n three times for a nested-pair question.",
        "exempt_when": "the count IS the reported quantity (a tally printed as a tally), or "
                       "a `manual` atom sits alongside naming the substantive bar.",
    },
    "single-disposition-carrier": {
        "fields": {"outcome", "resolution", "result"},
        "why": "read-one-carrier has bitten FOUR times in ledger_invariants.py. A line "
               "carries its disposition on any of `outcome`/`resolution`/`result`; a reader "
               "that consults one and asserts about the line is asserting past its evidence.",
        "exempt_when": "the enclosing function reads >=2 of the three carriers, or delegates "
                       "to verdict_of()/disposition()/outcome_word()/result_field().",
    },
}

_MACHINE_GUARDS = ("stamp", "is_marked", "era_boundary", "machine")
# A gate INSIDE a check that exists to police ts is the remedy, not the disease. Narrow on
# purpose: named tripwires only, so it cannot become a blanket "anything mentioning ts".
_TS_POLICE = ("ts_disorder", "future_ts", "ts-correction", "_ts_seen", "ts_typo")
_DECLARED_TOKENS = ("STATUS_HEADS", "OUTCOME_DECLARED", "KIND_TOKENS", "EVENT_TOKENS",
                    "_HEADS", "_head_word", "alert_claims", "acknowledges", "alert_class")
_CARRIER_HELPERS = ("verdict_of", "disposition", "outcome_word", "result_field",
                    "event_class", "status_class", "outcome_class")
_COUNT_SUBJECTS = ("entr", "priced", "line", "spark", "amend", "update", "arm", "reading",
                   "signature", "case", "pair")


def _fields_in(node):
    """Every literal field name this expression reads via x["f"] / x.get("f")."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) \
                and isinstance(n.slice.value, str):
            out.add(n.slice.value)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == "get" and n.args \
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            out.add(n.args[0].value)
    return out


def _bound_names(target):
    """Names an assignment actually BINDS. `_names_in` also returned subscript indices, so
    `id_stamps[f][pid] = (str(l.get("ts")), ...)` taught the scanner that `f` holds a ts --
    and a comparison 900 lines later, `f == "result"`, was reported as a ts-keyed gate.
    Provenance read too wide once more; the target is where binding happens, not the index."""
    out = set()
    if isinstance(target, ast.Name):
        out.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for e in target.elts:
            out |= _bound_names(e)
    elif isinstance(target, ast.Starred):
        out |= _bound_names(target.value)
    return out


def _alias_bases(node):
    """Names whose VALUE this operand IS -- a bare name, or the bare names of a boolean
    operand. Not a subscript base, not a call argument: in both of those the operand's value
    is something the name merely contains, and inheriting the container's provenance is how
    the scanner invented two ts gates that do not exist."""
    out = set()
    if isinstance(node, ast.Name):
        out.add(node.id)
    elif isinstance(node, ast.BoolOp):
        for v in node.values:
            out |= _alias_bases(v)
    # NOT through a subscript: `rec["resolved"] != "cleared"` reads the `resolved` key, and
    # inheriting the whole dict's provenance reported a ts gate on a verdict comparison.
    # _fields_in already names the key actually read; the alias is only for the bare value.
    return out


def _names_in(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _src(node, lines):
    try:
        return "\n".join(lines[node.lineno - 1:(node.end_lineno or node.lineno)]).strip()[:160]
    except Exception:
        return ""


_CLOCK = ("now", "utcnow", "today", "time", "monotonic")


def _is_clock_expr(node):
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            nm = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if nm in _CLOCK:
                return True
    return False


def _module_stamps_its_own_ts(tree):
    """The budget.py exemption, detected structurally: the module WRITES the ts field FROM A
    CLOCK, so every ts it later reads back is machine-generated.

    First cut asked only whether some Call subtree mentioned both `ts` and a clock word. On a
    1700-line parser that is true by accident -- and it returned True for the INCIDENT FILE,
    exempting the very gate the register exists to catch, while looking green. The scanner had
    read one carrier and asserted about the module; entry 4, committed by the tool enforcing
    entry 4. The write must now be a ts-keyed assignment whose VALUE is a clock expression.

    Not a filename allowlist: an allowlist would be procedure-recalled-as-prose one level up."""
    for n in ast.walk(tree):
        # x["ts"] = <clock>
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant) \
                        and t.slice.value == "ts" and _is_clock_expr(n.value):
                    return True
        # x.setdefault("ts", <clock>)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in ("setdefault", "get") and len(n.args) > 1 \
                and isinstance(n.args[0], ast.Constant) and n.args[0].value == "ts" \
                and _is_clock_expr(n.args[1]):
            return True
        # {"ts": <clock>, ...}
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and k.value == "ts" and _is_clock_expr(v):
                    return True
    return False


def _enclosing_funcs(tree):
    """line -> FunctionDef covering it (innermost wins)."""
    cover = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for ln in range(fn.lineno, (fn.end_lineno or fn.lineno) + 1):
                prev = cover.get(ln)
                if prev is None or fn.lineno > prev.lineno:
                    cover[ln] = fn
    return cover


def scan_code(path, text=None):
    """Every COMPARISON in the file, checked against the register. A comparison is the
    executable form of a gate: a threshold, a date cutoff, a legality condition.

    `text` scans PROPOSED content for `path` instead of what is on disk -- the hook in
    analysis/hooks/gate-register-pretool.py uses it to diff a pending Edit/Write against
    the file as it stands, so the register fires on the DELTA at the authoring moment
    rather than on the standing findings at the next sweep (spark #59)."""
    src = open(path).read() if text is None else text
    lines = src.splitlines()
    tree = ast.parse(src)
    machine_ts = _module_stamps_its_own_ts(tree)
    cover = _enclosing_funcs(tree)

    # alias map: local name -> fields it was assigned from, SCOPED to the enclosing
    # function. A module-global map leaks `status` into every later comprehension
    # variable named `s` and invents provenance -- which is the register's own failure
    # mode one level up, so the scanner is not allowed to commit it.
    # (func, var) -> [(lineno, fields), ...]. NEAREST PRECEDING assignment wins, not the
    # union: inside a 700-line main() the union of every `pid = ...` in the function put
    # `ts` on a name whose reaching definition is `l.get("id")`, and the scanner reported 18
    # gates that key on nothing of the kind. Over-wide provenance is how a register earns
    # the reputation that gets it ignored -- entry 1's stated failure mode, in the scanner.
    alias = {}
    for fn in list(ast.walk(tree)):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            continue
        key = getattr(fn, "name", "<module>")
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign):
                f = _fields_in(n.value)
                if not f:
                    continue
                for t in n.targets:
                    for nm in _bound_names(t):
                        alias.setdefault((key, nm), []).append((n.lineno, f))
    for v in alias.values():
        v.sort()

    # A comparison inside a print() is a TALLY BEING REPORTED, not a gate -- entry 3's
    # own exemption ("the count IS the reported quantity"), applied to the scanner.
    reporting = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print":
            for c in ast.walk(n):
                if isinstance(c, ast.Compare):
                    reporting.add(id(c))

    findings = []
    for cmp_ in ast.walk(tree):
        if not isinstance(cmp_, ast.Compare) or id(cmp_) in reporting:
            continue
        operands = [cmp_.left] + list(cmp_.comparators)
        fields = set()
        for o in operands:
            fields |= _fields_in(o)
        fn = cover.get(cmp_.lineno)
        _k = fn.name if fn else "<module>"
        for o in operands:
            for nm in _alias_bases(o):
                fields |= _reaching(alias, _k, nm, cmp_.lineno)
        fn_src = _src(fn, lines) if fn else ""
        fn_body = ("\n".join(lines[fn.lineno - 1:(fn.end_lineno or fn.lineno)])
                   if fn else src)
        here = _src(cmp_, lines)
        # The machine-stamp guard must be LOCAL to the gate. Scanning the whole enclosing
        # function exempted every ts comparison in ledger_invariants.py, because a 700-line
        # main() contains the word "stamp" somewhere -- read-too-wide, same genus.
        near = "\n".join(lines[max(0, cmp_.lineno - 4):(cmp_.end_lineno or cmp_.lineno) + 2])

        # 1 — hand-stamped ts
        if fields & REGISTER["hand-stamped-ts"]["fields"]:
            guarded = (machine_ts or any(g in near for g in _MACHINE_GUARDS)
                       or any(g in near for g in _TS_POLICE))
            if not guarded:
                findings.append(dict(entry="hand-stamped-ts", path=path, line=cmp_.lineno,
                                     func=fn.name if fn else "<module>", code=here,
                                     field=sorted(fields & REGISTER["hand-stamped-ts"]["fields"])))
        # 2 — prose
        pf = fields & REGISTER["prose"]["fields"]
        if pf and _recovers_from_prose(cmp_, here, fn_body):
            findings.append(dict(entry="prose", path=path, line=cmp_.lineno,
                                 func=fn.name if fn else "<module>", code=here,
                                 field=sorted(pf)))
        # 4 — single disposition carrier
        cf = fields & REGISTER["single-disposition-carrier"]["fields"]
        if len(cf) == 1:
            others = REGISTER["single-disposition-carrier"]["fields"] - cf
            reads_others = any(f'"{o}"' in fn_body or f"'{o}'" in fn_body for o in others)
            delegates = any(h in fn_body for h in _CARRIER_HELPERS)
            if not reads_others and not delegates:
                findings.append(dict(entry="single-disposition-carrier", path=path,
                                     line=cmp_.lineno, func=fn.name if fn else "<module>",
                                     code=here, field=sorted(cf)))
        # 3 — entry count as a quantity (code side)
        if _count_gate(cmp_, here):
            findings.append(dict(entry="entry-count-as-quantity", path=path, line=cmp_.lineno,
                                 func=fn.name if fn else "<module>", code=here, field=["len()"]))

    # 2b — a REGEX over prose is a gate even though it is not a Compare node. This is the
    # alert-honesty incident's actual shape, and a scanner that only walked Compare nodes
    # would have missed it -- the same read-one-carrier error, in the scanner.
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in ("findall", "search", "match", "fullmatch") \
                and _names_in(n.func.value) & {"re"}:
            fn = cover.get(n.lineno)
            fn_body = ("\n".join(lines[fn.lineno - 1:(fn.end_lineno or fn.lineno)])
                       if fn else src)
            here = _src(n, lines)
            subj = n.args[1] if len(n.args) > 1 else None
            subj_names = _names_in(subj) if subj is not None else set()
            prose_subj = bool(_fields_in(n) & REGISTER["prose"]["fields"]) or \
                bool(subj_names & {"a", "alert", "alerts", "note", "why", "text", "prose"})
            if prose_subj and not any(t in here or t in fn_body for t in _DECLARED_TOKENS):
                findings.append(dict(entry="prose", path=path, line=n.lineno,
                                     func=fn.name if fn else "<module>", code=here,
                                     field=["regex-over-prose"]))
    seen, uniq = set(), []
    for f in findings:
        k = (f["entry"], f["path"], f["line"], tuple(f["field"]))
        if k in seen:
            continue
        seen.add(k); uniq.append(f)
    return uniq


def _reaching(alias, key, nm, line):
    """Fields of the nearest assignment to `nm` at or before `line`."""
    best = set()
    for ln, f in alias.get((key, nm), []):
        if ln <= line:
            best = f
        else:
            break
    return best


def _is_head_read(here, fn_body):
    """A DECLARED-HEAD read: the first token of a prose field checked against a declared
    table or an UPPERCASE literal. This is the exempt form -- the remedy the register
    recommends -- and flagging it would teach `avoid note` instead of `avoid wording`."""
    if any(t in here or t in fn_body for t in _DECLARED_TOKENS + _CARRIER_HELPERS):
        return True
    if re.search(r'startswith\(\s*\(?\s*"[A-Z][A-Z0-9_-]*"', here):
        return True
    if re.search(r'"[A-Z][A-Z0-9_-]{2,}"\s+in\s', here):
        return True
    return False


def _recovers_from_prose(cmp_, here, fn_body):
    """Flag only gates that recover a VALUE from WORDING.

    Three forms are NOT that, and each cost a false positive before it was written down:
      - a head read (`status.startswith("VOID")`, a declared-token table)  -- the remedy;
      - an ENUM read: the field compared with ==/in against single lowercase WORDS. The
        seven-dpt store's `status` is a closed enum (open/worked/failed/pending) while the
        arc ledger's `status` is free text. One field NAME, two dialects -- the recurring
        class, met inside the scanner that hunts it;
      - a value-to-value comparison with no literal at all (sources_diff observed vs read).

    What IS flagged: a SUBSTRING search into a prose field (`"..." in note`), a multi-word
    phrase literal, and (handled separately) a regex capture over free text."""
    if _is_head_read(here, fn_body):
        return False
    # substring search INTO the prose field: `<literal> in <prose>` -- right operand is the text
    for op, comp in zip(cmp_.ops, cmp_.comparators):
        if isinstance(op, ast.In) and _fields_in(comp) & REGISTER["prose"]["fields"] \
                and isinstance(cmp_.left, ast.Constant):
            return True
    for n in ast.walk(cmp_):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            v = n.value.strip()
            if len(v) > 3 and v != v.upper() and " " in v:
                return True
    return False


def _count_gate(cmp_, here):
    """A `len(...)`/count compared to a numeric bar, where the counted subject is one of the
    proxy nouns. Narrow ON PURPOSE: every parser is full of legitimate `len(x) < 2` guards,
    and a register that fires on those has learned "avoid len" -- entry 3's own failure mode."""
    ops = [cmp_.left] + list(cmp_.comparators)
    has_len = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "len"
                  for o in ops for n in ast.walk(o))
    if not has_len:
        return False
    if not any(isinstance(o, ast.Constant) and isinstance(o.value, (int, float)) and o.value >= 2
               for o in ops):
        return False
    return any(s in here.lower() for s in _COUNT_SUBJECTS)


def scan_store(path=STORE):
    """seven-dpt's own wakeConditions. The gates here are `gte` thresholds on counts, and
    two of the four banked incidents are exactly this shape -- a numeric atom standing in
    for a substantive quantity, with nothing alongside naming the real bar."""
    if not os.path.exists(path):
        return []
    s = json.load(open(path))
    NUMERIC = {"sparkCount", "resolvedSparkCount", "openProblemCount", "fileLines",
               "fileMatches", "fileCount"}
    findings = []
    for kind in ("sparks", "problems"):
        for item in s.get(kind, []):
            wc = item.get("wakeCondition")
            if not isinstance(wc, dict):
                continue
            atoms = wc.get("all") or wc.get("any") or []
            nums = [a for a in atoms if a.get("signal") in NUMERIC]
            has_manual = any(a.get("signal") == "manual" for a in atoms)
            if nums and not has_manual:
                findings.append(dict(entry="entry-count-as-quantity", path=path,
                                     line=item.get("id"), func=f"{kind[:-1]} #{item.get('id')}",
                                     code=json.dumps(nums)[:140],
                                     field=[a["signal"] for a in nums]))
            if wc.get("any") and nums and has_manual:
                # an `any` block lets the numeric half fire ALONE -- the manual atom is
                # decoration, which is precisely how spark #50 woke at 470/450.
                findings.append(dict(entry="entry-count-as-quantity", path=path,
                                     line=item.get("id"), func=f"{kind[:-1]} #{item.get('id')}",
                                     code="any-block: numeric atom can fire without the manual bar",
                                     field=[a["signal"] for a in nums]))
    return findings


# ── META-TEST ────────────────────────────────────────────────────────────────
# A check is not evidence until its meta-test runs BOTH directions (standing lesson 2).
# Every incident frame is paired with the SAME code after its fix, so a scanner that
# flagged everything would fail here rather than score 4/4. The FP control is arc's
# budget.py, which keys on a ts the program writes at append time: a register that flags
# it has learned "avoid ts" rather than "avoid a HAND-STAMPED ts" -- the wrong rule, and
# the one that would get the register ignored.
FIX = os.path.join(HERE, "fixtures", "unreliable_register")
SELFTEST = [
    # (label, fixture, entry, must_flag, incidents_carried) — the last field because a
    # FRAME count is not an INCIDENT count: B_wakes_at_incident.json carries two. Reporting
    # 3/3 where the bar is 4 would be entry 3's own error, committed in the scoreboard.
    ("A  ts-keyed legality gate (2026-08-31, reconstructed)", "A_ts_keyed_gate.py",
     "hand-stamped-ts", True, 1),
    ("A' same gate keyed to file position (as fixed)", "A_fixed_file_position.py",
     "hand-stamped-ts", False, 0),
    ("B1/B2 count wakes on sparks #50/#49 (as they fired)", "B_wakes_at_incident.json",
     "entry-count-as-quantity", True, 2),
    ("B'  the same wakes as re-parked with a manual bar", "B_wakes_as_reparked.json",
     "entry-count-as-quantity", False, 0),
    ("C  alert-honesty regex over prose (pre-764723f)", "C_alert_honesty_prose.py",
     "prose", True, 1),
    ("C' the structured alert_claims channel (as fixed)", "C_fixed_structured_channel.py",
     "prose", False, 0),
    ("FP MACHINE-stamped ts — the exemption, as a shape",
     "FP_machine_stamped_ts.py", "hand-stamped-ts", False, 0),
]

# The live control, kept OUT OF TREE: this repo has a public remote and arc's budget.py
# carries spend and account detail the 2026-08-30 memory audit flagged. Scanned when
# present so the strong frame still runs locally; silently absent on any other machine.
LIVE_FP = os.path.expanduser("~/projects/arc-agi-3/scripts/budget.py")


def selftest():
    caught = fp = 0
    frames = list(SELFTEST)
    if os.path.exists(LIVE_FP):
        frames.append(("FP arc scripts/budget.py — the LIVE machine-stamped control"
                       " (out of tree)", LIVE_FP, "hand-stamped-ts", False, 0))
    total_want = sum(n for _, _, _, w, n in SELFTEST if w)
    print(f"REGISTER META-TEST — {total_want} banked incidents, each paired with its fix\n")
    for label, fname, entry, want, carries in frames:
        path = fname if os.path.isabs(fname) else os.path.join(FIX, fname)
        hits = [f for f in (scan_store(path) if path.endswith(".json") else scan_code(path))
                if f["entry"] == entry]
        got = bool(hits)
        ok = got == want
        # an incident frame counts its INCIDENTS, and only if every one of them was hit
        if want and len(hits) >= carries: caught += carries
        if not want and got: fp += len(hits)
        print(f"  [{'ok ' if ok else 'FAIL'}] {label}")
        print(f"          expect {'FLAG' if want else 'clean'} on {entry}; "
              f"got {len(hits)} hit(s)")
        for h in hits[:2]:
            print(f"            {h['code'].splitlines()[0][:100]}")
    print(f"\n  catch rate  {caught}/{total_want} BANKED INCIDENTS"
          f"   false positives {fp}"
          f"\n  spark #54 exhaustion bar: abandon at <3/{total_want} caught, or on ANY hit"
          f" against the machine-stamped control")
    return 0 if caught >= 3 and fp == 0 else 2


def main():
    if "--selftest" in sys.argv:
        return selftest()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    paths = args or sorted(os.path.join(HERE, f) for f in os.listdir(HERE)
                           if f.endswith(".py") and f != os.path.basename(__file__))
    findings = []
    for p in paths:
        if p.endswith(".py"):
            findings += scan_code(p)
        elif p.endswith(".json"):
            findings += scan_store(p)
    if not args:
        findings += scan_store()
    if as_json:
        print(json.dumps(findings, indent=1)); return 0
    by = {}
    for f in findings:
        by.setdefault(f["entry"], []).append(f)
    print(f"DECLARED-UNRELIABLE REGISTER — {len(REGISTER)} entries, "
          f"{len(paths)} file(s) scanned, {len(findings)} gate(s) flagged")
    for k, v in REGISTER.items():
        hits = by.get(k, [])
        print(f"\n  [{k}] {len(hits)} hit(s)")
        print(f"      why:    {v['why']}")
        print(f"      exempt: {v['exempt_when']}")
        for h in hits:
            print(f"      - {os.path.basename(str(h['path']))}:{h['line']} in {h['func']} "
                  f"({','.join(h['field'])})")
            print(f"          {h['code'].splitlines()[0][:120]}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
