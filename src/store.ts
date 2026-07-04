import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

export type ProblemStatus = "open" | "solved" | "retired";
export type SparkStatus = "pending" | "tried" | "worked" | "failed";

export interface Problem {
  id: number;
  title: string;
  statement: string;
  framing: string;
  status: ProblemStatus;
  tags: string[];
  origin: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Spark {
  id: number;
  problemId: number;
  trick: string;
  idea: string;
  nextStep: string;
  outcome: string | null;
  status: SparkStatus;
  // Reward channel — the signal a spend-policy (problem #2) is learned from. Without these,
  // "how much to spend on background problems" is unlearnable by any method (Gittins/market/RL
  // all consume the same history). null until logged.
  cost: number | null; // effort to chase this spark to a verdict (a consistent scale)
  value: number | null; // graded payoff: 0 if it failed / yielded nothing, higher for bigger wins
  resolvedAt: string | null; // when status first reached worked/failed — for resolution lag
  createdAt: string;
  updatedAt: string;
}

interface DB {
  version: number;
  nextProblemId: number;
  nextSparkId: number;
  problems: Problem[];
  sparks: Spark[];
}

// Feynman kept "about a dozen." The cap is advisory in this MVP — we warn, not block.
export const SOFT_CAP = 12;

export function storePath(): string {
  if (process.env.SEVEN_DPT_DB) return process.env.SEVEN_DPT_DB;
  const base = process.env.XDG_DATA_HOME || join(homedir(), ".local", "share");
  return join(base, "seven-dpt", "store.json");
}

function emptyDB(): DB {
  return { version: 1, nextProblemId: 1, nextSparkId: 1, problems: [], sparks: [] };
}

// A FRESH install starts with seven-dpt's own open product problems — the tool dogfoods
// its own method from the first run, and the ambient digest has something to show before
// the user adds their own set. Tool-generic by design (identical for every install, about
// the tool rather than the user); they are ordinary rows in the user's store — edit,
// replace, or retire freely. An existing store is never touched.
function seededDB(): DB {
  const db = emptyDB();
  const ts = now();
  const seeds: Array<{ title: string; statement: string; tags: string[] }> = [
    {
      title: "Detect recurring issues automatically from ongoing work",
      statement:
        "Notice when a mistake or theme recurs across sessions without being told — recurrence is the signal a dormant problem should wake up.",
      tags: ["seven-dpt", "detection"],
    },
    {
      title: "Learn how/when/how much to spend on background problems",
      statement:
        "A policy for chasing sparks: most bets fail, value is heavy-tailed. Learn it from the spark cost/value history (see analysis/reservation_value.py) instead of hard-coding it.",
      tags: ["seven-dpt", "spend-policy"],
    },
    {
      title: "Surface a dormant problem's trail proactively when it is sparked",
      statement:
        "When new work touches an old problem, bring that problem's accumulated sparks into view unprompted — the right memory at the right moment.",
      tags: ["seven-dpt", "surfacing"],
    },
    {
      title: "Keep the active set near twelve (retire / solve / merge)",
      statement:
        "Feynman kept ~a dozen so they stay live in mind. The cap is only advisory today; build/learn the retire-solve-merge loop that keeps the set sharp.",
      tags: ["seven-dpt", "curation"],
    },
    {
      title: "Graduate storage from JSON to SQLite + embedding-ranked evoke",
      statement:
        "The JSON store and model-side evoke matching are deliberate MVP choices; outgrow them when the spark history or problem set demands it.",
      tags: ["seven-dpt", "storage"],
    },
  ];
  for (const s of seeds) {
    db.problems.push({
      id: db.nextProblemId++,
      title: s.title,
      statement: s.statement,
      framing: "",
      status: "open",
      tags: s.tags,
      origin: "ships with seven-dpt (its own open problems — edit or retire freely)",
      createdAt: ts,
      updatedAt: ts,
    });
  }
  return db;
}

function load(): DB {
  const path = storePath();
  // Missing file = fresh install -> seeded. (A CORRUPT file below falls back to EMPTY,
  // not seeded: that is an incident to notice, not a fresh start to paper over.)
  if (!existsSync(path)) return seededDB();
  try {
    const db = JSON.parse(readFileSync(path, "utf8")) as Partial<DB>;
    const merged = { ...emptyDB(), ...db } as DB;
    // Backfill the reward-channel fields on sparks written before they existed.
    merged.sparks = merged.sparks.map((s) => ({
      ...s,
      cost: s.cost ?? null,
      value: s.value ?? null,
      resolvedAt: s.resolvedAt ?? null,
    }));
    return merged;
  } catch {
    // Corrupt/partial file: start clean rather than crash the server.
    return emptyDB();
  }
}

function save(db: DB): void {
  const path = storePath();
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, JSON.stringify(db, null, 2), "utf8");
  renameSync(tmp, path); // atomic-ish swap so a crashed write can't truncate the store
}

function now(): string {
  return new Date().toISOString();
}

export function listProblems(includeClosed: boolean): Problem[] {
  const db = load();
  const ps = includeClosed ? db.problems : db.problems.filter((p) => p.status === "open");
  return ps.sort((a, b) => a.id - b.id);
}

export function getProblem(id: number): { problem: Problem; sparks: Spark[] } | null {
  const db = load();
  const problem = db.problems.find((p) => p.id === id);
  if (!problem) return null;
  const sparks = db.sparks.filter((s) => s.problemId === id).sort((a, b) => a.id - b.id);
  return { problem, sparks };
}

export function addProblem(input: {
  title: string;
  statement?: string;
  tags?: string[];
  origin?: string;
}): { problem: Problem; warning?: string } {
  const db = load();
  const ts = now();
  const problem: Problem = {
    id: db.nextProblemId++,
    title: input.title,
    statement: input.statement ?? "",
    framing: "",
    status: "open",
    tags: input.tags ?? [],
    origin: input.origin ?? null,
    createdAt: ts,
    updatedAt: ts,
  };
  db.problems.push(problem);
  save(db);

  const openCount = db.problems.filter((p) => p.status === "open").length;
  const warning =
    openCount > SOFT_CAP
      ? `You now have ${openCount} open problems. Feynman kept about ${SOFT_CAP} so they stay live in mind — consider consolidating or retiring some.`
      : undefined;
  return { problem, warning };
}

export function captureSpark(input: {
  problemId: number;
  trick: string;
  idea: string;
  nextStep: string;
  cost?: number;
}): Spark | null {
  const db = load();
  const problem = db.problems.find((p) => p.id === input.problemId);
  if (!problem) return null;
  const ts = now();
  const spark: Spark = {
    id: db.nextSparkId++,
    problemId: input.problemId,
    trick: input.trick,
    idea: input.idea,
    nextStep: input.nextStep,
    outcome: null,
    status: "pending",
    cost: input.cost ?? null, // an a-priori effort estimate is fine; refine on update_spark
    value: null,
    resolvedAt: null,
    createdAt: ts,
    updatedAt: ts,
  };
  db.sparks.push(spark);
  problem.updatedAt = ts;
  save(db);
  return spark;
}

export function updateSpark(input: {
  id: number;
  outcome?: string;
  status?: SparkStatus;
  cost?: number;
  value?: number;
}): Spark | null {
  const db = load();
  const spark = db.sparks.find((s) => s.id === input.id);
  if (!spark) return null;
  if (input.outcome !== undefined) spark.outcome = input.outcome;
  if (input.status !== undefined) spark.status = input.status;
  if (input.cost !== undefined) spark.cost = input.cost;
  if (input.value !== undefined) spark.value = input.value;
  // Stamp resolution time once, when the spark first reaches a terminal verdict (for lag).
  if ((spark.status === "worked" || spark.status === "failed") && spark.resolvedAt === null) {
    spark.resolvedAt = now();
  }
  spark.updatedAt = now();
  save(db);
  return spark;
}
