#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

passed=0
total=0
skipped=0

pass() { echo "PASS  $1"; passed=$((passed + 1)); total=$((total + 1)); }
fail() { echo "FAIL  $1"; total=$((total + 1)); }
skip() { echo "SKIP  $1"; skipped=$((skipped + 1)); }

# Derive the expected staged-skill count and the Hermes staging leaf name the
# same way install.sh does, so this test doesn't rot when a skill is added or
# the checkout directory is renamed.
declare -a allowed=()
while read -r domain _rest || [ -n "$domain" ]; do
  case "$domain" in ""|\#*) continue ;; esac
  allowed+=("$domain")
done < "$REPO/install.conf"

expected_skill_count=0
first_skill_name=""
while IFS= read -r -d '' skill_md; do
  dir="$(dirname "$skill_md")"
  rel="${dir#"$REPO"/}"
  top="${rel%%/*}"
  for a in "${allowed[@]}"; do
    if [ "$a" = "$top" ]; then
      expected_skill_count=$((expected_skill_count + 1))
      [ -z "$first_skill_name" ] && first_skill_name="$(basename "$dir")"
      break
    fi
  done
done < <(find "$REPO" \
  -type d \( -name node_modules -o -name deprecated -o -name .git -o -name .omc -o -name .claude \) -prune -o \
  -type f -name SKILL.md -print0)

hermes_staging_leaf="$(basename "$REPO")"
hermes_source_marker=".agent-skills-source"

# --- Hermes-dependent assertions -----------------------------------------------
# These need a Python that can `import yaml`, mimicking Hermes' colocated venv.
# HERMES_TEST_PYTHON overrides the probe; otherwise we look for the same venv
# convention install.sh's own interpreter probe checks first. When neither is
# available (e.g. CI with no Hermes installed anywhere), these SKIP instead of
# failing the run.
hermes_runtime_python="${HERMES_TEST_PYTHON:-$HOME/.hermes/hermes-agent/venv/bin/python}"
hermes_runtime_ok=0
if [ -x "$hermes_runtime_python" ] && "$hermes_runtime_python" -c 'import yaml' >/dev/null 2>&1; then
  hermes_runtime_ok=1
fi

if [ "$hermes_runtime_ok" -eq 1 ]; then
  hermes_bin="$TMPDIR/bin"
  mkdir -p "$hermes_bin"

  # HERMES_HOME/hermes-agent/venv/bin/python mirrors the real Hermes layout so
  # install.sh's interpreter probe finds it on its own — no HERMES_TEST_PYTHON
  # override, and deliberately no python3 next to the fake hermes binary, which
  # would let the probe pass without exercising real resolution. When the
  # runtime is a venv (has a pyvenv.cfg two levels up), symlink the whole venv
  # dir rather than just bin/python: a venv interpreter locates its
  # site-packages relative to its own invoked path, so a bare bin/python
  # symlink elsewhere can't find pyvenv.cfg/lib/ and silently loses PyYAML.
  hermes_home="$TMPDIR/hermes-home"
  mkdir -p "$hermes_home/hermes-agent"
  real_venv_root="$(cd "$(dirname "$hermes_runtime_python")/.." 2>/dev/null && pwd || true)"
  if [ -n "$real_venv_root" ] && [ -f "$real_venv_root/pyvenv.cfg" ]; then
    ln -s "$real_venv_root" "$hermes_home/hermes-agent/venv"
  else
    mkdir -p "$hermes_home/hermes-agent/venv/bin"
    ln -s "$hermes_runtime_python" "$hermes_home/hermes-agent/venv/bin/python"
  fi

  printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -euo pipefail' \
    'if [ "${1-}" = "config" ] && [ "${2-}" = "path" ]; then' \
    '  printf "%s" "${FAKE_HERMES_CONFIG_PATH:?}"' \
    '  exit 0' \
    'fi' \
    'exit 1' > "$hermes_bin/hermes"
  chmod +x "$hermes_bin/hermes"

  hermes_config="$hermes_home/config.yaml"
  printf '%s\n' 'skills:' '  external_dirs:' '    - /unrelated' > "$hermes_config"

  install_output="$(
    HOME="$TMPDIR/home" \
    PATH="$hermes_bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    FAKE_HERMES_CONFIG_PATH="$hermes_config" \
    bash "$REPO/install.sh" --hermes
  )"
  staging="$hermes_home/external-skills/$hermes_staging_leaf"
  [ -d "$staging" ] \
    && pass "Hermes staging directory is created" \
    || fail "Hermes staging directory is created"

  staged_count="$(find "$staging" -type l 2>/dev/null | wc -l | tr -d ' ')"
  [ "$staged_count" -eq "$expected_skill_count" ] \
    && pass "all allow-listed skills are staged for Hermes ($expected_skill_count)" \
    || fail "all allow-listed skills are staged for Hermes (expected $expected_skill_count, got $staged_count)"

  grep -Fq "$staging" "$hermes_config" \
    && pass "Hermes external directory is registered" \
    || fail "Hermes external directory is registered"
  grep -Fq '/unrelated' "$hermes_config" \
    && pass "unrelated Hermes external directory is preserved" \
    || fail "unrelated Hermes external directory is preserved"

  # Re-running is idempotent and must not duplicate the config entry.
  HOME="$TMPDIR/home" \
  PATH="$hermes_bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  FAKE_HERMES_CONFIG_PATH="$hermes_config" \
  bash "$REPO/install.sh" --hermes >/dev/null
  [ "$(grep -Fc "$staging" "$hermes_config")" -eq 1 ] \
    && pass "Hermes registration is idempotent" \
    || fail "Hermes registration is idempotent"

  # A foreign staging dir (marker missing or naming a different repo) is
  # refused without --force, and overwritten with it.
  rm -rf "$staging"
  mkdir -p "$staging"
  printf '%s' "/some/other/repo" > "$staging/$hermes_source_marker"
  touch "$staging/sentinel-foreign-file"

  HOME="$TMPDIR/home" \
  PATH="$hermes_bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  FAKE_HERMES_CONFIG_PATH="$hermes_config" \
  bash "$REPO/install.sh" --hermes >/dev/null 2>&1
  [ -f "$staging/sentinel-foreign-file" ] \
    && pass "foreign Hermes staging directory is refused without --force" \
    || fail "foreign Hermes staging directory is refused without --force"

  HOME="$TMPDIR/home" \
  PATH="$hermes_bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  FAKE_HERMES_CONFIG_PATH="$hermes_config" \
  bash "$REPO/install.sh" --hermes --force >/dev/null
  [ -d "$staging" ] && [ ! -f "$staging/sentinel-foreign-file" ] \
    && pass "foreign Hermes staging directory is overwritten with --force" \
    || fail "foreign Hermes staging directory is overwritten with --force"

  # Uninstall removes only this repo's staging and registration.
  HOME="$TMPDIR/home" \
  PATH="$hermes_bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  FAKE_HERMES_CONFIG_PATH="$hermes_config" \
  bash "$REPO/install.sh" --hermes --uninstall >/dev/null
  [ ! -e "$staging" ] \
    && pass "Hermes staging is removed on uninstall" \
    || fail "Hermes staging is removed on uninstall"
  grep -Fq '/unrelated' "$hermes_config" \
    && pass "unrelated Hermes directory survives uninstall" \
    || fail "unrelated Hermes directory survives uninstall"
  if grep -Fq "$staging" "$hermes_config"; then
    fail "repo Hermes registration is removed on uninstall"
  else
    pass "repo Hermes registration is removed on uninstall"
  fi
else
  skip "Hermes staging directory is created (no PyYAML-capable Hermes runtime; set HERMES_TEST_PYTHON to override)"
  skip "all allow-listed skills are staged for Hermes"
  skip "Hermes external directory is registered"
  skip "unrelated Hermes external directory is preserved"
  skip "Hermes registration is idempotent"
  skip "foreign Hermes staging directory is refused without --force"
  skip "foreign Hermes staging directory is overwritten with --force"
  skip "Hermes staging is removed on uninstall"
  skip "unrelated Hermes directory survives uninstall"
  skip "repo Hermes registration is removed on uninstall"
fi

# --- Hermes absent -------------------------------------------------------------
# The installer should skip Hermes without failing, and stay quiet about it on
# a default run (no --hermes) since most users have no Hermes installed.
hermes_absent_stderr="$(
  HOME="$TMPDIR/no-hermes-home" \
  PATH="/usr/bin:/bin:/usr/sbin:/sbin" \
  bash "$REPO/install.sh" --dry-run 2>&1 >/dev/null
)"
[ -z "$hermes_absent_stderr" ] \
  && pass "Hermes target is skipped silently when Hermes is absent" \
  || fail "Hermes target is skipped silently when Hermes is absent (stderr: $hermes_absent_stderr)"

# --- --copy stages real directories, not symlinks -------------------------------
copy_home="$TMPDIR/copy-home"
HOME="$copy_home" \
PATH="/usr/bin:/bin:/usr/sbin:/sbin" \
bash "$REPO/install.sh" --claude --copy >/dev/null
copy_target="$copy_home/.claude/skills"
copy_ok=1
[ -d "$copy_target" ] || copy_ok=0
for entry in "$copy_target"/*; do
  [ -L "$entry" ] && copy_ok=0
done
[ "$copy_ok" -eq 1 ] \
  && pass "--copy stages real directories, not symlinks" \
  || fail "--copy stages real directories, not symlinks"

# --- --force refusal on a per-agent target --------------------------------------
force_home="$TMPDIR/force-home"
mkdir -p "$force_home/.claude/skills/$first_skill_name"
touch "$force_home/.claude/skills/$first_skill_name/sentinel-foreign-file"

HOME="$force_home" \
PATH="/usr/bin:/bin:/usr/sbin:/sbin" \
bash "$REPO/install.sh" --claude >/dev/null 2>&1
[ -f "$force_home/.claude/skills/$first_skill_name/sentinel-foreign-file" ] \
  && pass "foreign skill directory is refused without --force" \
  || fail "foreign skill directory is refused without --force"

HOME="$force_home" \
PATH="/usr/bin:/bin:/usr/sbin:/sbin" \
bash "$REPO/install.sh" --claude --force >/dev/null
[ -L "$force_home/.claude/skills/$first_skill_name" ] \
  && [ ! -f "$force_home/.claude/skills/$first_skill_name/sentinel-foreign-file" ] \
  && pass "foreign skill directory is overwritten with --force" \
  || fail "foreign skill directory is overwritten with --force"

echo
echo "$passed/$total assertions passed ($skipped skipped)"
[ "$passed" -eq "$total" ]
