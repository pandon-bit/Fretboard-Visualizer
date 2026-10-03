"""
routers/scales.py — API endpoints for querying scales and generating fretboard maps.
"""

from fastapi import APIRouter, HTTPException, Query
from ..config import STANDARD_TUNING, NOTE_NAMES
from ..models import ScaleRequest, ScaleResponse, ScaleNote
from ..database import get_note_by_name, get_scale_by_name
from ..engine_bridge import compute_fretboard_map

router = APIRouter(prefix="/api/scales", tags=["Scales"])


def _build_scale_response(
    root_str: str,
    scale_type_str: str,
    tuning: list[int] | None = None,
    include_fretboard: bool = True
) -> ScaleResponse:
    # 1. Resolve note from SQL database
    note_info = get_note_by_name(root_str)
    if not note_info:
        raise HTTPException(
            status_code=404,
            detail=f"Musical note '{root_str}' not found in database. Allowed roots: {', '.join(NOTE_NAMES)}"
        )
    root_pc = note_info["note_id"]
    canonical_root = note_info["name"]

    # 2. Resolve scale formula from SQL database
    scale_info = get_scale_by_name(scale_type_str)
    if not scale_info:
        raise HTTPException(
            status_code=404,
            detail=f"Scale type '{scale_type_str}' not found. Supported: 'major', 'minor', 'harmonic minor', etc."
        )

    # 3. Calculate active notes and degree metadata
    active_notes: list[ScaleNote] = []
    offsets: list[int] = []

    for item in scale_info["intervals"]:
        degree = item["degree"]
        offset = item["semitone_offset"]
        label = item["degree_label"]
        pc = (root_pc + offset) % 12
        note_name = NOTE_NAMES[pc]

        offsets.append(offset)
        active_notes.append(ScaleNote(
            degree=degree,
            label=label,
            note_name=note_name,
            pitch_class=pc,
            semitone_offset=offset
        ))

    # 4. Generate dynamic fretboard grid via C++ engine
    fretboard_grid = None
    if include_fretboard:
        active_tuning = tuning if tuning else STANDARD_TUNING
        fretboard_grid = compute_fretboard_map(
            open_midis=active_tuning,
            scale_offsets=offsets,
            root_pitch_class=root_pc
        )

    return ScaleResponse(
        root=canonical_root,
        scale_type=scale_info["name"],
        formula=offsets,
        active_notes=active_notes,
        fretboard_map=fretboard_grid
    )


@router.get("", response_model=ScaleResponse)
def get_scale(
    root: str = Query("C", description="Root note name (e.g. C, G#, Eb, A)"),
    scale_type: str = Query("major", description="Scale type: 'major' or 'minor'"),
    include_fretboard: bool = Query(True, description="Whether to include full fretboard grid")
):
    """
    Query scale active notes and fretboard map via GET parameters.
    """
    return _build_scale_response(root, scale_type, include_fretboard=include_fretboard)


@router.post("", response_model=ScaleResponse)
def post_scale(payload: ScaleRequest):
    """
    Query scale active notes and fretboard map via POST payload (supports custom instrument tunings).
    """
    return _build_scale_response(
        root_str=payload.root,
        scale_type_str=payload.scale_type,
        tuning=payload.tuning,
        include_fretboard=payload.include_fretboard
    )
