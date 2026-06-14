---
name: council
description: Convene an independent cross-model judge (Codex, a different model family) to cross-examine an artifact — a decision, a diff, a document, or a research answer — and adjudicate its findings disbelieve-it-back. This is the cross-model *mechanism*; the caller brings the artifact and its own in-family review. Use via `vet` (code), `research-council` (research), `plan` (a design decision), or directly when you want a second opinion from a model that doesn't share your blind spots. It reviews; it never edits.
---

# Council — an independent cross-model judge

A conclusion you trust is one you haven't cross-examined. One model believes its own work — it shares the blind spot it never considered. A *different* model, handed the artifact cold, doesn't. This skill is that second model, pointed at your work with orders to break it.

It is the **mechanism only**: convene the outside model and adjudicate. The *methodology* — what to look for — is the caller's: `scrutinize` for a code diff, citation-and-staleness checks for a research answer, plain critical reading for a decision. `vet`, `research-council`, `plan`, and autonomous `execute` all compose this skill so the cross-model machinery lives in one place.

## Convene the council — an outside adversary

Hand the artifact to a model of a *different family* and tell it to **attack, not approve**. In Claude Code the council is Codex. Shell out directly, from the **top-level session**:

    # small artifact (a decision, a short diff): inline it; no extra stdin, so close it
    codex exec --skip-git-repo-check -c model_reasoning_effort="high" "<artifact + attack brief>" < /dev/null

    # large diff / PR-scale: pass it via a FILE on stdin — avoids argv length + shell-quoting limits
    { printf '%s\n\n' "<attack brief>"; git diff <range>; } > "$TMPDIR/council.txt"
    codex exec --skip-git-repo-check -c model_reasoning_effort="high" "Review the artifact provided on stdin, per the brief at the top of it." < "$TMPDIR/council.txt"

read stdout as the verdict. **stdin rule:** with no extra input, redirect `< /dev/null` or `codex exec` **hangs waiting for stdin EOF**; to pass a large artifact, pipe it **from a file** (the file's EOF prevents the hang *and* sidesteps argv limits). Never leave stdin open.

**Two sandboxes — disable the right one.** "Sandbox disabled" here means the **Claude Code Bash-tool sandbox** (`dangerouslyDisableSandbox: true`, or pre-allow via `/sandbox`) so the `codex` process can spawn and persist to `~/.codex`. Codex's *own* sandbox (`-s`, default `read-only`) is left as-is — read-only is enough to read and review. A nested/background subagent has its harness sandbox-disable rejected *before the command runs*, so it can't launch Codex (`bypassPermissions` doesn't fix it — verified); **make the call from the top level**, never a subagent.

**Cross-context — keep the council blind.** Hand over the artifact and its context, **never your preferred answer, your reasoning, or your own review's findings** — that's the anti-sycophancy lever; an anchored second model isn't independent. Your in-family findings meet the council's only at adjudication, never as the council's input. Give it license to be harsh; a rubber-stamp council manufactures false confidence. Tier reasoning effort by stakes (`-c model_reasoning_effort="high"` for a decision or a `vet` pass; add `-m <model>` to pin the family; a frequent low-stakes caller, e.g. an autonomous in-loop judge, sets its own lower tier).

## Adjudicate — disbelieve it back

The council convenes against *you*, so disbelieve it back. Reconcile its findings with the caller's in-family findings:

- **Every council point is a claim to verify, not an order.** A confident outsider is still wrong — check each against the actual code/source before accepting, and reject the ones that don't hold, **out loud**. Resolve disagreement by evidence, not by who sounds surer.
- **Lead with disagreement.** Where the two models part is the high-signal zone; where they agree is a *weak* signal (shared blind spots agree silently).
- Dedup overlapping findings, severity-rank the survivors, and show a short **"what the council changed"** list, so the cross-examination is visible.
- **STOP — report, don't edit.** Council returns the adjudicated verdict; it never edits. The caller acts, and "caller" is **mode-aware**: a human in interactive use, the **controller** in an autonomous loop. The gate is *verify-before-applying*, never a human halt — don't stall an autonomous run for a prompt.

## How callers use it

- **A decision** (no external artifact): state 2–4 concrete options (order randomized, your lean withheld), brief the council to "argue the strongest case against each and name the angle missed," then adjudicate → `My lean: X · Council (blind): Y · Where we differ + why · Recommendation`. Present a decision aid; don't adopt the council's view silently.
- **A diff / document / research answer:** the caller first runs its *own* in-family review (`vet`→`scrutinize`; `research-council`→re-check citations and staleness; a plan→critical read), then convenes the council **blind on the artifact** (brief: "examine this independently; challenge every claimed property; find what a first reviewer would miss"), then adjudicates the two sets. Council does not run the caller's methodology — it convenes and reconciles.

## When Codex can't be reached — degrade down a ladder, disclose the rung

If Codex isn't reachable (you're in a subagent, or it isn't installed), fall back to your own model — but say which rung you used. **Best:** run the caller's in-family review (`scrutinize`, etc.) in a **fresh subagent** (fresh context is what makes it a real *second* look). **If subagents are unavailable too:** run it **inline** — the weakest rung (same model, same context, least independent). Never fail the review for lack of isolation; just **say so** — name the rung and that the cross-model lens (and, if inline, the fresh-context lens) was lost, so the reader weights it accordingly.

## Rules

- **Honesty over completeness.** A smaller verdict that's all true beats a thorough one with a confident wrong claim in it.
