#!/usr/bin/env python3
"""Join each spark's OUTCOME to the MODEL that produced it — the one pairing no ledger held.

Cost and model live in ~/.claude/budget/spend.jsonl; outcome and value live in the
seven-dpt store. They share no key, so every model comparison to date has been a
comparison of SPEND, never of what the spend bought.

No schema change and no self-report: a session's transcript already records, per turn,
both the model that ran it and the `capture_spark` / `update_spark` tool call it made.
That is an exact join on the spark id, and it works retroactively over every spark ever
written. A field on the spark would have needed the model to name itself, which is the
one witness that cannot be checked.

THREE LIMITS, printed with the table because a number this easy to over-read needs them:
  1. The model named is the one that ADJUDICATED the spark, not necessarily the one that
     did the work. Spark #58 was resolved here while a peer session on another model did
     the build. Delegated work attributes to the desk, not the hand.
  2. The sample is OBSERVATIONAL and the assignment is not random: model follows pool
     state (~/.claude/CLAUDE.md), so "which model resolved more sparks" is entangled with
     "which pool was free that week". Any comparison is confounded by calendar.
  3. `value` is a small subjective scale set by the same model that did the work.

Usage:  python3 analysis/spark_model_join.py [--verbose]
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
STORE = Path(os.environ.get("SEVEN_DPT_DB",
              Path.home() / ".local" / "share" / "seven-dpt" / "store.json"))
TOOLS = ("capture_spark", "update_spark")
CAPTURED = re.compile(r"Captured spark #(\d+)")
UPDATED = re.compile(r"Updated spark #(\d+)")


def family(model_id: str | None) -> str:
    """Model family from a raw id. Mirrors tokmeter.py so the two agree."""
    if not model_id:
        return "unknown"
    m = model_id.lower()
    for fam in ("fable", "opus", "sonnet", "haiku"):
        if fam in m:
            return fam
    return m


def scan() -> dict[int, list[dict]]:
    """spark id -> [{tool, family, model, ts, session}], in transcript order."""
    hits: dict[int, list[dict]] = defaultdict(list)
    for path in PROJECTS.rglob("*.jsonl"):
        pending: dict[str, dict] = {}     # tool_use_id -> partial hit awaiting its result
        try:
            fh = path.open(errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                # Cheap prefilter: full JSON parse of a 725 MB corpus is the slow path.
                # BOTH forms are needed and the first cut had only the first: the tool CALL
                # carries `capture_spark`, but the RESULT that names the new id says
                # "Captured spark #57" — no underscore. Filtering on `_spark` alone found
                # 37 resolutions and 3 of 58 captures, and the missing 55 read as "transcript
                # rotated" rather than as a bug in the filter.
                if "_spark" not in line and "spark #" not in line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = rec.get("message") or {}
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use" and any(t in (c.get("name") or "") for t in TOOLS):
                        tool = "capture" if "capture_spark" in c["name"] else "update"
                        hit = {
                            "tool": tool,
                            "model": msg.get("model"),
                            "family": family(msg.get("model")),
                            "ts": rec.get("timestamp"),
                            "session": (rec.get("sessionId") or "")[:8],
                            "project": path.parent.name,
                        }
                        sid = (c.get("input") or {}).get("id")
                        if tool == "update" and isinstance(sid, int):
                            hits[sid].append(hit)      # id is in the call itself
                        else:
                            pending[c.get("id")] = hit  # capture: id only exists in the result
                    elif c.get("type") == "tool_result" and c.get("tool_use_id") in pending:
                        hit = pending.pop(c["tool_use_id"])
                        body = c.get("content")
                        if isinstance(body, list):
                            body = " ".join(str(b.get("text", "")) for b in body if isinstance(b, dict))
                        m = CAPTURED.search(str(body)) or UPDATED.search(str(body))
                        if m:
                            hits[int(m.group(1))].append(hit)
    return hits


def main() -> int:
    verbose = "--verbose" in sys.argv
    if not STORE.exists():
        print(f"no store at {STORE}", file=sys.stderr)
        return 2
    db = json.loads(STORE.read_text())
    sparks = {s["id"]: s for s in db.get("sparks", [])}
    hits = scan()

    # A spark's outcome is attributed to the model of its RESOLVING call (the last update
    # that set a terminal status); an unresolved spark is attributed to nothing.
    rows = []
    for sid, s in sorted(sparks.items()):
        calls = hits.get(sid, [])
        cap = next((h for h in calls if h["tool"] == "capture"), None)
        upd = [h for h in calls if h["tool"] == "update"]
        resolver = upd[-1] if upd else None
        rows.append({
            "id": sid, "problem": s.get("problemId"), "status": s.get("status"),
            "value": s.get("value"), "cost": s.get("cost"),
            "captured_by": cap["family"] if cap else "?",
            "resolved_by": resolver["family"] if resolver else "-",
            "session": (resolver or cap or {}).get("session", "?"),
        })

    print(f"SPARK x MODEL  ({len(rows)} sparks, {sum(1 for r in rows if r['captured_by'] != '?')} "
          f"with a located capture call)")
    print()
    print("CAPTURE side — which model minted the spark:")
    by_cap: dict[str, list] = defaultdict(list)
    for r in rows:
        by_cap[r["captured_by"]].append(r)
    for fam, rs in sorted(by_cap.items(), key=lambda kv: -len(kv[1])):
        resolved = [r for r in rs if r["status"] in ("worked", "failed")]
        worked = [r for r in resolved if r["status"] == "worked"]
        vals = [r["value"] for r in resolved if isinstance(r.get("value"), (int, float))]
        rate = f"{len(worked)}/{len(resolved)}" if resolved else "0/0"
        mean = f"{sum(vals)/len(vals):.2f}" if vals else "n/a"
        print(f"  {fam:8s} captured {len(rs):3d}   resolved {len(resolved):3d}   "
              f"worked {rate:7s}   mean value {mean}")

    print()
    print("RESOLVE side — which model graded the outcome:")
    by_res: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["resolved_by"] != "-":
            by_res[r["resolved_by"]].append(r)
    for fam, rs in sorted(by_res.items(), key=lambda kv: -len(kv[1])):
        worked = [r for r in rs if r["status"] == "worked"]
        vals = [r["value"] for r in rs if isinstance(r.get("value"), (int, float))]
        mean = f"{sum(vals)/len(vals):.2f}" if vals else "n/a"
        print(f"  {fam:8s} graded {len(rs):3d}   worked {len(worked):3d}   mean value {mean}")

    unlocated = [r["id"] for r in rows if r["captured_by"] == "?"]
    if unlocated:
        print(f"\n  {len(unlocated)} sparks have no locatable capture call "
              f"(transcript rotated, or written before this corpus): {unlocated[:12]}"
              f"{' …' if len(unlocated) > 12 else ''}")

    if verbose:
        print("\nper spark:")
        for r in rows:
            print(f"  #{r['id']:<3d} p{r['problem']} {str(r['status']):8s} "
                  f"val={str(r['value']):5s} cap={r['captured_by']:7s} res={r['resolved_by']:7s} "
                  f"[{r['session']}]")

    print("\nREAD THIS BEFORE USING THE TABLE")
    print("  1. ADJUDICATOR, NOT AUTHOR: the model named resolved the spark; delegated work")
    print("     (a peer session on another model) attributes to the desk, not the hand.")
    print("  2. OBSERVATIONAL, CONFOUNDED BY CALENDAR: model follows POOL STATE, so model")
    print("     and week are entangled. This table cannot support a causal comparison, and")
    print("     n is small — treat any gap under ~2x as noise.")
    print("  3. `value` is graded by the model that did the work. Self-reported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
