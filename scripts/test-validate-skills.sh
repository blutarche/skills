#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATE_SRC="$SCRIPT_DIR/validate-skills.sh"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/skills-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

passed=0
total=0

setup_fixture() {
  local root="$1"
  mkdir -p "$root/scripts"
  cp "$VALIDATE_SRC" "$root/scripts/validate-skills.sh"
  printf '%s\n' 'testdomain' > "$root/install.conf"
}

run_validate() {
  bash "$1/scripts/validate-skills.sh" >/dev/null 2>&1
}

assert_exit() {
  local name="$1"
  local expect_ok="$2"
  local root="$3"

  total=$((total + 1))
  set +e
  run_validate "$root"
  local code=$?
  set -e

  local ok=0
  if [ "$expect_ok" -eq 1 ] && [ "$code" -eq 0 ]; then
    ok=1
  elif [ "$expect_ok" -eq 0 ] && [ "$code" -ne 0 ]; then
    ok=1
  fi

  if [ "$ok" -eq 1 ]; then
    echo "PASS  $name"
    passed=$((passed + 1))
  else
    echo "FAIL  $name (expected exit $([ "$expect_ok" -eq 1 ] && echo 0 || echo non-zero), got $code)"
  fi
}

# Run validate and check whether stderr warns about a skill missing from the README.
assert_readme_warning() {
  local name="$1" expect_warn="$2" root="$3" skill="$4" err warned=0

  total=$((total + 1))
  err="$(bash "$root/scripts/validate-skills.sh" 2>&1 >/dev/null || true)"
  case "$err" in *"no entry for '$skill'"*) warned=1 ;; esac

  if [ "$warned" -eq "$expect_warn" ]; then
    echo "PASS  $name"
    passed=$((passed + 1))
  else
    echo "FAIL  $name (expected warning=$expect_warn, got $warned)"
  fi
}

# Run validate; check that stderr has voice warnings, and that the count line matches.
# expect_voice: 1 = at least 2 voice warnings, 0 = none.
assert_voice_warning() {
  local name="$1" expect_voice="$2" root="$3" out err voices ok=0

  total=$((total + 1))
  set +e
  out="$(bash "$root/scripts/validate-skills.sh" 2>"$WORK/voice.err")"
  local code=$?
  set -e
  err="$(cat "$WORK/voice.err")"
  voices="$(printf '%s\n' "$err" | grep -c 'warn  voice' || true)"

  if [ "$code" -eq 0 ]; then
    if [ "$expect_voice" -eq 1 ] && [ "$voices" -ge 1 ] \
       && [ "$(printf '%s' "$out" | sed -n 's/.* \([0-9][0-9]*\) warning(s)/\1/p')" -ge 2 ]; then ok=1; fi
    if [ "$expect_voice" -eq 0 ] && [ "$voices" -eq 0 ]; then ok=1; fi
  fi

  if [ "$ok" -eq 1 ]; then
    echo "PASS  $name"
    passed=$((passed + 1))
  else
    echo "FAIL  $name (exit $code, voice lines=$voices, out: $out)"
  fi
}

write_skill() {
  local path="$1"
  local body="$2"
  mkdir -p "$(dirname "$path")"
  printf '%s\n' "$body" > "$path"
}

# 1. Valid skill: name matches folder, kebab-case, listed in README.
root="$WORK/valid-skill"
setup_fixture "$root"
write_skill "$root/testdomain/my-skill/SKILL.md" '---
name: my-skill
description: test skill
---
# my-skill
'
printf '%s\n' '# testdomain' '' '| Skill | Path |' '| my-skill | [my-skill](my-skill/SKILL.md) |' > "$root/testdomain/README.md"
assert_exit "valid skill passes validation" 1 "$root"

# 2. name: does not equal leaf folder name.
root="$WORK/name-mismatch"
setup_fixture "$root"
write_skill "$root/testdomain/wrong-folder/SKILL.md" '---
name: different-name
description: test skill
---
# wrong-folder
'
assert_exit "name mismatch fails validation" 0 "$root"

# 3. Duplicate leaf folder name at different paths.
root="$WORK/duplicate-leaf"
setup_fixture "$root"
write_skill "$root/testdomain/a/my-skill/SKILL.md" '---
name: my-skill
description: first
---
# my-skill
'
write_skill "$root/testdomain/b/my-skill/SKILL.md" '---
name: my-skill
description: second
---
# my-skill
'
assert_exit "duplicate leaf name fails validation" 0 "$root"

# 4. SKILL.md with no name: in frontmatter.
root="$WORK/missing-name"
setup_fixture "$root"
write_skill "$root/testdomain/no-name/SKILL.md" '---
description: test skill without name
---
# no-name
'
assert_exit "missing name in frontmatter fails validation" 0 "$root"

# 5. README entry for a longer sibling must not satisfy a shorter skill's README check.
root="$WORK/readme-suffix"
setup_fixture "$root"
write_skill "$root/testdomain/council/SKILL.md" '---
name: council
description: short name
---
# council
'
write_skill "$root/testdomain/research-council/SKILL.md" '---
name: research-council
description: longer sibling
---
# research-council
'
printf '%s\n' '# testdomain' '' '| [research-council](research-council/SKILL.md) | x |' > "$root/testdomain/README.md"
assert_readme_warning "README entry for research-council does not cover council" 1 "$root" "council"
assert_readme_warning "README entry for research-council still covers itself" 0 "$root" "research-council"

# 6. Voice lint: warns on workflow docs, never fails.
voice_fixture() {
  local root="$1" body="$2"
  setup_fixture "$root"
  printf '%s\n' 'workflows' > "$root/install.conf"
  mkdir -p "$root/_lib"
  cp "$SCRIPT_DIR/lint-voice.py" "$root/scripts/lint-voice.py"
  cp "$SCRIPT_DIR/../_lib/voice.py" "$SCRIPT_DIR/../_lib/voice-words.json" \
     "$SCRIPT_DIR/../_lib/pagelib.py" "$root/_lib/"
  write_skill "$root/workflows/demo/SKILL.md" "---
name: demo
description: test skill
---
# demo

$body
"
  printf '%s\n' '# workflows' '' '| [demo](demo/SKILL.md) | x |' > "$root/workflows/README.md"
}

voice_fixture "$WORK/voice-bad" 'This step is simple — do it now. We want the reader to understand every one of the many parts of this long sentence before they begin to work on the next part of the job.'
assert_voice_warning "voice lint warns without failing" 1 "$WORK/voice-bad"
voice_fixture "$WORK/voice-clean" 'Run the tests. Fix any failure.'
assert_voice_warning "clean workflow doc has no voice warnings" 0 "$WORK/voice-clean"

# A linter crash must show as a warning, not pass as clean.
voice_fixture "$WORK/voice-crash" 'Run the tests. Fix any failure.'
echo "raise RuntimeError('boom')" >> "$WORK/voice-crash/_lib/voice.py"
total=$((total + 1))
set +e
bash "$WORK/voice-crash/scripts/validate-skills.sh" >/dev/null 2>"$WORK/voice.err"
code=$?
set -e
if [ "$code" -eq 0 ] && grep -q 'warn  voice lint did not run' "$WORK/voice.err"; then
  echo "PASS  voice lint crash shows as a warning"; passed=$((passed + 1))
else
  echo "FAIL  voice lint crash shows as a warning (exit $code)"
fi

echo "$passed/$total assertions passed"
[ "$passed" -eq "$total" ]
