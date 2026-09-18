# cursor-agent — Cursor agent

**Resolve a non-Claude `--model` at runtime** — cursor-agent can run Claude models too, and a
council on a Claude model is not cross-family and defeats the mechanism. `COUNCIL_MODEL`, if
set, is used verbatim; otherwise `council_cursor_model` below resolves one from
`cursor-agent --list-models` at convene time, so nothing here rots when model names change.
Selected per [`selection.md`](selection.md).

## Resolving `--model`

POSIX-sh, no arrays — just grep/awk/head — safe under both bash and zsh:

```sh
council_cursor_model() {
  if [ -n "${COUNCIL_MODEL:-}" ]; then printf '%s\n' "$COUNCIL_MODEL"; return 0; fi
  # NOTE: `--list-models` output format was not verified on this box (unauthed) — if
  # resolution ever picks something odd, run `cursor-agent --list-models` yourself and eyeball it.
  candidates="$(cursor-agent --list-models 2>/dev/null \
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
model="$(council_cursor_model)" || exit 1   # no non-Claude id → model-selection failure, loop tries the next CLI
cursor-agent -p --output-format text --mode ask --trust --model "$model" \
  "<artifact + attack brief>" < /dev/null
```

Large diff / PR-scale — unlike `codex exec`, cursor-agent does not ingest the artifact
from stdin; write it to a file and have the agent read it (file reads are allowed in
read-only `ask` mode):

```sh
# mktemp (not a fixed $TMPDIR/council.txt): a predictable name races concurrent runs; trap cleans up.
art="$(mktemp -t council.XXXXXX)"; trap 'rm -f "$art"' EXIT
{ printf '%s\n\n' "<attack brief>"; git diff <range>; } > "$art"
model="$(council_cursor_model)" || exit 1   # no non-Claude id → model-selection failure, loop tries the next CLI
cursor-agent -p --output-format text --mode ask --trust --model "$model" \
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

Install via Cursor's installer and authenticate (`cursor-agent login`, or `CURSOR_API_KEY`),
then verify: `cursor-agent --version` (presence) and `cursor-agent --list-models` (auth —
"No models available for this account" means installed-but-not-authed). Note `--version`
alone returns 0 even when unauthed, so detection (selection.md) treats an auth error on
the first real call as a signal to fall through to the next provider.
