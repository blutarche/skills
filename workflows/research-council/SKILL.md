---
name: research-council
disable-model-invocation: true
description: Cross-examine a research answer with an outside model — citations, overclaims, staleness, missing angles.
---

# Research Council

This skill **reviews**: it points a second model at an answer with orders to break it. It does not fan out researchers or run a deep-research pipeline. It reviews research someone else gathered: the answer already in this conversation, a deep-research tool's output, or a pasted report. In a one-shot `/research /research-council` chain, you review what `research` just produced, in the *same turn*. If there's nothing in hand yet, do a quick [`research`](../../meta/research/SKILL.md) pass yourself and council that. This is still one turn. Never hand the user back to "go research and come back"; that round-trip is the experience to avoid.

## What to do

**Put the answer under review.** Take the synthesis and the sources behind it: whatever you're about to trust. If it carries no citations to check, run a quick `research` pass yourself to get them. Then continue in this same turn.

**Convene the council: an outside adversary.** A model from a *different family* than the one that wrote the answer must attack it. Tell it to attack rather than approve. It must re-check that each citation resolves and actually says what's claimed. It must challenge anything asserted past its evidence or gone stale. It must name the angles that are missing. It must adjudicate contradictions by which source is more authoritative. A rubber-stamp council is worse than none. It manufactures false confidence, so give it license to be harsh and default to skepticism.

> **Run your own citation review (fan out the fetch-checks) and convene the [`council`](../../meta/council/SKILL.md) skill alongside it.** Only the **per-citation** leg parallelizes. It asks two things: does this source resolve, and does it actually say what the claim attributes to it? So **fan that out: one read-only subagent per citation (or per cluster of related claims).** Each one **re-fetches its source and tests its own claim against it.**
>
> The **cross-citation** judgments are **global**. They are staleness ranking, contradiction between sources, whether several citations *together* carry one claim, and which angles are missing. Do them yourself in **one pass over the returned results**, never inside the fan-out.
>
> Run the fan-out concurrently with the council and meet at adjudication; `council` owns the convene, blindness, background-launch, and adjudication mechanics. Hand it the answer + sources, and let it run its own web searches where the chosen CLI has web access. Independent verification is the point. The reconcile-and-report below is the research-specific shape of that adjudication.

**Reconcile and report.** Treat each council challenge as a claim to verify, not an order to obey. The council can be confidently wrong, fabricated citation and all. Confirm every challenge against its source before accepting it. Reject the ones that don't hold, and say so out loud. Resolve a factual disagreement by evidence, not by who sounds surer. Each side names its source and how it got there. The weaker-sourced side concedes, but only after checking the other's source *itself*. Weigh authority and directness over mere recency (a faster-updating mirror doesn't beat the canonical source). Often the two are really answering different questions (e.g. "latest *published* version" vs "what the docs currently endorse"). Then state both and reframe. Don't crown one. Surface a conflict in the final answer only when authoritative sources are genuinely irreconcilable. This is rare. Give it in one line with a recommended pick. Deliver the corrected answer, and below it a short **"What the council changed"** section. It lists each challenge the council raised and how you resolved it (verified as-is, corrected, or downgraded), so the review is visible, not silent. When `brief` is installed, deliver the answer as a `brief` sheet of kind `research`. Put the answer in `state`. Put each claim with its source and result (verified, corrected, unverified) in the claims panel, and the council's challenges in a table. Reply in 3 lines at most. Use short sentences and common words; see `brief`'s `lib/voice.md` when installed. An invisible cross-examination earns no more trust than no review at all; showing what got caught is the proof it was real. Keep an explicit "unverified / still open" list. Include any gaps the council named. This skill names the hole and doesn't chase it; researching further is the user's call. Also note who reviewed (which model). If you fell back to your own, say so: a same-family review is weaker on the blind spots you share).

Don't pre-soften the answer to please the council. A smaller answer that's all true beats a broader one with one confident wrong claim buried in it.
