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
  // Why the problem left the open set — and, for a retirement, the explicit RE-OPEN trigger.
  // A retired problem is parked with a wake condition, not deleted; a merge is a retirement
  // whose resolution names the absorbing problem. null while open.
  resolution: string | null;
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
  // FORWARD estimate of the effort to chase this spark to a verdict, set at capture and PRESERVED:
  // update_spark refines `cost` to the realized spend but never touches this. It is the Pandora/
  // Gittins "cost to open the box" the spend-policy ranks on — kept separate so resolving a spark
  // cannot overwrite its a-priori estimate. null until logged; analysis falls back to `cost` when absent.
  costToOpen: number | null;
  cost: number | null; // effort to chase this spark to a verdict — refined to the ACTUAL on update_spark
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

// Feynman kept "about a dozen." Adding beyond the cap is refused until something is
// retired/solved/merged (update_problem) — or explicitly overridden with overCap.
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
      resolution: null,
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
    // Backfill fields written before they existed.
    merged.problems = merged.problems.map((p) => ({
      ...p,
      resolution: p.resolution ?? null,
    }));
    merged.sparks = merged.sparks.map((s) => ({
      ...s,
      costToOpen: s.costToOpen ?? null,
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

// Sparks acted on (status past `pending`) but never given a graded `value` — the reward
// channel left half-open. Surfaced in the ambient digest so they get closed out: an
// ungraded outcome (especially an unlogged failure) is exactly what leaves problem #2's
// spend-policy unlearnable, since every allocator method consumes this same cost/value history.
export function sparksAwaitingGrade(): Spark[] {
  const db = load();
  return db.sparks
    .filter((s) => s.value === null && s.status !== "pending")
    .sort((a, b) => a.id - b.id);
}

export function addProblem(input: {
  title: string;
  statement?: string;
  tags?: string[];
  origin?: string;
  overCap?: boolean;
}): { problem: Problem | null; warning?: string; blocked?: string } {
  const db = load();
  const open = db.problems.filter((p) => p.status === "open");
  // The cap is the method: the set only works if it stays small enough to keep live in mind.
  if (open.length >= SOFT_CAP && !input.overCap) {
    const stalest = [...open]
      .sort((a, b) => a.updatedAt.localeCompare(b.updatedAt))
      .slice(0, 3)
      .map((p) => `#${p.id} ${p.title} (last touched ${p.updatedAt.slice(0, 10)})`)
      .join("\n  ");
    return {
      problem: null,
      blocked:
        `Not added: ${open.length} problems are already open and Feynman's cap is ~${SOFT_CAP}. ` +
        `Retire, solve, or merge one first (update_problem) — stalest candidates:\n  ${stalest}\n` +
        `Or pass overCap: true if this one genuinely earns an over-cap slot.`,
    };
  }
  const ts = now();
  const problem: Problem = {
    id: db.nextProblemId++,
    title: input.title,
    statement: input.statement ?? "",
    framing: "",
    status: "open",
    resolution: null,
    tags: input.tags ?? [],
    origin: input.origin ?? null,
    createdAt: ts,
    updatedAt: ts,
  };
  db.problems.push(problem);
  save(db);

  const warning =
    open.length + 1 > SOFT_CAP
      ? `You now have ${open.length + 1} open problems (cap ~${SOFT_CAP}, overridden). Retire or merge soon — the set only works if it stays live in mind.`
      : undefined;
  return { problem, warning };
}

export function updateProblem(input: {
  id: number;
  title?: string;
  statement?: string;
  framing?: string;
  status?: ProblemStatus;
  resolution?: string;
  tags?: string[];
}): Problem | null {
  const db = load();
  const problem = db.problems.find((p) => p.id === input.id);
  if (!problem) return null;
  if (input.title !== undefined) problem.title = input.title;
  if (input.statement !== undefined) problem.statement = input.statement;
  if (input.framing !== undefined) problem.framing = input.framing;
  if (input.status !== undefined) problem.status = input.status;
  if (input.resolution !== undefined) problem.resolution = input.resolution;
  if (input.tags !== undefined) problem.tags = input.tags;
  problem.updatedAt = now();
  save(db);
  return problem;
}

export function captureSpark(input: {
  problemId: number;
  trick: string;
  idea: string;
  nextStep: string;
  costToOpen?: number;
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
    // The a-priori estimate IS the forward cost-to-open; keep it in its own field so a later
    // update_spark that refines `cost` to the realized spend can't destroy it. Accept the legacy
    // `cost` arg as the estimate too, for callers written before costToOpen existed.
    costToOpen: input.costToOpen ?? input.cost ?? null,
    cost: input.cost ?? null,
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
  costToOpen?: number;
  cost?: number;
  value?: number;
}): Spark | null {
  const db = load();
  const spark = db.sparks.find((s) => s.id === input.id);
  if (!spark) return null;
  if (input.outcome !== undefined) spark.outcome = input.outcome;
  if (input.status !== undefined) spark.status = input.status;
  // costToOpen is the forward estimate — revisable before resolution, but resolution never
  // auto-touches it (that is the whole point of keeping it separate from `cost`).
  if (input.costToOpen !== undefined) spark.costToOpen = input.costToOpen;
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
