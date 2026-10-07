#!/usr/bin/env python3
"""Tests for gitfacts.py.

Run from this directory:
    python3 -m unittest test_gitfacts.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gitfacts  # noqa: E402


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def commit(root: Path, msg: str) -> None:
    git(root, "add", "-A")
    git(
        root, "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false",
        "commit", "-q", "-m", msg,
    )


class DiffRowsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        (self.root / "a.txt").write_text("1\n2\n3\n")
        (self.root / "gone.txt").write_text("x\n")
        commit(self.root, "base")
        (self.root / "a.txt").write_text("1\nTWO\n3\n4\n")
        (self.root / "gone.txt").unlink()
        (self.root / "new.txt").write_text("n\nn\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_worktree_rows_include_untracked(self):
        rows = gitfacts.diff_rows(self.root, "main", "worktree")
        self.assertEqual(
            [(r.status, r.path, r.added, r.removed) for r in rows],
            [("M", "a.txt", 2, 1), ("D", "gone.txt", 0, 1), ("A", "new.txt", 2, 0)],
        )

    def test_range_rows(self):
        git(self.root, "add", "a.txt", "new.txt", "gone.txt")
        commit(self.root, "change")
        rows = gitfacts.diff_rows(self.root, "main~1", "HEAD")
        self.assertEqual(sorted(r.path for r in rows), ["a.txt", "gone.txt", "new.txt"])

    def test_binary_counts_are_none(self):
        (self.root / "bin.dat").write_bytes(b"\0\1")
        rows = gitfacts.diff_rows(self.root, "main", "worktree")
        row = next(r for r in rows if r.path == "bin.dat")
        self.assertEqual((row.status, row.added, row.removed), ("A", None, None))

    def test_rename_is_one_row_with_old_path(self):
        (self.root / "dir one").mkdir()
        (self.root / "dir one" / "old name.txt").write_text("a\nb\nc\nd\n")
        commit(self.root, "add spaced")
        base = git(self.root, "rev-parse", "HEAD").strip()
        (self.root / "dir one" / "old name.txt").rename(self.root / "new name.txt")
        (self.root / "new name.txt").write_text("a\nb\nc\nd\ne\n")
        commit(self.root, "rename")
        rows = [r for r in gitfacts.diff_rows(self.root, base, "HEAD") if r.status == "R"]
        self.assertEqual(
            [(r.path, r.old_path, r.added, r.removed) for r in rows],
            [("new name.txt", "dir one/old name.txt", 1, 0)],
        )
        self.assertFalse([r for r in gitfacts.diff_rows(self.root, base, "HEAD") if r.status == "D" and "old" in r.path])

    def test_pure_rename_counts_zero(self):
        base = git(self.root, "rev-parse", "HEAD").strip()
        (self.root / "a.txt").write_text("1\n2\n3\n")
        (self.root / "a.txt").rename(self.root / "b.txt")
        commit(self.root, "mv")
        rows = {r.path: r for r in gitfacts.diff_rows(self.root, base, "HEAD")}
        self.assertEqual((rows["b.txt"].status, rows["b.txt"].old_path, rows["b.txt"].added), ("R", "a.txt", 0))

    def test_copy_is_an_added_row(self):
        base = git(self.root, "rev-parse", "HEAD").strip()
        (self.root / "copy.txt").write_text("1\n2\n3\n")
        (self.root / "a.txt").write_text("1\n2\n3\nfour\n")
        commit(self.root, "copy")
        rows = {r.path: r for r in gitfacts.diff_rows(self.root, base, "HEAD")}
        self.assertEqual((rows["copy.txt"].status, rows["copy.txt"].old_path), ("A", None))

    def test_line_exists_worktree(self):
        self.assertTrue(gitfacts.line_exists(self.root, "worktree", "a.txt:4"))
        self.assertFalse(gitfacts.line_exists(self.root, "worktree", "a.txt:9"))
        self.assertTrue(gitfacts.line_exists(self.root, "worktree", "a.txt:2-3"))
        self.assertFalse(gitfacts.line_exists(self.root, "worktree", "nope.txt:1"))
        self.assertFalse(gitfacts.line_exists(self.root, "worktree", "not a ref"))

    def test_line_exists_at_commit(self):
        self.assertFalse(gitfacts.line_exists(self.root, "HEAD", "a.txt:4"))
        self.assertTrue(gitfacts.line_exists(self.root, "HEAD", "a.txt:3"))

    def test_commit_exists(self):
        sha = git(self.root, "rev-parse", "HEAD").strip()
        self.assertTrue(gitfacts.commit_exists(self.root, sha[:7]))
        self.assertFalse(gitfacts.commit_exists(self.root, "deadbeef"))


if __name__ == "__main__":
    unittest.main()
