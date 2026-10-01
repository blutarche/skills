# Skill template

Copy this into a new folder named after the skill (kebab-case), e.g.
`my-new-skill/SKILL.md`. One skill = one folder = one `SKILL.md` (plus any
supporting files the skill references).

```markdown
---
name: my-new-skill
description: One or two sentences. Lead with WHAT it does, then "Use when ..." so the
  agent can match it to a request. This text is the only thing the model sees when
  deciding whether to load the skill — make the triggers concrete.
# license: MIT        # only if adapted from a licensed source — see CREDITS.md
# disable-model-invocation: true   # user-invoked only; see below
---

# My New Skill

Short paragraph: what this skill is for and when to reach for it.

## Steps / Guidelines

1. ...
2. ...

## Notes

- Keep it focused. A skill should do one thing well.
```

## Frontmatter notes

- **`description:`** is the trigger. Write it for matching, not marketing: say what it does
  and when to use it.
- **`disable-model-invocation: true`** makes a skill user-invoked only (the user types its
  `/command`; the agent never loads it on its own). Such a skill needs no "Use when ..."
  trigger wording — the description just says what the command does.
- Codex CLI ignores `disable-model-invocation`. To keep a skill from implicit invocation there,
  add `agents/openai.yaml` next to `SKILL.md` with `policy: {allow_implicit_invocation: false}`.
- **`license:`** — see [`AGENTS.md`](../AGENTS.md) for when to keep it.

## Rules

Naming, placement, the README row, credits, and the validation gate live in
[`AGENTS.md`](../AGENTS.md). For a guided authoring flow, use the `skill-creator` skill
(`/skill-creator`).
