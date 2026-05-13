"""Shared pytest configuration: make `app` importable and enable asyncio."""

from __future__ import annotations

import os
import sys

# Ensure `Backend/` is on sys.path so `import app...` works regardless of
# where pytest is invoked from.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)
