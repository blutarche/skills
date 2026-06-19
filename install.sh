#!/usr/bin/env bash
set -euo pipefail

# install.sh — link this repo's skills into the skill dirs of every supported agent.
#
# SKILL.md is a cross-agent open standard, but each agent reads a different user-level
# dir. The union of two dirs covers all three (verified 2026-05-30; see README):
#   ~/.claude/skills   <- Claude Code            (reads ONLY this)
#   ~/.agents/skills   <- Codex CLI + Cursor      (Codex reads ONLY this; Cursor reads both)
#
# Only the top-level domains listed in install.conf are installed (default-deny): a new
# folder — e.g. a non-coding domain — won't leak into your coding agents until you add it
# there. Within each listed domain, every leaf folder containing a SKILL.md is linked; the
# leaf folder name becomes the skill's command name, so leaf names must be unique repo-wide.
#
# See usage() below, or run ./install.sh --help.

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude/skills"
AGENTS_DIR="$HOME/.agents/skills"   # Codex + Cursor
CONF="$REPO/install.conf"

usage() {
  cat <<'EOF'
install.sh — link this repo's skills into the supported agents' skill dirs.

Only the top-level domains listed in install.conf are installed (default-deny).

Usage:
  ./install.sh              link configured domains into all targets (default)
  ./install.sh --claude     ~/.claude/skills only   (Claude Code)
  ./install.sh --codex      ~/.agents/skills only   (Codex CLI)
  ./install.sh --cursor     ~/.agents/skills only   (Cursor reads it)
  ./install.sh --copy       copy instead of symlink (edits won't sync back)
  ./install.sh --force      overwrite an existing FOREIGN skill of the same name
  ./install.sh --uninstall  remove only the links pointing back into this repo
  ./install.sh --dry-run    preview, change nothing
  ./install.sh -h | --help
EOF
  exit "${1:-0}"
}

# --- parse args ----------------------------------------------------------------
declare -a TARGETS=()
COPY=0
DRY_RUN=0
FORCE=0
UNINSTALL=0
SELECTED=0

add_target() { # dedupe
  local d="$1" t
  for t in "${TARGETS[@]:-}"; do [ "$t" = "$d" ] && return; done
  TARGETS+=("$d")
}

while [ $# -gt 0 ]; do
  case "$1" in
    --claude)    add_target "$CLAUDE_DIR"; SELECTED=1 ;;
    --codex)     add_target "$AGENTS_DIR"; SELECTED=1 ;;
    --cursor)    add_target "$AGENTS_DIR"; SELECTED=1 ;;
    --copy)      COPY=1 ;;
    --force)     FORCE=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --dry-run|-n) DRY_RUN=1 ;;
    -h|--help)   usage 0 ;;
    *) echo "unknown option: $1" >&2; usage 1 ;;
  esac
  shift
done

if [ "$SELECTED" -eq 0 ]; then
  TARGETS=("$CLAUDE_DIR" "$AGENTS_DIR")
fi

# --- uninstall: remove only links that point back into this repo ---------------
if [ "$UNINSTALL" -eq 1 ]; then
  removed=0
  for dest in "${TARGETS[@]}"; do
    [ -d "$dest" ] || continue
    echo "==> $dest"
    for entry in "$dest"/*; do
      [ -L "$entry" ] || continue                      # only symlinks (skips --copy'd dirs)
      tgt="$(readlink "$entry" 2>/dev/null || true)"
      case "$tgt" in
        "$REPO"|"$REPO"/*)
          if [ "$DRY_RUN" -eq 1 ]; then
            echo "  would remove $(basename "$entry")"
          else
            rm -f "$entry"; echo "  removed $(basename "$entry")"
          fi
          removed=$((removed + 1)) ;;
      esac
    done
  done
  echo
  echo "Done: removed $removed link(s) belonging to this repo."
  [ "$DRY_RUN" -eq 1 ] && echo "(dry run — nothing changed)"
  exit 0
fi

# --- read install.conf: the allow-list of top-level domains --------------------
if [ ! -f "$CONF" ]; then
  echo "error: $CONF not found — it lists which top-level domains to install." >&2
  exit 1
fi

declare -a ALLOWED=()
while read -r domain _rest || [ -n "$domain" ]; do
  case "$domain" in ""|\#*) continue ;; esac          # skip blank + comment lines
  ALLOWED+=("$domain")
done < "$CONF"

if [ "${#ALLOWED[@]}" -eq 0 ]; then
  echo "error: $CONF lists no domains — nothing to install." >&2
  exit 1
fi

# --- discover skills under allowed domains (any depth); warn on skipped --------
declare -a SKILL_DIRS=()
declare -a SKIPPED=()
while IFS= read -r -d '' skill_md; do
  dir="$(dirname "$skill_md")"
  rel="${dir#"$REPO"/}"
  top="${rel%%/*}"
  ok=0
  for a in "${ALLOWED[@]}"; do [ "$a" = "$top" ] && { ok=1; break; }; done
  if [ "$ok" -eq 1 ]; then
    SKILL_DIRS+=("$dir")
  else
    seen=0
    for s in "${SKIPPED[@]:-}"; do [ "$s" = "$top" ] && { seen=1; break; }; done
    [ "$seen" -eq 0 ] && SKIPPED+=("$top")
  fi
done < <(find "$REPO" \
  -type d \( -name node_modules -o -name deprecated -o -name .git -o -name .omc -o -name .claude \) -prune -o \
  -type f -name SKILL.md -print0 | sort -z)

if [ "${#SKIPPED[@]}" -gt 0 ]; then
  for top in "${SKIPPED[@]}"; do
    echo "  ! skipping '$top/' — not listed in install.conf (add it there to install)" >&2
  done
fi

if [ "${#SKILL_DIRS[@]}" -eq 0 ]; then
  echo "No installable SKILL.md found under the domains in $CONF" >&2
  exit 1
fi

# --- detect leaf-name collisions (fail loud, before touching anything) ---------
declare -a NAMES=()
COLLISION=0
for src in "${SKILL_DIRS[@]}"; do
  name="$(basename "$src")"
  for prev in "${NAMES[@]:-}"; do
    if [ "$prev" = "$name" ]; then
      echo "error: duplicate skill name '$name' — leaf folder names must be unique." >&2
      echo "       offending path: $src" >&2
      COLLISION=1
    fi
  done
  NAMES+=("$name")
done
[ "$COLLISION" -eq 1 ] && { echo "Aborting; rename one of the colliding skills and re-run." >&2; exit 1; }

# --- link/copy into each target ------------------------------------------------
REFUSED=0
link_one() { # src target_dir
  local src="$1" dest_dir="$2" name target current
  name="$(basename "$src")"
  target="$dest_dir/$name"

  if [ "$DRY_RUN" -eq 1 ]; then
    echo "  would link $name -> $target"
    return
  fi

  # Refuse to clobber a skill we didn't create (foreign dir, or symlink elsewhere),
  # unless --force. Our own symlink (points back at $src) is safe to refresh.
  if [ -e "$target" ] || [ -L "$target" ]; then
    current="$(readlink "$target" 2>/dev/null || true)"
    if [ "$current" != "$src" ] && [ "$FORCE" -eq 0 ]; then
      echo "  ! refusing '$name': $target exists and isn't ours — pass --force to overwrite" >&2
      REFUSED=$((REFUSED + 1))
      return
    fi
    rm -rf "$target"
  fi

  if [ "$COPY" -eq 1 ]; then
    cp -R "$src" "$target"
    echo "  copied $name -> $target"
  else
    ln -sfn "$src" "$target"
    echo "  linked $name -> $target"
  fi
}

LINKED=0
for dest in "${TARGETS[@]}"; do
  # Safety: refuse to write into a dir that is itself a symlink back into this repo
  # (would scatter per-skill links inside the working copy).
  if [ -L "$dest" ]; then
    resolved="$(readlink -f "$dest" 2>/dev/null || readlink "$dest")"
    case "$resolved" in
      "$REPO"|"$REPO"/*)
        echo "error: $dest is a symlink into this repo ($resolved)." >&2
        echo "       remove it (rm \"$dest\") and re-run." >&2
        exit 1 ;;
    esac
  fi

  [ "$DRY_RUN" -eq 1 ] || mkdir -p "$dest"
  echo "==> $dest"
  for src in "${SKILL_DIRS[@]}"; do
    link_one "$src" "$dest"
    [ "$DRY_RUN" -eq 1 ] || LINKED=$((LINKED + 1))
  done
done

echo
echo "Done: ${#SKILL_DIRS[@]} skill(s) into ${#TARGETS[@]} target(s)."
[ "$REFUSED" -gt 0 ] && echo "Refused $REFUSED existing foreign skill(s); re-run with --force to overwrite." >&2
[ "$DRY_RUN" -eq 1 ] && echo "(dry run — nothing changed)"
exit 0
