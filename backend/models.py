"""
models.py — Pydantic Schemas for Request & Response Payloads
"""

from typing import Any
from pydantic import BaseModel, Field
from .config import STANDARD_TUNING


# =============================================================================
# Tuning Models
# =============================================================================

class TuningRequest(BaseModel):
    open_midi: list[int] = Field(
        default=STANDARD_TUNING,
        min_length=1,
        max_length=8,
        description="Array of open-string MIDI pitches ordered from highest to lowest string."
    )


class TuningShiftItem(BaseModel):
    string_number: int
    standard_midi: int
    standard_name: str
    custom_midi: int
    custom_name: str
    semitone_delta: int
    fret_shift: int


class TuningResponse(BaseModel):
    custom_tuning: list[int]
    reference_tuning: list[int]
    shifts: list[TuningShiftItem]


# =============================================================================
# Scale Models
# =============================================================================

class ScaleRequest(BaseModel):
    root: str = Field(default="C", description="Root note name (e.g. 'C', 'G#', 'Eb', 'A')")
    scale_type: str = Field(default="major", description="Scale quality: 'major' or 'minor'")
    tuning: list[int] | None = Field(default=None, description="Optional custom instrument tuning")
    include_fretboard: bool = Field(default=True, description="Whether to include full 2D fretboard grid")


class ScaleNote(BaseModel):
    degree: int
    label: str
    note_name: str
    pitch_class: int
    semitone_offset: int


class ScaleResponse(BaseModel):
    root: str
    scale_type: str
    formula: list[int]
    active_notes: list[ScaleNote]
    fretboard_map: list[list[dict[str, Any]]] | None = None


# =============================================================================
# Chord Models
# =============================================================================

class ChordRequest(BaseModel):
    key: str = Field(default="C Major", description="Key name (e.g. 'C Major', 'A Minor', 'G Major')")
    tuning: list[int] | None = Field(default=None, description="Instrument tuning MIDI pitches")
    max_voicings: int = Field(default=4, ge=1, le=16, description="Max voicings per chord to calculate")


class VoicingPlacement(BaseModel):
    string_number: int
    fret: int
    midi_note: int
    finger: int
    note_name: str


class VoicingDto(BaseModel):
    placements: list[VoicingPlacement]
    difficulty_score: float
    min_fret: int
    max_fret: int
    barre_fret: int
    root_string: int | None
    tab_repr: str


class DiatonicChordDto(BaseModel):
    degree: int
    roman_numeral: str
    chord_name: str
    chord_symbol: str
    root_note: str
    root_pitch_class: int
    chord_offsets: list[int]
    notes: list[str]
    voicings: list[VoicingDto]


class ChordsResponse(BaseModel):
    key_name: str
    root: str
    scale_type: str
    tuning: list[int]
    diatonic_chords: list[DiatonicChordDto]
