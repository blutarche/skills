"""Git facts for sheets: diff rows, `path:line` existence, commit existence. Read-only git
calls; the builder shows these instead of trusting an agent's own counts.

Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pagelib

REF_RE = re.compile(r"^(.+?):(\d+)(?:-(\d+))?$")


@dataclass
class FileRow:
    status: str
    path: str
    added: int | None
    removed: int | None
    old_path: str | None = None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True)


def _must(root: Path, *args: str) -> bytes:
    proc = _git(root, *args)
    if proc.returncode != 0:
        pagelib.fail(f"git {args[0]} failed: {proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def _split(raw: bytes) -> list[str]:
    return [p.decode("utf-8", "replace") for p in raw.split(b"\0") if p]


def diff_rows(root: Path, base: str, head: str) -> list[FileRow]:
    rev = [base] if head == "worktree" else [f"{base}..{head}"]
    parts = _split(_must(root, "diff", "--name-status", "-z", "-M", *rev))
    entries: list[tuple[str, str, str | None]] = []  # status, path, old path
    i = 0
    while i < len(parts):
        code = parts[i][0]
        if code in "RC":
            entries.append(("R" if code == "R" else "A", parts[i + 2], parts[i + 1] if code == "R" else None))
            i += 3
        else:
            entries.append((code if code in "AMD" else "M", parts[i + 1], None))
            i += 2

    counts: dict[str, tuple[int | None, int | None]] = {}
    toks = _must(root, "diff", "--numstat", "-z", "-M", *rev).split(b"\0")
    i = 0
    while i < len(toks):
        if not toks[i]:
            i += 1
            continue
        added, removed, path = toks[i].decode("utf-8", "replace").split("\t", 2)
        i += 1
        if not path:  # rename or copy: `added\tremoved\t\0old\0new\0`
            path = toks[i + 1].decode("utf-8", "replace")
            i += 2
        counts[path] = (None, None) if added == "-" else (int(added), int(removed))

    rows = []
    for st, path, old in entries:
        added, removed = counts.get(path, (None, None))
        rows.append(FileRow(st, path, added, removed, old))

    if head == "worktree":
        for path in sorted(_split(_must(root, "ls-files", "--others", "--exclude-standard", "-z"))):
            data = (root / path).read_bytes()
            added = None if b"\0" in data else len(data.splitlines())
            rows.append(FileRow("A", path, added, 0 if added is not None else None))
    return rows


def line_exists(root: Path, head: str, ref: str) -> bool:
    m = REF_RE.match(ref)
    if not m:
        return False
    path, first, last = m.group(1), int(m.group(2)), m.group(3)
    wanted = int(last) if last else first
    disk = root / path
    if head == "worktree" and disk.is_file():
        data = disk.read_bytes()
    else:
        proc = _git(root, "show", f"{'HEAD' if head == 'worktree' else head}:{path}")
        if proc.returncode != 0:
            return False
        data = proc.stdout
    return 1 <= first <= wanted <= len(data.splitlines())


def commit_exists(root: Path, sha: str) -> bool:
    return _git(root, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def project_name(root: Path) -> str | None:
    """Name of the main repo folder. The common git dir is shared by every worktree; `--show-toplevel` is not."""
    proc = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if proc.returncode != 0:
        return None
    common = Path(proc.stdout.decode("utf-8", "replace").strip())
    name = common.parent.name if common.name == ".git" else re.sub(r"\.git$", "", common.name)
    return name or None


def branch_name(root: Path) -> str | None:
    """The checked-out branch, `detached at <sha7>` on a detached head, None when git cannot say."""
    proc = _git(root, "symbolic-ref", "--short", "-q", "HEAD")
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.decode("utf-8", "replace").strip()
    sha = _git(root, "rev-parse", "--short=7", "HEAD")
    if sha.returncode != 0:
        return None
    return f"detached at {sha.stdout.decode().strip()}"
