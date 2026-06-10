import json
import lxml.html
import chevron
import prairielearn as pl


WEIGHT_DEFAULT = 1
HSCALE_DEFAULT = 1.5
SIGNALS_PARAM_DEFAULT = "signals"
FEEDBACK_DEFAULT = "cell"
FEEDBACK_OPTIONS = {"cell", "row", "table"}
INPUT_MODE_DEFAULT = "toggle"
INPUT_MODE_OPTIONS = {"toggle", "text"}
LABEL_DEFAULT = None
SHOW_SCORE_DEFAULT = True
VALID_VALUES = {"0", "1", "x"}
TOGGLE_FIXED_VALUES = {"0", "1"}


def _get_signals(element, data):
    signals_param = pl.get_string_attrib(element, "signals-param", SIGNALS_PARAM_DEFAULT)
    return _normalize_signals(data["params"].get(signals_param, []))


def _editable_signals(signals):
    return [s for s in signals if s.get("editable", False)]


def _answer_key(answers_name, sig_name, cycle_num):
    """Namespaced key: e.g. 'timing_Q_1'."""
    return f"{answers_name}_{sig_name}_{cycle_num}"


def _normalize_value(val):
    if val is None:
        return None
    normalized = str(val).strip().lower()
    if normalized == "":
        return None
    return normalized


def _display_value(val):
    if val is None:
        return None
    displayed = str(val).strip()
    if displayed == "":
        return None
    return displayed


def _allowed_value_map(allowed_values):
    return {_normalize_value(value): value for value in allowed_values}


def _canonical_value(val, allowed_values):
    normalized = _normalize_value(val)
    if normalized is None:
        return None
    return _allowed_value_map(allowed_values).get(normalized)


def _is_binary_allowed_values(allowed_values):
    return all(_normalize_value(value) in VALID_VALUES for value in allowed_values)


def _uses_bus_rendering(sig):
    return "data" in sig or not _is_binary_allowed_values(_get_allowed_values(sig))


def _normalize_binary_value(val, sig_name, field_name, position=None):
    normalized = _normalize_value(val)
    if normalized not in VALID_VALUES:
        location = f" at position {position}" if position is not None else ""
        raise Exception(
            f"pl-waveform: signal '{sig_name}' has invalid {field_name} value '{val}'{location}; "
            f"expected one of {sorted(VALID_VALUES)}"
        )
    return normalized


def _normalize_binary_list(values, sig_name, field_name, allow_empty=False):
    if not isinstance(values, list):
        raise Exception(f"pl-waveform: signal '{sig_name}' must define '{field_name}' as a list")
    if not allow_empty and len(values) == 0:
        raise Exception(f"pl-waveform: signal '{sig_name}' must define '{field_name}' as a non-empty list")
    return [
        _normalize_binary_value(val, sig_name, field_name, position=idx)
        for idx, val in enumerate(values, start=1)
    ]


def _encode_wave_from_values(values):
    """Build a WaveDrom wave string from a flat list of values.
    An 'x' cell always emits 'x' (never '.') so it never silently extends
    the previous state, and it resets the continuation chain so the next
    cell also emits its full character.
    """
    if not values:
        return ""

    chars = [values[0]]
    prev = values[0] if values[0] != "x" else None
    for idx in range(1, len(values)):
        val = values[idx]
        if val != "x" and val == prev:
            chars.append(".")
        else:
            chars.append(val)
            prev = val if val != "x" else None
    return "".join(chars)


def _build_correct_wave_from_values(initial, values):
    """Build a WaveDrom wave string for the correct answer.
    An 'x' value resets the continuation chain so the next cell always
    emits a full character rather than '.', matching JS behaviour.
    """
    prev = initial if initial != "x" else None
    chars = [initial]
    for val in values:
        if val != "x" and val == prev:
            chars.append(".")
        else:
            chars.append(val)
            prev = val if val != "x" else None
    return "".join(chars)


def _normalize_signal(sig, idx):
    if not isinstance(sig, dict):
        raise Exception(f"pl-waveform: signal at index {idx} must be a dictionary")

    sig_name = sig.get("name", f"signal[{idx}]")
    editable = bool(sig.get("editable", False))
    has_wave = "wave" in sig
    has_values = "values" in sig
    has_initial = "initial" in sig

    if has_wave and (has_values or has_initial):
        raise Exception(
            f"pl-waveform: signal '{sig_name}' mixes raw WaveDrom fields with shorthand authoring fields; "
            "use either 'wave' or the shorthand API, but not both"
        )

    normalized = dict(sig)

    if has_wave:
        return normalized

    if has_values:
        if editable:
            raise Exception(
                f"pl-waveform: editable signal '{sig_name}' cannot use 'values' shorthand; "
                "use 'initial' + 'correct_answers' or provide raw 'wave'/'correct_wave'"
            )
        normalized["wave"] = _encode_wave_from_values(
            _normalize_binary_list(sig["values"], sig_name, "values")
        )
        return normalized

    if editable and has_initial:
        correct_answers = _normalize_binary_list(
            sig.get("correct_answers"), sig_name, "correct_answers", allow_empty=True
        )
        initial = _normalize_binary_value(sig["initial"], sig_name, "initial")
        normalized["initial"] = initial
        normalized["correct_answers"] = correct_answers
        normalized["wave"] = initial + ("x" * len(correct_answers))
        normalized["correct_wave"] = _build_correct_wave_from_values(initial, correct_answers)
        return normalized

    return normalized


def _normalize_signals(signals):
    if not isinstance(signals, list):
        return signals
    return [_normalize_signal(sig, idx) for idx, sig in enumerate(signals)]


def _get_allowed_values(sig):
    raw_allowed_values = sig.get("allowed_values")
    if raw_allowed_values is None:
        normalized_answers = [_normalize_value(val) for val in sig.get("correct_answers", [])]
        if any(val == "x" for val in normalized_answers):
            return ["0", "1", "x"]
        return ["0", "1"]

    if not isinstance(raw_allowed_values, list) or len(raw_allowed_values) == 0:
        raise Exception(
            f"pl-waveform: editable signal '{sig['name']}' must define 'allowed_values' as a non-empty list"
        )

    allowed_values = []
    seen = set()
    for idx, val in enumerate(raw_allowed_values, start=1):
        displayed = _display_value(val)
        normalized = _normalize_value(displayed)
        if normalized is None:
            raise Exception(
                f"pl-waveform: editable signal '{sig['name']}' has blank allowed_values entry at position {idx}"
            )
        if normalized in seen:
            raise Exception(
                f"pl-waveform: editable signal '{sig['name']}' repeats allowed_values entry '{normalized}'"
            )
        seen.add(normalized)
        allowed_values.append(displayed)

    return allowed_values


def _format_allowed_values_hint(allowed_values):
    return f"Type one of: {', '.join(allowed_values)}"


def _answer_value(raw, from_json=True):
    if raw is None:
        return None
    value = raw
    if from_json:
        value = pl.from_json(raw)
    return _display_value(value)


def _submitted_answer_value(raw):
    return _normalize_value(_answer_value(raw, from_json=True))


def _canonical_answer_value(raw, allowed_values, from_json=True):
    return _canonical_value(_answer_value(raw, from_json=from_json), allowed_values)


def _is_invalid_submission(raw, allowed_values):
    submitted = _submitted_answer_value(raw)
    return submitted is not None and submitted not in _allowed_value_map(allowed_values)


def _build_wavedrom(signals, hscale):
    """Build a WaveDrom JSON string from the signal list."""
    wd_signals = []
    for sig in signals:
        s = {"name": sig["name"]}
        s["wave"] = sig["wave"]
        if "period" in sig:
            s["period"] = sig["period"]
        if "data" in sig:
            s["data"] = sig["data"]
        wd_signals.append(s)

    return json.dumps({
        "signal": wd_signals,
        "config": {"hscale": hscale},
        "head": {"tick": 0},
    })


def _editable_cells(sig, answers_name):
    cells = []
    allowed_values = _get_allowed_values(sig)
    for editable_index, abs_index in enumerate(
        [idx for idx, ch in enumerate(sig["wave"]) if ch == "x"],
        start=1,
    ):
        correct_value = _canonical_value(sig["correct_answers"][editable_index - 1], allowed_values)
        if correct_value is None:
            correct_value = _display_value(sig["correct_answers"][editable_index - 1])
        cells.append({
            "editable_index": editable_index,
            "cycle_num": editable_index,
            "abs_index": abs_index,
            "key": _answer_key(answers_name, sig["name"], editable_index),
            "correct_value": correct_value,
            "period": sig.get("period", 1),
        })
    return cells


def _build_editable_bus_wave_and_data(wave_chars, cells_by_abs_index, value_by_key):
    """Build compressed WaveDrom bus wave/data for editable rows.
    Repeated adjacent answered values continue with '.', transitions emit '=',
    and unanswered editable cells emit 'x' and reset continuity.
    """
    new_chars = []
    data_values = []
    prev_bus_value = None

    for abs_index, ch in enumerate(wave_chars):
        cell = cells_by_abs_index.get(abs_index)
        if cell is not None:
            value = value_by_key.get(cell["key"])
            if value is None:
                new_chars.append("x")
                prev_bus_value = None
            elif prev_bus_value is not None and value == prev_bus_value:
                new_chars.append(".")
            else:
                new_chars.append("=")
                data_values.append(value)
                prev_bus_value = value
            continue

        new_chars.append(ch)
        if ch == "=":
            prev_bus_value = None
        elif ch == "x":
            prev_bus_value = None

    return "".join(new_chars), data_values


def _build_value_rendered_signal(sig, answers_name, answer_values, from_json=True):
    s = dict(sig)
    allowed_values = _get_allowed_values(sig)
    wave_chars = list(sig["wave"])
    cells_by_abs_index = {
        cell["abs_index"]: cell for cell in _editable_cells(sig, answers_name)
    }

    if _uses_bus_rendering(sig):
        value_by_key = {}
        for cell in cells_by_abs_index.values():
            value_by_key[cell["key"]] = _canonical_answer_value(
                answer_values.get(cell["key"], None),
                allowed_values,
                from_json=from_json,
            )

        wave, data_values = _build_editable_bus_wave_and_data(
            wave_chars,
            cells_by_abs_index,
            value_by_key,
        )
        s["wave"] = wave
        if data_values:
            s["data"] = data_values
        elif "data" in s:
            del s["data"]
        return s

    # prev_val tracks the last non-x, non-dot character so we can collapse
    # identical adjacent values into '.'.  We MUST reset it to None on 'x'
    # so that a cell following an 'x' (even if it has the same value as the
    # cell *before* the 'x') always emits its full character rather than '.'.
    # Without this, 0→x→0 would produce "0x." (x extended) instead of "0x0".
    prev_val = None
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
            if val != "x" and val == prev_val:
                new_chars.append(".")
            else:
                new_chars.append(val)
                prev_val = val if val != "x" else None
        else:
            new_chars.append(ch)
            if ch not in (".", "x"):
                prev_val = ch
            elif ch == "x":
                prev_val = None
    s["wave"] = "".join(new_chars)
    return s


def _build_correct_rendered_signal(sig, answers_name):
    if not sig.get("editable"):
        return dict(sig)

    s = dict(sig)
    if not _uses_bus_rendering(sig):
        s["wave"] = sig["correct_wave"]
        return s

    cells_by_abs_index = {
        cell["abs_index"]: cell for cell in _editable_cells(sig, answers_name)
    }
    value_by_key = {}
    for cell in cells_by_abs_index.values():
        value_by_key[cell["key"]] = cell["correct_value"]

    wave, data_values = _build_editable_bus_wave_and_data(
        list(sig["wave"]),
        cells_by_abs_index,
        value_by_key,
    )
    s["wave"] = wave
    if data_values:
        s["data"] = data_values
    elif "data" in s:
        del s["data"]
    return s


def _build_submission_signals(signals, data, answers_name, from_json=True):
    """Build signal list with student's submitted values replacing 'x' placeholders."""
    result = []
    for sig in signals:
        if sig.get("editable"):
            result.append(_build_value_rendered_signal(
                sig,
                answers_name,
                data["submitted_answers"],
                from_json=from_json,
            ))
        else:
            result.append(dict(sig))
    return result


def _build_question_signals(signals, data, answers_name, input_mode, from_json=True):
    result = _build_submission_signals(signals, data, answers_name, from_json=from_json)
    if input_mode != "text":
        return result

    editable_bus_names = {
        sig["name"] for sig in signals
        if sig.get("editable") and _uses_bus_rendering(sig)
    }
    if not editable_bus_names:
        return result

    for sig in result:
        if sig.get("name") in editable_bus_names:
            sig.pop("data", None)
    return result


def _build_correct_signals(signals, answers_name):
    return [_build_correct_rendered_signal(sig, answers_name) for sig in signals]


def _validate_toggle_signal(sig):
    sig_name = sig["name"]
    wave = sig["wave"]
    allowed_values = _get_allowed_values(sig)

    if _uses_bus_rendering(sig):
        # Bus/hex signals in toggle mode: wave must start with '=' (fixed initial bus value)
        # or 'x' (all editable), followed only by editable 'x' cells.
        if not wave or wave[0] not in {"=", "x"}:
            raise Exception(
                f"pl-waveform: editable bus signal '{sig_name}' must start with '=' or 'x' in "
                "input-mode='toggle'. Use input-mode='text' for other wave shapes."
            )
    else:
        if "data" in sig:
            raise Exception(
                f"pl-waveform: editable signal '{sig_name}' uses bus 'data', which is not supported in input-mode='toggle'. "
                "Use input-mode='text' for this signal."
            )
        if not _is_binary_allowed_values(allowed_values):
            raise Exception(
                f"pl-waveform: editable signal '{sig_name}' has non-binary allowed_values, which are not supported in "
                "input-mode='toggle'. Use input-mode='text' for this signal."
            )
        if not wave or wave[0] not in TOGGLE_FIXED_VALUES:
            raise Exception(
                f"pl-waveform: editable signal '{sig_name}' must start with a fixed '0' or '1' in input-mode='toggle'. "
                "Use input-mode='text' for other wave shapes."
            )
    if any(ch != "x" for ch in wave[1:]):
        raise Exception(
            f"pl-waveform: editable signal '{sig_name}' must use a fixed initial state followed by editable 'x' cells in input-mode='toggle'. "
            "Use input-mode='text' for other wave shapes."
        )


def _build_editable_row_model(sig, answers_name, raw_submitted_answers):
    cells = []
    allowed_values = _get_allowed_values(sig)

    for cell in _editable_cells(sig, answers_name):
        raw = raw_submitted_answers.get(cell["key"], "")
        submitted_value = _canonical_answer_value(raw, allowed_values, from_json=False) or ""
        cells.append({
            "abs_index": cell["abs_index"],
            "editable": True,
            "key": cell["key"],
            "cycle_num": cell["editable_index"],
            "editable_index": cell["editable_index"],
            "value": submitted_value,
            "is_unanswered": submitted_value == "",
            "is_zero": submitted_value == "0",
            "is_one": submitted_value == "1",
            "is_x": submitted_value == "x",
            "aria_label": f"{sig['name']} cycle {cell['editable_index']} answer",
        })

    return {
        "signal_name": sig["name"],
        "wave": sig["wave"],
        "wave_length": len(sig["wave"]),
        "data": sig.get("data", []),
        "allowed_values": allowed_values,
        "period": sig.get("period", 1),
        "is_bus": _uses_bus_rendering(sig),
        "cells": cells,
    }


def _validate_signals(signals, answers_name, input_mode):
    if not isinstance(signals, list):
        raise Exception("pl-waveform: signals param must be a list of signal dictionaries")

    seen_names = set()
    for idx, sig in enumerate(signals):
        sig_name = sig.get("name")
        wave = sig.get("wave")
        if not sig_name or not isinstance(sig_name, str):
            raise Exception(f"pl-waveform: signal at index {idx} must have a string 'name'")
        if sig_name in seen_names:
            raise Exception(f"pl-waveform: duplicate signal name '{sig_name}' in '{answers_name}'")
        seen_names.add(sig_name)

        if not isinstance(wave, str):
            raise Exception(f"pl-waveform: signal '{sig_name}' must have a string 'wave'")

        if not sig.get("editable", False):
            continue

        if "correct_answers" not in sig:
            raise Exception(f"pl-waveform: editable signal '{sig_name}' must define 'correct_answers'")
        if "correct_wave" not in sig or not isinstance(sig.get("correct_wave"), str):
            raise Exception(f"pl-waveform: editable signal '{sig_name}' must define string 'correct_wave'")

        correct_answers = sig.get("correct_answers")
        if not isinstance(correct_answers, list):
            raise Exception(f"pl-waveform: editable signal '{sig_name}' must define 'correct_answers' as a list")
        allowed_values = _get_allowed_values(sig)

        editable_cells = _editable_cells(sig, answers_name)
        if len(editable_cells) != len(correct_answers):
            raise Exception(
                f"pl-waveform: editable signal '{sig_name}' has {len(editable_cells)} editable cells in 'wave' "
                f"but {len(correct_answers)} entries in 'correct_answers'"
            )

        for cycle_idx, val in enumerate(correct_answers, start=1):
            canonical = _canonical_value(val, allowed_values)
            if canonical is None:
                raise Exception(
                    f"pl-waveform: editable signal '{sig_name}' has correct_answers value '{val}' "
                    f"at cycle {cycle_idx} that is not in allowed_values {allowed_values}"
                )

        if input_mode == "toggle":
            _validate_toggle_signal(sig)


def prepare(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    required_attribs = ["answers-name"]
    optional_attribs = [
        "weight",
        "hscale",
        "signals-param",
        "feedback",
        "input-mode",
        "label",
        "show-score",
    ]
    pl.check_attribs(element, required_attribs, optional_attribs)

    answers_name = pl.get_string_attrib(element, "answers-name")
    feedback = pl.get_string_attrib(element, "feedback", FEEDBACK_DEFAULT)
    input_mode = pl.get_string_attrib(element, "input-mode", INPUT_MODE_DEFAULT)
    signals = _get_signals(element, data)

    if feedback not in FEEDBACK_OPTIONS:
        raise Exception(f"pl-waveform: invalid feedback '{feedback}'. Must be one of {FEEDBACK_OPTIONS}")
    if input_mode not in INPUT_MODE_OPTIONS:
        raise Exception(f"pl-waveform: invalid input-mode '{input_mode}'. Must be one of {INPUT_MODE_OPTIONS}")

    _validate_signals(signals, answers_name, input_mode)

    for sig in _editable_signals(signals):
        for cell in _editable_cells(sig, answers_name):
            key = cell["key"]
            if key in data["correct_answers"]:
                raise Exception(f"pl-waveform: duplicate correct_answers key '{key}'")
            data["correct_answers"][key] = cell["correct_value"]


def render(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    answers_name = pl.get_string_attrib(element, "answers-name")
    signals = _get_signals(element, data)

    # hscale: attribute overrides param
    hscale = pl.get_float_attrib(element, "hscale", None)
    if hscale is None:
        hscale = data["params"].get("hscale", HSCALE_DEFAULT)

    editable_sigs = _editable_signals(signals)

    if data["panel"] == "question":
        feedback = pl.get_string_attrib(element, "feedback", FEEDBACK_DEFAULT)
        input_mode = pl.get_string_attrib(element, "input-mode", INPUT_MODE_DEFAULT)
        show_score = pl.get_boolean_attrib(element, "show-score", SHOW_SCORE_DEFAULT)
        base_wavedrom_json = _build_wavedrom(signals, hscale)
        question_signals = _build_question_signals(
            signals,
            {"submitted_answers": data["raw_submitted_answers"]},
            answers_name,
            input_mode,
            from_json=False,
        )
        wavedrom_json = _build_wavedrom(question_signals, hscale)
        is_editable = data.get("editable", True)

        editable_rows = []
        editable_row_models = []
        max_cycles = 0
        for sig in editable_sigs:
            sig_name = sig["name"]
            allowed_values = _get_allowed_values(sig)
            sig_cells = _editable_cells(sig, answers_name)
            num_cycles = len(sig_cells)
            max_cycles = max(max_cycles, num_cycles)

            editable_row_models.append(_build_editable_row_model(sig, answers_name, data["raw_submitted_answers"]))

            cells = []
            for cell in sig_cells:
                raw = data["raw_submitted_answers"].get(cell["key"], "")
                canonical_raw = _canonical_answer_value(raw, allowed_values, from_json=False)
                cells.append({
                    "key": cell["key"],
                    "signal_name": sig_name,
                    "raw_value": canonical_raw if canonical_raw is not None else raw,
                    "has_raw_value": bool(raw),
                    "editable": is_editable,
                    "cycle_num": cell["editable_index"],
                    "editable_index": cell["editable_index"],
                    "abs_index": cell["abs_index"],
                    "period": cell["period"],
                    "toggle_mode": input_mode == "toggle",
                    "text_mode": input_mode == "text",
                    "toggle_value": canonical_raw if canonical_raw is not None else "",
                    "allowed_values_json": json.dumps(allowed_values),
                    "text_input_hint": _format_allowed_values_hint(allowed_values),
                    "aria_label": f"{sig_name} cycle {cell['editable_index']} answer",
                })
            editable_rows.append({"signal_name": sig_name, "cells": cells})

        cycle_headers = [{"cycle_num": i + 1} for i in range(max_cycles)]

        editable_signal_names = [s["name"] for s in editable_sigs]

        parse_errors = {}
        for sig in editable_sigs:
            for cell in _editable_cells(sig, answers_name):
                if cell["key"] in data.get("format_errors", {}):
                    parse_errors[cell["key"]] = data["format_errors"][cell["key"]]

        cell_scores = []
        for sig in editable_sigs:
            allowed_values = _get_allowed_values(sig)
            for cell in _editable_cells(sig, answers_name):
                score_data = data.get("partial_scores", {}).get(cell["key"])
                if score_data is not None:
                    a_sub_raw = data["submitted_answers"].get(cell["key"])
                    is_unanswered = a_sub_raw is None
                    is_invalid = _is_invalid_submission(a_sub_raw, allowed_values)
                    cell_scores.append({
                        "signal_name": sig["name"],
                        "cycle_num": cell["editable_index"],
                        "abs_index": cell["abs_index"],
                        "period": cell["period"],
                        "correct": score_data.get("score", 0) >= 1,
                        "incorrect": not is_unanswered and score_data.get("score", 0) < 1,
                        "invalid": is_invalid,
                        "invalid_message": f"Invalid value. Expected one of: {', '.join(allowed_values)}.",
                        "unanswered": is_unanswered,
                    })

        html_params = {
            "question": True,
            "feedback": feedback,
            "input_mode": input_mode,
            "toggle_question": input_mode == "toggle",
            "wavedrom_json": wavedrom_json,
            "base_wavedrom_json": base_wavedrom_json,
            "editable_row_models_json": json.dumps(editable_row_models),
            "editable_rows": editable_rows,
            "has_editable": len(editable_rows) > 0,
            "cycle_headers": cycle_headers,
            "editable_signals_json": json.dumps(editable_signal_names),
            "parse_errors_json": json.dumps(parse_errors),
            "has_parse_errors": len(parse_errors) > 0,
            "cell_scores_json": json.dumps(cell_scores),
            "has_cell_scores": show_score and len(cell_scores) > 0,
            "uuid": pl.get_uuid(),
        }
        with open("pl-waveform.mustache", "r", encoding="utf-8") as f:
            return chevron.render(f, html_params).strip()

    elif data["panel"] == "submission":
        feedback = pl.get_string_attrib(element, "feedback", FEEDBACK_DEFAULT)
        label = pl.get_string_attrib(element, "label", LABEL_DEFAULT)

        sub_signals = _build_submission_signals(signals, data, answers_name)
        wavedrom_json = _build_wavedrom(sub_signals, hscale)

        editable_signal_names = [s["name"] for s in editable_sigs]
        feedback_cells = []
        total_cells = 0
        correct_count = 0
        max_cycles = 0
        result_rows = []

        for sig in editable_sigs:
            sig_name = sig["name"]
            allowed_values = _get_allowed_values(sig)
            sig_cells = _editable_cells(sig, answers_name)
            num_cycles = len(sig_cells)
            max_cycles = max(max_cycles, num_cycles)
            row_cells = []
            row_correct = 0

            for cell in sig_cells:
                score = data["partial_scores"].get(cell["key"], {}).get("score", None)
                a_sub_raw = data["submitted_answers"].get(cell["key"], None)
                submitted = _answer_value(a_sub_raw, from_json=True) if a_sub_raw is not None else ""
                correct_val = cell["correct_value"]
                is_unanswered = a_sub_raw is None
                is_invalid = _is_invalid_submission(a_sub_raw, allowed_values)
                is_correct = score is not None and score >= 1
                is_incorrect = not is_unanswered and score is not None and score < 1

                cell = {
                    "signal_name": sig_name,
                    "cycle_num": cell["editable_index"],
                    "abs_index": cell["abs_index"],
                    "period": cell["period"],
                    "submitted": submitted,
                    "has_submitted": bool(submitted),
                    "correct_value": correct_val,
                    "correct": is_correct,
                    "incorrect": is_incorrect,
                    "invalid": is_invalid,
                    "invalid_message": f"Invalid value. Expected one of: {', '.join(allowed_values)}.",
                    "unanswered": is_unanswered,
                }
                feedback_cells.append(cell)
                row_cells.append(cell)
                total_cells += 1
                if is_correct:
                    correct_count += 1
                    row_correct += 1

            row_all_correct = row_correct == num_cycles
            result_rows.append({
                "signal_name": sig_name,
                "cells": row_cells,
                "row_correct": row_all_correct,
                "row_incorrect": not row_all_correct,
                "row_score": f"{row_correct}/{num_cycles}",
            })

        cycle_headers = [{"cycle_num": i + 1} for i in range(max_cycles)]
        score_pct = round(100 * correct_count / total_cells) if total_cells > 0 else 0

        html_params = {
            "submission": True,
            "label": label or "",
            "wavedrom_json": wavedrom_json,
            "feedback_json": json.dumps(feedback_cells),
            "editable_signals_json": json.dumps(editable_signal_names),
            "correct_count": correct_count,
            "total_cells": total_cells,
            "score_pct": score_pct,
            "correct": score_pct == 100,
            "partial": score_pct if 0 < score_pct < 100 else False,
            "incorrect": score_pct == 0,
            "has_feedback": len(feedback_cells) > 0,
            "fb_cell": feedback == "cell",
            "fb_row": feedback == "row",
            "fb_table": feedback == "table",
            "result_rows": result_rows,
            "cycle_headers": cycle_headers,
            "uuid": pl.get_uuid(),
        }
        with open("pl-waveform.mustache", "r", encoding="utf-8") as f:
            return chevron.render(f, html_params).strip()

    elif data["panel"] == "answer":
        wavedrom_json = _build_wavedrom(_build_correct_signals(signals, answers_name), hscale)
        editable_signal_names = [s["name"] for s in editable_sigs]

        diff_cells = []
        for sig in editable_sigs:
            for cell in _editable_cells(sig, answers_name):
                submitted_raw = data["submitted_answers"].get(cell["key"], None)
                submitted = _answer_value(submitted_raw, from_json=True) if submitted_raw is not None else None
                differs = (
                    submitted is not None
                    and _normalize_value(submitted) != _normalize_value(cell["correct_value"])
                )
                diff_cells.append({
                    "signal_name": sig["name"],
                    "cycle_num": cell["editable_index"],
                    "abs_index": cell["abs_index"],
                    "period": cell["period"],
                    "student_value": submitted if submitted else "?",
                    "correct_value": cell["correct_value"],
                    "differs": differs,
                })

        html_params = {
            "answer": True,
            "wavedrom_json": wavedrom_json,
            "diff_json": json.dumps(diff_cells),
            "editable_signals_json": json.dumps(editable_signal_names),
            "uuid": pl.get_uuid(),
        }
        with open("pl-waveform.mustache", "r", encoding="utf-8") as f:
            return chevron.render(f, html_params).strip()

    else:
        raise Exception(f"pl-waveform: invalid panel '{data['panel']}'")


def parse(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    answers_name = pl.get_string_attrib(element, "answers-name")
    signals = _get_signals(element, data)

    for sig in _editable_signals(signals):
        allowed_values = _get_allowed_values(sig)
        for cell in _editable_cells(sig, answers_name):
            val = data["submitted_answers"].get(cell["key"], None)
            val_normalized = _normalize_value(val)

            if val_normalized is None:
                data["submitted_answers"][cell["key"]] = None
            else:
                canonical = _canonical_value(val, allowed_values)
                data["submitted_answers"][cell["key"]] = pl.to_json(
                    canonical if canonical is not None else val_normalized
                )


def grade(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    answers_name = pl.get_string_attrib(element, "answers-name")
    weight = pl.get_integer_attrib(element, "weight", WEIGHT_DEFAULT)
    signals = _get_signals(element, data)

    for sig in _editable_signals(signals):
        for cell in _editable_cells(sig, answers_name):
            key = cell["key"]

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
