# pstack for Claude Code

A Claude Code port of [pstack](https://github.com/poteto/plugins/tree/main/pstack), a set of agent skills for
rigorous engineering work by [poteto](https://x.com/poteto) (Lauren Tan). MIT licensed; the original
copyright and license are kept in [LICENSE](LICENSE).

poteto's pitch, unchanged: if you want to go fast, go deep first. pstack helps you write less, but higher
quality code. The goal is not to maximize lines. `/pstack:poteto-mode` at the start of a task reads your
request, picks a playbook, and routes to the other skills as the steps need them.

Read [PORTING_NOTES.md](PORTING_NOTES.md) for what changed and why. **Start with
["Differences from the Cursor version"](#differences-from-the-cursor-version) below** if you have used pstack
in Cursor, because one change is significant.

## Install

```bash
git clone <this-repo> pstack && cd pstack
```

Then, in Claude Code:

```
/plugin marketplace add ./
/plugin install pstack@pstack-local
/reload-plugins
```

Confirm it loaded with `/skills` (34 skills under `pstack`) and `@agent-pstack:poteto-agent`.

Validate the manifest before or after installing:

```bash
claude plugin validate .
claude plugin validate skills/
python3 scripts/check-refs.py
```

## Usage

Type `/pstack:poteto-mode` at the start of a task. It opens a todo list whose first item is reading the
principles index, matches your task to one of fifteen playbooks, copies that playbook's steps in verbatim, and
routes to the other skills as the steps fire.

```
/pstack:poteto-mode this pr has a subtle bug where the scroll drifts every 750ms even when idle.
                    repro first, then fix and verify.
/pstack:how         do we cancel runs? do we have an n+1 when we look up every run to cancel?
/pstack:why         is this feature flag not on yet?
/pstack:interrogate review this pr.
/pstack:arena       take my prompt to the arena verbatim. i want to compare their proposals with yours.
```

It pairs with the bundled `/loop` skill for long autonomous runs.

### Playbooks

`/pstack:poteto-mode` routes to one of these fifteen: investigation, bug fix, perf issue, runtime forensics,
trace forensics, feature, refactoring, prototype, visual parity, authoring a skill, eval, autonomous run,
session pickup, pause safely, multi-phase plan. Opening a PR runs at the end of every other playbook.

### Skills

| Skill | Use it when | Invocation |
|---|---|---|
| `/pstack:poteto-mode` | Default entry point for any non-trivial task | you or Claude |
| `/pstack:how` | You want a walkthrough of how a subsystem works | you or Claude |
| `/pstack:why` | You want to know why something was built this way. Discovers available MCP servers and queries each evidence category in parallel | you or Claude |
| `/pstack:architect` | You're about to write code that crosses a function boundary and want the usage, types, and module shape settled first | you or Claude |
| `/pstack:interrogate` | You have a diff and want parallel reviewers on different models to try to break it | you or Claude |
| `/pstack:figure-it-out` | No bundled playbook fits. Designs a rigorous, auditable playbook | you or Claude |
| `/pstack:reflect` | A long task landed and you want the recipe captured as a skill edit | you or Claude |
| `/pstack:tdd` | You're fixing a bug and there's a cheap local test path | you or Claude |
| `/pstack:unslop` | You're cleaning up writing. Removes AI tells | you or Claude |
| `/pstack:typescript-best-practices` | Auto-loads for `.ts`/`.tsx` files. Grounds type-system discipline in syntax | you or Claude |
| `/pstack:arena` | You want N parallel attempts at the same thing, then the best parts of each | you only |
| `/pstack:show-me-your-work` | You want a reviewable decision trail. Logs decisions to a committable TSV | you only |
| `/pstack:automate-me` | You want your own `-mode` skill, drafted from how you've actually worked | you only |
| `/pstack:setup-pstack` | You want to pick which models pstack uses per role | you only |

Plus 20 single-principle skills (`pstack:principle-*`). Claude reads the relevant one when it applies that
principle; they are hidden from your `/` menu because invoking a principle is not an action you take.

- core: laziness-protocol, foundational-thinking, redesign-from-first-principles, subtract-before-you-add,
  minimize-reader-load, outcome-oriented-execution, experience-first, exhaust-the-design-space, build-the-lever
- architecture: boundary-discipline, type-system-discipline, make-operations-idempotent,
  migrate-callers-then-delete-legacy-apis, separate-before-serializing-shared-state
- verification: prove-it-works, fix-root-causes, sequence-verifiable-units
- delegation: guard-the-context-window, never-block-on-the-human
- meta: encode-lessons-in-structure

### The `poteto-agent` subagent

`agents/poteto-agent.md` runs poteto's style end to end. Spawn it with
`subagent_type: "pstack:poteto-agent"`, or `@agent-pstack:poteto-agent`. It starts with `poteto-mode`
preloaded in full via the `skills` frontmatter field, including the principles index, so it does not have to
go find it. Substituting `general-purpose` skips that and drifts.

### Model routing

`/pstack:setup-pstack` detects the models you can use and writes `${CLAUDE_PLUGIN_DATA}/models.json`, one key
per role. Every consuming skill reads that file when it loads and falls back to its own default when a key is
absent, so you override only what you want. The defaults are `sonnet` for code, `opus` for judgment and prose,
and `opus, sonnet, haiku` for the review panels.

The config lives in the plugin's persistent data directory, so a plugin update does not wipe it. Delete a key
to go back to that skill's default; delete the file to reset everything.

That directory is scoped per install. A marketplace install uses
`~/.claude/plugins/data/pstack-pstack-local/`, while `--plugin-dir` loading uses
`~/.claude/plugins/data/pstack-inline/`, and the two do not share a config. Re-run `/pstack:setup-pstack` if
you switch between them.

## Differences from the Cursor version

### Multi-vendor review panels are gone. Read this one.

`arena`, `interrogate`, `how` (critique mode), `architect` and `show-me-your-work` all worked by running the
same prompt against several vendors' models. poteto is explicit that this is the mechanism: *"the adversarial
signal comes from model diversity, not assigned personas."*

Claude Code reaches only Claude models. There is no equivalent. This port substitutes different model tiers
(`opus`, `sonnet`, `haiku`) plus an explicitly assigned lens per reviewer, which is the assigned-personas
approach poteto rejected as weaker.

**What it costs you.** Reviewers on one model family share blind spots that no assigned lens removes. Treat
cross-reviewer agreement as softer evidence than it was in Cursor, and do not read "no reviewer raised it" as
"it isn't there". Arena candidates will converge more often, which makes convergence a weaker signal. Each
affected skill states this at the top of its body.

### Everything else

| Change | Detail |
|---|---|
| Claude can invoke `poteto-mode` itself | Required so `poteto-agent` can preload it. The description is narrow, so drift should be rare |
| Principles are model-invocable, not user-invocable | Inverted from pstack, because Claude has to be able to read a leaf skill when it applies the principle |
| Model config is a file, not an always-applied rule | Claude Code has no always-applied rule. See PORTING_NOTES |
| `/deslop` became `/simplify` | Bundled. Covers code; `unslop` still covers prose |
| `control-ui` and `control-cli` became `/run` and `/verify` | Bundled. `/run-skill-generator` records the launch recipe per project |
| Cursor's `/loop` became the bundled `/loop` | Same idea, and it can self-pace |
| No `babysit` | Claude Code has no equivalent. PR watching is now `gh pr checks --watch` plus `gh pr view --comments`, driven by `/loop`. The most degraded substitution in the port |
| `create-skill` became `skill-creator` | Ships in the `skill-creator` plugin on `claude-plugins-official`, not in Claude Code. Every call site degrades gracefully and says so |
| Transcript mining is best-effort | Claude Code's project-path encoding is undocumented. `automate-me` refuses to invent a working style when resolution fails |
| `why` finds MCP servers from tool names | `mcp__<server>__<tool>`. Assumes nothing is installed and reports empty categories as documented nulls |

### Not shipped, same as the original

pstack referenced a few things it did not bundle. In Claude Code:

- `/deslop`, `control-cli`, `control-ui` (Cursor's `cursor-team-kit`) are replaced by the bundled
  `/simplify`, `/run` and `/verify`. Nothing to install.
- `/loop` is bundled.
- `skill-creator` is an optional install: `/plugin install skill-creator@claude-plugins-official`.
- `babysit` has no equivalent.

## Why are there no planning skills?

poteto's answer, which still applies: Claude Code has a good plan mode that works fine with pstack, and the
best spec is code. If you do want a plan, `/pstack:poteto-mode` covers it through the multi-phase playbook,
but it is not a default.

## Credit

All skill content is poteto's. Fork it, improve it, make it yours.

- Original: https://github.com/poteto/plugins/tree/main/pstack
- Author: Lauren Tan, https://x.com/poteto

## License

MIT. See [LICENSE](LICENSE).
