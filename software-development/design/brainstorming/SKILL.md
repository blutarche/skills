---
name: brainstorming
description: "Use before any creative/build work — adding features, building components, new functionality, or changing behavior. Turns a brief or vague idea into an approved design doc through one-question-at-a-time dialogue. Does NOT write code until the design is approved. Output is the design doc; the next step is owned by the caller."
license: MIT
---

# Brainstorming Ideas Into Designs

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design and get user approval.

> **Hard gate:** Do not invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it. This applies to every project regardless of perceived simplicity.

## The Process

**Understanding the idea:**

- Check out the current project state first (files, docs, recent commits)
- Before asking detailed questions, assess scope: if the request describes multiple independent subsystems (e.g., "build a platform with chat, file storage, billing, and analytics"), flag this immediately. Don't spend questions refining details of a project that needs to be decomposed first.
- If the project is too large for a single spec, help the user decompose into sub-projects: what are the independent pieces, how do they relate, what order should they be built? Then brainstorm the first sub-project through the normal design flow. Each sub-project gets its own spec → plan → implementation cycle.
- For appropriately-scoped projects, ask questions one at a time to refine the idea
- Prefer multiple choice questions when possible, but open-ended is fine too
- Only one question per message - if a topic needs more exploration, break it into multiple questions
- Focus on understanding: purpose, constraints, success criteria
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
- Be ready to go back and clarify if something doesn't make sense
- Break the system into smaller units with one clear purpose and well-defined interfaces; in existing codebases follow existing patterns and don't propose unrelated refactoring

## After the Design

**Documentation:**

- Write the validated design (spec) to `docs/specs/YYYY-MM-DD-<topic>-design.md`
  - (User preferences for spec location override this default)
- After the user approves the spec at the User Review Gate, commit the design document to git.

**Spec Self-Review:**
After writing the spec document, look at it with fresh eyes:

1. **Placeholder scan:** Any "TBD", "TODO", incomplete sections, or vague requirements? Fix them.
2. **Internal consistency:** Do any sections contradict each other? Does the architecture match the feature descriptions?
3. **Scope check:** Is this focused enough for a single implementation plan, or does it need decomposition?
4. **Ambiguity check:** Could any requirement be interpreted two different ways? If so, pick one and make it explicit.

Fix any issues inline. No need to re-review — just fix and move on.

**User Review Gate:**
After the self-review checklist is complete, ask the user to review the written spec before proceeding:

> "Spec written to `<path>` (not yet committed). Please review it and let me know if you want any changes; I'll commit it once you approve, before we start the implementation plan."

Wait for the user's response. If they request changes, make them and re-run the self-review checklist. Only proceed once the user approves.

**Next step (advisory):**

- The approved design doc is this skill's output. A typical next step is turning it into an implementation plan — e.g. the `writing-plans` skill — but that sequencing is owned by the workflow or user that invoked this skill (see the `plan` workflow). Don't auto-invoke it.
