// Cross-session store tests. Run: npm test.
// One store.json is shared by every session's server process; these pin the two guarantees
// store.ts makes about that: a stale save is refused (no lost update), and sparks captured by
// another process are reported on the next read (no predicted ids).
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { StoreChangedError, captureSpark, listProblems, mutate, priorCheck, takeForeignSparkNote, updateSpark } from "./store.js";

function scratchStore(): string {
  const dir = mkdtempSync(join(tmpdir(), "sevendpt-store-"));
  const path = join(dir, "store.json");
  writeFileSync(
    path,
    JSON.stringify({
      version: 1,
      nextProblemId: 2,
      nextSparkId: 1,
      problems: [{ id: 1, title: "p1", statement: "", framing: "", status: "open", createdAt: "2026-01-01T00:00:00Z", updatedAt: "2026-01-01T00:00:00Z", resolution: null, wakeCondition: null }],
      sparks: [],
    }),
  );
  process.env.SEVEN_DPT_DB = path;
  return path;
}

test("a second process's sparks are reported on the next read, and ids are never predicted", () => {
  const path = scratchStore();
  listProblems(false); // this process reads: nextSparkId=1 seen
  assert.equal(takeForeignSparkNote(), null, "nothing foreign yet");

  // Simulate ANOTHER session capturing two sparks (#1, #2) by editing the file directly.
  const db = JSON.parse(readFileSync(path, "utf8"));
  db.sparks.push({ id: 1, problemId: 1, trick: "t", idea: "i", nextStep: "n", outcome: null, status: "pending", createdAt: "x", updatedAt: "x" });
  db.sparks.push({ id: 2, problemId: 1, trick: "t", idea: "i", nextStep: "n", outcome: null, status: "pending", createdAt: "x", updatedAt: "x" });
  db.nextSparkId = 3;
  writeFileSync(path, JSON.stringify(db));

  const mine = captureSpark({ problemId: 1, trick: "t", idea: "i", nextStep: "n" });
  assert.ok(mine);
  assert.equal(mine.id, 3, "id comes from the store, after the other session's two");
  const note = takeForeignSparkNote();
  assert.ok(note && note.includes("2 spark(s) (#1-#2)"), `note names the foreign range: ${note}`);
  assert.equal(takeForeignSparkNote(), null, "note is consumed once");

  // Our own capture is not foreign.
  captureSpark({ problemId: 1, trick: "t", idea: "i", nextStep: "n" });
  assert.equal(takeForeignSparkNote(), null);
});

test("a save over a store another process changed since our read is refused, not clobbered", () => {
  const path = scratchStore();
  const s = captureSpark({ problemId: 1, trick: "t", idea: "i", nextStep: "n" });
  assert.ok(s);
  // Inside mutate's window (after load, before save) another session writes the file.
  assert.throws(
    () =>
      mutate((db) => {
        const other = JSON.parse(readFileSync(path, "utf8"));
        other.problems[0].title = "renamed-by-other-session";
        // A same-ms rewrite would share our recorded mtime; push it forward as a real rename
        // landing later would.
        writeFileSync(path, JSON.stringify(other));
        const t = new Date(Date.now() + 5000);
        utimesSync(path, t, t);
        db.sparks[0].status = "tried"; // our stale mutation — must NOT land
      }),
    StoreChangedError,
  );
  const after = JSON.parse(readFileSync(path, "utf8"));
  assert.equal(after.problems[0].title, "renamed-by-other-session", "other session's write survived");
  assert.equal(after.sparks[0].status, "pending", "our stale mutation was refused");
  // A fresh call reloads and succeeds — the error is retryable, nothing to repair.
  const r = updateSpark({ id: s.id, status: "tried", outcome: "x" });
  assert.ok(r);
  assert.equal(JSON.parse(readFileSync(path, "utf8")).sparks[0].status, "tried");
});

test("priorCheck counts only resolved sparks with a stated prior", () => {
  const path = scratchStore();
  const db = JSON.parse(readFileSync(path, "utf8"));
  const spark = (id: number, prior: number | null, status: string, value: number | null) =>
    ({ id, problemId: 1, trick: "t", idea: "i", nextStep: "n", outcome: null, status, prior, value, createdAt: "x", updatedAt: "x" });
  db.sparks.push(
    spark(1, 0.5, "worked", 2),
    spark(2, 0.3, "failed", 1), // a failure that still paid: valued, not worked
    spark(3, 0.4, "failed", 0),
    spark(4, null, "worked", 2), // no prior: out
    spark(5, 0.9, "tried", null), // unresolved: out
  );
  db.nextSparkId = 6;
  writeFileSync(path, JSON.stringify(db));
  const c = priorCheck();
  assert.ok(c);
  assert.deepEqual(c.rows.map((s) => s.id), [1, 2, 3]);
  assert.equal(c.worked, 1);
  assert.equal(c.valued, 2);
  assert.ok(Math.abs(c.meanPrior - 0.4) < 1e-9);
  assert.ok(c.lo < 1 / 3 && 1 / 3 < c.hi);
});

test("a fresh store seeds only the problems seven-dpt still has open", () => {
  const dir = mkdtempSync(join(tmpdir(), "sevendpt-store-"));
  process.env.SEVEN_DPT_DB = join(dir, "store.json"); // no file yet: a fresh install
  const seeded = listProblems(true);
  assert.equal(seeded.length, 3, "README's 'three open product problems'");
  assert.ok(seeded.every((p) => p.status === "open"));
  const tags = seeded.flatMap((p) => p.tags ?? []);
  assert.ok(!tags.includes("curation"), "the near-twelve cap is solved (addProblem refuses past it)");
  assert.ok(!tags.includes("storage"), "storage graduation was retired");
});
