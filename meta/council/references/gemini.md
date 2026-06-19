# gemini — Google Gemini

Google family — off-family by default. **Opt-in only** (`COUNCIL_CLI=gemini`): unlike the
codex and cursor-agent recipes, this one is **not verified end-to-end**, so it is kept out
of the default auto-detect order until someone confirms it on a real call.

> **Verify flags with `gemini --help` on the box.** This CLI's interface moves; the
> shape below is the rough form, not a guarantee — confirm before relying on it.

## Invocation

Non-interactive prompting is roughly:

```sh
gemini -p "<artifact + attack brief>"
```

For a large artifact, pass it on stdin or via a file the agent reads. Pin `--model` to a
Gemini model and run read-only. Read stdout as the verdict.

## Install / auth / verify

Install and authenticate per Google's Gemini CLI docs, then verify: `gemini --version`
(presence) and one real prompt call (auth).
