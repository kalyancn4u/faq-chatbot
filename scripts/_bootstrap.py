"""Make the project importable when running scripts directly.

Running ``python scripts/foo.py`` puts ``scripts/`` on ``sys.path`` but not the
project root, so ``import app...`` would fail. Importing this module first fixes
that. Each script does ``import _bootstrap  # noqa: F401`` as its first import.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
