"""V-SHIELD Backend Package."""
import os
import sys

# Ensure repository root is on sys.path so top-level packages (ml, models) are cleanly importable
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
