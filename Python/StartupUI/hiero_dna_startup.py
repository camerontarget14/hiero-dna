#
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Dailies Notes Assistant Project.
#
"""Hiero startup hook: adds the DNA menu.

Hiero runs every module in <HIERO_PLUGIN_PATH entry>/Python/StartupUI when
its interface starts.
The plugin code lives in <repo>/lib so Hiero does not load it twice.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PYTHON = os.path.join(_ROOT, "lib")
if _PYTHON not in sys.path:
    sys.path.insert(0, _PYTHON)

try:
    from hiero_dna import plugin as _dna_plugin

    _dna_plugin.install()
except Exception as _error:  # keep Hiero starting even if DNA can't load
    import traceback

    print(f"hiero_dna: failed to load: {_error}")
    traceback.print_exc()
