---
name: reflect
description: Spawn three parallel review subagents over the active transcript, surface learnings, and route each to a concrete edit on an existing skill. Use when the user says reflect.
argument-hint: [optional focus for the review]
allowed-tools: Bash(cat ${CLAUDE_PLUGIN_DATA}/*) Bash(echo *)
---

# Reflect

## Model configuration

Your configured models, or `{}` when `/pstack:setup-pstack` has not run:

!`cat ${CLAUDE_PLUGIN_DATA}/models.json 2>/dev/null || echo '{}'`

Read `reflect-tooling`, `reflect-judgment` from that object. A key that is absent falls back to the default named at the step that uses it. Values are Claude Code model aliases or IDs, passed as the `model` parameter when you spawn the subagent.

Mine the current conversation for durable learnings, then route them into skill edits.

## When to invoke

- The user said "reflect" or "/reflect".
- A complex task (5+ tool calls) just landed cleanly and the recipe is worth keeping.
- The agent hit dead ends, found the working path, and the path generalizes.
- The user corrected the agent's approach mid-task.
- A non-trivial workflow emerged that isn't captured anywhere.

Skip when the conversation is trivial, off-topic, or already covered by an existing skill the parent followed correctly. One-offs are not learnings.

## Process

### 1. Locate the active transcript

The parent finds its own transcript file before fanning out. Claude Code writes transcripts to `~/.claude/projects/<project>/`, where `<project>` encodes the project's absolute path. Resolve the directory for **this** project only:

```bash
# The project directory name is the absolute path with each non-alphanumeric run replaced by a dash.
d="$HOME/.claude/projects/$(printf '%s' "${CLAUDE_PROJECT_DIR}" | sed 's/[^A-Za-z0-9]/-/g')"
ls -t "$d"/*.jsonl "$d"/*/*.jsonl "$d"/*/subagents/*.jsonl 2>/dev/null | head -10
```

`claude-directory` documents the `projects/<project>/<session>.jsonl` layout and the `<session>/subagents/` directory, but not the exact path-encoding rule, so treat the `sed` above as a best effort. If it resolves nothing, fall back to `ls -td "$HOME"/.claude/projects/*/ | head` and pick the directory whose name ends with this project's path segments. Do not glob across `~/.claude/projects/*/` for content. That crosses project boundaries and reads private transcripts from unrelated work.

Your own session id is `${CLAUDE_SESSION_ID}`, which names this session's transcript directly.

Three transcript layouts: flat (`<id>.jsonl`), nested (`<id>/<id>.jsonl`), and subagent (`<parent>/subagents/<child>.jsonl`).

For each candidate, read the first JSONL line and check that `message.content[0].text` contains the conversation's opening user prompt. Take the matching path. If no path resolves, write a tight digest of the session and pass that instead.

### 2. Spawn three reviewers in parallel

One message, three `Agent` calls, `subagent_type: general-purpose`, explicit `model` on each. Reviewers need MCP access for context lookups (tickets, chat threads, observability traces referenced in the transcript), so they cannot be `Explore` agents, whose reduced tool set is aimed at reading the local repository. The prompt forbids file writes; the parent applies edits.

| Lens | `model` | Prompt template |
|---|---|---|
| Judgment | your configured `reflect-judgment` model (default `opus`) | `${CLAUDE_SKILL_DIR}/references/judgment-reviewer.md` |
| Tooling | your configured `reflect-tooling` model (default `sonnet`) | `${CLAUDE_SKILL_DIR}/references/tooling-reviewer.md` |
| Divergent | your configured `reflect-judgment` model (default `opus`) | `${CLAUDE_SKILL_DIR}/references/divergent-reviewer.md` |

Pass each template verbatim, substituting the transcript path or digest where marked. Reviewers return findings in the `Task` response body.

### 3. Synthesize

One `Agent` call, `subagent_type: general-purpose`, using your configured `reflect-judgment` model (default `opus`). The synthesizer's quality check includes spot-verifying citations, which can require MCP access, so it cannot be an `Explore` agent either. Use `${CLAUDE_SKILL_DIR}/references/synthesizer.md` verbatim, with each reviewer's full output inlined where marked. The synthesizer returns a structured Accepted / Rejected / Backlog list.

### 4. Structural enforcement check

Sanity-check the synthesizer's Accepted list. For any item that would be enforced more reliably by a lint rule, script, metadata flag, or runtime check, move it from Accepted to Backlog. The synthesizer already applies this criterion; this is a final pass before edits land. See the **encode-lessons-in-structure** principle skill.

### 5. Apply

Before applying any Accepted edit, present the synthesizer's full Accepted/Rejected/Backlog output to the user and wait for explicit approval. The user picks which subset to apply and may redirect routings. Skill changes affect every future agent in the org; do not auto-apply.

Backlog items file to whatever devex / backlog tracker your team uses automatically. Those are tracker submissions, not skill edits. Only the Accepted list waits for approval.

For each approved Accepted item, follow the Routing field exactly:

- Trivial existing-skill edit (a one-line bullet, a tightened sentence, a stale fact corrected): parent does directly.
- Substantive existing-skill edit (a new section, a new pattern table, more than ~10 lines): hand to the `skill-creator` skill and run its draft / test / iterate loop. It ships in the `skill-creator` plugin from `claude-plugins-official`, not in Claude Code. When it is not installed, make the edit directly and say the loop did not run.
- `tune description: <skill path>` (the skill exists but didn't trigger when it should have): hand to `skill-creator` and run its description-optimization loop.
- `new skill via skill-creator: <kebab-name>`: hand creation to `skill-creator`. Do not invent the shape ad hoc.

Run `claude plugin validate` on every touched skill directory before declaring done. It reports `SKILL.md` frontmatter that does not parse. Skip this step only when the `claude` CLI is not on `PATH`, and say so.

### 6. Summarize for the user

Short list, no preamble:

- Edits applied: `<skill path>`. What changed, one line each.
- New skills created: `<skill path>`. One line each (rare).
- Backlog filed to the devex tracker: `<issue title>` (`<tags>`). One line each.
- Dropped: one line per rejected finding + reason from the synthesizer.
