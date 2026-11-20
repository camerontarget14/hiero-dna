#
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Dailies Notes Assistant Project.
#
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

from hiero_dna.fields import build_fields  # noqa: E402
from hiero_dna.version_id import extract_version_id  # noqa: E402


class BuildFieldsTest(unittest.TestCase):
    def test_file_path_becomes_file_property(self):
        props, meta = build_fields("/x/file_serve/version/123/a.mov", [])
        self.assertEqual(props, {"File": "/x/file_serve/version/123/a.mov"})
        self.assertEqual(meta, {})
        self.assertEqual(extract_version_id(props, meta), "123")

    def test_tag_prefix_is_also_stripped(self):
        props, meta = build_fields(None, [("tag.version_id", "77")])
        self.assertEqual(meta["tag.version_id"], "77")
        self.assertEqual(meta["version_id"], "77")
        self.assertEqual(extract_version_id(props, meta), "77")

    def test_first_value_wins_and_empty_values_skipped(self):
        _, meta = build_fields(
            None, [("version_id", ""), ("version_id", "1"), ("tag.version_id", "2")]
        )
        self.assertEqual(meta["version_id"], "1")

    def test_sg_version_id(self):
        props, meta = build_fields(None, [("tag.sg_version_id", "9")])
        self.assertEqual(extract_version_id(props, meta), "9")


if __name__ == "__main__":
    unittest.main()
