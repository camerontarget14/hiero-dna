# hiero-dna

A Hiero / Nuke Studio plugin that connects Hiero to
[DNA (Dailies Notes Assistant)](https://github.com/AcademySoftwareFoundation/dna).
It is the Hiero counterpart of [rv-dna](https://github.com/camerontarget14/rv-dna)
and shares its sign-in flow, API calls and version-ID rules.

It adds a **DNA** menu to Hiero's menu bar:

- **Signed in as ... — session** / **Not signed in**
- **Playlist: ...**: the playlist chosen at sign-in.
- **Sign In...** / **Sign Out**: opens DNA's `/desktop-signin` page in a window
  inside Hiero.
- **Choose session...**: the DNA session Hiero drives, or none to use each
  playlist's own session.
- **Switch show/playlist...**: reopen the sign-in page without signing out.
- **Send current version now**: push the clip under the playhead again.
- **Set DNA URL...**: for example `https://dna.example.com` or `http://localhost:5173`.
- **Debug mode**: logs every request/response to the Script Editor / terminal
  (prefixed `hiero_dna:`) and the status bar.

## Requirements

- Hiero / Nuke Studio 13+ (PySide2) or 16+ (PySide6), with QtWebEngine.
- A DNA build with sessions (`PUT /sessions/{id}/in-review`, `/desktop-signin`
  payload version 2).

## Install

Add this repo's root to `HIERO_PLUGIN_PATH` and restart Hiero:

```sh
export HIERO_PLUGIN_PATH="/path/to/hiero-dna:$HIERO_PLUGIN_PATH"
```

Hiero runs `Python/Startup/hiero_dna_startup.py`, which puts `lib/` on
`sys.path` and installs the menu. (Alternatively copy both folders into
`~/.nuke/`.)

## Version sync

When the clip under the playhead changes (Hiero's `kPlaybackClipChanged`
event, backed by a 0.5 s poll), Hiero takes the top-most enabled track item
at the playhead (or the clip, when a clip is open in the viewer) and extracts
a version ID with `lib/hiero_dna/version_id_paths.json`:

1. The media file path containing `/file_serve/version/<id>/`
2. A `version_id` metadata value
3. A `sg_version_id` metadata value

Metadata is read from the track item's tags, the media source, the clip and
the clip's tags. Tag keys like `tag.version_id` also match `version_id`.
Point `HIERO_DNA_VERSION_ID_PATHS` at your own JSON to change the rules.

Hiero has no Screening Room playlist context, so it uses the playlist from
sign-in. With a DNA session chosen, it searches the session's playlists
(the one already in review first) for the version.

Settings (URL, session, debug) are stored with `QSettings("DNA", "hiero-dna")`.
The session token is stored in plain text.

## Development

```sh
python3 -m unittest discover -s tests -v
```

| File | Purpose |
| --- | --- |
| `Python/Startup/hiero_dna_startup.py` | Hiero startup hook. |
| `lib/hiero_dna/plugin.py` | DNA menu, sign in, version sync (Hiero API). |
| `lib/hiero_dna/signin_dialog.py` | Sign-in web view and injected bridge. |
| `lib/hiero_dna/qt.py` | PySide6 / PySide2 compatibility. |
| `lib/hiero_dna/fields.py` | Builds the bags the version-ID rules search. |
| `lib/hiero_dna/auth.py`, `in_review.py`, `version_id.py` | Ported unchanged from rv-dna. No Hiero or Qt imports. |
