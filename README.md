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

This element renders digital timing diagrams using the
[WaveDrom library](https://wavedrom.com/) and allows students to fill in auto-gradable signals by toggling
values via click or by entering their values.

<img src="images/sampleWaveform.png" width="500">

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
| `hscale` | float (default: `1.5`) | Height of each signal row, represented as a WaveDrom horizontal scale factor. |
| `signals-param` | string (default: `"signals"`) | Key in `data["params"]` containing the signal data as a list (see below). |
| `feedback` | string (default: `"cell"`) | Granularity for feedback given to students: `"cell"`, `"row"`, or `"table"`. |
| `input-mode` | string (default: `"toggle"`) | Input mechanism used for student submissions: `"toggle"` or `"text"`. |
| `label` | string (optional) | Label shown in the submission card header. |
| `show-score` | boolean (default: `true`) | Whether to show score overlays in the question panel after submission. |

### Signal Data

Signal definitions are stored in `data["params"]` in the key that matches the `signals-param` attribute (see above). Each signal row is a dictionary with at minimum a unique `name` and an `"editable"` key. Signals with `"editable"` set to `True` are filled in by students, those with it set to `False` are pre-rendered rows. The remaining keys are different for editable and non-editable rows.

#### Editable Signals

Editable signals require a `"correct_answers"` key that is used for auto-grading and generating the sample solution in the answer panel. Correct answers can be provided as an array of integers or strings (the latter also supports `"x"`), or as a WaveDrom string (with `"."` optionally representing a repeat of the previous signal).

```python
data["params"]["signals"] = [
    {"name": "A", "correct_answers": ["0", "0", "1", "1"], "editable": True},
    {"name": "B", "correct_answers": [0, 0, 1, 1], "editable": True},
    {"name": "C", "correct_answers": "0.1.", "editable": True},
]
```

Editable signals can be assigned a `prefix` and/or a `suffix` that are pre-rendered and not editable. Note that the size of each row (length of `prefix` + `correct_answers` + `suffix`) must match.

```python
data["params"]["signals"] = [
    {"name": "A", "correct_answers": "0.1.", "prefix": "11", "editable": True},
    {"name": "B", "correct_answers": "1.0.", "suffix": "11", "editable": True},
    {"name": "C", "correct_answers": "1.0.1.", "editable": True},
]
```

#### Pre-rendered Signals

Non-editable signals that are rendered for reference can be defined via the `wave` key. It supports the same input formats as the `correct_answers` key, but also some special WaveDrom syntax for clock and bus values (see below). In addition, the period of a non-editable wave can be adjusted via `period` (default is `1`). As for editable signals, the total size of each row (after `period` scaling must match).

```python
data["params"]["signals"] = [
    {"name": "clk", "wave": "lP......", "editable": False},
    {"name": "D", "wave": "01.0", "period": 0.5, "editable": False},
]
```

#### Non-binary Signals

The `allowed_values` key enables student inputs beyond binary signals. By default, students can only enter (or toggle between) 0 and 1 (and `x`, if present in the `correct_answers` string). By setting `allowed_values`, non-binary signals like ternary or hexadecimal can also be supported. You can use `"hex"` as a special string instead of listing all values from 0 to F.

```python
data["params"]["signals"] = [
    {"name": "hex", "correct_answers": "2102", "allowed_values": "01234" "editable": True},
    {"name": "hex", "correct_answers": "ABC123", "allowed_values": "hex" "editable": True},
]
```

Note that pre-rendered signals support hexadecimal values, but no custom `allowed_values` are not supported in pre-rendered signals as this conflicts with WaveDrom's special syntax (see below). To encode these values, we recommend using the bus syntax.


### Input Modes and Feedback

The `input-mode` attribute determines whether students input answers as text or by clicking on editable cells to switch the value (or cycle through the signal's `allowed_values`, if applicable). The default is `"toggle"`, but alternatively, the `"text"` setting overlays text boxes on editable cells. We recommend the text input mode for large sets of allowed values (where toggling would be tedious) or for dense plots where each cell is small and clicking it might require some dexterity.

The `feedback` attribute controls the granularity of post-submission feedback that students receive. We recommend giving less fine-grained feedback when allowing multiple submissions to avoid brute forcing.

| Value | Description |
|-------|-------------|
| `"cell"` | Per-cell green/red overlays and detailed submitted-vs-expected feedback. |
| `"row"` | Per-row correctness highlighting and row score summaries. |
| `"table"` | Overall score summary only. |


### Wave Encoding

The `wave` key supports the following WaveDrom syntax:

| Character | Meaning |
|-----------|---------|
| `0` | Low state |
| `1` | High state |
| `.` | Hold previous value |
| `x` | Unknown |
| `l`, `h` | Clock low/high |
| `P`, `N` | Positive/negative clock edge |
| `=` | Bus value (see below) |

For bus values, provide an additional `data` key that contains a list of strings with the bus labels. Note that `.` means that the previous bus is continued while `=` starts a new bus, so the number of `=`s should match the number of items in `data`.

```python
data["params"]["signals"] = [
    {"name": "bus", "wave": "=.=", "data": ["first", "second"] "editable": False},
]
```

Other `wave` [syntax](https://wavedrom.com/tutorial.html) is also supported, but keys like `phase`, `node` or `edge` are currently not. If you are interested in support for these keys, please open an issue in the element repository - we might be able to add support!
