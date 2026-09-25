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
/plugin marketplace add .
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

Measured statically in the porting session: **7,010 characters, roughly 1,752 tokens**, from the 30 skills
whose descriptions enter the listing. The four user-only skills cost nothing there.

The 20 principles are **65% of that** (4,581 chars) for 20 entries Claude reads rather than you. If
`/skill-doctor` or `/doctor` reports the listing as heavy, collapse those to name-only rather than trimming
descriptions, which would strip the keywords Claude matches on. Plugin skills are not affected by
`skillOverrides`, so raise the budget instead:

```json
{ "skillListingBudgetFraction": 0.02 }
```

If you would rather cut, the honest order is: the 20 principles first (largest share, and poteto-mode's inline
index already summarizes each one, so Claude can still route by reading the leaf file directly), then `why`
(428 chars, the single largest description).
