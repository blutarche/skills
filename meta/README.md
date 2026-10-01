# meta

Domain-agnostic skills — about the *process of working with the agent* or general working techniques,
not tied to any one domain. Sources for adapted skills are in [`../CREDITS.md`](../CREDITS.md).

| Skill | What it does |
|-------|--------------|
| [`brief`](brief/SKILL.md) | Render the current session as one visual HTML page: chapters, a figure per chapter, decision and evidence tables. The wall-of-text replacement. |
| [`research`](research/SKILL.md) | Answer a single question from sources fetched this session, with a citation behind every claim — never from memory. The evidence-discipline engine. |
| [`grill-me`](grill-me/SKILL.md) | Relentlessly interview you about a plan or design until shared understanding, resolving each branch of the decision tree. Codebase-agnostic; the brownfield counterpart is the [`grill-with-docs`](../workflows/grill-with-docs/SKILL.md) workflow. |
| [`wat`](wat/SKILL.md) | Type it when the agent's last message didn't land. Re-pitches with the missing premise, in plain full English and `CONTEXT.md` vocabulary — suspends any terse output style for that one reply. User-invoked only (`/wat`). Adapted from mattpocock/skills `wait-what`. |
| [`council`](council/SKILL.md) | The cross-model judge *mechanism* — convene an outside model (a different family — e.g. Codex/GPT, Gemini, or a Cursor agent pinned to a non-Claude model) to cross-examine an artifact (decision, diff, document, research answer) and adjudicate disbelieve-it-back. Mechanism only: callers bring the artifact + their own in-family review. Composed by `vet` (code), `research-council` (research), and `plan` (decisions). |
| [`technical-writing`](technical-writing/SKILL.md) | Writing standard for docs, READMEs, RFCs, PR descriptions, and commit messages: pick the document type first, write to the reader, one thought per sentence (ASD-STE100), no sentence that reads two ways. User-invoked only (`/technical-writing`). |
| [`reflect`](reflect/SKILL.md) | Mine the current conversation for durable learnings: three parallel reviewer subagents (judgment, tooling, divergent) plus a synthesizer, then route each accepted learning to a concrete skill edit after your approval. User-invoked only (`/reflect`). Adapted from pstack `reflect`. |
| [`handoff`](handoff/SKILL.md) | Compact the current conversation into a handoff doc for a fresh agent to pick up. |
| [`writing-great-skills`](writing-great-skills/SKILL.md) | Reference for the *craft* of writing skills well — the vocabulary and principles behind predictability (invocation vs context load, the information hierarchy, leading words, the failure-mode catalog). User-invoked (`/writing-great-skills`); the design theory to edit skills toward; test the edited skill on a sample prompt. |
