---
name: brainstorming
description: Turn a vague idea or feature brief into an approved design doc through one-question-at-a-time dialogue; no code until approved. Use before adding features or changing behavior.
license: MIT
---

# Brainstorming Ideas Into Designs

> **Hard gate:** Do not invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it. This applies to every project regardless of perceived simplicity.

## The Process

**Understanding the idea:**

- **Look before you ask.** Check the project state (files, docs, recent commits) and read whatever context the user referenced (spec, plan, handoff, files, earlier conversation) and the code it connects to. Keep reading until you can explain how the relevant parts work today and what the change would touch. Never ask what the project already answers, and never reopen a point they already decided.
- Before asking detailed questions, assess scope: if the request describes multiple independent subsystems (e.g., "build a platform with chat, file storage, billing, and analytics"), flag this immediately. Don't spend questions refining details of a project that needs to be decomposed first.
- If the project is too large for a single spec, help the user decompose into sub-projects: what are the independent pieces, how do they relate, what order should they be built? Then brainstorm the first sub-project through the normal design flow. Each sub-project gets its own spec → plan → implementation cycle.
- For appropriately-scoped projects, ask questions one at a time to refine the idea
- Ask only when the answer changes what gets built and nothing answers it. Otherwise state your call and reason as a proposal they can correct, and move on.
- Only one question per message, asked through the host's structured question tool (Claude Code: `AskUserQuestion`) when available - if a topic needs more exploration, break it into multiple questions
- Apply YAGNI ruthlessly — keep unnecessary features out of the design

**Exploring approaches:**

- Propose 2-3 different approaches with trade-offs
- Present options conversationally with your recommendation and reasoning
- Lead with your recommended option and explain why

**Presenting the design:**

- Once you believe you understand what you're building, present the design (it can be short — a few sentences for truly simple projects — but you must present it and get approval)
- Scale each section to its complexity: a few sentences if straightforward, up to 200-300 words if nuanced
- Get the user's approval after each section before moving on
- Cover: architecture, components, data flow, error handling, testing
- Break the system into smaller units with one clear purpose and well-defined interfaces; in existing codebases follow existing patterns and don't propose unrelated refactoring

## After the Design

**Documentation:**

- Write the validated design to `docs/plans/YYYY-MM-DD-<topic>-design.md` — `docs/plans/` holds working designs and plans (often gitignored, local-only); `docs/specs/` is for *finalized* specs only.
  - (User preferences for location override this default)
- The doc has an **Approaches** part: the options considered, their trade-offs, your pick and why.
- If (and only if) the target directory is tracked by git, commit the design after the User Review Gate. If it's gitignored (as `docs/plans/` often is), skip the commit. Check before assuming you can commit.

**Spec Self-Review:**
After writing the spec, look at it with fresh eyes and fix any issues inline:

1. **Placeholder scan:** Any "TBD", "TODO", incomplete sections, or vague requirements?
2. **Internal consistency:** Do any sections contradict each other? Does the architecture match the feature descriptions?
3. **Scope check:** Is this focused enough for a single implementation plan, or does it need decomposition?
4. **Ambiguity check:** Could any requirement be interpreted two different ways? If so, pick one and make it explicit.

**Builder check:**
Next to the self-review, dispatch a fresh subagent to read the doc as a builder who can't ask questions. It returns a ranked list of questions it would have to answer before building. Sort each into answered (the doc already says), your call (decide, and write it into the doc as your call), or theirs (a decision only the user can make). Bring "theirs" back to the user in one message. With no subagent available, do this pass yourself and say so.

**User Review Gate:**
After the self-review, ask the user to review the written spec before proceeding:

> "Design written to `<path>`. Please review it and let me know if you want any changes[, then I'll commit it]. We'll start the implementation plan once you approve."

(Include the commit clause only if the directory is git-tracked; omit it for gitignored/local-only locations.)

Wait for the user's response. If they request changes, make them and re-run the self-review. Only proceed once the user approves.

**Next step:** The approved design doc is this skill's output. Turning it into an implementation plan (e.g. `writing-plans`) is owned by the workflow or user that invoked this skill (see the `blueprint` workflow) — don't auto-invoke it.

## Red Flags

- A default they never heard is one they couldn't reject. Anything you decided for them goes in the design where they can see it and push back.
