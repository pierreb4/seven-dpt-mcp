"""INCIDENT A, AS FIXED — the same gate keyed to FILE POSITION of the declaring line.

File order is dialect-3's first authority precisely because it cannot be hand-mistyped.
MUST NOT FLAG. Without this frame the meta-test runs one direction only, and a scanner
that flags every gate in sight would pass it.
"""
def check(lines, out, alerts):
    decl = next((n for n, l in enumerate(lines)
                 if l.get("id") == "kind-dialect-semantics-5"), None)
    prior_seen, flat_amend = {}, []
    for n, l in enumerate(lines):
        i, pr = l.get("id"), l.get("prior")
        if not i: continue
        if pr is None:
            prior_seen.setdefault(i, None); continue
        is_amend = bool(l.get("amends")) or l.get("kind") == "amendment"
        if (is_amend and prior_seen.get(i) is not None and pr == prior_seen[i]
                and decl is not None and n > decl):
            flat_amend.append({"id": i, "prior": pr, "line": n + 1})
        prior_seen[i] = pr
    return flat_amend
