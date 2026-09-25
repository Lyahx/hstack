---
name: setup-pstack
description: Configure which models pstack uses per role. Detects your available models and writes a config file that overrides the skill defaults. Use for /setup-pstack, "configure pstack models", or changing pstack's model choices.
disable-model-invocation: true
allowed-tools: Bash(cat ${CLAUDE_PLUGIN_DATA}/*) Bash(mkdir -p ${CLAUDE_PLUGIN_DATA}) Bash(test *)
---

# Setup pstack

Write `${CLAUDE_PLUGIN_DATA}/models.json`, the config that sets pstack's model per role. The skills read it and fall back to their inline defaults when a key is absent, so this is an override layer, not a requirement.

`${CLAUDE_PLUGIN_DATA}` is the plugin's persistent data directory. It survives plugin updates, so a re-install does not wipe your choices.

## Steps

### 1. Detect available models

Claude Code resolves a `model` field to an alias (`opus`, `sonnet`, `haiku`, `fable`), a full model ID (`claude-opus-5`, `claude-sonnet-5`), or `inherit`. Those are the values that may be written here.

Confirm what this account can actually use before writing anything. Run `claude --help` for the `--model` flag's accepted values, and check whether the organization restricts models with an `availableModels` allowlist. A blocked value makes Claude Code silently substitute another model, so a config full of unusable names looks like it works and quietly does something else.

Prefer aliases over full IDs. An alias keeps working when a new model version ships; a pinned ID goes stale.

If you cannot detect the set, ask the user which models they have. Never write a value you have not confirmed.

### 2. Load current state

The default role-to-model mapping is the shape in step 5. Read `${CLAUDE_PLUGIN_DATA}/models.json` if it exists and treat its values as the current choices. Otherwise start from the defaults.

### 3. Map and confirm

Show every role with its current model, marking any whose model is not in the detected set as needing a choice. Ask whether to accept as-is or change specific roles, offering the detected models as the options. Prefer `AskUserQuestion` over free text. For panel roles (how critics, arena runners, architect runners, interrogate reviewers) the value is a list, and one subagent runs per entry, so the list length sets the count.

### 4. Validate

Every value written must be in the detected set. If a chosen value is not available, stop and ask again. A config pointing at a model the user cannot use breaks every delegation that reads it.

### 5. Write the config

Write `${CLAUDE_PLUGIN_DATA}/models.json`. Create the directory first with `mkdir -p`. Overwrite the whole file so re-runs stay idempotent. Keep the keys exactly as below; the consuming skills look them up by these names. Delete a key to fall back to that skill's default.

```json
{
  "feature-refactoring": "sonnet",
  "bug-fix-perf": "opus",
  "judgment-and-prose": "opus",
  "how-explorer": "sonnet",
  "how-explainer": "opus",
  "how-critics": ["opus", "sonnet", "haiku"],
  "why-investigators": "sonnet",
  "why-synthesizer": "opus",
  "reflect-tooling": "sonnet",
  "reflect-judgment": "opus",
  "arena-runners": ["opus", "sonnet", "haiku"],
  "architect-runners": ["opus", "sonnet", "haiku"],
  "interrogate-reviewers": ["opus", "sonnet", "haiku"]
}
```

Write valid JSON. The consuming skills inline this file's contents verbatim, so a syntax error reaches them as a broken blob rather than a parse failure they can report.

### 6. Confirm

Tell the user the config was written and where. It applies to the next skill invocation in any session, because each consuming skill reads the file when it loads. Re-running this skill updates it.

## Why this is a config file and not a rule

The Cursor original wrote an always-applied rule (`~/.cursor/rules/pstack-models.mdc` with `alwaysApply: true`), which every skill saw for free. Claude Code has no always-applied rule mechanism. The closest equivalent that stays scoped to pstack is this file plus per-skill dynamic context injection, so each skill pays for the config only when it runs instead of every session paying for it always.
