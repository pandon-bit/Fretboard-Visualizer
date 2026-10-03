# Guitar Fretboard Visualizer — Architecture Plan

> **Author:** Principal Software Engineer  
> **Date:** 2026-09-30  
> **Stack:** C++ · Python · SQLite · HTML/CSS · TypeScript

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [SQLite Database Schema](#2-sqlite-database-schema)
3. [C++ Algorithm Engine](#3-c-algorithm-engine)
4. [Python REST API](#4-python-rest-api)
5. [TypeScript / HTML / CSS Frontend](#5-typescript--html--css-frontend)
6. [Data Flow & Sequence Diagrams](#6-data-flow--sequence-diagrams)
7. [Build & Deployment](#7-build--deployment)

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND  (Browser)                         │
│   HTML / CSS / TypeScript                                       │
│   ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐  │
│   │ Fretboard│  │ ScaleView│  │ ChordView │  │ TuningPanel  │  │
│   │ Renderer │  │ Toggle   │  │ + Roman   │  │ (per-string) │  │
│   └────┬─────┘  └────┬─────┘  └─────┬─────┘  └──────┬───────┘  │
│        └──────────────┴──────────────┴───────────────┘          │
│                          ▼  HTTP / JSON                         │
├─────────────────────────────────────────────────────────────────┤
│                     PYTHON API  (FastAPI)                        │
│   ┌────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│   │ /scales    │  │ /chords      │  │ /fretboard             │  │
│   │ /keys      │  │ /voicings    │  │ /tunings               │  │
│   └─────┬──────┘  └──────┬───────┘  └───────────┬────────────┘  │
│         │                │                       │              │
│   ┌─────▼────────────────▼───────────────────────▼────────┐     │
│   │  SQLite DAL            │    C++ Bindings (ctypes)     │     │
│   └────────┬───────────────┴──────────────┬───────────────┘     │
├────────────▼──────────────────────────────▼─────────────────────┤
│   SQLite DB (fretboard.db)       libfretengine.so / .dll        │
│   Music Theory Data              Interval Math & Voicing Solver │
└─────────────────────────────────────────────────────────────────┘
```

### Guiding Principles

| Principle | Rationale |
|-----------|-----------|
| **Separation of concerns** | SQL owns *data*, C++ owns *computation*, Python owns *orchestration*, TS owns *presentation*. |
| **Low-latency path** | Hot-path calls (fretboard mapping, voicing search) go through C++ via ctypes — no serialization overhead. |
| **Relational integrity** | All music-theory relationships (scale → intervals, key → diatonic chords) are enforced by foreign keys. |
| **Tuning-agnostic engine** | The C++ engine receives open-string MIDI pitches as input; it never hard-codes standard tuning. |

---

## 2. SQLite Database Schema

The database file is `fretboard.db`. All pitches are stored as **MIDI note numbers** (0–127) to enable pure integer arithmetic in the C++ layer.

### 2.1 Entity-Relationship Diagram

```
┌──────────┐        ┌────────────────┐        ┌──────────┐
│  Notes   │◄──────▶│ ScaleIntervals │◄───────▶│  Scales  │
│ (12 rows)│  N:M   │  (junction)    │   N:M   │          │
└──────────┘        └────────────────┘         └──────────┘
      ▲                                              ▲
      │                                              │
      │         ┌────────────────┐                   │
      └────────▶│ ChordIntervals │◄──────┐           │
         N:M    │  (junction)    │       │           │
                └────────────────┘  ┌────┴─────┐     │
                                    │  Chords  │     │
                                    └──────────┘     │
                                         ▲           │
                ┌────────────────┐       │           │
                │ DiatonicChords │───────┘           │
                │ (key-chord map)│───────────────────┘
                └───────┬────────┘
                        │
                   ┌────┴────┐
                   │  Keys   │
                   └─────────┘

┌──────────┐      ┌───────────────┐
│ Tunings  │◄────▶│ TuningStrings │
│          │ 1:N  │ (6+ rows each)│
└──────────┘      └───────────────┘
```

### 2.2 Table DDL

```sql
-- ============================================================
-- Notes: The 12 chromatic pitch classes
-- ============================================================
CREATE TABLE Notes (
    note_id        INTEGER PRIMARY KEY,          -- 0-11 (C=0, C#=1, ... B=11)
    name           TEXT    NOT NULL UNIQUE,       -- 'C', 'C#', 'D', ...
    enharmonic     TEXT,                          -- 'Db', 'Eb', etc. (NULL if none)
    midi_base      INTEGER NOT NULL               -- lowest octave MIDI (e.g. C0=12)
);

-- Seed data (12 rows)
-- note_id | name | enharmonic | midi_base
-- 0       | C    | NULL       | 12
-- 1       | C#   | Db         | 13
-- 2       | D    | NULL       | 14
-- ...
-- 11      | B    | NULL       | 23

-- ============================================================
-- Scales: Named scale formulas
-- ============================================================
CREATE TABLE Scales (
    scale_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL UNIQUE,       -- 'Major', 'Natural Minor', 'Harmonic Minor', ...
    mode_of        INTEGER REFERENCES Scales(scale_id),  -- NULL for parent scales
    degree_count   INTEGER NOT NULL               -- 7 for heptatonic, 5 for pentatonic, etc.
);

-- ============================================================
-- ScaleIntervals: Defines each scale's interval pattern
-- Intervals are stored as semitone offsets from the root.
-- ============================================================
CREATE TABLE ScaleIntervals (
    scale_id       INTEGER NOT NULL REFERENCES Scales(scale_id) ON DELETE CASCADE,
    degree         INTEGER NOT NULL,              -- 1-indexed scale degree (1 = root)
    semitone_offset INTEGER NOT NULL,             -- semitones from root (root = 0)
    degree_label   TEXT    NOT NULL,              -- 'P1','M2','M3','P4','P5','M6','M7' etc.
    PRIMARY KEY (scale_id, degree)
);

-- Example: Major scale intervals
-- scale_id=1, degree=1, semitone_offset=0,  degree_label='P1'
-- scale_id=1, degree=2, semitone_offset=2,  degree_label='M2'
-- scale_id=1, degree=3, semitone_offset=4,  degree_label='M3'
-- scale_id=1, degree=4, semitone_offset=5,  degree_label='P4'
-- scale_id=1, degree=5, semitone_offset=7,  degree_label='P5'
-- scale_id=1, degree=6, semitone_offset=9,  degree_label='M6'
-- scale_id=1, degree=7, semitone_offset=11, degree_label='M7'

-- ============================================================
-- Chords: Named chord formulas (triad, 7th, etc.)
-- ============================================================
CREATE TABLE Chords (
    chord_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL UNIQUE,       -- 'Major', 'Minor', 'Diminished', 'Augmented', 'Dom7', ...
    symbol         TEXT    NOT NULL,              -- '', 'm', '°', '+', '7', ...
    note_count     INTEGER NOT NULL               -- 3 for triads, 4 for 7ths, etc.
);

-- ============================================================
-- ChordIntervals: Interval structure of each chord type
-- ============================================================
CREATE TABLE ChordIntervals (
    chord_id       INTEGER NOT NULL REFERENCES Chords(chord_id) ON DELETE CASCADE,
    position       INTEGER NOT NULL,              -- 1=root, 2=third, 3=fifth, 4=seventh, ...
    semitone_offset INTEGER NOT NULL,             -- semitones from root
    interval_name  TEXT    NOT NULL,              -- 'P1', 'M3', 'P5', 'm3', 'dim5', etc.
    PRIMARY KEY (chord_id, position)
);

-- Example: Minor chord
-- chord_id=2, position=1, semitone_offset=0,  interval_name='P1'
-- chord_id=2, position=2, semitone_offset=3,  interval_name='m3'
-- chord_id=2, position=3, semitone_offset=7,  interval_name='P5'

-- ============================================================
-- Keys: Root + Scale combinations
-- ============================================================
CREATE TABLE Keys (
    key_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    root_note_id   INTEGER NOT NULL REFERENCES Notes(note_id),
    scale_id       INTEGER NOT NULL REFERENCES Scales(scale_id),
    name           TEXT    NOT NULL UNIQUE,       -- 'C Major', 'A Minor', 'F# Major', ...
    UNIQUE (root_note_id, scale_id)
);

-- ============================================================
-- DiatonicChords: Maps each scale degree to its chord quality
--                 within a key, with Roman numeral labels.
-- ============================================================
CREATE TABLE DiatonicChords (
    key_id             INTEGER NOT NULL REFERENCES Keys(key_id) ON DELETE CASCADE,
    degree             INTEGER NOT NULL,          -- 1–7 scale degree
    chord_id           INTEGER NOT NULL REFERENCES Chords(chord_id),
    root_note_id       INTEGER NOT NULL REFERENCES Notes(note_id),
    roman_numeral      TEXT    NOT NULL,          -- 'I','ii','iii','IV','V','vi','vii°'
    PRIMARY KEY (key_id, degree)
);

-- Example: C Major diatonic chords
-- key_id=1, degree=1, chord_id=1(Maj),  root_note_id=0(C),  roman_numeral='I'
-- key_id=1, degree=2, chord_id=2(Min),  root_note_id=2(D),  roman_numeral='ii'
-- key_id=1, degree=3, chord_id=2(Min),  root_note_id=4(E),  roman_numeral='iii'
-- key_id=1, degree=4, chord_id=1(Maj),  root_note_id=5(F),  roman_numeral='IV'
-- key_id=1, degree=5, chord_id=1(Maj),  root_note_id=7(G),  roman_numeral='V'
-- key_id=1, degree=6, chord_id=2(Min),  root_note_id=9(A),  roman_numeral='vi'
-- key_id=1, degree=7, chord_id=3(Dim),  root_note_id=11(B), roman_numeral='vii°'

-- ============================================================
-- Tunings: Named tuning presets
-- ============================================================
CREATE TABLE Tunings (
    tuning_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL UNIQUE,       -- 'Standard', 'Drop D', 'DADGAD', 'Open G', ...
    string_count   INTEGER NOT NULL DEFAULT 6
);

-- ============================================================
-- TuningStrings: Per-string open-note MIDI values
-- String 1 = highest pitched (thinnest), String 6 = lowest.
-- ============================================================
CREATE TABLE TuningStrings (
    tuning_id      INTEGER NOT NULL REFERENCES Tunings(tuning_id) ON DELETE CASCADE,
    string_number  INTEGER NOT NULL,              -- 1 (high E) to 6 (low E)
    open_note_midi INTEGER NOT NULL,              -- MIDI note number of the open string
    open_note_name TEXT    NOT NULL,              -- 'E4', 'B3', 'G3', 'D3', 'A2', 'E2'
    PRIMARY KEY (tuning_id, string_number)
);

-- Standard tuning seed:
-- tuning_id=1, string_number=1, open_note_midi=64, open_note_name='E4'
-- tuning_id=1, string_number=2, open_note_midi=59, open_note_name='B3'
-- tuning_id=1, string_number=3, open_note_midi=55, open_note_name='G3'
-- tuning_id=1, string_number=4, open_note_midi=50, open_note_name='D3'
-- tuning_id=1, string_number=5, open_note_midi=45, open_note_name='A2'
-- tuning_id=1, string_number=6, open_note_midi=40, open_note_name='E2'

-- ============================================================
-- Indexes for query performance
-- ============================================================
CREATE INDEX idx_scale_intervals_scale   ON ScaleIntervals(scale_id);
CREATE INDEX idx_chord_intervals_chord   ON ChordIntervals(chord_id);
CREATE INDEX idx_diatonic_key            ON DiatonicChords(key_id);
CREATE INDEX idx_tuning_strings_tuning   ON TuningStrings(tuning_id);
CREATE INDEX idx_keys_root_scale         ON Keys(root_note_id, scale_id);
```

### 2.3 Schema Rationale

| Design Decision | Why |
|----------------|-----|
| **MIDI integers for all pitches** | Enables O(1) interval arithmetic: `fret_note = open_midi + fret_number`. No string parsing in the hot path. |
| **Separate `ScaleIntervals` / `ChordIntervals` junction tables** | Scales and chords are defined by their *interval structure*, not by enumerated notes. This makes transposition trivial — just add the root's `note_id` to each offset, mod 12. |
| **`DiatonicChords` as a pre-computed join** | Avoids recomputing chord quality per degree at runtime. The Roman numeral column stores the display-ready label. |
| **`Tunings` / `TuningStrings` split** | Supports arbitrary string counts (7-string, bass, etc.) and custom per-string overrides without schema changes. |

---

## 3. C++ Algorithm Engine

The C++ layer is compiled into a shared library (`libfretengine.so` on Linux, `fretengine.dll` on Windows, `libfretengine.dylib` on macOS). It exposes a **flat C API** (no C++ name mangling) so Python can call it via `ctypes` with zero-copy integer arrays.

### 3.1 Header File: `fretengine.h`

```cpp
// =============================================================================
// fretengine.h — Guitar Fretboard Algorithm Engine
// Shared library interface (C linkage for ctypes compatibility)
// =============================================================================
#ifndef FRETENGINE_H
#define FRETENGINE_H

#include <cstdint>

#ifdef _WIN32
    #define FRETAPI __declspec(dllexport)
#else
    #define FRETAPI __attribute__((visibility("default")))
#endif

extern "C" {

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────
#define MAX_STRINGS     8
#define MAX_FRETS       24
#define MAX_SCALE_NOTES 12
#define MAX_CHORD_NOTES 7

// ─────────────────────────────────────────────────────────────────────────────
// Structs
// ─────────────────────────────────────────────────────────────────────────────

/// Represents the tuning of an entire instrument.
typedef struct {
    int32_t string_count;                       // Number of strings (typically 6)
    int32_t open_midi[MAX_STRINGS];             // MIDI note of each open string
    int32_t fret_count;                         // Number of frets (typically 21-24)
} Tuning;

/// A single fretboard cell: string + fret + computed pitch.
typedef struct {
    int32_t string_num;                         // 0-indexed string number
    int32_t fret;                               // 0 = open, 1–24
    int32_t midi_note;                          // Absolute MIDI note number
    int32_t pitch_class;                        // midi_note % 12 (0=C, 1=C#, ..., 11=B)
    int32_t in_scale;                           // 1 if this note is in the active scale
    int32_t scale_degree;                       // 1–7 if in_scale, else 0
    int32_t is_root;                            // 1 if this is the root of the scale/chord
} FretCell;

/// Full fretboard map: a 2D grid of FretCells.
typedef struct {
    int32_t string_count;
    int32_t fret_count;
    FretCell cells[MAX_STRINGS][MAX_FRETS + 1]; // +1 for open string (fret 0)
} FretboardMap;

/// A single finger placement within a chord voicing.
typedef struct {
    int32_t string_num;                         // 0-indexed
    int32_t fret;                               // 0 = open, -1 = muted
    int32_t midi_note;                          // Resulting pitch (-1 if muted)
    int32_t finger;                             // Suggested finger: 0=thumb,1=index,...,4=pinky,-1=open/muted
} FingerPlacement;

/// A complete chord voicing across all strings.
typedef struct {
    int32_t string_count;
    FingerPlacement placements[MAX_STRINGS];
    float   difficulty_score;                   // Lower = easier. Computed from span, barre, etc.
    int32_t min_fret;                           // Lowest fretted fret (0 if open chord)
    int32_t max_fret;                           // Highest fretted fret
    int32_t barre_fret;                         // -1 if no barre, else the barre fret
} ChordVoicing;

/// Result buffer for voicing search.
typedef struct {
    int32_t      count;                         // Number of voicings found
    ChordVoicing voicings[32];                  // Top 32 voicings, sorted by difficulty_score
} VoicingResult;

/// Tuning shift descriptor for the frontend.
/// When a user changes one string's pitch, this describes the horizontal
/// fret offset the frontend must apply to that string's row.
typedef struct {
    int32_t string_num;                         // Which string was retuned
    int32_t semitone_delta;                     // +N = tuned up N semitones, -N = tuned down
    int32_t fret_shift;                         // Number of frets to shift the visual display
                                                // (negative = shift left, positive = shift right)
} TuningShift;

typedef struct {
    int32_t count;
    TuningShift shifts[MAX_STRINGS];
} TuningShiftResult;

// ─────────────────────────────────────────────────────────────────────────────
// API Functions
// ─────────────────────────────────────────────────────────────────────────────

/// Compute the complete fretboard map for the given tuning.
/// `scale_offsets` is an array of semitone offsets (e.g., {0,2,4,5,7,9,11} for major).
/// `scale_len` is the number of elements in `scale_offsets`.
/// `root_pitch_class` is 0–11 (the root note of the scale).
/// Returns: 0 on success, negative on error.
FRETAPI int32_t fret_compute_map(
    const Tuning*    tuning,
    const int32_t*   scale_offsets,
    int32_t          scale_len,
    int32_t          root_pitch_class,
    FretboardMap*    out_map
);

/// Compute the note at a specific (string, fret) position.
/// Pure arithmetic: result = tuning->open_midi[string] + fret
FRETAPI int32_t fret_note_at(
    const Tuning*    tuning,
    int32_t          string_num,
    int32_t          fret
);

/// Find optimal chord voicings for a chord defined by its intervals.
/// `chord_offsets`: array of semitone offsets from root (e.g., {0, 4, 7} for major triad).
/// `chord_len`: number of notes in the chord.
/// `root_pitch_class`: 0–11.
/// `tuning`: current instrument tuning.
/// `max_span`: maximum allowed fret span for a single hand (typically 4–5).
/// `max_results`: how many voicings to return (capped at 32).
///
/// Algorithm:
///   1. For each string, enumerate frets [0..fret_count] whose pitch_class is in chord_tones.
///   2. Cartesian-product search with aggressive pruning:
///      a. Prune branches where fret span > max_span.
///      b. Prune branches missing the root on the lowest sounding string.
///      c. Allow muting of non-adjacent outer strings only.
///   3. Score each surviving voicing by difficulty (see scoring section below).
///   4. Sort by difficulty_score ascending, return top `max_results`.
///
/// Returns: 0 on success, negative on error.
FRETAPI int32_t fret_find_voicings(
    const Tuning*    tuning,
    const int32_t*   chord_offsets,
    int32_t          chord_len,
    int32_t          root_pitch_class,
    int32_t          max_span,
    int32_t          max_results,
    VoicingResult*   out_result
);

/// Compute the horizontal fret shift for each string when the user
/// changes from `reference_tuning` to `custom_tuning`.
///
/// Mathematical approach:
///   For each string i:
///     delta = custom.open_midi[i] - reference.open_midi[i]
///     shift = -delta   (tuning UP shifts the visual LEFT, tuning DOWN shifts RIGHT)
///
/// The frontend uses this to translate the fret markers horizontally
/// on a per-string basis, so that the *same finger position* produces
/// the visual note the user expects.
///
/// Returns: 0 on success, negative on error.
FRETAPI int32_t fret_compute_tuning_shifts(
    const Tuning*         reference_tuning,
    const Tuning*         custom_tuning,
    TuningShiftResult*    out_shifts
);

/// Compute the pitch class (0–11) of scale degree `degree` (1–7)
/// given a root pitch class and a scale interval array.
/// Useful for building diatonic chords dynamically.
FRETAPI int32_t fret_pitch_class_at_degree(
    int32_t          root_pitch_class,
    const int32_t*   scale_offsets,
    int32_t          scale_len,
    int32_t          degree
);

} // extern "C"

#endif // FRETENGINE_H
```

### 3.2 Mathematical Approach

#### 3.2.1 Core Pitch Arithmetic

All pitch calculations reduce to **integer modular arithmetic** on MIDI note numbers:

```
note_at(string, fret) = open_midi[string] + fret
pitch_class(midi)     = midi % 12
octave(midi)          = (midi / 12) - 1
```

#### 3.2.2 Scale Membership Test

Given a scale defined as an array of semitone offsets from the root (e.g., Major = `[0, 2, 4, 5, 7, 9, 11]`):

```
in_scale(pitch_class, root, offsets[]) =
    there exists i : (root + offsets[i]) % 12 == pitch_class
```

Implemented as a **12-element boolean lookup table** built once per `fret_compute_map` call — O(1) per cell lookup:

```cpp
bool scale_mask[12] = {false};
for (int i = 0; i < scale_len; i++) {
    scale_mask[(root_pitch_class + scale_offsets[i]) % 12] = true;
}
// Then for each cell:
cell.in_scale = scale_mask[cell.pitch_class] ? 1 : 0;
```

#### 3.2.3 Scale Degree Lookup

A parallel **degree map** is built for O(1) degree lookups:

```cpp
int8_t degree_map[12];
memset(degree_map, 0, sizeof(degree_map));
for (int i = 0; i < scale_len; i++) {
    degree_map[(root_pitch_class + scale_offsets[i]) % 12] = i + 1;  // 1-indexed
}
// Then: cell.scale_degree = degree_map[cell.pitch_class];
```

#### 3.2.4 Tuning Shift Calculation

When a user changes one string's tuning:

```
delta_semitones[i] = custom_midi[i] - reference_midi[i]
fret_shift[i]      = -delta_semitones[i]
```

**Intuition:** If string 6 is tuned from E2 (MIDI 40) down to D2 (MIDI 38), delta = -2. The visual shift is +2 frets to the right — because what was at fret 2 (originally F#) is now at fret 4 in the new tuning to produce the same pitch. The frontend applies `transform: translateX(shift * fretWidth)` per string row.

#### 3.2.5 Chord Voicing Search — Constrained DFS

The voicing algorithm performs a **depth-first search** over the string x fret space with aggressive pruning:

```
function findVoicings(strings, chordTones, maxSpan):
    candidates = []
    
    // Phase 1: Build per-string candidate frets
    for each string s in [0..N-1]:
        s.candidates = []
        for fret f in [0..maxFrets]:
            pc = (openMidi[s] + f) % 12
            if pc in chordTones:
                s.candidates.append({fret: f, pitchClass: pc})
        s.candidates.append({fret: -1, pitchClass: -1})  // muted option
    
    // Phase 2: DFS with pruning
    function dfs(stringIdx, currentVoicing, usedTones, minFret, maxFret):
        if stringIdx == N:
            if root is in lowest sounding string AND all chord tones covered:
                score = computeDifficulty(currentVoicing)
                candidates.append((currentVoicing, score))
            return
        
        for each candidate c in strings[stringIdx].candidates:
            if c.fret == -1:  // muted
                dfs(stringIdx + 1, currentVoicing + c, usedTones, minFret, maxFret)
            else:
                newMin = min(minFret, c.fret) if c.fret > 0 else minFret
                newMax = max(maxFret, c.fret) if c.fret > 0 else maxFret
                if newMax - newMin <= maxSpan:  // PRUNE: span check
                    dfs(stringIdx + 1, currentVoicing + c,
                        usedTones union {c.pitchClass}, newMin, newMax)
    
    dfs(0, [], {}, INT_MAX, 0)
    sort candidates by score ascending
    return top K candidates
```

#### 3.2.6 Voicing Difficulty Scoring

```
difficulty_score = w1 * fret_span
                 + w2 * num_muted_strings
                 + w3 * (barre_required ? barre_penalty : 0)
                 + w4 * avg_fret_position         // higher positions = harder
                 + w5 * finger_stretch_penalty     // non-uniform gaps between fingers
```

Default weights: `w1=2.0, w2=1.5, w3=3.0, w4=0.5, w5=1.0`. These are tunable constants.

#### 3.2.7 Finger Assignment Heuristic

After a voicing's fret positions are chosen, fingers are assigned bottom-up:

1. If a barre is detected (multiple strings at the same fret), assign index finger (1) to the barre.
2. Remaining fretted notes are assigned fingers 2–4 (middle, ring, pinky) from lowest fret to highest.
3. Open strings get `finger = -1`.

### 3.3 Implementation Files

```
engine/
├── include/
│   └── fretengine.h          # Public C API header (shown above)
├── src/
│   ├── fretboard_map.cpp     # fret_compute_map, fret_note_at, fret_pitch_class_at_degree
│   ├── voicing_search.cpp    # fret_find_voicings (DFS + scoring)
│   ├── tuning_shift.cpp      # fret_compute_tuning_shifts
│   └── util.cpp              # Scale mask builders, modular arithmetic helpers
├── tests/
│   ├── test_map.cpp           # Unit tests for fretboard mapping
│   ├── test_voicings.cpp      # Unit tests for voicing search
│   └── test_tuning.cpp        # Unit tests for tuning shift
├── CMakeLists.txt             # Build configuration
└── README.md
```

### 3.4 CMake Build Configuration

```cmake
cmake_minimum_required(VERSION 3.16)
project(fretengine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)         # Required for shared libs

add_library(fretengine SHARED
    src/fretboard_map.cpp
    src/voicing_search.cpp
    src/tuning_shift.cpp
    src/util.cpp
)

target_include_directories(fretengine PUBLIC include)

# Platform-specific output naming
if(WIN32)
    set_target_properties(fretengine PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
        PREFIX ""
        SUFFIX ".dll"
    )
else()
    set_target_properties(fretengine PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
    )
endif()

# Tests (optional, requires GoogleTest)
option(BUILD_TESTS "Build unit tests" OFF)
if(BUILD_TESTS)
    enable_testing()
    find_package(GTest REQUIRED)
    add_executable(fretengine_tests
        tests/test_map.cpp
        tests/test_voicings.cpp
        tests/test_tuning.cpp
    )
    target_link_libraries(fretengine_tests fretengine GTest::GTest GTest::Main)
    add_test(NAME FretEngineTests COMMAND fretengine_tests)
endif()
```

---

## 4. Python REST API

### 4.1 Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Framework | **FastAPI** | Async-ready, auto-generated OpenAPI docs, Pydantic validation. |
| DB Access | **sqlite3** (stdlib) | Zero-dependency, sufficient for single-user/embedded use. |
| C++ Binding | **ctypes** | No build-time dependency on pybind11; the C API is flat and struct-based. |
| Server | **Uvicorn** | ASGI server, pairs natively with FastAPI. |

### 4.2 Project Structure

```
api/
├── main.py                    # FastAPI application entry point
├── config.py                  # Paths, constants, environment vars
├── database/
│   ├── __init__.py
│   ├── connection.py          # SQLite connection pool / context manager
│   ├── seed.py                # Initial data seeding script
│   └── queries.py             # Parameterized query functions
├── engine/
│   ├── __init__.py
│   └── bindings.py            # ctypes struct definitions + function wrappers
├── routers/
│   ├── __init__.py
│   ├── scales.py              # /api/scales endpoints
│   ├── chords.py              # /api/chords endpoints
│   ├── keys.py                # /api/keys endpoints
│   ├── tunings.py             # /api/tunings endpoints
│   └── fretboard.py           # /api/fretboard endpoints (calls C++ engine)
├── models/
│   ├── __init__.py
│   └── schemas.py             # Pydantic request/response models
├── requirements.txt
└── tests/
    ├── test_scales.py
    ├── test_chords.py
    ├── test_fretboard.py
    └── conftest.py
```

### 4.3 ctypes Binding Layer (`engine/bindings.py`)

```python
"""
ctypes bindings to libfretengine.

All C structs are mirrored as ctypes.Structure subclasses.
Functions are loaded once at module import and wrapped with
type-safe Python callables.
"""
import ctypes
import platform
from pathlib import Path

# -- Load shared library -----------------------------------------------
_LIB_DIR = Path(__file__).resolve().parent.parent.parent / "engine" / "build"

if platform.system() == "Windows":
    _LIB_PATH = _LIB_DIR / "bin" / "fretengine.dll"
elif platform.system() == "Darwin":
    _LIB_PATH = _LIB_DIR / "lib" / "libfretengine.dylib"
else:
    _LIB_PATH = _LIB_DIR / "lib" / "libfretengine.so"

_lib = ctypes.CDLL(str(_LIB_PATH))

# -- Constants ---------------------------------------------------------
MAX_STRINGS = 8
MAX_FRETS = 24
MAX_CHORD_NOTES = 7

# -- Struct mirrors ----------------------------------------------------
class Tuning(ctypes.Structure):
    _fields_ = [
        ("string_count", ctypes.c_int32),
        ("open_midi", ctypes.c_int32 * MAX_STRINGS),
        ("fret_count", ctypes.c_int32),
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
    ]

class VoicingResult(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_int32),
        ("voicings", ChordVoicing * 32),
    ]

class TuningShift(ctypes.Structure):
    _fields_ = [
        ("string_num", ctypes.c_int32),
        ("semitone_delta", ctypes.c_int32),
        ("fret_shift", ctypes.c_int32),
    ]

class TuningShiftResult(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_int32),
        ("shifts", TuningShift * MAX_STRINGS),
    ]

# -- Function signatures -----------------------------------------------
_lib.fret_compute_map.argtypes = [
    ctypes.POINTER(Tuning),
    ctypes.POINTER(ctypes.c_int32),
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.POINTER(FretboardMap),
]
_lib.fret_compute_map.restype = ctypes.c_int32

_lib.fret_find_voicings.argtypes = [
    ctypes.POINTER(Tuning),
    ctypes.POINTER(ctypes.c_int32),
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.POINTER(VoicingResult),
]
_lib.fret_find_voicings.restype = ctypes.c_int32

_lib.fret_compute_tuning_shifts.argtypes = [
    ctypes.POINTER(Tuning),
    ctypes.POINTER(Tuning),
    ctypes.POINTER(TuningShiftResult),
]
_lib.fret_compute_tuning_shifts.restype = ctypes.c_int32

# -- Pythonic wrappers -------------------------------------------------
def make_tuning(open_midis: list[int], fret_count: int = 24) -> Tuning:
    """Create a Tuning struct from a list of open-string MIDI values."""
    t = Tuning()
    t.string_count = len(open_midis)
    for i, midi in enumerate(open_midis):
        t.open_midi[i] = midi
    t.fret_count = fret_count
    return t

def compute_fretboard(
    open_midis: list[int],
    scale_offsets: list[int],
    root_pitch_class: int,
    fret_count: int = 24,
) -> dict:
    """Compute the full fretboard map and return as a serializable dict."""
    tuning = make_tuning(open_midis, fret_count)
    offsets_arr = (ctypes.c_int32 * len(scale_offsets))(*scale_offsets)
    fb_map = FretboardMap()

    rc = _lib.fret_compute_map(
        ctypes.byref(tuning), offsets_arr, len(scale_offsets),
        root_pitch_class, ctypes.byref(fb_map)
    )
    if rc != 0:
        raise RuntimeError(f"fret_compute_map failed with code {rc}")

    # Convert to JSON-serializable structure
    result = []
    for s in range(fb_map.string_count):
        string_data = []
        for f in range(fb_map.fret_count + 1):
            cell = fb_map.cells[s][f]
            string_data.append({
                "string": cell.string_num,
                "fret": cell.fret,
                "midi": cell.midi_note,
                "pitchClass": cell.pitch_class,
                "inScale": bool(cell.in_scale),
                "degree": cell.scale_degree,
                "isRoot": bool(cell.is_root),
            })
        result.append(string_data)
    return {"strings": result}
```

### 4.4 REST Endpoint Structure

All endpoints are prefixed with `/api/v1`.

#### Scales

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/api/v1/scales` | List all scales | `[{id, name, degreeCount}]` |
| `GET` | `/api/v1/scales/{id}` | Get scale detail + intervals | `{id, name, intervals: [{degree, semitoneOffset, label}]}` |
| `GET` | `/api/v1/scales/{id}/notes?root={pitchClass}` | Get concrete note names for a scale in a key | `{root, scaleName, notes: ["C","D","E",...]}` |

#### Chords

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/api/v1/chords` | List all chord types | `[{id, name, symbol, noteCount}]` |
| `GET` | `/api/v1/chords/{id}` | Get chord detail + intervals | `{id, name, symbol, intervals: [{position, semitoneOffset, intervalName}]}` |

#### Keys

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/api/v1/keys` | List all keys | `[{id, name, rootNoteId, scaleId}]` |
| `GET` | `/api/v1/keys/{id}/diatonic` | Get diatonic chords for a key | `{keyName, chords: [{degree, romanNumeral, chordName, rootNote}]}` |

#### Tunings

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/api/v1/tunings` | List preset tunings | `[{id, name, stringCount}]` |
| `GET` | `/api/v1/tunings/{id}` | Get tuning detail | `{id, name, strings: [{stringNumber, openMidi, openNoteName}]}` |
| `POST` | `/api/v1/tunings/shifts` | Compute per-string visual shifts | Request: `{reference: [midi...], custom: [midi...]}` / Response: `{shifts: [{string, delta, fretShift}]}` |

#### Fretboard (Hot Path — calls C++ engine)

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `POST` | `/api/v1/fretboard/map` | Compute full fretboard map | Request: `{openMidis, scaleOffsets, rootPitchClass, fretCount?}` / Response: `{strings: [[FretCell...]]}` |
| `POST` | `/api/v1/fretboard/voicings` | Find optimal chord voicings | Request: `{openMidis, chordOffsets, rootPitchClass, maxSpan?, maxResults?}` / Response: `{voicings: [ChordVoicing...]}` |

#### Example Pydantic Schemas (`models/schemas.py`)

```python
from pydantic import BaseModel, Field

class FretboardMapRequest(BaseModel):
    open_midis: list[int] = Field(..., min_length=1, max_length=8,
        description="MIDI note numbers for each open string, high to low")
    scale_offsets: list[int] = Field(..., min_length=1, max_length=12,
        description="Semitone offsets from root defining the scale")
    root_pitch_class: int = Field(..., ge=0, le=11,
        description="Root note pitch class (0=C, 1=C#, ..., 11=B)")
    fret_count: int = Field(default=24, ge=12, le=24)

class VoicingRequest(BaseModel):
    open_midis: list[int] = Field(..., min_length=1, max_length=8)
    chord_offsets: list[int] = Field(..., min_length=2, max_length=7)
    root_pitch_class: int = Field(..., ge=0, le=11)
    max_span: int = Field(default=4, ge=3, le=6)
    max_results: int = Field(default=8, ge=1, le=32)

class TuningShiftRequest(BaseModel):
    reference: list[int] = Field(..., min_length=1, max_length=8)
    custom: list[int] = Field(..., min_length=1, max_length=8)
```

### 4.5 CORS & Startup

```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import scales, chords, keys, tunings, fretboard
from .database.connection import init_db

app = FastAPI(
    title="Fretboard Visualizer API",
    version="1.0.0",
    description="Backend API bridging SQLite music theory data and C++ fretboard engine."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],    # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    init_db()

app.include_router(scales.router,    prefix="/api/v1/scales",    tags=["Scales"])
app.include_router(chords.router,    prefix="/api/v1/chords",    tags=["Chords"])
app.include_router(keys.router,      prefix="/api/v1/keys",      tags=["Keys"])
app.include_router(tunings.router,   prefix="/api/v1/tunings",   tags=["Tunings"])
app.include_router(fretboard.router, prefix="/api/v1/fretboard", tags=["Fretboard"])
```

---

## 5. TypeScript / HTML / CSS Frontend

### 5.1 Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Bundler | **Vite** | Fast HMR, native TS support, zero-config. |
| UI Library | **Vanilla TS + Web Components** or **Lit** | Minimal overhead; this is a single-page visualizer, not a CRUD app. Keeps the stack to pure HTML/CSS/TS as required. |
| State | **Custom reactive store** (Proxy-based) | Avoids framework dependency. Simple pub/sub for tuning, scale, and chord state. |
| CSS | **Vanilla CSS with custom properties** | CSS variables for theming; no preprocessor needed. |

### 5.2 Project Structure

```
frontend/
├── index.html                          # Shell HTML
├── vite.config.ts                      # Vite configuration
├── tsconfig.json
├── package.json
├── public/
│   └── favicon.svg
├── src/
│   ├── main.ts                         # Entry point: mount app, init store
│   ├── api/
│   │   └── client.ts                   # Typed fetch wrappers for all API endpoints
│   ├── state/
│   │   ├── store.ts                    # Reactive state store (Proxy-based)
│   │   └── types.ts                    # State interfaces (AppState, Tuning, etc.)
│   ├── components/
│   │   ├── FretboardRenderer.ts        # Core SVG/Canvas fretboard grid
│   │   ├── FretMarker.ts              # Individual note dot on the fretboard
│   │   ├── StringRow.ts               # One horizontal row (string) with shift transform
│   │   ├── ScaleToggle.ts             # Major/Minor toggle switch
│   │   ├── KeySelector.ts            # Root note dropdown (C, C#, D, ...)
│   │   ├── TuningPanel.ts            # Per-string pitch selectors
│   │   ├── ChordBar.ts               # Horizontal bar of Roman numeral chord buttons
│   │   ├── ChordDiagram.ts           # Mini chord diagram overlay
│   │   └── ViewModeSwitch.ts         # Scale View / Chord View toggle
│   ├── utils/
│   │   ├── music.ts                   # Note names, pitch class helpers
│   │   └── dom.ts                     # DOM creation helpers, SVG namespace utils
│   └── styles/
│       ├── global.css                 # CSS reset, custom properties, typography
│       ├── fretboard.css              # Fretboard grid layout, string/fret lines
│       ├── markers.css                # Note dot styles, scale-degree color coding
│       ├── controls.css               # Buttons, dropdowns, toggles
│       ├── chord-bar.css              # Roman numeral button strip
│       ├── tuning-panel.css           # Per-string tuning controls
│       └── animations.css             # Transitions, hover effects, shift animations
└── tests/
    ├── store.test.ts
    └── music.test.ts
```

### 5.3 Component Architecture Diagram

```
┌────────────────────────────────────────────────────────────┐
│                        App Shell                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   Control Bar                         │   │
│  │  ┌────────────┐ ┌───────────┐ ┌───────────────────┐  │   │
│  │  │ViewMode    │ │KeySelector│ │  ScaleToggle      │  │   │
│  │  │Switch      │ │ C C# D ..│ │  Major <-> Minor  │  │   │
│  │  └────────────┘ └───────────┘ └───────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              ChordBar  (visible in Chord View)        │   │
│  │  ┌───┐ ┌───┐ ┌────┐ ┌───┐ ┌───┐ ┌───┐ ┌─────┐      │   │
│  │  │ I │ │ii │ │iii │ │IV │ │ V │ │vi │ │vii° │      │   │
│  │  └───┘ └───┘ └────┘ └───┘ └───┘ └───┘ └─────┘      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌────────────┐  ┌───────────────────────────────────────┐  │
│  │TuningPanel │  │         FretboardRenderer              │  │
│  │            │  │                                        │  │
│  │  E4 [+][-]│  │  String 1: --o--o--o--o--o--o--o--o--  │  │
│  │  B3 [+][-]│  │  String 2: --o--o--o--o--o--o--o--o--  │  │
│  │  G3 [+][-]│  │  String 3: --o--o--o--o--o--o--o--o--  │  │
│  │  D3 [+][-]│  │  String 4: --o--o--o--o--o--o--o--o--  │  │
│  │  A2 [+][-]│  │  String 5: --o--o--o--o--o--o--o--o--  │  │
│  │  E2 [+][-]│  │  String 6: --o--o--o--o--o--o--o--o--  │  │
│  │            │  │                                        │  │
│  │            │  │  Fret:  0  1  2  3  4  5  6  7  8 ... │  │
│  └────────────┘  └───────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          ChordDiagram  (overlay, Chord View only)     │   │
│  │          Renders selected voicing with finger numbers │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 5.4 Reactive State Store

```typescript
// state/types.ts

export interface AppState {
  // View mode
  viewMode: 'scale' | 'chord';

  // Key selection
  rootPitchClass: number;      // 0-11
  scaleType: 'major' | 'minor';

  // Tuning (per-string MIDI values, index 0 = highest string)
  tuning: number[];            // e.g., [64, 59, 55, 50, 45, 40] for standard
  referenceTuning: number[];   // Standard tuning for shift calculation

  // Fretboard data (from API)
  fretboardMap: FretCellData[][] | null;
  tuningShifts: TuningShiftData[] | null;

  // Chord view
  diatonicChords: DiatonicChordData[] | null;
  selectedChordDegree: number | null;  // 1-7
  activeVoicing: VoicingData | null;

  // UI
  fretCount: number;           // default 24
  isLoading: boolean;
}

export interface FretCellData {
  string: number;
  fret: number;
  midi: number;
  pitchClass: number;
  inScale: boolean;
  degree: number;
  isRoot: boolean;
}

export interface TuningShiftData {
  string: number;
  delta: number;
  fretShift: number;
}

export interface DiatonicChordData {
  degree: number;
  romanNumeral: string;
  chordName: string;
  rootNote: string;
  chordOffsets: number[];
  rootPitchClass: number;
}

export interface VoicingData {
  placements: { string: number; fret: number; finger: number }[];
  difficultyScore: number;
  minFret: number;
  maxFret: number;
  barreFret: number;
}
```

```typescript
// state/store.ts

import { AppState } from './types';

type Listener = (state: AppState, changedKey: keyof AppState) => void;

class Store {
  private listeners: Listener[] = [];
  private state: AppState;

  constructor(initial: AppState) {
    // Wrap state in a Proxy to detect mutations
    this.state = new Proxy(initial, {
      set: (target, prop, value) => {
        (target as any)[prop] = value;
        this.notify(prop as keyof AppState);
        return true;
      },
    });
  }

  get(): AppState {
    return this.state;
  }

  /** Batch-update multiple keys and fire a single notification per key. */
  update(partial: Partial<AppState>): void {
    for (const [key, value] of Object.entries(partial)) {
      (this.state as any)[key] = value;
    }
  }

  subscribe(listener: Listener): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify(key: keyof AppState): void {
    for (const listener of this.listeners) {
      listener(this.state, key);
    }
  }
}

export const store = new Store({ /* ... default initial state ... */ } as AppState);
```

### 5.5 Component Behaviors

#### `FretboardRenderer`

- **Renders** an SVG grid: horizontal lines for strings, vertical lines for frets.
- **Subscribes** to `store` for `fretboardMap`, `tuningShifts`, `activeVoicing`.
- **Per-string horizontal shift:** When `tuningShifts` data is present, each `StringRow` group receives a CSS transform:
  ```css
  .string-row[data-shift] {
      transition: transform 0.4s cubic-bezier(0.25, 0.1, 0.25, 1);
  }
  ```
  ```typescript
  // Applied dynamically:
  stringGroup.style.transform = `translateX(${shift.fretShift * FRET_WIDTH_PX}px)`;
  ```
- **Fret markers** are `<circle>` elements colored by scale degree. Root notes use an accent ring.

#### `ScaleToggle`

- Toggles `store.scaleType` between `'major'` and `'minor'`.
- On change: API call to `/api/v1/fretboard/map` with the corresponding scale offsets:
  - Major: `[0, 2, 4, 5, 7, 9, 11]`
  - Minor: `[0, 2, 3, 5, 7, 8, 10]`
- Result updates `store.fretboardMap`, triggering a re-render.

#### `TuningPanel`

- Shows one row per string with the current note name and up/down semitone buttons.
- On change: updates `store.tuning[stringIndex]` plus/minus 1.
- Fires two API calls in parallel:
  1. `POST /api/v1/tunings/shifts` to update `store.tuningShifts`.
  2. `POST /api/v1/fretboard/map` with new tuning to update `store.fretboardMap`.

#### `ChordBar`

- Visible only when `store.viewMode === 'chord'`.
- On mount: fetches `GET /api/v1/keys/{keyId}/diatonic` to populate buttons.
- Each button displays the Roman numeral label. On click:
  1. Sets `store.selectedChordDegree`.
  2. Calls `POST /api/v1/fretboard/voicings` with the chord's interval offsets.
  3. Updates `store.activeVoicing` with the top-scoring result.

#### `ChordDiagram`

- Overlays finger-position dots on the fretboard.
- Renders finger numbers (1–4) inside each dot.
- Muted strings display an X above the nut.
- Open strings display an O above the nut.
- Includes a barre indicator (horizontal bar) when `voicing.barreFret >= 0`.

### 5.6 CSS Design System

```css
/* styles/global.css */

:root {
  /* -- Color palette -- */
  --bg-primary:        #0a0a0f;
  --bg-secondary:      #12121a;
  --bg-surface:        #1a1a2e;
  --bg-surface-hover:  #252540;

  --text-primary:      #e8e8f0;
  --text-secondary:    #8888aa;
  --text-muted:        #555570;

  --accent-root:       #ff6b6b;       /* Root note highlight */
  --accent-scale:      #4ecdc4;       /* In-scale notes */
  --accent-chord:      #ffe66d;       /* Chord tones */
  --accent-blue:       #45b7d1;       /* Interactive elements */

  /* Degree-based coloring (rainbow, subtle) */
  --degree-1:          #ff6b6b;       /* Root / Tonic */
  --degree-2:          #ff9f43;
  --degree-3:          #feca57;
  --degree-4:          #48dbfb;
  --degree-5:          #0abde3;
  --degree-6:          #a29bfe;
  --degree-7:          #fd79a8;

  /* -- Spacing -- */
  --fret-width:        52px;
  --string-gap:        36px;
  --marker-radius:     14px;

  /* -- Typography -- */
  --font-family:       'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono:         'JetBrains Mono', 'Fira Code', monospace;

  /* -- Effects -- */
  --glow-root:         0 0 12px rgba(255, 107, 107, 0.6);
  --glow-scale:        0 0 8px  rgba(78, 205, 196, 0.4);
  --transition-fast:   150ms cubic-bezier(0.25, 0.1, 0.25, 1);
  --transition-smooth: 400ms cubic-bezier(0.25, 0.1, 0.25, 1);

  /* -- Glass effect -- */
  --glass-bg:          rgba(26, 26, 46, 0.7);
  --glass-border:      rgba(255, 255, 255, 0.08);
  --glass-blur:        12px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font-family);
  background: var(--bg-primary);
  color: var(--text-primary);
  min-height: 100vh;
  overflow-x: hidden;
}
```

```css
/* styles/markers.css -- Reactive note markers */

.fret-marker {
  r: var(--marker-radius);
  fill: var(--bg-surface);
  stroke: var(--text-muted);
  stroke-width: 1.5;
  opacity: 0.3;
  transition: all var(--transition-fast);
  cursor: pointer;
}

.fret-marker.in-scale {
  fill: var(--accent-scale);
  stroke: none;
  opacity: 0.9;
  filter: drop-shadow(var(--glow-scale));
}

.fret-marker.is-root {
  fill: var(--accent-root);
  stroke: white;
  stroke-width: 2;
  opacity: 1;
  filter: drop-shadow(var(--glow-root));
  animation: pulse-root 2s ease-in-out infinite;
}

.fret-marker.chord-tone {
  fill: var(--accent-chord);
  opacity: 1;
  r: calc(var(--marker-radius) + 2px);
}

/* Degree-specific coloring */
.fret-marker[data-degree="1"] { fill: var(--degree-1); }
.fret-marker[data-degree="2"] { fill: var(--degree-2); }
.fret-marker[data-degree="3"] { fill: var(--degree-3); }
.fret-marker[data-degree="4"] { fill: var(--degree-4); }
.fret-marker[data-degree="5"] { fill: var(--degree-5); }
.fret-marker[data-degree="6"] { fill: var(--degree-6); }
.fret-marker[data-degree="7"] { fill: var(--degree-7); }

.fret-marker:hover {
  r: calc(var(--marker-radius) + 4px);
  filter: brightness(1.3) drop-shadow(0 0 16px currentColor);
}

@keyframes pulse-root {
  0%, 100% { r: var(--marker-radius); }
  50%      { r: calc(var(--marker-radius) + 2px); }
}
```

```css
/* styles/animations.css -- Tuning shift transitions */

.string-row {
  transition: transform var(--transition-smooth);
  will-change: transform;
}

.string-row.shifting {
  /* Brief flash effect during shift */
  animation: shift-flash 0.6s ease-out;
}

@keyframes shift-flash {
  0%   { filter: brightness(1); }
  30%  { filter: brightness(1.5); }
  100% { filter: brightness(1); }
}

/* Chord view enter/exit */
.chord-bar {
  transform: translateY(-20px);
  opacity: 0;
  transition: all 0.3s ease-out;
}

.chord-bar.visible {
  transform: translateY(0);
  opacity: 1;
}

.chord-button {
  transition: all var(--transition-fast);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
}

.chord-button:hover {
  background: var(--bg-surface-hover);
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

.chord-button.active {
  border-color: var(--accent-chord);
  box-shadow: 0 0 16px rgba(255, 230, 109, 0.3);
}
```

---

## 6. Data Flow & Sequence Diagrams

### 6.1 Scale View — User Selects "A Minor"

```
User clicks KeySelector -> "A" (pitchClass=9)
User clicks ScaleToggle -> "Minor"
                |
                v
        +-----------------+
        |  TypeScript      |  store.rootPitchClass = 9
        |  Store Update    |  store.scaleType = 'minor'
        +--------+--------+
                 |
                 v
        POST /api/v1/fretboard/map
        Body: {
          openMidis: [64,59,55,50,45,40],
          scaleOffsets: [0,2,3,5,7,8,10],   <-- Natural Minor
          rootPitchClass: 9,
          fretCount: 24
        }
                 |
                 v
        +-----------------+
        |  Python API      |  Converts to ctypes structs
        |  (FastAPI)       |  Calls _lib.fret_compute_map()
        +--------+--------+
                 |
                 v
        +-----------------+
        |  C++ Engine      |  Builds scale_mask[12], iterates 6x25 cells,
        |  (libfret)       |  fills FretboardMap with in_scale/degree/isRoot
        +--------+--------+
                 |
                 v
        JSON response -> store.fretboardMap updated
                 |
                 v
        FretboardRenderer re-renders markers
        Root notes (A) glow red, scale tones glow teal
```

### 6.2 Custom Tuning — User Tunes String 6 Down to D

```
User clicks [-] on String 6 (E2 -> D#2 -> D2)
                |
                v
        store.tuning[5] = 38  (was 40)
                |
                +-----------------------------------+
                v                                   v
        POST /api/v1/tunings/shifts          POST /api/v1/fretboard/map
        Body: {                              Body: {
          reference: [64,59,55,50,45,40],      openMidis: [64,59,55,50,45,38],
          custom:    [64,59,55,50,45,38]       scaleOffsets: [...],
        }                                      rootPitchClass: 9
                |                              }
                v                                   |
        C++ fret_compute_tuning_shifts()            v
        -> shifts[5] = {delta: -2, shift: +2}   C++ fret_compute_map()
                |                                   |
                v                                   v
        store.tuningShifts updated           store.fretboardMap updated
                |                                   |
                +----------------+------------------+
                                 v
                    FretboardRenderer:
                    - String 6 row: transform: translateX(+2 * 52px)
                    - All markers re-colored with new pitch data
                    - Smooth CSS transition plays
```

### 6.3 Chord View — User Selects "V" in C Major

```
User selects ViewMode -> "Chord"
User selects Key -> "C Major" (key_id=1)
                |
                v
        GET /api/v1/keys/1/diatonic
                |
                v
        +-----------------+
        |  Python API      |  SELECT dc.*, c.name, c.symbol, n.name
        |                  |  FROM DiatonicChords dc
        |                  |  JOIN Chords c, Notes n ...
        |                  |  WHERE dc.key_id = 1
        +--------+--------+
                 |
                 v
        store.diatonicChords = [
          {degree:1, roman:'I',    chord:'Major', root:'C', offsets:[0,4,7],  rootPC:0},
          {degree:2, roman:'ii',   chord:'Minor', root:'D', offsets:[0,3,7],  rootPC:2},
          {degree:3, roman:'iii',  chord:'Minor', root:'E', offsets:[0,3,7],  rootPC:4},
          {degree:4, roman:'IV',   chord:'Major', root:'F', offsets:[0,4,7],  rootPC:5},
          {degree:5, roman:'V',    chord:'Major', root:'G', offsets:[0,4,7],  rootPC:7},
          {degree:6, roman:'vi',   chord:'Minor', root:'A', offsets:[0,3,7],  rootPC:9},
          {degree:7, roman:'vii*', chord:'Dim',   root:'B', offsets:[0,3,6],  rootPC:11},
        ]
        -> ChordBar renders 7 buttons
                |
        User clicks "V" (G Major)
                |
                v
        POST /api/v1/fretboard/voicings
        Body: {
          openMidis: [64,59,55,50,45,40],
          chordOffsets: [0, 4, 7],
          rootPitchClass: 7,     <-- G
          maxSpan: 4,
          maxResults: 8
        }
                |
                v
        C++ fret_find_voicings()
        -> DFS over 6 strings, prune by span,
           score by difficulty, return top 8
                |
                v
        store.activeVoicing = voicings[0]  (easiest)
        -> ChordDiagram renders finger dots + barre
        -> FretboardRenderer highlights chord tones in gold
```

---

## 7. Build & Deployment

### 7.1 Directory Layout (Monorepo)

```
fretboard-visualizer/
├── engine/                     # C++ shared library
│   ├── include/
│   ├── src/
│   ├── tests/
│   └── CMakeLists.txt
├── api/                        # Python FastAPI backend
│   ├── main.py
│   ├── database/
│   ├── engine/
│   ├── routers/
│   ├── models/
│   ├── requirements.txt
│   └── tests/
├── frontend/                   # TypeScript + HTML + CSS
│   ├── src/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── data/
│   └── fretboard.db            # SQLite database (generated by seed script)
├── scripts/
│   ├── build_engine.sh         # cmake + make for C++ lib
│   ├── seed_db.py              # Populate SQLite with music theory data
│   └── dev.sh                  # Start all services for development
├── ARCHITECTURE_PLAN.md        # This document
└── README.md
```

### 7.2 Build Steps

```bash
# 1. Build C++ engine
cd engine
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release

# 2. Seed database
cd ../api
python -m database.seed          # Creates ../data/fretboard.db

# 3. Start Python API
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 4. Start frontend dev server
cd ../frontend
npm install
npm run dev                      # Vite on http://localhost:5173
```

### 7.3 Key Design Constraints & Trade-offs

| Constraint | Decision | Trade-off |
|------------|----------|-----------|
| C++ must be a shared library | Flat C API with `extern "C"` | Loses C++ type safety at the boundary; gained universal FFI compatibility. |
| Python calls C++ via ctypes | Zero-copy integer arrays, struct mirrors | Must manually keep Python struct definitions in sync with `fretengine.h`. |
| SQLite for persistence | Single-file DB, no server process | Not suitable for concurrent multi-user writes; fine for this single-user visualizer. |
| Vanilla TS (no React/Vue) | Proxy-based store + manual DOM updates | More boilerplate than a framework; gained zero-dependency frontend per requirements. |
| Per-string horizontal shift for tuning | CSS `transform: translateX()` | Elegant visually; requires the fretboard to have overflow clipping per string row. |
| Voicing search is DFS with pruning | Worst-case exponential but bounded by MAX_FRETS x MAX_STRINGS | 6 strings x 25 frets = manageable; max_span constraint prunes >99% of branches. |

---

*End of Architecture Plan.*
