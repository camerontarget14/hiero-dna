#
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Dailies Notes Assistant Project.
#
"""Native sign-in helpers for hosts without QtWebEngine (Nuke 17).

Does what DNA's /desktop-signin page does for the email ("none") auth
provider: the token is the user's email, then the user picks a show and a
playlist from the DNA API.

Pure Python with no Hiero or Qt imports so it can be unit tested outside Hiero.
"""

import json
import urllib.request
from dataclasses import dataclass
from typing import List, Mapping, Optional, Tuple
from urllib.parse import quote, urlsplit

from hiero_dna.auth import PAYLOAD_VERSION, normalize_dna_url
from hiero_dna.in_review import InReviewResult, _bad_response, _json_body, _send_json

# DNA's local stack serves the web app on 5173 and the API on 8000.
_LOCAL_FRONTEND_PORT = 5173
_LOCAL_API_PORT = 8000


@dataclass(frozen=True)
class Choice:
    id: str
    name: str


def default_api_url(dna_url: str) -> str:
    """Best guess at the DNA API URL for a DNA web app URL."""
    url = normalize_dna_url(dna_url)
    parts = urlsplit(url)
    if parts.port == _LOCAL_FRONTEND_PORT:
        return f"{parts.scheme}://{parts.hostname}:{_LOCAL_API_PORT}"
    return url


def email_headers(email: str) -> dict:
    return {"Authorization": f"Bearer {email}"}


def _choices(body, name_keys) -> Optional[List[Choice]]:
    if not isinstance(body, list):
        return None
    out = []
    for raw in body:
        if not isinstance(raw, Mapping) or raw.get("id") is None:
            continue
        name = next((raw.get(k) for k in name_keys if raw.get(k)), None)
        out.append(Choice(id=str(raw["id"]), name=str(name or raw["id"])))
    return out


def list_user_projects(
    api_base_url: str, email: str, opener=urllib.request.urlopen
) -> Tuple[Optional[List[Choice]], InReviewResult]:
    url = f"{api_base_url.rstrip('/')}/projects/user/{quote(email, safe='')}"
    result = _send_json("GET", url, None, email_headers(email), opener)
    if not result.ok:
        return None, result
    choices = _choices(_json_body(result), ("name",))
    if choices is None:
        return None, _bad_response(result, "no project list")
    return choices, result


def list_project_playlists(
    api_base_url: str, email: str, project_id: str, opener=urllib.request.urlopen
) -> Tuple[Optional[List[Choice]], InReviewResult]:
    url = f"{api_base_url.rstrip('/')}/projects/{quote(project_id, safe='')}/playlists"
    result = _send_json("GET", url, None, email_headers(email), opener)
    if not result.ok:
        return None, result
    choices = _choices(_json_body(result), ("code", "name"))
    if choices is None:
        return None, _bad_response(result, "no playlist list")
    return choices, result


def build_payload_json(
    email: str, api_base_url: str, project: Choice, playlist: Choice
) -> str:
    """The same JSON the DNA page hands to desktop apps (payload v2)."""
    return json.dumps(
        {
            "version": PAYLOAD_VERSION,
            "token": email,
            "user": {"id": email, "email": email},
            "authProvider": "none",
            "apiBaseUrl": api_base_url,
            "project": {"id": project.id, "name": project.name},
            "playlist": {"id": playlist.id, "name": playlist.name},
        }
    )
