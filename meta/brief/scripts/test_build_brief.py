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


VALID_SVG = (
    '<svg viewBox="0 0 100 40" role="img" aria-label="A box">'
    '<rect x="4" y="4" width="92" height="32" fill="currentColor"/>'
    "</svg>"
)


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

    # ---------------------------------------------------------------- 20: svg figures
    def test_valid_svg_figure_builds(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = {"svg": VALID_SVG, "caption": "A plain box."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertIn('<figure class="fig">', page)
        self.assertIn('<div class="svg">', page)
        self.assertIn('<svg xmlns="http://www.w3.org/2000/svg"', page)

    def test_array_of_figures_builds_and_renders_in_order(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = [
            {"mermaid": "flowchart LR\n  a --> b", "caption": "First figure."},
            {"svg": VALID_SVG, "caption": "Second figure."},
        ]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertLess(page.index("First figure."), page.index("Second figure."))
        stats = json.loads(r.data_out.read_text(encoding="utf-8"))
        self.assertEqual(stats["visuals"], 3)  # 2 here + 1 in the other chapter
        self.assertEqual(stats["mermaidFigures"], 2)
        self.assertEqual(stats["svgFigures"], 1)

    def test_svg_missing_viewbox_fails(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = {"svg": "<svg><rect/></svg>", "caption": "No viewBox."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("visual[0]", r.stderr)
        self.assertIn("viewBox", r.stderr)

    def test_svg_script_tag_fails_naming_chapter_and_index(self) -> None:
        spec = valid_spec()
        svg = '<svg viewBox="0 0 10 10"><script>alert(1)</script></svg>'
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "Bad svg."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("visual[0]", r.stderr)
        self.assertIn("script", r.stderr)

    def test_svg_onclick_attr_fails(self) -> None:
        spec = valid_spec()
        svg = '<svg viewBox="0 0 10 10"><rect onclick="alert(1)"/></svg>'
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "Bad svg."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("onclick", r.stderr)

    def test_svg_external_href_fails(self) -> None:
        spec = valid_spec()
        svg = '<svg viewBox="0 0 10 10"><use href="http://evil.example/x.svg#a"/></svg>'
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "Bad svg."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("href", r.stderr)

    def test_svg_local_url_ref_passes_external_url_ref_fails(self) -> None:
        spec = valid_spec()
        good = (
            '<svg viewBox="0 0 10 10"><defs><linearGradient id="g"/></defs>'
            '<rect fill="url(#g)"/></svg>'
        )
        spec["chapters"][0]["visual"] = {"svg": good, "caption": "Local ref."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)

        bad = '<svg viewBox="0 0 10 10"><rect fill="url(http://evil.example/x.svg#g)"/></svg>'
        spec["chapters"][0]["visual"] = {"svg": bad, "caption": "External ref."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("url(", r.stderr)

    def test_oversized_svg_fails(self) -> None:
        spec = valid_spec()
        rects = "".join(f'<rect x="{i}" y="0" width="1" height="1"/>' for i in range(6000))
        svg = f'<svg viewBox="0 0 100 100">{rects}</svg>'
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "Too big."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("64 KB", r.stderr)

    def test_svg_output_has_no_ns0_prefix(self) -> None:
        spec = valid_spec()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            'viewBox="0 0 10 10"><rect/></svg>'
        )
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "Namespaced input."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertNotIn("ns0", page)
        self.assertIn('<svg xmlns="http://www.w3.org/2000/svg"', page)

    def test_figure_caption_over_25_words_fails(self) -> None:
        spec = valid_spec()
        long_caption = " ".join(["word"] * 26)
        spec["chapters"][0]["visual"] = {"svg": VALID_SVG, "caption": long_caption}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("caption", r.stderr)
        self.assertIn("26 words", r.stderr)

    def test_mixed_mermaid_and_svg_figures_in_one_chapter(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = [
            {"mermaid": "flowchart LR\n  a --> b", "caption": "The flow."},
            {"svg": VALID_SVG, "caption": "The shape."},
        ]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertIn('<pre class="mermaid">', page)
        self.assertIn('<div class="svg">', page)

    def test_stats_counts_split_between_mermaid_and_svg(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = [
            {"mermaid": "flowchart LR\n  a --> b", "caption": "The flow."},
            {"svg": VALID_SVG, "caption": "The shape."},
        ]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("svg=1", r.stdout)
        stats = json.loads(r.data_out.read_text(encoding="utf-8"))
        # chapter 0 now has 2 figures (1 mermaid + 1 svg), chapter 1 has its original mermaid one
        self.assertEqual(stats["visuals"], 3)
        self.assertEqual(stats["mermaidFigures"], 2)
        self.assertEqual(stats["svgFigures"], 1)

    # ---------------------------------------------------------------- 21: type guards, no traceback
    def test_chapters_wrong_type_int_fails_cleanly(self) -> None:
        spec = valid_spec()
        spec["chapters"] = 5
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("build_brief:", r.stderr)
        self.assertIn("chapters", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_chapters_containing_a_string_fails_cleanly(self) -> None:
        spec = valid_spec()
        spec["chapters"] = ["not-a-chapter-object"]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("chapters[0]", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_decisions_as_dict_fails_cleanly(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["decisions"] = {"decision": "x"}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("decisions", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_evidence_as_dict_fails_cleanly(self) -> None:
        spec = valid_spec()
        spec["chapters"][1]["evidence"] = {"cmd": "x"}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][1]["id"], r.stderr)
        self.assertIn("evidence", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_visual_as_string_fails_cleanly(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = "not-a-figure"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("visual", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_open_as_string_fails_cleanly(self) -> None:
        spec = valid_spec()
        spec["open"] = "not a list"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("open", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    # ---------------------------------------------------------------- 22: svg allowlist PoCs
    def test_poc_a_smil_set_event_handler_fails(self) -> None:
        spec = valid_spec()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            '<rect width="10" height="10">'
            '<set attributeName="onbegin" to="alert(document.domain)" begin="0s"/>'
            "</rect></svg>"
        )
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "SMIL set demo."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("set", r.stderr)
        self.assertFalse(r.out.exists())  # a failed build writes nothing

    def test_poc_b_use_animate_href_rebind_fails(self) -> None:
        spec = valid_spec()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            '<use href="#x"><animate attributeName="href" to="https://evil.example/exfil.svg" '
            'begin="0s" dur="1s" fill="freeze"/></use></svg>'
        )
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "use animate demo."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("animate", r.stderr)

    def test_poc_c_feimage_animate_fails(self) -> None:
        spec = valid_spec()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            '<filter id="f"><feImage><animate attributeName="href" '
            'to="https://evil.example/beacon.png" begin="0s"/></feImage></filter>'
            '<rect width="10" height="10" filter="url(#f)"/></svg>'
        )
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "feImage animate demo."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("feImage", r.stderr)

    def test_poc_d_img_src_fails(self) -> None:
        spec = valid_spec()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            '<img src="https://evil.example/beacon.png"/></svg>'
        )
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "img src demo."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("img", r.stderr)

    def test_svg_style_attribute_fails(self) -> None:
        spec = valid_spec()
        svg = '<svg viewBox="0 0 10 10"><rect style="fill:red"/></svg>'
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "Style attr."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("style", r.stderr)

    def test_svg_html_div_fails(self) -> None:
        spec = valid_spec()
        svg = '<svg viewBox="0 0 10 10"><div>hi</div></svg>'
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "HTML div."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("div", r.stderr)

    def test_svg_javascript_scheme_in_value_fails(self) -> None:
        spec = valid_spec()
        svg = '<svg viewBox="0 0 10 10"><rect fill="jav\tascript:alert(1)"/></svg>'
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "JS scheme."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("disallowed scheme", r.stderr)

    def test_svg_href_on_rect_fails(self) -> None:
        spec = valid_spec()
        svg = '<svg viewBox="0 0 10 10"><rect href="#x"/></svg>'
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "href on rect."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("href", r.stderr)

    def test_svg_href_local_on_use_passes(self) -> None:
        spec = valid_spec()
        svg = (
            '<svg viewBox="0 0 10 10"><defs><g id="x"><rect width="4" height="4"/></g></defs>'
            '<use href="#x"/></svg>'
        )
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "Local use ref."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_svg_unknown_attribute_fails_naming_it(self) -> None:
        spec = valid_spec()
        svg = '<svg viewBox="0 0 10 10"><rect data-evil="x"/></svg>'
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "Unknown attr."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("data-evil", r.stderr)

    # ---------------------------------------------------------------- 23: figure id scoping
    def test_figure_ids_scoped_per_chapter_and_references_rewritten(self) -> None:
        def marker_svg() -> str:
            return (
                '<svg viewBox="0 0 20 20">'
                '<defs><marker id="ar" markerWidth="6" markerHeight="6">'
                '<path d="M0,0 L6,3 L0,6 z" fill="currentColor"/></marker></defs>'
                '<line x1="0" y1="0" x2="10" y2="10" stroke="currentColor" marker-end="url(#ar)"/>'
                "</svg>"
            )

        spec = valid_spec()
        spec["chapters"][0]["visual"] = {"svg": marker_svg(), "caption": "Marker one."}
        spec["chapters"][1]["visual"] = {"svg": marker_svg(), "caption": "Marker two."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")

        cid0, cid1 = spec["chapters"][0]["id"], spec["chapters"][1]["id"]
        id0, id1 = f"f{cid0}-0-ar", f"f{cid1}-0-ar"
        self.assertNotEqual(id0, id1)

        blocks = page.split('<div class="svg">')
        self.assertEqual(len(blocks), 3)  # preamble + one block per figure
        block0, block1 = blocks[1], blocks[2]

        # each figure carries only its own scoped id, and its marker-end points at it
        self.assertIn(f'id="{id0}"', block0)
        self.assertIn(f'url(#{id0})', block0)
        self.assertNotIn(id1, block0)

        self.assertIn(f'id="{id1}"', block1)
        self.assertIn(f'url(#{id1})', block1)
        self.assertNotIn(id0, block1)

    # ---------------------------------------------------------------- 24: normalize_figures bounds
    def test_visual_empty_array_fails(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = []
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)

    def test_visual_five_figures_fail(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = [
            {"mermaid": "flowchart LR\n  a --> b", "caption": f"Figure {i}."} for i in range(5)
        ]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("1 to 4", r.stderr)
        self.assertIn("5", r.stderr)

    def test_visual_four_figures_pass(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = [
            {"mermaid": "flowchart LR\n  a --> b", "caption": f"Figure {i}."} for i in range(4)
        ]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)

    # ---------------------------------------------------------------- 25: figure field crash guards
    def test_mermaid_non_string_fails_cleanly(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = {"mermaid": 5, "caption": "Not a string."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("mermaid must be a string", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_svg_non_string_fails_cleanly(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = {"svg": ["not", "a", "string"], "caption": "Not a string."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("svg must be a string", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_caption_non_string_fails_cleanly(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["visual"] = {"svg": VALID_SVG, "caption": 42}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("caption must be a non-empty string", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
