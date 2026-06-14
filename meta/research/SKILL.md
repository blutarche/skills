---
name: research
description: Research a question and answer it from sources fetched right now, with a citation behind every claim — never from memory, never a guess dressed as a fact. Use when the answer is version- or time-sensitive ("what's the current/latest X", "is this still true", "which version introduced Y", "what does the docs/spec say"), when a wrong answer is costly, or whenever you catch yourself about to state something you only "remember." When you've researched something important and want a *different* model to try to break it before you trust it, follow up with the `research-council` skill.
---

# Research

Answer from evidence you can point to, not from what you think you know. Your training has a cutoff and your memory blurs versions, dates, and details — so a confident-sounding recollection is exactly the kind of claim that turns out wrong. This skill is the discipline that prevents that: fetch the source, quote it, cite it, or say you couldn't.

## The Iron Law

```
NO TIME- OR VERSION-SENSITIVE CLAIM WITHOUT A SOURCE FETCHED THIS SESSION
```

If you have not opened a credible, current source for it in *this* session, you do not state it as fact. You either fetch it, or you label it **unverified** and say why. "I couldn't find a reliable source" is a better answer than a fluent guess — the guess is the failure mode this skill exists to kill.

What counts as time/version-sensitive (assume yes when unsure): latest/current versions, release dates, API signatures, pricing, defaults, "best practice today," who-owns-what, what-changed, whether something is deprecated, numbers and statistics, anything where reality moves.

## The loop

1. **State the question precisely.** Pin down what would actually answer it — a version number, a quote from a spec, a benchmark. Vague questions produce vague (uncheckable) answers.
2. **Fetch, don't recall.** Search and open primary sources. Read the page; don't infer its contents from the title or your memory of it. If a search result *summarizes* a source, open the source.
3. **Check the date.** Note when the source was published or last updated. A 2019 blog post answering a "current best practice" question is itself stale evidence — say so. Prefer the most recent authoritative source; when sources disagree, prefer the more recent *and* more authoritative.
4. **Quote the load-bearing bit.** Capture the exact sentence/snippet that supports the claim, plus the URL and the date you accessed it. If you can't quote it, you can't claim it.
5. **Separate fact from reading.** Distinguish "the source says X" (cited) from "so I infer Y" (your interpretation, labelled). Don't let interpretation inherit the source's authority.

## Source credibility

Prefer sources in this order, and name which tier a claim rests on when it matters:

1. **Primary / authoritative** — official docs, the spec, the source repo, release notes/changelog, the vendor's own pricing page, the law/standard itself.
2. **Reputable secondary** — maintainer blog posts, well-known references, papers, established outlets — useful for context, but verify specifics against primary.
3. **Community / informal** — Stack Overflow, forum posts, random blogs, AI-generated content — a lead to chase, never a final citation. Confirm against a primary source before stating as fact.

Two reputable independent sources beat one. A single forum post is a hypothesis, not a finding.

For technical topics (libraries, APIs, versions, repos, CVEs), read [references/technical-sources.md](references/technical-sources.md) for where the authoritative sources live and how to pin versions.

## Output

Lead with the answer, then make it checkable:

- **Every claim carries its evidence** — inline `[source](url)` (accessed YYYY-MM-DD), or a Sources list keyed to the claims. The reader must be able to land on the page that backs each statement.
- **Mark confidence** where it isn't obvious: *verified* (primary source, quoted) / *likely* (reputable secondary) / *unverified* (couldn't confirm — stated as such).
- **An "Unverified / possibly stale" section** whenever it applies — list what you could not confirm, what you're relying on memory for, and what a reader should double-check.
- **Sources** — URLs with access dates, and the source's own date where it matters.

## Red flags — stop and fetch

- You're about to write a version number, date, price, or API detail from memory.
- "As of my knowledge…", "I believe…", "typically…", "should be…" — these are tells that you're recalling, not citing.
- You're paraphrasing a source you found in search results but didn't open.
- A single low-tier source is carrying a load-bearing claim.
- The question is about "the latest" anything and your newest source predates this year.

## When not to use this

Stable, uncontested facts (arithmetic, settled definitions, how a well-known algorithm works) don't need a fetched citation — cite-everything theatre wastes everyone's time. The test is the Iron Law: *could this have changed, or am I unsure?* If yes, fetch. If genuinely no, just answer.
