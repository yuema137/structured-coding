#!/usr/bin/env python3
"""Regression checks for the generated bilingual human presentation.

Run with: python3 scripts/test_human_docs.py
No browser, network, or third-party dependencies are required.
"""

import copy
import html
import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import build_human_docs as docs


class HumanDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = [
            json.loads((docs.ROOT / f"docs/content.{lang}.json").read_text())
            for lang in ("en", "zh-CN")
        ]
        cls.outputs = docs.expected_outputs()

    def test_generated_outputs_are_current(self):
        docs.check()
        self.assertEqual(len(self.outputs), 12)

    def test_mirror_structure_and_preserved_prompts(self):
        english, chinese = self.sources
        self.assertEqual(set(english), set(chinese))
        for key, value in english.items():
            if isinstance(value, list):
                self.assertEqual(len(value), len(chinese[key]), key)
                for item, mirror in zip(value, chinese[key]):
                    if isinstance(item, list):
                        self.assertEqual(len(item), len(mirror), key)
        self.assertEqual(english["prompts"], chinese["prompts"])
        self.assertEqual(len(english["prompts"]), 3)
        for key, value in english.items():
            if key != "switch":
                self.assertIsNone(re.search(r"[\u4e00-\u9fff]", str(value)), key)

    def test_html_order_and_progressive_disclosure(self):
        for source in self.sources:
            page = docs.render_html(source)
            order = [
                page.index(f'id="{key}"')
                for key in ("why", "workflow", "kit", "start", "roles", "sessions", "tutorial", "people", "technical")
            ]
            self.assertEqual(order, sorted(order))
            self.assertEqual(page.count('class="flow-node"'), 6)
            self.assertEqual(page.count('class="kit-card"'), 6)
            self.assertEqual(page.count("<details "), 5)
            self.assertNotRegex(page, r"<details[^>]*\bopen\b")
            self.assertEqual(page.count("<h1>"), 1)
            self.assertIn(f'<html lang="{source["lang"]}"', page)
            self.assertNotRegex(page, r'<(?:script|link)[^>]*(?:src|href)="https?://')

    def test_complete_tutorial_reaches_all_human_formats(self):
        for source in self.sources:
            page = docs.render_html(source)
            visible = page[:page.index('<section class="block technical"')]
            readmes = (docs.render_readme(source), docs.render_package_guide(source))
            for step in source["tutorial"]:
                for value in [step["title"], *step["paragraphs"], step["checkpoint"]]:
                    self.assertIn(html.escape(value, quote=True), visible)
                    for readme in readmes:
                        self.assertIn(value, readme)
                index = step["promptIndex"]
                if index is not None:
                    self.assertIn(html.escape(source["prompts"][index], quote=True), visible)
                    for readme in readmes:
                        self.assertIn(source["prompts"][index], readme)
            self.assertNotIn("docs/assets/", readmes[1])
            self.assertNotIn("](structured-coding/", readmes[1])

    def test_tutorial_mirror_errors_are_rejected(self):
        english, chinese = self.sources
        shortened = copy.deepcopy(chinese)
        shortened["tutorial"].pop()
        with self.assertRaises(ValueError):
            docs.check_tutorial_mirrors(english, shortened)
        for mutation in ("paragraph", "prompt", "fields", "index"):
            mirror = copy.deepcopy(chinese)
            step = mirror["tutorial"][0]
            if mutation == "paragraph":
                step["paragraphs"].pop()
            elif mutation == "prompt":
                step["promptIndex"] = 1
            elif mutation == "fields":
                step["extra"] = "unexpected"
            else:
                step["promptIndex"] = len(mirror["prompts"])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                docs.check_tutorial_mirrors(english, mirror)

    def test_tutorial_html_escapes_content(self):
        source = copy.deepcopy(self.sources[0])
        source["tutorial"][0]["paragraphs"] = ['<script>alert("x")</script>']
        rendered = docs.tutorial_html(source)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_diagrams_are_portable_and_have_connected_arrows(self):
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        for relative, markup in self.outputs.items():
            if not relative.endswith(".svg"):
                continue
            root = ET.fromstring(markup)
            self.assertIsNotNone(root.find("svg:title", namespace))
            self.assertIsNone(root.find(".//svg:foreignObject", namespace))
            if "workflow" in relative:
                _, _, width, height = map(float, root.attrib["viewBox"].split())
                self.assertEqual(width / height, 1.5)
                arrows = root.findall(".//svg:path[@marker-end]", namespace)
                self.assertEqual(len(arrows), 6)  # Five forward edges + next-PR loop.

    def test_chinese_wrapping_preserves_english_terms(self):
        lines = docs.wrap_svg("新 session · coding · 验证 · commit", 33)
        self.assertTrue(any("commit" in line for line in lines))
        self.assertTrue(any("session" in line for line in lines))
        self.assertTrue(all(line == line.strip() for line in lines))

    def test_link_validation_rejects_missing_targets_and_duplicate_ids(self):
        for markup in (
            '<a href="#missing">x</a>',
            '<img src="absent.png">',
            '<a href="../../outside.md">x</a>',
            '<p id="a"></p><p id="a"></p>',
        ):
            with self.subTest(markup=markup), self.assertRaises(ValueError):
                docs.check_links("docs/index.html", markup)

    def test_stale_generated_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(docs, "ROOT", Path(directory)):
                with patch.object(
                    docs, "expected_outputs", return_value={"README.md": "new"}
                ):
                    with self.assertRaisesRegex(
                        ValueError, "Human presentation is stale"
                    ):
                        docs.check()


if __name__ == "__main__":
    unittest.main()
