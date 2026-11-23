import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, ".agent-board", "marketplace.json")

NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
TOP_KEYS = {"protocol", "name", "description", "feeds"}
FEED_KEYS = {"program", "description"}
MAX_BYTES = 64 * 1024
MAX_FEEDS = 50
MAX_TEXT = 300
MAX_PROGRAM = 200


class MarketplaceManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MANIFEST, "rb") as handle:
            raw = handle.read()
        cls.size = len(raw)
        cls.manifest = json.loads(raw.decode("utf-8"))

    def test_top_level_shape(self):
        self.assertLessEqual(self.size, MAX_BYTES)
        self.assertIsInstance(self.manifest, dict)
        self.assertLessEqual(set(self.manifest), TOP_KEYS)
        self.assertEqual(self.manifest["protocol"], 1)
        self.assertRegex(self.manifest["name"], NAME)
        description = self.manifest.get("description")
        if description is not None:
            self.assertIsInstance(description, str)
            self.assertLessEqual(len(description), MAX_TEXT)
        self.assertIsInstance(self.manifest["feeds"], dict)
        self.assertLessEqual(len(self.manifest["feeds"]), MAX_FEEDS)

    def test_every_feed_is_valid(self):
        for key, feed in self.manifest["feeds"].items():
            with self.subTest(feed=key):
                self.assertRegex(key, NAME)
                self.assertIsInstance(feed, dict)
                self.assertLessEqual(set(feed), FEED_KEYS)
                self.assertIsInstance(feed["program"], str)
                self.assertLessEqual(len(feed["program"]), MAX_PROGRAM)
                description = feed.get("description")
                if description is not None:
                    self.assertIsInstance(description, str)
                    self.assertLessEqual(len(description), MAX_TEXT)

    def test_every_program_is_an_executable_regular_file(self):
        for key, feed in self.manifest["feeds"].items():
            with self.subTest(feed=key):
                segments = feed["program"].split("/")
                for segment in segments:
                    self.assertRegex(segment, SEGMENT)
                    self.assertNotIn(segment, (".", ".."))
                path = os.path.join(ROOT, *segments)
                self.assertFalse(os.path.islink(path), "program is a symlink")
                self.assertTrue(os.path.isfile(path), "program is not a file")
                self.assertTrue(os.access(path, os.X_OK), "program is not executable")


if __name__ == "__main__":
    unittest.main()
