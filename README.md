# seven-dpt-mcp

A tiny, local MCP server that gives Claude (in any project) a persistent set of
**long-running problems** and a loop for cracking them — Feynman's *twelve favorite
problems* method, driven by the tripartite model of inspiration.

- **Feynman's method** (via Gian-Carlo Rota): keep ~a dozen problems dormant in mind;
  every time you meet a new *trick*, test it against all of them.
- **Inspiration = evocation + transcendence + approach motivation** (Thrash & Elliot):
  a stimulus *evokes* a possibility, you *transcend* the problem's current framing, then
  you're *motivated* to act on it.

The server holds state and scaffolding; the connected model does the thinking — no LLM
runs inside the server, no API key.

## Tools

| Tool | Purpose |
|------|---------|
| `add_problem` | Add a long-running problem to your set |
| `list_problems` | See your open problems |
| `get_problem` | One problem + every spark (idea, next step, outcome) — the memory |
| `evoke` | **The loop.** Feed it a trick; returns your problems + a scaffold walking evocation → transcendence → approach |
| `capture_spark` | Persist a candidate idea + concrete next step against a problem (+ an optional `cost` estimate) |
| `update_spark` | Record a spark's outcome — status (tried/worked/failed), `cost` (effort spent), `value` (graded payoff, `0` for a miss). **Log failures too**; the zero-value outcomes are the signal a background-effort policy is learned from |

Storage: `~/.local/share/seven-dpt/store.json` (override with `SEVEN_DPT_DB`). One store,
shared by every project = one brain.

## How it bootstraps

On first run (no store file yet), the store **seeds itself with seven-dpt's own five open
product problems** — auto-detection of recurring issues, the background-spend policy,
proactive surfacing, keeping the set near twelve, and storage scaling. Design decision,
made deliberately: the seeds are **tool-generic** (identical for every install, about the
tool rather than about you), so the server dogfoods its own method from minute one and the
ambient digest has something to show before you add your own problems. They are ordinary
rows in *your* store — edit, replace, or clear them freely; an existing store is never
touched. So the moment it runs it is already "taking care of its own problems": while you
work on anything else, those sit in context and can be sparked by unrelated discoveries.
The *policy* for how/when/how-much to chase background problems is deliberately **not**
coded — it's meant to be learned later from the accumulated `spark → outcome` history,
which is why `update_spark` exists.

That history is the **reward channel**: each spark carries a `cost` (effort to a verdict) and,
once resolved, a `value` (graded payoff, `0` for a miss). `analysis/reservation_value.py` turns it
into a Pandora's-Box / Gittins reservation-value ranking — but it **gates on data sufficiency** and
refuses to emit numbers until enough resolved sparks (with cost + value, *including failures*)
accrue, so the policy is never fit on false precision.

## Install (turn on for all projects)

### Via npm (recommended)

Published on npm — no build step. Register it for every project (user scope):

```bash
claude mcp add --scope user seven-dpt -- npx -y seven-dpt-mcp
```

### From source (alternative)

```bash
npm install && npm run build
# Register for every project (user scope). Use an ABSOLUTE node path — hooks and MCP
# servers don't source your shell profile, so nvm-style setups need one:
claude mcp add --scope user seven-dpt -- "$(command -v node)" "$(pwd)/dist/index.js"
```

Then make the problems **ambient** — merge into `~/.claude/settings.json` so every
session opens with your dormant problems in context:

```jsonc
{
  "hooks": {
    "SessionStart": [
      { "matcher": "startup", "hooks": [{ "type": "command", "command": "npx -y seven-dpt-mcp --digest", "timeout": 10 }] },
      { "matcher": "resume",  "hooks": [{ "type": "command", "command": "npx -y seven-dpt-mcp --digest", "timeout": 10 }] },
      { "matcher": "clear",   "hooks": [{ "type": "command", "command": "npx -y seven-dpt-mcp --digest", "timeout": 10 }] }
    ]
  }
}
```

(Installed from source instead? Replace each command with an absolute node path +
`/absolute/path/to/seven-dpt-mcp/dist/index.js --digest` — hooks don't source your shell
profile, so nvm-style setups need the absolute path.)

(`--digest` prints nothing when no problems are open; a fresh install prints the five
seeded ones — that's the bootstrap working, not noise.)

## Validate the idea

1. Add a few of your own long-running problems — `add_problem`.
2. When you hit an interesting technique in any repo, `evoke` it; watch Claude test it
   against every problem and reframe the ones that light up.
3. Let it `capture_spark` the hits, then `update_spark` once you've tried them.
4. Days later, `get_problem` — if that accumulated trail feels useful, the idea's proven.

## Known MVP limits (intentional)

- JSON file, last-write-wins (fine for one user).
- No `retire`/`solve`/`update_problem` yet — the 12-cap only warns. (Tracked as one of
  seven-dpt's own seeded problems.)
- `evoke` matching is done by the connected model, not pre-ranked by embeddings.

## License

Apache-2.0 — see [LICENSE](LICENSE).
