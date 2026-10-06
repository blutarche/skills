#!/usr/bin/env python3
"""Tests for figures.py.

Run from this directory:
    python3 -m unittest test_figures.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import figures  # noqa: E402


class WavesTest(unittest.TestCase):
    TASKS = [
        {"id": "T1", "name": "Store", "status": "done"},
        {"id": "T2", "name": "Worker", "status": "done", "after": ["T1"]},
        {"id": "T3", "name": "Route", "status": "failed", "after": ["T1"]},
        {"id": "T4", "name": "Docs", "status": "todo", "after": ["T2", "T3"]},
    ]

    def test_wave_numbers(self):
        self.assertEqual(figures.waves(self.TASKS), {"T1": 0, "T2": 1, "T3": 1, "T4": 2})

    def test_cycle_fails(self):
        bad = [{"id": "A", "after": ["B"]}, {"id": "B", "after": ["A"]}]
        with self.assertRaises(SystemExit):
            figures.waves(bad)

    def test_unknown_after_fails(self):
        with self.assertRaises(SystemExit):
            figures.waves([{"id": "A", "after": ["Z"]}])

    def test_svg_has_one_box_per_task_and_status_class(self):
        out = figures.task_waves_svg(self.TASKS)
        self.assertEqual(out.count('class="task '), 4)
        self.assertIn("n-failed", out)
        self.assertIn('aria-label="4 tasks in 3 waves: 2 done, 1 failed, 1 to do"', out)

    def test_task_with_more_is_a_click_target(self):
        tasks = [{"id": "T1", "name": "A", "status": "done", "more": "x", "moreN": 2, "moreTitle": "The <x>"},
                 {"id": "T2", "name": "B", "status": "done"}]
        out = figures.task_waves_svg(tasks)
        self.assertEqual(out.count("data-go="), 1)
        self.assertIn('<g class="task n-done go" data-go="ch-x">', out)
        self.assertIn("<title>Section 2: The &lt;x&gt;</title>", out)
        self.assertEqual(out.count("<title>"), 1)

    def test_svg_escapes_names(self):
        tasks = [{"id": "T1", "name": "<b>x</b>", "status": "done"}]
        self.assertNotIn("<b>", figures.task_waves_svg(tasks))

    def test_graph_is_never_scaled_above_its_natural_size(self):
        one = figures.task_waves_svg([{"id": "T1", "name": "Only", "status": "done"}])
        w = figures.BOX_W + 2 * figures.PAD
        self.assertIn(f'viewBox="0 0 {w} ', one)
        self.assertIn(f'style="min-width:min(600px,{w}px);max-width:min(880px,{w}px)"', one)
        five = figures.task_waves_svg([{"id": f"T{i}", "name": "n", "status": "todo"} for i in range(1, 6)])
        self.assertIn("max-width:min(880px,", five)


class VennTest(unittest.TestCase):
    def test_counts(self):
        rows = [{"foundBy": ["a", "b"]}, {"foundBy": ["a"]}, {"foundBy": ["b"]}, {"foundBy": ["b"]}]
        self.assertEqual(figures.venn_counts(rows), (["a", "b"], 1, 2, 1))

    def test_none_when_not_two_reviewers(self):
        self.assertIsNone(figures.venn_svg([{"foundBy": ["a"]}]))

    def test_svg_label_states_numbers(self):
        rows = [{"foundBy": ["a", "b"]}, {"foundBy": ["b"]}]
        out = figures.venn_svg(rows)
        self.assertIn('aria-label="a found 1, b found 2, both found 1"', out)
        self.assertIn("rv-a", out)
        self.assertIn("rv-b", out)


class StripTest(unittest.TestCase):
    def test_severity_strip_skips_zero(self):
        out = figures.severity_strip([{"sev": "P0"}, {"sev": "P2"}, {"sev": "P2"}])
        self.assertIn("P0 1", out)
        self.assertIn("P2 2", out)
        self.assertNotIn("P1", out)


class TreeTest(unittest.TestCase):
    def test_nested_list(self):
        rows = [{"id": "a", "decision": "Root"}, {"id": "b", "decision": "Child", "parent": "a"}]
        out = figures.decision_tree(rows)
        self.assertRegex(out, r'<ul class="tree"><li>.*Root.*<ul><li>.*Child')

    def test_unknown_parent_fails(self):
        with self.assertRaises(SystemExit):
            figures.decision_tree([{"id": "b", "decision": "x", "parent": "zz"}])


class MatrixTest(unittest.TestCase):
    def test_cell_holds_id(self):
        out = figures.heat_matrix([{"id": "R1", "label": "x", "likelihood": "high", "impact": "low"}])
        self.assertIn('data-cell="high-low"', out)
        self.assertIn("R1", out)

    def test_axis_labels(self):
        out = figures.heat_matrix([{"id": "R1", "label": "x", "likelihood": "high", "impact": "low"}])
        for word in ("likelihood", "impact", "low", "med", "high"):
            self.assertIn(word, out)
        self.assertEqual(out.count('class="ax-x"'), 3)


class ClaimStackTest(unittest.TestCase):
    def test_counts_in_label(self):
        rows = [{"result": "verified"}, {"result": "verified"}, {"result": "corrected"}]
        self.assertIn("2 verified", figures.claim_stack(rows))

    def test_bars_carry_result_word(self):
        rows = [{"result": "verified"}, {"result": "verified"}, {"result": "corrected"}]
        out = figures.claim_stack(rows)
        self.assertIn(">verified 2</span>", out)
        self.assertIn(">corrected 1</span>", out)
        self.assertIn('title="verified 2"', out)


if __name__ == "__main__":
    unittest.main()
