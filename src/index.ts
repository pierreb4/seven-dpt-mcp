#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import {
  addProblem,
  captureSpark,
  evaluateWake,
  getProblem,
  listProblems,
  sparksAwaitingGrade,
  storePath,
  updateProblem,
  updateSpark,
  wakeLedger,
  type Problem,
  type WakeCondition,
  type WakeEntry,
} from "./store.js";

// ---- wake-condition schema (0.1.4): the machine half of a re-open trigger ----
// Pure-read signals only (store counters, dates, files) — no shell, no network — so the
// package stays portable and user-specific paths live in user DATA, never in code.
const gteSchema = z.number().positive().describe("Threshold — the atom is ripe when current >= gte");
const wakeAtomSchema = z.discriminatedUnion("signal", [
  z.object({ signal: z.literal("sparkCount"), gte: gteSchema }),
  z.object({ signal: z.literal("resolvedSparkCount"), gte: gteSchema }),
  z.object({ signal: z.literal("openProblemCount"), gte: gteSchema }),
  z.object({
    signal: z.literal("date"),
    onOrAfter: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "YYYY-MM-DD"),
  }),
  z.object({ signal: z.literal("fileLines"), path: z.string(), gte: gteSchema }),
  z.object({ signal: z.literal("fileMatches"), path: z.string(), pattern: z.string(), gte: gteSchema }),
  z.object({ signal: z.literal("fileCount"), dir: z.string(), suffix: z.string().optional(), gte: gteSchema }),
  z.object({ signal: z.literal("manual"), note: z.string() }),
]);
const wakeConditionSchema = z
  .object({
    summary: z.string().describe("One-line human statement of the trigger"),
    all: z
      .array(wakeAtomSchema)
      .min(1)
      .optional()
      .describe(
        "Ripe when EVERY atom is ripe. A `manual` atom here means: once the numeric atoms are ripe, surface as 'manual check due' instead of auto-firing.",
      ),
    any: z.array(wakeAtomSchema).min(1).optional().describe("Ripe when AT LEAST ONE atom is ripe"),
  })
  .refine((c) => (c.all ? 1 : 0) + (c.any ? 1 : 0) === 1, {
    message: "Provide exactly one of all/any",
  });

function wakeLabel(e: WakeEntry): string {
  return e.kind === "problem" ? `problem #${e.id}` : `spark #${e.id}`;
}

function truncate(s: string, n: number): string {
  const one = s.replace(/\s+/g, " ").trim();
  return one.length <= n ? one : one.slice(0, n - 1) + "…";
}

function pctOf(p: number | null): string {
  return p === null ? "" : ` ${Math.round(p * 100)}%`;
}

function fmtWakeEntry(e: WakeEntry): string {
  const r = e.readout;
  return [
    `${wakeLabel(e)} [${r.state}${pctOf(r.progress)}] — ${e.summary}`,
    `    atoms: ${r.atoms.map((a) => `[${a.state}] ${a.echo}`).join(" · ")}`,
    `    ${e.kind === "problem" ? "title" : "next"}: ${truncate(e.context, 140)}`,
  ].join("\n");
}

// Echoed at ARM time: a wrong aim (path, suffix, unit) must be visible now, not at wake time.
function fmtWakeArmed(cond: WakeCondition): string {
  const r = evaluateWake(cond);
  return `wake armed [${r.state}${pctOf(r.progress)}]: ${r.atoms
    .map((a) => `[${a.state}] ${a.echo}`)
    .join(" · ")}`;
}

function fmtProblem(p: Problem): string {
  const tags = p.tags.length ? ` [${p.tags.join(", ")}]` : "";
  const stmt = p.statement ? `\n    ${p.statement}` : "";
  const res = p.resolution ? `\n    resolution: ${p.resolution}` : "";
  let wake = "";
  if (p.wakeCondition) {
    const r = evaluateWake(p.wakeCondition);
    wake = `\n    wake [${r.state}${pctOf(r.progress)}]: ${r.binding}`;
  }
  return `#${p.id} (${p.status})${tags} — ${p.title}${stmt}${res}${wake}`;
}

// The theory lives here. evoke() returns this to the connected model so *it* runs
// the loop — the server stores state and scaffolds, but never calls an LLM itself.
function evocationScaffold(trick: string, problems: Problem[]): string {
  const list = problems.length
    ? problems
        .map((p, i) => `${i + 1}. [#${p.id}] ${p.title}${p.statement ? ` — ${p.statement}` : ""}`)
        .join("\n")
    : "(no open problems yet — add some with add_problem)";

  return [
    "Run Feynman's twelve-problems loop, guided by the tripartite model of inspiration",
    "(evocation -> transcendence -> approach motivation).",
    "",
    `STIMULUS (the new trick / result / observation):\n"${trick}"`,
    "",
    `OPEN PROBLEMS — test the stimulus against EACH:\n${list}`,
    "",
    "Then:",
    "1. EVOCATION — For each problem ask: does this stimulus (or a close analogy of it) unlock or advance it? Most will not. Say so in a few words and move on.",
    '2. INVERT (run this on the no-hits before you accept them) — Take the 1-2 dismissals that would matter most if they were wrong. For each, flip the question: *assume* this stimulus is exactly the key to that problem — what non-obvious bridge would have to hold for that to be true? Name the least-obvious such mechanism. If a bridge survives a second look, that problem joins the ones that lit up; if none does, keep the no-hit. A bounded probe against mode-seeking (the reflexive mainstream "no"), not a mandate to find links.',
    '3. TRANSCENDENCE — For the problems that light up (including any rescued by INVERT), reframe: "what is this problem an instance of, such that the stimulus applies?" State the new framing explicitly; aim past the obvious constraints.',
    "4. APPROACH — For each genuine hit, propose ONE concrete next experiment and call capture_spark(problemId, trick, idea, nextStep) to persist it.",
    "",
    "When you later act on a captured spark, record what happened with `update_spark` — status (worked/failed), the cost (effort spent), and the value (graded payoff, 0 for a miss). LOG FAILURES TOO; 'most bets fail', so the zero-value outcomes are exactly what the spend-policy learns from. That outcome history is how this system learns when surfacing a dormant problem is worth the attention.",
    "",
    'Be terse. After the invert pass, "no hit" is a perfectly good answer — do not force connections.',
  ].join("\n");
}

// Non-MCP CLI mode: `--digest` prints the open problems as a compact context block
// and exits. A SessionStart hook runs this so the dormant problems ride along in
// every session — the substrate that lets unrelated work spark an old problem.
function buildDigest(): string {
  const problems = listProblems(false);
  const ungraded = sparksAwaitingGrade();
  const blocks: string[] = [];
  if (problems.length > 0) {
    const lines = problems.map((p) => `  #${p.id} ${p.title}`).join("\n");
    blocks.push(
      "[seven-dpt] Your dormant problems — if anything this session bears on one, run the `evoke` tool with the trick/insight and `capture_spark` any genuine hit:\n" +
        lines,
    );
  }
  if (ungraded.length > 0) {
    const ids = ungraded.map((s) => `#${s.id}`).join(", ");
    blocks.push(
      `[seven-dpt] ${ungraded.length} spark(s) acted on but not yet graded (${ids}) — close the reward channel with update_spark(id, status, cost, value). Log failures too (value 0); the zero-value outcomes are exactly what problem #2's spend-policy is learned from.`,
    );
  }
  blocks.push(...buildWakeBlocks());
  return blocks.join("\n\n"); // "" when nothing to say — the print-nothing rule holds
}

// The wake sections of the digest: ripe entries always, broken aims always, plus one
// compact ripening line (top 3 by progress) so approach is visible before arrival.
function buildWakeBlocks(): string[] {
  const entries = wakeLedger();
  if (entries.length === 0) return [];
  const blocks: string[] = [];

  const act = entries.filter((e) => e.readout.state === "ripe" || e.readout.state === "manual-gate");
  if (act.length > 0) {
    const lines = act.map((e) => {
      const what =
        e.readout.state === "manual-gate"
          ? `manual check due — ${e.readout.atoms
              .filter((a) => a.state === "manual")
              .map((a) => a.echo.replace(/^manual: /, ""))
              .join("; ")}`
          : `${e.readout.atoms
              .filter((a) => a.state === "ripe")
              .map((a) => a.echo)
              .join(" · ")} ✓`;
      const action =
        e.kind === "problem"
          ? `reopen with update_problem(${e.id}, status: "open") — or re-aim its wakeCondition`
          : `act on: ${truncate(e.context, 120)} — or re-park with update_spark(${e.id}, wakeCondition: …)`;
      return `  ${wakeLabel(e)} — ${e.summary} · ${what}\n    → ${action}`;
    });
    blocks.push(`[seven-dpt] WAKE — ripe, act or re-park:\n${lines.join("\n")}`);
  }

  const unreadable = entries.filter((e) => e.readout.atoms.some((a) => a.state === "unreadable"));
  if (unreadable.length > 0) {
    const lines = unreadable.map(
      (e) =>
        `  ${wakeLabel(e)} · ${e.readout.atoms
          .filter((a) => a.state === "unreadable")
          .map((a) => a.echo)
          .join(" · ")}`,
    );
    blocks.push(`[seven-dpt] wake source unreadable — fix the aim:\n${lines.join("\n")}`);
  }

  const ripening = entries
    .filter((e) => e.readout.state === "ripening" && e.readout.progress !== null)
    .slice(0, 3); // wakeLedger is already sorted by progress within the state
  if (ripening.length > 0) {
    const bits = ripening.map((e) => {
      const pct = e.readout.progress! > 0 ? ` (${Math.round(e.readout.progress! * 100)}%)` : "";
      return `${wakeLabel(e)} ${e.readout.binding}${pct}`;
    });
    blocks.push(`[seven-dpt] ripening: ${bits.join(" · ")}`);
  }
  return blocks;
}

// Non-MCP CLI mode: `--wake` prints the full wake ledger (every parked entry, every atom
// echo) and exits — ops parity with wake_status for timers or hands-on checks.
if (process.argv.includes("--wake")) {
  const entries = wakeLedger();
  process.stdout.write(
    entries.length > 0 ? entries.map(fmtWakeEntry).join("\n") + "\n" : "No wake conditions set.\n",
  );
  process.exit(0);
}

if (process.argv.includes("--digest")) {
  const digest = buildDigest();
  if (digest) process.stdout.write(digest + "\n");
  process.exit(0);
}

const server = new McpServer({ name: "seven-dpt", version: "0.1.4" });

server.registerTool(
  "add_problem",
  {
    title: "Add a favorite problem",
    description:
      "Add a long-running problem to your global Feynman set — the ~dozen you keep dormant in mind across every project. Keep the active set small; that constraint is the method.",
    inputSchema: {
      title: z.string().describe("Short name for the problem"),
      statement: z.string().optional().describe("Fuller description / what 'solved' would look like"),
      tags: z.array(z.string()).optional().describe("Freeform tags, e.g. domains or project names"),
      origin: z.string().optional().describe("Where it came from (project, context)"),
      overCap: z
        .boolean()
        .optional()
        .describe(
          "Override the ~twelve-problem cap for this add (only after weighing a retire/merge first — the cap is the method)",
        ),
    },
  },
  async ({ title, statement, tags, origin, overCap }) => {
    const { problem, warning, blocked } = addProblem({ title, statement, tags, origin, overCap });
    if (!problem) return { content: [{ type: "text", text: blocked ?? "Not added." }], isError: true };
    const head = `Added #${problem.id}: ${problem.title}`;
    return { content: [{ type: "text", text: warning ? `${warning}\n\n${head}` : head }] };
  },
);

server.registerTool(
  "update_problem",
  {
    title: "Update / retire / solve a problem",
    description:
      "Edit a problem or move it out of the active set — the retire/solve/merge loop that keeps the set near twelve. When closing (status solved/retired), write a resolution saying WHY plus, for a retirement, the explicit RE-OPEN trigger: a retired problem is parked with a wake condition, not deleted. A merge is a retirement whose resolution names the absorbing problem. Reopen later by setting status back to open.",
    inputSchema: {
      id: z.number().int().describe("Problem id"),
      title: z.string().optional().describe("New short name"),
      statement: z.string().optional().describe("New fuller description"),
      framing: z.string().optional().describe("New framing (the 'instance of what?' reframe)"),
      status: z
        .enum(["open", "solved", "retired"])
        .optional()
        .describe("open (reopen) | solved | retired"),
      resolution: z
        .string()
        .optional()
        .describe(
          "Why it left the open set + the re-open trigger in prose (write one whenever closing; for a merge, name the absorbing problem)",
        ),
      tags: z.array(z.string()).optional().describe("Replace the tag list"),
      wakeCondition: wakeConditionSchema
        .nullable()
        .optional()
        .describe(
          "Structured, COMPUTABLE re-open trigger — the machine half of the resolution prose. The ambient digest evaluates it every session and surfaces ripeness (see wake_status). Parked problems only; pass null to clear; reopening always clears it.",
        ),
    },
  },
  async ({ id, title, statement, framing, status, resolution, tags, wakeCondition }) => {
    // Wake conditions belong to PARKED problems — refuse loudly rather than store a
    // condition the digest would evaluate against an active entry.
    if (wakeCondition != null) {
      const existing = getProblem(id);
      if (!existing) return { content: [{ type: "text", text: `No problem #${id}.` }], isError: true };
      if ((status ?? existing.problem.status) === "open")
        return {
          content: [
            {
              type: "text",
              text: `Problem #${id} is (or would stay) open — wake conditions belong to parked problems. Retire/solve it in the same call, or park a spark instead.`,
            },
          ],
          isError: true,
        };
    }
    const problem = updateProblem({ id, title, statement, framing, status, resolution, tags, wakeCondition });
    if (!problem) return { content: [{ type: "text", text: `No problem #${id}.` }], isError: true };
    const armed =
      wakeCondition != null && problem.wakeCondition ? `\n${fmtWakeArmed(problem.wakeCondition)}` : "";
    return { content: [{ type: "text", text: `Updated:\n${fmtProblem(problem)}${armed}` }] };
  },
);

server.registerTool(
  "list_problems",
  {
    title: "List your favorite problems",
    description: "Show your global set of long-running problems. Defaults to open ones only.",
    inputSchema: {
      includeClosed: z.boolean().optional().describe("Also show solved/retired problems"),
    },
  },
  async ({ includeClosed }) => {
    const problems = listProblems(includeClosed ?? false);
    const text = problems.length
      ? problems.map(fmtProblem).join("\n")
      : "No problems yet. Add some with add_problem.";
    return { content: [{ type: "text", text }] };
  },
);

server.registerTool(
  "get_problem",
  {
    title: "Get a problem and its history",
    description:
      "Show one problem plus every spark (idea + next step + outcome) captured against it — the long-running memory that makes a stuck issue accumulate progress across sessions.",
    inputSchema: { id: z.number().int().describe("Problem id") },
  },
  async ({ id }) => {
    const found = getProblem(id);
    if (!found) return { content: [{ type: "text", text: `No problem #${id}.` }], isError: true };
    const { problem, sparks } = found;
    const header = fmtProblem(problem) + (problem.framing ? `\n    framing: ${problem.framing}` : "");
    const hist = sparks.length
      ? sparks
          .map(
            (s) =>
              `  • [spark #${s.id} · ${s.status}${s.claimType ? ` · ${s.claimType}` : ""}] ${s.idea}\n      next: ${s.nextStep}` +
              (s.prior !== null || s.costToOpen !== null || s.cost !== null || s.value !== null
                ? `\n      ${s.prior !== null ? `prior: ${s.prior} · ` : ""}cost-to-open: ${s.costToOpen ?? "?"} · actual cost: ${s.cost ?? "?"} · value: ${s.value ?? "?"}`
                : "") +
              (s.forbids ? `\n      forbids: ${s.forbids}` : "") +
              (s.exhaustion ? `\n      exhaustion: ${s.exhaustion}` : "") +
              (s.outcome ? `\n      outcome: ${s.outcome}` : "") +
              `\n      (evoked by: ${s.trick})`,
          )
          .join("\n")
      : "  (no sparks captured yet)";
    return { content: [{ type: "text", text: `${header}\n\nSparks:\n${hist}` }] };
  },
);

server.registerTool(
  "evoke",
  {
    title: "Evoke — test a new trick against all your problems",
    description:
      "The core loop. Give it a trick, result, idea, or observation you just encountered. Returns your open problems plus a scaffold that walks you through evocation -> transcendence -> approach. Call this whenever you learn something that might generalize.",
    inputSchema: {
      trick: z
        .string()
        .describe("The new trick / result / insight / observation to test against your problems"),
      project: z.string().optional().describe("Optional: which project you're in right now"),
    },
  },
  async ({ trick }) => {
    const problems = listProblems(false);
    return { content: [{ type: "text", text: evocationScaffold(trick, problems) }] };
  },
);

server.registerTool(
  "capture_spark",
  {
    title: "Capture a spark (approach motivation)",
    description:
      "Persist a candidate solution plus a concrete next step against a problem — the output of a successful evocation. This is the memory that lets long-running issues progress across sessions.",
    inputSchema: {
      problemId: z.number().int().describe("Which problem this advances"),
      trick: z.string().describe("The trick / stimulus that evoked it"),
      idea: z.string().describe("The candidate solution or insight"),
      nextStep: z.string().describe("ONE concrete next experiment or action"),
      prior: z
        .number()
        .min(0)
        .max(1)
        .optional()
        .describe(
          "Your honest stated probability (0-1) at capture that chasing this spark yields a worked outcome. IMMUTABLE afterwards — update_spark cannot revise it — so stated credences can later be calibrated against realized outcomes. State what you believe, not what sounds good; the audit compares.",
        ),
      claimType: z
        .enum(["universal", "existential-bounded"])
        .optional()
        .describe(
          "Logical type of the claim, so a null result kills the right thing: 'universal' = a clean null anywhere kills the CLAIM; 'existential-bounded' = the claim asserts existence within a named frame, so a null kills only the tested FRAME. Most sparks are existential-bounded. Write-once.",
        ),
      forbids: z
        .string()
        .optional()
        .describe(
          "One sentence naming an observation this spark RULES OUT — the content statement (a spark that forbids nothing is unfalsifiable spend). Write-once, immutable like `prior`: revising it after results is the post-hoc rescue it exists to block.",
        ),
      exhaustion: z
        .string()
        .optional()
        .describe(
          "The retirement predicate: when to ABANDON this spark rather than re-park it (the dual of wakeCondition — wake says when it revives, exhaustion says when it dies). E.g. 'second unpowered read at n>=50 abandons the meter'. Write-once.",
        ),
      costToOpen: z
        .number()
        .optional()
        .describe(
          "Rough EXPECTED effort to chase this spark to a verdict, on a consistent scale (e.g. minutes, or a 1-5 effort score). This is the Pandora 'cost to open' the spend-policy ranks on — the a-priori estimate is PRESERVED even after update_spark records the actual spend (unlike `cost`, which it refines).",
        ),
      cost: z
        .number()
        .optional()
        .describe("Legacy alias for costToOpen at capture time (kept for older callers). Prefer costToOpen."),
      wakeCondition: wakeConditionSchema
        .optional()
        .describe(
          "Optional: park this spark behind a computable gate from birth (captured now, actionable when X) — the ambient digest evaluates it and surfaces ripeness.",
        ),
    },
  },
  async ({ problemId, trick, idea, nextStep, prior, claimType, forbids, exhaustion, costToOpen, cost, wakeCondition }) => {
    const spark = captureSpark({ problemId, trick, idea, nextStep, prior, claimType, forbids, exhaustion, costToOpen, cost, wakeCondition });
    if (!spark)
      return { content: [{ type: "text", text: `No problem #${problemId}; spark not saved.` }], isError: true };
    const pr = spark.prior !== null ? ` · prior ${spark.prior}` : "";
    const ct = spark.claimType !== null ? ` · ${spark.claimType}` : "";
    const co = spark.costToOpen !== null ? ` · cost-to-open ${spark.costToOpen}` : "";
    const fb = spark.forbids !== null ? `\nForbids: ${spark.forbids}` : "";
    const armed = spark.wakeCondition ? `\n${fmtWakeArmed(spark.wakeCondition)}` : "";
    return {
      content: [{ type: "text", text: `Captured spark #${spark.id} on problem #${problemId}${pr}${ct}${co}.${fb}${armed}\nNext step: ${nextStep}` }],
    };
  },
);

server.registerTool(
  "update_spark",
  {
    title: "Record a spark's outcome",
    description:
      "Record what happened when you acted on a spark — an outcome note, a new status (tried / worked / failed), and ideally the cost (effort spent) and value (graded payoff). LOG FAILURES TOO: 'most bets fail' is the premise of problem #2, so failed and zero-value outcomes are exactly the signal a spend-policy is learned from — recording only wins makes the history unusable. This outcome history is what lets the system learn when surfacing a dormant problem is worth the attention.",
    inputSchema: {
      id: z.number().int().describe("Spark id"),
      outcome: z.string().optional().describe("What happened when you tried it"),
      status: z
        .enum(["pending", "tried", "worked", "failed"])
        .optional()
        .describe("New status for the spark"),
      claimType: z
        .enum(["universal", "existential-bounded"])
        .optional()
        .describe(
          "Backfill the claim's logical type IF never stated (write-once: ignored when already set). 'universal' = a null kills the claim; 'existential-bounded' = a null kills only the tested frame.",
        ),
      forbids: z
        .string()
        .optional()
        .describe(
          "Backfill the content statement (one observation this spark rules out) IF never stated. Write-once: an existing forbids is immutable — revising it after results is the post-hoc rescue it exists to block.",
        ),
      exhaustion: z
        .string()
        .optional()
        .describe(
          "State the retirement predicate (when to ABANDON rather than re-park — the dual of wakeCondition) IF never stated. Write-once. A parked spark with a wake but no exhaustion is unkillable-in-practice; ledger_invariants.py flags these as ORPHANED-EXISTENTIAL.",
        ),
      costToOpen: z
        .number()
        .optional()
        .describe(
          "Revise the FORWARD cost-to-open estimate (uncommon — normally set once at capture). Resolution never changes it automatically.",
        ),
      cost: z
        .number()
        .optional()
        .describe("ACTUAL effort spent chasing it to a verdict (same scale as capture's estimate)."),
      value: z
        .number()
        .optional()
        .describe(
          "Graded payoff of the outcome: 0 if it failed or yielded nothing, higher for bigger wins (heavy-tailed). The reward signal the budget policy is fit on — log it for failures too.",
        ),
      wakeCondition: wakeConditionSchema
        .nullable()
        .optional()
        .describe(
          "Park a HOLD/STOPped spark with its computable re-run trigger — the digest owns the wait (see wake_status). Pass null to clear; resolving worked/failed auto-clears.",
        ),
    },
  },
  async ({ id, outcome, status, claimType, forbids, exhaustion, costToOpen, cost, value, wakeCondition }) => {
    const spark = updateSpark({ id, outcome, status, claimType, forbids, exhaustion, costToOpen, cost, value, wakeCondition });
    if (!spark) return { content: [{ type: "text", text: `No spark #${id}.` }], isError: true };
    const bits = [`status=${spark.status}`];
    if (spark.cost !== null) bits.push(`cost=${spark.cost}`);
    if (spark.value !== null) bits.push(`value=${spark.value}`);
    // Write-once refusals must be VISIBLE: a silently-dropped backfill would read as saved.
    const refused = (["claimType", "forbids", "exhaustion"] as const).filter(
      (f) => ({ claimType, forbids, exhaustion })[f] !== undefined && spark[f] !== ({ claimType, forbids, exhaustion })[f],
    );
    const kept = refused.length ? `\n(write-once: ${refused.join(", ")} already set — kept the original)` : "";
    const tail = spark.outcome ? `, outcome: ${spark.outcome}` : "";
    const armed =
      wakeCondition != null && spark.wakeCondition ? `\n${fmtWakeArmed(spark.wakeCondition)}` : "";
    return { content: [{ type: "text", text: `Updated spark #${spark.id}: ${bits.join(", ")}${tail}${kept}${armed}` }] };
  },
);

server.registerTool(
  "wake_status",
  {
    title: "Wake-condition ledger",
    description:
      "Evaluate every parked problem/spark's wakeCondition right now: ripeness, progress, and current/target echoes per atom. Read-only. The ambient digest shows the compact version at session start; this is the full view for curation passes.",
    inputSchema: {},
  },
  async () => {
    const entries = wakeLedger();
    if (entries.length === 0)
      return {
        content: [
          {
            type: "text",
            text: "No wake conditions set. Park a problem (update_problem, when retiring/solving) or a spark (capture_spark / update_spark) with a wakeCondition — the digest then owns the wait.",
          },
        ],
      };
    return { content: [{ type: "text", text: entries.map(fmtWakeEntry).join("\n") }] };
  },
);

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // stdout is the JSON-RPC channel — all logging must go to stderr.
  console.error(`seven-dpt MCP server running. Store: ${storePath()}`);
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
