#!/usr/bin/env python3
"""sources_diff.py — a TRANSIENT CHANNEL over the programme's external source surface.

WHY THIS EXISTS (spark #48, built 2026-08-16)
The Duck write-up sat public for a MONTH carrying the ACTION7/UNDO exclusion rationale
while three arm-4 runs voided against exactly that exclusion. The post was indexed by
nobody and surfaced only when a task-scoped question happened to point at it. Same
morning, the same failure fired INTERNALLY (whatchanged/object_diff.py, pre-ledger,
invisible to arc's precedent gate) — asset blindness is one genus: an asset not indexed
at the point of use might as well not exist.

The internal half is arc's precedent_check to own. This file is the EXTERNAL half, and
it is deliberately NOT a better map — maps get read once and go static (the game-ledger
lesson). It is a transient channel: biology computes change early and cheap and hands
cognition a sparse changed-first pointer, because without a transient the change is
simply not seen (change blindness). The morning sweep's alerts already are that channel
for the internal decision record; this extends it to tracked external primaries.

DESIGN RULES
- Registry (hand-curated, launch/sources.jsonl) and state (machine-written,
  ~/.local/share) are SEPARATE FILES. The sweep never writes where humans author.
- Check types are a CLOSED SET implemented here: git | http | manual. There is no
  "cmd" type BY DESIGN — a data file that supplies shell to a sweep script is an
  injection surface (the registry lives in a dir other sessions write to).
- The face never prints fetched content — only ids/urls/hashes/dates WE authored.
  Fetched bytes are untrusted input; a page title can carry instructions aimed at
  whichever session reads the sweep. Hashes can't.
- CHANGED means observed != last READ, not != last fetch: a transient persists until
  someone attends to it (--mark-read), exactly like the sweep's alerts persist until
  absorbed. A signal that expires unattended is a signal designed to be missed.
- Exit code is ALWAYS 0. This is reconnaissance, not an invariant: an edit on someone
  else's website must never flip the audit sweep's rc, which speaks only about the
  decision record.

Run:   python3 analysis/sources_diff.py              (inside the sweep, or alone)
       python3 analysis/sources_diff.py --force      (ignore per-source fetch cadence)
       python3 analysis/sources_diff.py --mark-read <id ...|all>
Env:   SOURCES_LEDGER (default ~/projects/launch/sources.jsonl)
       SOURCES_STATE  (default $XDG_DATA_HOME/seven-dpt/sources-state.json)
"""
from __future__ import annotations
import hashlib, json, os, re, subprocess, sys
from datetime import datetime, timezone

HOME    = os.path.expanduser("~")
LEDGER  = os.environ.get("SOURCES_LEDGER") or os.path.join(HOME, "projects/launch/sources.jsonl")
DATA    = os.environ.get("XDG_DATA_HOME") or os.path.join(HOME, ".local/share")
STATE_P = os.environ.get("SOURCES_STATE") or os.path.join(DATA, "seven-dpt", "sources-state.json")

CHECKS = {"git", "http", "manual"}          # closed set — see design rules above
FETCH_TIMEOUT = 25
UA = "seven-dpt-sources/1.0 (+pierre@baume.org)"

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def days_since(iso):
    if not iso: return None
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - t).days

def load_registry():
    rows, bad = [], []
    if not os.path.exists(LEDGER):
        return rows, bad
    for i, line in enumerate(open(LEDGER), 1):
        line = line.strip()
        if not line or line.startswith("#"): continue
        try:
            r = json.loads(line)
        except ValueError:
            bad.append(f"line {i}: unparseable"); continue
        if not r.get("id") or r.get("check") not in CHECKS:
            bad.append(f"line {i}: id/check invalid ({r.get('id')}/{r.get('check')})"); continue
        rows.append(r)
    return rows, bad

def load_state():
    try:
        return json.load(open(STATE_P))
    except (OSError, ValueError):
        return {}

def save_state(st):
    os.makedirs(os.path.dirname(STATE_P), exist_ok=True)
    tmp = STATE_P + ".tmp"
    json.dump(st, open(tmp, "w"), indent=1, sort_keys=True)
    os.replace(tmp, STATE_P)

# ── observation ──────────────────────────────────────────────────────────────
def obs_git(url):
    """HEAD sha via ls-remote — cheap, exact, and immune to page cosmetics."""
    out = subprocess.run(["git", "ls-remote", url, "HEAD"],
                         capture_output=True, text=True, timeout=FETCH_TIMEOUT)
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"ls-remote rc={out.returncode}")
    return out.stdout.split()[0][:12]

_TAG   = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_ENTRY = re.compile(r"<(?:yt:videoId|guid[^>]*|id)>([^<]+)</", re.I)

def obs_http(url):
    """Content fingerprint. Feeds hash their ENTRY IDS (view counters and per-entry
    timestamps churn every fetch, and a churny source teaches everyone to ignore the
    face — same reason the kind-census refuses to alert on prose). Pages hash their
    visible text, tags and script/style stripped, whitespace collapsed."""
    out = subprocess.run(["curl", "-sL", "--max-time", str(FETCH_TIMEOUT), "-A", UA, url],
                         capture_output=True, text=True, timeout=FETCH_TIMEOUT + 10)
    if out.returncode != 0 or not out.stdout:
        raise RuntimeError(f"curl rc={out.returncode}")
    body = out.stdout
    head = body[:300].lstrip().lower()
    if head.startswith("<?xml") or "<feed" in head or "<rss" in head:
        ids = sorted(set(_ENTRY.findall(body)))
        if ids:
            return hashlib.sha1("\n".join(ids).encode()).hexdigest()[:12]
    text = _TAG.sub(" ", _BLOCK.sub(" ", body))
    text = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha1(text.encode()).hexdigest()[:12]

# ── main ─────────────────────────────────────────────────────────────────────
def main(argv):
    rows, bad = load_registry()
    st = load_state()

    if argv[:1] == ["--mark-read"]:
        targets = argv[1:] or []
        ids = [r["id"] for r in rows] if targets == ["all"] else targets
        marked = []
        for i in ids:
            s = st.setdefault(i, {})
            s["read"], s["read_at"] = s.get("observed"), now_iso()
            marked.append(i)
        save_state(st)
        print(f"marked read: {', '.join(marked) if marked else '(nothing)'}")
        return 0

    force = "--force" in argv
    if not rows:
        print(f"SOURCES (recon)  no registry at {LEDGER} — seed it to arm the channel")
        return 0

    changed, unread, due, failed, quiet = [], [], [], [], []
    for r in rows:
        rid, s = r["id"], st.setdefault(r["id"], {})
        cad = int(r.get("cadence_days") or 7)
        if r["check"] == "manual":
            d = days_since(s.get("read_at"))
            if d is None:  unread.append((rid, r, s))
            elif d >= cad: due.append((rid, r, s, d))
            else:          quiet.append(rid)
            continue
        stale = force or s.get("observed") is None or (days_since(s.get("observed_at")) or 0) >= cad
        if stale:
            try:
                s["observed"] = obs_git(r["url"]) if r["check"] == "git" else obs_http(r["url"])
                s["observed_at"], s["error"] = now_iso(), None
            except Exception as e:          # keep the previous observation; report, don't crash
                s["error"] = str(e)[:80]
        if s.get("error") and s.get("observed") is None:
            failed.append((rid, r, s)); continue
        if s.get("read") is None:           unread.append((rid, r, s))
        elif s.get("observed") != s.get("read"): changed.append((rid, r, s))
        else:                               quiet.append(rid)
        if s.get("error"):                  failed.append((rid, r, s))
    save_state(st)

    print(f"SOURCES (recon)  {len(rows)} tracked · changed {len(changed)} · unread {len(unread)}"
          f" · manual due {len(due)} · check-failed {len(failed)} · quiet {len(quiet)}"
          + (f" · registry-bad {len(bad)}" if bad else ""))
    for rid, r, s in changed:               # changed-first: salience REORDERS, it does not add
        print(f"  CHANGED     {rid}  {s.get('read')} -> {s.get('observed')}"
              f"  (read {str(s.get('read_at'))[:10]}, observed {str(s.get('observed_at'))[:10]})  {r['url']}")
    for rid, r, s in unread:
        print(f"  UNREAD      {rid}  never marked read  {r['url']}")
    for rid, r, s, d in due:
        print(f"  MANUAL DUE  {rid}  cadence {r.get('cadence_days')}d, last read {str(s.get('read_at'))[:10]} ({d}d ago)  {r['url']}")
    for rid, r, s in failed:
        print(f"  FAILED      {rid}  {s.get('error')}  (previous observation kept)")
    for msg in bad:
        print(f"  REGISTRY    {msg}")
    if changed or unread or due:
        print(f"  attend with: python3 analysis/sources_diff.py --mark-read <id|all>")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
