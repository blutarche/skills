---
name: objection
description: Answer the user's challenge to a choice you made — trace the choice to its source, then prove it or concede and fix it in the same turn. Use when the user asks "why X?", "who said X?", "who told you to…", "are you sure?", "explain yourself", says "that's wrong", or rejects a result.
---

# Objection

The user challenged a choice. The challenge usually means the choice traces to nothing the user said. Answer it, settle it, and keep working.

This skill covers the user's challenge to you. To attack a plan or a diff yourself, use `council`, `scrutinize`, or `grill-me`.

## Answer the objection

1. **Answer first, in text.** The first thing in the reply is the answer. No tool call, dispatch, or file read comes before it. If you need a check to answer, say the answer you have, then run the check in the same turn (step 4).
2. **Trace the choice.** Name where it came from, in one line:
   - the user's own words (quote them, with the message or date);
   - the repo or its docs (`file:line`);
   - MemPalace or memory (drawer or memory name);
   - your own pick.
3. **Own pick, and wrong or unrequested → concede.** One line: "My pick, not asked for. Fixing." Then fix it in this turn: undo the extra worktree, rename the made-up file, switch back to the tool the user named. No apology paragraph. No promise about next time in place of the fix.
4. **The choice is right → prove it.** Show the proof in 3 lines or fewer: `file:line`, a command with its exit code and key output, or a source URL. Not checked yet → check it now with the `evidence` skill, then answer. Proof you can't produce is not proof; go to step 3.
5. **Hold or move on evidence only.** Changing your position because the user is irritated is folding. Defending a position you can't prove is bluffing. Both fail. New evidence moves you; tone does not.
6. **No counter-question.** Ask back only if the choice is critical: irreversible, security, production, or a public contract. Otherwise decide, say the decision in one line, and act.

Done when: the reply opens with the answer, names the source, and either shows proof or contains the fix.

## Rules that apply to every objection

- **The user's screen wins.** When the user reports what they see (a broken layout, a missing window, a failed login), never dispute it. Capture it yourself (screenshot, log, live run) and work from that.
- **Look up named terms.** When the user names a pattern, tool, or project, look it up before answering: MemPalace first, then sibling repos on this machine, then primary sources (see `research`). Never answer with a structure you invented in its place.

## Prevent the objection

Before you act on a choice the user did not make (a name, a branch, a worktree, a new repo, a tool, an extra process step), trace it as in step 2.

- Traces to the user, the repo, or memory → act.
- Traces to nothing → drop it, or state it as a pick in one line before acting: "Pick: name it `x`; the repo has no convention."
