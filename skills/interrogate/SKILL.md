---
name: interrogate
description: "Use for \"interrogate\", \"adversarial review\", \"multi-model review\", \"challenge this\", \"stress test this code\", \"find blind spots\", or \"tear this apart\". Parallel reviewers on different models challenge changes from independent angles, then a lead verdict sorts every finding."
argument-hint: [diff, PR, or files to review]
allowed-tools: Bash(cat ${CLAUDE_PLUGIN_DATA}/*) Bash(echo *)
---

# Interrogate

## Model configuration

Your configured models, or `{}` when `/pstack:setup-pstack` has not run:

!`cat ${CLAUDE_PLUGIN_DATA}/models.json 2>/dev/null || echo '{}'`

Read `interrogate-reviewers` from that object. A key that is absent falls back to the default named at the step that uses it. Values are Claude Code model aliases or IDs, passed as the `model` parameter when you spawn the subagent.

Spawn parallel reviewers to adversarially review code changes. Each reviewer gets the same diff, intent, and rubric, and its own review lens.

**This differs from the Cursor original.** There, every reviewer ran the same prompt and the adversarial signal came from using several vendors' models, whose blind spots and priors genuinely differ. Claude Code can only reach Claude models, so that source of independence is gone. This port replaces it with two weaker substitutes: different model tiers, and an explicitly assigned lens per reviewer. Treat cross-reviewer agreement as a softer signal than it was. Reviewers on the same model family share blind spots that no assigned lens removes, so a finding none of them raised is not thereby absent.

Agreement across reviewers is the higher-confidence signal; lone-reviewer findings are worth reading but lower confidence.

For a cheaper single-pass review, the bundled `/code-review` skill produces ranked correctness findings and can post them to a PR. Use interrogate when you want independent lenses and a lead verdict that sorts every finding into act on / consider / noted / dismissed.

The deliverable is a synthesized verdict. Do NOT auto-apply changes.

## Step 1, Determine Scope

Identify what to review from context:

- If the user points at specific files or a diff, use that
- If on a feature branch, run `git diff main...HEAD` (or the appropriate base branch) for the full changeset
- If the user's message references recent work, gather the relevant files

Package the diff (or file contents) plus any surrounding context files the reviewers need to understand the code.

## Step 2, State the Intent

Before spawning reviewers, state the intent explicitly. What is this code trying to accomplish? Derive this from:

- The user's message
- Commit messages
- PR description if one exists
- The code itself

Write one clear paragraph. Reviewers challenge whether the work achieves the intent well, not whether the intent itself is correct. If you're unsure about the intent, ask the user before proceeding.

## Step 3, Spawn Reviewers

Launch one reviewer per entry in your configured `interrogate-reviewers` list (defaults `opus`, `sonnet`, `haiku`), all in a single message so they run concurrently.

Assign each reviewer one lens, pairing the heaviest lens with the strongest model. With the three defaults:

| Lens | Model | Hunts for |
|---|---|---|
| Correctness | first entry (default `opus`) | Logic errors, broken invariants, wrong edge-case handling, races, anything that makes the code do the wrong thing |
| Code quality | second entry (default `sonnet`) | The `references/code-quality-review.md` lens: structure, naming, layering, reader load, dead weight |
| Edge cases and failure modes | third entry (default `haiku`) | Empty and boundary inputs, concurrency, partial failure, retries, resource exhaustion, what happens when a dependency is down |

If the list has more entries than lenses, repeat the Correctness lens on the extra models. If it has fewer, drop from the bottom and say which lens went unrun in the Reviewers section of the output. A lens nobody ran is a gap the user should see, not a silent omission.

For each reviewer:
- `subagent_type`: `Explore` when the reviewer only needs to read the repository, which is the normal case. It is read-only by construction, which is what the Cursor original got from `readonly: true`. Use `general-purpose` when the reviewer needs an MCP server for context the diff references.
- `model`: its entry from the configured list.
- `run_in_background`: `true`.

If a configured model value is rejected as unresolvable, read the valid values from the error, pick the closest equivalent (prefer the highest-reasoning tier of the same family), spawn with that, and tell the user their `/pstack:setup-pstack` config names a model this account cannot use. Do not block the review on it.

Read `${CLAUDE_SKILL_DIR}/references/reviewer-prompt.md` and fill in the template with:
1. The stated intent
2. The diff or file contents
3. The review rubric from `${CLAUDE_SKILL_DIR}/references/rubric.md`
4. Its assigned lens from the table above, and for the code-quality reviewer the full lens in `${CLAUDE_SKILL_DIR}/references/code-quality-review.md`

Every reviewer gets the same intent, diff and rubric. Only the lens differs.

Each reviewer produces structured findings as described in the prompt template.

## Step 4, Synthesize

As results come back, build a unified picture:

1. **Parse all findings** from the reviewers
2. **Identify consensus**. Findings raised by 2+ models independently are highest signal.
3. **Identify lone-model findings**. Still worth reading, but weight accordingly.
4. **Deduplicate**. Different models may describe the same issue differently. Merge these and note which models raised it.
5. **Note disagreements**. If one model flags something and another explicitly says the opposite, that's useful context for the verdict.

## Step 5, Lead Judgment

You are the lead reviewer, a pragmatic senior engineer, not a neutral aggregator.

Read `${CLAUDE_SKILL_DIR}/references/lead-judgment.md` for the full framework. Reviewers only see a slice of the codebase. You have the full context (the goal, the constraints, the timeline, which tradeoffs were already considered). Use that context aggressively.

Categorize every finding using these buckets:

- **Act on**. Real issues affecting correctness, security, or maintainability given the actual goals. These would block a real PR.
- **Consider**. Legitimate points, but you're not sure they outweigh the cost of addressing them right now. Worth the user's attention.
- **Noted**. Technically valid but not actionable. Context-dependent, premature optimization, or low-impact given the current stage.
- **Dismissed**. Wrong, nitpicky, or missing context. Brief explanation why.

For each finding, include:
- Which model(s) raised it
- The category (act on / consider / noted / dismissed)
- A one-line rationale for the categorization

## Output Format

Present the verdict in this structure:

### Intent
> [The stated intent paragraph from Step 2]

### Reviewers
List each reviewer on its own line like `- <lens> (<model>): [N findings]`, and name any lens that did not run.

### Act On
[Findings that should be addressed. For each: description, which models raised it, why it matters.]

### Consider
[Findings worth thinking about. For each: description, which models raised it, tradeoff involved.]

### Noted
[Valid but low-priority. Brief list.]

### Dismissed
[Rejected findings with brief rationale. This shows the user what was filtered out and why, so they can override your judgment if they disagree.]

### Agreement Map
[Where did models agree, where did they diverge, and what does the pattern of agreement/disagreement tell us?]
