#!/usr/bin/env python3
"""Sort every changed file of a diff into reading tiers, and prove which ones the reader may skip.

A file the tour lets the reader skip either has a mechanical proof that a rule explains every
change in it (tier `matched`), or rests on the agent's word (tier `word`) and carries random
spot-check samples. A file a substitution group claims but its rule does not explain is
`flagged`: the build still succeeds, and the page puts it at the top of the reading list.

Stdlib only, Python 3.10 or newer. This module must not import build_tour: build_tour imports it.
"""

from __future__ import annotations

import difflib
import fnmatch
import math
import random
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WORKTREE = "worktree"
SKILL_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(SKILL_DIR / "lib"))
import pagelib  # noqa: E402  (needs sys.path set up above)

fail = pagelib.fail

TIERS = ("flagged", "read", "skim", "matched", "word")
DERIVED_IDS = ("moved", "line-ends", "everything-else", "deleted", "binary")
WORD_KINDS = ("generated", "lockfile", "bulk")
DERIVED_TITLE = {
    "moved": "Moved without a change",
    "line-ends": "Line endings and trailing spaces only",
    "everything-else": "Everything else",
    "deleted": "Deleted files",
    "binary": "Binary files",
}
DERIVED_TIER = {"moved": "matched", "line-ends": "matched", "everything-else": "word", "deleted": "word", "binary": "word"}
STATUS_REASON = {
    "A": "This file is new, so a rule cannot explain it.",
    "D": "This file is deleted, so a rule cannot explain it.",
    "C": "A copy adds code, so a rule cannot explain it.",
    "T": "The file type changed, so a rule cannot explain it.",
}
BINARY_REASON = "This file is binary, so a rule cannot explain it."
MISMATCH_REASON = "Applying the rule to the old file does not give the new file."
ENDINGS_REASON = "Applying the rule gives the new lines, but the line endings or the final newline differ."
MAX_BLOCKS = 5
SAMPLE_PAD, SAMPLE_MAX = 2, 40
SYMLINK_MODE = "120000"
# two trailing spaces are a hard line break in Markdown, so trailing space there is content
NO_LINE_ENDS_SUFFIXES = {".md", ".markdown"}


@dataclass
class Sample:
    path: str
    side: str  # "new" or "old"
    start: int  # 1-based, inclusive, on that side
    end: int


@dataclass
class Group:
    id: str  # spec group id, or one of DERIVED_IDS
    title: str
    kind: str  # substitution moved line-ends generated lockfile bulk everything-else deleted binary
    tier: str  # "matched" or "word"
    files: list[str]  # sorted, only files that ended up in this group
    rule: dict | None = None  # substitution only: {"from": str, "to": str, "regex": bool}
    why: str | None = None
    samples: list[Sample] = field(default_factory=list)


@dataclass
class Flag:
    path: str
    group: str  # id of the substitution group that claimed the file
    reason: str  # one plain sentence for the reader
    # (1-based head line of the first actual line, expected lines, actual lines); at most MAX_BLOCKS
    blocks: list[tuple[int, list[str], list[str]]]


@dataclass
class Digest:
    tiers: dict[str, str]  # every changed path -> one of TIERS
    groups: list[Group]  # spec groups in spec order, then non-empty derived groups in DERIVED_IDS order
    flags: list[Flag]  # in path order
    seed: int
    counts: dict[str, int]  # files per tier, every tier present
    lines: dict[str, int]  # changed lines: total, read (flagged/read/skim), matched, word, sampled


@dataclass
class RawEntry:
    old_mode: str
    new_mode: str
    old_sha: str
    new_sha: str  # all zeros when git has not hashed the working-tree file
    status: str  # one letter
    score: int | None  # similarity of a rename or copy


# ---------------------------------------------------------------- git


def git_bytes(root: Path, *args: str) -> bytes:
    out = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if out.returncode != 0:
        fail(f"git {' '.join(args)} failed: {out.stderr.decode('utf-8', 'replace').strip()}")
    return out.stdout


def raw_entries(root: Path, rev_args: list[str]) -> dict[str, RawEntry]:
    """Modes, blob shas, and rename scores keyed by new path. Untracked files are absent."""
    fields = git_bytes(root, "diff", "--raw", "-z", "-M", "--no-abbrev", *rev_args).split(b"\0")
    entries: dict[str, RawEntry] = {}
    i = 0
    while i < len(fields) and fields[i]:
        old_mode, new_mode, old_sha, new_sha, status = fields[i].decode("ascii")[1:].split(" ")
        n = 2 if status[:1] in "RC" else 1
        path = fields[i + n].decode("utf-8", "surrogateescape")
        entries[path] = RawEntry(old_mode, new_mode, old_sha, new_sha, status[:1], int(status[1:]) if status[1:] else None)
        i += 1 + n
    return entries


# ---------------------------------------------------------------- validation


def check_groups(spec: dict, chapter_ids: set[str]) -> None:
    groups = spec.get("groups", [])
    if not isinstance(groups, list):
        fail("groups must be a list")
    seen: set[str] = set()
    for i, g in enumerate(groups):
        if not isinstance(g, dict):
            fail(f"groups[{i}] must be an object")
        gid = g.get("id")
        if not isinstance(gid, str) or not gid:
            fail(f"groups[{i}] needs a non-empty string id")
        label = f"group {gid}"
        if gid in DERIVED_IDS:
            fail(f"{label}: the id {gid} is reserved for a derived group; pick another")
        if gid in chapter_ids:
            fail(f"{label}: a chapter has the same id; pick another")
        if gid in seen:
            fail(f"{label}: duplicate group id")
        seen.add(gid)
        if not isinstance(g.get("title"), str) or not g["title"]:
            fail(f"{label} is missing a title")
        globs = g.get("files")
        if not isinstance(globs, list) or not globs or not all(isinstance(x, str) and x for x in globs):
            fail(f"{label}: files must be a non-empty list of non-empty glob strings")

        if "kind" in g:
            kind = g["kind"]
            if kind not in WORD_KINDS:
                fail(f"{label}: unknown kind {kind!r}; use generated, lockfile, or bulk")
            if not isinstance(g.get("why"), str) or not g["why"]:
                fail(f"{label}: a {kind} group needs a why")
            extra = [k for k in ("from", "to", "regex") if k in g]
            if extra:
                fail(f"{label}: a {kind} group takes no {', '.join(extra)}")
            continue

        if "from" not in g:
            fail(f"{label}: give from and to for a rule, or kind and why for files that rest on the agent's word")
        if not isinstance(g["from"], str) or not g["from"]:
            fail(f"{label}: from must be a non-empty string")
        if not isinstance(g.get("to"), str):
            fail(f"{label}: to must be a string (it may be empty)")
        regex = g.get("regex", False)
        if not isinstance(regex, bool):
            fail(f"{label}: regex must be true or false")
        if "why" in g and not isinstance(g["why"], str):
            fail(f"{label}: why must be a string")
        if regex:
            try:
                pattern = re.compile(g["from"])
            except re.error as e:
                fail(f"{label}: from is not a valid regex: {e}")
            # a bad template only raises when sub() runs, so try it here rather than mid-classify
            try:
                pattern.sub(g["to"], "")
            except re.error as e:
                fail(f"{label}: to is not a valid replacement for the regex: {e}")


# ---------------------------------------------------------------- proofs


def check_rule(fd: Any, entry: RawEntry | None, rule: dict, gid: str) -> Flag | None:
    """A flag unless replaying the rule on the old file gives exactly the new file."""
    reason = STATUS_REASON.get(fd.status) or (BINARY_REASON if fd.binary else None)
    if reason is None and entry is not None and entry.old_mode != entry.new_mode:
        reason = f"The file mode changed from {entry.old_mode} to {entry.new_mode}."
    if reason is not None:
        return Flag(fd.path, gid, reason, [])

    if rule["regex"]:
        pattern, repl = re.compile(rule["from"]), rule["to"]
    else:
        to = rule["to"]
        pattern, repl = re.compile(re.escape(rule["from"])), (lambda _m: to)
    # exact text, not lines: a CRLF conversion or a changed final newline is a change the rule did not make
    expected_text = pattern.sub(repl, fd.old_text)
    if expected_text == fd.new_text:
        return None
    expected = pattern.sub(repl, "\n".join(fd.old_lines))
    if expected == "\n".join(fd.new_lines):
        return Flag(fd.path, gid, ENDINGS_REASON, [])
    # replay, not a line multiset: a guard moved below the write it guarded must not pass
    expected_lines = expected.split("\n") if expected else []
    ops = difflib.SequenceMatcher(None, expected_lines, fd.new_lines, autojunk=False).get_opcodes()
    blocks = [
        (j1 + 1, expected_lines[i1:i2], fd.new_lines[j1:j2]) for tag, i1, i2, j1, j2 in ops if tag != "equal"
    ]
    return Flag(fd.path, gid, MISMATCH_REASON, blocks[:MAX_BLOCKS])


def is_moved(root: Path, fd: Any, entry: RawEntry | None) -> bool:
    if fd.status != "R" or entry is None or entry.status != "R" or entry.score != 100:
        return False
    if entry.old_mode != entry.new_mode or entry.new_mode == SYMLINK_MODE:
        return False
    new_sha = entry.new_sha
    if not new_sha.strip("0"):
        new_sha = git_bytes(root, "hash-object", "--", fd.path).decode("ascii").strip()
    return new_sha == entry.old_sha


def is_line_ends(root: Path, rev_args: list[str], fd: Any, entry: RawEntry | None) -> bool:
    """True when only line endings or trailing spaces changed. Not `git diff -w`: that also
    ignores indentation, so it would call a Python dedent whitespace only."""
    if fd.status != "M" or fd.binary or Path(fd.path).suffix.lower() in NO_LINE_ENDS_SUFFIXES:
        return False
    if entry is None or entry.old_mode != entry.new_mode:
        return False
    args = ["diff", "--quiet", "--no-ext-diff", "--no-textconv", "--ignore-space-at-eol", "--ignore-cr-at-eol"]
    out = subprocess.run(["git", "-C", str(root), *args, *rev_args, "--", fd.path], capture_output=True)
    if out.returncode not in (0, 1):
        fail(f"git diff --quiet on {fd.path} failed: {out.stderr.decode('utf-8', 'replace').strip()}")
    return out.returncode == 0


# ---------------------------------------------------------------- samples


def runs(fd: Any) -> list[tuple[str, int, int]]:
    """Contiguous runs of added lines, or of removed lines when the file adds none."""
    if fd.binary:
        return []
    side, numbers = ("new", fd.added) if fd.added else ("old", fd.removed)
    out: list[tuple[str, int, int]] = []
    for n in sorted(numbers):
        if out and n == out[-1][2] + 1:
            out[-1] = (side, out[-1][1], n)
        else:
            out.append((side, n, n))
    return out


def widen(fd: Any, run: tuple[str, int, int]) -> Sample:
    side, start, end = run
    count = len(fd.new_lines if side == "new" else fd.old_lines)
    start = max(1, start - SAMPLE_PAD)
    return Sample(fd.path, side, start, min(count, end + SAMPLE_PAD, start + SAMPLE_MAX - 1))


def spot_checks(group: Group, files: dict[str, Any], rng: random.Random) -> list[Sample]:
    eligible = [p for p in group.files if runs(files[p])]
    n = min(len(eligible), 8, max(3, math.ceil(0.10 * len(group.files))))
    if n == 0:
        return []
    first = min(eligible, key=lambda p: (-(len(files[p].added) + len(files[p].removed)), p))
    picks = [first, *rng.sample([p for p in eligible if p != first], n - 1)]
    return [widen(files[p], rng.choice(runs(files[p]))) for p in picks]


def changed_in(fd: Any, s: Sample) -> int:
    changed = fd.added if s.side == "new" else fd.removed
    return sum(1 for n in range(s.start, s.end + 1) if n in changed)


# ---------------------------------------------------------------- classify


def classify(spec: dict, files: dict[str, Any], root: Path, base: str, head: str, seed: int) -> Digest:
    chapters = spec.get("chapters", [])
    check_groups(spec, {ch["id"] for ch in chapters})
    spec_groups = spec.get("groups", [])
    rev_args = [base] if head == WORKTREE else [f"{base}..{head}"]

    tiers: dict[str, str] = {}
    for ch in chapters:
        for f in ch.get("files", []):
            path = f["path"]
            if path in files:
                close = ch["risk"] in ("attention", "medium") or tiers.get(path) == "read"
                tiers[path] = "read" if close else "skim"
    chaptered = set(tiers)

    # a glob is dead only if it matches no changed path at all; chapter files are just skipped
    claimed: dict[str, list[str]] = {}
    for g in spec_groups:
        for glob in g["files"]:
            hits = [p for p in files if fnmatch.fnmatchcase(p, glob)]
            if not hits:
                fail(f"group {g['id']}: glob {glob} matches no changed file")
            for p in hits:
                if p in chaptered:
                    continue
                ids = claimed.setdefault(p, [])
                if g["id"] not in ids:
                    ids.append(g["id"])
    for p in sorted(claimed):
        if len(claimed[p]) > 1:
            fail(f"{p} matches groups {' and '.join(claimed[p])}; keep it in one")
    else_paths = {f["path"] for f in spec.get("everythingElse", [])}
    for p in sorted(else_paths & set(claimed)):
        fail(f"{p} is in everythingElse and matches group {claimed[p][0]}; keep it in one place")
    members = {g["id"]: sorted(p for p, ids in claimed.items() if ids[0] == g["id"]) for g in spec_groups}
    for g in spec_groups:
        if not members[g["id"]]:
            fail(f"group {g['id']}: every file its globs match is in a chapter; drop the group or those globs")

    raw = raw_entries(root, rev_args)
    groups: list[Group] = []
    flags: list[Flag] = []
    for g in spec_groups:
        paths = members[g["id"]]
        if "kind" in g:
            groups.append(Group(g["id"], g["title"], g["kind"], "word", paths, why=g["why"]))
            tiers.update((p, "word") for p in paths)
            continue
        rule = {"from": g["from"], "to": g["to"], "regex": g.get("regex", False)}
        kept: list[str] = []
        for p in paths:
            flag = check_rule(files[p], raw.get(p), rule, g["id"])
            if flag is None:
                kept.append(p)
                tiers[p] = "matched"
            else:
                flags.append(flag)
                tiers[p] = "flagged"
        groups.append(Group(g["id"], g["title"], "substitution", "matched", kept, rule=rule, why=g.get("why")))

    derived: dict[str, list[str]] = {gid: [] for gid in DERIVED_IDS}
    derived["everything-else"] = sorted(p for p in else_paths if p in files and p not in chaptered)
    loose: list[str] = []
    for p in sorted(set(files) - chaptered - set(claimed) - else_paths):
        fd, entry = files[p], raw.get(p)
        if is_moved(root, fd, entry):
            derived["moved"].append(p)
        elif is_line_ends(root, rev_args, fd, entry):
            derived["line-ends"].append(p)
        elif fd.status == "D":
            derived["deleted"].append(p)
        elif fd.binary:
            derived["binary"].append(p)
        else:
            loose.append(p)
    if loose:
        fail("changed files no chapter or group claims: " + ", ".join(loose))
    for gid in DERIVED_IDS:
        if derived[gid]:
            tier = DERIVED_TIER[gid]
            groups.append(Group(gid, DERIVED_TITLE[gid], gid, tier, derived[gid]))
            tiers.update((p, tier) for p in derived[gid])

    # one generator for the whole call, walked in group order, so a seed fixes every pick
    rng = random.Random(seed)
    sampled = 0
    for group in groups:
        if group.kind in ("substitution", "line-ends"):
            for p in group.files:
                first = runs(files[p])
                if first:
                    group.samples = [widen(files[p], first[0])]
                    break
        elif group.kind in WORD_KINDS or group.kind == "everything-else":
            group.samples = spot_checks(group, files, rng)
            sampled += sum(changed_in(files[s.path], s) for s in group.samples)

    size = {p: len(fd.added) + len(fd.removed) for p, fd in files.items()}
    return Digest(
        tiers=tiers,
        groups=groups,
        flags=sorted(flags, key=lambda f: f.path),
        seed=seed,
        counts={t: sum(1 for v in tiers.values() if v == t) for t in TIERS},
        lines={
            "total": sum(size.values()),
            "read": sum(size[p] for p, t in tiers.items() if t in ("flagged", "read", "skim")),
            "matched": sum(size[p] for p, t in tiers.items() if t == "matched"),
            "word": sum(size[p] for p, t in tiers.items() if t == "word"),
            "sampled": sampled,
        },
    )
