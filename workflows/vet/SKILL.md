---
name: vet
description: "Deliberate cross-model review of a branch, diff, or PR, then a gated fix loop. Runs `scrutinize` (Claude's outsider pass) and `council` (a cross-model attack on the same diff, e.g. Codex), which adjudicates the two disagreement-first; then drives accepted fixes through the fixer skills and re-reviews until clean. Use when you want a finished change vetted before it ships — review plus follow-through, not just a report."
---

# Vet (workflow)

Takes a finished change — working tree, a diff against a base ref, or a PR — and drives it through a cross-model review and a gated fix loop to a shippable state.

This is a **linear playbook**, deliberately **thin**: it sequences existing skills. `scrutinize` owns the in-family review methodology; `council` owns the cross-model machinery (convene the outside model, adjudicate disbelieve-back); the fixer skills own the edits. Vet runs `scrutinize` and council's cross-model **convene** on the **same diff** *concurrently* — the convene is **blind** (the diff only, never `scrutinize`'s findings) no matter the order — then, once both are in, `council` **adjudicates** the two sets, reconciling its findings against `scrutinize`'s. Vet then adds the **gated fix loop**. If you find yourself writing review or edit logic here, push it back into the leaf skill.

## When to use this vs a single skill

- **Use this workflow** when a change is done and you want it vetted *and followed through* — review, then fix what's real and re-review.
- **Invoke a single skill directly** when you only need one piece: `scrutinize` for a Claude-only report, `council` for the cross-model second opinion, `/simplify` or `slop-cleanup` to apply a known cleanup.
- **Don't re-vet what `execute` autonomous mode already reviewed** — that loop reviews every task with `scrutinize` + `council`, so vetting its output just reviews twice. Use `vet` for changes made *outside* that loop (interactive-mode or hand-authored work, a PR) or as a deliberate fresh second opinion.

## Stages

Run in order. Finish each gate before the next.

1. **Scope**
   Fix what's under review: the working tree, a `--base <ref>` diff, or a PR. State it explicitly so both reviews look at the same thing.
   *Gate:* the artifact and its boundaries are pinned.

2. **Review — `scrutinize` ∥ `council`** (both read-only, run concurrently)
   The two passes are **independent** — `council` stays blind to `scrutinize`'s findings either way — so don't serialize them. On a wide or risky diff, **launch `council`'s cross-model CLI as a background top-level call and run `scrutinize` concurrently** (which itself fans its lenses out to read-only subagents); then **join at adjudication**, where `council` reconciles the two blind sets disbelieve-it-back and returns **disagreement-first** findings + a "what the council changed" note. (`council` convenes from the **top-level session** — a subagent can't reach the CLI; only `scrutinize`'s lenses fan out.) On a small/low-risk diff the overlap earns nothing — run them inline in either order. Add `/security-review` when the change touches untrusted input/authz/secrets; `/review` for a PR.
   *Gate:* `council` has returned the adjudicated findings (or has degraded — see below).

3. **Decide which to apply** (the gate)
   `council` already adjudicated, so vet's job is to *act on* the findings, not re-review them. **Don't apply blindly** — the caller decides: in interactive use, present the findings and ask which to fix; when vet runs inside an autonomous loop, the controller decides and proceeds with no human halt (see Rules).
   *Gate:* the findings to act on are chosen.

4. **Fix loop**
   For the accepted findings, hand off — don't fix inline:
   - **`receiving-code-review`** first — evaluate each accepted finding with rigor, push back with reasons where the reviewer (Claude or council) is wrong, then implement only what's valid.
   - **`/simplify`** for quality/over-engineering cleanups; **`slop-cleanup`** *only* when the finding is AI-slop-shaped.
   - **`verification-before-completion`** (or `/verify` / `/run`) to confirm each fix on real evidence; then **`git-commit`**.
   - **Re-review** the fixed change (back through stage 2) until it comes back clean. If the findings amount to substantial rework, this isn't a fix loop — hand back to the `execute` workflow.
   *Gate:* the change re-reviews clean, or has been escalated back to `execute`.

## Degrade visibly

If no outside model is reachable, `council` degrades down its ladder (fresh-subagent `scrutinize`, or inline as the weakest rung) and says which. Vet then has only the in-family lens: it still runs, but the report must note that the cross-model property was lost — a same-family review is blind to the blind spots you share, and the reader must know.

## Rules

- **Thin by design.** Vet sequences review (`scrutinize` ∥ `council`) → decision → fix loop; it never reimplements review methodology, and never edits *inline*. Editing happens only in the fix stage, *after* the decision gate, by handing off to the fixer skills — vet drives them, it doesn't do the edits itself. The composed skills stay atomic and unaware of this sequence.
- **Disbelieve the council back.** A confident outsider is still wrong; the code decides, never the louder voice. (`council` enforces this in its adjudication; don't undo it.)
- **Agreement is weak signal; disagreement is the payload.** Lead with where the two models differ.
- **Separate review from fixing — don't apply blindly.** The caller decides what to apply: a human in interactive use, the **controller** in an autonomous loop. The gate is "verify before applying," *not* "halt for a human" — never stall an autonomous run waiting on a prompt.
- **Composed skills are soft references.** Normally vet hands off and doesn't edit inline. The only exception is *degraded operation* when a tool is genuinely absent — and it still happens in the **fix stage, after the decision gate**, never folded into review: a missing repo skill (`receiving-code-review`, `slop-cleanup`) → apply its discipline directly; a missing opaque host command (`/simplify`, `/security-review`, `/review`) → use it if present, else **note it was skipped** and move on (don't pretend to reimplement a built-in you can't see). Never skip a *stage* just because one tool is missing.
