---
name: sitrep
description: "Gather the real state of the current work, report what is done with proof, what needs the user, and what comes next, then start the next step. Use when the user asks \"what now?\", \"what next?\", \"so?\", \"all done?\", \"status?\", \"what's left?\", or comes back after being away."
argument-hint: "[all]"
---

# Sitrep (workflow)

The user asks for a sitrep at two moments. Either the agent stopped early, or the user comes back after time away. Both need the same answer: the true state in a few lines, then work that continues. A sitrep is not a stopping point.

## Steps

Run in order.

1. **Gather the real state.** Read only. Change nothing in this step. Use each source that is present:
   - Git: branch, `git status`, ahead and behind the base, and the project's worktrees.
   - Pull requests: open PRs and their checks, through `gh`, when the project has a remote.
   - Running work: background tasks, subagents, and agent threads (T3 or Orca tools, when present).
   - MemPalace: recent drawers in the project's wing.
   - This session: its own open tasks and promises.

   If a source is absent, skip it. Name the skip in one line only when it hides something the user needs.

2. **Sort each item into one class.**
   - **Done:** finished, with proof. Use the `evidence` skill to check each claim. An item without proof is not done. It is in flight.
   - **In flight:** started and not finished.
   - **Needs the user:** only critical items. These are irreversible actions, security, production, a public contract, or the user's own login, credentials, or browser.
   - **Noise:** everything else.

3. **Drop the noise.** Do not list leftovers that do not need the user. Do not add items from before this work or from other sessions. Do not repeat history the user already saw.

4. **Report.** Name the project and the branch every time. The user works on many projects at once. The chat reply has 3 lines at most:
   - State: what is done and proven, and what is in flight.
   - Needs you: the critical items, or "nothing".
   - Next: the step you start now.

   If the report needs more than 3 lines, render it with the `brief` skill (kind `session`). Then reply with the 3 lines and the page path or link.

5. **Start the next step in the same turn.** Do the work. Do not end with "next is X" and stop. If the next step is blocked on the user, write one line that starts with `Blocked:` and says exactly what stops it. Then do any other work that is not blocked.

## Across projects

Use this mode when a hub runs the sitrep, or when the argument is `all`. Read the project list from the hub, for example the `hub/registry` folder of the companion agents repo, when present. Run steps 1 to 3 for each project. Give one line per project: project, branch, state, and needs-you. Then report and continue as in steps 4 and 5.

## Rules

- Give only what is true now. Old status from memory is a lead to check, not a fact.
- Do not ask questions about choices that are not critical. Pick the best option and state it in one line.
- Do not give the user steps that you can do yourself, such as running, testing, or checking.
