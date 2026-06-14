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
---

# My New Skill

Short paragraph: what this skill is for and when to reach for it.

## Steps / Guidelines

1. ...
2. ...

## Notes

- Keep it focused. A skill should do one thing well.
```

## Conventions in this repo

- **Folder name == `name:` frontmatter == kebab-case.**
- **`description:`** is the trigger. Write it for matching, not marketing: say what it does
  and when to use it.
- **Borrowed something?** Add a row to [`CREDITS.md`](../CREDITS.md). If the source license
  requires it (MIT/BSD/Apache), keep a `license:` line in the skill's frontmatter.
- For a guided authoring flow, use the `skill-creator` skill (`/skill-creator`).
