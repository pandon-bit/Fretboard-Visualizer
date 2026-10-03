"""
config.py — Configuration for the Fretboard Visualizer Backend
"""

import sys
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "database" / "music_models.db"

# Shared library detection
ENGINE_DIR = BASE_DIR / "cpp_engine"
if sys.platform == "win32":
    LIB_PATH = ENGINE_DIR / "fretboard_math.dll"
elif sys.platform == "darwin":
    LIB_PATH = ENGINE_DIR / "libfretboard_math.dylib"
else:
    LIB_PATH = ENGINE_DIR / "libfretboard_math.so"

# Standard Guitar Tuning (High E to Low E): E4, B3, G3, D3, A2, E2
STANDARD_TUNING = [64, 59, 55, 50, 45, 40]
STANDARD_TUNING_NAMES = ["E4", "B3", "G3", "D3", "A2", "E2"]
DEFAULT_FRET_COUNT = 24

# Pitch class names
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
ENHARMONIC_MAP = {
    "DB": "C#",
    "EB": "D#",
    "FB": "E",
    "GB": "F#",
    "AB": "G#",
    "BB": "A#",
    "B#": "C",
    "E#": "F",
    "CB": "B",
}
