import json
import importlib
import os
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.modules.setdefault("chevron", types.SimpleNamespace(render=lambda _template, params: json.dumps(params)))

lxml_module = types.ModuleType("lxml")
lxml_html_module = types.ModuleType("lxml.html")
lxml_html_module.fragment_fromstring = ET.fromstring
lxml_module.html = lxml_html_module
sys.modules.setdefault("lxml", lxml_module)
sys.modules.setdefault("lxml.html", lxml_html_module)

pl_stub = types.SimpleNamespace(
    get_string_attrib=lambda element, name, default=None: element.get(name, default),
    get_float_attrib=lambda element, name, default=None: (
        float(element.get(name)) if element.get(name) is not None else default
    ),
    get_boolean_attrib=lambda element, name, default=None: (
        element.get(name, str(default)).lower() in {"true", "1", "yes"}
        if element.get(name) is not None
        else default
    ),
    get_integer_attrib=lambda element, name, default=None: (
        int(element.get(name)) if element.get(name) is not None else default
    ),
    check_attribs=lambda _element, _required, _optional: None,
    from_json=lambda value: json.loads(value) if isinstance(value, str) and value[:1] in {'"', "[", "{"} else value,
    to_json=lambda value: json.dumps(value),
    get_uuid=lambda: "test-uuid",
)

sys.modules.setdefault("prairielearn", pl_stub)

pl_waveform = importlib.import_module("pl-waveform")


def test_normalize_noneditable_wave_list_to_wave() -> None:
    signals = pl_waveform._normalize_signals([  # noqa: SLF001
        {"name": "D", "wave": ["0", "1", "1", "0"], "editable": False}
    ])

    assert signals[0]["wave"] == "01.0"


def test_normalize_editable_prefix_to_wave_and_correct_wave() -> None:
    signals = pl_waveform._normalize_signals([  # noqa: SLF001
        {"name": "Q", "prefix": "0", "editable": True, "correct_answers": ["1", "1", "0"]}
    ])

    assert signals[0]["wave"] == "0xxx"
    assert signals[0]["correct_wave"] == "01.0"


def test_normalize_editable_string_answers_expand_dot_repeats() -> None:
    signals = pl_waveform._normalize_signals([  # noqa: SLF001
        {"name": "Q", "editable": True, "correct_answers": "0.1.", "suffix": "0"}
    ])

    assert signals[0]["correct_answers"] == ["0", "0", "1", "1"]
    assert signals[0]["wave"] == "xxxx0"
    assert signals[0]["correct_wave"] == "0.1.0"


def test_prepare_and_grade_keep_answer_key_contract_for_documented_api() -> None:
    element_html = '<pl-waveform answers-name="timing"></pl-waveform>'
    data = {
        "params": {
            "signals": [
                {"name": "clk", "wave": "lP.", "editable": False},
                {"name": "Q", "prefix": "0", "editable": True, "correct_answers": ["1", "0"]},
            ]
        },
        "correct_answers": {},
        "submitted_answers": {"timing_Q_1": "1", "timing_Q_2": "1"},
        "partial_scores": {},
        "format_errors": {},
        "raw_submitted_answers": {"timing_Q_1": "1", "timing_Q_2": "1"},
    }

    pl_waveform.prepare(element_html, data)
    pl_waveform.parse(element_html, data)
    pl_waveform.grade(element_html, data)

    assert data["correct_answers"] == {
        "timing_Q_1": "1",
        "timing_Q_2": "0",
    }
    assert data["partial_scores"]["timing_Q_1"]["score"] == 1
    assert data["partial_scores"]["timing_Q_2"]["score"] == 0


def test_invalid_cell_submission_still_allows_per_cell_feedback() -> None:
    element_html = '<pl-waveform answers-name="timing" input-mode="text"></pl-waveform>'
    data = {
        "params": {
            "signals": [
                {"name": "clk", "wave": "lP..", "editable": False},
                {
                    "name": "Q",
                    "prefix": "0",
                    "editable": True,
                    "correct_answers": ["1", "0", "0"],
                },
            ]
        },
        "correct_answers": {},
        "submitted_answers": {
            "timing_Q_1": "1",
            "timing_Q_2": "n",
            "timing_Q_3": "0",
        },
        "partial_scores": {},
        "format_errors": {},
        "raw_submitted_answers": {
            "timing_Q_1": "1",
            "timing_Q_2": "n",
            "timing_Q_3": "0",
        },
    }

    pl_waveform.prepare(element_html, data)
    pl_waveform.parse(element_html, data)
    pl_waveform.grade(element_html, data)

    assert data["format_errors"] == {}
    assert data["partial_scores"]["timing_Q_1"]["score"] == 1
    assert data["partial_scores"]["timing_Q_2"]["score"] == 0
    assert data["partial_scores"]["timing_Q_3"]["score"] == 1
    assert pl_waveform._is_invalid_submission(  # noqa: SLF001
        data["submitted_answers"]["timing_Q_2"], ["0", "1"]
    ) is True
    assert pl_waveform._is_invalid_submission(  # noqa: SLF001
        '"2"', ["0", "1"]
    ) is True
    normalized_signals = pl_waveform._normalize_signals(data["params"]["signals"])  # noqa: SLF001
    assert pl_waveform._build_submission_signals(  # noqa: SLF001
        normalized_signals, data, "timing"
    )[1]["wave"] == "01x0"

    data["panel"] = "question"
    old_cwd = os.getcwd()
    try:
        os.chdir(Path(__file__).resolve().parent)
        rendered = json.loads(pl_waveform.render(element_html, data))
    finally:
        os.chdir(old_cwd)

    invalid_score = json.loads(rendered["cell_scores_json"])[1]
    assert invalid_score["incorrect"] is True
    assert invalid_score["invalid"] is True
    assert invalid_score["invalid_message"] == "Invalid value. Expected one of: 0, 1."

    data["panel"] = "submission"
    old_cwd = os.getcwd()
    try:
        os.chdir(Path(__file__).resolve().parent)
        rendered = json.loads(pl_waveform.render(element_html, data))
    finally:
        os.chdir(old_cwd)

    invalid_cell = rendered["result_rows"][0]["cells"][1]
    assert invalid_cell["submitted"] == "n"
    assert invalid_cell["has_submitted"] is True
    assert invalid_cell["incorrect"] is True
    assert invalid_cell["invalid"] is True
    assert invalid_cell["invalid_message"] == "Invalid value. Expected one of: 0, 1."


def test_blank_toggle_cell_only_zeros_that_cell() -> None:
    element_html = '<pl-waveform answers-name="part1"></pl-waveform>'
    data = {
        "params": {
            "signals": [
                {"name": "clk", "wave": "lP..", "editable": False},
                {
                    "name": "Q",
                    "prefix": "0",
                    "editable": True,
                    "correct_answers": ["1", "0", "1"],
                },
            ]
        },
        "correct_answers": {},
        "submitted_answers": {
            "part1_Q_1": "1",
            "part1_Q_2": "",
            "part1_Q_3": "0",
        },
        "partial_scores": {},
        "format_errors": {},
        "raw_submitted_answers": {
            "part1_Q_1": "1",
            "part1_Q_2": "",
            "part1_Q_3": "0",
        },
    }

    pl_waveform.prepare(element_html, data)
    pl_waveform.parse(element_html, data)
    pl_waveform.grade(element_html, data)

    assert data["partial_scores"]["part1_Q_1"]["score"] == 1
    assert data["partial_scores"]["part1_Q_2"]["score"] == 0
    assert data["partial_scores"]["part1_Q_3"]["score"] == 0

    data["panel"] = "submission"
    old_cwd = os.getcwd()
    try:
        os.chdir(Path(__file__).resolve().parent)
        rendered = json.loads(pl_waveform.render(element_html, data))
    finally:
        os.chdir(old_cwd)

    assert rendered["correct_count"] == 1
    assert rendered["total_cells"] == 3
    assert rendered["score_pct"] == 33
    cells = rendered["result_rows"][0]["cells"]
    assert cells[0]["correct"] is True
    assert cells[1]["unanswered"] is True
    assert cells[2]["incorrect"] is True


def test_editable_cells_track_absolute_wave_positions() -> None:
    signal = {
        "name": "Y",
        "wave": "0x.x",
        "correct_wave": "0101",
        "editable": True,
        "correct_answers": ["1", "1"],
        "period": 0.5,
    }

    cells = pl_waveform._editable_cells(signal, "part4")  # noqa: SLF001

    assert [cell["key"] for cell in cells] == ["part4_Y_1", "part4_Y_2"]
    assert [cell["abs_index"] for cell in cells] == [1, 3]


def test_render_question_includes_abs_index_metadata() -> None:
    element_html = '<pl-waveform answers-name="part4"></pl-waveform>'
    data = {
        "panel": "question",
        "editable": True,
        "params": {
            "signals": [
                {"name": "clk", "wave": "lP.", "editable": False},
                {
                    "name": "Y",
                    "wave": "0x.x",
                    "correct_wave": "0101",
                    "editable": True,
                    "correct_answers": ["1", "1"],
                    "period": 0.5,
                },
            ]
        },
        "submitted_answers": {},
        "raw_submitted_answers": {},
        "correct_answers": {},
        "partial_scores": {},
        "format_errors": {},
    }

    old_cwd = os.getcwd()
    try:
        os.chdir(Path(__file__).resolve().parent)
        rendered = json.loads(pl_waveform.render(element_html, data))
    finally:
        os.chdir(old_cwd)

    editable_cells = rendered["editable_rows"][0]["cells"]
    assert [cell["abs_index"] for cell in editable_cells] == [1, 3]
    assert all(cell["period"] == 0.5 for cell in editable_cells)


def test_render_text_mode_includes_allowed_value_hint() -> None:
    element_html = '<pl-waveform answers-name="part6" input-mode="text"></pl-waveform>'
    data = {
        "panel": "question",
        "editable": True,
        "params": {
            "signals": [
                {"name": "clk", "wave": "lP.", "editable": False},
                {
                    "name": "Y",
                    "prefix": "0",
                    "editable": True,
                    "correct_answers": ["1", "x"],
                    "allowed_values": ["0", "1", "x"],
                },
            ]
        },
        "submitted_answers": {},
        "raw_submitted_answers": {},
        "correct_answers": {},
        "partial_scores": {},
        "format_errors": {},
    }

    old_cwd = os.getcwd()
    try:
        os.chdir(Path(__file__).resolve().parent)
        rendered = json.loads(pl_waveform.render(element_html, data))
    finally:
        os.chdir(old_cwd)

    editable_cell = rendered["editable_rows"][0]["cells"][0]
    assert editable_cell["text_input_hint"] == "Type one of: 0, 1, x"
    assert json.loads(editable_cell["allowed_values_json"]) == ["0", "1", "x"]


def test_hex_allowed_values_grade_case_insensitively_and_display_canonical() -> None:
    hex_values = list("0123456789ABCDEF")
    element_html = '<pl-waveform answers-name="hex" input-mode="text"></pl-waveform>'
    data = {
        "params": {
            "signals": [
                {"name": "clk", "wave": "lP", "editable": False},
                {
                    "name": "rdata",
                    "editable": True,
                    "correct_answers": ["A", "F"],
                    "allowed_values": "hex",
                },
            ]
        },
        "correct_answers": {},
        "submitted_answers": {"hex_rdata_1": "a", "hex_rdata_2": "f"},
        "partial_scores": {},
        "format_errors": {},
        "raw_submitted_answers": {"hex_rdata_1": "a", "hex_rdata_2": "f"},
    }

    pl_waveform.prepare(element_html, data)
    pl_waveform.parse(element_html, data)
    pl_waveform.grade(element_html, data)

    assert data["correct_answers"] == {
        "hex_rdata_1": "A",
        "hex_rdata_2": "F",
    }
    assert json.loads(data["submitted_answers"]["hex_rdata_1"]) == "A"
    assert json.loads(data["submitted_answers"]["hex_rdata_2"]) == "F"
    assert data["partial_scores"]["hex_rdata_1"]["score"] == 1
    assert data["partial_scores"]["hex_rdata_2"]["score"] == 1

    data["panel"] = "submission"
    old_cwd = os.getcwd()
    try:
        os.chdir(Path(__file__).resolve().parent)
        rendered = json.loads(pl_waveform.render(element_html, data))
    finally:
        os.chdir(old_cwd)

    waveform = json.loads(rendered["wavedrom_json"])
    rdata = waveform["signal"][1]
    assert rdata["wave"] == "=="
    assert rdata["data"] == ["A", "F"]
    assert rendered["result_rows"][0]["cells"][0]["submitted"] == "A"


def test_render_question_hides_live_hex_bus_labels_but_keeps_bus_metadata() -> None:
    hex_values = list("0123456789ABCDEF")
    element_html = '<pl-waveform answers-name="hex" input-mode="text"></pl-waveform>'
    data = {
        "panel": "question",
        "editable": True,
        "params": {
            "signals": [
                {"name": "clk", "wave": "lP", "editable": False},
                {
                    "name": "rdata",
                    "editable": True,
                    "correct_answers": ["A", "F"],
                    "allowed_values": "hex",
                },
            ]
        },
        "submitted_answers": {},
        "raw_submitted_answers": {"hex_rdata_1": "a"},
        "correct_answers": {},
        "partial_scores": {},
        "format_errors": {},
    }

    old_cwd = os.getcwd()
    try:
        os.chdir(Path(__file__).resolve().parent)
        rendered = json.loads(pl_waveform.render(element_html, data))
    finally:
        os.chdir(old_cwd)

    waveform = json.loads(rendered["wavedrom_json"])
    rdata = waveform["signal"][1]
    assert rdata["wave"] == "=x"
    assert "data" not in rdata

    row_model = json.loads(rendered["editable_row_models_json"])[0]
    assert row_model["is_bus"] is True
    assert row_model["allowed_values"] == hex_values
    assert [cell["abs_index"] for cell in row_model["cells"]] == [0, 1]


def test_invalid_answer_value_raises() -> None:
    with pytest.raises(Exception, match="not in allowed_values"):
        pl_waveform._normalize_signals([  # noqa: SLF001
            {"name": "D", "correct_answers": ["0", "2"], "editable": True}
        ])
