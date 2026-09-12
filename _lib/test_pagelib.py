#!/usr/bin/env python3
"""Tests for pagelib.py.

Run from this directory:
    python3 -m unittest test_pagelib.py
    python3 test_pagelib.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pagelib  # noqa: E402  (needs sys.path set up above)


class AssembleTest(unittest.TestCase):
    SHELL = (
        "<!doctype html><html><head>"
        "<!-- TITLE:START --><title>x</title><!-- TITLE:END -->"
        "<!-- STYLE:START --><style>body{color:red}</style><!-- STYLE:END -->"
        "</head><body>"
        "<!-- BODY:START --><!-- BODY:END -->"
        "<!-- SCRIPT:START --><script>var x=1;</script><!-- SCRIPT:END -->"
        "</body></html>"
    )

    def test_document_has_title_and_body_spliced_in(self) -> None:
        document, _ = pagelib.assemble(self.SHELL, "My Title", "<p>hello</p>")
        self.assertIn("<title>My Title</title>", document)
        self.assertIn("<p>hello</p>", document)
        # the style/script regions pass through untouched in the document
        self.assertIn("<style>body{color:red}</style>", document)
        self.assertIn("<script>var x=1;</script>", document)

    def test_fragment_has_no_document_wrappers(self) -> None:
        _, fragment = pagelib.assemble(self.SHELL, "My Title", "<p>hello</p>")
        for wrapper in ("<!doctype", "<html", "<head", "<body"):
            self.assertNotIn(wrapper, fragment.lower())
        self.assertTrue(fragment.startswith("<title>My Title</title>"))
        self.assertIn("<p>hello</p>", fragment)
        self.assertIn("body{color:red}", fragment)
        self.assertIn("var x=1;", fragment)

    def test_missing_marker_fails(self) -> None:
        broken = self.SHELL.replace("<!-- BODY:START -->", "")
        with self.assertRaises(SystemExit):
            pagelib.assemble(broken, "t", "b")


class SanitizeProseTest(unittest.TestCase):
    def test_script_tag_dropped_its_text_kept(self) -> None:
        out = pagelib.sanitize_prose("<p>Fine.</p><script>alert(1)</script>")
        self.assertEqual(out, "<p>Fine.</p>alert(1)")

    def test_img_onerror_is_stripped(self) -> None:
        out = pagelib.sanitize_prose("<img src=x onerror=alert(1)>")
        self.assertNotIn("<img", out.lower())
        self.assertNotIn("onerror", out.lower())

    def test_entity_obscured_javascript_href_is_dropped(self) -> None:
        out = pagelib.sanitize_prose('<a href="&#x6a;avascript:alert(1)">click</a>')
        self.assertEqual(out, "<a>click</a>")
        self.assertNotIn("javascript", out.lower())

    def test_hash_href_survives(self) -> None:
        out = pagelib.sanitize_prose('<a href="#ch-core">jump</a>')
        self.assertEqual(out, '<a href="#ch-core">jump</a>')

    def test_base_and_form_are_stripped(self) -> None:
        out = pagelib.sanitize_prose(
            '<base href="https://evil.example/">'
            '<form action="https://evil.example/x" method="post"></form>'
        )
        self.assertNotIn("<base", out.lower())
        self.assertNotIn("<form", out.lower())
        self.assertNotIn("evil.example", out)

    def test_non_string_input_returns_empty(self) -> None:
        self.assertEqual(pagelib.sanitize_prose(None), "")
        self.assertEqual(pagelib.sanitize_prose(42), "")


if __name__ == "__main__":
    unittest.main()
