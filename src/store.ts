import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, join } from "node:path";

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
  // Structured, COMPUTABLE re-open trigger, evaluated by the ambient digest — the machine
  // half of `resolution`'s prose trigger. Only parked (solved/retired) problems carry one;
  // reopening clears it. null = no automatic wake (a permanent exclusion is a valid state).
  wakeCondition: WakeCondition | null;
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
  // Stated p(works) at capture — the calibration channel: once enough sparks resolve, compare
  // stated priors to realized outcomes and de-bias. IMMUTABLE by design: update_spark never
  // touches it, because a post-hoc revision would let hindsight contaminate exactly that audit.
  prior: number | null;
  // Logical TYPE of the claim (0.1.5, from the scope-leak census): a null result against a
  // UNIVERSAL claim kills the claim; against an EXISTENTIAL-BOUNDED one it kills only the tested
  // frame — the census measured 12-20% of verdicts banking frame-nulls in kill vocabulary.
  // WRITE-ONCE: settable late (backfill beats never) but immutable once stated.
  claimType: "universal" | "existential-bounded" | null;
  // The content statement: one sentence naming an observation this spark RULES OUT — the
  // conjecture-side twin of a pre-registered gate (a spark that forbids nothing is
  // unfalsifiable spend). WRITE-ONCE, same anti-hindsight rationale as `prior`.
  forbids: string | null;
  // The retirement predicate — when to ABANDON rather than re-park: the dual of wakeCondition
  // (wake = when a parked spark revives; exhaustion = when it dies). Without it a parked
  // existential is unkillable-in-practice. WRITE-ONCE.
  exhaustion: string | null;
  // FORWARD estimate of the effort to chase this spark to a verdict, set at capture and PRESERVED:
  // update_spark refines `cost` to the realized spend but never touches this. It is the Pandora/
  // Gittins "cost to open the box" the spend-policy ranks on — kept separate so resolving a spark
  // cannot overwrite its a-priori estimate. null until logged; analysis falls back to `cost` when absent.
  costToOpen: number | null;
  cost: number | null; // effort to chase this spark to a verdict — refined to the ACTUAL on update_spark
  value: number | null; // graded payoff: 0 if it failed / yielded nothing, higher for bigger wins
  resolvedAt: string | null; // when status first reached worked/failed — for resolution lag
  // Parked-spark re-run trigger (a probe STOPped/HOLD with a stated wake), evaluated by the
  // digest like a problem's. Cleared automatically when the spark resolves worked/failed.
  wakeCondition: WakeCondition | null;
  createdAt: string;
  updatedAt: string;
}

// ---------- wake conditions (0.1.4) ----------
// A retired problem or parked spark carries a computable re-open trigger; the digest
// evaluates every condition at session start, so the wait has a live owner instead of
// "someone will remember." No auto-reopen: ripeness is surfaced, the model/human acts.

export type WakeAtom =
  | { signal: "sparkCount"; gte: number } // total sparks in the store
  | { signal: "resolvedSparkCount"; gte: number } // sparks with a graded value
  | { signal: "openProblemCount"; gte: number } // for cap-drift style triggers
  | { signal: "date"; onOrAfter: string } // "YYYY-MM-DD" not-before gate (UTC)
  | { signal: "fileLines"; path: string; gte: number } // non-empty lines in a file
  | { signal: "fileMatches"; path: string; pattern: string; gte: number } // lines matching a JS regex
  | { signal: "fileCount"; dir: string; suffix?: string; gte: number } // entries in a directory
  | { signal: "manual"; note: string }; // never auto-ripens; carried for the human

export interface WakeCondition {
  summary: string; // one-line human statement of the trigger
  all?: WakeAtom[]; // ripe when EVERY atom is ripe (exactly one of all/any, enforced at the tool edge)
  any?: WakeAtom[]; // ripe when AT LEAST ONE atom is ripe
}

export interface AtomReadout {
  echo: string; // human echo of aim + current/target ("sparks 28/50") — wrong aims must be visible
  state: "ripe" | "ripening" | "manual" | "unreadable";
  progress: number | null; // 0..1 for numeric atoms; null for manual/unreadable
}

export interface WakeReadout {
  state: "ripe" | "ripening" | "manual-gate" | "unreadable";
  progress: number | null;
  binding: string; // compact echo of the deciding atom (weakest link for all, best for any)
  atoms: AtomReadout[];
}

export interface WakeEntry {
  kind: "problem" | "spark";
  id: number;
  context: string; // problem title / spark nextStep — the thing acting means doing
  summary: string;
  readout: WakeReadout;
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
      wakeCondition: null,
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
      wakeCondition: p.wakeCondition ?? null,
    }));
    merged.sparks = merged.sparks.map((s) => ({
      ...s,
      prior: s.prior ?? null,
      claimType: s.claimType ?? null,
      forbids: s.forbids ?? null,
      exhaustion: s.exhaustion ?? null,
      costToOpen: s.costToOpen ?? null,
      cost: s.cost ?? null,
      value: s.value ?? null,
      resolvedAt: s.resolvedAt ?? null,
      wakeCondition: s.wakeCondition ?? null,
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
    wakeCondition: null,
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
  wakeCondition?: WakeCondition | null;
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
  if (input.wakeCondition !== undefined) problem.wakeCondition = input.wakeCondition;
  // A wake condition belongs to a PARKED problem: whatever else this update did, an open
  // problem carries none — so reopening auto-clears (parked -> active unparks the wait).
  if (problem.status === "open") problem.wakeCondition = null;
  problem.updatedAt = now();
  save(db);
  return problem;
}

export function captureSpark(input: {
  problemId: number;
  trick: string;
  idea: string;
  nextStep: string;
  prior?: number;
  claimType?: "universal" | "existential-bounded";
  forbids?: string;
  exhaustion?: string;
  costToOpen?: number;
  cost?: number;
  wakeCondition?: WakeCondition;
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
    prior: input.prior ?? null,
    claimType: input.claimType ?? null,
    forbids: input.forbids ?? null,
    exhaustion: input.exhaustion ?? null,
    // The a-priori estimate IS the forward cost-to-open; keep it in its own field so a later
    // update_spark that refines `cost` to the realized spend can't destroy it. Accept the legacy
    // `cost` arg as the estimate too, for callers written before costToOpen existed.
    costToOpen: input.costToOpen ?? input.cost ?? null,
    cost: input.cost ?? null,
    value: null,
    resolvedAt: null,
    // A spark can be born parked behind a gate (captured now, actionable when X) — the
    // digest owns the wait from day one.
    wakeCondition: input.wakeCondition ?? null,
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
  claimType?: "universal" | "existential-bounded";
  forbids?: string;
  exhaustion?: string;
  costToOpen?: number;
  cost?: number;
  value?: number;
  wakeCondition?: WakeCondition | null;
}): Spark | null {
  const db = load();
  const spark = db.sparks.find((s) => s.id === input.id);
  if (!spark) return null;
  if (input.outcome !== undefined) spark.outcome = input.outcome;
  if (input.status !== undefined) spark.status = input.status;
  // `prior` is deliberately NOT accepted here: stated-at-capture credences are immutable,
  // or the calibration audit they exist for would be contaminated by hindsight.
  // claimType/forbids/exhaustion are WRITE-ONCE: settable here only while unset (late backfill
  // beats never), but an existing statement never changes — revising what a spark forbids, or
  // its claim scope, after seeing results is the conventionalist stratagem the fields block.
  if (input.claimType !== undefined && spark.claimType === null) spark.claimType = input.claimType;
  if (input.forbids !== undefined && spark.forbids === null) spark.forbids = input.forbids;
  if (input.exhaustion !== undefined && spark.exhaustion === null) spark.exhaustion = input.exhaustion;
  // costToOpen is the forward estimate — revisable before resolution, but resolution never
  // auto-touches it (that is the whole point of keeping it separate from `cost`).
  if (input.costToOpen !== undefined) spark.costToOpen = input.costToOpen;
  if (input.cost !== undefined) spark.cost = input.cost;
  if (input.value !== undefined) spark.value = input.value;
  if (input.wakeCondition !== undefined) spark.wakeCondition = input.wakeCondition;
  // Stamp resolution time once, when the spark first reaches a terminal verdict (for lag).
  if ((spark.status === "worked" || spark.status === "failed") && spark.resolvedAt === null) {
    spark.resolvedAt = now();
  }
  // Resolution unparks: a terminal verdict makes any wake condition moot (set-wake +
  // resolve in one call therefore resolves — predictable over clever).
  if (spark.status === "worked" || spark.status === "failed") spark.wakeCondition = null;
  spark.updatedAt = now();
  save(db);
  return spark;
}

// ---------- wake-condition evaluation ----------

// The digest runs in a SessionStart hook — evaluation must stay fast, so file reads are
// capped rather than streamed. Over-cap counts as unreadable: loud beats slow.
const MAX_WAKE_FILE = 10 * 1024 * 1024;

function expandPath(p: string): string {
  return p.startsWith("~/") ? join(homedir(), p.slice(2)) : p;
}

function numAtom(label: string, current: number, target: number): AtomReadout {
  return {
    echo: `${label} ${current}/${target}`,
    state: current >= target ? "ripe" : "ripening",
    progress: Math.min(current / target, 1),
  };
}

// An unreadable source must SCREAM, not sit at 0% forever — a wake condition whose file
// vanished would otherwise be silence indistinguishable from "not ripe yet."
function unreadableAtom(source: string, why: string): AtomReadout {
  return { echo: `${source} → ${why}`, state: "unreadable", progress: null };
}

function readCapped(rawPath: string): { text: string } | { err: string } {
  const path = expandPath(rawPath);
  try {
    if (statSync(path).size > MAX_WAKE_FILE) return { err: "exceeds 10 MB cap" };
    return { text: readFileSync(path, "utf8") };
  } catch (e) {
    return { err: (e as NodeJS.ErrnoException).code ?? "unreadable" };
  }
}

function evalAtom(atom: WakeAtom, db: DB): AtomReadout {
  switch (atom.signal) {
    case "sparkCount":
      return numAtom("sparks", db.sparks.length, atom.gte);
    case "resolvedSparkCount":
      return numAtom("resolved sparks", db.sparks.filter((s) => s.value !== null).length, atom.gte);
    case "openProblemCount":
      return numAtom("open problems", db.problems.filter((p) => p.status === "open").length, atom.gte);
    case "date": {
      const open = now().slice(0, 10) >= atom.onOrAfter;
      return {
        echo: open ? `gate open since ${atom.onOrAfter}` : `gate ${atom.onOrAfter}`,
        state: open ? "ripe" : "ripening",
        progress: open ? 1 : 0,
      };
    }
    case "fileLines": {
      const r = readCapped(atom.path);
      if ("err" in r) return unreadableAtom(atom.path, r.err);
      const n = r.text.split("\n").filter((l) => l.length > 0).length;
      return numAtom(basename(expandPath(atom.path)), n, atom.gte);
    }
    case "fileMatches": {
      const r = readCapped(atom.path);
      if ("err" in r) return unreadableAtom(atom.path, r.err);
      let re: RegExp;
      try {
        re = new RegExp(atom.pattern);
      } catch {
        return unreadableAtom(atom.path, `invalid regex ${JSON.stringify(atom.pattern)}`);
      }
      const n = r.text.split("\n").filter((l) => re.test(l)).length;
      return numAtom(basename(expandPath(atom.path)), n, atom.gte);
    }
    case "fileCount": {
      const dir = expandPath(atom.dir);
      try {
        const n = readdirSync(dir).filter((f) => (atom.suffix ? f.endsWith(atom.suffix) : true)).length;
        return numAtom(basename(dir), n, atom.gte);
      } catch (e) {
        return unreadableAtom(atom.dir, (e as NodeJS.ErrnoException).code ?? "unreadable");
      }
    }
    case "manual":
      return { echo: `manual: ${atom.note}`, state: "manual", progress: null };
  }
}

// A manual note states the real bar in full; the digest has one line. Take the first
// clause, capped — enough to recognise the bar, never enough to swamp the numeric echo.
function shortNote(echo: string, cap = 72): string {
  const body = echo.replace(/^manual: /, "").split(/(?<=[.;:])\s|\s—\s/)[0].trim();
  return body.length > cap ? `${body.slice(0, cap - 1)}…` : body;
}

function evalCondition(cond: WakeCondition, db: DB): WakeReadout {
  const mode = cond.all ? "all" : "any";
  const atoms = (cond.all ?? cond.any ?? []).map((a) => evalAtom(a, db));
  const numeric = atoms.filter((a) => a.progress !== null);
  const hasUnreadable = atoms.some((a) => a.state === "unreadable");
  const hasManual = atoms.some((a) => a.state === "manual");

  let state: WakeReadout["state"];
  let bindingAtom: AtomReadout | undefined;
  if (mode === "any") {
    // Ripe when any atom fires; the binding echo is the ripe (else best-progress) atom.
    bindingAtom = numeric.reduce<AtomReadout | undefined>(
      (best, a) => (best === undefined || a.progress! > best.progress! ? a : best),
      undefined,
    );
    const ripeAtom = atoms.find((a) => a.state === "ripe");
    if (ripeAtom) {
      state = "ripe";
      bindingAtom = ripeAtom;
    } else if (hasUnreadable) state = "unreadable";
    else state = "ripening";
  } else {
    // Ripe when every numeric atom fires AND no manual atom remains; a manual atom turns
    // full numeric ripeness into "manual-gate" — check due, never auto-fired.
    //
    // Binding = weakest link, and a MANUAL ATOM IS ALWAYS THE WEAKEST: it cannot ripen on
    // its own, so no numeric atom can be the constraint while one is outstanding. Binding
    // used to be reduced over `numeric` alone, which made the manual bar structurally
    // invisible — spark #50 read "prior-ledger 522/560 (93%)" in the digest for a month
    // while its real bar (a manual census, 2 of 6 distinct-value arms) had not moved. The
    // number on display was the LEAST informative one available: #50's line atom had been
    // raised to 560 precisely so the numeric half could not fire alone. A percentage is
    // still shown, because approach to "check due" is real progress — but it is never
    // shown alone, and it never claims to be progress toward ripe.
    const manualAtom = atoms.find((a) => a.state === "manual");
    const weakestNumeric = numeric.reduce<AtomReadout | undefined>(
      (worst, a) => (worst === undefined || a.progress! < worst.progress! ? a : worst),
      undefined,
    );
    if (hasUnreadable) state = "unreadable"; // an all-condition with a blind atom can't be known ripe
    else if (numeric.length > 0 && numeric.every((a) => a.state === "ripe"))
      state = hasManual ? "manual-gate" : "ripe";
    else state = "ripening"; // includes pure-manual conditions: they can never auto-ripen

    if (hasUnreadable) bindingAtom = atoms.find((a) => a.state === "unreadable");
    else if (state === "manual-gate") bindingAtom = manualAtom; // numerics are in; the judgement is the gate
    else bindingAtom = weakestNumeric ?? manualAtom;

    // The numerics are still climbing AND a manual bar is outstanding: name both, or the
    // percentage reads as the whole constraint.
    if (state === "ripening" && manualAtom && weakestNumeric)
      return {
        state,
        progress: weakestNumeric.progress,
        binding: `${weakestNumeric.echo} · manual bar unmet: ${shortNote(manualAtom.echo)}`,
        atoms,
      };
  }
  return {
    state,
    progress: bindingAtom?.progress ?? null,
    binding: bindingAtom?.echo ?? atoms[0]?.echo ?? "",
    atoms,
  };
}

// Evaluate one condition against the current store (arm-time echoes, fmtProblem).
export function evaluateWake(cond: WakeCondition): WakeReadout {
  return evalCondition(cond, load());
}

// Every parked problem/spark carrying a condition, evaluated now — ripe first, then by
// how close to ripe. This is what the digest and wake_status render.
export function wakeLedger(): WakeEntry[] {
  const db = load();
  const entries: WakeEntry[] = [];
  for (const p of db.problems) {
    if (p.wakeCondition)
      entries.push({
        kind: "problem",
        id: p.id,
        context: p.title,
        summary: p.wakeCondition.summary,
        readout: evalCondition(p.wakeCondition, db),
      });
  }
  for (const s of db.sparks) {
    if (s.wakeCondition)
      entries.push({
        kind: "spark",
        id: s.id,
        context: s.nextStep,
        summary: s.wakeCondition.summary,
        readout: evalCondition(s.wakeCondition, db),
      });
  }
  const order: Record<WakeReadout["state"], number> = {
    ripe: 0,
    "manual-gate": 1,
    unreadable: 2,
    ripening: 3,
  };
  return entries.sort(
    (a, b) =>
      order[a.readout.state] - order[b.readout.state] ||
      (b.readout.progress ?? -1) - (a.readout.progress ?? -1) ||
      a.id - b.id,
  );
}
