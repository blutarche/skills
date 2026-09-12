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
HERMES_BIN=""
HERMES_CONFIG=""
HERMES_EXTERNAL_ROOT=""
HERMES_SELECTED=0
HERMES_ARG=0
HERMES_SOURCE_MARKER=".agent-skills-source"
HERMES_PYTHON="python3"

usage() {
  cat <<'EOF'
install.sh — link this repo's skills into the supported agents' skill dirs.

Only the top-level domains listed in install.conf are installed (default-deny).

Usage:
  ./install.sh              link configured domains into all targets (default)
  ./install.sh --claude     ~/.claude/skills only   (Claude Code)
  ./install.sh --codex      ~/.agents/skills only   (Codex CLI)
  ./install.sh --cursor     ~/.agents/skills only   (Cursor reads it)
  ./install.sh --copy       copy instead of symlink (edits won't sync back; dereferences a
                            skill's shared lib symlink so the copy is self-contained)
  ./install.sh --force      overwrite an existing FOREIGN skill of the same name
  ./install.sh --hermes     configure Hermes only (when Hermes is installed)
  ./install.sh --uninstall  remove only the links pointing back into this repo
  ./install.sh --prune-only remove only stale links this installer created; link nothing
  ./install.sh --dry-run    preview, change nothing
  ./install.sh -h | --help

Set SKILLS_TARGET_DIR to replace the target list with that single directory and
disable Hermes (testing only).
EOF
  exit "${1:-0}"
}

# --- parse args ----------------------------------------------------------------
declare -a TARGETS=()
COPY=0
DRY_RUN=0
FORCE=0
UNINSTALL=0
PRUNE_ONLY=0
PRUNED=0
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
    --hermes)    HERMES_SELECTED=1; SELECTED=1; HERMES_ARG=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --prune-only) PRUNE_ONLY=1 ;;
    --dry-run|-n) DRY_RUN=1 ;;
    -h|--help)   usage 0 ;;
    *) echo "unknown option: $1" >&2; usage 1 ;;
  esac
  shift
done

if [ -n "${SKILLS_TARGET_DIR:-}" ]; then
  TARGETS=("$SKILLS_TARGET_DIR")
  HERMES_SELECTED=0
  SELECTED=1
fi

if [ "$SELECTED" -eq 0 ]; then
  TARGETS=("$CLAUDE_DIR" "$AGENTS_DIR")
  HERMES_SELECTED=1
fi

# Hermes reads skills from ~/.hermes/skills/ plus configured external skill
# directories. Keep this repository as the source of truth instead of copying
# every skill into Hermes' managed directory. The small staging directory below
# contains only symlinks/copies for the allow-listed domains, so project-local
# .claude helpers are not accidentally exposed to Hermes.
detect_hermes() {
  [ "$HERMES_SELECTED" -eq 1 ] || return 0
  if ! HERMES_BIN="$(command -v hermes 2>/dev/null || true)"; then
    HERMES_BIN=""
  fi
  if [ -z "$HERMES_BIN" ]; then
    # Silent on the default run (most users have no Hermes); explicit --hermes
    # still reports it so a typo'd install is not mistaken for success.
    [ "$HERMES_ARG" -eq 1 ] && echo "  ! Hermes not found; skipping Hermes installation" >&2
    return 0
  fi

  HERMES_CONFIG="$("$HERMES_BIN" config path 2>/dev/null || true)"
  if [ -z "$HERMES_CONFIG" ]; then
    if [ -n "${HERMES_HOME:-}" ]; then
      HERMES_CONFIG="$HERMES_HOME/config.yaml"
    else
      HERMES_CONFIG="$HOME/.hermes/config.yaml"
    fi
  fi

  # Only canonicalize when the parent exists. A fresh Hermes install can point
  # at a parent that doesn't; `cd`-ing into it fails silently under `set -e`'s
  # command-substitution exemption, collapsing the path to "/config.yaml" and
  # HERMES_HOME to "/".
  config_parent="$(dirname "$HERMES_CONFIG")"
  resolved_parent="$(cd "$config_parent" 2>/dev/null && pwd || true)"
  if [ -n "$resolved_parent" ]; then
    HERMES_CONFIG="$resolved_parent/$(basename "$HERMES_CONFIG")"
  fi
  HERMES_HOME="$(dirname "$HERMES_CONFIG")"

  if [ -z "$HERMES_HOME" ] || [ "$HERMES_HOME" = "/" ]; then
    echo "  ! Hermes config path resolved to '$HERMES_HOME' (unsafe); skipping Hermes installation" >&2
    HERMES_EXTERNAL_ROOT=""
    return 0
  fi

  HERMES_EXTERNAL_ROOT="$HERMES_HOME/external-skills/$(basename "$REPO")"

  # Probe for a Python that can actually `import yaml`: the hermes wrapper's
  # own bin/ dir rarely ships a python3, so a bare fallback silently picks up
  # whatever system python3 is on PATH, which usually lacks PyYAML.
  declare -a py_candidates=(
    "$HERMES_HOME/hermes-agent/venv/bin/python"
    "$HERMES_HOME/hermes-agent/venv/bin/python3"
  )
  if [ -f "$HERMES_BIN" ]; then
    wrapper_python="$(grep -Im1 -Eo 'exec "[^"]*/python3?"' "$HERMES_BIN" 2>/dev/null \
      | sed -E 's/^exec "//; s/"$//' || true)"
    [ -n "$wrapper_python" ] && py_candidates+=("$wrapper_python")
  fi
  py_candidates+=("$(dirname "$HERMES_BIN")/python3" "python3")

  HERMES_PYTHON=""
  for cand in "${py_candidates[@]}"; do
    [ -n "$cand" ] || continue
    "$cand" -c 'import yaml' >/dev/null 2>&1 || continue
    HERMES_PYTHON="$cand"
    break
  done

  if [ -z "$HERMES_PYTHON" ]; then
    echo "  ! no Python with PyYAML found for Hermes (tried: ${py_candidates[*]}); skipping Hermes installation" >&2
    HERMES_EXTERNAL_ROOT=""
    return 0
  fi
}

detect_hermes

# Stale link: a symlink this installer created (points at $REPO or $REPO/*) whose
# target no longer exists — i.e. the skill was removed/renamed in the repo. Real
# directories, --copy'd trees, and symlinks pointing anywhere else are untouched.
prune_stale() { # dir
  local dir="$1" entry name tgt
  [ -d "$dir" ] || return 0
  for entry in "$dir"/*; do
    [ -L "$entry" ] || continue
    tgt="$(readlink "$entry" 2>/dev/null || true)"
    case "$tgt" in
      "$REPO"|"$REPO"/*)
        [ -e "$entry" ] && continue   # target still exists: live link, keep
        name="$(basename "$entry")"
        if [ "$DRY_RUN" -eq 1 ]; then
          echo "  would prune $name (stale link to removed skill)"
        else
          rm -f "$entry"
          echo "  pruned $name (stale link to removed skill)"
        fi
        PRUNED=$((PRUNED + 1)) ;;
    esac
  done
}

# --- prune-only: scan targets (and Hermes staging dir) for stale links, exit ---
if [ "$PRUNE_ONLY" -eq 1 ]; then
  for dest in "${TARGETS[@]:-}"; do
    [ -n "$dest" ] || continue
    [ -d "$dest" ] || continue
    echo "==> $dest"
    prune_stale "$dest"
  done

  if [ -n "$HERMES_EXTERNAL_ROOT" ] && [ -f "$HERMES_EXTERNAL_ROOT/$HERMES_SOURCE_MARKER" ] \
     && [ "$(<"$HERMES_EXTERNAL_ROOT/$HERMES_SOURCE_MARKER")" = "$REPO" ]; then
    echo "==> $HERMES_EXTERNAL_ROOT"
    prune_stale "$HERMES_EXTERNAL_ROOT"
  fi

  echo
  echo "Done: pruned $PRUNED stale link(s)."
  [ "$DRY_RUN" -eq 1 ] && echo "(dry run — nothing changed)"
  exit 0
fi

# --- uninstall: remove only links that point back into this repo ---------------
if [ "$UNINSTALL" -eq 1 ]; then
  removed=0
  for dest in "${TARGETS[@]:-}"; do
    [ -n "$dest" ] || continue
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

  if [ -n "$HERMES_EXTERNAL_ROOT" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "  would remove Hermes external skill registration for $HERMES_EXTERNAL_ROOT"
    else
      "$HERMES_PYTHON" "$REPO/scripts/manage-hermes-external-dir.py" \
        --config "$HERMES_CONFIG" \
        --external-dir "$HERMES_EXTERNAL_ROOT" \
        --action uninstall
      owner=""
      if [ -f "$HERMES_EXTERNAL_ROOT/$HERMES_SOURCE_MARKER" ]; then
        owner="$(<"$HERMES_EXTERNAL_ROOT/$HERMES_SOURCE_MARKER")"
      fi
      if [ "$owner" = "$REPO" ]; then
        rm -rf "$HERMES_EXTERNAL_ROOT"
        rmdir "$(dirname "$HERMES_EXTERNAL_ROOT")" 2>/dev/null || true
        echo "  removed Hermes external skill staging directory"
      else
        echo "  ! leaving Hermes staging directory: ownership marker is missing or differs" >&2
      fi
    fi
  fi
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
    cp -RL "$src" "$target"
    echo "  copied $name -> $target"
  else
    ln -sfn "$src" "$target"
    echo "  linked $name -> $target"
  fi
}

LINKED=0
for dest in "${TARGETS[@]:-}"; do
  [ -n "$dest" ] || continue
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
  prune_stale "$dest"
done

install_hermes() {
  [ -n "$HERMES_EXTERNAL_ROOT" ] || return 0

  if [ "$DRY_RUN" -eq 1 ]; then
    echo "==> $HERMES_EXTERNAL_ROOT (Hermes external skills)"
    for src in "${SKILL_DIRS[@]}"; do
      echo "  would link $(basename "$src") -> $HERMES_EXTERNAL_ROOT/$(basename "$src")"
    done
    echo "  would register $HERMES_EXTERNAL_ROOT in Hermes skills.external_dirs"
    return 0
  fi

  if [ -e "$HERMES_EXTERNAL_ROOT" ] || [ -L "$HERMES_EXTERNAL_ROOT" ]; then
    marker="$HERMES_EXTERNAL_ROOT/$HERMES_SOURCE_MARKER"
    owner=""
    if [ -f "$marker" ]; then
      owner="$(<"$marker")"
    fi
    if [ "$owner" != "$REPO" ] && [ "$FORCE" -eq 0 ]; then
      echo "  ! refusing Hermes staging directory: $HERMES_EXTERNAL_ROOT exists and isn't ours — pass --force to overwrite" >&2
      REFUSED=$((REFUSED + 1))
      return 0
    fi
    prune_stale "$HERMES_EXTERNAL_ROOT"
    rm -rf "$HERMES_EXTERNAL_ROOT"
  fi

  mkdir -p "$HERMES_EXTERNAL_ROOT"
  printf '%s' "$REPO" > "$HERMES_EXTERNAL_ROOT/$HERMES_SOURCE_MARKER"
  for src in "${SKILL_DIRS[@]}"; do
    name="$(basename "$src")"
    target="$HERMES_EXTERNAL_ROOT/$name"
    if [ "$COPY" -eq 1 ]; then
      cp -RL "$src" "$target"
      echo "  copied $name -> $target (Hermes)"
    else
      ln -s "$src" "$target"
      echo "  linked $name -> $target (Hermes)"
    fi
  done

  "$HERMES_PYTHON" "$REPO/scripts/manage-hermes-external-dir.py" \
    --config "$HERMES_CONFIG" \
    --external-dir "$HERMES_EXTERNAL_ROOT" \
    --action install
}

install_hermes

echo
target_count=0
for dest in "${TARGETS[@]:-}"; do
  [ -n "$dest" ] && target_count=$((target_count + 1))
done
[ -n "$HERMES_EXTERNAL_ROOT" ] && target_count=$((target_count + 1))
echo "Done: ${#SKILL_DIRS[@]} skill(s) into $target_count target(s)."
[ "$PRUNED" -gt 0 ] && echo "Pruned $PRUNED stale link(s)."
[ "$REFUSED" -gt 0 ] && echo "Refused $REFUSED existing foreign skill(s); re-run with --force to overwrite." >&2
[ "$DRY_RUN" -eq 1 ] && echo "(dry run — nothing changed)"
exit 0
