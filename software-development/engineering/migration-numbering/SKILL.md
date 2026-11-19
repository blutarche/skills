---
name: migration-numbering
description: Detect and fix clashing sequentially numbered database migrations when parallel branches land, then reset throwaway databases safely. Use when adding a numbered migration on a branch, merging or rebasing branches that both add migrations, or when migrate reports "no change", "dirty", or a duplicate version.
---

# Migration Numbering

Sequential migrators that keep one current version per database (golang-migrate and its kin) apply only versions above that number. A merged migration numbered at or below a database's version is **skipped silently**: no error, the table is just missing. Two branches that both add `0042` is the loud case. The recurring one is the quiet case: a branch's `0042` lands after the base already reached `0045`.

This skill covers sequential, single-version tools. A tool that tracks migrations as a dependency graph has its own merge procedure; use that.

**The unapplied side moves.** Never renumber a migration already applied to a shared, staging, or production database. That database records the old number, so the renamed file runs twice or never. If both sides are applied somewhere shared, stop and ask the owner.

## Steps

1. **Check before every merge.** Fetch the base. Then, inside the project repo, run this skill's `scripts/migcheck.sh <base> <tip> <migrations-dir>`. It prints `LOW` (new on tip, at or below the base's highest, so skipped), `DUP` (two migrations, one number), and the next free number. Exit 1 means renumber. Run it again right before push and after every merge into the base. A branch that was clean goes `LOW` the moment another branch lands above it. Two unmerged branches that both add `0042` each pass against the old base, so pass the branch that merges first as `<base>`. Exit 2 means it found no migrations: wrong directory or wrong repo. Done when it exits 0 against the freshly fetched base.

2. **Decide who moves.**
   - Whoever merges second renumbers, and only after the first has merged. Renumbering against an unmerged branch leaves a gap, or a new clash if the order changes. With several colliding branches, fix the merge order and have each one renumber when its predecessor lands.
   - Number blocks reserved per branch are reservations only. A branch whose block the base has passed moves above the base's max.
   - A migration that must stay last (a final bootstrap step) moves above the newcomer. A number cited elsewhere (ADRs, docs, other repos) keeps its number; move the other one.

3. **Renumber.**
   - Take the next free numbers above the base's max and keep the zero-padding width. `git mv` the up and down files and commit the renames on their own.
   - For several files, or a history rewrite, compute every rename from the original snapshot and apply them at once. Chained renames are not idempotent (`051→040`, then `040→038`, collides).
   - `git grep` the old numbers (tests, seeds, docs, schema-version asserts) and update them.
   - Reread migrations whose order changed relative to each other. If two redefine the same function, view, or trigger, the higher number wins; merge the bodies so the last one keeps every change.
   - Keep the migrations directory to real migrations. Any `NNN_name.up.*` file parses as a version, so variant or backup copies there are duplicates (`migcheck` reports them).
   - Done when `migcheck` exits 0 and the grep finds only intended references.

4. **Reset throwaway databases.** A local, test, or demo database that already ran a higher number will skip the renumbered migration. Drop it, recreate it, and migrate from zero; do not migrate it incrementally.
   - Prove the target is local from everything each tool reads, not just the hostname. Some drivers honour `?host=`/`?hostaddr=` query parameters or `PGHOST` that another driver ignores. A URL with no host (`postgres:///dbname`) makes every driver use `PGHOST`; then check that `PGHOST` is local.
   - Migrate through the project's own entrypoint (Makefile, script). It carries flags such as the migrations-table name; a bare URL can track progress in a different table, retry migration 1, and go `dirty`.
   - On `dirty`: drop and recreate a throwaway database. Never `force` a version on a shared one without its owner.

5. **Verify.** On a fresh database, migrate up to head, down to zero, and up again, then run the DB-backed tests. Keep the renumber commit unpushed until this passes. A shared database may meet a renamed migration under its new number. Then confirm the file is idempotent, and tell the owner which versions it will apply.
