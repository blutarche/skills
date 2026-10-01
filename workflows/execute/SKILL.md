---
name: execute
disable-model-invocation: true
description: Drive an approved plan to verified code — interactive-gated or autonomous-subagent mode.
license: MIT
---

# Execute (workflow)

Executes an approved plan or a task list you maintain; it does not author one. If there's no plan yet, or it's still being shaped, write or harden it first (`plan`). Pick the mode first (don't make the user pre-choose), then follow that mode's stages. The skills it routes to (`diagnose`, `slop-cleanup`, `receiving-code-review`) are soft references: if one isn't installed, apply the same discipline inline.

## Pick a mode

| Mode | What it is | Default when |
|---|---|---|
| **interactive-gated** | The main agent works the plan one task at a time, surfacing blockers. | Oversight wanted, exploratory work, the plan is loose, or subagents aren't available. |
| **autonomous-subagent** | Fresh implementer subagent per task, then two controller-run review stages; runs continuously. | A well-specified plan that wants isolation + cross-model review with minimal human-in-loop. |

When unsure, default to **interactive-gated** — it's the safer, lower-machinery path.

---

# Mode: interactive-gated

Work through the tasks in order, verify each before moving on, and stop the moment something is unclear or fails.

## Stages

Run in order. Finish each stage's gate before the next.

1. **Load the plan**
   Read the entire plan/task list before touching anything.
   *Gate:* you can restate, in your own words, what "done" looks like for the whole thing.

2. **Review critically before starting**
   Read the plan as a skeptic, not a clerk. Look for gaps, contradictions, missing setup, untestable tasks, or assumptions that don't hold against the actual codebase. List every concern.
   *Gate:* either you have no concerns, or you've raised them and gotten a decision. Don't implement around a known flaw — fix the plan first.

3. **Set up task tracking**
   Turn the tasks into a tracked checklist (use whatever task-tracking mechanism this environment provides, or a simple ordered list). Each item maps to one task with its own verification.
   *Gate:* every task has a corresponding tracked item.

4. **Execute one task at a time**
   Re-read the current task from the plan rather than working from memory — context drifts. Follow its steps exactly; make only the changes that task calls for, and clean up your own mess, not adjacent code. Don't batch several tasks or fold in unrelated improvements. If a task exposes a plan flaw, return to Stage 2, get the plan corrected, then resume.
   *Gate:* the changes are complete and scoped to that task.

5. **Verify each task with real evidence**
   Run the verification the task specifies (tests, build, typecheck, lint, manual check). Read the actual output. A task is done only when its verification passes on fresh evidence, not when it "should" pass; claim it done only after the real command's output and exit code say so. A skipped check means not done.
   *Gate:* verification ran and passed. Only then mark the task complete and move on.
   *If verification surfaces a problem:* a hard bug, perf regression, or a test that fails intermittently or passes for the wrong reason → use **`diagnose`**. Fix it, then re-verify — don't weaken the check.

6. **Stop when blocked — don't fake progress**
   Halt and surface the problem instead of guessing when you hit a blocker, the plan has a gap, or the same verification keeps failing. Report what blocked you and what you tried; ask for a decision. Never mark a task done that isn't, and never weaken or delete a check to make it pass. A stopped-and-asked execution is correct; a silently-completed-but-broken one is not.

7. **Review pass, then report**
   Keep authoring and review as separate passes — don't self-approve in the same breath that you finished. After all tasks pass individually, do a distinct review pass over the whole change (re-run the full relevant checks; give it fresh eyes where you can). Before reporting, run **`slop-cleanup`** over the diff to strip characteristic AI slop, behavior-preserving. When you get review feedback back (human or agent), apply **`receiving-code-review`** to evaluate it with rigor rather than reflexively complying. Then report what was implemented, which files changed, and the verification evidence. Deliver that report as a `walkthrough` of the BASE..HEAD diff by default; use `brief` instead when the run halted BLOCKED at stage 6, or ran in autonomous-subagent mode across multiple tasks, where the story is the run itself — task timeline, verification evidence table, blockers — not the code. Never deliver both for the same run. Without `walkthrough` or `brief` installed, report in prose. **This workflow stops here** — the natural follow-on is the `finish` workflow.

## Long efforts: run it as a state-in-files loop

For a large effort — many tasks, easy to lose the thread across long context — externalize the state so the work survives context loss. It's the same cycle above, disciplined for length:

- **State lives in the plan file, not in context.** Keep each task discrete with concrete, testable acceptance criteria. Re-read the file at the start of every work chunk to see what's done, what's blocked, and what's next.
- **Order tasks in dependency waves** — foundational work first; tasks within a wave are independent, later waves depend on earlier ones.
- **Record progress in the file** after each task (files touched, key decisions) so a cold restart can resume from it.

It is still a **manual** loop — you drive each cycle. For *machine-driven* continuous execution, use **autonomous-subagent mode** below.

---

# Mode: autonomous-subagent

For a well-specified plan where you want continuous, isolated execution with cross-model review and minimal human-in-loop: a **fresh implementer subagent per task**, then **two distinct review stages**, looping until the plan is done.

The discipline of interactive mode still holds (re-read each task, surgical changes, verify on real evidence, never weaken a check, stop-and-surface a true blocker). What changes is *who* does the work and how it loops. Run without check-in prompts between tasks, but stop on an unresolvable BLOCKED or genuine ambiguity rather than guess.

## The autonomy engine and the workspace

Set these up once, before the per-task loop:

- **Completion condition via `/goal`** *(where available)*. Register the goal as the autonomy engine: `all plan tasks done + tests green`. `/goal` drives the continuous loop across turns. The per-task Stage 1 and Stage 2 reviews below are still hard gates — never advance a task until both are clean. **If the host has no `/goal`,** the loop is identical — implementer → two-stage review → next — but continuation isn't automatic across turns; the controller runs it within a turn and the user re-prompts to continue. Don't fake `/goal`; just name that continuation is manual here.
- **Isolated workspace via the `git-worktree` skill (setup).** Create the feature worktree off the intended base and **bootstrap-or-surface its environment** — a fresh tree has no `node_modules`/`.env`/build cache, and `git-worktree`'s setup either runs the project's install or stops and surfaces that the env must be set up before autonomous runs. Never run a task's tests in a half-built tree.

## Per-task loop

Tasks run **serially** — never dispatch implementer subagents in parallel (concurrent edits conflict). For each task:

1. **Pin the review range.** Before dispatching, capture `BASE_SHA=$(git rev-parse HEAD)`. After the implementer commits, `HEAD_SHA=$(git rev-parse HEAD)`. **Both reviews scope to exactly `BASE_SHA..HEAD_SHA`** — the diff this task produced — so they never review an empty tree or the whole accumulated branch. **Re-capture `HEAD_SHA` after every fix round** (fixes are new commits), so a re-review covers the fixes, not stale code. (Each task lands as one or more commits, never an uncommitted tree, or the range is empty.)

2. **Implement the task — route by shape.** Default: dispatch a fresh implementer subagent (the host's default implementer subagent when it has one), or work inline. Use `delegate-coding` (e.g. cursor-agent in an isolated worktree behind the verify gate) only when the user asked for an external CLI, or for bulk mechanical work; if that CLI is unreachable/unauthed, fall back to the subagent path. Either way, drop to a cheaper model tier (Sonnet/Haiku) when the task doesn't need frontier reasoning. Whichever path, the task's changes must be committed before the reviews below — that commit range is what they read (the subagent and inline paths commit directly; the delegate path commits through its merge).
   *Subagent path:* dispatch a fresh subagent with the task's full text and scene-setting context — it implements exactly the task, writes or keeps tests, verifies, **commits**, self-reviews, and reports DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT. Answer its questions; handle non-DONE statuses (more context, a stronger model, smaller pieces, or escalate to the human) rather than forcing a retry unchanged.
   *Delegate path — mind the review range:* `delegate-coding` commits in its **own worktree** and merges later, so it breaks step 1's assumption that the implementer commits into the controller's tree. Reconcile it: let `delegate-coding` run through its **merge and Tier-2 verification** (stages 1–7) into the controller worktree, then capture `HEAD_SHA` **after** that import, so `BASE_SHA..HEAD_SHA` is the merged diff. Skip only delegate-coding's Stage 8 (review/report) — execute's two-stage review below replaces it.

3. **Stage 1 — spec-compliance review, run by the controller (Claude), no cross-model CLI.** Holding the task text, the controller independently verifies the `BASE_SHA..HEAD_SHA` diff built **exactly** the task — nothing missing, nothing extra — by reading the actual code, not trusting the report. This is a comparison against a *known spec*, not a blindspot-prone judgment call, so it needs no outside model and carries no cross-model-CLI hang risk. If issues: the implementer fixes, then re-review. Do not start Stage 2 until Stage 1 is clean.

4. **Stage 2 — code-quality / correctness review, run by the controller.** On the `BASE_SHA..HEAD_SHA` diff, the controller runs `scrutinize` (in-family) and `council` (cross-model, blind) concurrently on the same diff — `council` adjudicates the two. This is the blindspot-prone judgment where the cross-model judge earns its cost. If issues: the implementer fixes, then re-review.

5. **Next task** once both stages are clean.

**Both review stages run at the controller / top level; only the implementer is a subagent** — a subagent can't reach `council`'s cross-model CLI (see `council`). Stage 1 is at the controller because it holds the spec.

After the loop completes, the natural follow-on is the `finish` workflow — which tears down the worktree (via the `git-worktree` skill).

## Degrade visibly (autonomous)

- **No cross-model CLI reachable:** `council` degrades down its own ladder (a fresh-subagent `scrutinize` pass, or inline as the weakest rung) and discloses which rung — Stage 2 takes whatever it returns; don't define a separate fallback here. The loop still runs, but it has **lost the cross-model property** and must say so — a same-family review is blind to the shared blind spots.
- **Subagents unavailable in this host:** don't simulate them — drop to **interactive-gated** mode and tell the user the autonomous path isn't available here.
