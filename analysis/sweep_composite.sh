#!/usr/bin/env bash
# sweep_composite.sh — Option C (2026-08-08): the arc program's ledger is ONE logical
# ledger in TWO files (arc-repo historical + shared-launch active since 08-07).
# Concatenate to a temp composite, run BOTH analysis layers on it via ARC_PRIOR_LEDGER
# (the env var is the only path the scripts read — a positional arg is silently
# ignored), and stamp provenance in a sidecar next to the self-persisted JSONs.
# The era question stays computable on demand: pass --split 2026-08-07 (the file
# boundary coincides with that prereg-date boundary) — prior expectation TRANSFERS,
# per the 0.1.5 Claude-5 era-split verdict. Never redirect onto the OUTJSON paths.
set -euo pipefail

A="${LEDGER_A:-$HOME/projects/arc-agi-3/launch/prior-ledger.jsonl}"
B="${LEDGER_B:-$HOME/projects/launch/prior-ledger.jsonl}"
OUTDIR="${XDG_DATA_HOME:-$HOME/.local/share}/seven-dpt"
HERE="$(cd "$(dirname "$0")" && pwd)"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
COMPOSITE="$TMP/prior-ledger-composite.jsonl"
# Exact-duplicate lines dedupe (first occurrence wins, order kept): since 2026-08-09
# arc keeps the two files as synced copies, so a plain cat would double-read every id.
# Diverged (non-identical) lines both survive, and per-id last-wins gives the later
# file (B, the active one) precedence — correct in both worlds.
awk '!seen[$0]++' "$A" "$B" > "$COMPOSITE"

mkdir -p "$OUTDIR"
printf '{"scope":"composite","built":"%s","sources":[{"path":"%s","lines":%s,"sha1":"%s"},{"path":"%s","lines":%s,"sha1":"%s"}]}\n' \
  "$(date -Is)" \
  "$A" "$(wc -l < "$A")" "$(sha1sum "$A" | cut -c1-12)" \
  "$B" "$(wc -l < "$B")" "$(sha1sum "$B" | cut -c1-12)" \
  > "$OUTDIR/ledger-sources.json"

echo "== composite: $(wc -l < "$COMPOSITE") lines ($(basename "$A"): $(wc -l < "$A") + shared: $(wc -l < "$B"))"
echo "== calibration"
ARC_PRIOR_LEDGER="$COMPOSITE" python3 "$HERE/calibration.py" --json "$@" >/dev/null
echo "== invariants (STORE_STRICT=${STORE_STRICT:-1})"
# `set -e` must not abort here: rc=1 is the NORMAL alert path, and the self-check below is
# exactly what we want to run when the faces are noisy. PIPESTATUS[0] because `| tail` would
# otherwise report tail's status (a trap this project has fallen into twice).
set +e
STORE_STRICT="${STORE_STRICT:-1}" ARC_PRIOR_LEDGER="$COMPOSITE" python3 "$HERE/ledger_invariants.py" --json | tail -40
INV_RC=${PIPESTATUS[0]}
echo "== self-check"
python3 "$HERE/self_check.py"
SC_RC=$?

# Reader controls (2026-08-31): can each reader still DISSENT? self_check asks whether the
# faces AGREE; this asks the prior question — whether any of them can say "no" at all. Two
# faces that agree because neither can see the specimen are consistent and both wrong, which
# is the pinned-green shape that cost this layer its most expensive bite. Planted specimens
# through the real sweep path, so it costs one extra pass over 476 lines.
# rc IS consulted (it joins self_check's rank): a reader that has lost the ability to dissent
# has not published a number, it has published a silence.
echo "== reader controls"
python3 "$HERE/reader_controls.py"
RC_RC=$?
set -e

# Reader-path census (2026-08-31). Prints the DENOMINATOR this layer never had: how many keys
# arc emits that nothing reads, and how many field-reads reach a face only through a helper the
# face never names — the column bite 7 lived in (a correct write and a correct read separated by
# a veto reader neither side knew was in the path). Print-only, rc never consulted: it is a
# census, and deciding which zero is a defect is a human judgement. ~10s, so PATHS_SKIP=1 skips
# it on a hurried morning; the cost is the traced parser run, not the printing.
if [ "${PATHS_SKIP:-0}" != 1 ]; then
  echo "== reader paths (census)"
  python3 "$HERE/reader_paths.py" --summary || true
fi

# Recon face (spark #48, 2026-08-16): transient channel over tracked EXTERNAL primaries
# (launch/sources.jsonl). Print-only, rc deliberately not consulted — an edit on someone
# else's website must never flip the audit rc, which speaks only about the decision record.
# SOURCES_SKIP=1 skips it entirely (offline mornings).
if [ "${SOURCES_SKIP:-0}" != 1 ]; then
  echo "== sources (recon)"
  python3 "$HERE/sources_diff.py" || true
fi

# Memory-index guard (2026-08-28, spark #52): the session-loaded MEMORY.md must stay an
# index of one-line HOOKS, never content — it re-drifted once into a 13k-char dump line.
# Structural, not advisory (problem #6's lesson). Print-only: rc never consulted, and the
# guard is silent when the file is absent (other machines / other users).
MEMFILE="${MEMORY_INDEX:-$HOME/.claude/projects/-home-pierre-projects-seven-dpt-mcp/memory/MEMORY.md}"
if [ -f "$MEMFILE" ]; then
  awk -v max=300 'length($0) > max { printf "  MEMORY-INDEX GUARD: line %d is %d chars (>%d) — trim to a hook, move content to the memory file [%s...]\n", NR, length($0), max, substr($0, 1, 60) }' "$MEMFILE" || true
fi

# A contradiction BETWEEN faces outranks any alert FROM a face: if the layers disagree about
# what happened, no number in this sweep has been established yet. rc=2 says so distinctly.
if [ "$SC_RC" -ne 0 ]; then exit "$SC_RC"; fi
if [ "$RC_RC" -ne 0 ]; then exit "$RC_RC"; fi
exit "$INV_RC"
