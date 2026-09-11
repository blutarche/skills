#!/usr/bin/env python3
"""Tests for build_tour.py against throwaway git repositories.

Run from the skill directory:
    python3 -m unittest scripts/test_build_tour.py
    python3 scripts/test_build_tour.py
"""

from __future__ import annotations

import json
import re
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
            "ran": [
                {"cmd": "python3 -m unittest", "cwd": ".", "exit": 0, "ok": True, "summary": "10 passed", "tree": "head"}
            ],
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
        spec = valid_spec(self.base, self.head)
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("build_tour: ok"), r.stdout)
        page = self.out.read_text(encoding="utf-8")
        # each focus item owns one grid cell, so it cannot wrap into the number column
        for item in spec["focus"]:
            self.assertIn(f"<li><span>{item}</span></li>", page)
        self.assertIn("Alpha returns 42 and delta arrives", page)
        self.assertIn("Notes gain a section", page)
        self.assertIn("def delta():", page)
        self.assertIn('<span class="sg">+</span>', page)
        self.assertNotIn("{{", page)
        self.assertNotIn(EM_DASH, page)
        # alpha.py's first hunk keeps context lines around the change, so the toggle stays visible
        self.assertIn(
            '<button type="button" class="btn" data-changed-only aria-pressed="false">'
            "Changed lines only</button>",
            page,
        )
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
        self.assertEqual(stats["linesShown"], 7)
        self.assertEqual(stats["linesChanged"], 12)
        self.assertEqual(stats["coveragePercent"], 58)
        self.assertIn("lines shown 7 / changed 12 (58%)", page)
        self.assertIn("lines shown 7 / changed 12 (58%)", r.stdout)
        self.assertNotIn("This tour shows", page)

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

    # ---------------------------------------------------------------- 11
    def test_prose_sanitizer_allowlist(self) -> None:
        """Sanitizing never fails the build; it strips. Six cases from the second adversarial
        pass, including the everythingElse[].why hole and the entity-obscured href bypass."""
        with self.subTest("script tag dropped, its text kept"):
            spec = valid_spec(self.base, self.head)
            spec["overview"] = "<p>Fine.</p><script>alert(1)</script>"
            r = self.build(spec)
            self.assertEqual(r.returncode, 0, r.stderr)
            page = self.out.read_text(encoding="utf-8")
            self.assertIn("<p>Fine.</p>alert(1)", page)

        with self.subTest("img onerror in everythingElse why is stripped"):
            spec = valid_spec(self.base, self.head)
            spec["everythingElse"][0]["why"] = "<img src=x onerror=alert(1)>"
            r = self.build(spec)
            self.assertEqual(r.returncode, 0, r.stderr)
            page = self.out.read_text(encoding="utf-8")
            self.assertNotIn("<img", page.lower())
            self.assertNotIn("onerror", page.lower())

        with self.subTest("entity-obscured javascript: href is dropped"):
            spec = valid_spec(self.base, self.head)
            spec["overview"] = '<a href="&#x6a;avascript:alert(1)">click</a>'
            r = self.build(spec)
            self.assertEqual(r.returncode, 0, r.stderr)
            page = self.out.read_text(encoding="utf-8")
            self.assertIn("<a>click</a>", page)
            self.assertNotIn("javascript", page.lower())

        with self.subTest("a hash href survives"):
            spec = valid_spec(self.base, self.head)
            spec["overview"] = '<a href="#ch-core">jump</a>'
            r = self.build(spec)
            self.assertEqual(r.returncode, 0, r.stderr)
            page = self.out.read_text(encoding="utf-8")
            self.assertIn('<a href="#ch-core">jump</a>', page)

        with self.subTest("config=prod is not an on*= handler"):
            spec = valid_spec(self.base, self.head)
            spec["overview"] = (
                "<p>Run it with <code>config=prod</code> and the <code>monkey=patch</code> trick.</p>"
            )
            r = self.build(spec)
            self.assertEqual(r.returncode, 0, r.stderr)
            page = self.out.read_text(encoding="utf-8")
            self.assertIn("config=prod", page)
            self.assertIn("monkey=patch", page)

        with self.subTest("base and form are stripped"):
            spec = valid_spec(self.base, self.head)
            spec["overview"] = (
                '<base href="https://evil.example/">'
                '<form action="https://evil.example/x" method="post"></form>'
            )
            r = self.build(spec)
            self.assertEqual(r.returncode, 0, r.stderr)
            page = self.out.read_text(encoding="utf-8")
            self.assertNotIn("<base", page.lower())
            self.assertNotIn("<form", page.lower())
            self.assertNotIn("evil.example", page)

    # ---------------------------------------------------------------- 12
    def test_low_coverage_notice(self) -> None:
        write(self.repo, "big.py", "\n".join(f"line_{i} = {i}" for i in range(1, 51)) + "\n")
        spec = valid_spec(self.base, "worktree")
        spec["everythingElse"].append({"path": "big.py", "why": "Bulk data, nothing to show line by line."})
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        stats = json.loads(self.stats.read_text(encoding="utf-8"))
        self.assertLess(stats["coveragePercent"], 30)
        page = self.out.read_text(encoding="utf-8")
        self.assertEqual(
            stats["linesUnshownInOpenedFiles"] + stats["linesUnshownInUnopenedFiles"],
            stats["linesChanged"] - stats["linesShown"],
        )
        # big.py never gets a hunk, so all of its lines land in the "listed by name only" bucket
        self.assertGreaterEqual(stats["linesUnshownInUnopenedFiles"], 50)
        self.assertIn(
            f'This tour shows {stats["coveragePercent"]}% of changed lines: '
            f'{stats["linesUnshownInOpenedFiles"]} lines not shown sit in files that are opened above, '
            f'{stats["linesUnshownInUnopenedFiles"]} in files listed by name only.',
            page,
        )

    # ---------------------------------------------------------------- 13
    def test_verify_row_missing_cwd_rejected(self) -> None:
        spec = valid_spec(self.base, self.head)
        del spec["verify"]["ran"][0]["cwd"]
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("verify.ran[0]", r.stderr)
        self.assertIn("cwd", r.stderr)

    # ---------------------------------------------------------------- 14
    def test_verify_ok_flag_colours_exit(self) -> None:
        spec = valid_spec(self.base, self.head)
        spec["verify"]["ran"].append(
            {"cmd": "flaky-check", "cwd": ".", "exit": 1, "ok": False, "summary": "failed once", "tree": "head"}
        )
        spec["verify"]["ran"].append(
            {"cmd": "no-ok-field", "cwd": ".", "exit": 0, "summary": "ran, ok unspecified", "tree": "head"}
        )
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")

        def chip_texts(cls: str) -> list[str]:
            # matches the literal class value, not the surrounding markup shape
            return [
                re.sub(r"<[^>]+>", "", m).strip()
                for m in re.findall(rf'class="{re.escape(cls)}">(.*?)</span>', page)
            ]

        self.assertEqual(chip_texts("chip exit-ok"), ["0"])
        self.assertEqual(chip_texts("chip exit-bad"), ["1"])
        self.assertEqual(chip_texts("chip"), ["0"])  # the ok-unspecified row gets the bare chip

        m = re.search(r'<td class="col-cwd">(.*?)</td>', page, re.S)
        self.assertIsNotNone(m)
        self.assertEqual(re.sub(r"<[^>]+>", "", m.group(1)).strip(), ".")

    # ---------------------------------------------------------------- 15
    def test_html_file_yields_no_entity_chips(self) -> None:
        write(self.repo, "page.html", "<html>\nfunction reallyLongName() {}\n</html>\n")
        spec = valid_spec(self.base, "worktree")
        spec["everythingElse"].append({"path": "page.html"})
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertNotIn("reallyLongName", page)

    # ---------------------------------------------------------------- 16
    def test_short_and_dollar_only_names_suppressed(self) -> None:
        js = "const $ = 1;\nconst $$ = 2;\nfunction raw() {}\nfunction process() {}\nfunction normalize() {}\n"
        write(self.repo, "util.js", js)
        spec = valid_spec(self.base, "worktree")
        spec["everythingElse"].append({"path": "util.js"})
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertNotIn("<li>$</li>", page)
        self.assertNotIn("<li>$$</li>", page)
        self.assertIn("<li>process</li>", page)

    # ---------------------------------------------------------------- 17
    def test_changed_only_toggle_hidden_when_no_context_rows(self) -> None:
        spec = valid_spec(self.base, self.head)
        spec["chapters"][0]["files"][0]["hunks"][0] = {"side": "new", "start": 2, "end": 2, "why": "The new return value."}
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn(
            '<button type="button" class="btn" data-changed-only aria-pressed="false" hidden>'
            "Changed lines only</button>",
            page,
        )


if __name__ == "__main__":
    unittest.main()
