# PrairieLearn Element: pl-waveform

This element renders interactive digital timing diagrams using [WaveDrom](https://wavedrom.com/) and supports per-cell grading of student responses. By default, editable signals are drawn as a custom click-to-render waveform editor layered on top of the static WaveDrom diagram, so students update the signal trace itself instead of filling in a separate overlay control.

## Usage

```html
<pl-waveform answers-name="timing" hscale="1.5"></pl-waveform>
```

Signal data is passed from `server.py` via `data["params"]["signals"]`. The element handles rendering, input collection, grading feedback, and displaying the correct answer automatically.

### Minimal question example

**`question.html`**

```html
<pl-question-panel>
    <p>Fill in the value of <code>Q</code> after each positive clock edge.</p>
</pl-question-panel>

<pl-waveform answers-name="timing" hscale="1.5"></pl-waveform>
```

**`server.py`**

```python
import random

def generate(data):
    wire_val = ["0", "1"]
    ITERS = 12
    D_vals = random.choices(wire_val, k=ITERS)

    # Simulate D flip-flop: Q captures D on positive clock edge
    Q_by_cycle = []
    for i in range(1, ITERS):
        if (i % 2) == 1 and i != ITERS - 1:
            Q_by_cycle.append(D_vals[i])

    data["params"]["signals"] = [
        {"name": "clk", "wave": "lP....", "editable": False},
        {"name": "D", "values": D_vals, "period": 0.5, "editable": False},
        {
            "name": "Q",
            "initial": "0",
            "editable": True,
            "correct_answers": Q_by_cycle,
        },
    ]
    data["params"]["hscale"] = 1.5
    return data
```

### Full element example

```html
<pl-waveform
    answers-name="timing"
    hscale="1.5"
    feedback="cell"
    input-mode="toggle"
    signals-param="signals"
    label="Part 1"
    show-score="true">
</pl-waveform>
```

## Authoring Styles

`pl-waveform` supports two compatible ways to describe signals:

- Raw WaveDrom form: you provide `wave` and, for editable rows, `correct_wave`.
- Shorthand form: you provide higher-level `values` or `initial + correct_answers`, and the element derives the WaveDrom strings for you.

The shorthand API is additive and backward-compatible. Existing authored questions that already provide raw `wave` data continue to work unchanged.

### Recommended shorthand

```python
data["params"]["signals"] = [
    {"name": "clk", "wave": "lP....", "editable": False},
    {"name": "D", "values": ["0", "1", "1", "0", "0", "1"], "period": 0.5, "editable": False},
    {"name": "Q", "initial": "0", "correct_answers": ["1", "1", "0"], "editable": True},
]
```

### Equivalent raw WaveDrom form

```python
data["params"]["signals"] = [
    {"name": "clk", "wave": "lP....", "editable": False},
    {"name": "D", "wave": "01.0.1", "period": 0.5, "editable": False},
    {
        "name": "Q",
        "wave": "0xxx",
        "correct_wave": "01.0",
        "editable": True,
        "correct_answers": ["1", "1", "0"],
    },
]
```

Use the shorthand API for ordinary single-bit rows. Use raw `wave` authoring when you need clocks, bus rows, or advanced WaveDrom-specific shapes.

## Element Attributes

| Attribute       | Type                       | Description                                                              |
| --------------- | -------------------------- | ------------------------------------------------------------------------ |
| `answers-name`  | string (required)          | Unique identifier for the element. Used to namespace all answer keys.    |
| `weight`        | integer (default: `1`)     | Weight of this element's score relative to other elements in a question. |
| `hscale`        | float (default: `1.5`)     | WaveDrom horizontal scale factor. Can also be set via `data["params"]["hscale"]` in `server.py`. The attribute takes precedence. |
| `signals-param` | string (default: `"signals"`) | Key in `data["params"]` where the signal list is stored.              |
| `feedback`      | string (default: `"cell"`) | Controls grading feedback granularity after submission. See feedback levels below. |
| `input-mode`    | string (default: `"toggle"`) | Question-panel input UI. Use `"toggle"` for the rendered waveform editor or `"text"` to keep the legacy text-entry overlay. |
| `label`         | string (optional)          | Human-readable label for the submission card header. No label is shown if the attribute is omitted. |
| `show-score`    | boolean (default: `true`) | Whether to show post-submit score overlays on the question panel. |

## Feedback Levels

The `feedback` attribute controls how much detail students see after grading:

| Value | What students see |
|-------|-------------------|
| `"cell"` | Per-cell detail: green/red overlays on each waveform cycle, plus a table showing submitted vs expected values for incorrect cells. |
| `"row"` | Per-signal detail: each editable signal row is highlighted green (all correct) or red (has errors), with a score like "3/5 correct" per signal. |
| `"table"` | Overall only: a single summary text showing total correct out of total cells (e.g. "7/10 correct (70%)"). No per-cell or per-signal breakdown. |

All three modes display the student's submitted waveform inside a labeled card. The card header shows the `label` (when provided) and a color-coded score badge (green 100%, yellow for partial credit, red 0%), so students can identify which sub-question each result belongs to when multiple `pl-waveform` elements appear on the same page.

## Input Validation

Accepted student values are controlled per editable signal by `allowed_values`.
Single-bit rows default to:
- `0` — Logic low
- `1` — Logic high
- `x` — Unknown / don't care, when any correct answer is `x`

Text-mode rows may use other values, such as one-digit hexadecimal answers
`["0", "1", ..., "F"]`. Submissions are compared case-insensitively and stored
using the canonical spelling from `allowed_values`.

Blank cells are treated as unanswered, not as parse errors. In `input-mode="text"`, invalid values are highlighted with a warning/error state and a parse-error badge appears on the waveform. In `input-mode="toggle"`, students can only cycle through that signal's `allowed_values`, so invalid values cannot be introduced from the question-panel UI. Invalid submitted values are not counted as answered.

## Allowed Values And Toggle Cycles

Each editable signal may define:

```python
"allowed_values": ["0", "1", "x"]
```

Rules:

- If `allowed_values` is omitted, the element derives it automatically.
- Binary rows default to `["0", "1"]`.
- Rows whose correct answers include `x` default to `["0", "1", "x"]`.
- `allowed_values` must contain unique non-empty string values, compared case-insensitively.
This list drives both validation and interaction:

- In `input-mode="text"`, submitted values must belong to `allowed_values`.
- In `input-mode="toggle"`, a fresh cell starts from `?` and then cycles through all entries in `allowed_values` in order.
  After a cell has been interacted with, it remains in value-only cycling (does not return to `?`).
  Toggle mode supports any `allowed_values` list, including non-binary sets such as hex digits.

Examples:

- `["0", "1"]` gives `? -> 0 -> 1`, then `0 <-> 1` on later clicks for that touched cell
- `["0", "1", "x"]` gives `? -> 0 -> 1 -> x`, then value-only cycling for that touched cell
- `["0", "1", ..., "F"]` cycles through all 16 hex values in `input-mode="toggle"` or accepts typed input in `input-mode="text"`

## Signal Object Format

Each signal in the `data["params"]["signals"]` list is a dictionary with the following fields:

| Field             | Type          | Required | Description                                                                                   |
| ----------------- | ------------- | -------- | --------------------------------------------------------------------------------------------- |
| `name`            | string        | yes      | Signal label displayed on the diagram (e.g., `"clk"`, `"D"`, `"Q"`).                         |
| `wave`            | string        | raw mode | WaveDrom wave encoding. Use `x` for editable positions. See wave encoding below.              |
| `values`          | list of str   | shorthand non-editable | Author-friendly shorthand for single-bit non-editable rows. The element converts this to `wave`. |
| `initial`         | string        | shorthand editable | Initial single-bit value for an editable shorthand row. Combined with `correct_answers` to derive `wave` and `correct_wave`. |
| `editable`        | boolean       | yes      | Whether students can input values for this signal.                                            |
| `period`          | float         | no       | WaveDrom period multiplier. Use `0.5` for signals that change twice per clock cycle.          |
| `data`            | list          | no       | WaveDrom data labels for bus signals (e.g., `["0xA", "0xB"]`).                                |
| `correct_wave`    | string        | raw editable | WaveDrom-encoded correct wave string, shown in the answer panel. Required for raw editable rows. |
| `correct_answers` | list of str   | editable | Correct value for each editable position. Values must belong to `allowed_values` when it is provided. Required if `editable: True`. |
| `allowed_values`  | list of str   | no       | Allowed student values for each editable position. Defaults to `["0", "1"]` for binary rows and `["0", "1", "x"]` when the signal's correct answers include `x`. Both text and toggle mode support arbitrary value lists, including hex digits. |

### Shorthand rules

- Non-editable shorthand rows use `values` and must stay single-bit.
- Editable shorthand rows use `initial` plus `correct_answers` and must stay single-bit.
- Raw rows with `wave` still work exactly as before.
- Do not mix raw and shorthand fields on the same signal. Use either `wave` or the shorthand API for that row.
- Bus rows and advanced WaveDrom constructs should keep using raw `wave` plus optional `data`. Editable bus rows use `wave` placeholders such as `"xxxx"` (all editable) or `"=xxx"` (fixed initial + editable), `correct_answers`, `correct_wave` such as `"===="`, and an explicit `allowed_values` list. Both `input-mode="text"` and `input-mode="toggle"` are supported for bus rows.

### Normalization behavior

Internally, the element normalizes shorthand rows before rendering:

- `values` becomes a compressed WaveDrom `wave`
- `initial + correct_answers` becomes:
  - student-facing `wave = initial + "x" * len(correct_answers)`
  - derived `correct_wave`
- Raw `wave` rows bypass shorthand normalization unchanged

This means shorthand and raw authoring both end up using the same grading and rendering pipeline.

## Wave Encoding Reference

The `wave` field uses WaveDrom's character encoding:

| Character | Meaning                                 |
| --------- | --------------------------------------- |
| `0`       | Logic low                               |
| `1`       | Logic high                              |
| `.`       | Hold previous value (no change)         |
| `x`       | Unknown / editable placeholder (hatched)|
| `l`       | Low for clock signal                    |
| `h`       | High for clock signal                   |
| `P`       | Positive clock edge                     |
| `N`       | Negative clock edge                     |
| `=`       | Bus value (paired with `data` field)    |

## How It Works

### Question Panel

The element renders a WaveDrom SVG diagram and measures the editable row geometry from that SVG. In the default `input-mode="toggle"`, transparent hit targets sit over the editable cells. A fresh cell starts at `?`, then cycles through that signal's allowed values. After first interaction, that touched cell stays in value-only cycling and does not return to `?`. The visual hierarchy is waveform first, interaction highlight second, and grading accents third: unanswered cells stay neutral, hover/focus uses a blue affordance, and graded states use lighter green/red tints so the trace remains the main thing students read. Hidden form inputs preserve the existing PrairieLearn answer-key contract behind the scenes.

Both input modes support sub-cycle placement through the signal `period`. In `input-mode="text"`, transparent text inputs are positioned from the real editable slot locations in the waveform, so you can show multiple answer boxes inside a single clock period. Text input also updates the WaveDrom JSON; for editable bus rows, adjacent equal entered values are rendered as a continuous segment (`.` continuation) and transitions render as new bus boundaries (`=`). In `input-mode="toggle"`, the hit targets use the same measured slot geometry, so sub-cycle interactive rows such as `period="0.5"` also redraw correctly in place. Both modes accept the same submitted values and use the same grading pipeline. In `feedback="cell"` mode, the question panel adds compact corner badges for graded interactive cells; unanswered cells get their own neutral badge state instead of being styled the same way as a wrong answer. In `feedback="row"` mode, interactive rows use a row tint plus a right-side score pill rather than per-cell badges.

`input-mode="toggle"` constraints:

- Binary rows must start with a fixed `0` or `1` initial value followed only by editable `x` cells.
- Bus/hex rows must start with `=` (fixed initial bus value) or `x` (all editable), followed only by `x` cells.
- `allowed_values` controls the cycle order. Any non-empty list is supported, including hex digits — each click advances to the next value in the list.

### Shared geometry contract

Editable cell metadata tracks both:

- `editable_index`: answer-key order
- `abs_index`: actual position in the authored waveform string
- `period`: slot-width multiplier relative to one tick

The client uses `abs_index` together with `period` to place:

- text inputs
- rendered toggle hit regions
- question-panel score badges
- submission feedback overlays
- answer diff markers

That geometry model is what allows multiple editable cells inside a single clock period.

### Rendered toggle row model

For `input-mode="toggle"`, the server emits a per-row model that includes:

- `signal_name`
- `wave_length`
- `initial_value`
- `allowed_values`
- `period`
- `cells[]`, where each cell includes `abs_index`, editability, answer key, current value, and accessible label

The client hydrates that model from hidden inputs and redraws only the affected row after each interaction instead of rerunning WaveDrom.

### Visual feedback contract

The question-panel visual hierarchy is:

- waveform first
- interaction affordance second
- grading accents third

Current behavior:

- unanswered cells use a neutral appearance
- hover and focus use blue interaction accents
- `feedback="cell"` uses light per-cell grading tint plus compact corner badges
- unanswered graded cells get their own neutral badge state rather than being shown as wrong answers
- `feedback="row"` suppresses per-cell badges and uses a row tint plus a right-side score pill
- `feedback="table"` keeps question-panel detail minimal and shows only the overall score overlay when enabled

### Grading

Grading is per-cell with partial credit. Each editable cell is scored independently:

- Answer keys are namespaced as `{answers-name}_{signal-name}_{cycle-number}` (e.g., `timing_Q_1`, `timing_Q_2`)
- Comparison is case-insensitive string matching
- Overall score = (number of correct cells) / (total editable cells)
- `show-score="false"` suppresses post-submit score overlays on the question panel while leaving submission and answer rendering unchanged

### Submission Panel

After submission, each `pl-waveform` element renders inside a labeled card showing:

- **Header**: the `label` (if provided) and overall score badge (e.g., "5 / 7 correct")
- **Waveform**: the student's submitted values rendered as a WaveDrom diagram
- **Feedback detail**: depends on the `feedback` attribute (cell table, row badges, or summary bar)

This card-based layout makes it easy to distinguish results when multiple waveform questions appear on the same page.

### Answer Panel

Displays the complete correct waveform using the `correct_wave` field from each editable signal. Where the student's answer differs, a "yours: X" label is overlaid on the correct waveform so they can see exactly where they went wrong.

## Compatibility Notes

- Existing raw WaveDrom-authored questions continue to work.
- Existing text-input workflows continue to work via `input-mode="text"`.
- The submission panel and answer panel still use WaveDrom output; only question-panel interactivity differs by input mode.
- The demo question under `questions/waveforms/pl_waveform_demo/` is the canonical showcase for:
  - binary toggle rows
  - row and table feedback
  - sub-cycle text rows
  - sub-cycle toggle rows
  - `x`-capable text rows
  - hex bus toggle rows (Part 10)

## Dependencies

The WaveDrom library is **bundled with the element** — no course-level script imports are needed. The following files are included in `elements/pl-waveform/wavedrom/`:

- `default.js` — WaveDrom default skin/theme
- `wavedrom.min.js` — WaveDrom rendering engine

These are declared as `elementScripts` in `info.json` and loaded automatically when the element is used.

## File Structure

```
elements/pl-waveform/
  info.json             — Element metadata and dependency declarations
  pl-waveform.py        — Server-side controller (prepare/render/parse/grade)
  pl-waveform.js        — Client-side SVG measurement, rendered toggle editor, input positioning, and feedback overlays
  pl-waveform.mustache  — HTML templates for question/submission/answer panels
  pl-waveform.css       — Styling for text inputs, rendered interactive rows, feedback cards, and layout
  wavedrom/             — Bundled WaveDrom library (self-contained, no course-level deps)
    default.js
    wavedrom.min.js
  README.md             — This file
  CHECKPOINTS.md        — Project milestone history
```
