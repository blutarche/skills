#!/usr/bin/env python3
"""Tests for svg.py. Run from this directory: python3 -m unittest test_svg.py"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import svg  # noqa: E402

OK = '<svg viewBox="0 0 10 10"><rect x="1" y="1" width="8" height="8" data-s="1 2"/></svg>'


class ValidateTest(unittest.TestCase):
    def test_data_s_allowed_and_kept(self):
        out = svg.validate_figure(OK, "panel D", "fD-")
        self.assertIn('data-s="1 2"', out)

    def test_step_ids_collected(self):
        self.assertEqual(svg.step_ids(OK), {1, 2})

    def test_bad_data_s_token_fails(self):
        bad = OK.replace('data-s="1 2"', 'data-s="1 x"')
        with self.assertRaises(SystemExit):
            svg.validate_figure(bad, "panel D", "fD-")

    def test_script_still_refused(self):
        with self.assertRaises(SystemExit):
            svg.validate_figure('<svg viewBox="0 0 1 1"><script/></svg>', "panel D", "fD-")

    def test_ids_scoped_with_prefix(self):
        src = '<svg viewBox="0 0 1 1"><defs><marker id="ar"/></defs><path d="M0 0" marker-end="url(#ar)"/></svg>'
        out = svg.validate_figure(src, "panel D", "fD-")
        self.assertIn('id="fD-ar"', out)
        self.assertIn("url(#fD-ar)", out)


if __name__ == "__main__":
    unittest.main()
