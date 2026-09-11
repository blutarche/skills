#!/usr/bin/env python3
"""Tests for build_tour.py against throwaway git repositories.

Run from the skill directory:
    python3 -m unittest scripts/test_build_tour.py
    python3 scripts/test_build_tour.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

BUILD = HERE / "build_tour.py"
EM_DASH = chr(0x2014)  # spelled by code point so this file stays free of it

ALPHA_BASE = """def alpha():
    return 1


def beta():
    return 2


def gamma():
    return 3
"""

ALPHA_HEAD = """def alpha():
    return 42


def beta():
    return 2


def gamma():
    return 3


def delta():
    return 4
"""

NOTES_BASE = """# Notes

Base note one.
Base note two.
Base note three.
Base note four.
"""

NOTES_HEAD = NOTES_BASE + "\n## Added section\n"


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=repo, capture_output=True, text=True
    )
    if out.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {out.stderr}")
    return out.stdout.strip()


def write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def make_repo(repo: Path) -> tuple[str, str]:
    """Base commit, then a feature commit that modifies, adds, and deletes. Returns (base, head)."""
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Walkthrough Test")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    write(repo, "alpha.py", ALPHA_BASE)
    write(repo, "keep.txt", "one\ntwo\n")
    write(repo, "notes.md", NOTES_BASE)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    write(repo, "alpha.py", ALPHA_HEAD)
    write(repo, "beta.py", 'def helper():\n    return "b"\n')
    write(repo, "notes.md", NOTES_HEAD)
    (repo / "keep.txt").unlink()
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "-m", "feature")
    head = git(repo, "rev-parse", "HEAD")
    return base, head


def valid_spec(base: str, head: str) -> dict:
    return {
        "title": "Delta lands next to alpha",
        "base": base,
        "head": head,
        "overview": "<p>A new function and a doc heading.</p>",
        "focus": ["<b><a href=\"#ch-core\">Core</a></b> holds the behaviour."],
        "chapters": [
            {
                "id": "core",
                "title": "Alpha returns 42 and delta arrives",
                "risk": "attention",
                "overview": "<p>The return value moves and a new function lands.</p>",
                "files": [
                    {
                        "path": "alpha.py",
                        "why": "The heart of the change.",
                        "hunks": [
                            {"side": "new", "start": 1, "end": 3, "why": "The new return value."},
                            {"side": "new", "start": 11, "end": 14},
                        ],
                    },
                    {"path": "beta.py"},
                ],
            },
            {
                "id": "docs",
                "title": "Notes gain a section",
                "risk": "safe",
                "overview": "<p>Documentation only.</p>",
                "files": [{"path": "notes.md", "hunks": [{"side": "new", "start": 7, "end": 8}]}],
            },
        ],
        "everythingElse": [{"path": "keep.txt", "why": "Dropped with its last caller."}],
        "verify": {
            "ran": [{"cmd": "python3 -m unittest", "exit": 0, "summary": "10 passed", "tree": "head"}],
            "manual": ["<b>Open the page.</b> Every chapter shows its hunks."],
        },
    }


class Walk(HTMLParser):
    """Parses the built page; the constructor raises on malformed markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)


class BuildTourTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.repo = self.dir / "repo"
        self.repo.mkdir()
        self.base, self.head = make_repo(self.repo)
        self.out = self.dir / "tour.html"
        self.fragment = self.dir / "tour.fragment.html"
        self.stats = self.dir / "stats.json"
        self.addCleanup(self.tmp.cleanup)

    def build(self, spec: dict, out: Path | None = None) -> subprocess.CompletedProcess:
        spec_path = self.dir / "review-tour.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(BUILD),
                "--spec",
                str(spec_path),
                "--repo-root",
                str(self.repo),
                "--out",
                str(out or self.out),
                "--fragment",
                str(self.fragment),
                "--data-out",
                str(self.stats),
            ],
            capture_output=True,
            text=True,
        )

    # ---------------------------------------------------------------- 1
    def test_valid_spec_builds(self) -> None:
        r = self.build(valid_spec(self.base, self.head))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("build_tour: ok"), r.stdout)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn("Alpha returns 42 and delta arrives", page)
        self.assertIn("Notes gain a section", page)
        self.assertIn("def delta():", page)
        self.assertIn('<span class="sg">+</span>', page)
        self.assertNotIn("{{", page)
        self.assertNotIn(EM_DASH, page)
        Walk().feed(page)

        frag = self.fragment.read_text(encoding="utf-8")
        self.assertTrue(frag.startswith("<title>"), frag[:40])
        for wrapper in ("<!doctype", "<html", "<body"):
            self.assertNotIn(wrapper, frag.lower())
        self.assertIn("Alpha returns 42 and delta arrives", frag)

        stats = json.loads(self.stats.read_text(encoding="utf-8"))
        self.assertEqual(stats["filesChanged"], 4)
        self.assertEqual(stats["filesPlaced"], 4)
        self.assertEqual(stats["everythingElse"], 1)
        self.assertEqual(stats["chapters"], 2)
        self.assertEqual(stats["hunksShown"], 3)
        self.assertEqual(stats["attentionChapters"], 1)
        self.assertEqual(stats["linesAdded"], 9)
        self.assertEqual(stats["linesRemoved"], 3)

    # ---------------------------------------------------------------- 2
    def test_changed_file_placed_nowhere(self) -> None:
        spec = valid_spec(self.base, self.head)
        spec["everythingElse"] = []
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("keep.txt", r.stderr)
        self.assertIn("no chapter claims", r.stderr)

    # ---------------------------------------------------------------- 3
    def test_placed_file_not_in_diff(self) -> None:
        spec = valid_spec(self.base, self.head)
        spec["everythingElse"].append({"path": "ghost.py"})
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ghost.py", r.stderr)
        self.assertIn("not in the diff", r.stderr)

    # ---------------------------------------------------------------- 4
    def test_range_without_a_changed_line(self) -> None:
        spec = valid_spec(self.base, self.head)
        spec["chapters"][0]["files"][0]["hunks"] = [{"side": "new", "start": 5, "end": 8}]
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("alpha.py", r.stderr)
        self.assertIn("5-8", r.stderr)
        self.assertIn("no changed line", r.stderr)

    # ---------------------------------------------------------------- 5
    def test_same_line_in_two_chapters(self) -> None:
        spec = valid_spec(self.base, self.head)
        spec["chapters"][1]["files"].append(
            {"path": "alpha.py", "hunks": [{"side": "new", "start": 2, "end": 3}]}
        )
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("shown twice", r.stderr)
        self.assertIn("alpha.py", r.stderr)

    # ---------------------------------------------------------------- 6
    def test_unknown_risk_value(self) -> None:
        spec = valid_spec(self.base, self.head)
        spec["chapters"][0]["risk"] = "spicy"
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown risk", r.stderr)

    # ---------------------------------------------------------------- 7
    def test_worktree_mode(self) -> None:
        write(self.repo, "alpha.py", ALPHA_HEAD.replace("return 42", "return 43"))
        write(self.repo, "gamma.txt", "fresh and untracked\n")
        spec = valid_spec(self.base, "worktree")
        spec["everythingElse"].append({"path": "gamma.txt"})
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn("return 43", page)
        self.assertIn("gamma.txt", page)
        self.assertIn("working tree", page)
        stats = json.loads(self.stats.read_text(encoding="utf-8"))
        self.assertEqual(stats["filesChanged"], 5)

    # ---------------------------------------------------------------- 8
    def test_deleted_file_on_the_old_side(self) -> None:
        spec = valid_spec(self.base, self.head)
        spec["everythingElse"] = []
        spec["chapters"][1]["files"].append(
            {"path": "keep.txt", "why": "Gone.", "hunks": [{"side": "old", "start": 1, "end": 2}]}
        )
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn('<span class="status st-D"', page)
        self.assertIn("keep.txt:1-2 (old side)", page)
        self.assertIn('<span class="sg">-</span>', page)

    # ---------------------------------------------------------------- 9
    def test_failed_build_leaves_the_out_file_untouched(self) -> None:
        ok = self.build(valid_spec(self.base, self.head))
        self.assertEqual(ok.returncode, 0, ok.stderr)
        before = self.out.read_text(encoding="utf-8")
        spec = valid_spec(self.base, self.head)
        spec["chapters"][0]["files"][0]["hunks"] = [{"side": "new", "start": 900, "end": 901}]
        bad = self.build(spec)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("outside the file", bad.stderr)
        self.assertEqual(self.out.read_text(encoding="utf-8"), before)

    # ---------------------------------------------------------------- 10
    def test_renamed_file(self) -> None:
        git(self.repo, "mv", "notes.md", "docs.md")
        write(self.repo, "docs.md", NOTES_HEAD + "renamed\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "--no-verify", "-m", "rename notes")
        head2 = git(self.repo, "rev-parse", "HEAD")
        spec = valid_spec(self.base, head2)
        spec["chapters"][1]["files"] = [
            {"path": "docs.md", "hunks": [{"side": "new", "start": 7, "end": 9}]}
        ]
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn("docs.md", page)
        self.assertIn("renamed", page)


if __name__ == "__main__":
    unittest.main()
