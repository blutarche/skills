---
name: evidence
description: Check every claim in a reply or report against proof before you state it; verify it now or drop it. Use before you say done, fixed, works, tested, or shipped; when you write a report or sitrep; when you relay a subagent's or worker's claim; and when the user asks "tested?", "verified?", "you sure?", "show me", or "e2e?".
---

# Evidence

A claim without proof is noise. It also makes the true claims next to it hard to trust. Before a reply goes out, every claim in it carries proof, or the claim goes.

## Steps

1. **List the claims.** Read your draft reply. Write down each statement of fact about the work: what changed, what works, what is fixed, what was tested, what a worker did. Done when every such statement is on the list.
2. **Attach proof or drop.** For each claim, attach proof from the ladder below. If you cannot, run the check now (step 3). If you still cannot, delete the claim. Never put a recommendation next to "I haven't verified". Verify first, or do not recommend.
3. **Run what you can run.** Any check you can run from this machine, you run now: start the app, open the page, run the command, read the trace. If the sandbox blocks it, retry through the permission gate. Do not report a runnable check as "untested".
4. **Mark what you truly cannot run.** Only production and the user's own login or credentials are out of reach. Put each on its own line that starts with `Blocked:` and say exactly what stops it. A `Blocked:` line is not a place to park work you could do.
5. **Check the reply again.** Done when every claim left has proof next to it, or sits on a `Blocked:` line.

## Proof ladder

Use the highest rung you can reach:

1. A live run, done as the user would do it: the real app, a browser tab the user can open, a real device.
2. A trace id or log line from that run.
3. The command, its exit code, and the key output, run on the current commit.
4. A screenshot of the real app.

These are **not** proof:

- Unit tests alone, for behavior the user sees.
- Screenshots of fixtures, dev scenes, or mock data.
- A subagent's or worker's word without primary output. If you relay it, label it "worker-reported".
- "Should work", "likely fixed", or reasoning from memory.

## Rules

- **Time-box.** Do not loop on a check. If a check cannot pass within the task's time budget, stop. Report it on a `Blocked:` line with what you tried.
- **Proof lives in the reply.** Put proof in the reply, report, or sitrep. Never put commit ids, proof notes, or check lists inside deliverable docs such as design docs or READMEs.
- **The user's screen wins.** When the user says what they see, do not argue. Capture the screen or reproduce it yourself, then fix.

## Notes

A Stop hook (`owner-handoff-check.py` in the companion agents repo) may block replies that name unverified work. This skill must work without it: Codex, Cursor, and Hermes do not load that hook or a global rule file.
