---
name: vet
disable-model-invocation: true
description: Cross-model review of a branch, diff, or PR (scrutinize + council), then a gated fix loop until clean.
---

# Vet (workflow)

Vet runs `scrutinize` and council's cross-model **convene** on the **same diff** *concurrently* — the convene is **blind** (the diff only, never `scrutinize`'s findings) no matter the order — then `council` **adjudicates** the two sets. Vet adds the **gated fix loop**. Review logic belongs to `scrutinize` and `council`, edit logic to the fixer skills; don't write either here.

## When to use this vs a single skill

- **Invoke a single skill directly** when you only need one piece: `scrutinize` for a Claude-only report, `council` for the cross-model second opinion, `/simplify` or `slop-cleanup` to apply a known cleanup.
- **Don't re-vet what `execute` autonomous mode already reviewed** — that loop reviews every task with `scrutinize` + `council`, so vetting its output just reviews twice. Use `vet` for changes made *outside* that loop (interactive-mode or hand-authored work, a PR) or as a deliberate fresh second opinion.

## Stages

Run in order. Finish each gate before the next.

1. **Scope**
   Fix what's under review: the working tree, a `--base <ref>` diff, or a PR. State it explicitly so both reviews look at the same thing.
   *Gate:* the artifact and its boundaries are pinned.

2. **Review — `scrutinize` ∥ `council`** (both read-only, run concurrently)
   On a wide or risky diff, **launch `council`'s cross-model CLI as a background top-level call and run `scrutinize` concurrently**; then **join at adjudication**, where `council` reconciles the two blind sets and returns **disagreement-first** findings + a "what the council changed" note. On a small/low-risk diff the overlap earns nothing — run them inline in either order. Add `/security-review` when the change touches untrusted input/authz/secrets; `/code-review` for a PR.
   *Gate:* `council` has returned the adjudicated findings (or has degraded — see below).

3. **Decide which to apply** (the gate)
   `council` already adjudicated, so vet's job is to *act on* the findings, not re-review them. **Don't apply blindly** — the caller decides: in interactive use, present the findings and ask which to fix — at five or more findings, or when `council` reported cross-model disagreement, deliver them as a `brief` page instead (findings as the decision table, disagreement-first, an evidence column drawn from the review) so the caller marks choices in the notes panel and copies the feedback back; fewer findings than that stay inline. When vet runs inside an autonomous loop, the controller decides and proceeds with no human halt and no page — the gate is "verify before applying," not "halt for a human"; never stall an autonomous run waiting on a prompt.
   *Gate:* the findings to act on are chosen.

4. **Fix loop**
   For the accepted findings, hand off — editing happens only here, after the decision gate, and never inline in the review stage:
   - **`receiving-code-review`** first — evaluate each accepted finding with rigor, push back with reasons where the reviewer (Claude or council) is wrong, then implement only what's valid.
   - If `receiving-code-review` or `slop-cleanup` isn't installed, apply its discipline directly here in the fix stage.
   - **`/simplify`** for quality/over-engineering cleanups; **`slop-cleanup`** *only* when the finding is AI-slop-shaped. If a host command (`/simplify`, `/security-review`, `/code-review`) is absent, note it was skipped and move on — don't reimplement a built-in you can't see, and never skip a *stage* because one tool is missing.
   - Confirm each fix by running it (`/run` where available) — read the real output and exit code before calling it green; then **`git-commit`**.
   - **Re-review** the fixed change (back through stage 2) until it comes back clean. If the findings amount to substantial rework, this isn't a fix loop — hand back to the `execute` workflow.
   *Gate:* the change re-reviews clean, or has been escalated back to `execute`.

## Degrade visibly

If no outside model is reachable, `council` degrades down its own ladder and says which. Vet then has only the in-family lens: it still runs, but the report must note that the cross-model property was lost.
