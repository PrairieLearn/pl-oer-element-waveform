import json
from typing import Any

import lxml.html
import chevron
import prairielearn as pl


WEIGHT_DEFAULT = 1
HSCALE_DEFAULT = 1.5
SIGNALS_PARAM_DEFAULT = "signals"
FEEDBACK_DEFAULT = "cell"
FEEDBACK_OPTIONS = {"cell", "row", "element", "none"}
INPUT_MODE_DEFAULT = "toggle"
INPUT_MODE_OPTIONS = {"toggle", "text"}
VALID_VALUES = {"0", "1", "x", "z"}
DEFAULT_BINARY_ALLOWED_VALUES = ["0", "1"]
HEX_ALLOWED_VALUES = list("0123456789ABCDEF")
BUS_WAVE_CHARS = set("=23456789")


def _name_text(value: Any) -> str:
    """Return the visible text represented by a WaveDrom name value."""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return ""
    if isinstance(value, list):
        children = value
        if value and isinstance(value[0], str):
            children = value[1:]
        if children and isinstance(children[0], dict):
            children = children[1:]
        return "".join(_name_text(child) for child in children)
    return ""


def _signal_key_from_name(name: Any) -> str:
    """Build a stable answer-key component from a signal name."""
    if isinstance(name, str):
        return name
    text = _name_text(name).strip()
    key = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text)
    return "_".join(part for part in key.split("_") if part)


def _get_signals(element: Any, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the normalized signal list from the PrairieLearn params."""
    signals_param = pl.get_string_attrib(
        element, "signals-param", SIGNALS_PARAM_DEFAULT
    )
    return _normalize_signals(data["params"].get(signals_param, []))


def _normalize_value(val: Any) -> str | None:
    """Normalize a submitted or authored value for comparison."""
    if val is None:
        return None
    normalized = str(val).strip().lower()
    if normalized == "":
        return None
    return normalized


def _display_value(val: Any) -> str | None:
    """Return the trimmed display form for a value when one exists."""
    if val is None:
        return None
    displayed = str(val).strip()
    if displayed == "":
        return None
    return displayed


def _canonical_value(val: Any, allowed_values: list[str]) -> str | None:
    """Return the display value matching a normalized value."""
    normalized = _normalize_value(val)
    if normalized is None:
        return None
    for allowed in allowed_values:
        if _normalize_value(allowed) == normalized:
            return allowed
    return None


def _normalize_values(
    values: Any,
    sig_name: str,
    field_name: str,
) -> list[str]:
    """Normalize an authored values list into display strings."""
    if not isinstance(values, list):
        raise Exception(
            f"pl-waveform: signal '{sig_name}' must define '{field_name}' as a list"
        )

    if len(values) == 0:
        raise Exception(
            f"pl-waveform: signal '{sig_name}' must define '{field_name}' as non-empty"
        )

    normalized_values = []
    for idx, value in enumerate(values, start=1):
        if not isinstance(value, str | int):
            raise Exception(
                f"pl-waveform: signal '{sig_name}' has invalid {field_name} value at position {idx}; "
                "expected a string or integer"
            )
        if isinstance(value, int) and value not in (0, 1):
            raise Exception(
                f"pl-waveform: signal '{sig_name}' has invalid integer {field_name} value at position {idx}; "
                "only integer 0 and 1 are supported; use a string for non-binary values"
            )
        displayed = _display_value(value)
        if displayed is None:
            raise Exception(
                f"pl-waveform: signal '{sig_name}' has blank {field_name} value at position {idx}"
            )
        normalized_values.append(displayed)

    return normalized_values


def _encode_values(values: list[str], force_bus: bool = False) -> tuple[str, list[str]]:
    """Convert display values into WaveDrom wave and data fields."""
    wave = []
    data = []
    previous: str | None = None

    for value in values:
        normalized = _normalize_value(value)
        encoded = "=" if force_bus else normalized if normalized in VALID_VALUES else "="
        if encoded == previous or (encoded == "=" and value == previous):
            wave.append(".")
        else:
            wave.append(encoded)
            if encoded == "=":
                data.append(value)
                previous = value
            else:
                previous = encoded

    return "".join(wave), data


def _wave_state(char: str, data_value: str | None = None) -> tuple[str, str] | None:
    """Return the hold-comparable state represented by one wave character."""
    if char in VALID_VALUES:
        return ("digital", char)
    if char in BUS_WAVE_CHARS and data_value is not None:
        return ("bus", data_value)
    return None


def _normalize_wave_segment(
    sig: dict[str, Any],
    sig_name: str,
    wave_field: str,
    data_field: str,
    values_field: str,
    *,
    required: bool = False,
    allow_wave: bool = True,
) -> dict[str, Any]:
    """Normalize one wave/data or values segment."""
    has_wave = wave_field in sig
    has_data = data_field in sig
    has_values = values_field in sig

    if has_values and (has_wave or has_data):
        raise Exception(
            f"pl-waveform: signal '{sig_name}' cannot mix '{values_field}' with '{wave_field}'/'{data_field}'"
        )
    if has_data and not has_wave:
        raise Exception(
            f"pl-waveform: signal '{sig_name}' defines '{data_field}' without '{wave_field}'"
        )
    if has_wave and not allow_wave:
        raise Exception(
            f"pl-waveform: editable signal '{sig_name}' cannot define '{wave_field}'; use '{values_field}'"
        )
    if not has_values and not has_wave:
        if required:
            raise Exception(
                f"pl-waveform: signal '{sig_name}' must define '{values_field}'"
                + (f" or '{wave_field}'" if allow_wave else "")
            )
        return {"wave": "", "data": [], "values": []}

    if has_values:
        values = _normalize_values(sig[values_field], sig_name, values_field)
        wave, data = _encode_values(values)
        return {"wave": wave, "data": data, "values": values, "from_values": True}

    raw_wave = sig[wave_field]
    if not isinstance(raw_wave, str) or raw_wave == "":
        raise Exception(
            f"pl-waveform: signal '{sig_name}' must define '{wave_field}' as a non-empty string"
        )
    data = []
    if sig.get(data_field) is not None:
        data = _normalize_values(sig.get(data_field), sig_name, data_field)
    expected_data_count = sum(1 for char in raw_wave if char in BUS_WAVE_CHARS)
    if data and len(data) != expected_data_count:
        raise Exception(
            f"pl-waveform: signal '{sig_name}' has {len(data)} entries in '{data_field}' "
            f"but wave expects {expected_data_count}"
        )
    return {"wave": raw_wave, "data": data, "values": [], "from_values": False}


def _encode_value_segments_as_bus(
    segments: tuple[dict[str, Any], ...],
    force_bus: bool,
) -> tuple[dict[str, Any], ...]:
    """Re-encode value-authored segments when the whole row is bus-rendered."""
    encoded_segments = []
    for segment in segments:
        if segment.get("from_values"):
            wave, data = _encode_values(segment["values"], force_bus=force_bus)
            encoded_segments.append({**segment, "wave": wave, "data": data})
        else:
            encoded_segments.append(segment)
    return tuple(encoded_segments)


def _combine_segments(*segments: dict[str, Any]) -> tuple[str, list[str]]:
    """Combine normalized wave segments into WaveDrom fields."""
    wave = []
    data = []
    previous_state = None
    for segment in segments:
        segment_data = iter(segment["data"])
        for char in segment["wave"]:
            data_value = next(segment_data) if char in BUS_WAVE_CHARS else None
            state = _wave_state(char, data_value)
            if state is not None and state == previous_state:
                wave.append(".")
                continue
            wave.append(char)
            if data_value is not None:
                data.append(data_value)
            if char != ".":
                previous_state = state
    return "".join(wave), data


def _normalize_signal(sig: Any, idx: int) -> dict[str, Any]:
    """Normalize one signal definition while preserving WaveDrom fields."""
    if not isinstance(sig, dict):
        raise Exception(f"pl-waveform: signal at index {idx} must be a dictionary")

    sig_name = sig.get("name", f"signal[{idx}]")
    if not isinstance(sig_name, (str, list)):
        raise Exception(
            f"pl-waveform: signal at index {idx} must have a string or list 'name'"
        )
    signal_key = _signal_key_from_name(sig_name)
    if not signal_key:
        raise Exception(
            f"pl-waveform: signal at index {idx} has a 'name' with no usable text"
        )
    editable = bool(sig.get("editable", False))
    normalized = {
        "name": sig_name,
        "signal_key": signal_key,
        "signal_label": _name_text(sig_name),
        "editable": editable,
    }
    if editable:
        if "period" in sig:
            normalized["period"] = sig["period"]
        if "phase" in sig:
            raise Exception(
                f"pl-waveform: editable signal '{signal_key}' cannot define 'phase'"
            )
    else:
        for field in ("period", "phase"):
            if field in sig:
                normalized[field] = sig[field]

    start = _normalize_wave_segment(
        sig,
        signal_key,
        "start_wave",
        "start_data",
        "start_values",
    )
    end = _normalize_wave_segment(
        sig,
        signal_key,
        "end_wave",
        "end_data",
        "end_values",
    )

    if editable:
        if "allowed_values" in sig:
            normalized["allowed_values"] = sig["allowed_values"]
        body = _normalize_wave_segment(
            sig,
            signal_key,
            "wave",
            "data",
            "values",
            required=True,
            allow_wave=False,
        )
        correct_answers = body["values"]
        normalized["correct_answers"] = correct_answers
        allowed_values = _get_allowed_values(normalized)
        # If any allowed or authored value is bus-like, render the whole row as
        # buses so digital-looking answers are not mixed with wire states.
        force_bus = any(_normalize_value(value) not in VALID_VALUES for value in allowed_values) or any(
            _normalize_value(value) not in VALID_VALUES
            for segment in (start, body, end)
            for value in segment["values"]
        )
        start, body, end = _encode_value_segments_as_bus((start, body, end), force_bus)
        correct_wave, correct_data = _combine_segments(start, body, end)

        normalized["correct_wave"] = correct_wave
        normalized["correct_data"] = correct_data
        normalized["is_bus"] = force_bus
        normalized["wave"] = start["wave"] + ("x" * len(correct_answers)) + end["wave"]
        if start["data"] or end["data"]:
            normalized["data"] = start["data"] + end["data"]
        else:
            normalized.pop("data", None)

        for answer_idx, value in enumerate(correct_answers, start=1):
            if _canonical_value(value, allowed_values) is None:
                raise Exception(
                    f"pl-waveform: editable signal '{signal_key}' has values entry '{value}' "
                    f"at cycle {answer_idx} that is not in allowed_values {allowed_values}"
                )
        return normalized

    body = _normalize_wave_segment(
        sig,
        signal_key,
        "wave",
        "data",
        "values",
        required=True,
    )
    force_bus = any(
        _normalize_value(value) not in VALID_VALUES
        for segment in (start, body, end)
        for value in segment["values"]
    )
    start, body, end = _encode_value_segments_as_bus((start, body, end), force_bus)
    wave, data = _combine_segments(start, body, end)
    normalized["wave"] = wave
    normalized["is_bus"] = bool(data)
    if data:
        normalized["data"] = data
    else:
        normalized.pop("data", None)
    return normalized


def _normalize_signals(signals: Any) -> Any:
    """Normalize every authored signal when the signal parameter is a list."""
    if not isinstance(signals, list):
        return signals
    return [_normalize_signal(sig, idx) for idx, sig in enumerate(signals)]


def _get_allowed_values(sig: dict[str, Any]) -> list[str]:
    """Return the canonical allowed values list for an editable signal."""
    raw_allowed_values = sig.get("allowed_values")
    inferred = raw_allowed_values is None
    if raw_allowed_values is None:
        raw_allowed_values = DEFAULT_BINARY_ALLOWED_VALUES + sig.get(
            "correct_answers", []
        )

    if isinstance(raw_allowed_values, str):
        if raw_allowed_values.strip().lower() == "hex":
            raw_allowed_values = HEX_ALLOWED_VALUES
        else:
            raise Exception(
                f"pl-waveform: editable signal '{sig['name']}' must define 'allowed_values' as a list or 'hex'"
            )

    if not isinstance(raw_allowed_values, list) or len(raw_allowed_values) == 0:
        raise Exception(
            f"pl-waveform: editable signal '{sig['name']}' must define 'allowed_values' as a non-empty list or 'hex'"
        )

    allowed_values = []
    seen = set()
    for idx, val in enumerate(raw_allowed_values, start=1):
        if not isinstance(val, str | int):
            raise Exception(
                f"pl-waveform: editable signal '{sig['name']}' has invalid allowed_values entry at position {idx}; "
                "expected a string or integer"
            )
        if isinstance(val, int) and val not in (0, 1):
            raise Exception(
                f"pl-waveform: editable signal '{sig['name']}' has invalid integer allowed_values entry at position {idx}; "
                "only integer 0 and 1 are supported; use a string for non-binary values"
            )
        displayed = _display_value(val)
        normalized = _normalize_value(displayed)
        if normalized is None:
            raise Exception(
                f"pl-waveform: editable signal '{sig['name']}' has blank allowed_values entry at position {idx}"
            )
        if normalized in seen:
            if inferred:
                continue
            else:
                raise Exception(
                    f"pl-waveform: editable signal '{sig['name']}' repeats allowed_values entry '{normalized}'"
                )
        seen.add(normalized)
        allowed_values.append(displayed)

    missing = [
        value
        for value in sig.get("correct_answers", [])
        if _canonical_value(value, allowed_values) is None
    ]
    if missing:
        raise Exception(
            f"pl-waveform: editable signal '{sig['name']}' has solution values {missing} "
            f"that are not in allowed_values {allowed_values}"
        )

    return allowed_values


def _answer_value(raw: Any, from_json: bool = True) -> str | None:
    """Decode and display a raw submitted answer value."""
    if raw is None:
        return None
    value = raw
    if from_json:
        value = pl.from_json(raw)
    return _display_value(value)


def _canonical_answer_value(
    raw: Any,
    allowed_values: list[str],
    from_json: bool = True,
) -> str | None:
    """Decode a raw answer and map it to an allowed display value."""
    return _canonical_value(_answer_value(raw, from_json=from_json), allowed_values)


def _is_invalid_submission(raw: Any, allowed_values: list[str]) -> bool:
    """Return whether a submitted value is outside the allowed values."""
    submitted = _answer_value(raw, from_json=True)
    return submitted is not None and _canonical_value(submitted, allowed_values) is None


def _invalid_value_message(allowed_values: list[str]) -> str:
    """Build feedback text for an invalid submitted value."""
    return f"Invalid value. Expected one of: {', '.join(allowed_values)}."


def _build_wavedrom(signals: list[dict[str, Any]], hscale: float) -> str:
    """Build the WaveDrom JSON payload for rendering."""
    wd_signals = []
    for sig in signals:
        s = {"name": sig["name"]}
        s["wave"] = sig["wave"]
        if "period" in sig:
            s["period"] = sig["period"]
        if "phase" in sig:
            s["phase"] = sig["phase"]
        if "data" in sig:
            s["data"] = sig["data"]
        wd_signals.append(s)

    return json.dumps(
        {
            "signal": wd_signals,
            "config": {"hscale": hscale},
            "head": {"tick": 0},
        }
    )


def _editable_cells(sig: dict[str, Any], answers_name: str) -> list[dict[str, Any]]:
    """Return the editable cell metadata for a signal."""
    cells = []
    allowed_values = _get_allowed_values(sig)
    for editable_index, abs_index in enumerate(
        [idx for idx, ch in enumerate(sig["wave"]) if ch == "x"],
        start=1,
    ):
        correct_value = _canonical_value(
            sig["correct_answers"][editable_index - 1], allowed_values
        )
        if correct_value is None:
            correct_value = _display_value(sig["correct_answers"][editable_index - 1])
        cells.append(
            {
                "editable_index": editable_index,
                "cycle_num": editable_index,
                "abs_index": abs_index,
                "key": f"{answers_name}_{sig['signal_key']}_{editable_index}",
                "correct_value": correct_value,
                "period": sig.get("period", 1),
            }
        )
    return cells


def _build_editable_bus_wave_and_data(
    wave_chars: list[str],
    fixed_data: list[str],
    cells_by_abs_index: dict[int, dict[str, Any]],
    value_by_key: dict[str, str | None],
) -> tuple[str, list[str]]:
    """Build a bus-rendered wave from editable cell values."""
    new_chars = []
    data_values = []
    previous_state = None
    fixed_data_index = 0

    for abs_index, ch in enumerate(wave_chars):
        cell = cells_by_abs_index.get(abs_index)
        if cell is not None:
            value = value_by_key.get(cell["key"])
            if value is None:
                new_chars.append("x")
                previous_state = _wave_state("x")
            else:
                state = ("bus", value)
                if state == previous_state:
                    new_chars.append(".")
                else:
                    new_chars.append("=")
                    data_values.append(value)
                previous_state = state
            continue

        if ch in BUS_WAVE_CHARS:
            if fixed_data_index < len(fixed_data):
                fixed_value = fixed_data[fixed_data_index]
                fixed_data_index += 1
                state = ("bus", fixed_value)
                if state == previous_state:
                    new_chars.append(".")
                else:
                    new_chars.append(ch)
                    data_values.append(fixed_value)
                previous_state = state
            else:
                new_chars.append(ch)
                previous_state = None
            continue

        state = _wave_state(ch)
        if state is not None and state == previous_state:
            new_chars.append(".")
        else:
            new_chars.append(ch)
        if ch != ".":
            previous_state = state

    return "".join(new_chars), data_values


def _build_value_rendered_signal(
    sig: dict[str, Any],
    answers_name: str,
    answer_values: dict[str, Any],
    from_json: bool = True,
) -> dict[str, Any]:
    """Render an editable signal using the submitted values."""
    s = dict(sig)
    allowed_values = _get_allowed_values(sig)
    wave_chars = list(sig["wave"])
    cells_by_abs_index = {
        cell["abs_index"]: cell for cell in _editable_cells(sig, answers_name)
    }

    if sig.get("is_bus"):
        value_by_key = {}
        for cell in cells_by_abs_index.values():
            value_by_key[cell["key"]] = _canonical_answer_value(
                answer_values.get(cell["key"], None),
                allowed_values,
                from_json=from_json,
            )

        wave, data_values = _build_editable_bus_wave_and_data(
            wave_chars,
            sig.get("data", []),
            cells_by_abs_index,
            value_by_key,
        )
        s["wave"] = wave
        if data_values:
            s["data"] = data_values
        else:
            s.pop("data", None)
        return s

    previous_state = None
    new_chars = []
    for abs_index, ch in enumerate(wave_chars):
        cell = cells_by_abs_index.get(abs_index)
        if cell is not None:
            val = _canonical_answer_value(
                answer_values.get(cell["key"], None),
                allowed_values,
                from_json=from_json,
            )
            if val is None:
                val = "x"
            state = _wave_state(val)
            if state is not None and state == previous_state:
                new_chars.append(".")
            else:
                new_chars.append(val)
            previous_state = state
        else:
            state = _wave_state(ch)
            if state is not None and state == previous_state:
                new_chars.append(".")
            else:
                new_chars.append(ch)
            if ch != ".":
                previous_state = state
    s["wave"] = "".join(new_chars)
    return s


def _validate_signals(signals: Any, answers_name: str) -> None:
    """Validate normalized signal rows before rendering or grading."""
    if not isinstance(signals, list):
        raise Exception(
            "pl-waveform: signals param must be a list of signal dictionaries"
        )

    seen_names = set()
    expected_duration = None
    for idx, sig in enumerate(signals):
        sig_name = sig.get("name")
        signal_key = sig["signal_key"]
        wave = sig.get("wave")
        if not sig_name or not isinstance(sig_name, (str, list)):
            raise Exception(
                f"pl-waveform: signal at index {idx} must have a string or list 'name'"
            )
        if signal_key in seen_names:
            raise Exception(
                f"pl-waveform: duplicate signal name '{signal_key}' in '{answers_name}'"
            )
        seen_names.add(signal_key)

        if not isinstance(wave, str):
            raise Exception(
                f"pl-waveform: signal '{signal_key}' must have a string 'wave'"
            )
        if len(wave) == 0:
            raise Exception(
                f"pl-waveform: signal '{signal_key}' must define a non-empty 'wave'"
            )

        duration = len(wave) * float(sig.get("period", 1))
        if expected_duration is None:
            expected_duration = duration
        elif abs(duration - expected_duration) > 1e-9:
            raise Exception(
                f"pl-waveform: signal '{signal_key}' has duration {duration:g}, "
                f"but expected {expected_duration:g}; adjust wave length or period"
            )

        if not sig.get("editable", False):
            continue

        if "correct_answers" not in sig:
            raise Exception(
                f"pl-waveform: editable signal '{signal_key}' must define 'correct_answers'"
            )
        if "correct_wave" not in sig or not isinstance(sig.get("correct_wave"), str):
            raise Exception(
                f"pl-waveform: editable signal '{signal_key}' must define string 'correct_wave'"
            )

        correct_answers = sig.get("correct_answers")
        if not isinstance(correct_answers, list):
            raise Exception(
                f"pl-waveform: editable signal '{signal_key}' must define 'correct_answers' as a list"
            )
        allowed_values = _get_allowed_values(sig)

        editable_cells = _editable_cells(sig, answers_name)
        if len(editable_cells) != len(correct_answers):
            raise Exception(
                f"pl-waveform: editable signal '{signal_key}' has {len(editable_cells)} editable cells in 'wave' "
                f"but {len(correct_answers)} entries in 'correct_answers'"
            )

        for cycle_idx, val in enumerate(correct_answers, start=1):
            canonical = _canonical_value(val, allowed_values)
            if canonical is None:
                raise Exception(
                    f"pl-waveform: editable signal '{signal_key}' has correct_answers value '{val}' "
                    f"at cycle {cycle_idx} that is not in allowed_values {allowed_values}"
                )


def prepare(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    required_attribs = ["answers-name"]
    optional_attribs = [
        "weight",
        "hscale",
        "signals-param",
        "feedback",
        "input-mode",
    ]
    pl.check_attribs(element, required_attribs, optional_attribs)

    answers_name = pl.get_string_attrib(element, "answers-name")
    feedback = pl.get_string_attrib(element, "feedback", FEEDBACK_DEFAULT)
    input_mode = pl.get_string_attrib(element, "input-mode", INPUT_MODE_DEFAULT)
    signals = _get_signals(element, data)

    if feedback not in FEEDBACK_OPTIONS:
        raise Exception(
            f"pl-waveform: invalid feedback '{feedback}'. Must be one of {FEEDBACK_OPTIONS}"
        )
    if input_mode not in INPUT_MODE_OPTIONS:
        raise Exception(
            f"pl-waveform: invalid input-mode '{input_mode}'. Must be one of {INPUT_MODE_OPTIONS}"
        )

    _validate_signals(signals, answers_name)

    for sig in signals:
        if not sig.get("editable", False):
            continue
        for cell in _editable_cells(sig, answers_name):
            key = cell["key"]
            if key in data["correct_answers"]:
                raise Exception(f"pl-waveform: duplicate correct_answers key '{key}'")
            data["correct_answers"][key] = cell["correct_value"]


def _question_editable_rows(
    signals: list[dict[str, Any]],
    answers_name: str,
    data: dict[str, Any],
    input_mode: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Build question-panel metadata for all editable rows."""
    editable_rows = []
    editable_row_models = []
    max_cycles = 0
    raw_answers = data["raw_submitted_answers"]
    is_editable = data.get("editable", True)

    for sig in signals:
        if not sig.get("editable", False):
            continue
        sig_cells = _editable_cells(sig, answers_name)
        allowed_values = _get_allowed_values(sig)
        row_model_cells = []
        input_cells = []
        max_cycles = max(max_cycles, len(sig_cells))
        for cell in sig_cells:
            raw = raw_answers.get(cell["key"], "")
            if (
                input_mode == "toggle"
                and cell["key"] not in raw_answers
                and _canonical_value("x", allowed_values)
            ):
                raw = "x"
            canonical_raw = _canonical_answer_value(
                raw, allowed_values, from_json=False
            )
            value = canonical_raw or ""
            aria_label = f"{sig['signal_label']} cycle {cell['editable_index']} answer"

            input_cells.append(
                {
                    "key": cell["key"],
                    "signal_name": sig["signal_label"],
                    "raw_value": canonical_raw if canonical_raw is not None else raw,
                    "has_raw_value": bool(raw),
                    "editable": is_editable,
                    "cycle_num": cell["editable_index"],
                    "editable_index": cell["editable_index"],
                    "abs_index": cell["abs_index"],
                    "period": cell["period"],
                    "toggle_mode": input_mode == "toggle",
                    "text_mode": input_mode == "text",
                    "toggle_value": value,
                    "allowed_values_json": json.dumps(allowed_values),
                    "text_input_hint": f"Type one of: {', '.join(allowed_values)}",
                    "text_input_maxlength": max(len(value) for value in allowed_values),
                    "aria_label": aria_label,
                }
            )
            row_model_cells.append(
                {
                    "abs_index": cell["abs_index"],
                    "editable": True,
                    "key": cell["key"],
                    "cycle_num": cell["editable_index"],
                    "editable_index": cell["editable_index"],
                    "value": value,
                    "is_unanswered": value == "",
                    "is_zero": value == "0",
                    "is_one": value == "1",
                    "is_x": value == "x",
                    "aria_label": aria_label,
                }
            )

        editable_row_models.append(
            {
                "signal_name": sig["signal_label"],
                "signal_key": sig["signal_key"],
                "display_name": sig["name"],
                "wave": sig["wave"],
                "wave_length": len(sig["wave"]),
                "data": sig.get("data", []),
                "allowed_values": allowed_values,
                "period": sig.get("period", 1),
                "is_bus": sig.get("is_bus", False),
                "cells": row_model_cells,
            }
        )
        editable_rows.append({"signal_name": sig["signal_label"], "cells": input_cells})

    return editable_rows, editable_row_models, max_cycles


def _parse_error_cells(
    signals: list[dict[str, Any]],
    answers_name: str,
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build parse-error overlay metadata for editable cells."""
    format_errors = data.get("format_errors", {})
    return [
        {
            "key": cell["key"],
            "signal_name": sig["signal_label"],
            "cycle_num": cell["editable_index"],
            "abs_index": cell["abs_index"],
            "period": cell["period"],
            "message": format_errors[cell["key"]],
        }
        for sig in signals
        if sig.get("editable", False)
        for cell in _editable_cells(sig, answers_name)
        if cell["key"] in format_errors
    ]


def _question_cell_scores(
    signals: list[dict[str, Any]],
    answers_name: str,
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build score overlay metadata for question-panel rendering."""
    cell_scores = []
    for sig in signals:
        if not sig.get("editable", False):
            continue
        allowed_values = _get_allowed_values(sig)
        for cell in _editable_cells(sig, answers_name):
            score_data = data.get("partial_scores", {}).get(cell["key"])
            if score_data is None:
                continue

            submitted_raw = data["submitted_answers"].get(cell["key"])
            is_unanswered = submitted_raw is None
            cell_scores.append(
                {
                    "signal_name": sig["signal_label"],
                    "cycle_num": cell["editable_index"],
                    "abs_index": cell["abs_index"],
                    "period": cell["period"],
                    "correct": score_data.get("score", 0) >= 1,
                    "incorrect": not is_unanswered and score_data.get("score", 0) < 1,
                    "invalid": _is_invalid_submission(submitted_raw, allowed_values),
                    "invalid_message": _invalid_value_message(allowed_values),
                    "unanswered": is_unanswered,
                }
            )
    return cell_scores


def _question_render_params(
    element: Any,
    signals: list[dict[str, Any]],
    data: dict[str, Any],
    answers_name: str,
    hscale: float,
) -> dict[str, Any]:
    """Build mustache parameters for the question panel."""
    feedback = pl.get_string_attrib(element, "feedback", FEEDBACK_DEFAULT)
    input_mode = pl.get_string_attrib(element, "input-mode", INPUT_MODE_DEFAULT)
    editable_rows, editable_row_models, max_cycles = _question_editable_rows(
        signals,
        answers_name,
        data,
        input_mode,
    )
    question_signals = []
    for sig in signals:
        rendered = (
            _build_value_rendered_signal(
                sig, answers_name, data["raw_submitted_answers"], from_json=False
            )
            if sig.get("editable")
            else dict(sig)
        )
        # Text inputs sit over the bus cells, so WaveDrom's own data labels are
        # hidden in the question panel but kept for submission/answer panels.
        if input_mode == "text" and sig.get("editable") and sig.get("is_bus"):
            rendered.pop("data", None)
        question_signals.append(rendered)
    parse_error_cells = _parse_error_cells(signals, answers_name, data)
    parse_errors = {cell["key"]: cell["message"] for cell in parse_error_cells}
    cell_scores = _question_cell_scores(signals, answers_name, data)
    graded = bool(cell_scores)

    return {
        "question": True,
        "feedback": feedback,
        "input_mode": input_mode,
        "toggle_question": input_mode == "toggle",
        "wavedrom_json": _build_wavedrom(question_signals, hscale),
        "editable_row_models_json": json.dumps(editable_row_models),
        "editable_rows": editable_rows,
        "has_editable": len(editable_rows) > 0,
        "cycle_headers": [{"cycle_num": idx + 1} for idx in range(max_cycles)],
        "editable_signals_json": json.dumps(
            [sig["signal_label"] for sig in signals if sig.get("editable", False)]
        ),
        "parse_errors_json": json.dumps(parse_errors),
        "parse_error_cells_json": json.dumps(parse_error_cells),
        "has_parse_errors": len(parse_error_cells) > 0,
        "cell_scores_json": json.dumps(cell_scores if graded else []),
        "has_cell_scores": feedback != "none"
        and graded
        and len(parse_error_cells) == 0
        and len(cell_scores) > 0,
        "uuid": pl.get_uuid(),
    }


def _submission_render_params(
    element: Any,
    signals: list[dict[str, Any]],
    data: dict[str, Any],
    answers_name: str,
    hscale: float,
) -> dict[str, Any]:
    """Build mustache parameters for the submission panel."""
    feedback = pl.get_string_attrib(element, "feedback", FEEDBACK_DEFAULT)
    input_mode = pl.get_string_attrib(element, "input-mode", INPUT_MODE_DEFAULT)
    parse_error_cells = _parse_error_cells(signals, answers_name, data)
    parse_errors = {cell["key"]: cell["message"] for cell in parse_error_cells}
    partial_scores = data.get("partial_scores", {})
    # Format errors can render before grading; score feedback should wait until
    # PrairieLearn has called grade() and populated partial_scores.
    graded = any(
        cell["key"] in partial_scores
        for sig in signals
        if sig.get("editable", False)
        for cell in _editable_cells(sig, answers_name)
    )
    feedback_cells = []
    result_rows = []
    total_cells = 0
    correct_count = 0
    max_cycles = 0

    for sig in signals:
        if not sig.get("editable", False):
            continue
        sig_cells = _editable_cells(sig, answers_name)
        allowed_values = _get_allowed_values(sig)
        row_cells = []
        max_cycles = max(max_cycles, len(sig_cells))
        for cell in sig_cells:
            key = cell["key"]
            score = partial_scores.get(key, {}).get("score") if graded else None
            submitted_raw = data["submitted_answers"].get(key, None)
            submitted = _answer_value(submitted_raw) if submitted_raw is not None else ""
            format_error = data.get("format_errors", {}).get(key)
            is_unanswered = submitted_raw is None
            row_cells.append(
                {
                    "signal_name": sig["signal_label"],
                    "cycle_num": cell["editable_index"],
                    "abs_index": cell["abs_index"],
                    "period": cell["period"],
                    "submitted": submitted,
                    "has_submitted": bool(submitted),
                    "correct_value": cell["correct_value"],
                    "correct": score is not None and score >= 1,
                    "incorrect": not is_unanswered and score is not None and score < 1,
                    "invalid": format_error is not None
                    or _is_invalid_submission(submitted_raw, allowed_values),
                    "invalid_message": format_error
                    or _invalid_value_message(allowed_values),
                    "unanswered": is_unanswered,
                }
            )

        row_correct = sum(1 for cell in row_cells if cell["correct"])
        feedback_cells.extend(row_cells)
        total_cells += len(row_cells)
        correct_count += row_correct
        result_rows.append(
            {
                "signal_name": sig["signal_label"],
                "cells": row_cells,
                "row_correct": row_correct == len(row_cells),
                "row_incorrect": row_correct != len(row_cells),
                "row_score": f"{row_correct}/{len(row_cells)}",
            }
        )

    score_pct = round(100 * correct_count / total_cells) if total_cells > 0 else 0

    return {
        "submission": True,
        "feedback": feedback,
        "input_mode": input_mode,
        "wavedrom_json": _build_wavedrom(
            [
                (
                    _build_value_rendered_signal(
                        sig, answers_name, data["submitted_answers"]
                    )
                    if sig.get("editable")
                    else dict(sig)
                )
                for sig in signals
            ],
            hscale,
        ),
        "cell_scores_json": json.dumps(feedback_cells if graded else []),
        "editable_signals_json": json.dumps(
            [sig["signal_label"] for sig in signals if sig.get("editable", False)]
        ),
        "parse_errors_json": json.dumps(parse_errors),
        "parse_error_cells_json": json.dumps(parse_error_cells),
        "has_parse_errors": len(parse_error_cells) > 0,
        "correct_count": correct_count,
        "total_cells": total_cells,
        "score_pct": score_pct,
        "correct": score_pct == 100,
        "partial": score_pct if 0 < score_pct < 100 else False,
        "incorrect": score_pct == 0,
        "has_cell_scores": feedback != "none"
        and graded
        and len(parse_error_cells) == 0
        and len(feedback_cells) > 0,
        "result_rows": result_rows,
        "cycle_headers": [{"cycle_num": idx + 1} for idx in range(max_cycles)],
        "uuid": pl.get_uuid(),
    }


def render(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    answers_name = pl.get_string_attrib(element, "answers-name")
    signals = _get_signals(element, data)
    hscale = pl.get_float_attrib(element, "hscale", None)
    if hscale is None:
        hscale = data["params"].get("hscale", HSCALE_DEFAULT)

    if data["panel"] == "question":
        html_params = _question_render_params(
            element, signals, data, answers_name, hscale
        )
    elif data["panel"] == "submission":
        html_params = _submission_render_params(
            element, signals, data, answers_name, hscale
        )
    elif data["panel"] == "answer":
        answer_signals = []
        diff_cells = []
        for sig in signals:
            rendered = dict(sig)
            if sig.get("editable"):
                rendered["wave"] = sig["correct_wave"]
                if sig.get("correct_data"):
                    rendered["data"] = sig["correct_data"]
                else:
                    rendered.pop("data", None)

                for cell in _editable_cells(sig, answers_name):
                    submitted = _answer_value(
                        data["submitted_answers"].get(cell["key"]), from_json=True
                    )
                    diff_cells.append(
                        {
                            "signal_name": sig["signal_label"],
                            "cycle_num": cell["editable_index"],
                            "abs_index": cell["abs_index"],
                            "period": cell["period"],
                            "student_value": submitted if submitted else "?",
                            "correct_value": cell["correct_value"],
                            "differs": submitted is not None
                            and _normalize_value(submitted)
                            != _normalize_value(cell["correct_value"]),
                        }
                    )
            answer_signals.append(rendered)

        html_params = {
            "answer": True,
            "wavedrom_json": _build_wavedrom(answer_signals, hscale),
            "diff_json": json.dumps(diff_cells),
            "editable_signals_json": json.dumps(
                [sig["signal_label"] for sig in signals if sig.get("editable", False)]
            ),
            "uuid": pl.get_uuid(),
        }
    else:
        raise Exception(f"pl-waveform: invalid panel '{data['panel']}'")

    with open("pl-waveform.mustache", "r", encoding="utf-8") as f:
        return chevron.render(f, html_params).strip()


def parse(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    answers_name = pl.get_string_attrib(element, "answers-name")
    input_mode = pl.get_string_attrib(element, "input-mode", INPUT_MODE_DEFAULT)
    signals = _get_signals(element, data)
    format_errors = data.setdefault("format_errors", {})

    for sig in signals:
        if not sig.get("editable", False):
            continue
        allowed_values = _get_allowed_values(sig)
        for cell in _editable_cells(sig, answers_name):
            val = data["submitted_answers"].get(cell["key"], None)
            val_normalized = _normalize_value(val)

            if val_normalized is None:
                data["submitted_answers"][cell["key"]] = None
                format_errors[cell["key"]] = _invalid_value_message(allowed_values)
            else:
                canonical = _canonical_value(val, allowed_values)
                if canonical is None and input_mode == "text":
                    format_errors[cell["key"]] = _invalid_value_message(allowed_values)
                    continue
                format_errors.pop(cell["key"], None)
                data["submitted_answers"][cell["key"]] = pl.to_json(
                    canonical if canonical is not None else val_normalized
                )


def grade(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    answers_name = pl.get_string_attrib(element, "answers-name")
    weight = pl.get_integer_attrib(element, "weight", WEIGHT_DEFAULT)
    signals = _get_signals(element, data)

    if _parse_error_cells(signals, answers_name, data):
        return

    for sig in signals:
        if not sig.get("editable", False):
            continue
        for cell in _editable_cells(sig, answers_name):
            key = cell["key"]
            if key in data.get("format_errors", {}):
                continue

            a_tru = pl.from_json(data["correct_answers"].get(key, None))
            if a_tru is None:
                continue

            a_sub = data["submitted_answers"].get(key, None)
            if a_sub is None:
                data["partial_scores"][key] = {"score": 0, "weight": weight}
                continue

            a_sub = pl.from_json(a_sub)
            if str(a_sub).strip().lower() == str(a_tru).strip().lower():
                data["partial_scores"][key] = {"score": 1, "weight": weight}
            else:
                data["partial_scores"][key] = {"score": 0, "weight": weight}
