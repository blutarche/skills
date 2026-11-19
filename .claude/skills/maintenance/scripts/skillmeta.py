"""Shared SKILL.md discovery and frontmatter parsing for the maintenance scripts."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

SKIP_DIRS = {".git", "node_modules"}
KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(?:\s+(.*))?$")


def find_skill_files(repo: Path) -> list[Path]:
    found = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        if "SKILL.md" in files:
            found.append(Path(root) / "SKILL.md")
    return sorted(found)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return json.loads(value)
        except ValueError:
            return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, str], dict[str, int]]:
    """Return (values, 1-based line of each key). Empty dicts when there is no frontmatter."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, {}
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, {}
    values: dict[str, str] = {}
    where: dict[str, int] = {}
    i = 1
    while i < end:
        m = KEY_RE.match(lines[i])
        if not m:
            i += 1
            continue
        key, raw = m.group(1), (m.group(2) or "").strip()
        where[key] = i + 1
        j = i + 1
        cont = []
        while j < end and (lines[j].startswith((" ", "\t")) or not lines[j].strip()):
            cont.append(lines[j].strip())
            j += 1
        while cont and not cont[-1]:
            cont.pop()
        if raw[:1] in (">", "|"):
            values[key] = "\n".join(cont) if raw[0] == "|" else " ".join(c for c in cont if c)
        elif not raw:
            values[key] = " ".join(c for c in cont if c)
        elif raw[0] in "\"'" and (len(raw) < 2 or raw[-1] != raw[0]) and cont:
            values[key] = _unquote(raw + " " + " ".join(c for c in cont if c))
        else:
            values[key] = _unquote(raw) if not cont else " ".join([raw] + [c for c in cont if c])
        i = j
    return values, where


def load_repo_skills(repo: Path) -> dict[str, dict]:
    """Map skill name to {file, user_invoked, description}; first file wins on duplicate names."""
    skills: dict[str, dict] = {}
    for f in find_skill_files(repo):
        fm, _ = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        name = fm.get("name", "").strip() or f.parent.name
        skills.setdefault(name, {
            "file": f,
            "user_invoked": fm.get("disable-model-invocation", "").strip().lower() == "true",
            "description": fm.get("description", ""),
        })
    return skills


def repo_root() -> Path:
    # The skill lives at <repo>/.claude/skills/maintenance; walk up to the repo's install.conf.
    for p in Path(__file__).resolve().parents:
        if (p / "install.conf").is_file():
            return p
    return Path.cwd()
