---
name: writing-plans
description: Turn a spec into a bite-sized, TDD-shaped implementation plan with exact files, code, and commands. Use when requirements exist for a multi-step task, before touching code.
license: MIT
---

# Writing Plans

## Overview

Write comprehensive implementation plans for a developer who is technically skilled but has zero context for this codebase, problem domain, and toolset — and assume limited test design judgment. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. Apply DRY, YAGNI, and TDD; plan for frequent commits.

**Save plans to:** `docs/plans/YYYY-MM-DD-<feature-name>.md`
- (User preferences for plan location override this default)

No time or effort estimates in the plan unless asked.

## Scope Check

If the spec covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. If it wasn't, suggest breaking this into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. Each file should have one clear responsibility; files that change together should live together — split by responsibility, not by technical layer. In existing codebases, follow established patterns; don't unilaterally restructure, though a split of a file that has grown unwieldy is reasonable to include. Each task should produce self-contained changes that make sense independently.

## Task Right-Sizing

A task is the smallest unit that carries its own test cycle and is worth a fresh reviewer's gate. Fold setup, configuration, scaffolding, and documentation steps into the task whose deliverable needs them. Split only where a reviewer could reject one task and approve its neighbor. Each task ends with an independently testable deliverable.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes).** For code tasks, follow the TDD cycle:
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

For tasks with no meaningful unit test (config, dependency, docs, or manual-verification changes), drop the test steps and give a concrete verification step instead — the exact command to run or the exact thing to check, with expected output. Do not fabricate a placeholder test.

## Plan Document Header

**Every plan starts with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For implementers:** steps use checkbox (`- [ ]`) syntax for tracking — execute them task-by-task. Hardening this plan (with `grill-me`, applying `domain-modeling` discipline against an existing codebase) and executing it are separate steps.

**Spec:** [path to the spec/design doc this plan implements; executors read both]

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

## Global Constraints

[The spec's project-wide requirements (version floors, dependency limits, naming and copy rules, platform requirements), one line each, exact values copied verbatim from the spec. Every task's requirements implicitly include this section.]

## Review Focus

[The top input classes or failure modes the spec implies but no task's tests exercise, most likely to bite a user first, one line each: the input or condition, and the behavior a reasonable person would expect. The spec's silence on an input is not permission for it to break. Write the list once, with the spec in front of you; then add the test that pins each line to the task that owns the code.]

---
```

## Task Structure

The examples below use Python/pytest only for illustration — write every code block and command in the plan's actual language and test runner.

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Interfaces:**
- Consumes: [what this task uses from earlier tasks, with exact signatures]
- Produces: [what later tasks rely on: exact function names, parameter and return types. An implementer sees only their own task; this block is how they learn the names and types neighboring tasks use.]

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## No Placeholders

Every step must contain the actual content an engineer needs. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — the engineer may be reading tasks out of order)
- Steps that describe what to do without showing how (code blocks required for code steps)
- References to types, functions, or methods not defined in any task

## Self-Review

After writing the complete plan, check it against the spec yourself — not as a subagent dispatch.

**1. Spec coverage:** Can you point to a task that implements each requirement in the spec? If a requirement has no task, add one.

**2. Placeholder scan:** Search the plan for any of the patterns in "No Placeholders" above. Fix them.

**3. Type consistency:** Do the types, method signatures, and property names you used in later tasks match what you defined in earlier tasks? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

**4. Review Focus:** Does each input class or failure mode in the header's Review Focus have a test in the task that owns its code? An empty section means you checked and found none.

Fix issues inline; no need to re-review.

## After the plan

This skill's output is the saved plan file. Hardening it (`grill-me`, applying `domain-modeling` discipline against an existing codebase's domain model) and executing it are **separate steps owned by the caller or workflow** — don't auto-invoke them from here. Never start implementation on `main`/`master` without explicit user consent.
