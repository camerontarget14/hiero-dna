# hiero-dna

A Hiero / Nuke Studio plugin that connects Hiero to
[DNA (Dailies Notes Assistant)](https://github.com/AcademySoftwareFoundation/dna).
It signs in to DNA and sets the version in review as you move through a
timeline in Hiero. For RV, see [rv-dna](https://github.com/camerontarget14/rv-dna).

It adds a **DNA** menu to Hiero's menu bar:

- **Signed in as ... — session** / **Not signed in**
- **Playlist: ...**: the playlist chosen at sign-in.
- **Sign In...** / **Sign Out**
- **Choose session...**: the DNA session Hiero drives, or none to use each
  playlist's own session.
- **Switch show/playlist...**: reopen the sign-in window without signing out.
- **Send current version now**: push the clip under the playhead again.
- **Set DNA URL...**: for example `https://dna.example.com` or `http://localhost:5173`.
- **Debug mode**: logs every request/response to the Script Editor / terminal
  (prefixed `hiero_dna:`) and the status bar.

## Requirements

- Hiero or Nuke Studio. Tested with Nuke Studio 17.0v3 on macOS (PySide6).
  The code also supports PySide2 (Nuke 13 to 15), but that is untested.
- A DNA build with sessions (`PUT /sessions/{id}/in-review`). The embedded
  sign-in page also needs the `/desktop-signin` route with payload version 2.

## Install

Hiero only sees `HIERO_PLUGIN_PATH` when it is started from a shell that sets
it, so the simplest install is a small file in your `.nuke` folder. Save this
as `~/.nuke/Python/Startup/hiero_dna_bootstrap.py`, with the path to your
copy of this repo, and restart Hiero:

```python
import sys

sys.path.insert(0, "/path/to/hiero-dna/lib")

from hiero_dna import plugin

plugin.install()
```

Or add the repo root to `HIERO_PLUGIN_PATH`. Hiero then runs
`Python/StartupUI/hiero_dna_startup.py`, which does the same thing:

```sh
export HIERO_PLUGIN_PATH="/path/to/hiero-dna:$HIERO_PLUGIN_PATH"
```

## Sign in

1. Choose **DNA > Sign In...**. If no DNA URL is saved yet, Hiero asks for it.
2. Sign in, then pick a show and a playlist.
3. If the show has DNA sessions, Hiero asks which one to drive. Change it
   later with **DNA > Choose session...**.

Which sign-in window opens depends on the Hiero build:

- **With QtWebEngine:** DNA's `/desktop-signin` page opens inside Hiero.
- **Without QtWebEngine (Nuke 17):** a native dialog asks for the DNA API URL
  and your email, then lists your shows and playlists. The API URL is guessed
  as `http://localhost:8000` for a local web app on port 5173. This dialog only
  works with DNA servers that use email sign-in (`VITE_AUTH_PROVIDER=none`).
  Google sign-in needs the web page.

## Version sync

When the clip under the playhead changes (Hiero's `kPlaybackClipChanged`
event, backed by a 0.5 s poll), Hiero takes the top-most enabled track item
at the playhead (or the clip, when a clip is open in the viewer) and extracts
a version ID with `lib/hiero_dna/version_id_paths.json`:

1. A `_sg_id` tag note (set by the Nuke Timeline Loader)
2. The media file path containing `/file_serve/version/<id>/`
3. A `version_id` metadata value
4. A `sg_version_id` metadata value

Values are read from the track item's tags, the media source, the clip and the
clip's tags. A tag contributes its metadata, and its note under the tag's name.
Tag metadata keys like `tag.version_id` also match `version_id`. Point
`HIERO_DNA_VERSION_ID_PATHS` at your own JSON file to change the rules.

Hiero has no playlist of its own, so it uses the playlist from sign-in. With
a DNA session chosen, it searches the session's playlists (the one already in
review first) for the version.

Hiero only sets a version that is on the playlist, and leaves in-review alone
while it is pinned in DNA. Failures show once in the status bar.

Settings (URL, API URL, sign-in, debug) are stored with
`QSettings("DNA", "hiero-dna")`. The sign-in token is stored in plain text.

## Known limits

- DNA requests run on Hiero's interface thread, so each clip change waits for
  DNA to answer. If DNA is unreachable, Hiero stops trying for 30 seconds.
- In Nuke Studio 17 the viewer does not report what it is playing, so the
  plugin reads the active timeline. A clip opened in the viewer from a bin,
  while a timeline is active, may be read as the timeline item at that frame.
- The native sign-in dialog does not support Google sign-in.
- Hiero has no playlist context of its own. It never follows a playlist you
  open; it uses the sign-in playlist or searches the chosen session.

## Development

```sh
python3 -m unittest discover -s tests -v
```

| File | Purpose |
| --- | --- |
| `Python/StartupUI/hiero_dna_startup.py` | Hiero startup hook. |
| `lib/hiero_dna/plugin.py` | DNA menu, sign in, version sync (Hiero API). |
| `lib/hiero_dna/signin_dialog.py` | Sign-in web view and injected bridge. |
| `lib/hiero_dna/qt.py` | PySide6 / PySide2 compatibility; QtWebEngine optional. |
| `lib/hiero_dna/native_signin_dialog.py`, `directory.py` | Native email sign-in when QtWebEngine is missing. |
| `lib/hiero_dna/fields.py` | Builds the bags the version-ID rules search. |
| `lib/hiero_dna/auth.py` | URL helpers, sign-in payload validation, saved sign-in. |
| `lib/hiero_dna/in_review.py` | DNA API calls and choosing the playlist to set in review on. |
| `lib/hiero_dna/version_id.py` | Version-ID extraction from the search rules. |
| `lib/hiero_dna/version_id_paths.json` | Ordered search rules for version IDs. |

## License

Apache-2.0. See [LICENSE](LICENSE).
