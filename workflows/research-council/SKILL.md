---
name: research-council
disable-model-invocation: true
description: Cross-examine a research answer with an outside model — citations, overclaims, staleness, missing angles.
---

# Research Council

This skill **reviews**: it points a second model at an answer with orders to break it. It does not fan out researchers or run a deep-research pipeline — it reviews research someone else gathered: the answer already in this conversation (in a one-shot `/research /research-council` chain, you review what `research` just produced, in the *same turn*), a deep-research tool's output, or a pasted report. If there's nothing in hand yet, do a quick [`research`](../../meta/research/SKILL.md) pass yourself and council that — still one turn. Never hand the user back to "go research and come back"; that round-trip is the experience to avoid.

## What to do

**Put the answer under review.** Take the synthesis and the sources behind it — whatever you're about to trust. If it carries no citations to check, run a quick `research` pass yourself to get them and continue — in this same turn.

**Convene the council — an outside adversary.** The answer must be attacked by a model from a *different family* than the one that wrote it, told to attack rather than approve: re-check that each citation resolves and actually says what's claimed, challenge anything asserted past its evidence or gone stale, name the angles that are missing, and adjudicate contradictions by which source is more authoritative. A rubber-stamp council is worse than none — it manufactures false confidence, so give it license to be harsh and default to skepticism.

> **Run your own citation review — fan out the fetch-checks — and convene the [`council`](../../meta/council/SKILL.md) skill alongside it.** Only the **per-citation** leg parallelizes — does this source resolve, and does it actually say what the claim attributes to it — so **fan that out: one read-only subagent per citation (or per cluster of related claims), each re-fetching its source and testing its own claim against it.**
>
> The **cross-citation** judgments — staleness ranking, contradiction between sources, whether several citations *together* carry one claim, which angles are missing — are **global**: do them yourself in **one pass over the returned results**, never inside the fan-out.
>
> Run the fan-out concurrently with the council and meet at adjudication; `council` owns the convene, blindness, background-launch, and adjudication mechanics. Hand it the answer + sources, and let it run its own web searches where the chosen CLI has web access — independent verification is the point. The reconcile-and-report below is the research-specific shape of that adjudication.

**Reconcile and report.** Treat each council challenge as a claim to verify, not an order to obey — the council can be confidently wrong, fabricated citation and all. Confirm every challenge against its source before accepting it, and reject — out loud — the ones that don't hold. Resolve a factual disagreement by evidence, not by who sounds surer: each side names its source and how it got there, and the weaker-sourced side concedes — but only after checking the other's source *itself*, weighing authority and directness over mere recency (a faster-updating mirror doesn't beat the canonical source). Often the two are really answering different questions (e.g. "latest *published* version" vs "what the docs currently endorse") — then state both and reframe, don't crown one. Surface a conflict in the final answer only when authoritative sources are genuinely irreconcilable — rarely, and in one line with a recommended pick. Deliver the corrected answer, and below it a short **"What the council changed"** section — each challenge it raised and how you resolved it (verified as-is, corrected, or downgraded) — so the review is visible, not silent. When `brief` is installed, deliver the answer as a `brief` sheet of kind `research`. Put the answer in `state`. Put each claim with its source and result (verified, corrected, unverified) in the claims panel, and the council's challenges in a table. Reply in 3 lines at most. Use short sentences and common words; see `brief`'s `lib/voice.md` when installed. An invisible cross-examination earns no more trust than no review at all; showing what got caught is the proof it was real. Keep an explicit "unverified / still open" list (including any gaps the council named — this skill names the hole, it doesn't chase it; researching further is the user's call), and note who reviewed (which model — if you fell back to your own, say so: a same-family review is weaker on the blind spots you share).

Don't pre-soften the answer to please the council. A smaller answer that's all true beats a comprehensive one with one confident wrong claim buried in it.
