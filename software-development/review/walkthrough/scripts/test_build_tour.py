#!/usr/bin/env python3
"""Tests for build_tour.py against throwaway git repositories.

Run from the skill directory:
    python3 -m unittest scripts/test_build_tour.py
    python3 scripts/test_build_tour.py
"""

from __future__ import annotations

import copy
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
        self, spec: dict, out: Path | None = None, with_pr_lens: bool = True, seed: int | None = None
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
                *(["--seed", str(seed)] if seed is not None else []),
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
        self.assertIn("lines shown 7 / changed 12 (58%)", r.stdout)
        self.assertIn("Of <b>12</b> changed lines, you read <b>10</b> (83%)", page)

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
    def test_low_coverage_shows_the_line_partition(self) -> None:
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
        # the digest's coverage line replaces the old low-coverage notice
        self.assertNotIn("This tour shows", page)
        lines = stats["digest"]["lines"]
        self.assertEqual(lines["total"], stats["linesChanged"])
        self.assertIn(f'<b>{lines["word"]}</b> ({round(100 * lines["word"] / lines["total"])}%) rest on the agent\'s word', page)

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
        spec["chapters"][1]["files"].append({"path": "page.html"})
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertNotIn("reallyLongName", page)

    # ---------------------------------------------------------------- 16
    def test_short_and_dollar_only_names_suppressed(self) -> None:
        js = "const $ = 1;\nconst $$ = 2;\nfunction raw() {}\nfunction process() {}\nfunction normalize() {}\n"
        write(self.repo, "util.js", js)
        spec = valid_spec(self.base, "worktree")
        spec["chapters"][1]["files"].append({"path": "util.js"})
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

    def test_no_sheet_means_no_sheet_markup_and_the_digest_replaces_the_strip(self) -> None:
        page = self.page(valid_spec(self.base, self.head))
        self.assertNotIn('class="sheet"', page)
        self.assertNotIn("SHEET:", page)
        self.assertNotIn('<div class="strip">', page)
        self.assertNotIn('id="everything-else"', page)
        self.assertLess(page.index("</header>"), page.index('<section class="digest" id="digest">'))
        self.assertLess(page.index('<section class="digest" id="digest">'), page.index('<section id="overview">'))

    def test_sheet_renders_with_auto_panels_and_no_stats_strip(self) -> None:
        page = self.page(self.sheet_spec())
        self.assertIn('class="sheet"', page)
        self.assertIn('data-kind="execute"', page)
        self.assertNotIn('<div class="strip">', page)
        self.assertLess(page.index("</header>"), page.index('<section class="digest" id="digest">'))
        self.assertLess(page.index('<section class="digest" id="digest">'), page.index('<section id="overview">'))
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
            self.assertEqual(page.count('<span class="meta" data-chapter-progress></span>'), len(spec["chapters"]))
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
            # report.js and the shell share one scope: a var named like its function would replace it
            self.assertIn("function chapters()", page)
            self.assertNotRegex(page, r"\bvar chapters\b")
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


RENAME_BASE = 'import {{ fetchUser }} from "./api";\n\nexport const v{i} = fetchUser({i});\n'


class DigestBuildTest(unittest.TestCase):
    """Reading tiers, groups, and the everythingElse cap, end to end through the build."""

    setUp = BuildTourTest.setUp
    add_pr_lens = BuildTourTest.add_pr_lens
    build = BuildTourTest.build

    def group_fixture(self, flagged: bool = True) -> tuple[str, str]:
        """Four files renamed fetchUser -> loadUser on top of the feature commit; with flagged,
        the last one also adds a call the rule does not explain. Returns (base, head)."""
        for i in range(4):
            write(self.repo, f"src/m{i}.ts", RENAME_BASE.format(i=i))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "--no-verify", "-m", "rename base")
        base = git(self.repo, "rev-parse", "HEAD")
        for i in range(4):
            write(self.repo, f"src/m{i}.ts", RENAME_BASE.format(i=i).replace("fetchUser", "loadUser"))
        if flagged:
            write(self.repo, "src/m3.ts", RENAME_BASE.format(i=3).replace("fetchUser", "loadUser") + "deleteAll();\n")
        write(self.repo, "alpha.py", ALPHA_HEAD.replace("return 42", "return 7"))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "--no-verify", "-m", "rename head")
        return base, git(self.repo, "rev-parse", "HEAD")

    def group_spec(self, base: str, head: str) -> dict:
        return {
            "title": "Rename the user reader",
            "base": base,
            "head": head,
            "overview": "<p>One rename and one value.</p>",
            "chapters": [
                {
                    "id": "core",
                    "title": "Alpha returns 7",
                    "risk": "attention",
                    "overview": "<p>The value moves.</p>",
                    "files": [{"path": "alpha.py", "hunks": [{"side": "new", "start": 2, "end": 2}]}],
                }
            ],
            "groups": [
                {"id": "rename", "title": "fetchUser becomes loadUser", "files": ["src/*.ts"],
                 "from": "fetchUser", "to": "loadUser"}
            ],
        }

    def test_unplaced_deletion_lands_in_the_deleted_group(self) -> None:
        spec = valid_spec(self.base, self.head)
        spec["everythingElse"] = []
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(self.stats.read_text(encoding="utf-8"))["digest"]
        self.assertEqual(d["tiers"]["keep.txt"], "word")
        self.assertEqual([(g["id"], g["files"]) for g in d["groups"]], [("deleted", ["keep.txt"])])

    def test_unplaced_changed_file_fails_with_the_digest_message(self) -> None:
        write(self.repo, "gamma.txt", "fresh and untracked\n")
        r = self.build(valid_spec(self.base, "worktree"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("changed files no chapter or group claims: gamma.txt", r.stderr)

    def test_everything_else_cap(self) -> None:
        for name in ("e1", "e2", "e3", "e4"):
            write(self.repo, f"{name}.txt", f"{name}\n")
        spec = valid_spec(self.base, "worktree")
        spec["everythingElse"] += [{"path": f"{n}.txt"} for n in ("e1", "e2", "e3", "e4")]
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("everythingElse holds 5 files; the limit for this diff is 3", r.stderr)
        self.assertIn("groups or chapters", r.stderr)
        spec["everythingElse"] = spec["everythingElse"][:3]
        spec["chapters"][1]["files"] += [{"path": "e3.txt"}, {"path": "e4.txt"}]
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_bad_group_fails_in_check_spec(self) -> None:
        spec = valid_spec(self.base, self.head)
        spec["groups"] = [{"id": "bad", "title": "Bad", "files": ["*.py"], "from": "(", "to": "", "regex": True}]
        r = self.build(spec)
        self.assertEqual(r.returncode, 1)
        self.assertIn("group bad: from is not a valid regex", r.stderr)

    def test_flagged_file_warns_and_the_data_out_carries_the_digest(self) -> None:
        base, head = self.group_fixture()
        r = self.build(self.group_spec(base, head))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("build_tour: warning: 1 file broke a rule: src/m3.ts (rename)", r.stderr)
        self.assertIn(" tiers flagged=1 read=1 skim=0 matched=3 word=0", r.stdout)
        stats = json.loads(self.stats.read_text(encoding="utf-8"))
        self.assertEqual(stats["flagged"], 1)
        d = stats["digest"]
        self.assertIsInstance(d["seed"], int)
        self.assertEqual(d["counts"], {"flagged": 1, "read": 1, "skim": 0, "matched": 3, "word": 0})
        self.assertEqual(set(d["lines"]), {"total", "read", "matched", "word", "sampled"})
        self.assertEqual(
            d["tiers"],
            {"alpha.py": "read", "src/m0.ts": "matched", "src/m1.ts": "matched", "src/m2.ts": "matched", "src/m3.ts": "flagged"},
        )
        self.assertEqual(list(d["tiers"]), sorted(d["tiers"]))
        [g] = d["groups"]
        self.assertEqual(
            (g["id"], g["kind"], g["tier"], g["files"]),
            ("rename", "substitution", "matched", ["src/m0.ts", "src/m1.ts", "src/m2.ts"]),
        )
        self.assertEqual(g["samples"], [{"path": "src/m0.ts", "side": "new", "start": 1, "end": 3}])
        self.assertEqual(
            d["flags"],
            [{"path": "src/m3.ts", "group": "rename",
              "reason": "Applying the rule to the old file does not give the new file."}],
        )

    def group_sheet_spec(self, base: str, head: str) -> dict:
        spec = self.group_spec(base, head)
        spec["sheet"] = {
            "state": "One rename and one value.",
            "panels": [
                {"role": "needs you", "type": "asks", "rows": [{"ask": "Keep the new name?", "why": "It touches callers."}]},
                {"role": "tasks", "type": "tasks", "rows": [{"id": "T1", "name": "Rename it", "status": "done"}]},
                {"role": "review", "type": "findings", "rows": []},
                {"role": "decisions", "type": "decisions", "rows": []},
            ],
        }
        return spec

    def test_flagged_file_puts_the_sheet_on_needs_you_with_a_builder_row_first(self) -> None:
        base, head = self.group_fixture()
        spec = self.group_sheet_spec(base, head)
        before = copy.deepcopy(spec["sheet"])
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(spec["sheet"], before)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn('<div class="stamp amb">NEEDS YOU</div>', page)
        m = re.search(r'data-role="needs you">(.*?)</section>', page, re.S)
        self.assertIsNotNone(m)
        panel = m.group(1)
        self.assertIn("Read the file the build flagged", panel)
        self.assertIn("src/m3.ts broke the rule fetchUser becomes loadUser.", panel)
        self.assertLess(panel.index("Read the file the build flagged"), panel.index("Keep the new name?"))

    def test_several_flagged_files_share_one_builder_row(self) -> None:
        base, head = self.group_fixture()
        for i in (1, 2):
            write(self.repo, f"src/m{i}.ts", RENAME_BASE.format(i=i).replace("fetchUser", "loadUser") + "deleteAll();\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "--no-verify", "-m", "more flagged")
        head = git(self.repo, "rev-parse", "HEAD")
        r = self.build(self.group_sheet_spec(base, head))
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn("Read the 3 files the build flagged", page)
        self.assertIn("3 files broke a rule. See Read first.", page)

    def test_no_flag_leaves_the_sheet_stamp_alone(self) -> None:
        base, head = self.group_fixture(flagged=False)
        spec = self.group_sheet_spec(base, head)
        spec["sheet"]["panels"][0]["rows"] = []
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn('<div class="stamp ok">DONE</div>', page)
        self.assertNotIn("the build flagged", page)

    def test_flagged_card_tops_the_reading_list(self) -> None:
        base, head = self.group_fixture()
        r = self.build(self.group_spec(base, head))
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        start = page.index('<details class="chapter flag" id="flag-src-m3-ts" data-flag="src/m3.ts" open>')
        card = page[start:page.index("</details>", start)]
        self.assertIn('<span class="num">!</span><span class="tier t-flagged">FLAGGED</span>', card)
        self.assertIn('<h3 class="ttl path">src/m3.ts</h3><span class="meta">rule: fetchUser becomes loadUser</span>', card)
        self.assertIn("Applying the rule to the old file does not give the new file.", card)
        # the rule expects nothing where the file adds a line: the expected side says so
        self.assertRegex(card, r"the rule gives.*\(no lines\).*the file has")
        self.assertIn(
            '<span class="row add"><span class="ln">4</span><span class="sg">+</span><span class="tx">deleteAll();</span></span>',
            card,
        )
        self.assertEqual(card.count('data-card="f-flag-src-m3-ts"'), 2)  # the read box counts in progress
        self.assertLess(page.index('<h3 class="sect"><b>Read first</b>'), start)
        self.assertLess(start, page.index('id="ch-core"'))
        self.assertIn("Flagged by the build: ", page)

    def page_fixture(self) -> dict:
        """Every tier and every derived group on top of the feature commit. Returns the spec."""
        write(self.repo, "plain.txt", "plain\n" * 4)
        write(self.repo, "trail.py", "x = 1   \ny = 2\n")
        write(self.repo, "old.txt", "one\ntwo\n")
        write(self.repo, "misc.cfg", "a = 1\n")
        (self.repo / "img.bin").write_bytes(b"\0\1\2")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "--no-verify", "-m", "fixture files")
        base, head = self.group_fixture()
        (self.repo / "moved").mkdir()
        git(self.repo, "mv", "plain.txt", "moved/plain.txt")
        write(self.repo, "trail.py", "x = 1\ny = 2\n")
        (self.repo / "old.txt").unlink()
        write(self.repo, "misc.cfg", "a = 2\n")
        (self.repo / "img.bin").write_bytes(b"\0\1\3\4")
        write(self.repo, "notes.md", NOTES_HEAD + "\nMore.\n")
        for i in range(4):
            write(self.repo, f"gen/g{i}.js", "".join(f"export const k{i}_{n} = {n};\n" for n in range(1, 4 + i)))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "--no-verify", "-m", "page head")
        spec = self.group_spec(base, git(self.repo, "rev-parse", "HEAD"))
        spec["chapters"].append(
            {"id": "docs", "title": "Notes grow", "risk": "safe", "overview": "<p>Docs.</p>", "files": [{"path": "notes.md"}]}
        )
        spec["groups"].append(
            {"id": "gen", "title": "Generated constants", "files": ["gen/*"], "kind": "generated",
             "why": "<p>Written by <code>make gen</code>.</p>"}
        )
        spec["everythingElse"] = [{"path": "misc.cfg", "why": "Bumps the setting."}]
        return spec

    def test_glance_block(self) -> None:
        spec = self.page_fixture()
        r = self.build(spec, seed=5)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        stats = json.loads(self.stats.read_text(encoding="utf-8"))
        self.assertEqual(stats["digest"]["counts"], {"flagged": 1, "read": 1, "skim": 1, "matched": 5, "word": 7})
        self.assertIn(
            '<p class="budget">Read <b>1</b> hunk in <b>1</b> file. Check <b>1</b> file the build flagged. '
            "Skim <b>1</b> file. The build matched <b>5</b> files to <b>3</b> rules. "
            "<b>7</b> files rest on the agent's word; <b>4</b> are sampled for you.</p>",
            page,
        )
        self.assertIn(
            '<div class="tierbar" role="img" aria-label="15 changed files: 1 flagged, 1 read, 1 skim, '
            '5 matched a rule, 7 agent&#x27;s word"><span class="t-flagged" style="flex:1 1 0">1</span>',
            page,
        )
        self.assertIn('<span class="t-word" style="flex:7 1 0">7</span></div>', page)
        fm = page[page.index('<div class="fm">'):page.index('<ul class="tiers">')]
        self.assertEqual(fm.count('<a class="sq t-'), 15)
        self.assertEqual(re.findall(r'<div class="fml"><span>([^<]+)</span><span>(\d+)</span>', fm),
                         [("(root)", "6"), ("gen", "4"), ("src", "4"), ("moved", "1")])
        for square in (
            '<a class="sq t-flagged" href="#flag-src-m3-ts" title="src/m3.ts" aria-label="src/m3.ts: flagged"></a>',
            '<a class="sq t-read" href="#f-core-alpha-py" title="alpha.py" aria-label="alpha.py: read"></a>',
            '<a class="sq t-skim" href="#f-docs-notes-md" title="notes.md" aria-label="notes.md: skim"></a>',
            '<a class="sq t-matched" href="#g-rename" title="src/m0.ts"',
            '<a class="sq t-matched" href="#g-moved" title="moved/plain.txt"',
            '<a class="sq t-matched" href="#g-line-ends" title="trail.py"',
            '<a class="sq t-word" href="#g-gen" title="gen/g0.js"',
            '<a class="sq t-word" href="#g-deleted" title="old.txt"',
            '<a class="sq t-word" href="#g-binary" title="img.bin"',
            '<a class="sq t-word" href="#g-everything-else" title="misc.cfg"',
        ):
            self.assertIn(square, fm)
        self.assertNotIn("dg-key", page)
        self.assertIn(
            '<p class="dg-how">Every changed file is in one group below, by how much of your attention it needs. '
            "Each square in the map is one file; click it to open its card.</p>",
            page,
        )
        rows = re.findall(r'<li><i class="sq t-(\w+)"></i><span class="tn"><b>(\d+)</b> ([^<]+)</span>'
                          r'<span class="tm">([^<]+)</span></li>', page)
        self.assertEqual([(t, n) for t, n, _, _ in rows],
                         [("flagged", "1"), ("read", "1"), ("skim", "1"), ("matched", "5"), ("word", "7")])
        self.assertEqual([m for *_, m in rows], [build_tour.TIER_MEANING[t] for t in
                                                 ("flagged", "read", "skim", "matched", "word")])
        self.assertIn("Read these first.", rows[0][3])
        lines = stats["digest"]["lines"]
        total = lines["total"]
        self.assertIn(
            f'<p class="cover">Of <b>{total}</b> changed lines, you read <b>{lines["read"]}</b> '
            f'({round(100 * lines["read"] / total)}%), a rule covers <b>{lines["matched"]}</b> '
            f'({round(100 * lines["matched"] / total)}%), and <b>{lines["word"]}</b> '
            f'({round(100 * lines["word"] / total)}%) rest on the agent\'s word. '
            f'The page shows <b>{stats["linesShown"]}</b> of the lines you read and <b>{lines["sampled"]}</b> '
            "sample lines.</p>",
            page,
        )
        self.assertNotIn('<div class="fm small">', page)

    def test_reading_order_and_group_cards(self) -> None:
        spec = self.page_fixture()
        r = self.build(spec, seed=5)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        heads = [page.index(f'<h3 class="sect"><b>{name}</b>') for name in
                 ("Read first", "Skim", "Matched by the build", "On the agent's word")]
        self.assertEqual(heads, sorted(heads))
        self.assertIn("<b>Read first</b><span>1 flagged · 1 chapter</span>", page)
        self.assertIn("<b>Matched by the build</b><span>5 files · 3 rules</span>", page)
        self.assertIn("<b>On the agent's word</b><span>7 files · 4 sampled</span>", page)
        self.assertLess(heads[0], page.index('id="flag-src-m3-ts"'))
        self.assertLess(page.index('id="flag-src-m3-ts"'), page.index('id="ch-core"'))
        self.assertLess(page.index('id="ch-core"'), heads[1])
        self.assertLess(heads[1], page.index('id="ch-docs"'))
        self.assertNotRegex(page, r'<details class="chapter group"[^>]* open')

        def card(gid: str) -> str:
            start = page.index(f'<details class="chapter group" id="g-{gid}">')
            return page[start:page.index("</div></details>", page.index("</summary>", start))]

        rename = card("rename")
        self.assertIn('<span class="num">✓</span><span class="tier t-matched">MATCHED</span>'
                      '<h3 class="ttl">fetchUser becomes loadUser</h3><span class="meta">3 files · 12 lines</span>', rename)
        self.assertIn("The build applied <code>fetchUser</code> → <code>loadUser</code> (plain text) to the old version "
                      "of each file and got the new version exactly. This shows the change is mechanical, "
                      "not that the rule is right.", rename)
        self.assertIn('<span class="loc">sample · src/m0.ts:1-3</span>', rename)
        self.assertIn("<summary>All 3 files</summary>", rename)
        self.assertNotIn("data-card", rename)
        moved = card("moved")
        self.assertIn("Same content and same file mode at a new path. Copies and links never count here.", moved)
        self.assertIn("<code>plain.txt</code> → <code>moved/plain.txt</code>", moved)
        ends = card("line-ends")
        self.assertIn("Only spaces at line ends or line-ending style changed. Indentation changes never count here.", ends)
        self.assertIn("sample · trail.py:1-2", ends)

        gen = card("gen")
        self.assertIn('<span class="num">≈</span><span class="tier t-word">AGENT\'S WORD</span>'
                      '<span class="kind">generated</span><h3 class="ttl">Generated constants</h3>'
                      '<span class="meta">4 files · 3 sampled</span>', gen)
        self.assertIn("<p>Written by <code>make gen</code>.</p>", gen)
        self.assertIn("Samples: the largest file plus 2 drawn at random, each at a random change. "
                      "Samples drawn with seed 5, set by hand.", gen)
        self.assertEqual(len(re.findall(r'<div class="file" id="f-sample-gen-gen-g\d-js" data-file="gen/g\d.js" '
                                        r'data-card="f-sample-gen-gen-g\d-js">', gen)), 3)
        self.assertIn('id="f-sample-gen-gen-g3-js"', gen)  # the largest file always leads
        self.assertIn("<summary>All 4 files</summary>", gen)
        rest = card("everything-else")
        self.assertIn('<span class="kind">everything else</span>', rest)
        self.assertIn("<li><code>misc.cfg</code>: Bumps the setting.</li>", rest)
        self.assertIn("Sample: the largest file, at a random change. Samples drawn with seed 5, set by hand.", rest)
        deleted = card("deleted")
        self.assertIn('<span class="meta">1 file</span>', deleted)
        self.assertIn("<code>old.txt</code> · 2 lines removed", deleted)
        self.assertIn("The build shows these files are gone. Whether anything still needs them rests on the agent.", deleted)
        binary = card("binary")
        self.assertIn("<code>img.bin</code> · modified · 4 bytes", binary)
        self.assertNotIn("sampled", binary)

        # progress counts chapter cards, the flagged card, and every sample
        cards = set(re.findall(r'<div class="file"[^>]* data-card="([^"]+)"', page))
        self.assertEqual(len(cards), 2 + 1 + 4)
        self.assertIn('" of " + cards.length + " cards read"', page)
        self.assertIn('$$("details.chapter[data-chapter]")', page)
        self.assertIn('window.addEventListener("hashchange", openToHash)', page)

    def test_group_prose_is_sanitized_and_titles_escaped(self) -> None:
        spec = self.page_fixture()
        hostile = '<script>alert(1)</script><a href="javascript:x">go</a>'
        spec["groups"][0]["why"] = "<p>Rename. " + hostile + "</p>"
        spec["groups"][0]["title"] = "<b>rename</b>"
        spec["groups"][1]["why"] = "<p>Gen. " + hostile + "</p>"
        spec["everythingElse"][0]["why"] = "Bump. " + hostile
        r = self.build(spec, seed=5)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("javascript:", page)
        self.assertEqual(page.count("alert(1)"), 3)  # the text survives as inert prose
        self.assertIn('<h3 class="ttl">&lt;b&gt;rename&lt;/b&gt;</h3>', page)
        self.assertIn('<span class="meta">rule: &lt;b&gt;rename&lt;/b&gt;</span>', page)

    def test_squares_shrink_past_300_files(self) -> None:
        paths = [f"d/f{i:03}.txt" for i in range(301)]
        dg = build_tour.digest.Digest(
            tiers={p: "word" for p in paths}, groups=[], flags=[], seed=1,
            counts={"flagged": 0, "read": 0, "skim": 0, "matched": 0, "word": 301},
            lines={"total": 301, "read": 0, "matched": 0, "word": 301, "sampled": 0},
        )
        glance = build_tour.render_glance(dg, dict.fromkeys(paths), {p: "g-bulk" for p in paths}, 0, 0)
        self.assertIn('<div class="fm small">', glance)
        self.assertEqual(glance.count('<a class="sq t-word"'), 301)
        dg.tiers.pop(paths[0])
        dg.counts["word"] = 300
        glance = build_tour.render_glance(dg, dict.fromkeys(paths[1:]), {p: "g-bulk" for p in paths}, 0, 0)
        self.assertIn('<div class="fm">', glance)

    def test_empty_tier_has_no_row_and_zero_clauses_drop(self) -> None:
        dg = build_tour.digest.Digest(
            tiers={"a.txt": "word"}, groups=[], flags=[], seed=1,
            counts={"flagged": 0, "read": 0, "skim": 0, "matched": 0, "word": 1},
            lines={"total": 4, "read": 0, "matched": 0, "word": 4, "sampled": 0},
        )
        glance = build_tour.render_glance(dg, {"a.txt": None}, {"a.txt": "g-bulk"}, 0, 0)
        self.assertEqual(glance.count("<li>"), 1)
        self.assertIn('<i class="sq t-word"></i>', glance)
        self.assertIn('<p class="cover">Of <b>4</b> changed lines, <b>4</b> (100%) rest on the agent\'s word.</p>', glance)
        dg = build_tour.digest.Digest(
            tiers={}, groups=[], flags=[], seed=1,
            counts=dict.fromkeys(("flagged", "read", "skim", "matched", "word"), 0),
            lines={"total": 0, "read": 0, "matched": 0, "word": 0, "sampled": 0},
        )
        glance = build_tour.render_glance(dg, {}, {}, 0, 0)
        self.assertNotIn("<li>", glance)
        self.assertIn("No file changed.", glance)

    def test_rule_every_file_broke_still_shows(self) -> None:
        base, head = self.group_fixture()
        spec = self.group_spec(base, head)
        spec["groups"][0]["to"] = "getUser"
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("build_tour: warning: 4 files broke a rule: src/m0.ts (rename), src/m1.ts (rename)", r.stderr)
        page = self.out.read_text(encoding="utf-8")
        start = page.index('<details class="chapter group" id="g-rename">')
        group = page[start:page.index("</details>", start)]
        self.assertIn('<span class="meta">0 files · 0 lines</span>', group)
        self.assertIn("Every file it claimed broke the rule, so each one is under Read first.", group)
        self.assertNotIn("got the new version exactly", group)
        self.assertNotIn("The build matched", page)
        self.assertEqual(page.count('<details class="chapter flag"'), 4)

    def test_no_flag_means_no_warning(self) -> None:
        base, head = self.group_fixture(flagged=False)
        r = self.build(self.group_spec(base, head))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("warning", r.stderr)
        self.assertEqual(json.loads(self.stats.read_text(encoding="utf-8"))["flagged"], 0)

    def test_seed_flag_fixes_the_samples(self) -> None:
        for i in range(12):
            write(self.repo, f"gen/f{i:02}.txt", "".join(f"v{i} {n}\n" for n in range(1, 9)))
        spec = valid_spec(self.base, "worktree")
        spec["groups"] = [{"id": "gen", "title": "Generated", "files": ["gen/*"], "kind": "generated",
                           "why": "Written by the generator."}]

        def samples(seed: int) -> tuple[int, list]:
            r = self.build(spec, seed=seed)
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(self.stats.read_text(encoding="utf-8"))["digest"]
            return d["seed"], [g["samples"] for g in d["groups"] if g["id"] == "gen"][0]

        seed, first = samples(11)
        self.assertEqual(seed, 11)
        self.assertEqual(len(first), 3)
        self.assertEqual(samples(11)[1], first)
        self.assertTrue(any(samples(s)[1] != first for s in range(12, 20)))

    def sampling_spec(self) -> dict:
        for i in range(12):
            write(self.repo, f"gen/f{i:02}.txt", "".join(f"v{i} {n}\n" for n in range(1, 9)))
        spec = valid_spec(self.base, "worktree")
        spec["groups"] = [{"id": "gen", "title": "Generated", "files": ["gen/*"], "kind": "generated",
                           "why": "Written by the generator."}]
        return spec

    def test_default_seed_comes_from_the_change(self) -> None:
        spec = self.sampling_spec()
        seen = []
        for _ in range(3):
            r = self.build(spec)
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(self.stats.read_text(encoding="utf-8"))["digest"]
            self.assertEqual(d["seedSource"], "commit")
            seen.append((d["seed"], [g["samples"] for g in d["groups"] if g["id"] == "gen"][0]))
            self.assertIn("Samples drawn from this commit.", self.out.read_text(encoding="utf-8"))
        self.assertEqual(seen[0], seen[1])
        self.assertEqual(seen[0], seen[2])

    def test_default_seed_of_a_commit_is_its_sha(self) -> None:
        r = self.build(valid_spec(self.base, self.head))
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(self.stats.read_text(encoding="utf-8"))["digest"]
        full = git(self.repo, "rev-parse", self.head).strip()
        self.assertEqual((d["seed"], d["seedSource"]), (int(full[:8], 16), "commit"))

    def test_manual_seed_is_labelled(self) -> None:
        spec = self.sampling_spec()
        r = self.build(spec, seed=11)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(self.stats.read_text(encoding="utf-8"))["digest"]
        self.assertEqual((d["seed"], d["seedSource"]), (11, "manual"))
        self.assertIn("Samples drawn with seed 11, set by hand.", self.out.read_text(encoding="utf-8"))

    def test_chapters_number_in_reading_order(self) -> None:
        spec = SheetTest.sheet_spec(self)
        spec["chapters"].reverse()  # safe docs first, attention core second
        spec["sheet"]["panels"][1]["more"] = "core"
        spec["sheet"]["panels"][2]["rows"][0]["more"] = "docs"
        r = self.build(spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn('id="ch-core" data-chapter="core" data-risk="attention"><summary class="chead"><span class="num">1</span>', page)
        self.assertIn('id="ch-docs" data-chapter="docs" data-risk="safe"><summary class="chead"><span class="num">2</span>', page)
        self.assertLess(page.index('id="ch-core"'), page.index('id="ch-docs"'))
        self.assertIn('aria-label="Section 1: Alpha returns 42 and delta arrives"', page)
        self.assertIn('aria-label="Section 2: Notes gain a section"', page)


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
