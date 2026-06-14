---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up.
argument-hint: "What will the next session be used for?"
license: MIT
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save it to the user's OS temporary directory (not the current workspace) with a descriptive, timestamped filename such as handoff-<topic>-<YYYYMMDD-HHMM>.md. After saving, report the absolute path of the file to the user.

Include a "suggested skills" section listing skills the next agent should consider invoking to continue the work. Do not invoke them yourself. Omit the section if no skill is clearly relevant rather than padding it.

Do not duplicate content already captured in other artifacts (PRDs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.
