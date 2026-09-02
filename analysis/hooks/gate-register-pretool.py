#!/usr/bin/env python3
"""PreToolUse(Edit|Write) — the unreliable-field register AT THE AUTHORING MOMENT (spark #59).

Spark #54 built the execution path a declared caveat was missing (analysis/
unreliable_register.py), but as a script one RUNS — it fires at the sweep, after the gate
is written. Problem #6's founding lesson is that a trigger discharged by construction beats
one discharged by asking, and the construction here is: scan the PROPOSED file content,
diff its register findings against the file as it stands, and speak only when the edit
introduces a NEW gate keyed to a registered-unreliable field. The 14 standing findings
never reach this hook; it sees the delta, and its addressee is the author at the one
moment they can still choose the field.

Borrowed from firstmate's arm-pretool-check (kunchenguid/firstmate, verified by them on
Claude Code 2.1.220): deny before execution, honoured through the PreToolUse JSON
contract. The same contract already runs on this machine in
~/.claude/hooks/block-wide-bounded-grep.py, which is the local evidence this relies on.

Modes (file ~/.local/share/seven-dpt/gate-register.mode, or GATE_REGISTER_MODE):
  warn  (default) — allow the edit, attach the finding as context the model sees and a
                    message the user sees. The first two weeks run here: a hook that nags
                    on edits which authored no gate gets disabled, so fires vs edits are
                    counted in the log and judged before anything blocks.
  deny            — block the edit with the finding as the reason.
  off             — log only.

Every invocation appends one line to ~/.local/share/seven-dpt/gate-register.log:
    <ts> <tool> <mode> fires=<n> <path>
so "fires vs edits" is a count read from a file, not a recollection.

Fail-open by design: a syntax error in the proposed text, a path outside analysis/, a
fixture, or any exception exits 0 silently — the sweep still runs behind it.
"""
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.realpath(os.path.join(HERE, ".."))
DATA = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
                    "seven-dpt")
LOG = os.path.join(DATA, "gate-register.log")
MODE_FILE = os.path.join(DATA, "gate-register.mode")


def _mode():
    m = os.environ.get("GATE_REGISTER_MODE")
    if not m and os.path.exists(MODE_FILE):
        m = open(MODE_FILE).read().strip()
    return m if m in ("warn", "deny", "off") else "warn"


def _log(tool, mode, fires, path, note=""):
    try:
        os.makedirs(DATA, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(f"{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} "
                    f"{tool} {mode} fires={fires} {path}{(' ' + note) if note else ''}\n")
    except Exception:
        pass


def _key(f):
    # line numbers shift under an edit; identity is (entry, normalised code, fields)
    return (f["entry"], " ".join(f["code"].split()), tuple(f["field"]))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = payload.get("tool_name")
    ti = payload.get("tool_input") or {}
    path = ti.get("file_path") or ""
    if tool not in ("Edit", "Write") or not path.endswith(".py"):
        return 0
    real = os.path.realpath(path)
    if not real.startswith(ANALYSIS + os.sep) or "/fixtures/" in real \
            or os.path.basename(real) == "unreliable_register.py":
        return 0

    pre = open(real).read() if os.path.exists(real) else ""
    if tool == "Write":
        post = ti.get("content") or ""
    else:
        old, new = ti.get("old_string") or "", ti.get("new_string") or ""
        if old not in pre:
            return 0                     # the Edit itself will fail; nothing to judge
        post = pre.replace(old, new) if ti.get("replace_all") else pre.replace(old, new, 1)

    sys.path.insert(0, ANALYSIS)
    try:
        import unreliable_register as ur
        before = {_key(f) for f in ur.scan_code(real, text=pre)} if pre else set()
        after = [f for f in ur.scan_code(real, text=post) if _key(f) not in before]
    except SyntaxError:
        _log(tool, _mode(), 0, real, "syntax-error-in-proposed-text")
        return 0
    except Exception as e:
        _log(tool, _mode(), 0, real, f"scanner-error:{type(e).__name__}")
        return 0

    mode = _mode()
    _log(tool, mode, len(after), real)
    if not after or mode == "off":
        return 0

    rel = os.path.relpath(real, os.path.dirname(ANALYSIS))
    lines = []
    for f in after:
        reg = ur.REGISTER[f["entry"]]
        lines.append(f"{rel}:{f['line']} keys a gate on {','.join(f['field'])} "
                     f"[{f['entry']}] — {f['code'].splitlines()[0][:100]}\n"
                     f"    why: {reg['why']}\n    exempt when: {reg['exempt_when']}")
    body = ("NEW gate keyed to a field this project has DECLARED unreliable "
            f"(analysis/unreliable_register.py):\n" + "\n".join(lines) +
            "\n(standing findings are not reported here — only what this edit adds)")

    if mode == "deny":
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": "deny",
                                      "permissionDecisionReason": body}}
    else:
        out = {"systemMessage": f"gate-register: {len(after)} new registered-unreliable "
                                f"gate(s) in {rel} (warn mode — edit allowed)",
               "hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": "allow",
                                      "additionalContext": body}}
    print(json.dumps(out))
    return 0


# ── SELF-TEST ────────────────────────────────────────────────────────────────
# Both directions, same discipline as unreliable_register.py --selftest: the hook must
# speak on the two positives and stay silent on the three negatives, including an edit
# to a file that already carries standing findings. Runs the hook as a subprocess on
# synthetic PreToolUse stdin with GATE_REGISTER_MODE=warn and the log redirected, so a
# self-test never counts as an edit in the fires-vs-edits tally.
def selftest():
    import subprocess, tempfile
    root = os.path.dirname(ANALYSIS)
    li = os.path.join(ANALYSIS, "ledger_invariants.py")
    cal = os.path.join(ANALYSIS, "calibration.py")
    fx = os.path.join(ANALYSIS, "fixtures", "unreliable_register", "A_fixed_file_position.py")
    ts_gate = '                and str(l.get("ts") or "") >= "2026-09-01"):'
    fp_gate = '                and decl is not None and n > decl):'
    cases = [
        ("P1 Edit re-introduces incident A's ts-keyed gate", True,
         {"tool_name": "Edit", "tool_input": {"file_path": li, "old_string": fp_gate,
                                               "new_string": ts_gate}}),
        ("P2 Write of a new analysis file with a prose regex gate", True,
         {"tool_name": "Write", "tool_input": {"file_path": os.path.join(ANALYSIS, "zz_new.py"),
          "content": "import re\ndef f(inv):\n    c=set()\n    for a in inv.get(\"alerts\") or []:\n"
                     "        c |= set(re.findall(r\"in-flight '([^']+)'\", a))\n    return c\n"}}),
        ("N1 unrelated Edit to calibration.py (3 standing findings stay silent)", False,
         {"tool_name": "Edit", "tool_input": {"file_path": cal,
          "old_string": 'SUBSTRATE_SCORES_SINCE = "2026-08-24"',
          "new_string": 'SUBSTRATE_SCORES_SINCE = "2026-08-24"  # touched'}}),
        ("N2 Edit adding the FIXED file-position form", False,
         {"tool_name": "Edit", "tool_input": {"file_path": li,
          "old_string": '    out["flat_amendment_priors"] = flat_amend',
          "new_string": '    late = [r for r in flat_amend if r["line"] > (decl or 0) + 1]\n'
                        '    out["flat_amendment_priors"] = flat_amend'}}),
        ("N3 Edit to a fixture (out of scope)", False,
         {"tool_name": "Edit", "tool_input": {"file_path": fx, "old_string": "n > decl",
                                               "new_string": 'str(l.get("ts")) >= "2026-09-01"'}}),
    ]
    env = dict(os.environ, GATE_REGISTER_MODE="warn",
               XDG_DATA_HOME=tempfile.mkdtemp(prefix="gate-register-selftest-"))
    bad = 0
    print("GATE-REGISTER HOOK SELF-TEST — 2 must fire, 3 must stay silent\n")
    for label, want, payload in cases:
        r = subprocess.run([sys.executable, __file__], input=json.dumps(payload),
                           capture_output=True, text=True, env=env)
        fired = bool(r.stdout.strip())
        ok = fired == want and r.returncode == 0
        bad += not ok
        print(f"  [{'ok ' if ok else 'FAIL'}] {label}: "
              f"{'fired' if fired else 'silent'} rc={r.returncode}")
    print(f"\n  {len(cases) - bad}/{len(cases)} as declared")
    return 0 if not bad else 2


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
