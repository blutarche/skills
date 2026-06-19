#!/usr/bin/env bash
set -euo pipefail

# validate-skills.sh — enforce this repo's skill invariants before install.sh would.
# Checks, over the top-level domains listed in install.conf:
#   1. every SKILL.md has a `name:` that equals its leaf folder name and is kebab-case
#   2. leaf folder names are unique repo-wide (install.sh maps them into one flat dir)
#   3. (warning only) each skill's leaf name appears in its area README.md
# Exit non-zero if any hard check (1 or 2) fails.

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF="$REPO/install.conf"
errors=0
warnings=0

[ -f "$CONF" ] || { echo "error: $CONF not found" >&2; exit 1; }

# Read allow-listed top-level domains (skip blanks + comments).
declare -a ALLOWED=()
while read -r domain _rest || [ -n "$domain" ]; do
  case "$domain" in ""|\#*) continue ;; esac
  ALLOWED+=("$domain")
done < "$CONF"

# Discover SKILL.md under allowed domains (mirror install.sh's prune list).
declare -a SKILL_MDS=()
while IFS= read -r -d '' f; do
  rel="${f#"$REPO"/}"; top="${rel%%/*}"
  for a in "${ALLOWED[@]}"; do [ "$a" = "$top" ] && { SKILL_MDS+=("$f"); break; }; done
done < <(find "$REPO" \
  -type d \( -name node_modules -o -name deprecated -o -name .git -o -name .omc -o -name .claude \) -prune -o \
  -type f -name SKILL.md -print0 | sort -z)

declare -a SEEN_NAMES=()
for f in "${SKILL_MDS[@]:-}"; do
  dir="$(dirname "$f")"
  folder="$(basename "$dir")"
  rel="${f#"$REPO"/}"
  name="$(awk -F':' '/^name:/{sub(/^[ \t]+/,"",$2); sub(/[ \t]+$/,"",$2); print $2; exit}' "$f")"

  if [ -z "$name" ]; then
    echo "FAIL  ${f#"$REPO"/}: no 'name:' in frontmatter" >&2; errors=$((errors+1))
  elif [ "$name" != "$folder" ]; then
    echo "FAIL  ${f#"$REPO"/}: name '$name' != folder '$folder'" >&2; errors=$((errors+1))
  fi
  if [ -n "$name" ] && ! printf '%s' "$name" | grep -Eq '^[a-z0-9]+(-[a-z0-9]+)*$'; then
    echo "FAIL  ${f#"$REPO"/}: name '$name' is not kebab-case" >&2; errors=$((errors+1))
  fi

  for prev in "${SEEN_NAMES[@]:-}"; do
    [ "$prev" = "$folder" ] && {
      echo "FAIL  duplicate leaf name '$folder' (second at ${dir#"$REPO"/})" >&2; errors=$((errors+1)); }
  done
  SEEN_NAMES+=("$folder")

  # Warning: leaf name should appear in the domain's README.
  # Match "<folder>/SKILL.md" (present in every README link) so a short name can't
  # false-match a longer sibling entry and silently suppress its own warning.
  readme="$REPO/${rel%%/*}/README.md"
  if [ -f "$readme" ] && ! grep -q "$folder/SKILL.md" "$readme"; then
    echo "warn  ${rel%%/*}/README.md: no entry for '$folder'" >&2; warnings=$((warnings+1))
  fi
done

count="${#SKILL_MDS[@]}"
echo "checked $count skill(s): $errors error(s), $warnings warning(s)"
[ "$errors" -eq 0 ]
