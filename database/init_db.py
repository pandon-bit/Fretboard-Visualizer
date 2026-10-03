"""
init_db.py — Database Initialization & Seeding for Guitar Fretboard Visualizer

Initializes 'music_models.db' with relational music models:
- 12 Chromatic Pitch Classes (Notes)
- Scale Formulas & Degree Intervals (Major, Natural Minor, Harmonic Minor, Pentatonic, etc.)
- Chord Formulas & Interval Structures (Major, Minor, Diminished, Augmented, 7ths)
- Keys (all 12 chromatic roots for Major & Minor)
- Diatonic Chords & Roman Numeral analysis (I-vii° for Major, i-VII for Minor)
- Presets for Tunings and Per-String MIDI notes (Standard, Drop D, DADGAD, Open D/G)
"""

import os
import sqlite3
import sys
from pathlib import Path


DB_FILENAME = "music_models.db"


def create_schema(cursor: sqlite3.Cursor) -> None:
    """Creates the relational database schema."""
    cursor.executescript("""
    PRAGMA foreign_keys = ON;

    -- ============================================================
    -- Notes: The 12 chromatic pitch classes
    -- ============================================================
    DROP TABLE IF EXISTS TuningStrings;
    DROP TABLE IF EXISTS Tunings;
    DROP TABLE IF EXISTS DiatonicChords;
    DROP TABLE IF EXISTS Keys;
    DROP TABLE IF EXISTS ChordIntervals;
    DROP TABLE IF EXISTS Chords;
    DROP TABLE IF EXISTS ScaleIntervals;
    DROP TABLE IF EXISTS Scales;
    DROP TABLE IF EXISTS Notes;

    CREATE TABLE Notes (
        note_id        INTEGER PRIMARY KEY,           -- 0-11 (C=0, C#=1, ... B=11)
        name           TEXT    NOT NULL UNIQUE,        -- 'C', 'C#', 'D', ...
        enharmonic     TEXT,                           -- 'Db', 'Eb', etc.
        midi_base      INTEGER NOT NULL                -- lowest reference octave (C0 = 12)
    );

    -- ============================================================
    -- Scales: Named scale formulas
    -- ============================================================
    CREATE TABLE Scales (
        scale_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT    NOT NULL UNIQUE,        -- 'Major', 'Natural Minor', etc.
        mode_of        INTEGER REFERENCES Scales(scale_id),
        degree_count   INTEGER NOT NULL                -- 7 for heptatonic, 5 for pentatonic
    );

    -- ============================================================
    -- ScaleIntervals: Semitone offsets and interval labels per degree
    -- ============================================================
    CREATE TABLE ScaleIntervals (
        scale_id        INTEGER NOT NULL REFERENCES Scales(scale_id) ON DELETE CASCADE,
        degree          INTEGER NOT NULL,               -- 1-indexed (1 = tonic)
        semitone_offset INTEGER NOT NULL,               -- semitones from root (0 for degree 1)
        degree_label    TEXT    NOT NULL,               -- 'P1', 'M2', 'M3', 'm3', 'P4', etc.
        PRIMARY KEY (scale_id, degree)
    );

    -- ============================================================
    -- Chords: Named chord qualities
    -- ============================================================
    CREATE TABLE Chords (
        chord_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT    NOT NULL UNIQUE,        -- 'Major', 'Minor', 'Diminished', etc.
        symbol         TEXT    NOT NULL,               -- '', 'm', '°', '+', '7', 'maj7', 'm7'
        note_count     INTEGER NOT NULL                -- 3 for triad, 4 for 7th
    );

    -- ============================================================
    -- ChordIntervals: Internal interval structure of each chord
    -- ============================================================
    CREATE TABLE ChordIntervals (
        chord_id        INTEGER NOT NULL REFERENCES Chords(chord_id) ON DELETE CASCADE,
        position        INTEGER NOT NULL,               -- 1=root, 2=third, 3=fifth, 4=seventh
        semitone_offset INTEGER NOT NULL,               -- semitones from root
        interval_name   TEXT    NOT NULL,               -- 'P1', 'M3', 'm3', 'P5', 'dim5', 'aug5'
        PRIMARY KEY (chord_id, position)
    );

    -- ============================================================
    -- Keys: Root note + Scale combinations
    -- ============================================================
    CREATE TABLE Keys (
        key_id         INTEGER PRIMARY KEY AUTOINCREMENT,
        root_note_id   INTEGER NOT NULL REFERENCES Notes(note_id),
        scale_id       INTEGER NOT NULL REFERENCES Scales(scale_id),
        name           TEXT    NOT NULL UNIQUE,        -- e.g. 'C Major', 'A Minor'
        UNIQUE (root_note_id, scale_id)
    );

    -- ============================================================
    -- DiatonicChords: Diatonic harmony mapped to Roman Numerals
    -- ============================================================
    CREATE TABLE DiatonicChords (
        key_id          INTEGER NOT NULL REFERENCES Keys(key_id) ON DELETE CASCADE,
        degree          INTEGER NOT NULL,               -- 1 to 7
        chord_id        INTEGER NOT NULL REFERENCES Chords(chord_id),
        root_note_id    INTEGER NOT NULL REFERENCES Notes(note_id),
        roman_numeral   TEXT    NOT NULL,               -- 'I', 'ii', 'iii', 'IV', 'V', 'vi', 'vii°'
        PRIMARY KEY (key_id, degree)
    );

    -- ============================================================
    -- Tunings: Presets for instrument tunings
    -- ============================================================
    CREATE TABLE Tunings (
        tuning_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT    NOT NULL UNIQUE,        -- 'Standard', 'Drop D', etc.
        string_count   INTEGER NOT NULL DEFAULT 6
    );

    -- ============================================================
    -- TuningStrings: Per-string open-string pitch definitions
    -- String 1 = high E (highest pitch), String 6 = low E (lowest pitch)
    -- ============================================================
    CREATE TABLE TuningStrings (
        tuning_id      INTEGER NOT NULL REFERENCES Tunings(tuning_id) ON DELETE CASCADE,
        string_number  INTEGER NOT NULL,               -- 1 (high) to 6 (low)
        open_note_midi INTEGER NOT NULL,               -- MIDI note number
        open_note_name TEXT    NOT NULL,               -- 'E4', 'B3', 'G3', 'D3', 'A2', 'E2'
        PRIMARY KEY (tuning_id, string_number)
    );

    -- Indexes
    CREATE INDEX idx_scale_intervals_scale ON ScaleIntervals(scale_id);
    CREATE INDEX idx_chord_intervals_chord ON ChordIntervals(chord_id);
    CREATE INDEX idx_diatonic_key          ON DiatonicChords(key_id);
    CREATE INDEX idx_tuning_strings_tuning ON TuningStrings(tuning_id);
    CREATE INDEX idx_keys_root_scale       ON Keys(root_note_id, scale_id);
    """)


def seed_database(cursor: sqlite3.Cursor) -> None:
    """Populates the database with foundational music theory records."""

    # 1. Notes (12 chromatic pitch classes, C=0 to B=11)
    notes_data = [
        (0,  "C",  "B#", 12),
        (1,  "C#", "Db", 13),
        (2,  "D",  None, 14),
        (3,  "D#", "Eb", 15),
        (4,  "E",  "Fb", 16),
        (5,  "F",  "E#", 17),
        (6,  "F#", "Gb", 18),
        (7,  "G",  None, 19),
        (8,  "G#", "Ab", 20),
        (9,  "A",  None, 21),
        (10, "A#", "Bb", 22),
        (11, "B",  "Cb", 23),
    ]
    cursor.executemany(
        "INSERT INTO Notes (note_id, name, enharmonic, midi_base) VALUES (?, ?, ?, ?)",
        notes_data
    )

    # 2. Scales
    scales_data = [
        (1, "Major", None, 7),
        (2, "Natural Minor", None, 7),
        (3, "Harmonic Minor", None, 7),
        (4, "Melodic Minor", None, 7),
        (5, "Major Pentatonic", None, 5),
        (6, "Minor Pentatonic", None, 5),
        (7, "Blues", None, 6),
    ]
    cursor.executemany(
        "INSERT INTO Scales (scale_id, name, mode_of, degree_count) VALUES (?, ?, ?, ?)",
        scales_data
    )

    # 3. ScaleIntervals
    # Major: 1(P1,0), 2(M2,2), 3(M3,4), 4(P4,5), 5(P5,7), 6(M6,9), 7(M7,11)
    major_intervals = [
        (1, 1, 0,  "P1"),
        (1, 2, 2,  "M2"),
        (1, 3, 4,  "M3"),
        (1, 4, 5,  "P4"),
        (1, 5, 7,  "P5"),
        (1, 6, 9,  "M6"),
        (1, 7, 11, "M7"),
    ]

    # Natural Minor: 1(P1,0), 2(M2,2), 3(m3,3), 4(P4,5), 5(P5,7), 6(m6,8), 7(m7,10)
    minor_intervals = [
        (2, 1, 0,  "P1"),
        (2, 2, 2,  "M2"),
        (2, 3, 3,  "m3"),
        (2, 4, 5,  "P4"),
        (2, 5, 7,  "P5"),
        (2, 6, 8,  "m6"),
        (2, 7, 10, "m7"),
    ]

    # Harmonic Minor: 1(P1,0), 2(M2,2), 3(m3,3), 4(P4,5), 5(P5,7), 6(m6,8), 7(M7,11)
    harmonic_minor_intervals = [
        (3, 1, 0,  "P1"),
        (3, 2, 2,  "M2"),
        (3, 3, 3,  "m3"),
        (3, 4, 5,  "P4"),
        (3, 5, 7,  "P5"),
        (3, 6, 8,  "m6"),
        (3, 7, 11, "M7"),
    ]

    # Minor Pentatonic: 1(0), 2(3), 3(5), 4(7), 5(10)
    minor_pentatonic = [
        (6, 1, 0,  "P1"),
        (6, 2, 3,  "m3"),
        (6, 3, 5,  "P4"),
        (6, 4, 7,  "P5"),
        (6, 5, 10, "m7"),
    ]

    cursor.executemany(
        "INSERT INTO ScaleIntervals (scale_id, degree, semitone_offset, degree_label) VALUES (?, ?, ?, ?)",
        major_intervals + minor_intervals + harmonic_minor_intervals + minor_pentatonic
    )

    # 4. Chords
    chords_data = [
        (1, "Major",       "",    3),
        (2, "Minor",       "m",   3),
        (3, "Diminished",  "°",   3),
        (4, "Augmented",   "+",   3),
        (5, "Dominant 7th","7",   4),
        (6, "Major 7th",   "maj7",4),
        (7, "Minor 7th",   "m7",  4),
        (8, "Half-Diminished 7th", "m7b5", 4),
    ]
    cursor.executemany(
        "INSERT INTO Chords (chord_id, name, symbol, note_count) VALUES (?, ?, ?, ?)",
        chords_data
    )

    # 5. ChordIntervals
    chord_intervals_data = [
        # Major: 1, 3, 5 -> 0, 4, 7
        (1, 1, 0, "P1"), (1, 2, 4, "M3"), (1, 3, 7, "P5"),
        # Minor: 1, b3, 5 -> 0, 3, 7
        (2, 1, 0, "P1"), (2, 2, 3, "m3"), (2, 3, 7, "P5"),
        # Diminished: 1, b3, b5 -> 0, 3, 6
        (3, 1, 0, "P1"), (3, 2, 3, "m3"), (3, 3, 6, "dim5"),
        # Augmented: 1, 3, #5 -> 0, 4, 8
        (4, 1, 0, "P1"), (4, 2, 4, "M3"), (4, 3, 8, "aug5"),
        # Dom 7th: 0, 4, 7, 10
        (5, 1, 0, "P1"), (5, 2, 4, "M3"), (5, 3, 7, "P5"), (5, 4, 10, "m7"),
        # Maj 7th: 0, 4, 7, 11
        (6, 1, 0, "P1"), (6, 2, 4, "M3"), (6, 3, 7, "P5"), (6, 4, 11, "M7"),
        # Min 7th: 0, 3, 7, 10
        (7, 1, 0, "P1"), (7, 2, 3, "m3"), (7, 3, 7, "P5"), (7, 4, 10, "m7"),
        # Half-Diminished: 0, 3, 6, 10
        (8, 1, 0, "P1"), (8, 2, 3, "m3"), (8, 3, 6, "dim5"), (8, 4, 10, "m7"),
    ]
    cursor.executemany(
        "INSERT INTO ChordIntervals (chord_id, position, semitone_offset, interval_name) VALUES (?, ?, ?, ?)",
        chord_intervals_data
    )

    # 6. Keys (12 Major Keys and 12 Natural Minor Keys)
    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    key_id = 1
    key_rows = []

    # Map of root note to key_id for fast lookup
    major_key_map = {}
    minor_key_map = {}

    for root_id, note_name in enumerate(note_names):
        # Major key (scale_id = 1)
        major_key_map[root_id] = key_id
        key_rows.append((key_id, root_id, 1, f"{note_name} Major"))
        key_id += 1

    for root_id, note_name in enumerate(note_names):
        # Natural Minor key (scale_id = 2)
        minor_key_map[root_id] = key_id
        key_rows.append((key_id, root_id, 2, f"{note_name} Minor"))
        key_id += 1

    cursor.executemany(
        "INSERT INTO Keys (key_id, root_note_id, scale_id, name) VALUES (?, ?, ?, ?)",
        key_rows
    )

    # 7. DiatonicChords & Roman Numerals
    # Major scale diatonic pattern (degrees 1..7):
    # I (Major), ii (Minor), iii (Minor), IV (Major), V (Major), vi (Minor), vii° (Diminished)
    # Chord IDs: Major=1, Minor=2, Diminished=3
    major_formula = [
        (1, 0,  1, "I"),
        (2, 2,  2, "ii"),
        (3, 4,  2, "iii"),
        (4, 5,  1, "IV"),
        (5, 7,  1, "V"),
        (6, 9,  2, "vi"),
        (7, 11, 3, "vii°"),
    ]

    # Natural Minor scale diatonic pattern (degrees 1..7):
    # i (Minor), ii° (Diminished), III (Major), iv (Minor), v (Minor), VI (Major), VII (Major)
    minor_formula = [
        (1, 0,  2, "i"),
        (2, 2,  3, "ii°"),
        (3, 3,  1, "III"),
        (4, 5,  2, "iv"),
        (5, 7,  2, "v"),
        (6, 8,  1, "VI"),
        (7, 10, 1, "VII"),
    ]

    diatonic_rows = []

    # Seed all 12 Major keys
    for root_id in range(12):
        k_id = major_key_map[root_id]
        for degree, semitone_offset, chord_id_val, roman in major_formula:
            chord_root_id = (root_id + semitone_offset) % 12
            diatonic_rows.append((k_id, degree, chord_id_val, chord_root_id, roman))

    # Seed all 12 Minor keys
    for root_id in range(12):
        k_id = minor_key_map[root_id]
        for degree, semitone_offset, chord_id_val, roman in minor_formula:
            chord_root_id = (root_id + semitone_offset) % 12
            diatonic_rows.append((k_id, degree, chord_id_val, chord_root_id, roman))

    cursor.executemany(
        """INSERT INTO DiatonicChords 
           (key_id, degree, chord_id, root_note_id, roman_numeral) 
           VALUES (?, ?, ?, ?, ?)""",
        diatonic_rows
    )

    # 8. Tunings & TuningStrings
    # Standard: E4(64), B3(59), G3(55), D3(50), A2(45), E2(40)
    # Drop D:   E4(64), B3(59), G3(55), D3(50), A2(45), D2(38)
    # DADGAD:   D4(62), A3(57), G3(55), D3(50), A2(45), D2(38)
    # Half-Step Down: Eb4(63), Bb3(58), Gb3(54), Db3(49), Ab2(44), Eb2(39)
    # Open D:   D4(62), A3(57), F#3(54), D3(50), A2(45), D2(38)
    # Open G:   D4(62), B3(59), G3(55), D3(50), G2(43), D2(38)
    tunings_data = [
        (1, "Standard", 6),
        (2, "Drop D", 6),
        (3, "DADGAD", 6),
        (4, "Half-Step Down", 6),
        (5, "Open D", 6),
        (6, "Open G", 6),
    ]
    cursor.executemany(
        "INSERT INTO Tunings (tuning_id, name, string_count) VALUES (?, ?, ?)",
        tunings_data
    )

    tuning_strings_data = [
        # Standard
        (1, 1, 64, "E4"),
        (1, 2, 59, "B3"),
        (1, 3, 55, "G3"),
        (1, 4, 50, "D3"),
        (1, 5, 45, "A2"),
        (1, 6, 40, "E2"),
        # Drop D
        (2, 1, 64, "E4"),
        (2, 2, 59, "B3"),
        (2, 3, 55, "G3"),
        (2, 4, 50, "D3"),
        (2, 5, 45, "A2"),
        (2, 6, 38, "D2"),
        # DADGAD
        (3, 1, 62, "D4"),
        (3, 2, 57, "A3"),
        (3, 3, 55, "G3"),
        (3, 4, 50, "D3"),
        (3, 5, 45, "A2"),
        (3, 6, 38, "D2"),
        # Half-Step Down
        (4, 1, 63, "Eb4"),
        (4, 2, 58, "Bb3"),
        (4, 3, 54, "Gb3"),
        (4, 4, 49, "Db3"),
        (4, 5, 44, "Ab2"),
        (4, 6, 39, "Eb2"),
        # Open D
        (5, 1, 62, "D4"),
        (5, 2, 57, "A3"),
        (5, 3, 54, "F#3"),
        (5, 4, 50, "D3"),
        (5, 5, 45, "A2"),
        (5, 6, 38, "D2"),
        # Open G
        (6, 1, 62, "D4"),
        (6, 2, 59, "B3"),
        (6, 3, 55, "G3"),
        (6, 4, 50, "D3"),
        (6, 5, 43, "G2"),
        (6, 6, 38, "D2"),
    ]
    cursor.executemany(
        """INSERT INTO TuningStrings 
           (tuning_id, string_number, open_note_midi, open_note_name) 
           VALUES (?, ?, ?, ?)""",
        tuning_strings_data
    )


def verify_database(conn: sqlite3.Connection) -> None:
    """Performs integrity checks and prints summary diagnostics."""
    cursor = conn.cursor()
    print("=" * 60)
    print("Database Verification & Summary:")
    print("=" * 60)

    tables = [
        "Notes", "Scales", "ScaleIntervals", "Chords",
        "ChordIntervals", "Keys", "DiatonicChords", "Tunings", "TuningStrings"
    ]

    for table in tables:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  [Table] {table:16} : {count:4} rows")

    # Sample check 1: C Major Diatonic Chords
    print("-" * 60)
    print("Sample Query — Diatonic Chords for C Major (Key ID 1):")
    query_c_major = """
        SELECT dc.degree, dc.roman_numeral, n.name AS root_note, c.name AS quality, c.symbol
        FROM DiatonicChords dc
        JOIN Notes n ON dc.root_note_id = n.note_id
        JOIN Chords c ON dc.chord_id = c.chord_id
        WHERE dc.key_id = 1
        ORDER BY dc.degree;
    """
    for row in cursor.execute(query_c_major).fetchall():
        print(f"  Degree {row[0]}: {row[1]:5} -> {row[2]}{row[4]} ({row[3]})")

    # Sample check 2: A Minor Diatonic Chords
    print("-" * 60)
    print("Sample Query — Diatonic Chords for A Minor (Key ID 22):")
    query_a_minor = """
        SELECT dc.degree, dc.roman_numeral, n.name AS root_note, c.name AS quality, c.symbol
        FROM DiatonicChords dc
        JOIN Keys k ON dc.key_id = k.key_id
        JOIN Notes n ON dc.root_note_id = n.note_id
        JOIN Chords c ON dc.chord_id = c.chord_id
        WHERE k.name = 'A Minor'
        ORDER BY dc.degree;
    """
    for row in cursor.execute(query_a_minor).fetchall():
        print(f"  Degree {row[0]}: {row[1]:5} -> {row[2]}{row[4]} ({row[3]})")

    # Sample check 3: Standard Tuning String list
    print("-" * 60)
    print("Sample Query — Standard Tuning Strings:")
    query_tuning = """
        SELECT string_number, open_note_name, open_note_midi
        FROM TuningStrings
        WHERE tuning_id = 1
        ORDER BY string_number ASC;
    """
    for row in cursor.execute(query_tuning).fetchall():
        print(f"  String {row[0]}: {row[1]:4} (MIDI {row[2]})")
    print("=" * 60)


def init_db(db_path: Path | None = None) -> Path:
    """Initializes and seeds the database at the target path."""
    if db_path is None:
        db_path = Path(__file__).resolve().parent / DB_FILENAME

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()  # Clean rebuild

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        create_schema(cursor)
        seed_database(cursor)
        conn.commit()
        verify_database(conn)
    finally:
        conn.close()

    print(f"\nSuccessfully initialized database at: {db_path.resolve()}\n")
    return db_path


if __name__ == "__main__":
    target = None
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    init_db(target)
