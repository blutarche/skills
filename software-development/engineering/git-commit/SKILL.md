---
name: git-commit
description: "Create clean, atomic, bisect-safe git commits — one logical change each, messages in the repo's commit convention (Conventional Commits by default), and a neutral Co-Authored-By trailer that credits the agent, not the model. Use whenever about to commit: staging changes, writing a commit message, or asked to \"commit this\"."
license: MIT
---

# Git Commit

- **One logical change per commit.** Group by concern, not by file: don't bundle unrelated work, and
  don't over-split into a broken chain (if the subject needs "and" it's too big; if a commit can't stand
  alone it's too small). Order so each commit builds on its own — a building commit beats a smaller one.
- **Match the repo's message style**, Conventional Commits when it has none. Body only when it says
  something the subject can't.
- **Stage only what belongs to the work you're committing.** Leave anything else in the tree alone and
  mention it; never sweep it in.
- **Attribution.** The commit author stays the configured git identity — never the agent. The agent is
  only ever a `Co-Authored-By` trailer, neutral, with the model/version stripped (`Opus 4.8`, `GPT-5`,
  `(1M context)`):

  | Agent | Trailer |
  |---|---|
  | Claude Code | `Co-Authored-By: Claude <noreply@anthropic.com>` |
  | Codex CLI | `Co-Authored-By: Codex <noreply@openai.com>` |

  No known agent identity, or a human committing → no trailer; never invent one. No "Generated with" /
  "Made-with" line.
- **Don't push, force-push, or amend a pushed/shared commit unless told to. Don't `--no-verify` past a
  failing hook.**
