#
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Dailies Notes Assistant Project.
#
"""Native DNA sign-in for hosts without QtWebEngine (Nuke 17).

Supports DNA servers using email sign-in (VITE_AUTH_PROVIDER=none). Google
sign-in needs the web page and is not available here.
"""

from hiero_dna.auth import InvalidPayloadError, parse_auth_payload
from hiero_dna.directory import (
    build_payload_json,
    default_api_url,
    list_project_playlists,
    list_user_projects,
)
from hiero_dna.qt import QtWidgets


class NativeSignInDialog(QtWidgets.QDialog):
    """Same contract as SignInDialog: ``exec()`` -> Accepted with ``session``."""

    CHANGE_URL = 2

    def __init__(self, dna_url, parent=None, title="Sign in to DNA", api_url=None, email=None):
        super().__init__(parent)
        self.session = None
        self._dna_url = dna_url
        self._projects = []
        self._playlists = []
        self.setWindowTitle(title)
        self.setMinimumWidth(460)

        self._api = QtWidgets.QLineEdit(api_url or default_api_url(dna_url))
        self._email = QtWidgets.QLineEdit(email or "")
        self._email.setPlaceholderText("you@studio.com")
        load = QtWidgets.QPushButton("Load shows")
        load.clicked.connect(self._load_projects)
        self._email.returnPressed.connect(self._load_projects)

        self._project = QtWidgets.QComboBox()
        self._project.currentIndexChanged.connect(self._load_playlists)
        self._playlist = QtWidgets.QComboBox()
        self._status = QtWidgets.QLabel(f"DNA web app: {dna_url}")
        self._status.setWordWrap(True)

        form = QtWidgets.QFormLayout()
        form.addRow("DNA API URL", self._api)
        email_row = QtWidgets.QHBoxLayout()
        email_row.addWidget(self._email)
        email_row.addWidget(load)
        form.addRow("Email", email_row)
        form.addRow("Show", self._project)
        form.addRow("Playlist", self._playlist)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        change = buttons.addButton("Change DNA URL...", QtWidgets.QDialogButtonBox.ResetRole)
        change.clicked.connect(lambda: self.done(self.CHANGE_URL))
        buttons.accepted.connect(self._finish)
        buttons.rejected.connect(self.reject)
        self._ok = buttons.button(QtWidgets.QDialogButtonBox.Ok)
        self._ok.setEnabled(False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._status)
        layout.addWidget(buttons)

    @property
    def api_url(self):
        return self._api.text().strip().rstrip("/")

    @property
    def email(self):
        return self._email.text().strip()

    def _fail(self, what, result):
        status = result.status if result.status is not None else "network error"
        detail = (result.response_body or "").strip().replace("\n", " ")[:200]
        self._status.setText(f"Could not load {what} ({status}) from {result.url}\n{detail}")

    def _load_projects(self):
        if not self.email or not self.api_url:
            self._status.setText("Enter the DNA API URL and your email.")
            return
        self._status.setText("Loading shows...")
        QtWidgets.QApplication.processEvents()
        projects, result = list_user_projects(self.api_url, self.email)
        self._project.blockSignals(True)
        self._project.clear()
        self._project.blockSignals(False)
        self._playlist.clear()
        self._ok.setEnabled(False)
        if projects is None:
            self._fail("shows", result)
            return
        if not projects:
            self._status.setText(f"No shows for {self.email}.")
            return
        self._projects = projects
        self._project.blockSignals(True)
        self._project.addItems([p.name for p in projects])
        self._project.blockSignals(False)
        self._load_playlists()

    def _load_playlists(self, *_):
        index = self._project.currentIndex()
        self._playlist.clear()
        self._ok.setEnabled(False)
        if index < 0 or index >= len(self._projects):
            return
        project = self._projects[index]
        self._status.setText(f"Loading playlists for {project.name}...")
        QtWidgets.QApplication.processEvents()
        playlists, result = list_project_playlists(self.api_url, self.email, project.id)
        if playlists is None:
            self._fail("playlists", result)
            return
        self._playlists = playlists
        self._playlist.addItems([p.name for p in playlists])
        self._ok.setEnabled(bool(playlists))
        self._status.setText(
            "Pick a playlist." if playlists else f"No playlists in {project.name}."
        )

    def _finish(self):
        pi, li = self._project.currentIndex(), self._playlist.currentIndex()
        if pi < 0 or li < 0:
            return
        payload = build_payload_json(
            self.email, self.api_url, self._projects[pi], self._playlists[li]
        )
        try:
            self.session = parse_auth_payload(payload, self._dna_url)
        except InvalidPayloadError as e:
            self._status.setText(str(e))
            return
        self.accept()
