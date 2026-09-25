# Porting notes: pstack, Cursor to Claude Code

Source: [poteto/plugins `pstack`](https://github.com/poteto/plugins/tree/main/pstack) by Lauren Tan
([@poteto](https://x.com/poteto)), MIT. This is a port, not a rewrite. poteto's wording and intent are
preserved; only what Claude Code requires changed. Commit `4926ea7` vendors the source tree unmodified, so
`git diff 4926ea7 -- skills agents` is the exact set of changes Claude Code forced.

Claude Code behavior below was verified against the live docs, downloaded verbatim rather than summarized:
`skills`, `plugins/{overview,components,manifest-reference,marketplace-reference,create,create-marketplace,cli-reference,loading}`,
`sub-agents`, `slash-commands`, `hooks`, `mcp`, `claude-directory`, `commands`. Nothing below uses a field or
command the docs do not confirm.

## The rule that drove most of the port

**A skill with `disable-model-invocation: true` is invisible to Claude.** Its description never enters
context, Claude cannot invoke it, and it cannot be preloaded into a subagent (`skills` frontmatter). pstack
sets that flag on 24 of its 34 skills.

In Cursor that was fine. In Claude Code it silently breaks pstack's central mechanism, because poteto-mode
works by *routing*: "read the leaf skill in full for any principle you apply", "code crossing a function
boundary → the **architect** skill", "contested design → the **interrogate** skill". Every one of those
targets was unreachable. The routing would not error; it would just quietly not happen.

Resolution, per target:

| Skill | pstack | This port | Why |
|---|---|---|---|
| 20 `principle-*` | `disable-model-invocation: true` | `user-invocable: false` | Claude must be able to read a leaf when it applies the principle. Hidden from your `/` menu because invoking a principle is not an action you take |
| `poteto-mode` | `disable-model-invocation: true` | neither flag | Required so `poteto-agent` can preload it. Consequence below |
| `architect`, `interrogate`, `figure-it-out`, `reflect` | `disable-model-invocation: true` | neither flag | All four are routing targets of poteto-mode's triggers. With the flag those triggers cannot fire |
| `setup-pstack` | no flag | `disable-model-invocation: true` | It writes a config file. A side effect you should time yourself |
| `arena`, `automate-me`, `show-me-your-work` | `disable-model-invocation: true` | unchanged | Side-effecting or timing-sensitive, kept user-only by request |

`arena` and `show-me-your-work` are *also* routing targets (`feature.md` step 4, poteto-mode's decision-trail
trigger, `figure-it-out` Phase D). Keeping them user-only means Claude cannot invoke them, so those call sites
now say to follow `${CLAUDE_PLUGIN_ROOT}/skills/<name>/SKILL.md` directly instead. The routing survives; it
just reads the file rather than invoking the skill.

## Behavior changes

### 1. Multi-vendor panels became multi-tier plus multi-lens. The biggest change.

`arena`, `interrogate`, `how` (critique mode), `architect` and `show-me-your-work` all relied on running the
same prompt against several vendors' models. poteto is explicit that this is the point: *"the adversarial
signal comes from model diversity, not assigned personas."*

Claude Code reaches only Claude models. There is no equivalent and no workaround. This port substitutes two
weaker things:

- **Different model tiers** (`opus`, `sonnet`, `haiku`) instead of different vendors.
- **An explicitly assigned lens or design direction per agent**, which is exactly the "assigned personas"
  poteto rejected as inferior.

Concretely, `interrogate` now runs a correctness lens on `opus`, a code-quality lens on `sonnet`, and an
edge-case lens on `haiku`. `arena` gives each runner a named design direction. `how`'s critics get
boundaries / state / failure-mode lenses.

**What this costs you.** Reviewers on one model family share blind spots that no assigned lens removes, so
cross-reviewer agreement is softer evidence than it was, and a finding nobody raised is not thereby absent.
Arena candidates will converge more often, which makes the convergence signal less meaningful. Every affected
skill says this at the top of its body, so the agent reading it knows too.

### 2. Claude may now invoke `poteto-mode` on its own

Dropping `disable-model-invocation` is the only way `poteto-agent` can preload the skill, which Phase 4
required. The description is narrow ("Use for poteto, /poteto-mode, or requests to work in this style"), so
drift should be rare. If it triggers when you do not want it, set `disable-model-invocation: true` back and
switch the agent to reading `${CLAUDE_PLUGIN_ROOT}/skills/poteto-mode/SKILL.md` instead of preloading it.

### 3. Model routing is a config file, not an always-applied rule

Cursor's `~/.cursor/rules/pstack-models.mdc` with `alwaysApply: true` was visible to every skill for free.
Claude Code has no always-applied rule. `/pstack:setup-pstack` now writes
`${CLAUDE_PLUGIN_DATA}/models.json`, and each consuming skill reads it with dynamic context injection:

```
!`cat ${CLAUDE_PLUGIN_DATA}/models.json 2>/dev/null || echo '{}'`
```

Three details that are requirements, not style:
- `${CLAUDE_PLUGIN_DATA}` is the plugin's persistent data directory, so a plugin update does not wipe the config.
- The `|| echo '{}'` is mandatory. A non-zero exit from an injected command **aborts the whole skill invocation**.
- Each consuming skill carries `allowed-tools: Bash(cat ${CLAUDE_PLUGIN_DATA}/*) Bash(echo *)`. Outside auto
  mode, an injected command whose permission check does not return allow aborts the invocation, and injected
  commands never prompt.

Trade-off versus Cursor: the config costs nothing when a skill is not running, but a skill that forgets the
injection block silently uses its defaults.

### 4. Transcript mining is best-effort

`automate-me`, `reflect`, `show-me-your-work` and two playbooks read the session transcript. Cursor named an
`agent-transcripts/` directory in the system prompt. Claude Code writes
`~/.claude/projects/<project>/<session>.jsonl` plus `<session>/subagents/*.jsonl`, documented in
`claude-directory`. The layout is documented; **the rule for encoding a project path into `<project>` is
not.** The skills derive it by replacing each non-alphanumeric run with a dash, fall back to picking the
newest matching directory, and say so. `automate-me` explicitly refuses to invent a working style when
resolution fails: it mines the current session, tells you the history pass found nothing, and leans on the
questions instead. `${CLAUDE_SESSION_ID}` names the current session reliably.

The privacy constraint carried over directly. poteto forbids globbing `~/.cursor/projects/*/` because it
reads unrelated private chats; these skills forbid globbing `~/.claude/projects/*/` for the same reason.

### 5. `why` discovers MCP servers from tool names

Cursor exposed an `mcps/` directory. Claude Code names MCP tools `mcp__<server>__<tool>`, and
`mcp__plugin_<plugin>_<server>__<tool>` for a plugin-bundled server. `why` now enumerates the distinct server
segments in its own tool list, falls back to `claude mcp list`, then to asking you. It assumes **no** server is
installed, treats an unauthenticated server as unavailable, and reports each category with no server as a
documented null. That is not a degraded mode; a coverage map with six nulls and a source-control answer is
what poteto already wanted from a thin record.

### 6. No `babysit`

Cursor's built-in PR-watching skill has no Claude Code equivalent, bundled or otherwise. The three call sites
now say to watch the PR with `gh pr checks <number> --watch` and `gh pr view <number> --comments`, triage each
comment on its merits, and drive the waiting with the bundled `/loop`. This is the most degraded substitution
in the port: it is a manual loop where Cursor had a skill. The skeptical-posture wording for automated
reviewers is preserved verbatim, retargeted from Bugbot to `/code-review` and `/security-review`.

## Cursor dependency map

| Cursor dependency | Where | Claude Code equivalent |
|---|---|---|
| `subagent_type: "poteto-agent"` | poteto-mode, plan.md, arena | `subagent_type: "pstack:poteto-agent"`. Plugin agents are namespaced `<plugin>:<name>` |
| `subagent_type: generalPurpose` | how, why, interrogate, reflect | `general-purpose`, or `Explore` for read-only lenses |
| `readonly: true` Task param | how, interrogate, arena | **NO EQUIVALENT as a parameter.** `subagent_type: Explore` is read-only by construction. Used everywhere the agent only reads the repo |
| `readonly: false` "agent mode, readonly strips MCP" | why, reflect | `general-purpose`. `Explore`'s reduced tool set is the thing to avoid, so the reasoning carries over with the names changed |
| `AskQuestion` | poteto-mode, plan.md, automate-me, setup-pstack | `AskUserQuestion`. Note its limits: at most 4 questions, 4 options each, and the flag is `multiSelect`, not `allow_multiple`. `automate-me`'s "4-6 options" was adjusted for this |
| `Task` tool | poteto-mode, reflect, opening-a-pr | `Agent` tool |
| `~/.cursor/rules/*.mdc`, `alwaysApply: true` | setup-pstack | **NO EQUIVALENT.** See behavior change 3 |
| Multi-vendor model slugs | 5 skills, 4 playbooks | **NO EQUIVALENT.** See behavior change 1 |
| `agent-transcripts/` | automate-me, reflect, show-me-your-work, eval, session-pickup | `~/.claude/projects/<project>/`. See behavior change 4 |
| `mcps/` directory | why | `mcp__*` tool names. See behavior change 5 |
| Cursor `/loop` | autonomous-run, bug-fix, visual-parity | **Bundled `/loop` skill.** Delegated, not ported |
| Cursor `/babysit` | poteto-mode, opening-a-pr, plan.md, investigation | **NO EQUIVALENT.** See behavior change 6 |
| Cursor `/create-skill` | authoring-a-skill, automate-me, reflect, poteto-mode, plan.md | `skill-creator`, which ships in the `skill-creator` plugin on `claude-plugins-official`, **not** in Claude Code. Every call site checks for it and degrades to authoring directly, saying so rather than dropping the step |
| `cursor-team-kit` `/deslop` | poteto-mode, opening-a-pr, plan.md | **Bundled `/simplify`** for code. The ported `unslop` keeps prose |
| `cursor-team-kit` `control-ui`, `control-cli` | poteto-mode, plan.md, visual-parity | **Bundled `/run` and `/verify`**, plus `/run-skill-generator` to record the launch recipe. The cleanest substitution in the port |
| Bugbot, agentic security review | poteto-mode, reflect/synthesizer | `/code-review`, `/security-review` |
| `/add-plugin pstack` | README | `/plugin marketplace add .`, `/plugin install pstack@pstack-local` |
| "restart Cursor" | pause-safely | "restart Claude Code" |
| `.cursor/skills/`, `~/.cursor/plugins/` | reflect reviewers, automate-me | `.claude/skills/`, `~/.claude/skills/`, `~/.claude/plugins/` |

## Manifest changes

pstack's `plugin.json` needed three corrections:

- `"skills": "./skills/"` and `"agents": "./agents/"` **dropped.** Both name the default locations Claude Code
  already scans. The `agents` key also accepts `.md` files only, not a directory, so the Cursor spelling would
  have failed validation.
- `"category"` and `"tags"` **moved to the marketplace entry.** They are entry fields, not `plugin.json`
  fields; as top-level manifest keys they would be stripped with a validator warning.
- `homepage` and `repository` repointed from `github.com/cursor/plugins` to `github.com/poteto/plugins`, which
  is where the source actually lives.

## Overlap with bundled skills

| pstack | Bundled | Decision |
|---|---|---|
| autonomous-run wake mechanism | `/loop` | **Delegate.** `/loop` takes an interval or self-paces. Reimplementing it would be worse and unowned |
| control-ui / control-cli | `/run`, `/verify` | **Delegate.** These are the unshipped dependency's real equivalent |
| `/deslop` | `/simplify` | **Delegate** for code. `unslop` keeps prose, which `/simplify` does not touch |
| `interrogate` | `/code-review` | **Port anyway.** `/code-review` gives ranked correctness findings and can post to a PR. `interrogate` gives independent lenses plus a lead verdict sorting every finding into act on / consider / noted / dismissed, and an agreement map. Different artifact. The body now names `/code-review` as the cheaper first pass |
| `arena` | `/batch` | **Port.** `/batch` splits work into N *different* units. `arena` runs N attempts at the *same* unit and grafts the winners. Not the same tool |
| bug-fix playbook | `/debug` | **Port.** Not an overlap. Bundled `/debug` "enables debug logging for the current session and troubleshoots issues by reading the session debug log", which is Claude Code's own log, not your bug |
| `tdd`, `unslop`, `how`, `why`, `reflect`, `figure-it-out`, `show-me-your-work`, `architect`, 20 principles | none | **Port.** No bundled equivalent |

## Justified grep survivors

`grep -ri` for `cursor`, `subagent_type`, `generalPurpose`, `/add-plugin`, `cursor-team-kit`,
`always-applied`. Zero hits for `generalPurpose`, `/add-plugin`, `cursor-team-kit`. The rest:

- **`cursor` (8 intentional).** Five are the behavior-change notes in `arena`, `interrogate`, `how`,
  `show-me-your-work` and `setup-pstack` that tell the reader what the Cursor original did and why this
  differs. One is `plugin.json`'s description naming the port. Two are false positives: "precursor" in
  `why`, and "cursor location" in `why`'s conversation-context list, which is poteto's wording about the text
  caret. That last one has no meaning in Claude Code but is harmless, and rewriting it would be an improvement
  rather than a port.
- **`subagent_type` (14).** Not a Cursor artifact. It is Claude Code's own parameter name on the `Agent` tool.
  Every value is now a valid Claude Code agent type: `pstack:poteto-agent`, `general-purpose`, or `Explore`.
- **`always-applied` (1).** `setup-pstack`'s explanation of what replaced the Cursor rule.

## Per-skill `user-invocable` reasoning

All 20 `principle-*` skills get `user-invocable: false`. They are single-rule reference documents that
poteto-mode's index points at, read when the agent applies that principle. `/pstack:principle-laziness-protocol`
is not a meaningful action for a person to take, and keeping 20 of them out of the `/` menu keeps the menu
readable. They stay model-invocable because poteto-mode requires Claude to read the leaf.

No other skill gets `user-invocable: false`. Every one of the other 14 is something you would type.

## Known limitations and unverified items

- **`skills: [pstack:poteto-agent]` preload spelling.** The docs show `skills:` with bare skill names and do
  not give a plugin-namespaced example. This port uses `pstack:poteto-mode`, matching how plugin skills are
  identified everywhere else. If the preload silently does not happen, a warning appears in the debug log
  (`claude --debug`) and the bare name `poteto-mode` is the alternative. **Verify this in the smoke test.**
- **Project-path encoding for transcripts.** Undocumented. See behavior change 4.
- **`claude plugin validate` was not run in the session that built this port.** The `claude` CLI is not
  installed on this machine and there is no node/npm. `scripts/check-refs.py` covers frontmatter fields,
  `${CLAUDE_*}` path resolution and cross-skill references, and passes with 0 errors, but it is not a
  substitute for the real validator on the manifest schema.
- **No skill was executed.** Nothing here has been run end to end.
