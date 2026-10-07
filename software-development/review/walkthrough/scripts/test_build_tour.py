#!/usr/bin/env python3
"""Tests for build_tour.py against throwaway git repositories.

Run from the skill directory:
    python3 -m unittest scripts/test_build_tour.py
    python3 scripts/test_build_tour.py
"""

from __future__ import annotations

import html
import hashlib
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

import build_tour  # noqa: E402  (needs sys.path set up above)

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

    def add_pr_lens(self, spec: dict, views: list[dict] | None = None) -> None:
        views = views or [
            {
                "id": "architecture-overview",
                "title": "Architecture overview",
                "lens": "architecture",
                "children": [],
            }
        ]
        head_sha = git(self.repo, "rev-parse", "HEAD") if spec["head"] == "worktree" else spec["head"]
        graph = {
            "schemaVersion": "0.2.0",
            "kind": "graph",
            "title": "Test change",
            "lenses": list(dict.fromkeys(view["lens"] for view in views)),
            "provenance": {"base": {"sha": spec["base"]}, "head": {"sha": head_sha}},
            "flows": [{"id": "flow"}] if any(view["lens"] == "data-flow" for view in views) else [],
            "views": views,
        }
        lens_dir = self.dir / "pr-lens"
        lens_dir.mkdir(exist_ok=True)
        write(self.dir, "pr-lens/drawn.graph.json", json.dumps(graph))
        assets = []

        def flatten(items: list[dict]) -> list[dict]:
            return [item for view in items for item in [view, *flatten(view.get("children", []))]]

        for view in flatten(views):
            for theme in ("light", "dark"):
                svg = (
                    f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="320" '
                    f'viewBox="0 0 640 320" role="img" aria-label="{view["title"]} {theme}">'
                    f'<defs><pattern id="dots" width="8" height="8" patternUnits="userSpaceOnUse">'
                    f'<circle cx="1" cy="1" r="1"/></pattern></defs>'
                    f'<rect width="640" height="320" fill="url(#dots)"/>'
                    f'<text x="20" y="40">{view["title"]} {theme}</text></svg>'
                )
                raw = svg.encode()
                digest = hashlib.sha256(raw).hexdigest()[:32]
                path = f'{view["id"]}-{theme}-{digest}.svg'
                write(self.dir, f"pr-lens/{path}", svg)
                assets.append(
                    {
                        "id": f'{view["id"]}-{theme}',
                        "lens": view["lens"],
                        "theme": theme,
                        "view": view["id"],
                        "mediaType": "image/svg+xml",
                        "contentHash": digest,
                        "bytes": len(raw),
                        "width": 640,
                        "height": 320,
                        "animated": False,
                        "path": path,
                    }
                )
        manifest = {
            "schemaVersion": "0.2.0",
            "kind": "render-manifest",
            "graph": {
                "headSha": head_sha,
                "contentHash": hashlib.sha256(
                    json.dumps(graph, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
                ).hexdigest()[:32],
            },
            "renderer": {"name": "pr-lens", "version": "test"},
            "assets": assets,
        }
        write(self.dir, "pr-lens/manifest.json", json.dumps(manifest))
        spec["prLens"] = {
            "graph": "pr-lens/drawn.graph.json",
            "manifest": "pr-lens/manifest.json",
        }
        if spec["head"] == "worktree":
            spec["prLens"]["worktreeHash"] = build_tour.revision_hash(self.repo, spec["base"])

    def build(
        self, spec: dict, out: Path | None = None, with_pr_lens: bool = True
    ) -> subprocess.CompletedProcess:
        if with_pr_lens and "prLens" not in spec:
            self.add_pr_lens(spec)
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

    def test_pr_lens_is_required(self) -> None:
        r = self.build(valid_spec(self.base, self.head), with_pr_lens=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("prLens", r.stderr)

    def test_pr_lens_embeds_every_view_with_theme_pairs(self) -> None:
        spec = valid_spec(self.base, self.head)
        self.add_pr_lens(
            spec,
            [
                {
                    "id": "system",
                    "title": "System boundary",
                    "lens": "architecture",
                    "children": [
                        {
                            "id": "components",
                            "title": "Changed components",
                            "lens": "architecture",
                            "children": [],
                        }
                    ],
                },
                {
                    "id": "request-flow",
                    "title": "Request flow",
                    "lens": "data-flow",
                    "children": [],
                },
            ],
        )
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertEqual(page.count('<figure class="pr-lens-view"'), 3)
        embedded = re.findall(r"data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)", page)
        self.assertEqual(len(set(embedded)), 6)
        for title in ("System boundary", "Changed components", "Request flow"):
            self.assertIn(title, page)

    def test_pr_lens_rejects_unsafe_svg(self) -> None:
        spec = valid_spec(self.base, self.head)
        self.add_pr_lens(spec)
        manifest_path = self.dir / spec["prLens"]["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        asset = manifest["assets"][0]
        unsafe = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        (manifest_path.parent / asset["path"]).write_bytes(unsafe)
        asset["bytes"] = len(unsafe)
        asset["contentHash"] = hashlib.sha256(unsafe).hexdigest()[:32]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unsafe SVG", r.stderr)

    def test_pr_lens_allows_url_in_inert_svg_label(self) -> None:
        spec = valid_spec(self.base, self.head)
        self.add_pr_lens(spec)
        manifest_path = self.dir / spec["prLens"]["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        asset = manifest["assets"][0]
        labelled = (
            b'<svg xmlns="http://www.w3.org/2000/svg" '
            b'aria-label="Requests to https://api.example.com"></svg>'
        )
        (manifest_path.parent / asset["path"]).write_bytes(labelled)
        asset["bytes"] = len(labelled)
        asset["contentHash"] = hashlib.sha256(labelled).hexdigest()[:32]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_pr_lens_rejects_missing_graph_view(self) -> None:
        spec = valid_spec(self.base, self.head)
        self.add_pr_lens(
            spec,
            [
                {
                    "id": "system",
                    "title": "System boundary",
                    "lens": "architecture",
                    "children": [
                        {
                            "id": "components",
                            "title": "Changed components",
                            "lens": "architecture",
                            "children": [],
                        }
                    ],
                }
            ],
        )
        manifest_path = self.dir / spec["prLens"]["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["assets"] = [asset for asset in manifest["assets"] if asset.get("view") != "components"]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("manifest views do not match", r.stderr)

    def test_pr_lens_rejects_parent_path(self) -> None:
        spec = valid_spec(self.base, self.head)
        self.add_pr_lens(spec)
        spec["prLens"]["manifest"] = "../manifest.json"
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("must not contain . or .. segments", r.stderr)

    def test_pr_lens_rejects_stale_graph(self) -> None:
        spec = valid_spec(self.base, self.head)
        self.add_pr_lens(spec)
        graph_path = self.dir / spec["prLens"]["graph"]
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        graph["title"] = "Changed after rendering"
        graph_path.write_text(json.dumps(graph), encoding="utf-8")
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("graph contentHash", r.stderr)

    def test_pr_lens_rejects_stale_worktree(self) -> None:
        spec = valid_spec(self.base, "worktree")
        self.add_pr_lens(spec)
        write(self.repo, "alpha.py", ALPHA_HEAD.replace("return 42", "return 99"))
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("worktreeHash", r.stderr)

    def test_print_worktree_hash(self) -> None:
        r = subprocess.run(
            [
                sys.executable,
                str(BUILD),
                "--repo-root",
                str(self.repo),
                "--print-worktree-hash",
                self.base,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), build_tour.revision_hash(self.repo, self.base))

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
            self.assertNotIn("<img src=x", page.lower())
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

    # ---------------------------------------------------------------- 18
    def test_hunk_rows_carry_highlighted_spans(self) -> None:
        """alpha.py is Python, so the fixture build's hunk rows should carry at least one token span."""
        spec = valid_spec(self.base, self.head)
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertRegex(page, r'class="tk-\w+"')


class SheetTest(unittest.TestCase):
    """The optional `sheet` block; borrows the fixture repo and build helper without rerunning its tests."""

    setUp = BuildTourTest.setUp
    add_pr_lens = BuildTourTest.add_pr_lens
    build = BuildTourTest.build

    def sheet_spec(self) -> dict:
        spec = valid_spec(self.base, self.head)
        spec["sheet"] = {
            "state": "One change set. Nothing needs you.",
            "panels": [
                {"role": "needs you", "type": "asks", "rows": []},
                {"role": "tasks", "type": "tasks", "rows": [{"id": "T1", "name": "Add delta", "status": "done"}]},
                {"role": "review", "type": "findings", "rows": [
                    {"id": "F1", "sev": "P2", "claim": "Delta has no test.", "where": "alpha.py:11",
                     "foundBy": ["scrutinize"], "default": "skip"}]},
                {"role": "decisions", "type": "decisions", "rows": [
                    {"decision": "Where delta lives", "chosen": "In alpha", "why": "It shares the helpers."}]},
            ],
        }
        return spec

    def page(self, spec: dict) -> str:
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.out.read_text(encoding="utf-8")

    def test_no_sheet_means_no_sheet_markup_and_a_stats_strip(self) -> None:
        page = self.page(valid_spec(self.base, self.head))
        self.assertNotIn('class="sheet"', page)
        self.assertNotIn("SHEET:", page)
        self.assertIn('<div class="strip">', page)

    def test_sheet_renders_with_auto_panels_and_no_stats_strip(self) -> None:
        page = self.page(self.sheet_spec())
        self.assertIn('class="sheet"', page)
        self.assertIn('data-kind="execute"', page)
        self.assertNotIn('<div class="strip">', page)
        self.assertNotIn("SHEET:", page)
        m = re.search(r'<section class="[^"]*" id="panel-[A-Z]" data-letter="B" data-role="checks">(.*?)</section>', page, re.S)
        self.assertIsNotNone(m)
        self.assertIn("python3 -m unittest", m.group(1))
        self.assertIn("exit 0", m.group(1))
        m = re.search(r'<section class="[^"]*" id="panel-[A-Z]" data-letter="C" data-role="files">(.*?)</section>', page, re.S)
        self.assertIsNotNone(m)
        changed = json.loads(self.stats.read_text(encoding="utf-8"))["filesChanged"]
        self.assertEqual(len(re.findall(r'class="frow', m.group(1))), changed)

    def test_sheet_more_links_to_a_tour_chapter(self) -> None:
        spec = self.sheet_spec()
        spec["sheet"]["panels"][1]["more"] = "core"
        spec["sheet"]["panels"][2]["rows"][0]["more"] = "core"
        page = self.page(spec)
        self.assertIn('<h2 class="go" data-go="ch-core">', page)
        self.assertIn('<a class="go-a" href="#ch-core" aria-label="Section 1: Alpha returns 42 and delta arrives">›</a>', page)
        self.assertNotIn("more-row", page)
        self.assertIn('id="ch-core"', page)

    def test_sheet_more_to_an_unknown_chapter_fails(self) -> None:
        spec = self.sheet_spec()
        spec["sheet"]["panels"][1]["more"] = "nope"
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("more 'nope' is not a chapter", r.stderr)

    def test_agent_may_not_supply_checks_or_files(self) -> None:
        for role, typ in (("checks", "checks"), ("files", "files")):
            spec = self.sheet_spec()
            spec["sheet"]["panels"].append({"role": role, "type": typ, "rows": []})
            r = self.build(spec)
            self.assertEqual(r.returncode, 1)
            self.assertIn("walkthrough builds checks and files itself", r.stderr)

    def test_missing_required_role_fails(self) -> None:
        spec = self.sheet_spec()
        spec["sheet"]["panels"] = [p for p in spec["sheet"]["panels"] if p["role"] != "review"]
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("review", r.stderr)

    def test_failure_page_is_written_when_a_sheet_build_fails(self) -> None:
        spec = self.sheet_spec()
        spec["sheet"]["panels"] = spec["sheet"]["panels"][:1]
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn("BUILD FAILED", page)

    def test_chapters_are_closed_cards_with_one_open_all_button(self) -> None:
        for spec in (valid_spec(self.base, self.head), self.sheet_spec()):
            page = self.page(spec)
            self.assertNotIn("<article", page)
            self.assertEqual(page.count('<details class="chapter"'), len(spec["chapters"]))
            self.assertEqual(page.count('<summary class="chead">'), len(spec["chapters"]))
            for n, ch in enumerate(spec["chapters"], 1):
                self.assertIn(
                    f'<details class="chapter" id="ch-{ch["id"]}" data-chapter="{ch["id"]}" data-risk="{ch["risk"]}">'
                    f'<summary class="chead"><span class="num">{n}</span>'
                    f'<span class="chip risk-{ch["risk"]}">',
                    page,
                )
            self.assertNotRegex(page, r'<details class="chapter"[^>]* open')
            self.assertIn('<span class="meta" data-chapter-progress></span><span class="chev"', page)
            self.assertEqual(page.count("data-toggle-all>"), 1)
            self.assertIn('<div class="rhead"><h2>Walkthrough</h2><div class="atrow', page)

    def test_report_files_are_spliced_and_shell_has_no_radius(self) -> None:
        for spec in (valid_spec(self.base, self.head), self.sheet_spec()):
            page = self.page(spec)
            self.assertIn(".rhead{display:flex", page)
            self.assertIn(".chapter[open]>.chead .chev", page)
            self.assertEqual(page.count('$("[data-toggle-all]")'), 1)
        shell = (HERE.parent / "templates" / "tour-shell.html").read_text(encoding="utf-8")
        self.assertNotIn("border-radius", shell)

    def test_one_dock_with_and_without_a_sheet(self) -> None:
        for spec, back in ((valid_spec(self.base, self.head), 0), (self.sheet_spec(), 1)):
            page = self.page(spec)
            self.assertEqual(page.count('<div class="dock"'), 1)
            self.assertEqual(page.count('class="tosheet"'), back)
            self.assertEqual(page.count("data-export "), 1)
            self.assertIn("data-export-status hidden", page)
            self.assertIn('<div class="dock-pop" hidden>', page)
            self.assertIn("dockCollect = function", page)
            self.assertIn("function dockCopy", page)
            self.assertNotIn("Copy feedback", page)
            self.assertNotIn("<pre data-export-preview hidden>", page)
            self.assertIn('data-project="repo"', page)

    def test_header_chips_and_title_order(self) -> None:
        branch = subprocess.run(["git", "-C", str(self.repo), "symbolic-ref", "--short", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
        spec = valid_spec(self.base, self.head)
        page = self.page(spec)
        self.assertIn(f"<title>repo · {branch} · {spec['title']}</title>", page)
        top = page[page.index('<header class="top">'):page.index("<h1>")]
        self.assertIn('<div class="atrow"><span class="pchip"', top)
        self.assertIn(f"</svg>{branch}</span>", top)
        self.assertNotIn("atrow sm", top)
        with_sheet = self.page(self.sheet_spec())
        start = with_sheet.index('<header class="top">')
        top = with_sheet[start:with_sheet.index("<h1>", start)]
        self.assertIn('<div class="atrow sm"><span class="pchip"', top)

    def test_no_text_link_toc_row(self) -> None:
        for spec in (valid_spec(self.base, self.head), self.sheet_spec()):
            page = self.page(spec)
            self.assertNotIn('class="toc"', page)
            self.assertNotIn('aria-label="Sections"', page)
            self.assertIn("data-continue", page)

    def test_tour_sheet_shows_project_and_branch_chips(self) -> None:
        page = self.page(self.sheet_spec())
        self.assertIn('class="pchip"', page)
        self.assertIn("data-project=", page)

    def test_tour_feedback_puts_the_answer_block_first(self) -> None:
        page = self.page(self.sheet_spec())
        self.assertIn("sheetAnswers().text", page)


class HighlightTest(unittest.TestCase):
    def strip(self, rendered: str) -> str:
        return re.sub(r"<[^>]+>", "", rendered)

    def test_python_def_and_comment(self) -> None:
        line = "def foo(x): # hi"
        out = build_tour.highlight(line, "python")
        self.assertIn('<span class="tk-kw">def</span>', out)
        self.assertIn('<span class="tk-fn">foo</span>', out)
        self.assertIn('<span class="tk-cm"># hi</span>', out)
        self.assertEqual(self.strip(out), html.escape(line, quote=True))

    def test_js_template_string_and_line_comment(self) -> None:
        line = 'const x = `hi ${1}`; // done'
        out = build_tour.highlight(line, "js")
        self.assertIn('<span class="tk-kw">const</span>', out)
        self.assertIn('<span class="tk-st">`hi ${1}`</span>', out)
        self.assertIn('<span class="tk-cm">// done</span>', out)
        self.assertEqual(self.strip(out), html.escape(line, quote=True))

    def test_html_tag_and_attribute(self) -> None:
        line = '<div class="x">'
        out = build_tour.highlight(line, "html")
        self.assertIn('<span class="tk-ty">div</span>', out)
        self.assertIn('<span class="tk-at">class</span>', out)
        self.assertIn('<span class="tk-st">&quot;x&quot;</span>', out)
        self.assertEqual(self.strip(out), html.escape(line, quote=True))

    def test_unknown_suffix_returns_plain_escape(self) -> None:
        line = 'raw <thing> & "stuff"'
        self.assertEqual(build_tour.highlight(line, "unknown"), html.escape(line, quote=True))

    def test_markdown_line_with_script_tag_stays_escaped(self) -> None:
        line = "See <script> for the loader."
        out = build_tour.highlight(line, "markdown")
        self.assertNotIn("<script", out)
        self.assertEqual(self.strip(out), html.escape(line, quote=True))

    def test_detect_lang_by_suffix_basename_and_shebang(self) -> None:
        self.assertEqual(build_tour.detect_lang("foo.py", ""), "python")
        self.assertEqual(build_tour.detect_lang("Makefile", ""), "makefile")
        self.assertEqual(build_tour.detect_lang("Dockerfile", ""), "dockerfile")
        self.assertEqual(build_tour.detect_lang("run", "#!/usr/bin/env bash"), "shell")
        self.assertEqual(build_tour.detect_lang("run", "#!/usr/bin/env python3"), "unknown")
        self.assertEqual(build_tour.detect_lang("weird.xyz", ""), "unknown")


if __name__ == "__main__":
    unittest.main()
