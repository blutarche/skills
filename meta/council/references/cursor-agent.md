# Cursor CLI (`agent`, legacy `cursor-agent`)

**Resolve a non-Claude `--model` at runtime** — the Cursor CLI can run Claude models too, and a
council on a Claude model is not cross-family and defeats the mechanism. `COUNCIL_MODEL`, if
set, is used verbatim; otherwise `council_cursor_model` below resolves one from
`--list-models` at convene time, so nothing here rots when model names change.
Selected per [`selection.md`](selection.md).

## Resolving the binary

Cursor's official command is `agent`; `cursor-agent` is the legacy alias (same binary). Use
`agent` first, then `cursor-agent`; `--version` is run, not just `command -v`, so a PATH shim
that fails when executed is skipped. The snippets below call `council_cursor_bin`, which is
defined in [`selection.md`](selection.md) next to `council_candidates`; define it before using them.

## Resolving `--model`

POSIX-sh, no arrays — just grep/awk/head — safe under both bash and zsh:

```sh
council_cursor_model() {
  if [ -n "${COUNCIL_MODEL:-}" ]; then printf '%s\n' "$COUNCIL_MODEL"; return 0; fi
  # NOTE: `--list-models` output format was not verified on this box (unauthed) — if
  # resolution ever picks something odd, run `<cli> --list-models` yourself and eyeball it.
  bin="$(council_cursor_bin)" || return 1
  candidates="$("$bin" --list-models 2>/dev/null \
    | grep -E '^[A-Za-z0-9]' \
    | awk '{print $1}' \
    | grep -E '^[A-Za-z0-9][A-Za-z0-9._/-]*$' \
    | grep -viE 'claude|sonnet|opus|haiku')"
  [ -n "$candidates" ] || return 1   # no non-Claude id found → caller treats this as a model-selection failure
  for pat in gpt gemini grok; do
    m=$(printf '%s\n' "$candidates" | grep -i "$pat" | head -n1)
    [ -n "$m" ] && { printf '%s\n' "$m"; return 0; }
  done
  printf '%s\n' "$candidates" | head -n1   # any other non-Claude id
}
```

Headless requirements: `-p` = non-interactive print mode; `--mode ask` =
read-only Q&A (council never edits); **`--trust`** is required in `-p` mode or it refuses
on "Workspace Trust Required"; `--output-format text` (use `json` to parse structure).
Read stdout as the verdict.

## Invocation

Small artifact:

```sh
bin="$(council_cursor_bin)" || exit 1       # neither `agent` nor `cursor-agent` runs
model="$(council_cursor_model)" || exit 1   # no non-Claude id → model-selection failure, loop tries the next CLI
"$bin" -p --output-format text --mode ask --trust --model "$model" \
  "<artifact + attack brief>" < /dev/null
```

Large diff / PR-scale — unlike `codex exec`, the Cursor CLI does not ingest the artifact
from stdin; write it to a file and have the agent read it (file reads are allowed in
read-only `ask` mode):

```sh
# mktemp (not a fixed $TMPDIR/council.txt): a predictable name races concurrent runs; trap cleans up.
art="$(mktemp -t council.XXXXXX)"; trap 'rm -f "$art"' EXIT
{ printf '%s\n\n' "<attack brief>"; git diff <range>; } > "$art"
bin="$(council_cursor_bin)" || exit 1
model="$(council_cursor_model)" || exit 1   # no non-Claude id → model-selection failure, loop tries the next CLI
"$bin" -p --output-format text --mode ask --trust --model "$model" \
  "Read $art and review the artifact in it, per the brief at the top." < /dev/null
```

(`< /dev/null` keeps the durable "never leave stdin open" rule — the artifact goes in via
the file, not stdin. `ask` mode reads an absolute `mktemp` path fine.)

## Flags

- `--model <model>` — resolved at runtime, see above; never pin a literal id in this skill.
- `--trust` — trust the workspace without prompting; **required** in headless `-p` mode.
- `--mode ask` — read-only Q&A; keeps the sandbox read-only regardless of config.
- `--sandbox enabled|disabled` — explicit sandbox override; `ask` mode is read-only either way.
- `--output-format text|json` — verdict format.

## Install / auth / verify

Install via Cursor's installer and authenticate (`agent login`, or `CURSOR_API_KEY`),
then verify: `agent --version` (presence) and `agent --list-models` (auth —
"No models available for this account" means installed-but-not-authed). Note `--version`
alone returns 0 even when unauthed, so detection (selection.md) treats an auth error on
the first real call as a signal to fall through to the next provider.
