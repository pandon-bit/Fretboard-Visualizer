"""
routers/chords.py — API endpoints for Diatonic Roman Numeral Chords and C++ Voicing Solver.
"""

from fastapi import APIRouter, HTTPException, Query
from ..config import STANDARD_TUNING
from ..models import (
    ChordRequest,
    ChordsResponse,
    DiatonicChordDto,
    VoicingDto,
    VoicingPlacement,
)
from ..database import get_key, get_diatonic_chords_for_key
from ..engine_bridge import find_chord_voicings

router = APIRouter(prefix="/api/chords", tags=["Chords"])


def _build_chords_response(
    key_str: str,
    tuning: list[int] | None = None,
    max_voicings: int = 4
) -> ChordsResponse:
    # 1. Resolve Key from SQL database
    key_info = get_key(key_str)
    if not key_info:
        raise HTTPException(
            status_code=404,
            detail=f"Key '{key_str}' not found in database. Example keys: 'C Major', 'A Minor', 'G Major', 'E Minor'."
        )

    key_id = key_info["key_id"]
    active_tuning = tuning if tuning else STANDARD_TUNING

    # 2. Query diatonic chords from SQL database
    diatonic_records = get_diatonic_chords_for_key(key_id)
    if not diatonic_records:
        raise HTTPException(
            status_code=500,
            detail=f"No diatonic chords found in database for key '{key_info['name']}'."
        )

    # 3. Calculate optimal voicings for each diatonic chord using C++ engine
    diatonic_dtos: list[DiatonicChordDto] = []

    for item in diatonic_records:
        chord_root_pc = item["root_note_id"]
        chord_offsets = item["chord_offsets"]

        # Call C++ engine voicing search algorithm
        raw_voicings = find_chord_voicings(
            open_midis=active_tuning,
            chord_offsets=chord_offsets,
            root_pitch_class=chord_root_pc,
            max_span=4,
            max_results=max_voicings
        )

        voicing_dtos: list[VoicingDto] = []
        for v in raw_voicings:
            placements = [VoicingPlacement(**p) for p in v["placements"]]
            voicing_dtos.append(VoicingDto(
                placements=placements,
                difficulty_score=v["difficulty_score"],
                min_fret=v["min_fret"],
                max_fret=v["max_fret"],
                barre_fret=v["barre_fret"],
                root_string=v["root_string"],
                tab_repr=v["tab_repr"]
            ))

        diatonic_dtos.append(DiatonicChordDto(
            degree=item["degree"],
            roman_numeral=item["roman_numeral"],
            chord_name=item["chord_name"],
            chord_symbol=item["chord_symbol"],
            root_note=item["root_note"],
            root_pitch_class=chord_root_pc,
            chord_offsets=chord_offsets,
            notes=item["chord_notes"],
            voicings=voicing_dtos
        ))

    return ChordsResponse(
        key_name=key_info["name"],
        root=key_info["root_note"],
        scale_type=key_info["scale_name"],
        tuning=active_tuning,
        diatonic_chords=diatonic_dtos
    )


@router.get("", response_model=ChordsResponse)
def get_diatonic_chords(
    key: str = Query("C Major", description="Key name (e.g. 'C Major', 'A Minor', 'G Major')"),
    max_voicings: int = Query(4, ge=1, le=16, description="Max voicings per chord to calculate")
):
    """
    Accepts a Key name, queries SQL relational schema for Roman numeral diatonic chords,
    and calculates optimal guitar voicings using the C++ algorithm engine.
    """
    return _build_chords_response(key, max_voicings=max_voicings)


@router.post("", response_model=ChordsResponse)
def post_diatonic_chords(payload: ChordRequest):
    """
    Accepts a Key and custom tuning, returning diatonic chords with custom-tuning voicings.
    """
    return _build_chords_response(
        key_str=payload.key,
        tuning=payload.tuning,
        max_voicings=payload.max_voicings
    )
