#
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Dailies Notes Assistant Project.
#
"""PySide6 (Hiero 16+) or PySide2 (Hiero 13-15).

QtWebEngine is optional: Nuke 17 does not ship it, so the plugin falls back
to a native sign-in dialog (see ``HAS_WEBENGINE``).
"""

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

try:
    try:
        from PySide6.QtWebChannel import QWebChannel
        from PySide6.QtWebEngineCore import (
            QWebEnginePage,
            QWebEngineProfile,
            QWebEngineScript,
        )
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        from PySide2.QtWebChannel import QWebChannel
        from PySide2.QtWebEngineWidgets import (
            QWebEnginePage,
            QWebEngineProfile,
            QWebEngineScript,
            QWebEngineView,
        )
    HAS_WEBENGINE = True
except ImportError:
    QWebChannel = QWebEnginePage = QWebEngineProfile = None
    QWebEngineScript = QWebEngineView = None
    HAS_WEBENGINE = False


def exec_dialog(dialog):
    return dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
