#ifndef FRETBOARD_MATH_H
#define FRETBOARD_MATH_H

#include <cstdint>

#ifdef _WIN32
    #ifdef FRETENGINE_EXPORTS
        #define FRETAPI __declspec(dllexport)
    #else
        #define FRETAPI __declspec(dllimport)
    #endif
#else
    #define FRETAPI __attribute__((visibility("default")))
#endif

extern "C" {

// =============================================================================
// Constants
// =============================================================================
#define MAX_STRINGS      8
#define MAX_FRETS        24
#define MAX_SCALE_NOTES  12
#define STANDARD_STRINGS 6

// Standard Tuning MIDI pitches (String 1 = high E -> String 6 = low E)
// String 1: E4 (64), String 2: B3 (59), String 3: G3 (55),
// String 4: D3 (50), String 5: A2 (45), String 6: E2 (40)
static const int32_t STANDARD_TUNING_MIDI[STANDARD_STRINGS] = {
    64, // String 1: E4
    59, // String 2: B3
    55, // String 3: G3
    50, // String 4: D3
    45, // String 5: A2
    40  // String 6: E2
};

// =============================================================================
// Data Structures (C ABI compatible for ctypes/pybind11)
// =============================================================================

/// Instrument tuning configuration.
typedef struct {
    int32_t string_count;                       // Number of strings (typically 6)
    int32_t open_midi[MAX_STRINGS];             // MIDI note for each string (high to low)
    int32_t fret_count;                         // Number of frets (typically 21-24)
} TuningConfig;

/// Detailed interval descriptor.
typedef struct {
    int32_t semitones;                          // Total semitones (signed)
    int32_t simple_semitones;                   // Semitones mod 12 (0-11)
    int32_t octaves;                            // Octave displacement
    char    name[16];                           // e.g. "P1", "m3", "M3", "P5", "m7"
} IntervalInfo;

/// Analysis of intervals across multiple simultaneously sounding strings.
typedef struct {
    int32_t      sounding_count;                // Number of unmuted strings
    int32_t      lowest_string_idx;             // Index of lowest-pitched sounding string
    int32_t      lowest_midi_note;              // Lowest sounding MIDI note
    int32_t      string_indices[MAX_STRINGS];   // String indices (0-indexed)
    int32_t      fret_positions[MAX_STRINGS];   // Fret per string (-1 = muted)
    int32_t      midi_notes[MAX_STRINGS];       // MIDI note per string (-1 = muted)
    IntervalInfo interval_from_lowest[MAX_STRINGS]; // Interval relative to the bass note
    IntervalInfo interval_from_adjacent[MAX_STRINGS];// Interval from previous sounding string
} MultiStringIntervalResult;

/// Horizontal shift descriptor for a single string.
typedef struct {
    int32_t string_number;                      // 1-indexed string (1 = high E, 6 = low E)
    int32_t standard_midi;                      // Standard tuning MIDI pitch
    int32_t custom_midi;                        // User custom open MIDI pitch
    int32_t semitone_delta;                     // custom - standard (+2 = tuned up 2 semitones)
    int32_t fret_shift;                         // Visual horizontal fret shift (-semitone_delta)
} TuningShift;

/// Shift result set across all strings.
typedef struct {
    int32_t     string_count;                   // Number of strings evaluated
    TuningShift shifts[MAX_STRINGS];            // Per-string shift descriptors
} TuningShiftResult;

/// Single fretboard coordinate metadata.
typedef struct {
    int32_t string_num;                         // 0-indexed string
    int32_t fret;                               // Fret number (0 = open)
    int32_t midi_note;                          // Calculated MIDI note number
    int32_t pitch_class;                        // midi_note % 12 (0=C, 1=C#, ..., 11=B)
    int32_t in_scale;                           // 1 if note belongs to active scale, else 0
    int32_t scale_degree;                       // 1-7 scale degree (0 if not in scale)
    int32_t is_root;                            // 1 if this note is the scale/chord root
} FretCell;

/// Full 2D matrix of the fretboard.
typedef struct {
    int32_t  string_count;
    int32_t  fret_count;
    FretCell cells[MAX_STRINGS][MAX_FRETS + 1]; // [string][fret], +1 for fret 0 (open)
} FretboardMap;

/// A single finger placement within a chord voicing.
typedef struct {
    int32_t string_num;                         // 0-indexed string (0 = high E)
    int32_t fret;                               // 0 = open, -1 = muted
    int32_t midi_note;                          // Resulting pitch (-1 if muted)
    int32_t finger;                             // Suggested finger: 1=index, 2=middle, 3=ring, 4=pinky, -1=open/muted
} FingerPlacement;

/// A complete chord voicing across all strings.
typedef struct {
    int32_t string_count;
    FingerPlacement placements[MAX_STRINGS];
    float   difficulty_score;                   // Lower = easier
    int32_t min_fret;                           // Lowest fretted fret (>0)
    int32_t max_fret;                           // Highest fretted fret
    int32_t barre_fret;                         // -1 if no barre, else the barre fret
    int32_t root_string;                        // Index of string with lowest root note (-1 if none)
} ChordVoicing;

/// Result buffer for voicing search.
typedef struct {
    int32_t      count;                         // Number of voicings found
    ChordVoicing voicings[32];                  // Top voicings, sorted by difficulty_score
} VoicingResult;

// =============================================================================
// Exported Core API Functions
// =============================================================================

/**
 * Computes interval information between two arbitrary MIDI pitches.
 * @param midi_low  Lower reference pitch (or root).
 * @param midi_high Higher target pitch.
 * @param out_info  Pointer to IntervalInfo struct to populate.
 * @return 0 on success, -1 on invalid arguments.
 */
FRETAPI int32_t fret_calculate_interval(
    int32_t       midi_low,
    int32_t       midi_high,
    IntervalInfo* out_info
);

/**
 * Calculates intervals across multiple strings for a given voicing/shape.
 * Computes:
 *   1. Intervals of each sounding string relative to the lowest sounding note (bass).
 *   2. Intervals between consecutively sounding strings.
 *
 * @param tuning        Instrument tuning configuration.
 * @param frets         Array of fret numbers per string (-1 for muted string, 0 for open).
 * @param string_count  Number of elements in frets array.
 * @param out_result    Output struct containing multi-string interval breakdown.
 * @return 0 on success, -1 on invalid arguments.
 */
FRETAPI int32_t fret_calculate_multi_string_intervals(
    const TuningConfig*        tuning,
    const int32_t*             frets,
    int32_t                    string_count,
    MultiStringIntervalResult* out_result
);

/**
 * Calculates the horizontal visual shift required for each string when retuned
 * relative to the Standard 6-string Guitar Tuning (E2-A2-D3-G3-B3-E4).
 *
 * Mathematical model:
 *   semitone_delta = custom_midi[i] - standard_midi[i]
 *   fret_shift     = -semitone_delta
 *
 * If a string is tuned DOWN by 2 semitones (e.g. E2(40) -> D2(38), delta = -2),
 * the visual representation shifts RIGHT (+2 frets) to align equivalent pitches.
 *
 * @param custom_open_midi Array of custom open-string MIDI pitches (index 0 = high E).
 * @param string_count     Number of strings (typically 6).
 * @param out_result       Output struct receiving per-string shift metrics.
 * @return 0 on success, -1 on invalid arguments.
 */
FRETAPI int32_t fret_calculate_tuning_shifts(
    const int32_t*     custom_open_midi,
    int32_t            string_count,
    TuningShiftResult* out_result
);

/**
 * Calculates horizontal shifts against an arbitrary reference tuning.
 */
FRETAPI int32_t fret_calculate_tuning_shifts_custom_ref(
    const int32_t*     ref_open_midi,
    const int32_t*     custom_open_midi,
    int32_t            string_count,
    TuningShiftResult* out_result
);

/**
 * Dynamically computes the complete fretboard grid for any tuning and scale.
 * Utilizes a 12-element boolean scale mask for O(1) membership determination.
 *
 * @param tuning           Tuning configuration.
 * @param scale_offsets    Array of semitone offsets from root (e.g. {0,2,4,5,7,9,11} for Major).
 * @param scale_len        Number of scale degrees in scale_offsets.
 * @param root_pitch_class Root note pitch class (0=C, 1=C#, ..., 11=B).
 * @param out_map          Output 2D matrix of FretCells.
 * @return 0 on success, -1 on invalid arguments.
 */
FRETAPI int32_t fret_compute_map(
    const TuningConfig* tuning,
    const int32_t*      scale_offsets,
    int32_t             scale_len,
    int32_t             root_pitch_class,
    FretboardMap*       out_map
);

/**
 * Computes the exact MIDI note at a specific string and fret.
 * Formula: open_midi[string_num] + fret.
 */
FRETAPI int32_t fret_note_at(
    const TuningConfig* tuning,
    int32_t             string_num,
    int32_t             fret
);

/**
 * Returns standard interval abbreviation string (e.g. "P1", "m3", "M3", "P5", "m7").
 * @param semitones Semitone distance.
 * @return Static string pointer.
 */
FRETAPI const char* fret_get_interval_name(int32_t semitones);

/**
 * Searches for optimal chord voicings across the fretboard for a given chord formula.
 *
 * @param tuning           Instrument tuning configuration.
 * @param chord_offsets    Semitone offsets defining the chord (e.g. {0, 4, 7} for Major).
 * @param chord_len        Number of intervals in chord_offsets.
 * @param root_pitch_class Root note pitch class (0=C, 1=C#, ..., 11=B).
 * @param max_span         Maximum allowed fret span (e.g. 4).
 * @param max_results      Maximum number of voicings to return (up to 32).
 * @param out_result       Output struct containing sorted voicings with finger assignments.
 * @return 0 on success, -1 on invalid arguments.
 */
FRETAPI int32_t fret_find_voicings(
    const TuningConfig* tuning,
    const int32_t*      chord_offsets,
    int32_t             chord_len,
    int32_t             root_pitch_class,
    int32_t             max_span,
    int32_t             max_results,
    VoicingResult*      out_result
);

} // extern "C"

#endif // FRETBOARD_MATH_H
