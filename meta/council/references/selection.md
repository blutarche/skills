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
  if [ -n "${COUNCIL_CLI:-}" ]; then set -- "$COUNCIL_CLI"; else set -- codex cursor-agent; fi  # ${..:-} so set -u doesn't trip on an unset override
  for cli in "$@"; do
    "$cli" --version >/dev/null 2>&1 && echo "$cli"
  done
}

# convene with auth/model fallback:
verdict=""
for cli in $(council_candidates); do
  # run_council prints the verdict on stdout (rc 0); any non-zero — auth/model miss, timeout, or
  # the CLI erroring — means "no verdict from this CLI", so try the next. That makes `&& break`
  # correct.
  verdict=$(run_council "$cli" "$artifact_file") && break   # success → verdict on stdout
  verdict=""                                                 # any failure → try the next candidate
done
[ -n "$verdict" ] || : # none worked → degrade down the ladder (see SKILL.md)
```

Any non-success — an auth/model-selection miss, a **timeout**, or the CLI erroring — means this
candidate produced no verdict, so the loop clears `$verdict` and tries the next; if every
candidate fails, degrade down the ladder. `run_council` must **wall-clock-bound** its CLI call so
a convene can never wedge — the shape is below. `COUNCIL_CLI` is honored **strictly**: if set but unreachable or
unauthed, council degrades rather than silently falling back to another family. The auth check itself is per tool
(e.g. `cursor-agent --list-models` → "No models available for this account" means
installed-but-not-authed).

## `run_council` — bound the convene, emit the verdict

`run_council` wraps **the per-tool convene command** (from that CLI's own file — `codex.md`,
`cursor-agent.md`, …) so the loop above stays tool-agnostic and *every* CLI is bounded, not
just one. It must: run the command wall-clock-bounded — `timeout(1)` isn't portable (absent on
stock macOS), so use a background-kill watchdog that escalates **TERM→KILL** if the CLI ignores
TERM; capture stderr (never `2>/dev/null` — a swallowed error reads as a silent hang); emit the
verdict on **stdout** on success; and return non-zero on any failure (a timeout or a CLI error)
so the loop drops the candidate:

```bash
run_council() {                       # $1=cli, $2=artifact file → prints verdict on stdout, rc 0
  out="$(mktemp -t verdict.XXXXXX)"
  # `convene` = the CLI's own command (replace it — see that CLI's ref file, e.g. codex.md). It
  # reads $2 and handles its own stdin (codex needs `< /dev/null` or `< "$art"`), writing stdout:
  convene "$1" "$2" > "$out" 2>&1 &
  cpid=$!
  # bound it; the >/dev/null 2>&1 is load-bearing — without it the watchdog inherits the
  # verdict=$(…) capture pipe and a fast success blocks for the full COUNCIL_TIMEOUT. Keep it.
  { sleep "${COUNCIL_TIMEOUT:-300}"; kill -TERM "$cpid" 2>/dev/null
    sleep 5; kill -KILL "$cpid" 2>/dev/null; } >/dev/null 2>&1 &
  wpid=$!
  wait "$cpid"; rc=$?; kill "$wpid" 2>/dev/null            # reap the watchdog
  cat "$out"; rm -f "$out"; return "$rc"                   # stdout = verdict (rc 0); non-zero → loop tries next
}
```

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
