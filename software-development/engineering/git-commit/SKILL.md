---
name: git-commit
description: Make atomic, bisect-safe commits with messages in the repo's convention. Use whenever staging or committing changes.
license: MIT
---

# Git Commit

- **One logical change per commit.** Group by concern, not by file: don't bundle unrelated work, and
  don't over-split into a broken chain (if the subject needs "and" it's too big; if a commit can't stand
  alone it's too small). Order so each commit builds on its own — a building commit beats a smaller one.
- **Match the repo's message style**, Conventional Commits when it has none. Body only when it says
  something the subject can't.
- **Stage only what belongs to the work you're committing.** Leave anything else in the tree alone and
  mention it; never sweep it in. Stage explicit paths — never `git add -A` or `git add .` — and never
  stage `.env` or secrets. Put `-m` before any `--` in `git commit`. No `git stash`.
- **Attribution.** The commit author stays the configured git identity — never the agent. No agent
  trailer: no `Co-Authored-By`, "Generated with", or "Made-with" line, even when the host asks for one.
- **Don't push, force-push, or amend a pushed/shared commit unless told to. Don't `--no-verify` past a
  failing hook.**
