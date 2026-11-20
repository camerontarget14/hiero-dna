#
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Dailies Notes Assistant Project.
#
"""Hiero plugin: a DNA menu that signs in and pushes in-review versions."""

import time

import hiero.core
import hiero.ui

from hiero_dna.auth import DnaEntityRef, SessionStore
from hiero_dna.fields import build_fields
from hiero_dna.in_review import (
    choose_playlist,
    ensure_session_for_playlist,
    get_playlist_version_ids,
    get_session,
    list_project_sessions,
    set_in_review,
    suggest_session,
)
from hiero_dna.qt import HAS_WEBENGINE, QtCore, QtWidgets, exec_dialog
from hiero_dna.version_id import extract_version_id, load_version_id_paths

SETTINGS_ORG = "DNA"
SETTINGS_APP = "hiero-dna"
DEBUG_SETTING = "debug"
API_URL_SETTING = "api_url"

# DNA refusals that are expected in normal use and stay quiet outside debug
# mode: 409 in-review pinned.
EXPECTED_REFUSALS = (409,)

# How long a playlist's version list is reused before asking DNA again.
PLAYLIST_VERSIONS_TTL_S = 30.0

NO_SESSION_LABEL = "No session (each playlist's own)"

# Hiero sends kPlaybackClipChanged when the clip under the playhead changes.
# A light poll backs it up (scrubbing, switching viewers, loading a sequence).
POLL_INTERVAL_MS = 500

LOG_PREFIX = "hiero_dna:"


def _settings():
    return QtCore.QSettings(SETTINGS_ORG, SETTINGS_APP)


def _read_setting(name, default):
    value = _settings().value(name, default)
    return default if value is None else str(value)


def _write_setting(name, value):
    settings = _settings()
    settings.setValue(name, value)
    settings.sync()


def _main_window():
    return hiero.ui.mainWindow()


# --- What is on screen -------------------------------------------------------


def _current_clip():
    """The clip under the playhead in the current viewer, or None.

    For a sequence, the clip of the top-most enabled track item at the
    current time; for a clip opened on its own, the clip itself.
    """
    viewer = hiero.ui.currentViewer()
    if viewer is None:
        return None, None
    try:
        player = viewer.player()
        sequence = player.sequence() if player else None
        frame = viewer.time()
    except Exception:
        return None, None
    if sequence is None:
        return None, None
    if isinstance(sequence, hiero.core.Clip):
        return sequence, None

    try:
        tracks = list(sequence.videoTracks())
    except Exception:
        return None, None
    for track in reversed(tracks):  # top track first
        if not track.isEnabled():
            continue
        for item in track.items():
            if not item.isEnabled():
                continue
            if item.timelineIn() <= frame <= item.timelineOut():
                source = item.source()
                if isinstance(source, hiero.core.Clip):
                    return source, item
    return None, None


def _data_items(collection):
    """(key, value) pairs from a Hiero DataCollection or dict."""
    if collection is None:
        return []
    try:
        return [(key, collection.value(key)) for key in collection.keys()]
    except AttributeError:
        try:
            return list(dict(collection).items())
        except Exception:
            return []


def _tag_items(obj):
    items = []
    try:
        tags = obj.tags() or []
    except Exception:
        tags = []
    for tag in tags:
        try:
            items.extend(_data_items(tag.metadata()))
        except Exception:
            pass
    return items


def gather_clip_fields(clip, track_item=None):
    """Collect property/metadata bags used by the version-ID extractor."""
    file_path = None
    items = []
    if track_item is not None:
        items.extend(_tag_items(track_item))
    try:
        media = clip.mediaSource()
    except Exception:
        media = None
    if media is not None:
        try:
            infos = media.fileinfos()
            if infos:
                file_path = infos[0].filename()
        except Exception:
            pass
        try:
            items.extend(_data_items(media.metadata()))
        except Exception:
            pass
    try:
        items.extend(_data_items(clip.metadata()))
    except Exception:
        pass
    items.extend(_tag_items(clip))
    return build_fields(file_path, items)


def _clip_key(clip, track_item):
    obj = track_item if track_item is not None else clip
    try:
        guid = obj.guid()
    except Exception:
        guid = None
    return guid or id(obj)


# --- Plugin ------------------------------------------------------------------


class DnaPlugin(QtCore.QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = SessionStore(_read_setting, _write_setting)
        self._session = self._store.load_session()
        self._version_id_paths = load_version_id_paths()
        self._debug = self._load_debug()
        self._last_clip_key = None
        self._last_sent_version_id = None
        self._last_error = None
        self._playlist_versions = {}  # playlist id -> (fetched_at, frozenset)
        self._playlist_sessions = {}  # playlist id -> its own DNA session id

        self._menu = self._install_menu()

        hiero.core.events.registerInterest(
            "kPlaybackClipChanged", self._on_clip_changed
        )
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._sync_current_clip)
        self._update_polling()

    def session(self):
        """The signed-in DnaSession, or None."""
        return self._session

    # --- Menu ---------------------------------------------------------------

    def _install_menu(self):
        menu_bar = hiero.ui.menuBar()
        menu = QtWidgets.QMenu("DNA", menu_bar)
        menu.aboutToShow.connect(self._rebuild_menu)
        # Insert before Help when it exists, like most host menus.
        help_action = next(
            (
                a
                for a in menu_bar.actions()
                if a.text().replace("&", "").lower() == "help"
            ),
            None,
        )
        if help_action is not None:
            menu_bar.insertMenu(help_action, menu)
        else:
            menu_bar.addMenu(menu)
        self._rebuild_menu(menu)
        return menu

    def _rebuild_menu(self, menu=None):
        menu = menu or self._menu
        menu.clear()
        signed_in = self._session is not None

        def add(label, slot=None, enabled=True):
            action = menu.addAction(label)
            action.setEnabled(enabled and slot is not None)
            if slot is not None:
                action.triggered.connect(lambda checked=False: slot())
            return action

        add(self._status_line(), enabled=False)
        add(self._playlist_line(), enabled=False)
        if signed_in:
            add("Sign Out", self.sign_out)
        else:
            add("Sign In...", self.sign_in)
        add("Choose session...", self.choose_session, signed_in)
        add("Switch show/playlist...", self.switch_playlist, signed_in)
        add("Send current version now", self.force_sync, signed_in)
        menu.addSeparator()
        add("Set DNA URL...", self.set_url)
        debug = add("Debug mode", self.toggle_debug)
        debug.setCheckable(True)
        debug.setChecked(self._debug)

    def _status_line(self):
        session = self._session
        if not session:
            return "Not signed in"
        if session.review_session:
            target = f"session {session.review_session.display_name}"
        else:
            target = "each playlist's own session"
        return f"Signed in as {session.email} — {target}"

    def _playlist_line(self):
        if self._session:
            return f"Playlist: {self._session.playlist.display_name}"
        return "Playlist: none"

    # --- State --------------------------------------------------------------

    def _load_debug(self):
        return str(_read_setting(DEBUG_SETTING, "false")).lower() in (
            "1",
            "true",
            "yes",
        )

    def _refresh(self):
        self._session = self._store.load_session()
        self._debug = self._load_debug()
        self._last_clip_key = None
        self._last_sent_version_id = None
        self._last_error = None
        self._playlist_versions = {}
        self._playlist_sessions = {}
        self._update_polling()

    def _update_polling(self):
        if self._session:
            self._poll_timer.start()
        else:
            self._poll_timer.stop()

    def toggle_debug(self):
        self._debug = not self._debug
        _write_setting(DEBUG_SETTING, "true" if self._debug else "false")
        self._feedback(f"DNA debug mode {'on' if self._debug else 'off'}", 2.0)

    # --- Feedback -----------------------------------------------------------

    def _feedback(self, message, seconds=4.0):
        print(f"{LOG_PREFIX} {message}", flush=True)
        try:
            _main_window().statusBar().showMessage(message, int(seconds * 1000))
        except Exception:
            pass

    def _debug_feedback(self, message, seconds=6.0):
        self._feedback(message, seconds)

    # --- Sign in ------------------------------------------------------------

    def sign_in(self):
        self._run_desktop_flow(title="Sign in to DNA")

    def switch_playlist(self):
        if not self._session:
            return
        self._run_desktop_flow(title="Select DNA playlist")

    def _run_desktop_flow(self, title):
        url = self._store.url or self._prompt_for_url()
        if not url:
            return

        dialog = self._make_signin_dialog(url, title)
        result = exec_dialog(dialog)
        if result == QtWidgets.QDialog.Accepted and dialog.session:
            previous = self._session
            signed_in = dialog.session
            # Keep the chosen session across re-sign-ins in the same project.
            if (
                previous
                and previous.review_session
                and previous.project.id == signed_in.project.id
            ):
                signed_in = signed_in.with_review_session(previous.review_session)
            self._store.save_session(signed_in)
            self._refresh()
            self._feedback(f"Signed in to DNA as {signed_in.display_name}", 3.0)
            if not signed_in.review_session:
                self.choose_session(only_if_sessions=True)
            self._sync_current_clip()
        elif result == dialog.CHANGE_URL and self._prompt_for_url():
            self._run_desktop_flow(title=title)

    def _make_signin_dialog(self, url, title):
        if HAS_WEBENGINE:
            from hiero_dna.signin_dialog import SignInDialog

            return SignInDialog(url, _main_window(), title=title)
        # No QtWebEngine (Nuke 17): native email sign-in.
        from hiero_dna.native_signin_dialog import NativeSignInDialog

        previous = self._session
        dialog = NativeSignInDialog(
            url,
            _main_window(),
            title=title,
            api_url=_read_setting(API_URL_SETTING, "") or None,
            email=previous.email if previous else None,
        )
        dialog.accepted.connect(
            lambda: _write_setting(API_URL_SETTING, dialog.api_url)
        )
        return dialog

    def choose_session(self, only_if_sessions=False):
        """Pick the DNA session Hiero drives.

        ``only_if_sessions``: skip the picker when the project has no named
        sessions (DNA without the sessions feature only has implicit ones).
        """
        session = self._session
        if not session:
            return
        sessions, result = list_project_sessions(
            session.api_base_url, session.project.id, session.auth_headers()
        )
        if sessions is None:
            self._debug_result(result)
            if not only_if_sessions:
                QtWidgets.QMessageBox.warning(
                    _main_window(),
                    "DNA sessions",
                    f"Could not load DNA sessions ({result.status or 'network error'}).",
                )
            return
        named = [s for s in sessions if not s.is_implicit]
        if only_if_sessions and not named:
            return

        current_id = session.review_session.id if session.review_session else None
        preselect = next((s for s in named if s.id == current_id), None)
        if preselect is None and current_id is None:
            preselect = suggest_session(named, session.playlist.id)

        labels = [NO_SESSION_LABEL] + [s.display_name for s in named]
        index = named.index(preselect) + 1 if preselect else 0
        label, ok = QtWidgets.QInputDialog.getItem(
            _main_window(),
            "DNA session",
            "Session Hiero drives:",
            labels,
            index,
            False,
        )
        if not ok:
            return
        chosen = None if label == NO_SESSION_LABEL else named[labels.index(label) - 1]
        ref = DnaEntityRef(id=chosen.id, name=chosen.name) if chosen else None
        self._store.save_session(session.with_review_session(ref))
        self._refresh()
        self._feedback(
            f"DNA session: {chosen.display_name if chosen else NO_SESSION_LABEL}", 3.0
        )
        self._sync_current_clip()

    def sign_out(self):
        self._store.clear_session()
        self._refresh()
        self._feedback("Signed out of DNA", 3.0)

    def set_url(self):
        self._prompt_for_url()

    def _prompt_for_url(self):
        """Ask for the DNA URL and save it. Returns the URL, or None if cancelled."""
        parent = _main_window()
        text = self._store.url or ""
        while True:
            text, ok = QtWidgets.QInputDialog.getText(
                parent,
                "DNA URL",
                "DNA web app URL (for example https://dna.example.com):",
                QtWidgets.QLineEdit.Normal,
                text,
            )
            if not ok:
                return None
            try:
                url = self._store.set_url(text)
            except ValueError as e:
                QtWidgets.QMessageBox.warning(parent, "Invalid DNA URL", str(e))
                continue
            self._refresh()
            return url

    # --- Version sync -------------------------------------------------------

    def _on_clip_changed(self, event=None):
        self._sync_current_clip()

    def force_sync(self):
        self._last_clip_key = None
        self._last_sent_version_id = None
        self._last_error = None
        self._sync_current_clip()

    def _sync_current_clip(self):
        """Push the on-screen version to DNA if the clip changed."""
        session = self._session
        if not session:
            return
        try:
            clip, track_item = _current_clip()
        except Exception as e:  # never let a Hiero API hiccup kill the timer
            if self._debug:
                self._debug_feedback(f"DNA debug: could not read the viewer: {e}")
            return
        if clip is None:
            return
        key = _clip_key(clip, track_item)
        if key == self._last_clip_key:
            return
        self._last_clip_key = key
        self._push_clip(session, clip, track_item)

    def _push_clip(self, session, clip, track_item):
        properties, metadata = gather_clip_fields(clip, track_item)
        version_id = extract_version_id(
            properties=properties,
            metadata=metadata,
            paths=self._version_id_paths,
        )
        if not version_id:
            if self._debug:
                self._debug_feedback(
                    f"DNA debug: no version ID for {clip.name()} "
                    f"props={properties!r} meta={metadata!r}",
                    8.0,
                )
            return
        if version_id == self._last_sent_version_id:
            if self._debug:
                self._debug_feedback(
                    f"DNA debug: skipped, version {version_id} already sent"
                )
            return

        if session.review_session:
            dna_session, result = get_session(
                session.api_base_url, session.review_session.id, session.auth_headers()
            )
            if dna_session is None:
                self._debug_result(result)
                if result.status == 404:
                    self._notify_once(
                        "DNA session not found. Choose DNA > Choose session..."
                    )
                else:
                    self._report_failure(result)
                return
        else:
            dna_session = None

        # Hiero has no production-tracking playlist context: start from the
        # sign-in playlist, and with a session search its playlists.
        target = choose_playlist(
            version_id,
            session.playlist.id,
            False,
            dna_session,
            lambda playlist_id: self._playlist_has_version(
                session, playlist_id, version_id
            ),
        )
        if target.playlist_id is None:
            if self._debug:
                self._debug_feedback(f"DNA debug: skipped, {target.skip_reason}")
            elif target.notify:
                self._notify_once(f"DNA: in review not set, {target.skip_reason}")
            return

        if dna_session is not None:
            session_id = dna_session.id
        else:
            session_id = self._playlist_session_id(session, target.playlist_id)
            if not session_id:
                return

        result = set_in_review(
            session.api_base_url,
            session_id,
            target.playlist_id,
            version_id,
            session.auth_headers(),
        )
        self._debug_result(result)
        if result.ok:
            self._last_sent_version_id = version_id
            self._last_error = None
        else:
            self._report_failure(result)

    def _playlist_has_version(self, session, playlist_id, version_id):
        """Whether the playlist holds the version; None if DNA can't say."""
        cached = self._playlist_versions.get(playlist_id)
        now = time.monotonic()
        if cached and now - cached[0] < PLAYLIST_VERSIONS_TTL_S and version_id in cached[1]:
            return True
        version_ids, result = get_playlist_version_ids(
            session.api_base_url, playlist_id, session.auth_headers()
        )
        if version_ids is None:
            self._debug_result(result)
            self._report_failure(result)
            return None
        self._playlist_versions[playlist_id] = (now, version_ids)
        return version_id in version_ids

    def _playlist_session_id(self, session, playlist_id):
        """The playlist's own DNA session (no session chosen), looked up once."""
        if playlist_id in self._playlist_sessions:
            return self._playlist_sessions[playlist_id]
        session_id, result = ensure_session_for_playlist(
            session.api_base_url,
            session.project.id,
            playlist_id,
            session.auth_headers(),
        )
        if not session_id:
            self._debug_result(result)
            self._report_failure(result)
            return None
        self._playlist_sessions[playlist_id] = session_id
        return session_id

    def _notify_once(self, message):
        if message == self._last_error:
            return
        self._last_error = message
        self._feedback(message, 5.0)

    def _report_failure(self, result):
        """Tell the user a DNA request failed, once per distinct failure."""
        if self._debug or result.status in EXPECTED_REFUSALS:
            return
        if result.status is None:
            message = "DNA unreachable: in review is not syncing"
        elif result.status == 401:
            message = "DNA sign-in expired. Choose DNA > Sign In..."
        else:
            message = f"DNA rejected the in-review update ({result.status})"
        self._notify_once(message)

    def _debug_result(self, result):
        if not self._debug:
            return
        self._debug_feedback(
            f"DNA debug request: {result.method} {result.url} {result.request_body}"
        )
        status = result.status if result.status is not None else "network error"
        body = (result.response_body or "(empty)").replace("\n", " ")
        if len(body) > 240:
            body = body[:237] + "..."
        self._debug_feedback(f"DNA debug response: {status} {body}", 8.0)


_plugin = None


def install():
    """Create the DNA menu once. Safe to call again."""
    global _plugin
    if _plugin is None:
        _plugin = DnaPlugin(_main_window())
    return _plugin


def thePlugin():
    return _plugin
