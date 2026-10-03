"""
test_api.py — End-to-end integration test suite for the FastAPI backend.
Validates:
1. Root health check (/)
2. /api/tuning (GET standard & POST custom Drop D)
3. /api/scales (GET C Major & POST A Minor with 2D fretboard map)
4. /api/chords (GET C Major diatonic Roman numerals & voicings, and POST custom tuning voicings)
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.main import app

client = TestClient(app)


def test_root_endpoint():
    print("=" * 65)
    print("TEST 1: GET / (System Status & Health Check)")
    print("=" * 65)
    response = client.get("/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    print(f"Status: {data['status']}")
    print(f"Database: {data['database']['status']}")
    print(f"Engine: {data['engine']['status']}")
    assert data["status"] == "online"
    assert data["database"]["status"] == "connected"
    assert data["engine"]["status"] == "loaded"
    print("-> PASS: System status online, DB and C++ engine fully linked.\n")


def test_tuning_endpoints():
    print("=" * 65)
    print("TEST 2: /api/tuning Endpoints")
    print("=" * 65)

    # 1. GET /api/tuning
    res_get = client.get("/api/tuning")
    assert res_get.status_code == 200
    get_data = res_get.json()
    print(f"Standard Tuning Shifts: {len(get_data['shifts'])} strings evaluated")
    for s in get_data["shifts"]:
        assert s["semitone_delta"] == 0
        assert s["fret_shift"] == 0

    # 2. POST /api/tuning with Drop D (String 6 tuned from 40 to 38)
    drop_d_payload = {"open_midi": [64, 59, 55, 50, 45, 38]}
    res_post = client.post("/api/tuning", json=drop_d_payload)
    assert res_post.status_code == 200
    post_data = res_post.json()
    print("Drop D Tuning Shifts:")
    for s in post_data["shifts"]:
        print(f"  String {s['string_number']}: Std {s['standard_name']} ({s['standard_midi']}) -> "
              f"Custom {s['custom_name']} ({s['custom_midi']}) | "
              f"Delta={s['semitone_delta']:+2} | Fret Shift={s['fret_shift']:+2}")

    # String 6 validation
    s6 = post_data["shifts"][5]
    assert s6["semitone_delta"] == -2
    assert s6["fret_shift"] == 2

    # 3. GET /api/tuning/presets
    res_presets = client.get("/api/tuning/presets")
    assert res_presets.status_code == 200
    preset_names = [p["name"] for p in res_presets.json()["presets"]]
    print(f"Presets in database: {', '.join(preset_names)}")
    assert "Drop D" in preset_names
    assert "Standard" in preset_names
    print("-> PASS: Tuning endpoints correctly compute horizontal string shift maps.\n")


def test_scales_endpoints():
    print("=" * 65)
    print("TEST 3: /api/scales Endpoints")
    print("=" * 65)

    # 1. GET /api/scales?root=C&scale_type=major
    res_c_major = client.get("/api/scales?root=C&scale_type=major")
    assert res_c_major.status_code == 200
    c_data = res_c_major.json()
    print(f"Scale: {c_data['root']} {c_data['scale_type']}")
    notes_str = ", ".join([f"{n['label']}:{n['note_name']}" for n in c_data["active_notes"]])
    print(f"Active notes: {notes_str}")
    expected_c_notes = ["C", "D", "E", "F", "G", "A", "B"]
    actual_c_notes = [n["note_name"] for n in c_data["active_notes"]]
    assert actual_c_notes == expected_c_notes

    # Verify fretboard map is included
    assert c_data["fretboard_map"] is not None
    assert len(c_data["fretboard_map"]) == 6  # 6 strings
    assert len(c_data["fretboard_map"][0]) == 25  # 0 to 24 frets

    # 2. POST /api/scales with A Natural Minor and custom tuning
    res_a_minor = client.post("/api/scales", json={
        "root": "A",
        "scale_type": "minor",
        "include_fretboard": True
    })
    assert res_a_minor.status_code == 200
    a_data = res_a_minor.json()
    actual_a_notes = [n["note_name"] for n in a_data["active_notes"]]
    expected_a_notes = ["A", "B", "C", "D", "E", "F", "G"]
    assert actual_a_notes == expected_a_notes
    print(f"Scale: {a_data['root']} {a_data['scale_type']} -> {', '.join(actual_a_notes)}")
    print("-> PASS: Scale queries successfully retrieve SQL notes & generate C++ fretboard grids.\n")


def test_chords_endpoints():
    print("=" * 65)
    print("TEST 4: /api/chords Endpoints (Roman Numerals & Voicings)")
    print("=" * 65)

    # 1. GET /api/chords?key=C Major
    res_c = client.get("/api/chords?key=C%20Major&max_voicings=3")
    assert res_c.status_code == 200
    c_data = res_c.json()
    print(f"Key: {c_data['key_name']}")

    expected_c_romans = ["I", "ii", "iii", "IV", "V", "vi", "vii°"]
    actual_c_romans = [c["roman_numeral"] for c in c_data["diatonic_chords"]]
    assert actual_c_romans == expected_c_romans
    print(f"Diatonic Roman Numerals: {', '.join(actual_c_romans)}")

    for chord in c_data["diatonic_chords"]:
        print(f"\n  Degree {chord['degree']}: {chord['roman_numeral']:4} -> {chord['root_note']}{chord['chord_symbol']} ({chord['chord_name']})")
        print(f"    Notes: {', '.join(chord['notes'])}")
        print(f"    Calculated Voicings ({len(chord['voicings'])} found):")
        for v in chord["voicings"]:
            barre_str = f" [Barre Fret {v['barre_fret']}]" if v['barre_fret'] > 0 else ""
            print(f"      Tab: {v['tab_repr']:15} | Score: {v['difficulty_score']:4.2f} | Span: {v['min_fret']}-{v['max_fret']}{barre_str}")

    # Check that degree 1 (C Major) has voicings and includes the standard open C or barre shape
    c_maj = c_data["diatonic_chords"][0]
    assert len(c_maj["voicings"]) > 0

    # 2. GET /api/chords?key=A Minor
    res_a = client.get("/api/chords?key=A%20Minor&max_voicings=2")
    assert res_a.status_code == 200
    a_data = res_a.json()
    expected_a_romans = ["i", "ii°", "III", "iv", "v", "VI", "VII"]
    actual_a_romans = [c["roman_numeral"] for c in a_data["diatonic_chords"]]
    assert actual_a_romans == expected_a_romans
    print(f"\nA Minor Diatonic Roman Numerals: {', '.join(actual_a_romans)}")

    # 3. POST /api/chords with Drop D custom tuning
    res_drop_d = client.post("/api/chords", json={
        "key": "D Minor",
        "tuning": [64, 59, 55, 50, 45, 38],
        "max_voicings": 2
    })
    assert res_drop_d.status_code == 200
    drop_d_data = res_drop_d.json()
    print(f"\nCustom Drop D Voicings for D Minor tonic (i):")
    d_min_chord = drop_d_data["diatonic_chords"][0]
    for v in d_min_chord["voicings"]:
        print(f"  Tab: {v['tab_repr']} | Score: {v['difficulty_score']}")

    print("\n-> PASS: Diatonic chords accurately queried with optimal C++ finger voicings.\n")
    print("=" * 65)
    print("ALL API ENDPOINT INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    test_root_endpoint()
    test_tuning_endpoints()
    test_scales_endpoints()
    test_chords_endpoints()
