"""
routers/tuning.py — API endpoints for dynamic custom tunings and horizontal shift calculations.
"""

from fastapi import APIRouter, HTTPException
from ..config import STANDARD_TUNING
from ..models import TuningRequest, TuningResponse, TuningShiftItem
from ..engine_bridge import calculate_tuning_shifts
from ..database import get_all_tunings

router = APIRouter(prefix="/api/tuning", tags=["Tuning"])


@router.post("", response_model=TuningResponse)
def post_tuning_shifts(payload: TuningRequest):
    """
    Accepts custom open-string MIDI pitches and calculates per-string horizontal
    fret shifts relative to standard tuning (E2-A2-D3-G3-B3-E4) using the C++ algorithm engine.
    """
    try:
        shifts = calculate_tuning_shifts(payload.open_midi)
        return TuningResponse(
            custom_tuning=payload.open_midi,
            reference_tuning=STANDARD_TUNING[:len(payload.open_midi)],
            shifts=[TuningShiftItem(**s) for s in shifts]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to calculate tuning shifts: {str(e)}")


@router.get("", response_model=TuningResponse)
def get_standard_tuning_shifts():
    """
    Returns shift baseline for Standard Guitar Tuning.
    """
    shifts = calculate_tuning_shifts(STANDARD_TUNING)
    return TuningResponse(
        custom_tuning=STANDARD_TUNING,
        reference_tuning=STANDARD_TUNING,
        shifts=[TuningShiftItem(**s) for s in shifts]
    )


@router.get("/presets")
def get_tuning_presets():
    """
    Returns named tuning presets stored in the SQL relational database.
    """
    return {"presets": get_all_tunings()}
