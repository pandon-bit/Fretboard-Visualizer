"""
test_engine.py — ctypes verification for fretboard_math shared library.

Validates:
1. Horizontal string shift calculation against standard tuning (E2-A2-D3-G3-B3-E4).
2. Multi-string interval calculations (e.g. an open C Major chord and Drop D power chord).
3. Dynamic fretboard map generation with scale masking and degree computation.
"""

import ctypes
import os
import sys
from pathlib import Path


# Locate shared library
ENGINE_DIR = Path(__file__).resolve().parent
if sys.platform == "win32":
    LIB_PATH = ENGINE_DIR / "fretboard_math.dll"
elif sys.platform == "darwin":
    LIB_PATH = ENGINE_DIR / "libfretboard_math.dylib"
else:
    LIB_PATH = ENGINE_DIR / "libfretboard_math.so"

if not LIB_PATH.exists():
    raise FileNotFoundError(f"Shared library not found at: {LIB_PATH}")

lib = ctypes.CDLL(str(LIB_PATH))

# Constants
MAX_STRINGS = 8
MAX_FRETS = 24

# Struct Definitions
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

# Setup argtypes / restypes
lib.fret_calculate_interval.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(IntervalInfo)]
lib.fret_calculate_interval.restype = ctypes.c_int32

lib.fret_calculate_multi_string_intervals.argtypes = [
    ctypes.POINTER(TuningConfig),
    ctypes.POINTER(ctypes.c_int32),
    ctypes.c_int32,
    ctypes.POINTER(MultiStringIntervalResult)
]
lib.fret_calculate_multi_string_intervals.restype = ctypes.c_int32

lib.fret_calculate_tuning_shifts.argtypes = [
    ctypes.POINTER(ctypes.c_int32),
    ctypes.c_int32,
    ctypes.POINTER(TuningShiftResult)
]
lib.fret_calculate_tuning_shifts.restype = ctypes.c_int32

lib.fret_compute_map.argtypes = [
    ctypes.POINTER(TuningConfig),
    ctypes.POINTER(ctypes.c_int32),
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.POINTER(FretboardMap)
]
lib.fret_compute_map.restype = ctypes.c_int32

lib.fret_note_at.argtypes = [ctypes.POINTER(TuningConfig), ctypes.c_int32, ctypes.c_int32]
lib.fret_note_at.restype = ctypes.c_int32


def test_tuning_shifts():
    print("=" * 65)
    print("TEST 1: Tuning Shift Calculation (Drop D Tuning)")
    print("=" * 65)

    # Drop D tuning: String 1..6 = E4(64), B3(59), G3(55), D3(50), A2(45), D2(38)
    drop_d = (ctypes.c_int32 * 6)(64, 59, 55, 50, 45, 38)
    result = TuningShiftResult()

    rc = lib.fret_calculate_tuning_shifts(drop_d, 6, ctypes.byref(result))
    assert rc == 0, f"fret_calculate_tuning_shifts failed with {rc}"

    print(f"Strings evaluated: {result.string_count}")
    for i in range(result.string_count):
        s = result.shifts[i]
        print(f"  String {s.string_number}: Std MIDI={s.standard_midi:2} -> "
              f"Custom MIDI={s.custom_midi:2} | Delta={s.semitone_delta:+2} st | "
              f"Horizontal Fret Shift={s.fret_shift:+2}")

    # String 6 (low E retuned to D) should have delta -2 and shift +2
    s6 = result.shifts[5]
    assert s6.semitone_delta == -2, f"Expected delta -2, got {s6.semitone_delta}"
    assert s6.fret_shift == 2, f"Expected shift +2, got {s6.fret_shift}"
    print("-> PASS: Low E -> D correctly produces -2 delta and +2 visual fret shift.\n")


def test_multi_string_intervals():
    print("=" * 65)
    print("TEST 2: Multi-String Interval Calculation (Open C Major Chord)")
    print("=" * 65)

    # Standard tuning
    tuning = TuningConfig()
    tuning.string_count = 6
    tuning.fret_count = 24
    std_pitches = [64, 59, 55, 50, 45, 40]
    for i, p in enumerate(std_pitches):
        tuning.open_midi[i] = p

    # Standard Open C Chord: x-3-2-0-1-0
    # String 1 (high E) = fret 0 (E4)
    # String 2 (B)      = fret 1 (C4)
    # String 3 (G)      = fret 0 (G3)
    # String 4 (D)      = fret 2 (E3)
    # String 5 (A)      = fret 3 (C3)  <- Root/Bass
    # String 6 (low E)  = -1 (muted)
    c_chord_frets = (ctypes.c_int32 * 6)(0, 1, 0, 2, 3, -1)

    result = MultiStringIntervalResult()
    rc = lib.fret_calculate_multi_string_intervals(
        ctypes.byref(tuning), c_chord_frets, 6, ctypes.byref(result)
    )
    assert rc == 0, f"fret_calculate_multi_string_intervals failed with {rc}"

    print(f"Sounding strings: {result.sounding_count}/6")
    print(f"Lowest sounding note: MIDI {result.lowest_midi_note} on String {result.lowest_string_idx + 1}")

    string_names = ["1 (E4)", "2 (B3)", "3 (G3)", "4 (D3)", "5 (A2)", "6 (E2)"]
    for s in range(6):
        fret = result.fret_positions[s]
        midi = result.midi_notes[s]
        if fret >= 0:
            from_bass = result.interval_from_lowest[s].name.decode()
            from_prev = result.interval_from_adjacent[s].name.decode()
            print(f"  String {string_names[s]}: fret {fret:2} -> MIDI {midi:2} | "
                  f"From Bass: {from_bass:4} | From Prev String: {from_prev:4}")
        else:
            print(f"  String {string_names[s]}: MUTED")

    # String 5 (fret 3) is C3 (MIDI 48).
    # String 4 (fret 2) is E3 (MIDI 52) -> Major 3rd (4 semitones) from bass C3.
    # String 3 (fret 0) is G3 (MIDI 55) -> Perfect 5th (7 semitones) from bass C3.
    assert result.lowest_midi_note == 48, f"Bass note should be C3 (48), got {result.lowest_midi_note}"
    assert result.interval_from_lowest[4].semitones == 0  # C3 to C3 (P1)
    assert result.interval_from_lowest[3].semitones == 4  # C3 to E3 (M3)
    assert result.interval_from_lowest[2].semitones == 7  # C3 to G3 (P5)
    print("-> PASS: Multi-string chord intervals verified (P1, M3, P5 correctly resolved).\n")


def test_fretboard_map():
    print("=" * 65)
    print("TEST 3: Dynamic Fretboard Map Calculation (C Major Scale)")
    print("=" * 65)

    tuning = TuningConfig()
    tuning.string_count = 6
    tuning.fret_count = 24
    for i, p in enumerate([64, 59, 55, 50, 45, 40]):
        tuning.open_midi[i] = p

    # Major scale offsets: 0, 2, 4, 5, 7, 9, 11
    major_offsets = (ctypes.c_int32 * 7)(0, 2, 4, 5, 7, 9, 11)
    c_root = 0  # C = 0

    fb_map = FretboardMap()
    rc = lib.fret_compute_map(
        ctypes.byref(tuning),
        major_offsets,
        7,
        c_root,
        ctypes.byref(fb_map)
    )
    assert rc == 0, f"fret_compute_map failed with {rc}"

    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    print("String 6 (Low E) frets 0-12 scale analysis:")
    for f in range(13):
        cell = fb_map.cells[5][f]
        name = note_names[cell.pitch_class]
        status = f"Degree {cell.scale_degree}" if cell.in_scale else "Out of Scale"
        root_flag = " [ROOT]" if cell.is_root else ""
        print(f"  Fret {f:2}: Note {name:2} (MIDI {cell.midi_note:2}) -> {status}{root_flag}")

    # Check fret 8 on low E string: 40 + 8 = 48 (C3) -> Root note, in scale, degree 1
    c_cell = fb_map.cells[5][8]
    assert c_cell.pitch_class == 0
    assert c_cell.in_scale == 1
    assert c_cell.scale_degree == 1
    assert c_cell.is_root == 1

    # Check fret 1 on low E string: 40 + 1 = 41 (F) -> Degree 4, in scale
    f_cell = fb_map.cells[5][1]
    assert f_cell.pitch_class == 5  # F
    assert f_cell.in_scale == 1
    assert f_cell.scale_degree == 4

    print("-> PASS: Fretboard map accurately marks notes, scale membership, degrees, and roots.\n")
    print("=" * 65)
    print("ALL C++ ENGINE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    test_tuning_shifts()
    test_multi_string_intervals()
    test_fretboard_map()
