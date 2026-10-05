#!/usr/bin/env python3
"""Voice-lint the prose of Markdown docs: scripts/lint-voice.py [FILE...].

Rules live in _lib/voice.md. Default files are DEFAULT_GLOBS under the repo root.
Prints `path:line: issues :: sentence` per issue; exit 1 if any.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_lib"))
import voice  # noqa: E402

DEFAULT_GLOBS = ["workflows/*/SKILL.md"]

START = re.compile(r"^\s*(#+\s|[-*+]\s|\d+[.)]\s|>)")


def blocks(path):
    """Yield (first line no, text) per paragraph or list item; skip frontmatter, code, tables."""
    lines = Path(path).read_text().splitlines()
    i, cur, start, inside = 0, [], 0, False
    if lines and lines[0].startswith("---"):
        i = 1
        while i < len(lines) and not lines[i].startswith("---"):
            i += 1
        i += 1

    def flush():
        nonlocal cur
        if cur:
            yield start, " ".join(cur)
        cur = []

    for n in range(i, len(lines)):
        line = lines[n]
        if line.lstrip().startswith("```"):
            yield from flush()
            inside = not inside
            continue
        if inside or line.lstrip().startswith("|") or not line.strip():
            yield from flush()
            continue
        if START.match(line) or not cur:
            yield from flush()
            start = n + 1
        cur.append(line.strip())
    yield from flush()


def rel(path):
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(path)


def main(argv):
    files = argv or [str(p) for g in DEFAULT_GLOBS for p in sorted(ROOT.glob(g))]
    total = 0
    for path in files:
        for n, text in blocks(path):
            text = re.sub(r"`[^`]*`", "X", text)
            text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
            text = re.sub(r"^\s*(#+|[-*+]|\d+[.)]|>)\s*", "", text).replace("**", "")
            for s in voice.sentences(text):
                iss = voice.issues(s, "prose")
                if iss:
                    total += 1
                    print(f"{rel(path)}:{n}: {'; '.join(iss)} :: {s[:100]}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
