#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import {
  addProblem,
  captureSpark,
  getProblem,
  listProblems,
  sparksAwaitingGrade,
  storePath,
  updateProblem,
  updateSpark,
  type Problem,
} from "./store.js";

function fmtProblem(p: Problem): string {
  const tags = p.tags.length ? ` [${p.tags.join(", ")}]` : "";
  const stmt = p.statement ? `\n    ${p.statement}` : "";
  const res = p.resolution ? `\n    resolution: ${p.resolution}` : "";
  return `#${p.id} (${p.status})${tags} — ${p.title}${stmt}${res}`;
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
  if (problems.length === 0 && ungraded.length === 0) return ""; // print nothing rather than add noise
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
  return blocks.join("\n\n");
}

if (process.argv.includes("--digest")) {
  const digest = buildDigest();
  if (digest) process.stdout.write(digest + "\n");
  process.exit(0);
}

const server = new McpServer({ name: "seven-dpt", version: "0.1.2" });

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
          "Why it left the open set + the re-open trigger (write one whenever closing; for a merge, name the absorbing problem)",
        ),
      tags: z.array(z.string()).optional().describe("Replace the tag list"),
    },
  },
  async ({ id, title, statement, framing, status, resolution, tags }) => {
    const problem = updateProblem({ id, title, statement, framing, status, resolution, tags });
    if (!problem) return { content: [{ type: "text", text: `No problem #${id}.` }], isError: true };
    return { content: [{ type: "text", text: `Updated:\n${fmtProblem(problem)}` }] };
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
              `  • [spark #${s.id} · ${s.status}] ${s.idea}\n      next: ${s.nextStep}` +
              (s.costToOpen !== null || s.cost !== null || s.value !== null
                ? `\n      cost-to-open: ${s.costToOpen ?? "?"} · actual cost: ${s.cost ?? "?"} · value: ${s.value ?? "?"}`
                : "") +
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
    },
  },
  async ({ problemId, trick, idea, nextStep, costToOpen, cost }) => {
    const spark = captureSpark({ problemId, trick, idea, nextStep, costToOpen, cost });
    if (!spark)
      return { content: [{ type: "text", text: `No problem #${problemId}; spark not saved.` }], isError: true };
    const co = spark.costToOpen !== null ? ` · cost-to-open ${spark.costToOpen}` : "";
    return {
      content: [{ type: "text", text: `Captured spark #${spark.id} on problem #${problemId}${co}.\nNext step: ${nextStep}` }],
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
    },
  },
  async ({ id, outcome, status, costToOpen, cost, value }) => {
    const spark = updateSpark({ id, outcome, status, costToOpen, cost, value });
    if (!spark) return { content: [{ type: "text", text: `No spark #${id}.` }], isError: true };
    const bits = [`status=${spark.status}`];
    if (spark.cost !== null) bits.push(`cost=${spark.cost}`);
    if (spark.value !== null) bits.push(`value=${spark.value}`);
    const tail = spark.outcome ? `, outcome: ${spark.outcome}` : "";
    return { content: [{ type: "text", text: `Updated spark #${spark.id}: ${bits.join(", ")}${tail}` }] };
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
