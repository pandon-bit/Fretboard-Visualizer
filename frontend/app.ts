/**
 * app.ts — Strongly-typed Frontend Controller for Guitar Fretboard Visualizer
 * Seamlessly bridges TypeScript UI with the Python FastAPI backend,
 * C++ Shared Algorithm Engine, and SQLite Relational Music Models.
 */

// =============================================================================
// Interfaces & Type Definitions
// =============================================================================

export interface TuningShiftItem {
  string_number: number;
  standard_midi: number;
  standard_name: string;
  custom_midi: number;
  custom_name: string;
  semitone_delta: number;
  fret_shift: number;
}

export interface TuningResponse {
  custom_tuning: number[];
  reference_tuning: number[];
  shifts: TuningShiftItem[];
}

export interface ScaleNote {
  degree: number;
  label: string;
  note_name: string;
  pitch_class: number;
  semitone_offset: number;
}

export interface FretCellData {
  string: number;
  string_idx: number;
  fret: number;
  midi_note: number;
  pitch_class: number;
  note_name: string;
  in_scale: boolean;
  scale_degree: number;
  is_root: boolean;
}

export interface ScaleResponse {
  root: string;
  scale_type: string;
  formula: number[];
  active_notes: ScaleNote[];
  fretboard_map: FretCellData[][] | null;
}

export interface VoicingPlacement {
  string_number: number;
  fret: number;
  midi_note: number;
  finger: number;
  note_name: string;
}

export interface VoicingDto {
  placements: VoicingPlacement[];
  difficulty_score: number;
  min_fret: number;
  max_fret: number;
  barre_fret: number;
  root_string: number | null;
  tab_repr: string;
}

export interface DiatonicChordDto {
  degree: number;
  roman_numeral: string;
  chord_name: string;
  chord_symbol: string;
  root_note: string;
  root_pitch_class: number;
  chord_offsets: number[];
  notes: string[];
  voicings: VoicingDto[];
}

export interface ChordsResponse {
  key_name: string;
  root: string;
  scale_type: string;
  tuning: number[];
  diatonic_chords: DiatonicChordDto[];
}

interface AppState {
  viewMode: "scale" | "chord";
  currentTuning: number[];
  shifts: number[];
  scaleRoot: string;
  scaleType: string;
  displayMode: "notes" | "degrees" | "intervals";
  chordKeyRoot: string;
  chordKeyMode: "Major" | "Minor";
  diatonicChords: DiatonicChordDto[];
  selectedChordIndex: number;
  selectedVoicingIndex: number;
  isApiConnected: boolean;
  scaleActiveNotes: ScaleNote[];
  scaleFretboardGrid: FretCellData[][] | null;
}

// =============================================================================
// Constants & Configuration
// =============================================================================

const NOTE_NAMES: readonly string[] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

const STANDARD_TUNING = [
  { string: 1, midi: 64, name: "E4" },
  { string: 2, midi: 59, name: "B3" },
  { string: 3, midi: 55, name: "G3" },
  { string: 4, midi: 50, name: "D3" },
  { string: 5, midi: 45, name: "A2" },
  { string: 6, midi: 40, name: "E2" }
];

const PRESET_TUNINGS: Record<string, number[]> = {
  standard:       [64, 59, 55, 50, 45, 40],
  drop_d:         [64, 59, 55, 50, 45, 38],
  dadgad:         [62, 57, 55, 50, 45, 38],
  half_step_down: [63, 58, 54, 49, 44, 39],
  open_d:         [62, 57, 54, 50, 45, 38],
  open_g:         [62, 59, 55, 50, 43, 38]
};

const FRET_COUNT = 24;
const FRET_WIDTH_PX = 58;

// Primary API endpoint (FastAPI runs on 127.0.0.1:8000)
const API_BASE_URL = "http://127.0.0.1:8000";

// =============================================================================
// Reactive State Store
// =============================================================================

const state: AppState = {
  viewMode: "scale",
  currentTuning: [64, 59, 55, 50, 45, 40],
  shifts: [0, 0, 0, 0, 0, 0],
  scaleRoot: "C",
  scaleType: "major",
  displayMode: "notes",
  chordKeyRoot: "C",
  chordKeyMode: "Major",
  diatonicChords: [],
  selectedChordIndex: 0,
  selectedVoicingIndex: 0,
  isApiConnected: false,
  scaleActiveNotes: [],
  scaleFretboardGrid: null
};

// =============================================================================
// Music Theory Helpers
// =============================================================================

function midiToNoteName(midi: number): string {
  const pc = ((midi % 12) + 12) % 12;
  const octave = Math.floor(midi / 12) - 1;
  return `${NOTE_NAMES[pc]}${octave}`;
}

function noteNameToPitchClass(name: string): number {
  const clean = name.replace(/[0-9]/g, "").trim().toUpperCase();
  const map: Record<string, number> = {
    "C": 0, "B#": 0,
    "C#": 1, "DB": 1,
    "D": 2,
    "D#": 3, "EB": 3,
    "E": 4, "FB": 4,
    "F": 5, "E#": 5,
    "F#": 6, "GB": 6,
    "G": 7,
    "G#": 8, "AB": 8,
    "A": 9,
    "A#": 10, "BB": 10,
    "B": 11, "CB": 11
  };
  return map[clean] ?? 0;
}

// =============================================================================
// API Service Layer (FastAPI Backend + C++ Engine)
// =============================================================================

async function apiFetchTuning(openMidis: number[]): Promise<TuningResponse> {
  const res = await fetch(`${API_BASE_URL}/api/tuning`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ open_midi: openMidis })
  });
  if (!res.ok) throw new Error(`Tuning API error: ${res.status} ${res.statusText}`);
  return res.json();
}

async function apiFetchScale(root: string, scaleType: string, tuning: number[]): Promise<ScaleResponse> {
  const res = await fetch(`${API_BASE_URL}/api/scales`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      root: root,
      scale_type: scaleType,
      tuning: tuning,
      include_fretboard: true
    })
  });
  if (!res.ok) throw new Error(`Scale API error: ${res.status} ${res.statusText}`);
  return res.json();
}

async function apiFetchChords(keyName: string, tuning: number[], maxVoicings: number = 4): Promise<ChordsResponse> {
  const res = await fetch(`${API_BASE_URL}/api/chords`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      key: keyName,
      tuning: tuning,
      max_voicings: maxVoicings
    })
  });
  if (!res.ok) throw new Error(`Chord API error: ${res.status} ${res.statusText}`);
  return res.json();
}

async function checkApiConnection(): Promise<boolean> {
  const statusBadge = document.getElementById("api-status-badge");
  const statusText = document.getElementById("api-status-text");

  try {
    const res = await fetch(`${API_BASE_URL}/`, { method: "GET" });
    if (res.ok) {
      state.isApiConnected = true;
      if (statusBadge) {
        statusBadge.style.background = "rgba(46, 213, 115, 0.12)";
        statusBadge.style.color = "#2ed573";
        statusBadge.style.borderColor = "rgba(46, 213, 115, 0.35)";
      }
      if (statusText) statusText.textContent = "C++ & Python API: Online";
      return true;
    }
  } catch {
    // API offline
  }

  state.isApiConnected = false;
  if (statusBadge) {
    statusBadge.style.background = "rgba(255, 165, 2, 0.12)";
    statusBadge.style.color = "#ffa502";
    statusBadge.style.borderColor = "rgba(255, 165, 2, 0.35)";
  }
  if (statusText) statusText.textContent = "Connecting to API Engine...";
  return false;
}

// =============================================================================
// DOM Initialization & Theme Controller
// =============================================================================

function initTheme(): void {
  const savedTheme = localStorage.getItem("fretboard_theme");
  const prefersLight = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  const initialTheme = savedTheme ? savedTheme : (prefersLight ? "light" : "dark");
  
  applyTheme(initialTheme);

  const toggleBtn = document.getElementById("theme-toggle-btn");
  toggleBtn?.addEventListener("click", () => {
    const currentTheme = document.documentElement.getAttribute("data-theme") || (prefersLight ? "light" : "dark");
    const nextTheme = currentTheme === "light" ? "dark" : "light";
    applyTheme(nextTheme);
    localStorage.setItem("fretboard_theme", nextTheme);
  });

  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", (e) => {
      if (!localStorage.getItem("fretboard_theme")) {
        applyTheme(e.matches ? "light" : "dark");
      }
    });
  }
}

function applyTheme(theme: string): void {
  document.documentElement.setAttribute("data-theme", theme);
  if (theme === "light") {
    document.body.classList.add("light-mode");
  } else {
    document.body.classList.remove("light-mode");
  }
  const iconEl = document.getElementById("theme-toggle-icon");
  const textEl = document.getElementById("theme-toggle-text");
  if (iconEl && textEl) {
    if (theme === "light") {
      iconEl.textContent = "🌙";
      textEl.textContent = "Dark Mode";
    } else {
      iconEl.textContent = "☀️";
      textEl.textContent = "Light Mode";
    }
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  initTuningDropdowns();
  buildFretboardStructure();
  setupEventListeners();
  await checkApiConnection();
  await triggerTuningUpdate();
});

function initTuningDropdowns(): void {
  for (let s = 1; s <= 6; s++) {
    const select = document.getElementById(`string-select-${s}`) as HTMLSelectElement | null;
    if (!select) continue;
    select.innerHTML = "";

    // Chromatic range from C2 (36) to C6 (72)
    for (let midi = 36; midi <= 72; midi++) {
      const opt = document.createElement("option");
      opt.value = String(midi);
      opt.textContent = midiToNoteName(midi);
      select.appendChild(opt);
    }
    select.value = String(STANDARD_TUNING[s - 1].midi);
  }
}

function buildFretboardStructure(): void {
  const fretNumbersRow = document.getElementById("fret-numbers-row");
  const inlayLayer = document.getElementById("fret-inlay-layer");
  if (!fretNumbersRow || !inlayLayer) return;

  const singleInlays = [3, 5, 7, 9, 15, 17, 19, 21];
  const doubleInlays = [12, 24];

  // Fret numbers 1 to 24
  for (let f = 1; f <= FRET_COUNT; f++) {
    const numCell = document.createElement("div");
    numCell.className = "fret-num-cell";
    if (singleInlays.includes(f) || doubleInlays.includes(f)) {
      numCell.classList.add("special-fret");
    }
    numCell.textContent = String(f);
    fretNumbersRow.appendChild(numCell);

    // Pearl Marker Inlays
    const inlaySlot = document.createElement("div");
    inlaySlot.className = "inlay-slot";
    if (singleInlays.includes(f)) {
      const dot = document.createElement("div");
      dot.className = "inlay-dot";
      inlaySlot.appendChild(dot);
    } else if (doubleInlays.includes(f)) {
      const doubleWrap = document.createElement("div");
      doubleWrap.className = "inlay-double";
      doubleWrap.innerHTML = '<div class="inlay-dot"></div><div class="inlay-dot"></div>';
      inlaySlot.appendChild(doubleWrap);
    }
    inlayLayer.appendChild(inlaySlot);
  }

  // Build the 6 string rows (String 1 = high E to String 6 = low E)
  for (let s = 1; s <= 6; s++) {
    const stringRow = document.getElementById(`string-row-${s}`);
    if (!stringRow) continue;
    const wire = stringRow.querySelector(".string-wire");
    stringRow.innerHTML = "";
    if (wire) stringRow.appendChild(wire);

    // Nut cell (Fret 0)
    const nutCell = document.createElement("div");
    nutCell.className = "fret-cell nut-cell";
    nutCell.dataset.string = String(s);
    nutCell.dataset.fret = "0";
    stringRow.appendChild(nutCell);

    // Frets 1 through 24
    for (let f = 1; f <= FRET_COUNT; f++) {
      const cell = document.createElement("div");
      cell.className = "fret-cell";
      cell.dataset.string = String(s);
      cell.dataset.fret = String(f);
      stringRow.appendChild(cell);
    }
  }
}

// =============================================================================
// Event Listeners
// =============================================================================

function setupEventListeners(): void {
  const tabScale = document.getElementById("tab-scale-mode");
  const tabChord = document.getElementById("tab-chord-mode");
  const panelScale = document.getElementById("panel-scale-controls");
  const panelChord = document.getElementById("panel-chord-controls");
  const romanBar = document.getElementById("roman-bar-section");

  // Tab: Scale View
  tabScale?.addEventListener("click", () => {
    state.viewMode = "scale";
    tabScale.classList.add("active");
    tabChord?.classList.remove("active");
    tabScale.setAttribute("aria-selected", "true");
    tabChord?.setAttribute("aria-selected", "false");
    if (panelScale) panelScale.style.display = "block";
    if (panelChord) panelChord.style.display = "none";
    if (romanBar) romanBar.style.display = "none";
    render();
  });

  // Tab: Chord View
  tabChord?.addEventListener("click", () => {
    state.viewMode = "chord";
    tabChord.classList.add("active");
    tabScale?.classList.remove("active");
    tabChord.setAttribute("aria-selected", "true");
    tabScale?.setAttribute("aria-selected", "false");
    if (panelScale) panelScale.style.display = "none";
    if (panelChord) panelChord.style.display = "block";
    if (romanBar) romanBar.style.display = "flex";
    fetchChordsFromApi();
  });

  // Preset Tuning Selector
  const presetSelect = document.getElementById("tuning-preset-select") as HTMLSelectElement | null;
  presetSelect?.addEventListener("change", (e) => {
    const val = (e.target as HTMLSelectElement).value;
    const preset = PRESET_TUNINGS[val];
    if (preset) {
      state.currentTuning = [...preset];
      for (let s = 1; s <= 6; s++) {
        const sel = document.getElementById(`string-select-${s}`) as HTMLSelectElement | null;
        if (sel) sel.value = String(preset[s - 1]);
      }
      triggerTuningUpdate();
    }
  });

  // Individual String Pitches (Strings 1 to 6)
  for (let s = 1; s <= 6; s++) {
    const sel = document.getElementById(`string-select-${s}`) as HTMLSelectElement | null;
    sel?.addEventListener("change", (e) => {
      const midiVal = parseInt((e.target as HTMLSelectElement).value, 10);
      state.currentTuning[s - 1] = midiVal;
      if (presetSelect) presetSelect.value = "";
      triggerTuningUpdate();
    });
  }

  // Reset Standard Tuning Button
  document.getElementById("reset-tuning-btn")?.addEventListener("click", () => {
    state.currentTuning = [...PRESET_TUNINGS.standard];
    if (presetSelect) presetSelect.value = "standard";
    for (let s = 1; s <= 6; s++) {
      const sel = document.getElementById(`string-select-${s}`) as HTMLSelectElement | null;
      if (sel) sel.value = String(STANDARD_TUNING[s - 1].midi);
    }
    triggerTuningUpdate();
  });

  // Scale Root Note Selector
  const rootSelect = document.getElementById("scale-root-select") as HTMLSelectElement | null;
  rootSelect?.addEventListener("change", (e) => {
    state.scaleRoot = (e.target as HTMLSelectElement).value;
    render();
  });

  // Scale Quality Selector
  const typeSelect = document.getElementById("scale-type-select") as HTMLSelectElement | null;
  typeSelect?.addEventListener("change", (e) => {
    state.scaleType = (e.target as HTMLSelectElement).value;
    render();
  });

  // Note Badge Label Display Mode (Note Name, Degree, Interval)
  const displaySelect = document.getElementById("note-display-mode") as HTMLSelectElement | null;
  displaySelect?.addEventListener("change", (e) => {
    state.displayMode = (e.target as HTMLSelectElement).value as "notes" | "degrees" | "intervals";
    render();
  });

  // Key Center Root Selector (Chord View)
  const chordRootSelect = document.getElementById("chord-key-root-select") as HTMLSelectElement | null;
  chordRootSelect?.addEventListener("change", (e) => {
    state.chordKeyRoot = (e.target as HTMLSelectElement).value;
    fetchChordsFromApi();
  });

  // Key Quality Selector (Chord View)
  const chordModeSelect = document.getElementById("chord-key-mode-select") as HTMLSelectElement | null;
  chordModeSelect?.addEventListener("change", (e) => {
    state.chordKeyMode = (e.target as HTMLSelectElement).value as "Major" | "Minor";
    fetchChordsFromApi();
  });

  // Voicing Navigation Buttons
  document.getElementById("prev-voicing-btn")?.addEventListener("click", () => {
    const chord = state.diatonicChords[state.selectedChordIndex];
    if (chord?.voicings && chord.voicings.length > 0) {
      state.selectedVoicingIndex = (state.selectedVoicingIndex - 1 + chord.voicings.length) % chord.voicings.length;
      renderChordVoicing();
    }
  });

  document.getElementById("next-voicing-btn")?.addEventListener("click", () => {
    const chord = state.diatonicChords[state.selectedChordIndex];
    if (chord?.voicings && chord.voicings.length > 0) {
      state.selectedVoicingIndex = (state.selectedVoicingIndex + 1) % chord.voicings.length;
      renderChordVoicing();
    }
  });

  setupTooltipEvents();
}

// =============================================================================
// Tuning & Dynamic Horizontal String Shift Loop
// =============================================================================

async function triggerTuningUpdate(): Promise<void> {
  try {
    const data = await apiFetchTuning(state.currentTuning);
    state.isApiConnected = true;
    updateApiStatusBadge(true);
    applyTuningShiftsFromApi(data.shifts);
  } catch (err) {
    console.warn("API tuning request failed, using local shift calculation:", err);
    applyLocalTuningShifts();
  }

  if (state.viewMode === "scale") {
    await renderScaleView();
  } else {
    await fetchChordsFromApi();
  }
}

function updateApiStatusBadge(online: boolean): void {
  const statusBadge = document.getElementById("api-status-badge");
  const statusText = document.getElementById("api-status-text");
  if (!statusBadge || !statusText) return;

  if (online) {
    statusBadge.style.background = "rgba(46, 213, 115, 0.12)";
    statusBadge.style.color = "#2ed573";
    statusBadge.style.borderColor = "rgba(46, 213, 115, 0.35)";
    statusText.textContent = "C++ & Python API: Online";
  } else {
    statusBadge.style.background = "rgba(255, 165, 2, 0.12)";
    statusBadge.style.color = "#ffa502";
    statusBadge.style.borderColor = "rgba(255, 165, 2, 0.35)";
    statusText.textContent = "Connecting to API Engine...";
  }
}

function applyTuningShiftsFromApi(shifts: TuningShiftItem[]): void {
  shifts.forEach((item) => {
    const s = item.string_number;
    const delta = item.semitone_delta;
    const fretShift = item.fret_shift;
    state.shifts[s - 1] = fretShift;

    updateStringShiftDom(s, delta, fretShift);
  });
}

function applyLocalTuningShifts(): void {
  for (let s = 1; s <= 6; s++) {
    const stdMidi = STANDARD_TUNING[s - 1].midi;
    const curMidi = state.currentTuning[s - 1];
    const delta = curMidi - stdMidi;
    const fretShift = -delta;
    state.shifts[s - 1] = fretShift;

    updateStringShiftDom(s, delta, fretShift);
  }
}

function updateStringShiftDom(stringNum: number, delta: number, fretShift: number): void {
  const badge = document.getElementById(`shift-badge-${stringNum}`);
  const box = document.getElementById(`tuning-box-${stringNum}`);
  const stringRow = document.getElementById(`string-row-${stringNum}`);

  if (badge) {
    if (delta === 0) {
      badge.textContent = "±0";
      badge.classList.remove("active-shift");
    } else {
      const shiftStr = fretShift > 0 ? `+${fretShift} fr` : `${fretShift} fr`;
      badge.textContent = `${delta > 0 ? "+" : ""}${delta} st (${shiftStr})`;
      badge.classList.add("active-shift");
    }
  }

  if (box) {
    if (delta !== 0) box.classList.add("shifted");
    else box.classList.remove("shifted");
  }

  // Smooth reactive horizontal shift of the physical string wire and frets!
  if (stringRow) {
    const pixelShift = fretShift * FRET_WIDTH_PX;
    stringRow.style.transform = `translateX(${pixelShift}px)`;
  }
}

// =============================================================================
// Scale Rendering Logic
// =============================================================================

async function renderScaleView(): Promise<void> {
  const rootStr = state.scaleRoot;
  const scaleTypeStr = state.scaleType;

  let fretboardGrid: FretCellData[][] | null = null;
  let activeNotes: ScaleNote[] = [];

  try {
    const res = await apiFetchScale(rootStr, scaleTypeStr, state.currentTuning);
    fretboardGrid = res.fretboard_map;
    activeNotes = res.active_notes;
    state.scaleActiveNotes = activeNotes;
    state.scaleFretboardGrid = fretboardGrid;
    updateApiStatusBadge(true);
  } catch (err) {
    console.warn("API scale fetch failed, rendering locally:", err);
  }

  const summary = document.getElementById("active-scale-summary");
  if (summary) summary.textContent = `${rootStr} ${scaleTypeStr.toUpperCase()}`;

  if (fretboardGrid) {
    renderFretboardFromGrid(fretboardGrid, activeNotes);
    renderFormulaPills(activeNotes);
  } else {
    renderScaleLocally();
  }
}

function renderFretboardFromGrid(grid: FretCellData[][], activeNotes: ScaleNote[]): void {
  const degreeToLabel = new Map<number, string>();
  activeNotes.forEach((n) => degreeToLabel.set(n.degree, n.label));

  grid.forEach((row, sIdx) => {
    const s = sIdx + 1;
    row.forEach((cellData) => {
      const f = cellData.fret;
      const cell = document.querySelector(`.fret-cell[data-string="${s}"][data-fret="${f}"]`);
      if (!cell) return;
      cell.innerHTML = "";

      const marker = document.createElement("div");
      marker.className = "note-marker";
      marker.dataset.string = String(s);
      marker.dataset.fret = String(f);
      marker.dataset.midi = String(cellData.midi_note);
      marker.dataset.note = cellData.note_name;
      marker.dataset.pc = String(cellData.pitch_class);
      marker.dataset.inScale = String(cellData.in_scale);
      marker.dataset.isRoot = String(cellData.is_root);
      marker.dataset.degree = String(cellData.scale_degree);

      // Display Mode Labeling
      if (cellData.in_scale) {
        if (state.displayMode === "degrees") {
          marker.textContent = String(cellData.scale_degree);
        } else if (state.displayMode === "intervals") {
          marker.textContent = degreeToLabel.get(cellData.scale_degree) || cellData.note_name;
        } else {
          marker.textContent = cellData.note_name;
        }
      } else {
        marker.textContent = cellData.note_name;
      }

      // Harmonic Styling
      if (!cellData.in_scale) {
        marker.classList.add("dimmed");
      } else {
        marker.classList.add("in-scale");
        if (cellData.is_root) {
          marker.classList.add("is-root");
        } else if (cellData.scale_degree === 3) {
          marker.classList.add("chord-3rd");
        } else if (cellData.scale_degree === 5) {
          marker.classList.add("chord-5th");
        } else if (cellData.scale_degree === 7) {
          marker.classList.add("chord-7th");
        }
      }

      cell.appendChild(marker);
    });
  });
}

function renderFormulaPills(notes: ScaleNote[]): void {
  const formulaBar = document.getElementById("scale-formula-bar");
  if (!formulaBar) return;
  formulaBar.innerHTML = "";

  notes.forEach((item, idx) => {
    const isRoot = idx === 0;
    const pill = document.createElement("div");
    pill.className = isRoot ? "formula-pill is-root" : "formula-pill";
    pill.innerHTML = `<span>${item.note_name}</span><span class="pill-label">(${item.label})</span>`;
    formulaBar.appendChild(pill);
  });
}

function renderScaleLocally(): void {
  const rootPc = noteNameToPitchClass(state.scaleRoot);
  const majorIntervals = [0, 2, 4, 5, 7, 9, 11];
  const minorIntervals = [0, 2, 3, 5, 7, 8, 10];
  const harmonicMinorIntervals = [0, 2, 3, 5, 7, 8, 11];
  const minorPentatonicIntervals = [0, 3, 5, 7, 10];
  const majorPentatonicIntervals = [0, 2, 4, 7, 9];
  const bluesIntervals = [0, 3, 5, 6, 7, 10];

  let intervals = majorIntervals;
  if (state.scaleType === "minor") intervals = minorIntervals;
  else if (state.scaleType === "harmonic minor") intervals = harmonicMinorIntervals;
  else if (state.scaleType === "minor pentatonic") intervals = minorPentatonicIntervals;
  else if (state.scaleType === "major pentatonic") intervals = majorPentatonicIntervals;
  else if (state.scaleType === "blues") intervals = bluesIntervals;

  const activePcs = new Map<number, number>();
  intervals.forEach((off, idx) => {
    activePcs.set((rootPc + off) % 12, idx + 1);
  });

  for (let s = 1; s <= 6; s++) {
    const openMidi = state.currentTuning[s - 1];

    for (let f = 0; f <= FRET_COUNT; f++) {
      const cell = document.querySelector(`.fret-cell[data-string="${s}"][data-fret="${f}"]`);
      if (!cell) continue;
      cell.innerHTML = "";

      const noteMidi = openMidi + f;
      const pc = ((noteMidi % 12) + 12) % 12;
      const noteName = NOTE_NAMES[pc];
      const degree = activePcs.get(pc) ?? 0;
      const inScale = degree > 0;
      const isRoot = pc === rootPc;

      const marker = document.createElement("div");
      marker.className = "note-marker";
      marker.dataset.string = String(s);
      marker.dataset.fret = String(f);
      marker.dataset.midi = String(noteMidi);
      marker.dataset.note = noteName;
      marker.dataset.pc = String(pc);
      marker.dataset.inScale = String(inScale);
      marker.dataset.isRoot = String(isRoot);
      marker.dataset.degree = String(degree);

      if (inScale && state.displayMode === "degrees") {
        marker.textContent = String(degree);
      } else {
        marker.textContent = noteName;
      }

      if (!inScale) {
        marker.classList.add("dimmed");
      } else {
        marker.classList.add("in-scale");
        if (isRoot) marker.classList.add("is-root");
        else if (degree === 3) marker.classList.add("chord-3rd");
        else if (degree === 5) marker.classList.add("chord-5th");
        else if (degree === 7) marker.classList.add("chord-7th");
      }

      cell.appendChild(marker);
    }
  }
}

// =============================================================================
// Chord View: Diatonic Roman Numerals & Voicing Solver
// =============================================================================

async function fetchChordsFromApi(): Promise<void> {
  const keyName = `${state.chordKeyRoot} ${state.chordKeyMode}`;
  const summary = document.getElementById("active-key-summary");
  if (summary) summary.textContent = `Key: ${keyName}`;

  try {
    const data = await apiFetchChords(keyName, state.currentTuning, 4);
    state.diatonicChords = data.diatonic_chords;
    state.selectedChordIndex = 0;
    state.selectedVoicingIndex = 0;
    updateApiStatusBadge(true);
    renderRomanButtons();
    renderChordVoicing();
  } catch (err) {
    console.warn("Chords API error, building local diatonic models:", err);
    buildLocalDiatonicChords(state.chordKeyRoot, state.chordKeyMode);
    renderRomanButtons();
    renderChordVoicing();
  }
}

function buildLocalDiatonicChords(rootNote: string, mode: "Major" | "Minor"): void {
  const rootPc = noteNameToPitchClass(rootNote);
  const majorDegrees = [
    { deg: 1, roman: "I",    symbol: "",     offsets: [0, 4, 7], quality: "Major" },
    { deg: 2, roman: "ii",   symbol: "m",    offsets: [0, 3, 7], quality: "Minor" },
    { deg: 3, roman: "iii",  symbol: "m",    offsets: [0, 3, 7], quality: "Minor" },
    { deg: 4, roman: "IV",   symbol: "",     offsets: [0, 4, 7], quality: "Major" },
    { deg: 5, roman: "V",    symbol: "",     offsets: [0, 4, 7], quality: "Major" },
    { deg: 6, roman: "vi",   symbol: "m",    offsets: [0, 3, 7], quality: "Minor" },
    { deg: 7, roman: "vii°", symbol: "°",    offsets: [0, 3, 6], quality: "Diminished" }
  ];
  const minorDegrees = [
    { deg: 1, roman: "i",    symbol: "m",    offsets: [0, 3, 7], quality: "Minor" },
    { deg: 2, roman: "ii°",  symbol: "°",    offsets: [0, 3, 6], quality: "Diminished" },
    { deg: 3, roman: "III",  symbol: "",     offsets: [0, 4, 7], quality: "Major" },
    { deg: 4, roman: "iv",   symbol: "m",    offsets: [0, 3, 7], quality: "Minor" },
    { deg: 5, roman: "v",    symbol: "m",    offsets: [0, 3, 7], quality: "Minor" },
    { deg: 6, roman: "VI",   symbol: "",     offsets: [0, 4, 7], quality: "Major" },
    { deg: 7, roman: "VII",  symbol: "",     offsets: [0, 4, 7], quality: "Major" }
  ];

  const scaleOffsets = mode === "Major" ? [0, 2, 4, 5, 7, 9, 11] : [0, 2, 3, 5, 7, 8, 10];
  const degreeTemplates = mode === "Major" ? majorDegrees : minorDegrees;

  state.diatonicChords = degreeTemplates.map((t, idx) => {
    const chordRootPc = (rootPc + scaleOffsets[idx]) % 12;
    const chordRootName = NOTE_NAMES[chordRootPc];
    const notes = t.offsets.map((off) => NOTE_NAMES[(chordRootPc + off) % 12]);

    return {
      degree: t.deg,
      roman_numeral: t.roman,
      chord_name: `${chordRootName} ${t.quality}`,
      chord_symbol: t.symbol,
      root_note: chordRootName,
      root_pitch_class: chordRootPc,
      chord_offsets: t.offsets,
      notes: notes,
      voicings: []
    };
  });
}

function renderRomanButtons(): void {
  const container = document.getElementById("roman-buttons-container");
  if (!container) return;
  container.innerHTML = "";

  state.diatonicChords.forEach((chord, idx) => {
    const btn = document.createElement("button");
    btn.className = "roman-chord-btn";
    btn.setAttribute("type", "button");
    btn.setAttribute("aria-label", `${chord.roman_numeral} - ${chord.root_note}${chord.chord_symbol}`);
    if (idx === state.selectedChordIndex) {
      btn.classList.add("active");
    }

    btn.innerHTML = `
      <span class="roman-numeral-text">${chord.roman_numeral}</span>
      <span class="roman-chord-name">${chord.root_note}${chord.chord_symbol}</span>
      <span class="roman-chord-notes">${chord.notes.join(" ")}</span>
    `;

    btn.addEventListener("click", () => {
      state.selectedChordIndex = idx;
      state.selectedVoicingIndex = 0;
      document.querySelectorAll(".roman-chord-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      renderChordVoicing();
    });

    container.appendChild(btn);
  });
}

function renderChordVoicing(): void {
  const chord = state.diatonicChords[state.selectedChordIndex];
  if (!chord) return;

  const voicings = chord.voicings || [];
  const voicing = voicings[state.selectedVoicingIndex];

  // Update Voicing Metadata Bar
  const titleEl = document.getElementById("voicing-chord-title");
  if (titleEl) {
    titleEl.textContent = `${chord.roman_numeral} : ${chord.root_note}${chord.chord_symbol} (${chord.chord_name})`;
  }

  const tabEl = document.getElementById("voicing-tab-display");
  const scoreEl = document.getElementById("voicing-score-display");
  const countEl = document.getElementById("voicing-index-indicator");
  const voicingCountLabel = document.getElementById("chord-voicing-count-label");

  if (voicingCountLabel) {
    voicingCountLabel.textContent = `C++ Solver: ${voicings.length} Voicings Found`;
  }

  if (voicing) {
    if (tabEl) tabEl.textContent = `Tab: ${voicing.tab_repr}`;
    if (scoreEl) {
      const barreInfo = voicing.barre_fret > 0 ? ` • [Barre Fret ${voicing.barre_fret}]` : "";
      scoreEl.textContent = `Score: ${voicing.difficulty_score} • Span: Frets ${voicing.min_fret}–${voicing.max_fret}${barreInfo}`;
    }
    if (countEl) countEl.textContent = `${state.selectedVoicingIndex + 1} / ${voicings.length}`;
  } else {
    if (tabEl) tabEl.textContent = `Triad: ${chord.notes.join(" - ")}`;
    if (scoreEl) scoreEl.textContent = "Voicing calculated on backend";
    if (countEl) countEl.textContent = "1 / 1";
  }

  // 1. Render all fretboard background notes for the current active Key and Chord
  renderChordBackgroundGrid(chord);

  // 2. Remove any previous nut status badges
  document.querySelectorAll(".nut-status-badge").forEach((badge) => badge.remove());

  // 3. Highlight the optimal finger voicings on the fretboard
  if (!voicing) return;

  voicing.placements.forEach((p) => {
    const stringNum = p.string_number;
    const fretVal = p.fret;
    const nutCell = document.querySelector(`.fret-cell.nut-cell[data-string="${stringNum}"]`);

    if (fretVal < 0) {
      // Muted string (✕ on nut)
      if (nutCell) {
        const xBadge = document.createElement("div");
        xBadge.className = "nut-status-badge muted";
        xBadge.textContent = "✕";
        xBadge.title = `String ${stringNum}: Muted`;
        nutCell.appendChild(xBadge);
      }
      return;
    }

    if (fretVal === 0) {
      // Open string (○ on nut)
      if (nutCell) {
        const oBadge = document.createElement("div");
        oBadge.className = "nut-status-badge open";
        oBadge.textContent = "○";
        oBadge.title = `String ${stringNum}: Open (${p.note_name})`;
        nutCell.appendChild(oBadge);
      }
      return;
    }

    // Fretted Note (fretVal >= 1)
    const cell = document.querySelector(`.fret-cell[data-string="${stringNum}"][data-fret="${fretVal}"]`);
    if (cell) {
      let marker = cell.querySelector(".note-marker") as HTMLElement | null;
      if (!marker) {
        marker = document.createElement("div");
        marker.className = "note-marker";
        cell.appendChild(marker);
      }

      marker.classList.remove("dimmed", "in-scale");
      const isBarre = voicing.barre_fret === fretVal && fretVal > 0;
      marker.classList.add(isBarre ? "voicing-barre" : "voicing-fretted");

      if (p.finger > 0) {
        marker.textContent = String(p.finger);
        marker.title = `Finger ${p.finger} (${p.note_name}) • String ${stringNum}, Fret ${fretVal}`;
      } else {
        marker.textContent = p.note_name;
        marker.title = `${p.note_name} • String ${stringNum}, Fret ${fretVal}`;
      }
    }
  });
}

/**
 * Renders the harmonic context for the Chord View:
 * - Highlights chord tones (Root = Red, 3rd = Orange, 5th = Green)
 * - Highlights Key diatonic scale tones subtly in the background
 * - Dims all chromatic tones outside the Key
 */
function renderChordBackgroundGrid(chord: DiatonicChordDto): void {
  const keyRootPc = noteNameToPitchClass(state.chordKeyRoot);
  const keyScaleOffsets = state.chordKeyMode === "Major" ? [0, 2, 4, 5, 7, 9, 11] : [0, 2, 3, 5, 7, 8, 10];
  const keyPcs = new Set(keyScaleOffsets.map((off) => (keyRootPc + off) % 12));

  const chordRootPc = chord.root_pitch_class;
  const chordOffsets = chord.chord_offsets;
  const chordThirdPc = (chordRootPc + (chordOffsets[1] ?? 4)) % 12;
  const chordFifthPc = (chordRootPc + (chordOffsets[2] ?? 7)) % 12;
  const chordSeventhPc = chordOffsets.length > 3 ? (chordRootPc + chordOffsets[3]) % 12 : -1;

  for (let s = 1; s <= 6; s++) {
    const openMidi = state.currentTuning[s - 1];

    for (let f = 0; f <= FRET_COUNT; f++) {
      const cell = document.querySelector(`.fret-cell[data-string="${s}"][data-fret="${f}"]`);
      if (!cell) continue;
      cell.innerHTML = "";

      const noteMidi = openMidi + f;
      const pc = ((noteMidi % 12) + 12) % 12;
      const noteName = NOTE_NAMES[pc];
      const isKeyNote = keyPcs.has(pc);
      const isChordRoot = pc === chordRootPc;
      const isChordThird = pc === chordThirdPc;
      const isChordFifth = pc === chordFifthPc;
      const isChordSeventh = pc === chordSeventhPc;
      const isChordTone = isChordRoot || isChordThird || isChordFifth || isChordSeventh;

      const marker = document.createElement("div");
      marker.className = "note-marker";
      marker.dataset.string = String(s);
      marker.dataset.fret = String(f);
      marker.dataset.midi = String(noteMidi);
      marker.dataset.note = noteName;
      marker.dataset.pc = String(pc);
      marker.dataset.inScale = String(isKeyNote);
      marker.dataset.isRoot = String(isChordRoot);
      marker.textContent = noteName;

      if (isChordRoot) {
        marker.classList.add("is-root");
      } else if (isChordThird) {
        marker.classList.add("chord-3rd");
      } else if (isChordFifth) {
        marker.classList.add("chord-5th");
      } else if (isChordSeventh) {
        marker.classList.add("chord-7th");
      } else if (isKeyNote) {
        marker.classList.add("in-scale");
      } else {
        marker.classList.add("dimmed");
      }

      cell.appendChild(marker);
    }
  }
}

function render(): void {
  if (state.viewMode === "scale") {
    renderScaleView();
  } else {
    renderChordVoicing();
  }
}

// =============================================================================
// Interactive Tooltip
// =============================================================================

function setupTooltipEvents(): void {
  const tooltip = document.getElementById("fret-tooltip");
  const fretboard = document.getElementById("fretboard");
  if (!tooltip || !fretboard) return;

  fretboard.addEventListener("mouseover", (e) => {
    const target = e.target as HTMLElement;
    const marker = target.closest(".note-marker") as HTMLElement | null;
    if (!marker) {
      tooltip.style.display = "none";
      return;
    }

    const stringIdx = marker.dataset.string ?? "1";
    const fretNum = marker.dataset.fret ?? "0";
    const midi = marker.dataset.midi ?? "";
    const noteName = marker.dataset.note ?? "";
    const isRoot = marker.dataset.isRoot === "true";
    const degree = marker.dataset.degree ?? "0";

    const titleEl = document.getElementById("tooltip-title");
    const stringEl = document.getElementById("tooltip-string");
    const fretEl = document.getElementById("tooltip-fret");
    const midiEl = document.getElementById("tooltip-midi");
    const degreeEl = document.getElementById("tooltip-degree");

    if (titleEl) {
      if (state.viewMode === "chord") {
        const chord = state.diatonicChords[state.selectedChordIndex];
        titleEl.textContent = `${noteName} ${isRoot ? `(Root of ${chord?.roman_numeral || ""})` : ""}`;
      } else {
        titleEl.textContent = `${noteName} ${isRoot ? "(Root / Tonic)" : ""}`;
      }
    }

    if (stringEl) {
      const stdName = STANDARD_TUNING[parseInt(stringIdx, 10) - 1]?.name || "";
      const curMidi = state.currentTuning[parseInt(stringIdx, 10) - 1];
      const curName = midiToNoteName(curMidi);
      stringEl.textContent = `String ${stringIdx} (${curName} / Std: ${stdName})`;
    }

    if (fretEl) {
      fretEl.textContent = fretNum === "0" ? "Nut / Open (Fret 0)" : `Fret ${fretNum}`;
    }

    if (midiEl) {
      midiEl.textContent = `${midi} (Pitch Class ${marker.dataset.pc})`;
    }

    if (degreeEl) {
      if (state.viewMode === "chord") {
        const chord = state.diatonicChords[state.selectedChordIndex];
        degreeEl.textContent = chord ? `Harmonic Member: ${chord.chord_name}` : "Key Tone";
      } else {
        degreeEl.textContent = degree !== "0" ? `Degree ${degree}` : "Chromatic (Out of Scale)";
      }
    }

    tooltip.style.display = "block";
  });

  fretboard.addEventListener("mousemove", (e) => {
    tooltip.style.left = `${e.clientX + 16}px`;
    tooltip.style.top = `${e.clientY + 16}px`;
  });

  fretboard.addEventListener("mouseleave", () => {
    tooltip.style.display = "none";
  });
}
