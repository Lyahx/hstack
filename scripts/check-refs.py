#!/usr/bin/env python3
"""Validate the pstack plugin's internal consistency.

Checks, each of which has caught a real bug in this port:
  1. Every SKILL.md and agent file has parseable frontmatter whose keys are
     fields Claude Code documents.
  2. Every ${CLAUDE_SKILL_DIR} and ${CLAUDE_PLUGIN_ROOT} path resolves to a
     file that exists.
  3. Every cross-skill reference names a skill this plugin ships.
  4. No skill both routes to a target and makes that target unreachable.

Exits non-zero on any failure so CI can gate on it.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKILL_FIELDS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools",
    "disallowed-tools", "model", "effort", "context", "agent", "background",
    "hooks", "paths", "shell", "metadata", "license", "compatibility",
}
AGENT_FIELDS = {
    "name", "description", "tools", "disallowedTools", "model",
    "permissionMode", "maxTurns", "skills", "mcpServers", "hooks", "memory",
    "background", "omitClaudeMd", "effort", "isolation", "color",
    "initialPrompt", "experimental",
}
# Ignored for plugin agents; using one is a silent no-op, so flag it.
AGENT_IGNORED = {"permissionMode", "hooks", "mcpServers", "initialPrompt"}

errors, warnings = [], []


def frontmatter(path):
    s = open(path).read()
    if not s.startswith("---\n"):
        return None, s
    try:
        end = s.index("\n---\n", 4)
    except ValueError:
        return None, s
    return s[4:end + 1], s[end + 5:]


def top_keys(fm):
    return [
        m.group(1)
        for line in fm.split("\n")
        if (m := re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):", line))
    ]


skill_dirs = sorted(
    os.path.basename(os.path.dirname(p))
    for p in glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md"))
)
skill_names = set(skill_dirs)
# poteto-mode's index writes a principle as either `principle-x` or bare `x`.
bare_principles = {n[len("principle-"):] for n in skill_names if n.startswith("principle-")}

# --- 1. frontmatter -------------------------------------------------------
for p in glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")):
    rel = os.path.relpath(p, ROOT)
    fm, _ = frontmatter(p)
    if fm is None:
        errors.append(f"{rel}: no parseable frontmatter block")
        continue
    for k in top_keys(fm):
        if k not in SKILL_FIELDS:
            errors.append(f"{rel}: unknown skill frontmatter field {k!r}")
    if "description:" not in fm:
        warnings.append(f"{rel}: no description, Claude cannot match it")
    if "disable-model-invocation: true" in fm and "user-invocable: false" in fm:
        errors.append(f"{rel}: both invocation flags set, nothing can invoke it")

for p in glob.glob(os.path.join(ROOT, "agents", "*.md")):
    rel = os.path.relpath(p, ROOT)
    fm, _ = frontmatter(p)
    if fm is None:
        errors.append(f"{rel}: no parseable frontmatter block")
        continue
    for k in top_keys(fm):
        if k not in AGENT_FIELDS:
            errors.append(f"{rel}: unknown agent frontmatter field {k!r}")
        elif k in AGENT_IGNORED:
            errors.append(f"{rel}: {k!r} is ignored for plugin agents, silent no-op")
    if "name:" not in fm or "description:" not in fm:
        errors.append(f"{rel}: agent needs both name and description")
    # A preloaded skill must exist and must not be user-only.
    for m in re.finditer(r"^\s*-\s*(?:pstack:)?([a-z0-9-]+)\s*$", fm, re.M):
        dep = m.group(1)
        if dep not in skill_names:
            errors.append(f"{rel}: preloads skill {dep!r} which this plugin does not ship")
            continue
        dfm, _ = frontmatter(os.path.join(ROOT, "skills", dep, "SKILL.md"))
        if dfm and "disable-model-invocation: true" in dfm:
            errors.append(
                f"{rel}: preloads {dep!r}, but that skill sets "
                "disable-model-invocation: true and cannot be preloaded"
            )

# --- 2. ${CLAUDE_*} paths -------------------------------------------------
VAR = re.compile(r"\$\{CLAUDE_(SKILL_DIR|PLUGIN_ROOT)\}/([A-Za-z0-9_./<>-]+)")
for p in glob.glob(os.path.join(ROOT, "skills", "**", "*.md"), recursive=True) + \
         glob.glob(os.path.join(ROOT, "agents", "*.md")):
    rel = os.path.relpath(p, ROOT)
    skill_dir = os.path.dirname(p)
    for var, ref in VAR.findall(open(p).read()):
        ref = ref.rstrip(".,);")
        if "<" in ref or "*" in ref:
            continue  # placeholder, not a literal path
        base = skill_dir if var == "SKILL_DIR" else ROOT
        if not os.path.exists(os.path.join(base, ref)):
            errors.append(f"{rel}: ${{CLAUDE_{var}}}/{ref} does not exist")

# --- 3. cross-skill references -------------------------------------------
# `/pstack:<name>` must name a skill we ship.
for p in glob.glob(os.path.join(ROOT, "skills", "**", "*.md"), recursive=True) + \
         glob.glob(os.path.join(ROOT, "agents", "*.md")) + \
         [os.path.join(ROOT, "README.md")]:
    if not os.path.exists(p):
        continue
    rel = os.path.relpath(p, ROOT)
    for ref in set(re.findall(r"/pstack:([a-z0-9-]+)", open(p).read())):
        if ref not in skill_names:
            errors.append(f"{rel}: references /pstack:{ref}, no such skill")

# --- 4. relative links inside skill dirs ---------------------------------
for p in glob.glob(os.path.join(ROOT, "skills", "**", "*.md"), recursive=True):
    rel = os.path.relpath(p, ROOT)
    for link in re.findall(r"\[[^\]]*\]\((\.\.?/[^)]+)\)", open(p).read()):
        target = link.split("#")[0]
        if not target:
            continue
        if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(p), target))):
            errors.append(f"{rel}: broken relative link {link}")

# --- 5. poteto-mode must index every principle ---------------------------
pm = os.path.join(ROOT, "skills", "poteto-mode", "SKILL.md")
if os.path.exists(pm):
    body = open(pm).read()
    for n in sorted(skill_names):
        if n.startswith("principle-") and n not in body:
            errors.append(f"skills/poteto-mode/SKILL.md: principle {n!r} is not in the inline index")

print(f"skills: {len(skill_dirs)}  agents: {len(glob.glob(os.path.join(ROOT,'agents','*.md')))}")
for w in warnings:
    print(f"WARN  {w}")
for e in errors:
    print(f"ERROR {e}")
print(f"\n{len(errors)} errors, {len(warnings)} warnings")
sys.exit(1 if errors else 0)
