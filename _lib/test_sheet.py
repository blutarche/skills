#!/usr/bin/env python3
"""Tests for sheet.py.

Run from this directory:
    python3 -m unittest test_sheet.py
"""

from __future__ import annotations

import copy
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pagelib  # noqa: E402
import sheet  # noqa: E402
import voice  # noqa: E402


def vet_spec() -> dict:
    return {
        "state": "3 findings. 2 are fixed by default.",
        "facts": [{"k": "branch", "v": "feat/outbox"}],
        "panels": [
            {"role": "needs you", "type": "asks", "rows": []},
            {"role": "findings", "type": "findings", "rows": [
                {"id": "F1", "sev": "P1", "claim": "A crash drops the event.", "foundBy": ["scrutinize", "council"], "default": "fix"},
                {"id": "F2", "sev": "P2", "claim": "The retry delay has no cap.", "foundBy": ["council"], "default": "fix"},
                {"id": "F3", "sev": "P3", "claim": "One log line is noisy.", "foundBy": ["scrutinize"], "default": "skip"},
            ]},
        ],
    }


def check(spec, kind="vet", **kw):
    return sheet.check_sheet(spec, kind=kind, title="Outbox review", **kw)


def fails(test, spec, kind="vet", **kw) -> str:
    with test.assertRaises(pagelib.BuildFailed) as cm:
        check(spec, kind, **kw)
    return cm.exception.msg


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout


def panel(spec, role):
    return next(p for p in spec["panels"] if p["role"] == role)


class SheetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        (self.root / "src").mkdir()
        (self.root / "src" / "a.txt").write_text("one\ntwo\nthree\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")
        self.sha = git(self.root, "rev-parse", "HEAD").strip()
        (self.root / "src" / "a.txt").write_text("one\ntwo\nthree\nfour\n")
        self.tree = {"repo": str(self.root), "base": "HEAD", "head": "worktree"}

    # minimal valid spec per kind
    def minimal(self, kind):
        ask = {"role": "needs you", "type": "asks", "rows": []}
        table = {"role": "hardening", "type": "table", "columns": ["Risk"], "rows": [["Low"]]}
        tasks = {"role": "tasks", "type": "tasks", "rows": [{"id": "T1", "name": "Store", "status": "done"}]}
        decisions = {"role": "decisions", "type": "decisions", "rows": [
            {"decision": "Queue", "chosen": "Outbox", "why": "It is simple."}]}
        checks = {"role": "checks", "type": "checks", "rows": [{"cmd": "make test", "cwd": ".", "exit": 0}]}
        files = {"role": "files", "type": "files"}
        findings = {"role": "review", "type": "findings", "rows": [
            {"id": "F1", "sev": "P3", "claim": "A log line is noisy.", "foundBy": ["a"], "default": "skip"}]}
        spec = {"state": "All done.", "tree": self.tree}
        spec["panels"] = {
            "plan": [ask, table, tasks, decisions],
            "execute": [ask, checks, files, tasks, findings, decisions],
            "vet": [ask, {**findings, "role": "findings"}],
            "finish": [ask, {"role": "next move", "type": "commands", "rows": [{"cmd": "git push", "does": "Push it."}]},
                       checks, {**files, "role": "diff"}, findings],
            "research": [ask, {"role": "claims", "type": "claims", "rows": [
                {"id": "C1", "claim": "It scales.", "source": "doc.md", "result": "verified"}]}],
            "grill": [ask, decisions, {**files, "role": "docs changed"}],
            "session": [ask],
        }[kind]
        return spec

    def test_1_vet_passes(self):
        s = check(vet_spec())
        self.assertEqual([p["letter"] for p in s["panels"]], ["A", "B"])
        self.assertEqual((s["stamp"], s["stampTone"]), ("DONE", "ok"))

    def test_2_stamps(self):
        spec = vet_spec()
        spec["panels"][0]["rows"] = [{"ask": "Fix F2 now?"}]
        s = check(spec)
        self.assertEqual((s["stamp"], s["stampTone"]), ("NEEDS YOU", "amb"))
        spec["blocked"] = True
        s = check(spec)
        self.assertEqual((s["stamp"], s["stampTone"]), ("BLOCKED", "bad"))

    def test_3_kind_defaults(self):
        for kind, stamp in [("plan", "READY"), ("finish", "READY"), ("research", "ANSWERED"),
                            ("execute", "DONE"), ("grill", "DONE"), ("session", "DONE"), ("vet", "DONE")]:
            with self.subTest(kind=kind):
                self.assertEqual(check(self.minimal(kind), kind)["stamp"], stamp)

    def test_4_first_panel_must_be_asks(self):
        spec = vet_spec()
        spec["panels"].reverse()
        self.assertIn("panel A must be needs you: asks", fails(self, spec))

    def test_5_missing_required_role(self):
        spec = vet_spec()
        del spec["panels"][1]
        self.assertIn("vet sheet needs a findings panel (findings)", fails(self, spec))

    def test_6_wrong_type(self):
        spec = vet_spec()
        spec["panels"][1] = {"role": "findings", "type": "claims", "rows": []}
        msg = fails(self, spec)
        self.assertIn("findings", msg)
        self.assertIn("must be type findings, not claims", msg)

    def test_7_structure_errors(self):
        bad = vet_spec()
        fails(self, bad, kind="nope")
        bad["panels"].append({"role": "x", "type": "nope", "rows": []})
        fails(self, bad)
        bad = vet_spec()
        bad["panels"].append({"role": "findings", "type": "table", "columns": ["a"], "rows": [["b"]]})
        self.assertIn("duplicate", fails(self, bad))
        bad = vet_spec()
        bad["panels"][1]["span"] = 5
        fails(self, bad)
        bad = vet_spec()
        bad["panels"] += [{"role": f"r{i}", "type": "table", "columns": ["a"], "rows": [["b"]]} for i in range(7)]
        fails(self, bad)
        bad = vet_spec()
        bad["facts"] = [{"k": f"k{i}", "v": "v"} for i in range(7)]
        fails(self, bad)

    def test_8_voice(self):
        spec = vet_spec()
        spec["panels"][1]["rows"][0]["claim"] = "We utilize a lock."
        self.assertIn('panel B findings[0] claim: "utilize" → "use"', fails(self, spec))
        spec = vet_spec()
        spec["state"] = "One. Two. Three."
        fails(self, spec)
        with self.assertRaises(pagelib.BuildFailed):
            sheet.check_sheet(vet_spec(), kind="vet", title=" ".join(["word"] * 13))
        spec = vet_spec()
        spec["panels"].append({"role": "checks", "type": "checks", "rows": [{"cmd": "utilize x", "cwd": ".", "exit": 0}]})
        check(spec)

    def test_9_files_needs_tree_and_no_rows(self):
        spec = vet_spec()
        spec["panels"].append({"role": "files", "type": "files"})
        self.assertIn("files panel needs tree", fails(self, spec))
        spec["tree"] = self.tree
        check(spec)
        panel(spec, "files")["rows"] = [{"path": "x"}]
        fails(self, spec)

    def test_10_where_checked(self):
        spec = vet_spec()
        rows = spec["panels"][1]["rows"]
        rows[0]["where"] = "src/a.txt:2"
        rows[1]["where"] = "src/a.txt:99"
        self.assertIn("where needs tree", fails(self, spec))
        spec["tree"] = self.tree
        html = sheet.render_sheet(check(spec))
        self.assertEqual(html.count("agent-reported"), 1)
        self.assertEqual(html.count("src/a.txt:2"), 1)

    def test_11_task_commit_and_cycle(self):
        spec = self.minimal("plan")
        panel(spec, "tasks")["rows"][0]["commit"] = "deadbeef"
        fails(self, spec, "plan")
        panel(spec, "tasks")["rows"][0]["commit"] = self.sha
        check(spec, "plan")
        panel(spec, "tasks")["rows"] = [
            {"id": "A", "name": "a", "status": "todo", "after": ["B"]},
            {"id": "B", "name": "b", "status": "todo", "after": ["A"]}]
        fails(self, spec, "plan")

    def test_12_figure_steps(self):
        def fig(svg, steps):
            spec = vet_spec()
            spec["panels"].append({"role": "flow", "type": "figure", "caption": "How it flows.", "svg": svg, "steps": steps})
            return spec
        one = '<svg viewBox="0 0 10 10"><g data-s="{}"><rect x="0" y="0" width="5" height="5"/></g></svg>'
        two = [{"n": 1, "say": "First."}, {"n": 2, "say": "Second."}]
        self.assertIn("step 2 is not used by any data-s", fails(self, fig(one.format("1"), two)))
        self.assertIn("data-s 3 has no step", fails(self, fig(one.format("3"), two)))
        spec = fig(one.format("1 2"), two)
        check(spec)
        html = sheet.render_sheet(check(spec))
        self.assertIn('data-act="next"', html)
        spec = vet_spec()
        spec["panels"].append({"role": "flow", "type": "figure", "caption": "How it flows.", "mermaid": "graph TD; A-->B", "steps": two})
        self.assertIn("steps need svg", fails(self, spec))

    def test_13_render(self):
        s = check(vet_spec())
        html = sheet.render_sheet(s)
        for needle in ['class="stamp ok"', ">DONE<", 'data-letter="A"', "✓ Nothing needs you", "sev-strip",
                       'aria-label="scrutinize found 2, council found 2, both found 1"', "feat/outbox", 'class="key"']:
            self.assertIn(needle, html)
        self.assertEqual(html.count('data-default="fix"'), 2)
        self.assertEqual(html.count('data-default="skip"'), 1)
        self.assertEqual(html.count("3 findings"), 1)

    def test_14_checks_panel(self):
        spec = vet_spec()
        spec["panels"].append({"role": "checks", "type": "checks", "rows": [
            {"cmd": "a", "cwd": ".", "exit": 0}, {"cmd": "b", "cwd": ".", "exit": 0},
            {"cmd": "c", "cwd": ".", "exit": 2}, {"cmd": "d", "cwd": ".", "exit": None}]})
        html = sheet.render_sheet(check(spec))
        self.assertIn("2 pass · 1 fail · 1 not run", html)
        self.assertIn("agent-reported", html)
        for mark in "✓✕○":
            self.assertIn(mark, html)

    def test_15_words(self):
        spec = vet_spec()
        s = check(spec)
        fields = ["Outbox review", spec["state"], "branch", "needs you", "findings"]
        fields += [r["claim"] for r in spec["panels"][1]["rows"]]
        self.assertEqual(s["words"], sum(len(voice.plain(f, "label").split()) for f in fields))

    def test_16_failure_sheet(self):
        html = sheet.render_failure("chapter x: too long <b>", "/t/brief.json")
        self.assertIn("BUILD FAILED", html)
        self.assertIn('class="stamp bad"', html)
        self.assertIn("<pre>chapter x: too long &lt;b&gt;</pre>", html)
        self.assertIn("/t/brief.json", html)
        self.assertNotIn("data-letter", html)

    def test_assets_and_relative_tree(self):
        css, js = sheet.assets()
        self.assertIsInstance(css, str)
        self.assertIsInstance(js, str)
        spec = vet_spec()
        spec["tree"] = {"repo": self.root.name, "base": "HEAD", "head": "worktree"}
        spec["panels"].append({"role": "files", "type": "files"})
        s = check(spec, spec_dir=self.root.parent)
        self.assertIn("src/a.txt", sheet.render_sheet(s))

    def test_auto_panels_after_a(self):
        auto = [{"role": "checks", "type": "checks", "rows": [{"cmd": "x", "cwd": ".", "exit": 0}]}]
        s = check(vet_spec(), auto_panels=auto)
        self.assertEqual([p["role"] for p in s["panels"]], ["needs you", "checks", "findings"])
        self.assertEqual([p["letter"] for p in s["panels"]], ["A", "B", "C"])


if __name__ == "__main__":
    unittest.main()
