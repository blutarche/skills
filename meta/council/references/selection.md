# Cross-model CLI — selection

Council needs **one non-interactive, one-shot CLI from a model family different than
Claude**, run from the top-level session. This file decides *which* CLI; the per-tool
invocation lives in a file of its own:

- [`codex.md`](codex.md) — OpenAI Codex (GPT family)
- [`cursor-agent.md`](cursor-agent.md) — Cursor agent (pin a non-Claude model)
- [`gemini.md`](gemini.md) — Google Gemini (opt-in via `COUNCIL_CLI=gemini`; recipe unverified)

The durable principles — convene blind, attack-not-approve, top-level-only, the two
sandboxes, never leave stdin open, disbelieve-it-back — live in `SKILL.md` and do not
change when a CLI's flags do.

## Auto-detect, fixed order, overridable

Default auto-detect order: **codex → cursor-agent**. `gemini` is **opt-in only**
(`COUNCIL_CLI=gemini`) — its invocation is not yet verified end-to-end (see
[`gemini.md`](gemini.md)), so it must not be auto-selected silently. Override the whole
order with `COUNCIL_CLI=<codex|cursor-agent|gemini>`.

`--version` proves the binary runs, **not** that it's authed (`cursor-agent --version`
returns 0 while logged out; the real call then fails "Authentication required"). So
detection cannot end at one binary — it must yield the **ordered list of reachable
candidates**, and the convene step tries them in order, dropping any that fail at auth or
model selection, before degrading. Detection must also **run** the binary, not just
`command -v`: shims (e.g. Superset) keep a wrapper on PATH that only fails when executed
(`--version` exits non-zero, typically 127). Build the order with `set --`, not a
space-defaulted variable — zsh does **not** word-split an unquoted
`${COUNCIL_CLI:-codex cursor-agent}`, so that form collapses to one bogus token and
detection silently fails. This works in both bash and zsh:

```sh
council_candidates() {                       # prints reachable CLIs, in order, one per line
  if [ -n "$COUNCIL_CLI" ]; then set -- "$COUNCIL_CLI"; else set -- codex cursor-agent; fi
  for cli in "$@"; do
    "$cli" --version >/dev/null 2>&1 && echo "$cli"
  done
}

# convene with auth/model fallback:
verdict=""
for cli in $(council_candidates); do
  verdict=$(run_council "$cli" "$artifact_file") && break   # run_council: the per-CLI recipe; non-zero on auth/model error
  verdict=""                                                 # this candidate failed → try the next
done
[ -n "$verdict" ] || : # none worked → degrade down the ladder (see SKILL.md)
```

Fall through **only** on auth/model-selection errors — not on every non-zero exit, or a
genuinely broken primary CLI gets silently skipped and council looks healthy when it isn't.
Match the known auth/model failure signatures; on an unrecognized error, surface it rather
than swallowing it. `COUNCIL_CLI` is honored **strictly**: if set but unreachable or
unauthed, council degrades rather than silently falling back to another family. The auth check itself is per tool
(e.g. `cursor-agent --list-models` → "No models available for this account" means
installed-but-not-authed).

## Keep it cross-family

The whole point is a model that does not share Claude's blind spots. `codex` (GPT) and
`gemini` (Gemini) are off-family by default; **`cursor-agent` must be pinned to a
non-Claude `--model` (e.g. `gpt-5.5-high`)** — it can run Claude models too, and letting
it default to one silently defeats the mechanism.

## Raw prompt, not a canned `review` subcommand

Council convenes the model *blind* with its own adversarial brief, and works on
decisions / research answers / documents, not just diffs. A packaged reviewer bakes in
its own prompt and assumes a diff — it takes the brief out of council's hands. Always
feed the raw prompt, whichever CLI you pick.

## Prerequisites

- At least **one** of the CLIs above installed *and authenticated*. Install + auth is
  per tool — see that tool's file; in every case **verify** with `<cli> --version`
  (presence) and one real call (auth).
- The call needs the **Claude Code Bash-tool sandbox disabled** (`dangerouslyDisableSandbox`,
  or pre-allow via `/sandbox`) so the process can spawn and persist its config dir — see
  SKILL.md "two sandboxes." The sub-CLI's *own* sandbox stays read-only.
- None installed? Council still runs — it degrades down its ladder and discloses the rung.
