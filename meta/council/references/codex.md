# codex — OpenAI Codex (GPT family)

Off-family by default. Codex's own sandbox defaults to `read-only`, which is enough to
read and review; it persists config to `~/.codex`. Selected per [`selection.md`](selection.md).

## Invocation

Small artifact (a decision, a short diff) — inline it; redirect `< /dev/null` or
`codex exec` **hangs waiting for stdin EOF**:

```sh
codex exec --skip-git-repo-check -c model_reasoning_effort="high" \
  "<artifact + attack brief>" < /dev/null
```

Large diff / PR-scale — pass via a **file on stdin** (the file's EOF prevents the hang
*and* sidesteps argv length + shell-quoting limits):

```sh
# mktemp (not a fixed $TMPDIR/council.txt): a predictable name races concurrent runs and can
# be read stale; trap removes it on exit.
art="$(mktemp -t council.XXXXXX)"; trap 'rm -f "$art"' EXIT
{ printf '%s\n\n' "<attack brief>"; git diff <range>; } > "$art"
codex exec --skip-git-repo-check -c model_reasoning_effort="high" \
  "Review the artifact provided on stdin, per the brief at the top of it." < "$art"
```

Read stdout as the verdict.

## Flags

- `-m <model>` — pin the model/family.
- `-c model_reasoning_effort="high"` — tier effort by stakes (`high` for a decision or a
  `vet` pass; lower for a frequent in-loop judge).
- `-s <mode>` — codex's own sandbox; leave at the `read-only` default (review never edits).

## Install / auth / verify

Install with `npm install -g @openai/codex`, then authenticate with `codex login`
(ChatGPT login or an API key). Verify: `codex --version` (presence) and one real
`codex exec ... < /dev/null` call (auth). Recipe verified end-to-end on codex-cli 0.141.0
(default model gpt-5.5, own sandbox `read-only`).
