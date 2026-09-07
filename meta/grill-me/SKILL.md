---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when the user wants to stress-test a plan before building, get grilled on a design, or uses any 'grill' trigger phrase.
license: MIT
---

If no plan or design has been provided yet, first ask me to state the plan (or point you to it). Then interview me about every open decision in the plan, walking down each branch of the decision tree and resolving dependencies between decisions. Stop when every branch is resolved or I say to stop, then summarise the decisions we settled. For each question, provide your recommended answer.

If the host agent exposes a structured question tool, such as Claude Code's `AskUserQuestion`, ask every grill question through it rather than as a wall of plain-text prose; fall back to plain text only when no such tool exists. Ask one question per call by default, listing your recommended answer first with "(Recommended)" appended to its label, then the other plausible branches, leaving room for me to pick "Other." Batch several questions in one call only when they are independent and sit on the same branch of the decision tree.

Resolve the current branch before moving on, using my answers to decide which branch to pursue next.

If a question can be answered by exploring the codebase, explore the codebase instead.
