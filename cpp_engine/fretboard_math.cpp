#ifndef FRETENGINE_EXPORTS
#define FRETENGINE_EXPORTS
#endif
#include "fretboard_math.h"

#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <algorithm>
#include <cmath>

// =============================================================================
// Helper Tables & Music Theory Data
// =============================================================================

static const char* SIMPLE_INTERVAL_NAMES[13] = {
    "P1",  // 0 semitones (Unison)
    "m2",  // 1 semitone (Minor 2nd)
    "M2",  // 2 semitones (Major 2nd)
    "m3",  // 3 semitones (Minor 3rd)
    "M3",  // 4 semitones (Major 3rd)
    "P4",  // 5 semitones (Perfect 4th)
    "TT",  // 6 semitones (Tritone / Diminished 5th / Augmented 4th)
    "P5",  // 7 semitones (Perfect 5th)
    "m6",  // 8 semitones (Minor 6th)
    "M6",  // 9 semitones (Major 6th)
    "m7",  // 10 semitones (Minor 7th)
    "M7",  // 11 semitones (Major 7th)
    "P8"   // 12 semitones (Octave)
};

static const char* COMPOUND_INTERVAL_NAMES[13] = {
    "P8",  // 12 semitones
    "m9",  // 13 semitones
    "M9",  // 14 semitones
    "#9",  // 15 semitones / m10
    "M10", // 16 semitones
    "P11", // 17 semitones (11th)
    "#11", // 18 semitones
    "P12", // 19 semitones
    "m13", // 20 semitones (b13)
    "M13", // 21 semitones (13th)
    "m14", // 22 semitones
    "M14", // 23 semitones
    "2P8"  // 24 semitones (Double Octave)
};

extern "C" {

const char* fret_get_interval_name(int32_t semitones) {
    if (semitones < 0) {
        return "-";
    }
    if (semitones <= 12) {
        return SIMPLE_INTERVAL_NAMES[semitones];
    }
    if (semitones <= 24) {
        return COMPOUND_INTERVAL_NAMES[semitones - 12];
    }
    return "Compound";
}

int32_t fret_calculate_interval(
    int32_t       midi_low,
    int32_t       midi_high,
    IntervalInfo* out_info
) {
    if (!out_info) {
        return -1;
    }

    int32_t delta = midi_high - midi_low;
    out_info->semitones = delta;

    if (delta >= 0) {
        out_info->simple_semitones = delta % 12;
        out_info->octaves = delta / 12;
        const char* name = fret_get_interval_name(delta);
        std::strncpy(out_info->name, name, sizeof(out_info->name) - 1);
        out_info->name[sizeof(out_info->name) - 1] = '\0';
    } else {
        out_info->simple_semitones = (delta % 12 + 12) % 12;
        out_info->octaves = delta / 12;
        std::snprintf(out_info->name, sizeof(out_info->name), "-%s",
                      fret_get_interval_name(-delta));
    }

    return 0;
}

int32_t fret_calculate_multi_string_intervals(
    const TuningConfig*        tuning,
    const int32_t*             frets,
    int32_t                    string_count,
    MultiStringIntervalResult* out_result
) {
    if (!tuning || !frets || !out_result || string_count <= 0) {
        return -1;
    }

    int32_t count = (string_count > MAX_STRINGS) ? MAX_STRINGS : string_count;
    std::memset(out_result, 0, sizeof(MultiStringIntervalResult));

    int32_t sounding_count = 0;
    int32_t lowest_midi = 999;
    int32_t lowest_idx = -1;

    // First pass: identify sounding strings and pitch values
    for (int32_t s = 0; s < count; ++s) {
        out_result->string_indices[s] = s;
        out_result->fret_positions[s] = frets[s];

        if (frets[s] >= 0) {
            int32_t midi = tuning->open_midi[s] + frets[s];
            out_result->midi_notes[s] = midi;
            sounding_count++;

            if (midi < lowest_midi) {
                lowest_midi = midi;
                lowest_idx = s;
            }
        } else {
            out_result->midi_notes[s] = -1;
        }
    }

    out_result->sounding_count = sounding_count;
    out_result->lowest_string_idx = lowest_idx;
    out_result->lowest_midi_note = (sounding_count > 0) ? lowest_midi : -1;

    if (sounding_count == 0) {
        return 0;
    }

    // Second pass: compute intervals relative to the lowest sounding note (bass)
    // and between adjacent sounding strings (scanning from bass to treble)
    int32_t prev_sounding_midi = -1;

    // Scan backwards from lowest string index (low pitch) to highest string index (high pitch)
    // Note: in standard guitar numbering: index 5 is low E, index 0 is high E.
    // We compute consecutive intervals ordered by ascending pitch.
    for (int32_t s = count - 1; s >= 0; --s) {
        if (out_result->midi_notes[s] < 0) {
            std::strncpy(out_result->interval_from_lowest[s].name, "Muted",
                         sizeof(out_result->interval_from_lowest[s].name) - 1);
            std::strncpy(out_result->interval_from_adjacent[s].name, "Muted",
                         sizeof(out_result->interval_from_adjacent[s].name) - 1);
            continue;
        }

        int32_t current_midi = out_result->midi_notes[s];

        // Interval from lowest note (bass)
        fret_calculate_interval(lowest_midi, current_midi,
                                &out_result->interval_from_lowest[s]);

        // Interval from previous sounding string
        if (prev_sounding_midi >= 0) {
            fret_calculate_interval(prev_sounding_midi, current_midi,
                                    &out_result->interval_from_adjacent[s]);
        } else {
            fret_calculate_interval(current_midi, current_midi,
                                    &out_result->interval_from_adjacent[s]);
        }

        prev_sounding_midi = current_midi;
    }

    return 0;
}

int32_t fret_calculate_tuning_shifts(
    const int32_t*     custom_open_midi,
    int32_t            string_count,
    TuningShiftResult* out_result
) {
    if (!custom_open_midi || !out_result || string_count <= 0) {
        return -1;
    }

    return fret_calculate_tuning_shifts_custom_ref(
        STANDARD_TUNING_MIDI,
        custom_open_midi,
        string_count,
        out_result
    );
}

int32_t fret_calculate_tuning_shifts_custom_ref(
    const int32_t*     ref_open_midi,
    const int32_t*     custom_open_midi,
    int32_t            string_count,
    TuningShiftResult* out_result
) {
    if (!ref_open_midi || !custom_open_midi || !out_result || string_count <= 0) {
        return -1;
    }

    int32_t count = (string_count > MAX_STRINGS) ? MAX_STRINGS : string_count;
    out_result->string_count = count;

    for (int32_t i = 0; i < count; ++i) {
        int32_t standard_pitch = (i < STANDARD_STRINGS) ? ref_open_midi[i] : 0;
        int32_t custom_pitch   = custom_open_midi[i];
        int32_t delta          = custom_pitch - standard_pitch;

        out_result->shifts[i].string_number  = i + 1; // 1-indexed (1 = high string)
        out_result->shifts[i].standard_midi  = standard_pitch;
        out_result->shifts[i].custom_midi    = custom_pitch;
        out_result->shifts[i].semitone_delta = delta;
        // Shift formula: tuning UP shifts the visual representation LEFT,
        // tuning DOWN shifts the visual representation RIGHT.
        out_result->shifts[i].fret_shift     = -delta;
    }

    return 0;
}

int32_t fret_compute_map(
    const TuningConfig* tuning,
    const int32_t*      scale_offsets,
    int32_t             scale_len,
    int32_t             root_pitch_class,
    FretboardMap*       out_map
) {
    if (!tuning || !scale_offsets || !out_map || scale_len <= 0) {
        return -1;
    }

    int32_t num_strings = (tuning->string_count > MAX_STRINGS) ? MAX_STRINGS : tuning->string_count;
    int32_t num_frets   = (tuning->fret_count > MAX_FRETS) ? MAX_FRETS : tuning->fret_count;

    out_map->string_count = num_strings;
    out_map->fret_count   = num_frets;

    // Build O(1) membership mask and scale degree mapping
    bool    scale_mask[12] = {false};
    int32_t degree_map[12] = {0};

    int32_t root_pc = (root_pitch_class % 12 + 12) % 12;

    for (int32_t d = 0; d < scale_len; ++d) {
        int32_t pc = (root_pc + scale_offsets[d]) % 12;
        scale_mask[pc] = true;
        degree_map[pc] = d + 1; // 1-indexed degree (1 = root/tonic)
    }

    // Populate full grid
    for (int32_t s = 0; s < num_strings; ++s) {
        int32_t open_pitch = tuning->open_midi[s];

        for (int32_t f = 0; f <= num_frets; ++f) {
            int32_t midi = open_pitch + f;
            int32_t pc   = (midi % 12 + 12) % 12;

            FretCell* cell = &out_map->cells[s][f];
            cell->string_num   = s;
            cell->fret         = f;
            cell->midi_note    = midi;
            cell->pitch_class  = pc;
            cell->in_scale     = scale_mask[pc] ? 1 : 0;
            cell->scale_degree = degree_map[pc];
            cell->is_root      = (pc == root_pc) ? 1 : 0;
        }
    }

    return 0;
}

int32_t fret_note_at(
    const TuningConfig* tuning,
    int32_t             string_num,
    int32_t             fret
) {
    if (!tuning || string_num < 0 || string_num >= tuning->string_count) {
        return -1;
    }
    return tuning->open_midi[string_num] + fret;
}

int32_t fret_find_voicings(
    const TuningConfig* tuning,
    const int32_t*      chord_offsets,
    int32_t             chord_len,
    int32_t             root_pitch_class,
    int32_t             max_span,
    int32_t             max_results,
    VoicingResult*      out_result
) {
    if (!tuning || !chord_offsets || !out_result || chord_len <= 0) {
        return -1;
    }

    int32_t num_strings = (tuning->string_count > MAX_STRINGS) ? MAX_STRINGS : tuning->string_count;
    int32_t max_allowed_span = (max_span > 0) ? max_span : 4;
    int32_t target_results   = (max_results > 0 && max_results <= 32) ? max_results : 8;

    std::memset(out_result, 0, sizeof(VoicingResult));

    int32_t root_pc = (root_pitch_class % 12 + 12) % 12;
    uint32_t required_mask = 0;
    bool is_chord_tone[12] = {false};

    for (int32_t i = 0; i < chord_len; ++i) {
        int32_t pc = (root_pc + chord_offsets[i]) % 12;
        required_mask |= (1u << pc);
        is_chord_tone[pc] = true;
    }

    std::vector<ChordVoicing> candidates;

    // Search across playable hand position windows W from 0 to 14
    for (int32_t window_start = 0; window_start <= 14; ++window_start) {
        int32_t window_end = (window_start == 0) ? max_allowed_span : (window_start + max_allowed_span);

        // Collect candidate frets for each string
        std::vector<std::vector<int32_t>> string_candidates(num_strings);
        for (int32_t s = 0; s < num_strings; ++s) {
            int32_t open_pitch = tuning->open_midi[s];
            int32_t open_pc = (open_pitch % 12 + 12) % 12;

            // Fret -1 (muted) is always an option
            string_candidates[s].push_back(-1);

            // Fret 0 (open string) if it's a chord tone
            if (is_chord_tone[open_pc]) {
                string_candidates[s].push_back(0);
            }

            // Fretted notes in the current window
            int32_t min_f = (window_start == 0) ? 1 : window_start;
            for (int32_t f = min_f; f <= window_end && f <= tuning->fret_count; ++f) {
                int32_t pc = (open_pitch + f) % 12;
                if (is_chord_tone[pc]) {
                    string_candidates[s].push_back(f);
                }
            }
        }

        // Backtracking DFS to explore chord voicings
        struct DFSState {
            int32_t current_frets[MAX_STRINGS];
        } state;

        auto dfs = [&](auto& self, int32_t s_idx, uint32_t cur_mask, int32_t min_f, int32_t max_f, int32_t sounding) -> void {
            if (s_idx == num_strings) {
                // Must have all chord tones present and at least min(3, chord_len) sounding strings
                if (cur_mask == required_mask && sounding >= std::min<int32_t>(3, chord_len)) {
                    // Check for contiguous sound (disallow arbitrary stranded muted strings)
                    // Find first and last sounding string indices
                    int32_t first_sounding = -1;
                    int32_t last_sounding = -1;
                    for (int32_t s = 0; s < num_strings; ++s) {
                        if (state.current_frets[s] >= 0) {
                            if (first_sounding < 0) first_sounding = s;
                            last_sounding = s;
                        }
                    }

                    if (first_sounding < 0 || last_sounding < 0) {
                        return;
                    }

                    // Count internal muted strings between first and last sounding string
                    int32_t internal_mutes = 0;
                    for (int32_t s = first_sounding; s <= last_sounding; ++s) {
                        if (state.current_frets[s] < 0) {
                            internal_mutes++;
                        }
                    }

                    // Allow at most 1 internal mute (common in guitar e.g. A string / D string mute)
                    if (internal_mutes > 1) {
                        return;
                    }

                    // Find lowest sounding string in pitch (bass note)
                    // Highest string index s represents lowest pitched open string in standard notation
                    int32_t bass_string = last_sounding;
                    int32_t bass_fret = state.current_frets[bass_string];
                    int32_t bass_midi = tuning->open_midi[bass_string] + bass_fret;
                    int32_t bass_pc = bass_midi % 12;

                    // Compute span
                    int32_t span = (max_f >= min_f && min_f > 0) ? (max_f - min_f) : 0;
                    if (span > max_allowed_span) {
                        return;
                    }

                    // Build voicing
                    ChordVoicing v;
                    std::memset(&v, 0, sizeof(ChordVoicing));
                    v.string_count = num_strings;
                    v.min_fret = (min_f > 0) ? min_f : 0;
                    v.max_fret = (max_f > 0) ? max_f : 0;
                    v.barre_fret = -1;
                    v.root_string = (bass_pc == root_pc) ? bass_string : -1;

                    // Detect barre
                    int32_t min_fret_count = 0;
                    if (min_f > 0) {
                        for (int32_t s = 0; s < num_strings; ++s) {
                            if (state.current_frets[s] == min_f) {
                                min_fret_count++;
                            }
                        }
                        if (min_fret_count >= 2) {
                            v.barre_fret = min_f;
                        }
                    }

                    // Assign fingers
                    for (int32_t s = 0; s < num_strings; ++s) {
                        int32_t f = state.current_frets[s];
                        v.placements[s].string_num = s;
                        v.placements[s].fret = f;
                        v.placements[s].midi_note = (f >= 0) ? (tuning->open_midi[s] + f) : -1;
                        v.placements[s].finger = -1; // default
                    }

                    if (v.barre_fret > 0) {
                        // Barre gets finger 1 (index)
                        for (int32_t s = 0; s < num_strings; ++s) {
                            if (state.current_frets[s] == v.barre_fret) {
                                v.placements[s].finger = 1;
                            }
                        }
                        // Remaining frets get fingers 2, 3, 4 based on fret distance
                        std::vector<int32_t> other_frets;
                        for (int32_t s = 0; s < num_strings; ++s) {
                            int32_t f = state.current_frets[s];
                            if (f > v.barre_fret) {
                                other_frets.push_back(f);
                            }
                        }
                        std::sort(other_frets.begin(), other_frets.end());
                        other_frets.erase(std::unique(other_frets.begin(), other_frets.end()), other_frets.end());

                        for (int32_t s = 0; s < num_strings; ++s) {
                            int32_t f = state.current_frets[s];
                            if (f > v.barre_fret) {
                                auto it = std::find(other_frets.begin(), other_frets.end(), f);
                                int32_t rank = static_cast<int32_t>(std::distance(other_frets.begin(), it));
                                v.placements[s].finger = std::min(4, 2 + rank);
                            }
                        }
                    } else {
                        // Non-barre finger assignment
                        std::vector<int32_t> active_frets;
                        for (int32_t s = 0; s < num_strings; ++s) {
                            int32_t f = state.current_frets[s];
                            if (f > 0) {
                                active_frets.push_back(f);
                            }
                        }
                        std::sort(active_frets.begin(), active_frets.end());
                        active_frets.erase(std::unique(active_frets.begin(), active_frets.end()), active_frets.end());

                        for (int32_t s = 0; s < num_strings; ++s) {
                            int32_t f = state.current_frets[s];
                            if (f > 0) {
                                auto it = std::find(active_frets.begin(), active_frets.end(), f);
                                int32_t rank = static_cast<int32_t>(std::distance(active_frets.begin(), it));
                                v.placements[s].finger = std::min(4, 1 + rank);
                            }
                        }
                    }

                    // Difficulty score
                    float score = 0.0f;
                    score += span * 2.0f;
                    score += (num_strings - sounding) * 1.5f;
                    score += internal_mutes * 2.5f;
                    if (bass_pc != root_pc) {
                        score += 3.5f; // Inversion penalty
                    }
                    if (v.barre_fret > 0) {
                        score += 1.5f;
                    }
                    score += ((min_f > 0) ? min_f : 0) * 0.15f; // Lower positions preferred

                    v.difficulty_score = score;
                    candidates.push_back(v);
                }
                return;
            }

            for (int32_t f : string_candidates[s_idx]) {
                state.current_frets[s_idx] = f;

                if (f < 0) {
                    self(self, s_idx + 1, cur_mask, min_f, max_f, sounding);
                } else if (f == 0) {
                    int32_t pc = tuning->open_midi[s_idx] % 12;
                    self(self, s_idx + 1, cur_mask | (1u << pc), min_f, max_f, sounding + 1);
                } else {
                    int32_t new_min = (min_f == 0) ? f : std::min(min_f, f);
                    int32_t new_max = std::max(max_f, f);
                    if (new_max - new_min <= max_allowed_span) {
                        int32_t pc = (tuning->open_midi[s_idx] + f) % 12;
                        self(self, s_idx + 1, cur_mask | (1u << pc), new_min, new_max, sounding + 1);
                    }
                }
            }
        };

        dfs(dfs, 0, 0, 0, 0, 0);
    }

    if (candidates.empty()) {
        out_result->count = 0;
        return 0;
    }

    // Sort by difficulty_score ascending
    std::sort(candidates.begin(), candidates.end(), [](const ChordVoicing& a, const ChordVoicing& b) {
        return a.difficulty_score < b.difficulty_score;
    });

    // Deduplicate equivalent fret configurations
    std::vector<ChordVoicing> unique_voicings;
    for (const auto& c : candidates) {
        bool duplicate = false;
        for (const auto& u : unique_voicings) {
            bool exact_match = true;
            for (int32_t s = 0; s < num_strings; ++s) {
                if (c.placements[s].fret != u.placements[s].fret) {
                    exact_match = false;
                    break;
                }
            }
            if (exact_match) {
                duplicate = true;
                break;
            }
        }
        if (!duplicate) {
            unique_voicings.push_back(c);
            if (static_cast<int32_t>(unique_voicings.size()) >= target_results) {
                break;
            }
        }
    }

    int32_t count = static_cast<int32_t>(unique_voicings.size());
    out_result->count = count;
    for (int32_t i = 0; i < count; ++i) {
        out_result->voicings[i] = unique_voicings[i];
    }

    return 0;
}

} // extern "C"
