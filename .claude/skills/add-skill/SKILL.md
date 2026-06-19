---
name: add-skill
description: Scaffold a new skill in THIS repo — correct folder, valid frontmatter, README row, credits, and validation. (For the authoring craft, use the global skill-creator.)
disable-model-invocation: true
---

# Add a skill to this repo

Place a new skill so it satisfies the repo's invariants and installs cleanly. This handles
*placement and bookkeeping*.

## Steps

1. **Choose the location** (grouping below the domain is for humans; only the leaf matters):
   - Atomic skill → `<domain>/<group>/<name>/` (e.g. `software-development/review/<name>/`).
   - Playbook composing atomic skills → `workflows/<name>/`.
   - Domain-agnostic → `meta/<name>/`.
   - A brand-new top-level domain must be added to [`install.conf`](../../../install.conf) or it
     won't install (default-deny).

2. **Pick a kebab-case leaf name unique across the *entire* repo** (all domains, all depths) —
   the installer flattens leaves into one dir. The step-6 validator enforces this.

3. **Create `<location>/<name>/SKILL.md`** from [`docs/skill-template.md`](../../../docs/skill-template.md):
   - `name:` must equal the folder name exactly.
   - `description:` is the trigger — lead with WHAT it does, then `Use when …` with concrete
     cues.

4. **If adapted from another source:** add a row to [`CREDITS.md`](../../../CREDITS.md), and if the
   license requires attribution (MIT/BSD/Apache) keep a `license:` line in the frontmatter.

5. **Add a one-line row to the area's `README.md` table** (`software-development/`, `workflows/`,
   or `meta/`). Keep it thin.

6. **Validate, then preview the install:**
   ```bash
   ./scripts/validate-skills.sh        # must pass (0 errors)
   ./install.sh --dry-run              # confirm the new leaf links with no collision
   ```
