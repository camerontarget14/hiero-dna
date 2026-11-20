#
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Dailies Notes Assistant Project.
#
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

from hiero_dna.auth import parse_auth_payload  # noqa: E402
from hiero_dna.directory import (  # noqa: E402
    Choice,
    build_payload_json,
    default_api_url,
    list_project_playlists,
    list_user_projects,
)


class _Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def opener_for(body, seen):
    def opener(request, timeout=None):
        seen.append(request)
        return _Response(json.dumps(body).encode())

    return opener


class DirectoryTest(unittest.TestCase):
    def test_default_api_url(self):
        self.assertEqual(default_api_url("localhost:5173"), "http://localhost:8000")
        self.assertEqual(default_api_url("https://dna.example.com/"), "https://dna.example.com")

    def test_list_user_projects(self):
        seen = []
        projects, result = list_user_projects(
            "http://api", "a@b.com", opener_for([{"id": 1, "name": "Show"}, {"x": 1}], seen)
        )
        self.assertTrue(result.ok)
        self.assertEqual(projects, [Choice("1", "Show")])
        self.assertEqual(seen[0].full_url, "http://api/projects/user/a%40b.com")
        self.assertEqual(seen[0].get_header("Authorization"), "Bearer a@b.com")

    def test_list_project_playlists_uses_code(self):
        playlists, _ = list_project_playlists(
            "http://api/", "a@b.com", "7", opener_for([{"id": 45, "code": "Dailies"}, {"id": 46}], [])
        )
        self.assertEqual(playlists, [Choice("45", "Dailies"), Choice("46", "46")])

    def test_bad_body(self):
        projects, result = list_user_projects("http://api", "a", opener_for({"no": 1}, []))
        self.assertIsNone(projects)
        self.assertFalse(result.ok)

    def test_payload_parses(self):
        payload = build_payload_json(
            "a@b.com", "http://localhost:8000", Choice("1", "Show"), Choice("45", "Dailies")
        )
        session = parse_auth_payload(payload, "http://localhost:5173")
        self.assertEqual(session.token, "a@b.com")
        self.assertEqual(session.playlist.display_name, "Dailies")
        self.assertEqual(session.api_base_url, "http://localhost:8000")


if __name__ == "__main__":
    unittest.main()
