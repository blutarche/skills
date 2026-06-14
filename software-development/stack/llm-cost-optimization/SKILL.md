---
name: llm-cost-optimization
description: A practical playbook for cutting token and dollar cost in production LLM pipelines without wrecking quality. Use when reducing the token or dollar cost of an LLM pipeline — prompt caching, model tiering, context trimming, or batching.
---

# LLM Cost Optimization

Cut the cost of an LLM pipeline by attacking it in order: **measure → cache → tier → trim → batch → cap → verify**. Each lever is independent; apply the ones that fit the workload. Do not optimize blind — find the expensive calls first, and prove savings after.

Prices, discounts, and thresholds change. Treat the vendor pricing pages (see References) as the source of truth and read live usage from the API rather than hardcoding fragile numbers.

## 1. Measure first

You cannot optimize what you have not measured. Before changing anything, find where the tokens and dollars actually go.

- **Count tokens before sending.** Anthropic exposes a free `count_tokens` endpoint (`POST /v1/messages/count_tokens`, returns `input_tokens`) that accepts the same payload as a real call, including system prompt, tools, images, and PDFs. Use it to size prompts and make routing decisions before paying for a completion.
- **Read usage off every response.** Both providers return token counts per call. Log them.
  - Anthropic `usage`: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`.
  - OpenAI `usage`: `prompt_tokens`, `completion_tokens`, and `prompt_tokens_details.cached_tokens`.
- **Attribute cost per call site.** Tag each call with its purpose (e.g. `extract`, `summarize`, `classify`) and aggregate. The 20% of call sites driving 80% of spend is where you spend your effort. Cheap, rare calls are not worth optimizing.
- **Find the dominant term.** Input-heavy (large context, long system prompt, re-sent history) and output-heavy (long generations) workloads call for different levers. Caching and context trimming attack input; output caps attack output.

Do not proceed to optimization until you know which calls cost the most and why.

## 2. Prompt caching

Caching lets a stable prefix be processed once and reused cheaply on later calls. It pays off when the **same large prefix repeats** across many requests within the cache lifetime.

**How it works (provider-specific):**

- **Anthropic — explicit breakpoints.** You mark cacheable content with `cache_control: { type: "ephemeral" }` (a small number of breakpoints per request). The cached prefix is built in a fixed order: `tools` → `system` → `messages`. A change anywhere invalidates that point and everything after it. There is a short default TTL (refreshed on each hit at no extra cost) and a longer extended-TTL option. Pricing is a multiplier on the base input rate: a cache *write* costs somewhat more than normal input, a cache *read* a small fraction of it — so a prefix read repeatedly is dramatically cheaper than re-sending it. There is a per-model minimum cacheable size; below it nothing is cached and **no error is raised** — check that `cache_creation_input_tokens`/`cache_read_input_tokens` are non-zero. Get the current breakpoint limit, TTLs, multipliers, and minimums from the docs.
- **OpenAI — automatic prefix caching.** No code changes; caching applies automatically once a prompt is long enough, matching on the longest common prefix. Cached input tokens are billed at a steep discount. Caches live for a short idle window. Read `usage.prompt_tokens_details.cached_tokens` to confirm hits; see the docs for the current length threshold and discount.

**Structure prompts to be cacheable:**

```
[ stable system prompt ]      ← cache these:
[ few-shot examples ]            same on every call
[ large shared context/docs ]
─────────────────────────────  ← breakpoint (Anthropic) / boundary
[ per-request variable input ]  ← keep volatile content LAST
```

Put everything stable at the **front** and everything that changes per request at the **back**. A single varying byte near the top (a timestamp, a request ID, a user name interpolated into the system prompt) breaks the whole prefix and you pay full price.

**When caching pays off:** repeated calls sharing a big prefix (same instructions + same large document across many questions; same few-shot block across a batch of extractions). **When it does not:** one-off calls, prefixes below the minimum size, or prefixes that legitimately change every call. The cache-write surcharge means caching a prefix used only once costs *more*, not less.

**Vercel AI SDK note:** with the Anthropic provider, set caching via `providerOptions.anthropic.cacheControl: { type: 'ephemeral' }` on a message content part (add `ttl: '1h'` for the extended TTL), and read `result.providerMetadata?.anthropic` for `cacheCreationInputTokens` / `cacheReadInputTokens`. OpenAI caching is automatic and needs no SDK flag.

## 3. Model tiering and routing

Frontier models cost several times more per token than small models and are slower. Most production traffic does not need the frontier model. Match model strength to task difficulty.

- **Classify, then route.** Use a small/cheap model (or plain code/heuristics) to judge difficulty or category first, then send only the hard cases to the frontier model. A regex, length check, or confidence threshold is free — use code for the routing decision, not a model, wherever code can answer.
- **Escalate, don't default high.** Start cases on the cheap model; escalate to the expensive one only on low confidence, parse failure, or a quality gate miss. For structured task-extraction and summarization, the small tier handles the bulk of well-formed inputs.
- **Know the tradeoff.** Vendors publish tiers spanning roughly an order of magnitude in price (a small/fast tier vs. a frontier reasoning tier), with latency tracking cost. Pull current per-tier prices from the pricing pages rather than memorizing them.

**Never downgrade a model without an eval.** Build a held-out set of representative inputs with known-good outputs, measure quality on both tiers, and only downgrade where the cheap tier clears your quality bar. A model swap that saves 60% but silently corrupts 5% of extractions is a regression, not a win.

## 4. Context discipline

The cheapest token is the one you never send. Re-sending unchanged bulk every call is the most common avoidable cost.

- **Trim history.** Summarize or window long conversation history instead of replaying the full transcript each turn. Keep a running summary plus the last few turns.
- **Retrieve, don't dump.** Fetch and inject only the snippets relevant to the current request rather than the whole corpus. Smaller, targeted context is cheaper *and* usually more accurate.
- **Stop re-sending unchanged blobs.** If a large document is constant across many calls, either cache it (section 2) or process it once and reuse the result. Resending a 50k-token document on every question is pure waste.
- **Prune redundancy.** Strip boilerplate, dead instructions, and duplicated examples from prompts. Verbose system prompts get paid for on every single call.

## 5. Batching and async

For work that is **not latency-sensitive** — bulk extraction, overnight summarization, evals, backfills — use the Batch API.

- **Anthropic Message Batches API:** asynchronous, at a substantial discount vs. synchronous pricing, with results returned within a stated window. Per-batch size/count limits apply — see the docs.
- **OpenAI Batch API:** submit a JSONL file of requests for a comparable discount, completed within a stated window.

Batching stacks with caching and tiering: run cheap-tier bulk extraction through the Batch API for compounding savings. Use it for any pipeline stage where a few hours of latency is acceptable. Reserve synchronous calls for user-facing, real-time paths.

## 6. Output controls

Output tokens are billed at a higher rate than input on most models, so shorter outputs save real money and latency.

- **Cap `max_tokens`/`max_output_tokens`** to the largest output you actually need. This bounds worst-case cost and stops runaways.
- **Demand structured, terse output.** Ask for JSON / specific fields / a fixed schema rather than prose. For extraction and summarization this both cuts tokens and simplifies parsing.
- **Use stop sequences** to end generation as soon as the useful part is done.
- **Avoid asking for restated input.** Don't make the model echo back the document or repeat the question; request only the new information.

## 7. Verify savings (and watch quality)

An optimization is not done until you have measured it.

- **Compare before vs. after** on the same representative sample: tokens per call and dollar cost per call, broken down by call site. Use logged `usage` fields, not estimates.
- **Confirm cache hits** are actually happening (`cache_read_input_tokens` > 0 on Anthropic; `cached_tokens` > 0 on OpenAI). A cache you think is working but isn't is a silent non-saving.
- **Re-run the quality eval** after any model downgrade or context trim. Track the quality metric alongside the cost metric — report both. A cost drop with an unmeasured quality drop is not a win.
- **Surface regressions loudly.** If quality fell, say so and roll back; don't bank the savings silently.

## Common mistakes

- Caching a prefix whose top changes every call (timestamp, request ID, interpolated user data) — the cache never hits and you pay the write surcharge.
- Putting variable content before stable content, breaking the cacheable prefix.
- Caching content below the per-model minimum size and assuming it cached — check the usage fields; no error is raised.
- Downgrading to a cheaper model with no eval, then shipping a silent quality regression.
- Using synchronous calls for bulk, non-urgent work that the Batch API would discount substantially.
- Re-sending a large unchanged document on every request instead of caching or reusing it.
- Optimizing rare, cheap calls while ignoring the few call sites that dominate spend.
- Leaving `max_tokens` uncapped, allowing runaway generations.
- Claiming savings from token counts alone without confirming cache hits or checking quality.

## References

- Anthropic — Prompt caching: https://docs.claude.com/en/docs/build-with-claude/prompt-caching
- Anthropic — Message Batches (batch processing): https://docs.claude.com/en/docs/build-with-claude/batch-processing
- Anthropic — Token counting: https://docs.claude.com/en/docs/build-with-claude/token-counting
- Anthropic — Models overview: https://docs.claude.com/en/docs/about-claude/models/overview
- Anthropic — Pricing: https://docs.claude.com/en/docs/about-claude/pricing
- OpenAI — Prompt caching: https://platform.openai.com/docs/guides/prompt-caching
- OpenAI — Batch API: https://platform.openai.com/docs/guides/batch
- OpenAI — Pricing: https://platform.openai.com/docs/pricing
- Vercel AI SDK — Anthropic provider (cache control & usage metadata): https://ai-sdk.dev/providers/ai-sdk-providers/anthropic
- Vercel AI SDK — Caching: https://ai-sdk.dev/docs/advanced/caching
