"""
engine_bridge.py — ctypes Bridge to C++ Fretboard Algorithm Engine
Loads libfretboard_math (or .dll/.dylib) and provides Pythonic abstractions.
"""

import ctypes
from typing import Any
from .config import LIB_PATH, NOTE_NAMES, STANDARD_TUNING

# Load shared library
if not LIB_PATH.exists():
    raise FileNotFoundError(
        f"C++ shared library not found at: {LIB_PATH.resolve()}. "
        "Please compile using cpp_engine/build.bat or make in cpp_engine/."
    )

_lib = ctypes.CDLL(str(LIB_PATH.resolve()))

MAX_STRINGS = 8
MAX_FRETS = 24


# =============================================================================
# ctypes Structure Mirrors
# =============================================================================

class TuningConfig(ctypes.Structure):
    _fields_ = [
        ("string_count", ctypes.c_int32),
        ("open_midi", ctypes.c_int32 * MAX_STRINGS),
        ("fret_count", ctypes.c_int32),
    ]


class IntervalInfo(ctypes.Structure):
    _fields_ = [
        ("semitones", ctypes.c_int32),
        ("simple_semitones", ctypes.c_int32),
        ("octaves", ctypes.c_int32),
        ("name", ctypes.c_char * 16),
    ]


class MultiStringIntervalResult(ctypes.Structure):
    _fields_ = [
        ("sounding_count", ctypes.c_int32),
        ("lowest_string_idx", ctypes.c_int32),
        ("lowest_midi_note", ctypes.c_int32),
        ("string_indices", ctypes.c_int32 * MAX_STRINGS),
        ("fret_positions", ctypes.c_int32 * MAX_STRINGS),
        ("midi_notes", ctypes.c_int32 * MAX_STRINGS),
        ("interval_from_lowest", IntervalInfo * MAX_STRINGS),
        ("interval_from_adjacent", IntervalInfo * MAX_STRINGS),
    ]


class TuningShift(ctypes.Structure):
    _fields_ = [
        ("string_number", ctypes.c_int32),
        ("standard_midi", ctypes.c_int32),
        ("custom_midi", ctypes.c_int32),
        ("semitone_delta", ctypes.c_int32),
        ("fret_shift", ctypes.c_int32),
    ]


class TuningShiftResult(ctypes.Structure):
    _fields_ = [
        ("string_count", ctypes.c_int32),
        ("shifts", TuningShift * MAX_STRINGS),
    ]


class FretCell(ctypes.Structure):
    _fields_ = [
        ("string_num", ctypes.c_int32),
        ("fret", ctypes.c_int32),
        ("midi_note", ctypes.c_int32),
        ("pitch_class", ctypes.c_int32),
        ("in_scale", ctypes.c_int32),
        ("scale_degree", ctypes.c_int32),
        ("is_root", ctypes.c_int32),
    ]


class FretboardMap(ctypes.Structure):
    _fields_ = [
        ("string_count", ctypes.c_int32),
        ("fret_count", ctypes.c_int32),
        ("cells", (FretCell * (MAX_FRETS + 1)) * MAX_STRINGS),
    ]


class FingerPlacement(ctypes.Structure):
    _fields_ = [
        ("string_num", ctypes.c_int32),
        ("fret", ctypes.c_int32),
        ("midi_note", ctypes.c_int32),
        ("finger", ctypes.c_int32),
    ]


class ChordVoicing(ctypes.Structure):
    _fields_ = [
        ("string_count", ctypes.c_int32),
        ("placements", FingerPlacement * MAX_STRINGS),
        ("difficulty_score", ctypes.c_float),
        ("min_fret", ctypes.c_int32),
        ("max_fret", ctypes.c_int32),
        ("barre_fret", ctypes.c_int32),
        ("root_string", ctypes.c_int32),
    ]


class VoicingResult(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_int32),
        ("voicings", ChordVoicing * 32),
    ]


# =============================================================================
# Function Signatures Binding
# =============================================================================

_lib.fret_calculate_interval.argtypes = [
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.POINTER(IntervalInfo),
]
_lib.fret_calculate_interval.restype = ctypes.c_int32

_lib.fret_calculate_multi_string_intervals.argtypes = [
    ctypes.POINTER(TuningConfig),
    ctypes.POINTER(ctypes.c_int32),
    ctypes.c_int32,
    ctypes.POINTER(MultiStringIntervalResult),
]
_lib.fret_calculate_multi_string_intervals.restype = ctypes.c_int32

_lib.fret_calculate_tuning_shifts.argtypes = [
    ctypes.POINTER(ctypes.c_int32),
    ctypes.c_int32,
    ctypes.POINTER(TuningShiftResult),
]
_lib.fret_calculate_tuning_shifts.restype = ctypes.c_int32

_lib.fret_compute_map.argtypes = [
    ctypes.POINTER(TuningConfig),
    ctypes.POINTER(ctypes.c_int32),
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.POINTER(FretboardMap),
]
_lib.fret_compute_map.restype = ctypes.c_int32

_lib.fret_note_at.argtypes = [
    ctypes.POINTER(TuningConfig),
    ctypes.c_int32,
    ctypes.c_int32,
]
_lib.fret_note_at.restype = ctypes.c_int32

_lib.fret_find_voicings.argtypes = [
    ctypes.POINTER(TuningConfig),
    ctypes.POINTER(ctypes.c_int32),
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.POINTER(VoicingResult),
]
_lib.fret_find_voicings.restype = ctypes.c_int32


# =============================================================================
# Pythonic Helper Functions
# =============================================================================

def build_tuning_config(open_midis: list[int], fret_count: int = 24) -> TuningConfig:
    """Instantiates a TuningConfig struct from a list of MIDI integers."""
    cfg = TuningConfig()
    cfg.string_count = len(open_midis)
    cfg.fret_count = fret_count
    for i, p in enumerate(open_midis):
        cfg.open_midi[i] = p
    return cfg


def calculate_tuning_shifts(custom_tuning: list[int]) -> list[dict[str, Any]]:
    """
    Computes horizontal fret shifts relative to standard guitar tuning.
    Returns per-string shifts for frontend reactive positioning.
    """
    count = len(custom_tuning)
    c_arr = (ctypes.c_int32 * count)(*custom_tuning)
    result = TuningShiftResult()

    rc = _lib.fret_calculate_tuning_shifts(c_arr, count, ctypes.byref(result))
    if rc != 0:
        raise RuntimeError(f"fret_calculate_tuning_shifts failed with code {rc}")

    shifts = []
    for i in range(result.string_count):
        s = result.shifts[i]
        custom_note = NOTE_NAMES[s.custom_midi % 12] + str((s.custom_midi // 12) - 1)
        std_note = NOTE_NAMES[s.standard_midi % 12] + str((s.standard_midi // 12) - 1)
        shifts.append({
            "string_number": s.string_number,
            "standard_midi": s.standard_midi,
            "standard_name": std_note,
            "custom_midi": s.custom_midi,
            "custom_name": custom_note,
            "semitone_delta": s.semitone_delta,
            "fret_shift": s.fret_shift,
        })
    return shifts


def compute_fretboard_map(
    open_midis: list[int],
    scale_offsets: list[int],
    root_pitch_class: int,
    fret_count: int = 24
) -> list[list[dict[str, Any]]]:
    """
    Generates the complete 2D fretboard grid with scale degrees and membership flags.
    """
    tuning_cfg = build_tuning_config(open_midis, fret_count)
    offsets_arr = (ctypes.c_int32 * len(scale_offsets))(*scale_offsets)
    out_map = FretboardMap()

    rc = _lib.fret_compute_map(
        ctypes.byref(tuning_cfg),
        offsets_arr,
        len(scale_offsets),
        root_pitch_class,
        ctypes.byref(out_map)
    )
    if rc != 0:
        raise RuntimeError(f"fret_compute_map failed with code {rc}")

    grid = []
    for s in range(out_map.string_count):
        string_row = []
        for f in range(out_map.fret_count + 1):
            cell = out_map.cells[s][f]
            string_row.append({
                "string": cell.string_num + 1,  # 1-indexed for display
                "string_idx": cell.string_num,  # 0-indexed
                "fret": cell.fret,
                "midi_note": cell.midi_note,
                "pitch_class": cell.pitch_class,
                "note_name": NOTE_NAMES[cell.pitch_class],
                "in_scale": bool(cell.in_scale),
                "scale_degree": cell.scale_degree,
                "is_root": bool(cell.is_root),
            })
        grid.append(string_row)
    return grid


def find_chord_voicings(
    open_midis: list[int],
    chord_offsets: list[int],
    root_pitch_class: int,
    max_span: int = 4,
    max_results: int = 6
) -> list[dict[str, Any]]:
    """
    Computes optimal, ergonomic guitar chord voicings using the C++ algorithm engine.
    """
    tuning_cfg = build_tuning_config(open_midis)
    offsets_arr = (ctypes.c_int32 * len(chord_offsets))(*chord_offsets)
    result = VoicingResult()

    rc = _lib.fret_find_voicings(
        ctypes.byref(tuning_cfg),
        offsets_arr,
        len(chord_offsets),
        root_pitch_class,
        max_span,
        max_results,
        ctypes.byref(result)
    )
    if rc != 0:
        raise RuntimeError(f"fret_find_voicings failed with code {rc}")

    voicings = []
    for i in range(result.count):
        v = result.voicings[i]
        placements = []
        tab_parts = []

        # High string (0) to Low string (count-1)
        # Tab notation is typically low to high (e.g. x-3-2-0-1-0)
        # So we collect string indices
        for s in range(v.string_count):
            p = v.placements[s]
            fret_val = p.fret
            note_name = NOTE_NAMES[p.midi_note % 12] if fret_val >= 0 else "X"
            placements.append({
                "string_number": s + 1,
                "fret": fret_val,
                "midi_note": p.midi_note,
                "finger": p.finger,
                "note_name": note_name
            })

        # Generate guitar tab string ordered from low E to high E (e.g. x-3-2-0-1-0)
        for s in reversed(range(v.string_count)):
            fret_val = v.placements[s].fret
            tab_parts.append(str(fret_val) if fret_val >= 0 else "x")
        tab_repr = "-".join(tab_parts)

        voicings.append({
            "placements": placements,
            "difficulty_score": round(float(v.difficulty_score), 2),
            "min_fret": v.min_fret,
            "max_fret": v.max_fret,
            "barre_fret": v.barre_fret,
            "root_string": v.root_string + 1 if v.root_string >= 0 else None,
            "tab_repr": tab_repr
        })

    return voicings
