#
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Dailies Notes Assistant Project.
#
"""PySide6 (Hiero 16+) or PySide2 (Hiero 13-15)."""

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtWebChannel import QWebChannel
    from PySide2.QtWebEngineWidgets import (
        QWebEnginePage,
        QWebEngineProfile,
        QWebEngineScript,
        QWebEngineView,
    )


def exec_dialog(dialog):
    return dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()


__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QWebChannel",
    "QWebEnginePage",
    "QWebEngineProfile",
    "QWebEngineScript",
    "QWebEngineView",
    "exec_dialog",
]
