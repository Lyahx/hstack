# Verification checklist

What was verified in the porting session, and what is yours to run. Anything marked UNVERIFIED has not been
executed, by anyone, at the time this file was written.

## Verified in the porting session

| Check | Result |
|---|---|
| Both manifests parse as JSON | pass |
| `plugin.json` uses only documented fields | pass. `skills`/`agents` keys dropped, `category`/`tags` moved to the marketplace entry |
| `poteto-agent` uses only fields plugin agents support | pass. `permissionMode`, `hooks`, `mcpServers`, `initialPrompt` would be silent no-ops and are absent |
| Agent's preload target exists and is not `disable-model-invocation: true` | pass. A user-only skill cannot be preloaded, and the checker asserts it |
| Every skill frontmatter key is a documented field | pass, 34 skills |
| No skill sets both invocation flags | pass |
| Every `${CLAUDE_SKILL_DIR}` / `${CLAUDE_PLUGIN_ROOT}` path resolves | pass |
| Every `/pstack:<name>` reference names a shipped skill | pass |
| Every relative markdown link resolves | pass |
| All 20 principles appear in poteto-mode's inline index | pass |
| Every `SKILL.md` under 500 lines | pass, longest is `why` at 243 |
| Every description under the 1,536-char listing cap | pass, longest is `why` at 428 |
| Injected config command exits 0 when the config is absent | pass. A non-zero exit would abort the skill invocation |
| `show-me-your-work/scripts/log.sh` runs and emits a well-formed TSV row | pass |
| `grep -ri` audit for cursor / subagent_type / generalPurpose / add-plugin / cursor-team-kit / always-applied | pass. Every survivor justified in PORTING_NOTES.md |

Reproduce all of the static checks:

```bash
python3 scripts/check-refs.py
```

## Verified by running it

The `claude` CLI was installed mid-session (v2.1.274), so the following were executed for real, not inferred.

| Check | Result |
|---|---|
| `claude plugin validate .` / `skills/` / `agents/`, plain and `--strict` | **Validation passed**, exit 0, all six runs |
| `plugin.json` validated as a plugin manifest, with `marketplace.json` moved aside | **Validation passed** |
| `claude plugin marketplace add ./ --scope project` | Success. Note **bare `.` is rejected**; the source must be `./` or an absolute path |
| `claude plugin install pstack@pstack-local` | Success |
| `claude plugin details pstack` inventory | **Skills (34), Agents (1)**, hooks 0, MCP 0. Matches what the port ships |
| Agent preload via `skills: [pstack:poteto-mode]` | **WORKS.** The subagent stated poteto-mode's long-dash rule and its Subagents default with **zero tool calls** in its transcript. The plugin-namespaced spelling resolves |
| A `user-invocable: false` principle is model-invocable | **WORKS.** Transcript shows `Skill pstack:principle-laziness-protocol`, and the reply quoted the leaf's actual prime directive |
| `subagent_type: "pstack:poteto-agent"` dispatches | **WORKS.** Transcript shows the `Agent` call resolving |
| Transcript path-mangling rule (undocumented) | **CONFIRMED** on v2.1.274. Predicted `~/.claude/projects/` + path with each non-alphanumeric run replaced by `-`, and the directory existed |
| `${CLAUDE_SKILL_DIR}` resolves at runtime | **WORKS.** Transcript shows a read of `skills/poteto-mode/playbooks/investigation.md` |

### Second round: the remaining mechanisms, all run

| Check | Result |
|---|---|
| `/pstack:setup-pstack` writes the config | **WORKS.** Wrote `~/.claude/plugins/data/pstack-pstack-local/models.json`: valid JSON, all 13 role keys present, no unexpected keys, every value a real model alias |
| A consuming skill *reads* that config via dynamic injection | **WORKS.** Planted `how-explorer: haiku` (the skill's written default is `sonnet`); `/pstack:how` quoted the raw injected JSON and answered "I'd use `haiku`, it came from the injected Model configuration block, overriding the skill's written default of `sonnet`". The override layer works end to end |
| `allowed-tools` grant for the injected command | **WORKS.** No permission prompt, no aborted invocation |
| `/pstack:interrogate` multi-model fan-out | **WORKS.** Spawned three reviewers on three models with the three assigned lenses (Correctness/opus, Code quality/sonnet, Edge cases/haiku), caught both planted bugs in a test diff, produced the four-bucket lead verdict and the Agreement Map, and did not auto-apply changes |
| Lens differentiation is real, and its limits | **Honest.** The verdict reported the opus reviewer as deepest and the haiku reviewer as "less elaboration, as expected from a lighter model", and noted no reviewer contradicted another. That is the tier-asymmetry caveat this port documents, observed in practice |
| `/pstack:why` graceful degradation with no MCP servers | **WORKS.** Correctly read six of seven categories as unavailable *because the servers are unauthenticated*, produced a full Sources Consulted coverage map naming each skipped category with its reason, answered from git, and reported the honest null ("treat it as an unexplained default") instead of inventing a rationale |

Observation, not a defect: `why` answered inline rather than spawning the investigator fan-out, justifying it
explicitly (two-commit repo, no remote, six categories unavailable). The skill permits that but calls it rare.
On a real repository with history, expect the fan-out.

### Smoke test, round one: trivial task, partial

`/pstack:poteto-mode investigate how ratelimit.py works` against a 22-line file, read-only.

Worked: matched the **Investigation** playbook and read it via `${CLAUDE_SKILL_DIR}`, routed to
`Skill pstack:how` and produced that skill's exact output shape, emitted the playbook's `throughput
checkpoint:` line, wrote no files, and named a principle with the decision it changed.

Did not: no principle *leaf* was invoked (it cited Guard the Context Window without reading it), and no todo
list. Round two explains both.

### Smoke test, round two: real multi-step work, clean pass

`/pstack:poteto-mode` on a genuine two-bug defect in `session.py` (a `TypeError` on unknown tokens, and
expired-session resurrection), with Bash/Edit/Write granted.

Everything the playbook demands, verified independently rather than taken from its summary:

| Required behavior | Observed |
|---|---|
| Match and follow the Bug fix playbook | Read `playbooks/bug-fix.md`, four times across the run |
| Invoke a principle leaf | **`Skill pstack:principle-fix-root-causes`** in the transcript. The round-one gap was a trivial-task artifact |
| Reproduce before fixing, with runtime evidence | Commit `f3d278d` adds a failing test; the real `TypeError` and `AssertionError` are quoted in the reply |
| Fix the root cause, not the symptom | Extracted the expiry check into `_expired()` and reused it, so `lookup` and `refresh` cannot drift again |
| Sequence into verifiable units | Two commits: failing test, then fix. It stashed the fix to confirm the test really failed first |
| Name each principle and the decision it changed | Fix Root Causes, Sequence Verifiable Units, Laziness Protocol, each tied to a specific choice |
| A skipped playbook step states why | "Opening a PR: skipped. This repo has no configured remote" |
| Frame impact for consumer and maintainer | Closing paragraph does exactly that, for callers of `refresh()` |

**I verified its claims myself** instead of trusting the report: the 3 tests pass on the fixed code, and on
the pre-fix code they fail with 1 failure and 1 error. The regression test is genuine, not tautological.

An earlier run of the same task with permissions *denied* is worth recording too. Rather than claim success,
it wrote a "Where I fell short of the playbook" section, said "That's a real gap against
principle-prove-it-works, and I'm not going to claim I saw it execute when I didn't", and offered the repro
for the user to run. The honesty discipline holds under pressure.

### Two real adherence gaps

1. **The long-dash ban does not hold.** poteto-mode says "the long-dash character is banned outright".
   Every reply in every run used it anyway, 5 times in the bug-fix reply alone. The rule is ported verbatim;
   the model does not follow it. If this matters to you, a `Stop` hook that rejects the character is the
   deterministic fix, since the docs recommend hooks where prose rules need enforcing.
2. **The todo-list requirement is still untested, and my testing could not test it.** `TodoWrite` does not
   exist in `-p` non-interactive mode, which is how every run above was driven. I confirmed this directly:
   asked in `-p`, Claude replies `NO TODO TOOL AVAILABLE`. So "no todo list" in rounds one and two is a
   harness artifact, not a skill or port defect, and it cannot be verified except **interactively**.
   **This is the one behavior you have to check by hand:** run `/pstack:poteto-mode` on a multi-step task in
   a normal interactive session and confirm a todo list opens whose first item is reading the principles
   index.

## Yours to run

### 1. Validate the manifest

```bash
claude plugin validate .
claude plugin validate skills/
claude plugin validate agents/
```

Expect `Validation passed`. `--strict` turns warnings into failures.

### 2. Install

```
/plugin marketplace add ./
/plugin install pstack@pstack-local
/reload-plugins
```

Then `/skills`. Expect 34 skills under `pstack`: 14 named commands and 20 `principle-*`. The four user-only
skills (`arena`, `automate-me`, `setup-pstack`, `show-me-your-work`) appear in the `/` menu; the 20 principles
do not, because they are `user-invocable: false`.

Confirm the agent with `@agent-pstack:poteto-agent` in the typeahead.

### 3. Smoke test, read-only

In a scratch directory with one small file:

```
/pstack:poteto-mode investigate how <that file> works
```

Correct behavior, in order:
1. A todo list opens, and its **first item is reading the principles index**.
2. It matches the task to the **Investigation** playbook and copies that playbook's steps in verbatim.
3. It routes to `/pstack:how` if the subsystem warrants a walkthrough.
4. The reply names each principle that shaped a decision and the specific choice it changed.
5. It does not open a PR, and does not write files.

### 4. Confirm the agent's preload actually happened

This is the one item in the port that the docs do not show an example for. The `skills:` field is documented
with bare skill names; this port uses the plugin-namespaced `pstack:poteto-mode`.

```bash
claude --debug
```

Then spawn the agent and check the debug log for a warning that a listed skill was missing or disabled. No
warning means the preload resolved. If there is one, change `agents/poteto-agent.md` to `- poteto-mode` and
retest.

### 5. Context cost

```
/skill-doctor
```

**Measured with `claude plugin details pstack`: ~2,943 tokens always-on**, added to every session. Run it
yourself for the per-component table:

```bash
claude plugin details pstack
```

My static estimate during the port was ~1,752 tokens, so the real cost is about 68% higher. The difference is
per-entry overhead plus the four user-only skills, which still cost ~80-120 tokens each for their names even
though `disable-model-invocation: true` keeps their descriptions out of the listing. "Zero listing cost" was
wrong; it is zero *description* cost.

The 20 principles are roughly **1,600 tokens, about 54%** of the always-on total. The most expensive
on-invoke components are `why` (~7.9k), `poteto-mode` (~5.5k) and `automate-me` (~3k), but on-invoke cost is
paid only when the skill actually fires.

If the always-on cost is too much, cut in this order:

1. **The 20 principles**, the largest share. poteto-mode's inline index already summarizes each one, so
   Claude can still route by reading `${CLAUDE_PLUGIN_ROOT}/skills/<name>/SKILL.md` directly. Setting
   `disable-model-invocation: true` on them drops their descriptions from the listing, though not their
   names. Cost: the verified leaf-invocation behavior below stops working.
2. **`why`**, the single largest description at ~150 tokens always-on.

`skillOverrides` does not apply to plugin skills, so `name-only` is not available here. Edit the frontmatter,
or raise the budget with `skillListingBudgetFraction`.
