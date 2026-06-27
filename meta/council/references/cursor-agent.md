# cursor-agent — Cursor agent

**Pin a non-Claude `--model`** — cursor-agent will happily run Claude models
(`claude-opus-4-8-*` appear in `--list-models`), and a council on a Claude model is not
cross-family and defeats the mechanism. Pick a current GPT/Gemini/Grok id from
`--list-models` (e.g. `gpt-5.5-high`; `gpt-5` is **not** a valid id — model names rot, so
check the list). Selected per [`selection.md`](selection.md).

Headless requirements: `-p` = non-interactive print mode; `--mode ask` =
read-only Q&A (council never edits); **`--trust`** is required in `-p` mode or it refuses
on "Workspace Trust Required"; `--output-format text` (use `json` to parse structure).
Read stdout as the verdict.

## Invocation

Small artifact:

```sh
cursor-agent -p --output-format text --mode ask --trust --model gpt-5.5-high \
  "<artifact + attack brief>" < /dev/null
```

Large diff / PR-scale — unlike `codex exec`, cursor-agent does not ingest the artifact
from stdin; write it to a file and have the agent read it (file reads are allowed in
read-only `ask` mode):

```sh
# mktemp (not a fixed $TMPDIR/council.txt): a predictable name races concurrent runs; trap cleans up.
art="$(mktemp -t council.XXXXXX)"; trap 'rm -f "$art"' EXIT
{ printf '%s\n\n' "<attack brief>"; git diff <range>; } > "$art"
cursor-agent -p --output-format text --mode ask --trust --model gpt-5.5-high \
  "Read $art and review the artifact in it, per the brief at the top." < /dev/null
```

(`< /dev/null` keeps the durable "never leave stdin open" rule — the artifact goes in via
the file, not stdin. `ask` mode reads an absolute `mktemp` path fine.)

## Flags

- `--model <model>` — pin a **non-Claude** model; list valid ids with `--list-models`.
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
