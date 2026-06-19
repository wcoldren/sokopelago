"""Make the pure helper modules importable without the Archipelago env.

``layout.py`` and ``build_corpus.py`` use only the stdlib, so we add their dirs to
sys.path and import them directly — importing the ``apworld.sokopelago`` *package*
would trigger its __init__ (which imports BaseClasses) and require a full AP install.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apworld" / "sokopelago"))
sys.path.insert(0, str(ROOT / "tools"))
