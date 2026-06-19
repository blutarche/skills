# Working in this repo

A curated, cross-agent **agent-skills** collection. Each skill is a folder with a `SKILL.md`
(an open standard read by Claude Code, Codex CLI, and Cursor). [`README.md`](README.md) is the
human map of the layout and the install model — read it once; this file is the rules an agent
needs that the README doesn't make obvious.

## Hard invariants — break these and `install.sh` aborts

1. **`name:` frontmatter == leaf folder name == kebab-case.** One skill = one folder = one
   `SKILL.md`. The leaf folder name becomes the skill's `/command`.
2. **Leaf folder names are unique across the whole repo** — even across domains and nesting
   depth. The installer maps every leaf into one flat dir, so a collision is fatal.

Run `./scripts/validate-skills.sh` before you call work done — it checks both, plus that each
skill is listed in its area README. This is the gate; don't declare "done" until it passes.

## Where a new skill goes

- Atomic skill → `<domain>/<group>/<name>/` (e.g. `software-development/review/<name>/`).
- Playbook that composes atomic skills → `workflows/<name>/`.
- Domain-agnostic → `meta/<name>/`.

Only the top-level domains listed in [`install.conf`](install.conf) install (default-deny). A new
domain doesn't ship until it's added there. Grouping below the domain is for humans only.

Fastest path: run `/add-skill` (scaffolds placement + frontmatter + README row + validation).
Use the global `/skill-creator` for the authoring craft itself (drafting, evals, description tuning).

## Conventions

- **`description:` is the trigger, not marketing.** Lead with WHAT it does, then `Use when …`
  with concrete cues. It's the only text the model sees when deciding to load the skill.
- **Prefer durable playbooks over version-pinned API references** — they rot. Skills may lean on
  Claude Code features if they degrade gracefully on other agents.
- **Borrowed from elsewhere?** Add a row to [`CREDITS.md`](CREDITS.md); if the source license
  requires it (MIT/BSD/Apache), keep a `license:` line in the skill's frontmatter.
- **Adding/removing/renaming a skill → update that area's `README.md` table** in the same change.
  Keep the README thin so it doesn't rot.
- **Don't edit the installed copies** in `~/.claude/skills` or `~/.agents/skills` — they're
  symlinks back here (unless installed with `--copy`). Edit in this repo; every agent sees it.

## Commits

Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, …).
