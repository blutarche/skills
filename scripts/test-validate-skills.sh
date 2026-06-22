#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATE_SRC="$SCRIPT_DIR/validate-skills.sh"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

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

write_skill() {
  local path="$1"
  local body="$2"
  mkdir -p "$(dirname "$path")"
  printf '%s\n' "$body" > "$path"
}

# 1. Valid skill: name matches folder, kebab-case, listed in README.
root="$TMPDIR/valid-skill"
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
root="$TMPDIR/name-mismatch"
setup_fixture "$root"
write_skill "$root/testdomain/wrong-folder/SKILL.md" '---
name: different-name
description: test skill
---
# wrong-folder
'
assert_exit "name mismatch fails validation" 0 "$root"

# 3. Duplicate leaf folder name at different paths.
root="$TMPDIR/duplicate-leaf"
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
root="$TMPDIR/missing-name"
setup_fixture "$root"
write_skill "$root/testdomain/no-name/SKILL.md" '---
description: test skill without name
---
# no-name
'
assert_exit "missing name in frontmatter fails validation" 0 "$root"

echo "$passed/$total assertions passed"
[ "$passed" -eq "$total" ]
