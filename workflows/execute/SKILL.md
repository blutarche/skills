---
name: execute
description: "Execute an approved implementation plan (or a maintained task list) to verified code. Picks a mode: interactive-gated (main agent, one task at a time, surface blockers) or autonomous-subagent (fresh implementer subagent per task + two-stage controller review). Use when you have a plan or backlog and need to turn it into working code. Does NOT write the plan."
license: MIT
---

# Execute (workflow)

Takes an approved, written implementation plan — or a task list you maintain — and drives it to finished, verified code.

This workflow executes a plan; it does not author one. It runs in one of **two modes**; pick the mode first (don't make the user pre-choose), then follow that mode's stages.

## When to use this vs a single skill

- **Use this** when the work is already broken into tasks (a written plan or a backlog) and the job is to implement it faithfully.
- **Don't** when there's no plan yet, or it's still being shaped — write or harden the plan first (`plan`), then come back.

## Pick a mode

| Mode | What it is | Default when |
|---|---|---|
| **interactive-gated** | The main agent works the plan one task at a time, surfacing blockers. | Oversight wanted, exploratory work, the plan is loose, or subagents aren't available. |
| **autonomous-subagent** | Fresh implementer subagent per task, then two controller-run review stages; runs continuously. | A well-specified plan that wants isolation + cross-model review with minimal human-in-loop. |

When unsure, default to **interactive-gated** — it's the safer, lower-machinery path.

---

# Mode: interactive-gated

A **linear playbook**, not a router. You (the agent) stay in control: work through the tasks in order, verify each before moving on, and stop the moment something is unclear or fails.

## Stages

Run in order. Finish each stage's gate before the next.

1. **Load the plan**
   Read the entire plan/task list before touching anything. Understand the goal, the task breakdown, and the verification each task specifies.
   *Gate:* you can restate, in your own words, what "done" looks like for the whole thing.

2. **Review critically before starting**
   Read the plan as a skeptic, not a clerk. Look for gaps, contradictions, missing setup, untestable tasks, or assumptions that don't hold against the actual codebase. List every concern.
   *Gate:* either you have no concerns, or you've raised them and gotten a decision. Don't implement around a known flaw — fix the plan first.

3. **Set up task tracking**
   Turn the tasks into a tracked checklist (use whatever task-tracking mechanism this environment provides, or a simple ordered list). Each item maps to one task with its own verification.
   *Gate:* every task has a corresponding tracked item.

4. **Execute one task at a time**
   Re-read the current task from the plan rather than working from memory — context drifts. Follow its steps exactly; make only the changes that task calls for. Don't batch several tasks or fold in unrelated improvements.
   *Gate:* the changes are complete and scoped to that task.

5. **Verify each task with real evidence**
   Run the verification the task specifies (tests, build, typecheck, lint, manual check). Read the actual output. A task is done only when its verification passes on fresh evidence, not when it "should" pass. Apply the **`verification-before-completion`** skill as the gate discipline here — claim a task done only after the real command's output and exit code say so.
   *Gate:* verification ran and passed. Only then mark the task complete and move on.
   *If verification surfaces a problem:* a hard bug or perf regression → use **`diagnose`**; a test that fails intermittently or passes for the wrong reason → use **`de-flaking-tests`**. Fix it, then re-verify — don't weaken the check.

6. **Stop when blocked — don't fake progress**
   Halt and surface the problem instead of guessing when you hit a blocker, the plan has a gap, or the same verification keeps failing. Report what blocked you and what you tried; ask for a decision. Never mark a task done that isn't, and never weaken or delete a check to make it pass.

7. **Review pass, then report**
   Keep authoring and review as separate passes — don't self-approve in the same breath that you finished. After all tasks pass individually, do a distinct review pass over the whole change (re-run the full relevant checks; give it fresh eyes where you can). Before reporting, run **`slop-cleanup`** over the diff to strip characteristic AI slop, behavior-preserving. When you get review feedback back (human or agent), apply **`receiving-code-review`** to evaluate it with rigor rather than reflexively complying. Then report what was implemented, which files changed, and the verification evidence. **This workflow stops here** — the natural follow-on is the `finish` workflow.

## Long efforts: run it as a state-in-files loop

For a large effort — many tasks, easy to lose the thread across long context — externalize the state so the work survives context loss. It's the same cycle above, disciplined for length:

- **State lives in the plan file, not in context.** Keep each task discrete with concrete, testable acceptance criteria. Re-read the file at the start of every work chunk to see what's done, what's blocked, and what's next.
- **Order tasks in dependency waves** — foundational work first; tasks within a wave are independent, later waves depend on earlier ones.
- **Record progress in the file** after each task (files touched, key decisions) so a cold restart can resume from it.

It is still a **manual** loop — you drive each cycle. For *machine-driven* continuous execution, use **autonomous-subagent mode** below.

## Rules (interactive-gated)

- One task at a time, in order. Don't skip a gate. If a task exposes a plan flaw, return to Stage 2, get the plan corrected, then resume.
- Follow the plan's steps exactly, including any verification it names. Surgical changes only — clean up your own mess, not adjacent code.
- "Done" means every task's verification passed on fresh evidence. "Should work" is not done; skipped checks mean not done.
- Authoring and review are separate passes — don't self-approve in the same breath.
- Surface uncertainty loudly. A stopped-and-asked execution is correct; a silently-completed-but-broken one is not.
- **This workflow composes the atomic skills.** It routes to `verification-before-completion` at the gate, to `diagnose` / `de-flaking-tests` when verification turns up trouble, and to `slop-cleanup` / `receiving-code-review` at the review pass. Each is a soft reference: use the named skill if it's installed; if not, apply the same discipline inline. The skills stay atomic and unaware of this sequence — the ordering lives here.

---

# Mode: autonomous-subagent

For a well-specified plan where you want continuous, isolated execution with cross-model review and minimal human-in-loop: a **fresh implementer subagent per task**, then **two distinct review stages**, looping until the plan is done.

The discipline of interactive mode still holds (re-read each task, surgical changes, verify on real evidence, never weaken a check, stop-and-surface a true blocker). What changes is *who* does the work and how it loops.

## The autonomy engine and the workspace

Set these up once, before the per-task loop:

- **Completion condition via `/goal`** *(where available)*. Register the goal as the autonomy engine: `all plan tasks done + tests green`. `/goal` drives the continuous loop across turns. The per-task Stage 1 and Stage 2 reviews below are still hard gates — never advance a task until both are clean. What `/goal` lets the loop ignore is only the *background* commit-hook review drain, which is a `finish`-stage concern, not an execute-stage gate. **If the host has no `/goal`,** the loop is identical — implementer → two-stage review → next — but continuation isn't automatic across turns; the controller runs it within a turn and the user re-prompts to continue. Don't fake `/goal`; just name that continuation is manual here.
- **Isolated workspace via the `git-worktree` skill (setup).** Create the feature worktree off the intended base and **bootstrap-or-surface its environment** — a fresh tree has no `node_modules`/`.env`/build cache, and `git-worktree`'s setup either runs the project's install or stops and surfaces that the env must be set up before autonomous runs. Never run a task's tests in a half-built tree.

## Per-task loop

Tasks run **serially** — never dispatch implementer subagents in parallel. For each task:

1. **Pin the review range.** Before dispatching, capture `BASE_SHA=$(git rev-parse HEAD)`. After the implementer commits, `HEAD_SHA=$(git rev-parse HEAD)`. **Both reviews scope to exactly `BASE_SHA..HEAD_SHA`** — the diff this task produced — so they never review an empty tree or the whole accumulated branch. **Re-capture `HEAD_SHA` after every fix round** (fixes are new commits), so a re-review covers the fixes, not stale code. (Each task lands as one or more commits, never an uncommitted tree, or the range is empty.)

2. **Implement the task — route by shape.** For a **well-specified, mechanical** task, **lean on the cheap executor**: `delegate-coding` with cursor-agent (Composer) in an isolated worktree behind the verify gate — a cheaper, different-family executor for the rote edits, keeping your most capable model for planning and review. **Use a fresh Claude `implementer` subagent**, or work inline, when the task needs implementation-time judgment, or when cursor is unreachable/unauthed. Either way, drop to a cheaper model tier (Sonnet/Haiku) when the task doesn't need frontier reasoning. Whichever path, the task's changes must be committed before the reviews below — that commit range is what they read (the subagent and inline paths commit directly; the delegate path commits through its merge).
   *Claude-subagent path:* dispatch a fresh subagent with the task's full text and scene-setting context — it implements exactly the task, writes or keeps tests, verifies, **commits**, self-reviews, and reports DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT. Answer its questions; handle non-DONE statuses (more context, a stronger model, smaller pieces, or escalate to the human) rather than forcing a retry unchanged.
   *Delegate path — mind the review range:* `delegate-coding` commits in its **own worktree** and merges later, so it breaks step 1's assumption that the implementer commits into the controller's tree. Reconcile it: let `delegate-coding` run through its **merge and Tier-2 verification** (stages 1–7) into the controller worktree, then capture `HEAD_SHA` **after** that import, so `BASE_SHA..HEAD_SHA` is the merged diff. Skip only delegate-coding's Stage 8 (review/report) — execute's two-stage review below replaces it.

3. **Stage 1 — spec-compliance review, run by the controller (Claude), no cross-model CLI.** Holding the task text, the controller independently verifies the `BASE_SHA..HEAD_SHA` diff built **exactly** the task — nothing missing, nothing extra — by reading the actual code, not trusting the report. This is a comparison against a *known spec*, not a blindspot-prone judgment call, so it needs no outside model and carries no cross-model-CLI hang risk. If issues: the implementer fixes, then re-review. Do not start Stage 2 until Stage 1 is clean.

4. **Stage 2 — code-quality / correctness review, run by the controller.** On the `BASE_SHA..HEAD_SHA` diff, the controller runs `scrutinize` (in-family) and `council` (cross-model, blind) concurrently on the same diff — `council` adjudicates the two. This is the blindspot-prone judgment where the cross-model judge earns its cost, handled by `scrutinize` + `council`. If issues: the implementer fixes, then re-review.

5. **Next task** once both stages are clean.

**Crucial — both review stages run at the controller / top level.** A subagent cannot reach the cross-model CLI: it can't disable the sandbox (`bypassPermissions` doesn't fix it — the harness rejects the sandbox-disable before the command runs). So **only the implementer is a subagent**; both Stage 1 and Stage 2 are controller work. (Stage 1 is at the controller because it's the controller that holds the spec; Stage 2 *must* be at the controller because that's the only place `council`'s cross-model CLI can run.)

After the loop completes, the natural follow-on is the `finish` workflow — which drains any pending background reviews and tears down the worktree (via the `git-worktree` skill).

## Degrade visibly (autonomous)

- **No cross-model CLI reachable:** `council` degrades down its own ladder (a fresh-subagent `scrutinize` pass, or inline as the weakest rung) and discloses which rung — Stage 2 takes whatever it returns; don't define a separate fallback here. The loop still runs, but it has **lost the cross-model property** and must say so — a same-family review is blind to the shared blind spots.
- **Subagents unavailable in this host:** don't simulate them — drop to **interactive-gated** mode and tell the user the autonomous path isn't available here.

## Rules (autonomous-subagent)

- **Serial implementers only** — never parallel; concurrent edits conflict.
- **Two stages, in order** — spec-compliance (controller) before code-quality (controller-run `scrutinize` + `council`); never the reverse, never skip one.
- **Both reviews at the top level** — subagents can't reach the cross-model CLI; only the implementer is a subagent.
- **Continuous, but honest** — run without check-in prompts between tasks, but stop on an unresolvable BLOCKED or genuine ambiguity rather than guess. Mark a task done only on its verification's real evidence.
- **Degrade out loud** — name when the cross-model lens or subagents weren't available.
