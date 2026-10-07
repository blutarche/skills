#!/usr/bin/env python3
"""Tests for layout_check.py: the pure rules and the probe JSON parsing. No browser needed.

Run from this directory:
    python3 -m unittest test_layout_check.py
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import layout_check  # noqa: E402  (needs sys.path set up above)


def good() -> dict:
    return {
        "viewport": {"innerWidth": 1280, "scrollWidth": 1280},
        "headers": [{
            "id": "panel-A", "top": 100, "bottom": 140, "borderTop": 0, "borderBottom": 2,
            "paddingTop": 0, "paddingBottom": 0, "scrollWidth": 300, "clientWidth": 300,
            "children": [
                {"name": "ltr", "top": 100, "bottom": 138},
                {"name": "note-btn", "top": 100, "bottom": 138},
            ],
        }],
        "files": [{"id": "panel-C", "rows": [
            {"bar": 200, "add": 400, "del": 440},
            {"bar": 200, "add": 400, "del": 440},
        ]}],
    }


class CheckTest(unittest.TestCase):
    def test_good_boxes_pass(self) -> None:
        self.assertEqual(layout_check.check(good(), 1280), [])

    def test_child_short_of_the_header_edge_fails(self) -> None:
        boxes = good()
        boxes["headers"][0]["children"][0]["bottom"] = 130
        fails = layout_check.check(boxes, 720)
        self.assertEqual(len(fails), 1)
        self.assertIn("720", fails[0])
        self.assertIn("panel-A", fails[0])
        self.assertIn("ltr", fails[0])

    def test_one_pixel_slack_passes(self) -> None:
        boxes = good()
        boxes["headers"][0]["children"][0]["bottom"] = 137.2
        self.assertEqual(layout_check.check(boxes, 1280), [])

    def test_header_padding_fails(self) -> None:
        boxes = good()
        boxes["headers"][0]["paddingBottom"] = 8
        fails = layout_check.check(boxes, 390)
        self.assertTrue(any("padding" in f and "panel-A" in f and "390" in f for f in fails), fails)

    def test_sideways_scroll_fails(self) -> None:
        boxes = good()
        boxes["viewport"]["scrollWidth"] = 1500
        fails = layout_check.check(boxes, 1280)
        self.assertEqual(len(fails), 1)
        self.assertIn("sideways", fails[0])

    def test_header_overflow_fails(self) -> None:
        boxes = good()
        boxes["headers"][0]["scrollWidth"] = 340
        fails = layout_check.check(boxes, 390)
        self.assertTrue(any("panel-A" in f and "wider" in f for f in fails), fails)

    def test_misaligned_add_column_fails(self) -> None:
        boxes = good()
        boxes["files"][0]["rows"][1]["add"] = 412
        fails = layout_check.check(boxes, 1280)
        self.assertEqual(len(fails), 1)
        self.assertIn("panel-C", fails[0])
        self.assertIn("+N", fails[0])

    def test_misaligned_bar_and_del_columns_fail(self) -> None:
        boxes = good()
        boxes["files"][0]["rows"][1]["bar"] = 230
        boxes["files"][0]["rows"][1]["del"] = 470
        self.assertEqual(len(layout_check.check(boxes, 1280)), 2)

    def test_binary_rows_without_columns_are_skipped(self) -> None:
        boxes = good()
        boxes["files"][0]["rows"].append({"bar": None, "add": None, "del": None})
        self.assertEqual(layout_check.check(boxes, 1280), [])

    def test_input_is_not_mutated(self) -> None:
        boxes = good()
        before = copy.deepcopy(boxes)
        layout_check.check(boxes, 1280)
        self.assertEqual(boxes, before)


class ParseTest(unittest.TestCase):
    def test_probe_json_is_read_from_the_dumped_dom(self) -> None:
        data = good()
        dom = ('<html><body><p>x</p><script type="application/json" id="layout-probe">'
               + json.dumps(data) + "</script></body></html>")
        self.assertEqual(layout_check.parse_probe(dom), data)

    def test_missing_probe_json_raises(self) -> None:
        with self.assertRaises(layout_check.BrowserError):
            layout_check.parse_probe("<html><body></body></html>")

    def test_bad_probe_json_raises(self) -> None:
        dom = '<script type="application/json" id="layout-probe">{nope</script>'
        with self.assertRaises(layout_check.BrowserError):
            layout_check.parse_probe(dom)

    def test_inline_puts_the_probe_before_the_last_body_close(self) -> None:
        page = "<body><script>var s='</body>';</script></body>"
        out = layout_check.inline_probe(page, "PROBE")
        self.assertTrue(out.endswith("<script>PROBE</script></body>"))
        self.assertEqual(out.count("PROBE"), 1)


if __name__ == "__main__":
    unittest.main()
