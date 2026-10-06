import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dock  # noqa: E402


class DockTest(unittest.TestCase):
    def test_one_dock_with_send_toast_and_popover(self):
        html = dock.render_dock("proj", "feat/x", False)
        self.assertEqual(html.count('class="dock"'), 1)
        for needle in ('data-project="proj"', 'data-branch="feat/x"', "data-export ", "data-export-status hidden",
                       '<div class="dock-pop" hidden>', "data-export-preview", "data-pop-close", ">Send feedback<"):
            self.assertIn(needle, html)

    def test_back_button_only_when_asked(self):
        self.assertNotIn("tosheet", dock.render_dock("p", None, False))
        self.assertEqual(dock.render_dock("p", None, True).count('class="tosheet"'), 1)
        self.assertNotIn("data-branch", dock.render_dock("p", None, True))

    def test_values_are_escaped(self):
        self.assertIn('data-project="a&lt;b&quot;"', dock.render_dock('a<b"', None, False))

    def test_assets_need_no_sheet(self):
        css, js = dock.assets()
        self.assertIn(".dock{", css)
        self.assertIn("var dockCollect", js)
        self.assertNotIn("sheetAnswers", js)
