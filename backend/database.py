"""
database.py — Database Access Layer for Music Theory Models
Connects to SQLite 'music_models.db' and queries relational schemas.
"""

import sqlite3
from typing import Any
from .config import DATABASE_PATH, NOTE_NAMES, ENHARMONIC_MAP


def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with Row factory enabled."""
    if not DATABASE_PATH.exists():
        # Fallback: attempt to run init_db if the db file was not yet created
        from ..database.init_db import init_db
        init_db(DATABASE_PATH)

    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def normalize_note_name(name: str) -> str:
    """Normalizes note names, converting enharmonics like Db -> C#."""
    clean = name.strip()
    if not clean:
        return "C"
    # Format e.g. "c#" -> "C#"
    upper = clean[0].upper() + clean[1:].lower()
    canonical = ENHARMONIC_MAP.get(upper.upper(), upper)
    return canonical


def get_note_by_name(name: str) -> dict[str, Any] | None:
    """Looks up a note by standard name or enharmonic."""
    canonical = normalize_note_name(name)
    with get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT note_id, name, enharmonic, midi_base FROM Notes WHERE name = ? OR enharmonic = ?",
            (canonical, canonical)
        ).fetchone()
        if row:
            return dict(row)
        # Try raw match
        row = cursor.execute(
            "SELECT note_id, name, enharmonic, midi_base FROM Notes WHERE UPPER(name) = ? OR UPPER(enharmonic) = ?",
            (name.upper(), name.upper())
        ).fetchone()
        return dict(row) if row else None


def get_all_notes() -> list[dict[str, Any]]:
    """Retrieves all 12 chromatic notes."""
    with get_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT note_id, name, enharmonic, midi_base FROM Notes ORDER BY note_id ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_scale_by_name(scale_type: str) -> dict[str, Any] | None:
    """
    Fetches scale definition and its degree interval structure.
    Accepts 'major', 'minor', 'natural minor', 'harmonic minor', etc.
    """
    clean_type = scale_type.strip().lower()
    if clean_type in ("minor", "natural minor", "aeolian"):
        lookup = "Natural Minor"
    elif clean_type in ("major", "ionian"):
        lookup = "Major"
    elif clean_type == "harmonic minor":
        lookup = "Harmonic Minor"
    elif clean_type == "melodic minor":
        lookup = "Melodic Minor"
    elif clean_type in ("pentatonic", "minor pentatonic"):
        lookup = "Minor Pentatonic"
    elif clean_type == "major pentatonic":
        lookup = "Major Pentatonic"
    elif clean_type == "blues":
        lookup = "Blues"
    else:
        lookup = scale_type.title()

    with get_connection() as conn:
        cursor = conn.cursor()
        scale_row = cursor.execute(
            "SELECT scale_id, name, degree_count FROM Scales WHERE LOWER(name) = LOWER(?)",
            (lookup,)
        ).fetchone()

        if not scale_row:
            return None

        scale_id = scale_row["scale_id"]
        interval_rows = cursor.execute(
            """SELECT degree, semitone_offset, degree_label 
               FROM ScaleIntervals 
               WHERE scale_id = ? 
               ORDER BY degree ASC""",
            (scale_id,)
        ).fetchall()

        return {
            "scale_id": scale_id,
            "name": scale_row["name"],
            "degree_count": scale_row["degree_count"],
            "intervals": [dict(r) for r in interval_rows]
        }


def get_key(key_input: str) -> dict[str, Any] | None:
    """
    Finds a Key by full name (e.g. 'C Major', 'A Minor') or creates key info.
    """
    clean = key_input.strip()
    with get_connection() as conn:
        cursor = conn.cursor()
        # Direct match in Keys table
        row = cursor.execute(
            """SELECT k.key_id, k.name, k.root_note_id, k.scale_id, 
                      n.name AS root_note, s.name AS scale_name
               FROM Keys k
               JOIN Notes n ON k.root_note_id = n.note_id
               JOIN Scales s ON k.scale_id = s.scale_id
               WHERE LOWER(k.name) = LOWER(?)""",
            (clean,)
        ).fetchone()

        if row:
            return dict(row)

        # Parse "Root + Scale" (e.g. "C Major" or "F# Minor")
        parts = clean.split()
        if len(parts) >= 2:
            root_part = parts[0]
            scale_part = " ".join(parts[1:])
            note = get_note_by_name(root_part)
            scale = get_scale_by_name(scale_part)
            if note and scale:
                row = cursor.execute(
                    """SELECT k.key_id, k.name, k.root_note_id, k.scale_id,
                              n.name AS root_note, s.name AS scale_name
                       FROM Keys k
                       JOIN Notes n ON k.root_note_id = n.note_id
                       JOIN Scales s ON k.scale_id = s.scale_id
                       WHERE k.root_note_id = ? AND k.scale_id = ?""",
                    (note["note_id"], scale["scale_id"])
                ).fetchone()
                if row:
                    return dict(row)

        return None


def get_diatonic_chords_for_key(key_id: int) -> list[dict[str, Any]]:
    """
    Retrieves the 7 diatonic chords for a key along with their internal chord intervals.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                dc.degree,
                dc.roman_numeral,
                dc.chord_id,
                c.name AS chord_name,
                c.symbol AS chord_symbol,
                dc.root_note_id,
                n.name AS root_note
            FROM DiatonicChords dc
            JOIN Chords c ON dc.chord_id = c.chord_id
            JOIN Notes n ON dc.root_note_id = n.note_id
            WHERE dc.key_id = ?
            ORDER BY dc.degree ASC
        """
        rows = cursor.execute(query, (key_id,)).fetchall()

        results = []
        for r in rows:
            chord_id = r["chord_id"]
            root_pc = r["root_note_id"]

            # Fetch chord intervals (e.g. {P1:0, M3:4, P5:7})
            int_rows = cursor.execute(
                """SELECT position, semitone_offset, interval_name 
                   FROM ChordIntervals 
                   WHERE chord_id = ? 
                   ORDER BY position ASC""",
                (chord_id,)
            ).fetchall()

            intervals = [dict(i) for i in int_rows]
            offsets = [i["semitone_offset"] for i in intervals]
            chord_notes = [NOTE_NAMES[(root_pc + off) % 12] for off in offsets]

            item = {
                "degree": r["degree"],
                "roman_numeral": r["roman_numeral"],
                "chord_id": chord_id,
                "chord_name": r["chord_name"],
                "chord_symbol": r["chord_symbol"],
                "root_note_id": root_pc,
                "root_note": r["root_note"],
                "chord_offsets": offsets,
                "intervals": intervals,
                "chord_notes": chord_notes
            }
            results.append(item)

        return results


def get_all_tunings() -> list[dict[str, Any]]:
    """Returns all tuning presets with their string specifications."""
    with get_connection() as conn:
        cursor = conn.cursor()
        tuning_rows = cursor.execute(
            "SELECT tuning_id, name, string_count FROM Tunings ORDER BY tuning_id ASC"
        ).fetchall()

        tunings = []
        for t in tuning_rows:
            t_id = t["tuning_id"]
            strings = cursor.execute(
                """SELECT string_number, open_note_midi, open_note_name 
                   FROM TuningStrings 
                   WHERE tuning_id = ? 
                   ORDER BY string_number ASC""",
                (t_id,)
            ).fetchall()

            tunings.append({
                "tuning_id": t_id,
                "name": t["name"],
                "string_count": t["string_count"],
                "strings": [dict(s) for s in strings],
                "open_midi": [s["open_note_midi"] for s in strings]
            })

        return tunings
