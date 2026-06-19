---
name: council
description: Convene an independent cross-model judge — a model of a different family (e.g. Codex/GPT, Gemini, or a Cursor agent pinned to a non-Claude model), whichever CLI is installed — to cross-examine an artifact (a decision, a diff, a document, or a research answer) and adjudicate its findings disbelieve-it-back. This is the cross-model *mechanism*; the caller brings the artifact and its own in-family review. Use via `vet` (code), `research-council` (research), `plan` (a design decision), or directly when you want a second opinion from a model that doesn't share your blind spots. It reviews; it never edits.
---

# Council — an independent cross-model judge

A conclusion you trust is one you haven't cross-examined. This skill is a *different* model — handed your work cold, with orders to break it, because it doesn't share the blind spot you never considered.

It is the **mechanism only**: convene the outside model and adjudicate. The *methodology* — what to look for — is the caller's: `scrutinize` for a code diff, citation-and-staleness checks for a research answer, plain critical reading for a decision. `vet`, `research-council`, `plan`, and autonomous `execute` all compose this skill so the cross-model machinery lives in one place.

## Convene the council — an outside adversary

Hand the artifact to a model of a *different family* and tell it to **attack, not approve**. The mechanism is provider-agnostic; what it requires is fixed:

- a **non-interactive, one-shot CLI** of a model family different than Claude (this is what makes it a real second opinion);
- run from the **top-level session**, with the **Claude Code Bash-tool sandbox disabled** for the call;
- fed the artifact **blind** (artifact + attack brief only), via argv for small inputs or a file/stdin for large ones, **never leaving stdin open**;
- read its stdout as the verdict.

The concrete per-tool invocation — which CLI to auto-detect, the exact flags, the stdin-vs-file handling — lives in [`references/selection.md`](references/selection.md) (the detection order and cross-family rule) and one file per CLI ([`codex.md`](references/codex.md), [`cursor-agent.md`](references/cursor-agent.md), [`gemini.md`](references/gemini.md)). Detect whichever cross-model CLI is installed (default order codex → cursor-agent; gemini opt-in via `COUNCIL_CLI`), try candidates in order falling through on auth/model failure; pass the chosen one the **raw adversarial prompt**, not a canned `review` subcommand (which would replace your brief with its own and assume a diff).

**Two sandboxes — disable the right one.** "Sandbox disabled" here means the **Claude Code Bash-tool sandbox** (`dangerouslyDisableSandbox: true`, or pre-allow via `/sandbox`) so the cross-model process can spawn and persist its own config (e.g. `~/.codex`). The sub-CLI's *own* sandbox is left **read-only** — enough to read and review, never to edit. A nested/background subagent has its harness sandbox-disable rejected *before the command runs*, so it can't launch the CLI (`bypassPermissions` doesn't fix it — verified); **make the call from the top level**, never a subagent.

**Cross-context — keep the council blind.** Hand over the artifact and its context, **never your preferred answer, your reasoning, or your own review's findings** — that's the anti-sycophancy lever; an anchored second model isn't independent. Your in-family findings meet the council's only at adjudication, never as the council's input. Give it license to be harsh; a rubber-stamp council manufactures false confidence. Tier reasoning effort by stakes (high for a decision or a `vet` pass; a frequent low-stakes caller, e.g. an autonomous in-loop judge, sets its own lower tier — see references for the per-tool flag), and pin a non-Claude model where the CLI can run several (a Cursor agent left on a Claude model is not cross-family).

## Run it concurrently — the convene is the long pole

The convene is a slow, top-level Bash call; the caller's own in-family review (`scrutinize` over a diff, a citation re-check over a research answer) is **independent** of it — the council is **blind** to those findings either way, so there is no reason to serialize the two. **Launch the convene asynchronously and run the in-family review while it works; join at adjudication**, where the two blind sets finally meet. Only the in-family leg may fan out into read-only subagents; the cross-model leg stays at the **top level** (above). For a trivial artifact where the convene is cheap, skip the overlap and run inline; it earns nothing.

## Adjudicate — disbelieve it back

The council convenes against *you*, so disbelieve it back. Reconcile its findings with the caller's in-family findings:

- **Every council point is a claim to verify, not an order.** A confident outsider is still wrong — check each against the actual code/source before accepting, and reject the ones that don't hold, **out loud**. Resolve disagreement by evidence, not by who sounds surer.
- **Lead with disagreement.** Where the two models part is the high-signal zone; where they agree is a *weak* signal (shared blind spots agree silently).
- Dedup overlapping findings, severity-rank the survivors, and show a short **"what the council changed"** list, so the cross-examination is visible.
- **STOP — report, don't edit.** Council returns the adjudicated verdict; it never edits. The caller acts, and "caller" is **mode-aware**: a human in interactive use, the **controller** in an autonomous loop. The gate is *verify-before-applying*, never a human halt — don't stall an autonomous run for a prompt.

## How callers use it

- **A decision** (no external artifact): state 2–4 concrete options (order randomized, your lean withheld), brief the council to "argue the strongest case against each and name the angle missed," then adjudicate → `My lean: X · Council (blind): Y · Where we differ + why · Recommendation`. Present a decision aid; don't adopt the council's view silently.
- **A diff / document / research answer:** the caller runs its *own* in-family review (`vet`→`scrutinize`; `research-council`→re-check citations and staleness; a plan→critical read) while the council **convenes concurrently** on the artifact **blind** (brief: "examine this independently; challenge every claimed property; find what a first reviewer would miss") — launch the convene in the background (see *Run it concurrently*) — then, once both are in, adjudicates the two sets. Council does not run the caller's methodology — it convenes and reconciles.

## When no cross-model CLI can be reached — degrade down a ladder, disclose the rung

If no cross-model CLI is reachable (none installed or authed, you're in a subagent, or the convene **wedged past its wall-clock bound** — every convene is time-bounded, never an unbounded wait), fall back to your own model — but say which rung you used. **Best:** run the caller's in-family review (`scrutinize`, etc.) in a **fresh subagent** (fresh context is what makes it a real *second* look). **If subagents are unavailable too:** run it **inline** — the weakest rung (same model, same context, least independent). Never fail the review for lack of isolation; just **say so** — name the rung and that the cross-model lens (and, if inline, the fresh-context lens) was lost, so the reader weights it accordingly.

## Prerequisites

At least one cross-model CLI installed *and authenticated* (`codex`, `cursor-agent`, or `gemini`); the call runs with the Claude Code Bash sandbox disabled (see *Two sandboxes*). Detection order and reachability checks are in [`references/selection.md`](references/selection.md); per-tool install/auth in [`codex.md`](references/codex.md), [`cursor-agent.md`](references/cursor-agent.md), [`gemini.md`](references/gemini.md). None installed is not an error — council degrades and discloses the rung.

## Rules

- **Honesty over completeness.** A smaller verdict that's all true beats a thorough one with a confident wrong claim in it.
