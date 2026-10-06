#!/usr/bin/env python3
"""Tests for voice.py.

Run from this directory:
    python3 -m unittest test_voice.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import voice  # noqa: E402


class IssuesTest(unittest.TestCase):
    def test_clean_label_passes(self):
        self.assertEqual(voice.issues("The worker retries with backoff.", "label"), [])

    def test_replace_word_names_the_fix(self):
        got = voice.issues("We utilize a queue.", "label")
        self.assertEqual(got, ['"utilize" → "use"'])

    def test_stem_catches_inflection(self):
        self.assertEqual(voice.issues("This ensures order.", "label"), ['"ensures" → "make sure"'])

    def test_banned_word(self):
        self.assertEqual(voice.issues("A robust fix.", "label"), ['"robust" is banned'])

    def test_banned_phrase_case_insensitive(self):
        self.assertEqual(voice.issues("Worth noting: it fails.", "label"), ['"Worth noting" is banned'])

    def test_em_dash(self):
        self.assertEqual(voice.issues("Fast — and safe.", "label"), ["em dash; split the sentence"])

    def test_code_span_exempt(self):
        self.assertEqual(voice.issues("Call `ensure_ready()` first.", "label"), [])

    def test_html_code_exempt_in_prose(self):
        self.assertEqual(voice.issues("<p>Call <code>leverage()</code> first.</p>", "prose"), [])

    def test_label_word_cap(self):
        text = " ".join(["word"] * 13) + "."
        self.assertEqual(voice.issues(text, "label"), ["13 words; keep to 12"])

    def test_label_one_sentence(self):
        self.assertEqual(voice.issues("One. Two.", "label"), ["2 sentences; keep to 1"])

    def test_instruction_sentence_cap(self):
        text = " ".join(["word"] * 21) + "."
        self.assertEqual(voice.issues(text, "instruction"), ['a sentence is 21 words, over 20: "word word word word word ..."'])

    def test_instruction_two_sentences_max(self):
        self.assertEqual(voice.issues("A. B. C.", "instruction"), ["3 sentences; keep to 2"])

    def test_prose_sentence_cap(self):
        text = "<p>" + " ".join(["word"] * 26) + ".</p>"
        self.assertEqual(voice.issues(text, "prose"), ['a sentence is 26 words, over 25: "word word word word word ..."'])

    def test_prose_max_sentences(self):
        self.assertEqual(voice.issues("<p>A. B. C.</p>", "prose", max_sentences=2), ["3 sentences; keep to 2"])

    def test_literal_never_checked(self):
        self.assertEqual(voice.issues("utilize — robust", "literal"), [])


class CheckFieldTest(unittest.TestCase):
    def test_check_field_fails_with_where(self):
        with self.assertRaises(SystemExit):
            voice.check_field("panel B why", "We utilize it.", "instruction")

    def test_check_field_passes_clean(self):
        voice.check_field("panel B why", "We use it.", "instruction")

    def test_table_cells_are_separate_sentences(self):
        table = "<table><tr><td>" + " ".join(["word"] * 15) + "</td><td>" + " ".join(["word"] * 15) + "</td></tr></table>"
        self.assertEqual(voice.issues(table, "prose"), [])


if __name__ == "__main__":
    unittest.main()
