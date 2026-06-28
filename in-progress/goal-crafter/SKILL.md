---
name: goal-crafter
description: Craft a clear /goal condition for Claude Code's autonomous mode from a rough task description.
disable-model-invocation: true
---

# Goal Crafter

Turn a rough task into a `/goal` condition — a done-check that a small fast model
evaluates from conversation output after each turn.

## How /goal works (write for this)

After each turn an evaluator model reads the conversation and decides yes/no on the
condition. It **cannot run commands or read files** — it only judges what Claude has
already printed. So the condition must name things Claude will surface: test output it
ran and showed, a `git status` it printed, a grep result it displayed.

Write checks as **"Claude has shown X"**, not **"X is true"** — the evaluator can only
verify what appeared in the transcript.

## What to do

1. **If the task is ambiguous, ask one question and stop.** A goal built on the wrong
   interpretation drives autonomous mode toward the wrong outcome — that's worse than
   pausing. Ambiguity triggers: subjective verbs without a measurable end state (clean up,
   improve, refactor, modernize, fix), missing scope boundary, unknown verification command.
   Output exactly one clarifying question and nothing else. If the task is concrete, skip
   this step.

2. **Write the condition.** A goal has three parts, folded into one or two sentences:
   - **End state** — what done looks like, measurable
   - **Stated check** — how Claude proves it in the transcript (e.g. "Claude runs
     `npm test` and the output shows all passing", "Claude prints `git diff --stat` showing
     only the intended files"). Use only commands you know exist in the project; if you don't
     know the test command, ask
   - **Constraints** — what must not change, if anything

   Don't add implementation guidance, skill references, or approach suggestions — the
   executing agent owns all of that.

3. **Print the goal.** Nothing else — no preamble, no explanation.

## What a good goal looks like

Short. The official example: `all tests in test/auth pass and the lint step is clean`.

A more constrained one: `config/ is split into config/parser.py and config/schema.py,
Claude runs pytest -q and shows all passing, and git diff --stat shows changes only in
config/.`

Tight means: if removing a clause wouldn't change the evaluator's yes/no decision, cut it.
Max 4,000 characters, but most goals are under 200.
