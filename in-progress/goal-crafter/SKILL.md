---
name: goal-crafter
description: Craft a robust, context-rich goal prompt from a rough task description, ready to paste into /goal.
disable-model-invocation: true
---

# Goal Crafter

Turn a rough task into a **dense** goal for `/goal`. Do the **legwork** — gather context,
resolve **forks** — then output a ready-to-paste end-state description. No reasoning, no
commentary, just the goal.

A goal describes **what done looks like**, not how to get there. The executing agent owns
the plan, the approach, and the implementation — the goal gives it an end state, constraints,
and the quality bar.

## 1. Legwork

Gather what the executing agent will need but won't discover on its own. Read, don't guess:

- **Conversation** — decisions made, constraints discussed, prior failures in this session
- **Codebase** — what the task touches, current patterns, project conventions
- **Git** — branch, recent commits, uncommitted changes, what's in-flight
- **Skills** — scan the skill README tables (each area's README.md) and any project-level or
  agent-level skill directories to build a map of what's available
- **Memory** — user preferences, project context, prior feedback
- **Project config** — CLAUDE.md, AGENTS.md, settings that constrain how work should be done

The purpose is to understand scope and constraints, not to pre-analyze the implementation.
Stop when you can state what the task touches and what binds it. The executing agent will
do its own codebase exploration — don't duplicate that work.

## 2. Forks

A **fork** is where two reasonable agents would interpret the task differently, producing
materially different outcomes. After the legwork:

- If you find a fork, ask at most 2 questions using the host's native question tool
  (e.g. `AskUserQuestion`). Each question resolves a fork — it's not an interview.
- If no forks exist, skip this step entirely. Most well-scoped tasks have no forks.

## 3. Output

Write the goal and print it — nothing else. No preamble ("Here's your goal:"), no explanation
of your choices, no follow-up suggestions.

The goal includes:
- **End state** — what done looks like, with a verifiable check (test command exits 0, build
  passes, specific behavior is observable). "It works" is not a done-condition
- **Scope** — what to do, and what not to touch if the task could sprawl. Agents expand scope
  by default — boundaries prevent drift
- **Constraints** — project rules, decisions, and conventions the agent wouldn't find through
  normal exploration. Not implementation details — which API to call, which pattern to use,
  or how to structure the code are approach choices that belong to the executing agent
- **Stop-if** — when to halt and ask instead of guessing. Include only when the task has
  expensive-to-reverse boundaries (e.g. public API surface, shared contracts, security
  semantics). Not every goal needs one
- **Skills** — from the skills map, name the skills that serve this task and when to use
  them. Tell the agent *what* to invoke (e.g. "run `/vet` before landing", "finish through
  `/finish`"), not the skill's internals. Only include skills that earn their place; not
  every goal needs a review pass

The goal is a **short paragraph** — 3 to 6 sentences. Every word must earn its place. Fold
the end state, scope, constraints, and skills into flowing prose rather than separate
sections. Headers, bullet lists, and structured blocks are overhead — write a directive,
not a document.

**Dense** means: if removing a sentence wouldn't change the agent's behavior, delete it.
Describe the end state; don't pre-solve the path to it.
