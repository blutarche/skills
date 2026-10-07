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
import time
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
        "title": "Outbox retries: review of feat/outbox",
        "kind": "vet",
        "project": "outbox-service",
        "branch": "feat/outbox",
        "state": "3 findings. 2 are fixed by default.",
        "facts": [{"k": "branch", "v": "feat/outbox"}],
        "panels": [
            {"role": "needs you", "type": "asks", "rows": []},
            {"role": "findings", "type": "findings", "rows": [
                {"id": "F1", "sev": "P1", "claim": "A crash drops the event.",
                 "foundBy": ["scrutinize", "council"], "default": "fix"},
                {"id": "F2", "sev": "P2", "claim": "The retry delay has no cap.",
                 "foundBy": ["council"], "default": "fix"},
                {"id": "F3", "sev": "P3", "claim": "One log line is noisy.",
                 "foundBy": ["scrutinize"], "default": "skip"},
            ]},
        ],
        "chapters": [
            {
                "id": "before-the-reply",
                "title": "The handler stores the event before it replies",
                "prose": "<p>The route inserts a row before it replies. The insert is idempotent on the event id.</p>",
                "visual": {
                    "mermaid": "flowchart LR\n  a[Handler] -->|insert| b[(Outbox)]",
                    "caption": "The insert commits before the reply.",
                },
                "decisions": [
                    {
                        "decision": "Where the write happens",
                        "chosen": "Inside the request",
                        "rejected": "After replying",
                        "why": "Acknowledging before the write is durable is the bug.",
                    }
                ],
            },
            {
                "id": "the-drain-loop",
                "title": "A worker drains the outbox with backoff",
                "prose": "<p>A worker claims rows and retries with backoff. A parked row keeps its last error.</p>",
                "visual": {"svg": VALID_SVG, "caption": "One claim per tick."},
                "evidence": [
                    {"cmd": "npm test", "cwd": ".", "exit": 0, "ok": True, "summary": "31 passed"},
                    {"cmd": "npm run e2e", "cwd": ".", "exit": None, "summary": "Not run."},
                ],
            },
        ],
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

    # ---------------------------------------------------------------- valid sheet, outputs
    def test_valid_spec_builds(self) -> None:
        spec = valid_spec()
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        positions = [page.index(f'id="ch-{ch["id"]}"') for ch in spec["chapters"]]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(page.index('class="sheet"'), positions[0])
        self.assertLess(page.index('class="grid"'), positions[0])

    def test_stdout_summary_line(self) -> None:
        r = self.build(valid_spec(), self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(
            r.stdout.strip(),
            r"^build_brief: ok kind=vet stamp=DONE panels=2 asks=0 words=\d+ chapters=2$",
        )

    def test_data_out_shape(self) -> None:
        r = self.build(valid_spec(), self.dir)
        data = json.loads(r.data_out.read_text(encoding="utf-8"))
        self.assertEqual(
            set(data), {"kind", "stamp", "panels", "asks", "words", "figures", "chapters"}
        )
        self.assertEqual((data["kind"], data["stamp"], data["chapters"]), ("vet", "DONE", 2))
        self.assertEqual(data["figures"], 2)

    def test_fragment_has_no_html_wrapper_or_cdn_document_has_both(self) -> None:
        r = self.build(valid_spec(), self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        frag = r.fragment.read_text(encoding="utf-8")
        for wrapper in ("<!doctype", "<html", "<body"):
            self.assertNotIn(wrapper, frag.lower())
        self.assertNotIn("cdnjs", frag.lower())
        self.assertIn('<pre class="mermaid">', frag)
        page = r.out.read_text(encoding="utf-8")
        self.assertIn("<html", page.lower())
        self.assertEqual(
            page.count("cdnjs.cloudflare.com/ajax/libs/mermaid/11.15.0/mermaid.min.js"), 1
        )

    def test_chapters_render_as_an_open_full_report_after_the_sheet(self) -> None:
        spec = valid_spec()
        r = self.build(spec, self.dir)
        page = r.out.read_text(encoding="utf-8")
        self.assertIn('<section class="report" id="report">', page)
        self.assertIn("<h2>Full report</h2>", page)
        self.assertNotIn('class="drawer"', page)
        self.assertNotIn('class="toc"', page)
        self.assertEqual(page.count("<details"), len(spec["chapters"]))
        for n, ch in enumerate(spec["chapters"], 1):
            self.assertIn(f'<details class="chapter" id="ch-{ch["id"]}" data-chapter="{ch["id"]}">', page)
            self.assertIn(f'<summary class="chead"><span class="num">{n}</span>', page)
            self.assertIn(f'data-note="ch-{ch["id"]}"', page)
        self.assertLess(page.index("</footer>"), page.index('id="report"'))

    def test_report_has_one_open_all_button_only_with_chapters(self) -> None:
        page = self.build(valid_spec(), self.dir).out.read_text(encoding="utf-8")
        self.assertEqual(page.count("data-toggle-all>"), 1)
        self.assertIn(">Open all</button>", page)
        spec = valid_spec()
        spec["chapters"] = []
        page = self.build(spec, self.dir).out.read_text(encoding="utf-8")
        self.assertNotIn("data-toggle-all>", page)
        self.assertNotIn("<details", page)

    def test_shared_report_files_are_spliced(self) -> None:
        page = self.build(valid_spec(), self.dir).out.read_text(encoding="utf-8")
        self.assertIn(".rhead{display:flex", page)
        self.assertIn(".chapter[open]>.chead .chev", page)
        self.assertIn('$("[data-toggle-all]")', page)
        self.assertEqual(page.count('$("[data-toggle-all]")'), 1)

    def test_one_floating_back_button_replaces_section_links(self) -> None:
        spec = valid_spec()
        spec["panels"][1]["rows"][0]["more"] = "the-drain-loop"
        page = self.build(spec, self.dir).out.read_text(encoding="utf-8")
        self.assertIn('<a class="go-a" href="#ch-the-drain-loop"', page)
        self.assertNotIn('class="back"', page)
        self.assertEqual(page.count('class="tosheet"'), 1)
        self.assertIn('<button type="button" class="tosheet" hidden>\u2191 Back to sheet</button>', page)
        spec["chapters"] = []
        spec["panels"][1]["rows"][0].pop("more")
        page = self.build(spec, self.dir).out.read_text(encoding="utf-8")
        self.assertNotIn('class="tosheet"', page)

    def test_more_must_name_a_chapter(self) -> None:
        spec = valid_spec()
        spec["panels"][1]["more"] = "nope"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("more 'nope' is not a chapter", r.stderr)

    def test_visual_is_optional_and_novisual_is_ignored(self) -> None:
        spec = valid_spec()
        del spec["chapters"][0]["visual"]
        spec["chapters"][0]["noVisual"] = "A table already carries this."
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("A table already carries this.", r.out.read_text(encoding="utf-8"))

    def test_chapters_are_optional(self) -> None:
        spec = valid_spec()
        del spec["chapters"]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('id="report"', r.out.read_text(encoding="utf-8"))

    def test_too_many_chapters(self) -> None:
        spec = valid_spec()
        base = spec["chapters"][0]
        spec["chapters"] = [{**base, "id": f"ch-{i}"} for i in range(12)]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        spec["chapters"] = [{**base, "id": f"ch-{i}"} for i in range(13)]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("keep between 0 and 12", r.stderr)

    def test_no_google_fonts_and_no_stats_strip(self) -> None:
        r = self.build(valid_spec(), self.dir)
        page = r.out.read_text(encoding="utf-8")
        self.assertNotIn("fonts.googleapis.com", page)
        self.assertNotIn('class="strip"', page)

    def test_sheet_js_owns_export_hooks(self) -> None:
        r = self.build(valid_spec(), self.dir)
        page = r.out.read_text(encoding="utf-8")
        for hook in ("data-export ", "data-export-status", "data-export-preview"):
            self.assertIn(hook, page)
        self.assertEqual(page.count("function dockCopy"), 1)
        self.assertNotIn("function copyText", page)
        self.assertNotIn("function sheetCopy", page)

    def test_dock_holds_send_feedback_outside_the_sheet(self) -> None:
        asks = valid_spec()
        asks["panels"][0]["rows"] = [{"ask": "Fix now?", "options": [{"label": "Yes"}, {"label": "No"}]}]
        bare = valid_spec()
        bare["chapters"] = []
        for spec in (valid_spec(), asks, bare):
            page = self.build(spec, self.dir).out.read_text(encoding="utf-8")
            self.assertEqual(page.count('<div class="dock" data-project='), 1)
            dock = page[page.index('<div class="dock" data-project='):]
            self.assertGreater(page.index('<div class="dock" data-project='), page.index('</footer></div>'))
            self.assertIn('<div class="dock-pop" hidden>', dock)
            self.assertIn("<pre data-export-preview></pre>", dock)
            self.assertIn('class="dock-toast" role="status" aria-live="polite" data-export-status hidden', dock)
            self.assertIn(">Send feedback</button>", dock)
            self.assertEqual(page.count("data-export>"), 0)
            self.assertEqual(page.count("data-export "), 1)
            self.assertEqual(page.count('class="tosheet"'), 1 if spec["chapters"] else 0)
            self.assertNotIn('class="sendbar"', page)
            self.assertNotIn('class="fb"', page)
            self.assertNotIn("data-" + "send>", page)

    def test_send_confirmation_hooks(self) -> None:
        page = self.build(valid_spec(), self.dir).out.read_text(encoding="utf-8")
        for needle in ('"\u2713 Sent"', ".dock-toast.ok", ".dock-toast.warn", ".dock .send.sent",
                       "prefers-reduced-motion"):
            self.assertIn(needle, page)

    def test_title_and_report_header_carry_project_and_branch(self) -> None:
        page = self.build(valid_spec(), self.dir).out.read_text(encoding="utf-8")
        self.assertIn("<title>outbox-service · feat/outbox · Outbox retries: review of feat/outbox</title>", page)
        rhead = page[page.index('<div class="rhead">'):page.index("data-toggle-all")]
        self.assertIn('class="pchip"', rhead)
        self.assertIn('class="bchip"', rhead)
        self.assertIn('data-project="outbox-service" data-branch="feat/outbox"', page)
        spec = valid_spec()
        del spec["branch"]
        page = self.build(spec, self.dir).out.read_text(encoding="utf-8")
        self.assertIn("<title>outbox-service · Outbox retries", page)

    def test_missing_project_fails_the_build(self) -> None:
        spec = valid_spec()
        del spec["project"]
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn('project: give "project"', r.stderr)

    # ---------------------------------------------------------------- prose rules
    def test_long_chapter_prose_builds(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["prose"] = "<p>" + " ".join(["The route stores one more fact."] * 6) + "</p>"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        spec["chapters"][0]["prose"] = make_prose(400)
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_prose_why_is_rejected(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["proseWhy"] = "The race needs the full order of events."
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(
            "chapter before-the-reply: proseWhy is no longer used; prose has no length cap", r.stderr)

    def test_table_and_h4_survive_in_chapter_prose_but_not_in_state(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["prose"] = (
            "<h4>Cost</h4><table><thead><tr><th>Step</th><th>Cost</th></tr></thead>"
            "<tbody><tr><td>Insert</td><td>One write</td></tr></tbody></table>")
        spec["state"] = "<h4 id=x><table><tr>3 findings. 2 are fixed.</tr></table></h4>"
        page = self.build(spec, self.dir).out.read_text(encoding="utf-8")
        chapter = page[page.index('id="ch-before-the-reply"'):page.index('id="ch-the-drain-loop"')]
        self.assertIn("<h4>Cost</h4>", chapter)
        self.assertIn("<td>One write</td>", chapter)
        state = page[page.index('<p class="state">'):page.index("</p>", page.index('<p class="state">'))]
        self.assertNotIn("<table", state)
        self.assertNotIn("<h4", state)

    def test_voice_lint_runs_on_chapter_title(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["title"] = "We utilize a very long title that goes on past twelve words in total"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("chapter before-the-reply title", r.stderr)

    # ---------------------------------------------------------------- failure page
    def test_failed_build_writes_failure_page_without_spec_text(self) -> None:
        spec = valid_spec()
        spec["title"] = "Zebrafish marker title"
        del spec["panels"][1]  # the vet sheet then lacks its findings panel
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        for path in (r.out, r.fragment):
            text = path.read_text(encoding="utf-8")
            self.assertIn("BUILD FAILED", text)
            self.assertIn("findings", text)
            self.assertNotIn("Zebrafish", text)
        self.assertFalse(r.data_out.exists())

    def test_unreadable_spec_still_writes_failure_page(self) -> None:
        out = self.dir / "o.html"
        old = sys.argv
        sys.argv = [str(BUILD), "--spec", str(self.dir / "missing.json"), "--out", str(out), "--no-mmdc"]
        try:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
                build_brief.main()
        finally:
            sys.argv = old
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("BUILD FAILED", out.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- mermaid pre-render
    def fake_mmdc(self, body: str) -> Path:
        script = self.dir / "mmdc"
        script.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return script

    def build_with_which(self, spec: dict, fake: Path | None) -> SimpleNamespace:
        old_which = build_brief.shutil.which
        build_brief.shutil.which = lambda name: (str(fake) if fake else None) if name == "mmdc" else old_which(name)
        try:
            return self.build(spec, self.dir, mmdc_check=True)
        finally:
            build_brief.shutil.which = old_which

    WRITER = (
        'while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift;; esac; shift; done\n'
        'printf \'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>\' > "$out"\n'
    )

    def test_mermaid_without_mmdc_keeps_pre_and_cdn(self) -> None:
        r = self.build_with_which(valid_spec(), None)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertIn('<pre class="mermaid">', page)
        self.assertIn("cdnjs.cloudflare.com/ajax/libs/mermaid", page)
        self.assertIn("build_brief: mmdc not found; mermaid figures render only online", r.stderr)

    def test_mermaid_with_mmdc_becomes_picture_and_drops_cdn(self) -> None:
        r = self.build_with_which(valid_spec(), self.fake_mmdc(self.WRITER))
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertIn("<picture>", page)
        self.assertEqual(page.count("data:image/svg+xml;base64,"), 2)
        self.assertNotIn('<pre class="mermaid">', page)
        self.assertNotIn("cdnjs", page)

    def test_mermaid_figure_panel_goes_through_mmdc_too(self) -> None:
        spec = valid_spec()
        spec["panels"].append({
            "role": "flow", "type": "figure", "mermaid": "flowchart LR\n  a --> b",
            "caption": "The flow of one event.",
        })
        r = self.build_with_which(spec, self.fake_mmdc(self.WRITER))
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertEqual(page.count("<picture>"), 2)
        self.assertNotIn('<pre class="mermaid">', page)
        r = self.build_with_which(spec, None)
        self.assertEqual(r.out.read_text(encoding="utf-8").count('<pre class="mermaid">'), 2)

    def test_mmdc_failure_fails_with_its_stderr(self) -> None:
        r = self.build_with_which(valid_spec(), self.fake_mmdc("echo fake-mmdc-stderr 1>&2\nexit 1\n"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("before-the-reply", r.stderr)
        self.assertIn("fake-mmdc-stderr", r.stderr)
        self.assertIn("fake-mmdc-stderr", r.out.read_text(encoding="utf-8"))

    def test_no_mmdc_flag_skips_mmdc_even_when_present(self) -> None:
        old_which = build_brief.shutil.which
        build_brief.shutil.which = lambda name: str(self.fake_mmdc("exit 1\n")) if name == "mmdc" else old_which(name)
        try:
            r = self.build(valid_spec(), self.dir)  # the harness passes --no-mmdc by default
        finally:
            build_brief.shutil.which = old_which
        self.assertEqual(r.returncode, 0, r.stderr)

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
        self.assertIn('<figure class="cfig">', page)
        self.assertIn('<div class="fig cfig-svg">', page)
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
        self.assertEqual(stats["figures"], 3)  # 2 here + 1 in the other chapter

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
        self.assertIn('<div class="fig cfig-svg">', page)

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
        self.assertIn("BUILD FAILED", r.out.read_text(encoding="utf-8"))

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

        blocks = page.split('<div class="fig cfig-svg">')
        self.assertEqual(len(blocks), 3)  # preamble + one block per chapter figure
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

    # ---------------------------------------------------------------- 26: case-insensitive url(), DTD/entity refusal
    def test_poc_e_uppercase_url_scheme_fails(self) -> None:
        spec = valid_spec()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            '<rect width="10" height="10" fill="black" '
            'filter="URL(https://evil.example/track.svg#f)"/></svg>'
        )
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "Uppercase URL()."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("filter", r.stderr)
        self.assertIn("url(", r.stderr)
        self.assertIn("BUILD FAILED", r.out.read_text(encoding="utf-8"))

    def test_svg_mixed_case_url_local_ref_passes(self) -> None:
        spec = valid_spec()
        svg = (
            '<svg viewBox="0 0 10 10"><defs><linearGradient id="ok"/></defs>'
            '<rect fill="Url(#ok)"/></svg>'
        )
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "Mixed-case local ref."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_poc_g_entity_declaration_rejected_before_parsing(self) -> None:
        spec = valid_spec()
        svg = (
            '<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a0 "AAAAAAAAAA">'
            '<!ENTITY a1 "&a0;&a0;&a0;&a0;&a0;&a0;&a0;&a0;&a0;&a0;">'
            '<!ENTITY a2 "&a1;&a1;&a1;&a1;&a1;&a1;&a1;&a1;&a1;&a1;">'
            '<!ENTITY a3 "&a2;&a2;&a2;&a2;&a2;&a2;&a2;&a2;&a2;&a2;">'
            '<!ENTITY a4 "&a3;&a3;&a3;&a3;&a3;&a3;&a3;&a3;&a3;&a3;">]>'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            "<title>&a4;</title></svg>"
        )
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "Entity expand."}
        start = time.monotonic()
        r = self.build(spec, self.dir)
        elapsed = time.monotonic() - start
        self.assertEqual(r.returncode, 1)
        self.assertIn("must not declare a DTD or entities", r.stderr)
        self.assertIn("BUILD FAILED", r.out.read_text(encoding="utf-8"))
        self.assertLess(elapsed, 1.0, "DTD/entity check must reject before any parsing occurs")

    def test_svg_doctype_without_entities_also_rejected(self) -> None:
        spec = valid_spec()
        svg = (
            '<?xml version="1.0"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
            '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>'
        )
        spec["chapters"][0]["visual"] = {"svg": svg, "caption": "DTD, no entities."}
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("must not declare a DTD or entities", r.stderr)

    # ---------------------------------------------------------------- 27: figureLayout
    def test_default_figure_layout_has_no_row_class(self) -> None:
        spec = valid_spec()
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertIn('<div class="figs">', page)
        self.assertNotIn('<div class="figs row">', page)

    def test_figure_layout_row_adds_row_class(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["figureLayout"] = "row"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.out.read_text(encoding="utf-8")
        self.assertIn('<div class="figs row">', page)

    def test_figure_layout_invalid_value_fails_naming_chapter(self) -> None:
        spec = valid_spec()
        spec["chapters"][0]["figureLayout"] = "grid"
        r = self.build(spec, self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn(spec["chapters"][0]["id"], r.stderr)
        self.assertIn("figureLayout", r.stderr)


class ExamplesTest(unittest.TestCase):
    KINDS = ("plan", "execute", "vet", "finish", "research", "grill", "session")

    def build_file(self, spec_path: Path, tmp: Path) -> SimpleNamespace:
        """Builds the example in place so a relative `tree.repo` resolves from its own folder."""
        argv = [str(BUILD), "--spec", str(spec_path), "--out", str(tmp / "o.html"), "--no-mmdc"]
        old_argv, code = sys.argv, 0
        out_buf, err_buf = io.StringIO(), io.StringIO()
        sys.argv = argv
        try:
            with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
                build_brief.main()
        except SystemExit as e:
            code = e.code or 0
        finally:
            sys.argv = old_argv
        return SimpleNamespace(code=code, stdout=out_buf.getvalue(), stderr=err_buf.getvalue())

    def test_one_example_per_kind_and_no_old_example(self) -> None:
        names = sorted(p.name for p in (HERE.parent / "examples").glob("*.example.json"))
        self.assertEqual(names, sorted(f"{k}.example.json" for k in self.KINDS))

    def test_every_example_builds(self) -> None:
        for path in sorted((HERE.parent / "examples").glob("*.example.json")):
            with self.subTest(example=path.name), tempfile.TemporaryDirectory() as tmp:
                r = self.build_file(path, Path(tmp))
                self.assertEqual(r.code, 0, r.stderr)
                kind = json.loads(path.read_text(encoding="utf-8"))["kind"]
                self.assertEqual(path.name, f"{kind}.example.json")


if __name__ == "__main__":
    unittest.main()
