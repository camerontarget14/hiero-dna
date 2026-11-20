#
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Dailies Notes Assistant Project.
#
"""Build the property/metadata bags the version-ID extractor searches.

Pure Python with no Hiero or Qt imports so it can be unit tested outside Hiero.
"""

from typing import Any, Iterable, Optional, Tuple

TAG_PREFIX = "tag."


def build_fields(
    file_path: Optional[str],
    metadata_items: Iterable[Tuple[str, Any]],
) -> Tuple[dict, dict]:
    """Return ``(properties, metadata)`` for one clip.

    ``file_path`` becomes the ``File`` property. ``metadata_items`` are
    ``(key, value)`` pairs from the media source, the clip and its tags, in
    priority order (first wins). Hiero prefixes tag metadata keys with
    ``tag.``; each such key is also available without the prefix, so a tag
    holding ``tag.version_id`` matches a ``version_id`` search step.
    """
    properties = {}
    metadata = {}
    if file_path:
        properties["File"] = file_path
    for key, value in metadata_items:
        if not isinstance(key, str) or value is None or value == "":
            continue
        names = [key]
        if key.startswith(TAG_PREFIX) and len(key) > len(TAG_PREFIX):
            names.append(key[len(TAG_PREFIX):])
        for name in names:
            metadata.setdefault(name, value)
            # Search steps may name either source.
            properties.setdefault(name, value)
    return properties, metadata
