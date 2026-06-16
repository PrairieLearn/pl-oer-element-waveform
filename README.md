# PrairieLearn OER Element: Waveform

This element was developed as a PrairieLearn OER element. Please carefully test
the element and understand its features and limitations before deploying it in a
course. It is provided as-is and not officially maintained by PrairieLearn, so
we can only provide limited support for any issues you encounter!

If you like this element, you can use it in your own PrairieLearn course by
copying the contents of the `elements` folder into your own course repository.
After syncing, the element can be used as illustrated by the example question
that is also contained in this repository.


## `pl-waveform` element

This element renders digital timing diagrams using
[WaveDrom](https://wavedrom.com/) and allows students to fill in auto-gradable signals by toggling
values via click or by entering their values.

### Example

```html
<pl-question-panel>
  <p>Fill in the value of <code>Q</code> after each positive clock edge.</p>
</pl-question-panel>

<pl-waveform answers-name="timing" hscale="1.5"></pl-waveform>
```

```python
import random


def generate(data):
    d_values = random.choices(["0", "1"], k=12)
    q_answers = []

    for i in range(1, len(d_values)):
        if i % 2 == 1 and i != len(d_values) - 1:
            q_answers.append(d_values[i])

    data["params"]["signals"] = [
        {"name": "clk", "wave": "lP....", "editable": False},
        {"name": "D", "values": d_values, "period": 0.5, "editable": False},
        {
            "name": "Q",
            "initial": "0",
            "editable": True,
            "correct_answers": q_answers,
        },
    ]
```

### Element Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `answers-name` | string (required) | Unique identifier for the element. Student answer keys are namespaced with this value. |
| `weight` | integer (default: `1`) | Weight applied to each editable cell during grading. |
| `hscale` | float (default: `1.5`) | WaveDrom horizontal scale factor. If omitted, `data["params"]["hscale"]` can also set it. |
| `signals-param` | string (default: `"signals"`) | Key in `data["params"]` containing the signal list. |
| `feedback` | string (default: `"cell"`) | Feedback granularity: `"cell"`, `"row"`, or `"table"`. |
| `input-mode` | string (default: `"toggle"`) | Question-panel input UI: `"toggle"` or `"text"`. |
| `label` | string (optional) | Label shown in the submission card header. |
| `show-score` | boolean (default: `true`) | Whether to show score overlays in the question panel after submission. |

### Signal Data

Signal definitions are stored in `data["params"][signals_param]` as a list of
dictionaries. Each signal needs a `name` and an `editable` flag.

For most single-bit questions, use the shorthand format:

```python
data["params"]["signals"] = [
    {"name": "clk", "wave": "lP....", "editable": False},
    {"name": "D", "values": ["0", "1", "1", "0"], "period": 0.5, "editable": False},
    {"name": "Q", "initial": "0", "correct_answers": ["1", "0"], "editable": True},
]
```

For advanced WaveDrom rows, use raw `wave` values. Editable raw rows must also
provide `correct_wave` and `correct_answers`:

```python
data["params"]["signals"] = [
    {"name": "clk", "wave": "lP....", "editable": False},
    {"name": "D", "wave": "01.0", "period": 0.5, "editable": False},
    {
        "name": "Q",
        "wave": "0xx",
        "correct_wave": "010",
        "correct_answers": ["1", "0"],
        "editable": True,
    },
]
```

Common signal fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Signal label displayed in the diagram. |
| `wave` | string | Raw WaveDrom wave encoding. |
| `values` | list of strings | Shorthand for non-editable single-bit rows. |
| `initial` | string | Initial value for editable shorthand rows. |
| `correct_answers` | list of strings | Correct values for editable cells. |
| `correct_wave` | string | Raw WaveDrom answer waveform for editable raw rows. |
| `period` | float | WaveDrom period multiplier; `0.5` creates two cells per clock period. |
| `data` | list | WaveDrom labels for bus rows. |
| `allowed_values` | list of strings | Allowed student values. Defaults to `["0", "1"]`, or `["0", "1", "x"]` when an answer includes `x`. Non-binary lists such as hexadecimal digits are supported. |
| `editable` | boolean | Whether students answer this row. |

Do not mix raw `wave` authoring with shorthand fields (`values` or `initial`) on
the same signal.

### Input Modes and Feedback

`input-mode="toggle"` lets students click editable cells to cycle through the
signal's `allowed_values`. This is the default and works for binary rows with a
fixed initial value, as well as non-binary rows such as hexadecimal bus values.

`input-mode="text"` overlays text boxes on editable cells. Use it when typed
answers are clearer, such as dense sub-cycle diagrams or custom value sets.

The `feedback` attribute controls post-submission detail:

| Value | Description |
|-------|-------------|
| `"cell"` | Per-cell green/red overlays and detailed submitted-vs-expected feedback. |
| `"row"` | Per-row correctness highlighting and row score summaries. |
| `"table"` | Overall score summary only. |

### Wave Encoding

The `wave` field uses WaveDrom syntax. Common characters include:

| Character | Meaning |
|-----------|---------|
| `0` | Logic low |
| `1` | Logic high |
| `.` | Hold previous value |
| `x` | Unknown or editable placeholder |
| `l`, `h` | Clock low/high |
| `P`, `N` | Positive/negative clock edge |
| `=` | Bus value, paired with the `data` field |

See the [WaveDrom tutorial](https://wavedrom.com/tutorial.html) for the full
wave syntax.
