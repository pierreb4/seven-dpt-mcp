// Wake-condition tests (0.1.4). Run: npm test  (builds, then `node --test dist/wake.test.js`).
// Fixture stores go through the existing SEVEN_DPT_DB override — no mocking, real files.
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  captureSpark,
  evaluateWake,
  updateProblem,
  updateSpark,
  wakeLedger,
  type WakeCondition,
} from "./store.js";

const INDEX_JS = fileURLToPath(new URL("./index.js", import.meta.url));

function scratch(): string {
  return mkdtempSync(join(tmpdir(), "sevendpt-wake-"));
}

function mkProblem(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    title: `p${id}`,
    statement: "",
    framing: "",
    status: "open",
    resolution: null,
    wakeCondition: null,
    tags: [],
    origin: null,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    ...over,
  };
}

function mkSpark(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    problemId: 1,
    trick: "t",
    idea: "i",
    nextStep: "the next step",
    outcome: null,
    status: "pending",
    prior: null,
    costToOpen: null,
    cost: null,
    value: null,
    resolvedAt: null,
    wakeCondition: null,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    ...over,
  };
}

function useStore(problems: unknown[], sparks: unknown[]): string {
  const p = join(scratch(), "store.json");
  writeFileSync(p, JSON.stringify({ version: 1, nextProblemId: 90, nextSparkId: 90, problems, sparks }));
  process.env.SEVEN_DPT_DB = p;
  return p;
}

test("any = max progress; ripe via a single atom, binding echoes the ripe atom", () => {
  useStore([], [mkSpark(1, { value: 1 }), mkSpark(2, { value: 0 }), mkSpark(3), mkSpark(4), mkSpark(5)]);
  const r = evaluateWake({
    summary: "s",
    any: [
      { signal: "sparkCount", gte: 10 },
      { signal: "resolvedSparkCount", gte: 2 },
    ],
  });
  assert.equal(r.state, "ripe");
  assert.equal(r.binding, "resolved sparks 2/2");
});

test("all = min progress; binding is the weakest link", () => {
  useStore([], [mkSpark(1, { value: 1 }), mkSpark(2, { value: 0 }), mkSpark(3), mkSpark(4), mkSpark(5)]);
  const r = evaluateWake({
    summary: "s",
    all: [
      { signal: "sparkCount", gte: 10 },
      { signal: "resolvedSparkCount", gte: 2 },
    ],
  });
  assert.equal(r.state, "ripening");
  assert.equal(r.progress, 0.5);
  assert.equal(r.binding, "sparks 5/10");
});

test("a manual atom turns full numeric ripeness into manual-gate, never ripe", () => {
  useStore([], [mkSpark(1, { value: 1 })]);
  const r = evaluateWake({
    summary: "s",
    all: [
      { signal: "resolvedSparkCount", gte: 1 },
      { signal: "manual", note: "check capture integrity" },
    ],
  });
  assert.equal(r.state, "manual-gate");
});

test("pure-manual condition never auto-ripens", () => {
  useStore([], []);
  const r = evaluateWake({ summary: "s", any: [{ signal: "manual", note: "vibes" }] });
  assert.equal(r.state, "ripening");
  assert.equal(r.progress, null);
});

test("date atom: past opens the gate, future holds at 0", () => {
  useStore([], []);
  assert.equal(evaluateWake({ summary: "s", all: [{ signal: "date", onOrAfter: "2000-01-01" }] }).state, "ripe");
  const future = evaluateWake({ summary: "s", all: [{ signal: "date", onOrAfter: "2999-01-01" }] });
  assert.equal(future.state, "ripening");
  assert.equal(future.progress, 0);
});

test("fileMatches: the spark-#22 acceptance shape (12/20 = 60%, then ripe at 12)", () => {
  const ledger = join(scratch(), "ledger.jsonl");
  writeFileSync(
    ledger,
    Array.from({ length: 30 }, (_, i) => (i < 12 ? `{"outcome":${i}}` : `{"x":${i}}`)).join("\n"),
  );
  useStore([], []);
  const at20 = evaluateWake({
    summary: "s",
    all: [{ signal: "fileMatches", path: ledger, pattern: '"outcome"', gte: 20 }],
  });
  assert.equal(at20.state, "ripening");
  assert.equal(at20.progress, 0.6);
  assert.match(at20.binding, /ledger\.jsonl 12\/20/);
  const at12 = evaluateWake({
    summary: "s",
    all: [{ signal: "fileMatches", path: ledger, pattern: '"outcome"', gte: 12 }],
  });
  assert.equal(at12.state, "ripe");
});

test("unreadable screams: missing file, invalid regex, oversized file", () => {
  const dir = scratch();
  useStore([], []);
  const missing = evaluateWake({
    summary: "s",
    all: [{ signal: "fileLines", path: join(dir, "nope.txt"), gte: 5 }],
  });
  assert.equal(missing.state, "unreadable");
  assert.match(missing.atoms[0]!.echo, /ENOENT/);

  const real = join(dir, "real.txt");
  writeFileSync(real, "a\nb\n");
  const badRe = evaluateWake({
    summary: "s",
    all: [{ signal: "fileMatches", path: real, pattern: "(", gte: 1 }],
  });
  assert.equal(badRe.state, "unreadable");
  assert.match(badRe.atoms[0]!.echo, /invalid regex/);

  const big = join(dir, "big.bin");
  writeFileSync(big, Buffer.alloc(10 * 1024 * 1024 + 1));
  const over = evaluateWake({ summary: "s", all: [{ signal: "fileLines", path: big, gte: 1 }] });
  assert.equal(over.state, "unreadable");
  assert.match(over.atoms[0]!.echo, /10 MB cap/);
});

test("fileCount honors the suffix filter", () => {
  const dir = scratch();
  writeFileSync(join(dir, "a.json"), "{}");
  writeFileSync(join(dir, "b.json"), "{}");
  writeFileSync(join(dir, "c.txt"), "x");
  useStore([], []);
  const r = evaluateWake({
    summary: "s",
    all: [{ signal: "fileCount", dir, suffix: ".json", gte: 4 }],
  });
  assert.equal(r.state, "ripening");
  assert.equal(r.progress, 0.5);
});

test("lifecycle: reopening a problem clears its wake condition", () => {
  const cond: WakeCondition = { summary: "s", any: [{ signal: "sparkCount", gte: 1 }] };
  useStore([mkProblem(1, { status: "retired", wakeCondition: cond })], []);
  const p = updateProblem({ id: 1, status: "open" });
  assert.equal(p!.wakeCondition, null);
});

test("lifecycle: set / explicit-clear / omit-preserves on a parked problem", () => {
  useStore([mkProblem(1, { status: "retired" })], []);
  const cond: WakeCondition = { summary: "s", any: [{ signal: "sparkCount", gte: 1 }] };
  assert.deepEqual(updateProblem({ id: 1, wakeCondition: cond })!.wakeCondition, cond);
  assert.deepEqual(updateProblem({ id: 1, resolution: "still parked" })!.wakeCondition, cond);
  assert.equal(updateProblem({ id: 1, wakeCondition: null })!.wakeCondition, null);
});

test("lifecycle: a terminal spark verdict clears the wake condition", () => {
  useStore([mkProblem(1)], [mkSpark(1, { status: "tried" })]);
  const cond: WakeCondition = { summary: "s", any: [{ signal: "sparkCount", gte: 99 }] };
  assert.deepEqual(updateSpark({ id: 1, wakeCondition: cond })!.wakeCondition, cond);
  assert.deepEqual(updateSpark({ id: 1, cost: 1 })!.wakeCondition, cond); // omit preserves
  const resolved = updateSpark({ id: 1, status: "worked", value: 2 });
  assert.equal(resolved!.wakeCondition, null);
});

test("captureSpark can park a spark from birth", () => {
  useStore([mkProblem(1)], []);
  const cond: WakeCondition = { summary: "s", all: [{ signal: "date", onOrAfter: "2999-01-01" }] };
  const s = captureSpark({ problemId: 1, trick: "t", idea: "i", nextStep: "n", wakeCondition: cond });
  assert.deepEqual(s!.wakeCondition, cond);
});

test("wakeLedger sorts ripe first, then by progress", () => {
  const ripe: WakeCondition = { summary: "ripe one", any: [{ signal: "sparkCount", gte: 1 }] };
  const far: WakeCondition = { summary: "far one", all: [{ signal: "sparkCount", gte: 100 }] };
  const near: WakeCondition = { summary: "near one", all: [{ signal: "sparkCount", gte: 4 }] };
  useStore(
    [mkProblem(1, { status: "retired", wakeCondition: far })],
    [mkSpark(2, { wakeCondition: ripe }), mkSpark(3, { wakeCondition: near })],
  );
  const ids = wakeLedger().map((e) => e.id);
  assert.deepEqual(ids, [2, 3, 1]); // ripe first, then ripening 50% (2/4), then ripening 2%
});

test("--digest integration: WAKE block, unreadable block, ripening line with %", () => {
  const dir = scratch();
  const ledger = join(dir, "ledger.jsonl");
  writeFileSync(
    ledger,
    Array.from({ length: 30 }, (_, i) => (i < 12 ? `{"outcome":${i}}` : `{"x":${i}}`)).join("\n"),
  );
  const store = useStore(
    [
      mkProblem(1, {
        status: "retired",
        wakeCondition: {
          summary: "ledger reaches 12",
          all: [{ signal: "fileMatches", path: ledger, pattern: '"outcome"', gte: 12 }],
        },
      }),
    ],
    [
      mkSpark(2, {
        status: "tried",
        wakeCondition: {
          summary: "ledger reaches 20",
          all: [{ signal: "fileMatches", path: ledger, pattern: '"outcome"', gte: 20 }],
        },
      }),
      mkSpark(3, {
        wakeCondition: {
          summary: "watches a ghost",
          all: [{ signal: "fileLines", path: join(dir, "nope.txt"), gte: 5 }],
        },
      }),
    ],
  );
  const out = execFileSync(process.execPath, [INDEX_JS, "--digest"], {
    env: { ...process.env, SEVEN_DPT_DB: store },
    encoding: "utf8",
  });
  assert.match(out, /WAKE — ripe, act or re-park:/);
  assert.match(out, /problem #1 — ledger reaches 12 .* ✓/);
  assert.match(out, /reopen with update_problem\(1, status: "open"\)/);
  assert.match(out, /wake source unreadable — fix the aim:/);
  assert.match(out, /spark #3 .*nope\.txt → ENOENT/);
  assert.match(out, /ripening: spark #2 ledger\.jsonl 12\/20 \(60%\)/);
});

test("--wake integration: full ledger with atom echoes", () => {
  const store = useStore(
    [],
    [
      mkSpark(1, {
        status: "tried",
        wakeCondition: { summary: "grow the corpus", all: [{ signal: "sparkCount", gte: 10 }] },
      }),
    ],
  );
  const out = execFileSync(process.execPath, [INDEX_JS, "--wake"], {
    env: { ...process.env, SEVEN_DPT_DB: store },
    encoding: "utf8",
  });
  assert.match(out, /spark #1 \[ripening 10%\] — grow the corpus/);
  assert.match(out, /atoms: \[ripening\] sparks 1\/10/);
  assert.match(out, /next: the next step/);
});

test("digest prints nothing when the store has nothing to say", () => {
  const store = useStore([], []);
  const out = execFileSync(process.execPath, [INDEX_JS, "--digest"], {
    env: { ...process.env, SEVEN_DPT_DB: store },
    encoding: "utf8",
  });
  assert.equal(out, "");
});
