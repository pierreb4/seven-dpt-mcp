#!/usr/bin/env python3
"""reader_paths.py — which readers sit between a field and each face?

WHY THIS EXISTS
Eight defects in three weeks, every one a reader that could not see something. The remedies
were built one at a time, each after its own bite, each on the axis that had just failed —
and the recurrence rate did not fall. The sharpest specimen was the 7th: arc wrote a
disposition onto a declared carrier exactly as asked, our face read that carrier correctly,
and the count did not move, because `event_class` sat in the path between them and vetoed the
line before its carrier was ever consulted. A correct write and a correct read, separated by a
THIRD READER NEITHER SIDE KNEW WAS THERE.

That class cannot be found by looking harder at the writer or the reader. It is a property of
the PATH, and nothing in this layer had ever enumerated the paths. Arc proposed the census; we
had independently reached the same table from the other end (28 ids placed by no face, 210
emitted keys no reader names, `status_class` judging 34 bare-status lines and recognising 3 —
and no face printing a denominator for any of it, which is why none of it ever looked wrong).

WHY RUNTIME TRACING AND NOT STATIC ANALYSIS
The faces are inline sections of `main()`, not functions, so a call graph would not name them.
And the reads that matter are INDIRECT: a face calls `_walk_word`, which calls `result_field`,
which calls `kind_tokens`, which reads `kind`. A static reading of the face's own source shows
none of that — which is precisely why bite 7 was invisible for a day. So: wrap every ledger
line in a dict that records each key access together with the live call stack, run the real
parser, and read the paths off the run.

WHAT IT ANSWERS
  1 COVERAGE     every key arc emits, and whether ANY reader consumed it — the denominator
                 this layer has never printed.
  2 PATHS        per field, the distinct chains of parser functions that reach it, and which
                 face each chain served.
  3 HIDDEN GATES the payload. For each face, fields it reads ONLY through a helper — never
                 named in the face's own source. Every one of those is a reader in the path
                 that the face's author did not write down, and any of them can veto.

Run:  python3 analysis/reader_paths.py [--json PATH] [--face SUBSTR]
Env:  ARC_PRIOR_LEDGER (same default as the parsers)
Exit: always 0 — this is a census, not a tripwire. It reports a denominator; deciding which
      zero is a defect is a human judgement and deliberately not automated here.
"""
import collections, io, json, contextlib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# ── the recording line ───────────────────────────────────────────────────────
# Records (key, path) on every VALUE read. Iteration is deliberately NOT recorded: `prior_of`
# scans `for k in l` looking for a prefix, and counting that as a read of every key would make
# the coverage number say "everything is read" — the exact vacuous denominator this file
# exists to replace.
ACCESS = []            # (key, path tuple, face)
_PARSER_FILE = None
_FACES = {}            # line number in the parser file -> face name


class RecordingDict(dict):
    __slots__ = ()

    def _rec(self, k):
        path, face = _stack()
        ACCESS.append((k, path, face))

    def get(self, k, default=None):
        self._rec(k); return dict.get(self, k, default)

    def __getitem__(self, k):
        self._rec(k); return dict.__getitem__(self, k)

    def __contains__(self, k):
        self._rec(k); return dict.__contains__(self, k)


def _stack():
    """(chain of parser functions innermost-first, face name) for the current access."""
    chain, face = [], None
    f = sys._getframe(3)                       # skip _stack/_rec/get
    while f is not None:
        if f.f_code.co_filename == _PARSER_FILE:
            name = f.f_code.co_name
            if name == "main":
                face = _face_at(f.f_lineno)    # faces are SECTIONS of main, not functions
            elif name.startswith("<"):
                pass                           # <genexpr>/<listcomp> frames are not READERS —
                                               # naming one hides the function that actually
                                               # touched the field, which is the whole answer
            elif not chain or chain[-1] != name:
                chain.append(name)
        f = f.f_back
    return tuple(chain), face or "(main, unsectioned)"


def _face_at(lineno):
    best = None
    for ln, name in _FACES.items():
        if ln <= lineno and (best is None or ln > best[0]): best = (ln, name)
    return best[1] if best else "(main, unsectioned)"


def load_faces(path):
    """Faces are marked by the file's own `# ── NAME ──` section headers."""
    out = {}
    for i, line in enumerate(open(path), start=1):
        m = re.match(r"\s*#\s*──+\s*(.+?)\s*──+\s*$", line)
        if m:
            name = m.group(1).strip()
            if len(name) > 2: out[i] = name
    return out


class _JsonShim:
    """json, but every parsed OBJECT becomes a RecordingDict."""
    def __init__(self, real): self._r = real
    def loads(self, s, **kw):
        d = self._r.loads(s, **kw)
        return RecordingDict(d) if isinstance(d, dict) else d
    def __getattr__(self, n): return getattr(self._r, n)


def source_of(mod_path):
    return open(mod_path).read()


def face_source_fields(src, faces):
    """Fields NAMED IN THE FACE'S OWN SOURCE — the reads its author wrote down.

    Anything a face touches that is not in here reached it through a helper, i.e. via a reader
    the face does not mention. That difference is the whole point of section 3.
    """
    lines = src.split("\n")
    bounds = sorted(faces)
    out = collections.defaultdict(set)
    for i, start in enumerate(bounds):
        end = bounds[i + 1] if i + 1 < len(bounds) else len(lines) + 1
        body = "\n".join(lines[start - 1:end - 1])
        for m in re.finditer(r"""\.get\(\s*["'](\w+)["']|\[\s*["'](\w+)["']\s*\]""", body):
            out[faces[start]].add(m.group(1) or m.group(2))
    return out


def main():
    global _PARSER_FILE, _FACES
    argv = sys.argv[1:]
    outjson = argv[argv.index("--json") + 1] if "--json" in argv else None
    only = argv[argv.index("--face") + 1] if "--face" in argv else None
    summary = "--summary" in argv

    import ledger_invariants as L
    _PARSER_FILE = os.path.abspath(L.__file__)
    _FACES = load_faces(_PARSER_FILE)
    src = source_of(_PARSER_FILE)

    # every key arc actually emits — the denominator side of coverage
    emitted = collections.Counter()
    ledger = L.LEDGER
    if not os.path.exists(ledger):
        print(f"no ledger at {ledger} — set ARC_PRIOR_LEDGER"); return 0
    for raw in open(ledger):
        raw = raw.strip()
        if not raw: continue
        try: emitted.update(json.loads(raw).keys())
        except ValueError: continue

    L.json = _JsonShim(json)                       # instrument, then run the REAL parser
    with contextlib.redirect_stdout(io.StringIO()):
        with open(os.devnull, "w") as devnull:
            old, L.OUTJSON = L.OUTJSON, os.path.join(os.path.dirname(devnull.name) or "/tmp",
                                                     "reader_paths_scratch.json")
            try: L.main()
            except SystemExit: pass
            finally: L.OUTJSON = old

    read_by_field = collections.defaultdict(set)   # field -> {(path, face)}
    faces_of = collections.defaultdict(set)        # field -> {face}
    fields_of_face = collections.defaultdict(set)  # face -> {field}
    for k, path, face in ACCESS:
        read_by_field[k].add((path, face))
        faces_of[k].add(face)
        fields_of_face[face].add(k)

    # ── 1 COVERAGE ──
    unread = sorted(k for k in emitted if k not in read_by_field)
    declared_ = face_source_fields(src, _FACES)
    n_gates = sum(len([f for f in fl if f not in declared_.get(fc, set())])
                  for fc, fl in fields_of_face.items())
    if summary:
        # ONE line, for the sweep. The denominator is the point: printing it daily is what
        # makes a zero here capable of looking wrong, which it never was before.
        print(f"READER PATHS  {len(emitted)} keys emitted · {len(emitted) - len(unread)} read "
              f"· {len(unread)} read by NOTHING · {len(fields_of_face)} faces · {n_gates} "
              f"field-reads reach a face only through a helper it never names "
              f"(full table: analysis/reader_paths.py)")
        return 0
    print("READER PATHS  which readers sit between a field and each face?\n")
    print(f"1 COVERAGE  {len(emitted)} keys emitted · {len(emitted) - len(unread)} read by "
          f"some reader · {len(unread)} READ BY NOTHING")
    heavy = [(k, emitted[k]) for k in unread if emitted[k] >= 3]
    print(f"    unread keys on >=3 lines ({len(heavy)}): "
          + (", ".join(f"{k}({n})" for k, n in sorted(heavy, key=lambda x: -x[1])[:14])
             if heavy else "none"))
    print("    (an unread key is not automatically a defect — most are prereg prose. It is a")
    print("     DENOMINATOR: until now nothing printed it, so no zero here could look wrong.)")

    # ── 3 HIDDEN GATES (printed before the full path dump; it is the payload) ──
    declared = face_source_fields(src, _FACES)
    print("\n2 HIDDEN GATES  fields a face reads ONLY through a helper — readers in the path")
    print("   that the face's own source never names. Bite 7 lived in exactly this column.")
    rows = []
    for face, fields in sorted(fields_of_face.items()):
        if only and only.lower() not in face.lower(): continue
        hidden = sorted(f for f in fields if f not in declared.get(face, set()))
        if hidden: rows.append((face, hidden, sorted(declared.get(face, set()))))
    for face, hidden, own in rows[:40]:
        via = collections.defaultdict(set)
        for f in hidden:
            for path, fc in read_by_field[f]:
                if fc == face and path: via[f].add(path[0])   # innermost = actual reader
        print(f"\n   {face}")
        print(f"     names in its own source : {', '.join(own) if own else '(none)'}")
        for f in hidden:
            print(f"     via helper: {f:22s} <- {', '.join(sorted(via.get(f) or ['?']))}")

    # ── 2 PATHS (full detail lands in the JSON; print the widest fan-out) ──
    print("\n3 PATHS  fields reached by the most distinct reader chains (full table in --json)")
    fan = sorted(read_by_field.items(), key=lambda kv: -len({p for p, _ in kv[1]}))
    for k, entries in fan[:8]:
        chains = sorted({p for p, _ in entries if p})
        print(f"   {k:14s} {len(chains)} chain(s), {len({f for _, f in entries})} face(s)")
        for c in chains[:4]:
            print(f"        {' <- '.join(c)}")
        if len(chains) > 4: print(f"        ... {len(chains) - 4} more")

    if outjson:
        blob = {
            "emitted": dict(emitted),
            "unread": unread,
            "faces": {f: sorted(v) for f, v in fields_of_face.items()},
            "declared_in_source": {f: sorted(v) for f, v in declared.items()},
            "paths": {k: sorted([list(p), f] for p, f in v) for k, v in read_by_field.items()},
        }
        os.makedirs(os.path.dirname(os.path.abspath(outjson)), exist_ok=True)
        json.dump(blob, open(outjson, "w"), indent=1)
        print(f"\njson -> {outjson}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
