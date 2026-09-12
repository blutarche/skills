#!/usr/bin/env python3
"""Tests for build_brief.py.

Run from the skill directory:
    python3 -m unittest scripts/test_build_brief.py
    python3 scripts/test_build_brief.py
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_brief  # noqa: E402  (needs sys.path set up above)

BUILD = HERE / "build_brief.py"


def make_prose(n_words: str | int, tag: str = "p") -> str:
    """`n_words` "word" tokens, split into 20-word sentences so the sentence cap never trips
    while the word cap is exercised on its own."""
    words = ["word"] * int(n_words)
    sentences = []
    for i in range(0, len(words), 20):
        sentences.append(" ".join(words[i : i + 20]) + ".")
    return f"<{tag}>" + " ".join(sentences) + f"</{tag}>"


def valid_spec() -> dict:
    return {
        "title": "Outbox retries land without touching the request path",
        "kind": "execution",
        "context": "<p>A webhook used to acknowledge before it was durable. Now it is durable first.</p>",
        "state": "<p>The outbox and the worker are merged and tested.</p>",
        "chapters": [
            {
                "id": "before-the-reply",
                "title": "The handler stores the event before it replies",
                "prose": "<p>The route inserts a row before it replies. The insert is idempotent on the event id.</p>",
                "visual": {
                    "mermaid": "flowchart LR\n  a[Handler] -->|insert| b[(Outbox)]",
                    "caption": "The insert commits before the reply leaves the handler.",
                },
                "decisions": [
                    {
                        "decision": "Where the write happens",
                        "chosen": "Inside the request",
                        "rejected": "After replying",
                        "why": "Acknowledging before the write is durable is the bug being fixed.",
                    }
                ],
            },
            {
                "id": "the-drain-loop",
                "title": "A worker drains the outbox with backoff",
                "prose": "<p>A worker claims rows and retries with backoff. A parked row keeps its last error.</p>",
                "visual": {
                    "mermaid": "sequenceDiagram\n  participant W as Worker\n  W->>W: claim and retry",
                    "caption": "One claim, one attempt, one backoff update per tick.",
                },
                "evidence": [
                    {"cmd": "npm test", "cwd": ".", "exit": 0, "ok": True, "summary": "31 passed"},
                    {"cmd": "npm run e2e", "cwd": ".", "exit": None, "summary": "not run"},
                ],
            },
        ],
        "open": ["<b>Assign an owner</b> for the parked-row alert."],
    }


class Harness:
    """Runs build_brief.main() in-process so shutil.which can be monkeypatched for the mmdc
    tests; a subprocess would spawn its own interpreter and never see the patch."""

    def build(self, spec: dict, tmp: Path, mmdc_check: bool = False) -> SimpleNamespace:
        """`mmdc_check=False` (the default) passes `--no-mmdc`, so tests unrelated to mmdc never
        depend on whether it happens to be installed. `mmdc_check=True` leaves the check enabled,
        for tests that monkeypatch `shutil.which` to point at a fake mmdc."""
        payload = json.dumps(spec).encode("utf-8")
        spec_path = tmp / "brief.json"
        spec_path.write_bytes(payload)
        out = tmp / "brief.html"
        fragment = tmp / "brief.fragment.html"
        data_out = tmp / "stats.json"
        argv = [
            str(BUILD),
            "--spec", str(spec_path),
            "--out", str(out),
            "--fragment", str(fragment),
            "--data-out", str(data_out),
        ]
        if not mmdc_check:
            argv.append("--no-mmdc")
        old_argv = sys.argv
        sys.argv = argv
        out_buf, err_buf = io.StringIO(), io.StringIO()
        code = 0
        try:
            with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
                build_brief.main()
        except SystemExit as e:
            code = e.code or 0
        finally:
            sys.argv = old_argv
        return SimpleNamespace(
            returncode=code, stdout=out_buf.getvalue(), stderr=err_buf.getvalue(),
            out=out, fragment=fragment, data_out=data_out, spec_bytes=payload,
        )


class BuildBriefTest(unittest.TestCase, Harness):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    # ---------------------------------------------------------------- 1: valid spec
    def test_valid_spec_builds(self) -> None:
        spec = valid_spec()
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("build_brief: ok"), r.stdout)
        page = r.out.read_text(encoding="utf-8")
        titles = [ch["title"] for ch in spec["chapters"]]
        # each title also labels its Notes textarea, so it appears twice; check reading order
        # by the first (heading) occurrence of each
        positions = [page.index(f"<h3>{t}</h3>") for t in titles]
        self.assertEqual(positions, sorted(positions))
        for t in titles:
            self.assertIn(t, page)
        stats = json.loads(r.data_out.read_text(encoding="utf-8"))
        self.assertEqual(stats["chapters"], 2)
        self.assertEqual(stats["visuals"], 2)
        self.assertEqual(stats["noVisuals"], 0)
        self.assertEqual(stats["decisions"], 1)
        self.assertEqual(stats["evidenceRan"], 1)
        self.assertEqual(stats["evidenceNotRun"], 1)
        self.assertGreater(stats["words"], 0)

    # ---------------------------------------------------------------- 2: fragment vs document
    def test_fragment_has_no_html_wrapper_or_cdn_document_has_both(self) -> None:
        spec = valid_spec()
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        frag = r.fragment.read_text(encoding="utf-8")
        for wrapper in ("<!doctype", "<html", "<body"):
            self.assertNotIn(wrapper, frag.lower())
        self.assertNotIn("cdnjs", frag.lower())
        self.assertIn('<pre class="mermaid">', frag)

        page = r.out.read_text(encoding="utf-8")
        self.assertIn("<html", page.lower())
        self.assertEqual(
            page.count("cdnjs.cloudflare.com/ajax/libs/mermaid/11.4.1/mermaid.min.js"), 1
        )

    # ---------------------------------------------------------------- 3: required fields
    def test_missing_required_field(self) -> None:
        spec = valid_spec()
        del spec["state"]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("build_brief:", r.stderr)
        self.assertIn("state", r.stderr)

    # ---------------------------------------------------------------- 4: kind
    def test_invalid_kind(self) -> None:
        spec = valid_spec()
        spec["kind"] = "vibes"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("vibes", r.stderr)

    # ---------------------------------------------------------------- 5: chapter count
    def test_too_many_chapters(self) -> None:
        spec = valid_spec()
        base = spec["chapters"][0]
        spec["chapters"] = [{**base, "id": f"ch-{i}"} for i in range(9)]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("keep between 1 and 8", r.stderr)

    # ---------------------------------------------------------------- 6: kebab-case id
    def test_non_kebab_chapter_id(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["id"] = "Not_Kebab"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Not_Kebab", r.stderr)
        self.assertIn("kebab-case", r.stderr)

    # ---------------------------------------------------------------- 7: duplicate id
    def test_duplicate_chapter_id(self) -> None:
        spec = valid_spec()
        spec["chapters"][1]["id"] = spec["chapters"][0]["id"]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("duplicate chapter id", r.stderr)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)

    # ---------------------------------------------------------------- 8: visual xor noVisual
    def test_visual_and_novisual_both_present_fails(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["noVisual"] = "not needed"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("both visual and noVisual", r.stderr)

    def test_neither_visual_nor_novisual_fails(self) -> None:
        spec = valid_spec()
        del spec["chapters"][0]["visual"]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("needs exactly one of visual or noVisual", r.stderr)

    def test_novisual_valid_string_builds(self) -> None:
        spec = valid_spec()
        del spec["chapters"][0]["visual"]
        spec["chapters"][0]["noVisual"] = "A table already carries this better than a picture."
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertNotIn("A table already carries this better than a picture.", page)

    # ---------------------------------------------------------------- 9: mermaid diagram type
    def test_mermaid_bad_diagram_type(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"]["mermaid"] = "notarealtype LR\n  a --> b"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("notarealtype LR", r.stderr)

    def test_mermaid_frontmatter_and_init_are_skipped(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"]["mermaid"] = (
            "---\ntitle: x\n---\n%%{init: {'theme': 'base'}}%%\nflowchart LR\n  a --> b"
        )
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)

    # ---------------------------------------------------------------- 10/11/12: mmdc
    def make_fake_mmdc(self, exit_code: int) -> Path:
        script = self.dir / "mmdc"
        script.write_text(f"#!/bin/sh\necho fake-mmdc-stderr 1>&2\nexit {exit_code}\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return script

    def test_mmdc_present_and_succeeds(self) -> None:
        fake = self.make_fake_mmdc(0)
        old_which = build_brief.shutil.which
        build_brief.shutil.which = lambda name: str(fake) if name == "mmdc" else old_which(name)
        try:
            spec = valid_spec()
            r = self.build(spec, self.dir, mmdc_check=True)
        finally:
            build_brief.shutil.which = old_which
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_mmdc_present_and_fails(self) -> None:
        fake = self.make_fake_mmdc(1)
        old_which = build_brief.shutil.which
        build_brief.shutil.which = lambda name: str(fake) if name == "mmdc" else old_which(name)
        try:
            spec = valid_spec()
            r = self.build(spec, self.dir, mmdc_check=True)
        finally:
            build_brief.shutil.which = old_which
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("fake-mmdc-stderr", r.stderr)

    def test_mmdc_absent_prints_notice_and_continues(self) -> None:
        old_which = build_brief.shutil.which
        build_brief.shutil.which = lambda name: None
        try:
            spec = valid_spec()
            r = self.build(spec, self.dir, mmdc_check=True)
        finally:
            build_brief.shutil.which = old_which
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("build_brief: mmdc not found, mermaid syntax unchecked", r.stderr)

    def test_no_mmdc_flag_skips_check_even_when_mmdc_present(self) -> None:
        fake = self.make_fake_mmdc(1)
        old_which = build_brief.shutil.which
        build_brief.shutil.which = lambda name: str(fake) if name == "mmdc" else old_which(name)
        try:
            spec = valid_spec()
            r = self.build(spec, self.dir)  # default args already include --no-mmdc
        finally:
            build_brief.shutil.which = old_which
        self.assertEqual(r.returncode, 0, r.stderr)

    # ---------------------------------------------------------------- 13: prose word cap
    def test_prose_word_cap_boundary(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["prose"] = make_prose(120)
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)

        spec["chapters"][0]["prose"] = make_prose(121)
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("121 words", r.stderr)

    def test_context_word_cap(self) -> None:
        spec = valid_spec()
        spec["context"] = make_prose(121)
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("context", r.stderr)
        self.assertIn("121 words", r.stderr)

    def test_state_word_cap(self) -> None:
        spec = valid_spec()
        spec["state"] = make_prose(61)
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("state", r.stderr)
        self.assertIn("61 words", r.stderr)

    # ---------------------------------------------------------------- 14: sentence cap
    def test_sentence_cap(self) -> None:
        spec = valid_spec()
        long_sentence = " ".join(["word"] * 26) + "."
        spec["chapters"][0]["prose"] = f"<p>{long_sentence}</p>"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("26 words, over 25", r.stderr)
        self.assertIn("word word word word word", r.stderr)

    # ---------------------------------------------------------------- 15: decisions
    def test_decision_row_missing_field(self) -> None:
        spec = valid_spec()
        del spec["chapters"][0]["decisions"][0]["why"]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("decisions[0]", r.stderr)
        self.assertIn("why", r.stderr)

    # ---------------------------------------------------------------- 16: evidence
    def test_evidence_row_missing_cwd(self) -> None:
        spec = valid_spec()
        del spec["chapters"][1]["evidence"][0]["cwd"]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][1]["id"], r.stderr)
        self.assertIn("evidence[0]", r.stderr)
        self.assertIn("cwd", r.stderr)

    def test_evidence_exit_must_be_int_or_null(self) -> None:
        spec = valid_spec()
        spec["chapters"][1]["evidence"][0]["exit"] = "zero"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("exit must be an integer or null", r.stderr)

    def test_evidence_ok_must_be_bool(self) -> None:
        spec = valid_spec()
        spec["chapters"][1]["evidence"][0]["ok"] = "yes"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ok must be true or false", r.stderr)

    # ---------------------------------------------------------------- 17: open items
    def test_open_item_must_be_string(self) -> None:
        spec = valid_spec()
        spec["open"] = [{"not": "a string"}]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("open[0]", r.stderr)

    # ---------------------------------------------------------------- 18: page key
    def test_page_key_derived_from_spec_bytes(self) -> None:
        spec = valid_spec()
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        expected = hashlib.sha256(r.spec_bytes).hexdigest()[:12]
        page = r.out.read_text(encoding="utf-8")
        self.assertIn(f'data-storage-key="brief:{expected}"', page)

    # ---------------------------------------------------------------- 19: sanitizer
    def test_sanitizer_strips_script_in_prose_keeps_text(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["prose"] = "<p>Fine.</p><script>alert(1)</script>"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertIn("<p>Fine.</p>alert(1)", page)
        self.assertNotIn("<script>alert(1)</script>", page)

    def test_mermaid_source_with_script_is_escaped_in_pre(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"]["mermaid"] = "flowchart LR\n  a[<script>alert(1)</script>] --> b"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)


if __name__ == "__main__":
    unittest.main()
