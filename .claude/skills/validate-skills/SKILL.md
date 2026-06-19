---
name: validate-skills
description: Check this repo's skill invariants and fix any violations — name==folder==kebab-case, leaf names unique repo-wide, and every skill listed in its area README. Use before committing skill changes or before running install.sh, or when install.sh aborts on a duplicate/name error.
---

# Validate this repo's skills

The fast gate that proves skill changes are sound before `install.sh` would catch them.

## Steps

1. Run the validator:
   ```bash
   ./scripts/validate-skills.sh
   ```
2. **Errors (exit non-zero) must be fixed** — they will break `install.sh`:
   - `name != folder` → make the `name:` frontmatter match the leaf folder name exactly.
   - `not kebab-case` → rename to lowercase words joined by single hyphens.
   - `duplicate leaf name` → rename one; leaf names are unique across the whole repo.
   - `no 'name:'` → add the frontmatter `name:` line.
3. **Warnings** flag a skill with no entry in its area `README.md` — add the one-line row
   (unless the skill was just removed, in which case delete its stale row).
4. Re-run until it reports `0 error(s)`. Treat that as the done-condition for skill changes.

## Notes

- The check mirrors `install.sh`'s discovery (same domains, same pruned dirs), so passing here
  means `./install.sh --dry-run` will link cleanly.
