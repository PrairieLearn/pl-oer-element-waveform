import importlib
import importlib.util
import json
import os
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ELEMENT_DIR = Path(__file__).resolve().parent
COURSE_DIR = ELEMENT_DIR.parent.parent

sys.modules.setdefault(
    "chevron",
    types.SimpleNamespace(render=lambda _template, params: json.dumps(params)),
)

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
    from_json=lambda value: (
        json.loads(value)
        if isinstance(value, str) and value[:1] in {'"', "[", "{"}
        else value
    ),
    to_json=lambda value: json.dumps(value),
    get_uuid=lambda: "test-uuid",
)

sys.modules.setdefault("prairielearn", pl_stub)

pl_waveform = importlib.import_module("pl-waveform")


def _normalize(signals):
    return pl_waveform._normalize_signals(signals)  # noqa: SLF001


def _base_data(
    signals,
    *,
    panel="question",
    submitted_answers=None,
    raw_submitted_answers=None,
):
    submitted_answers = submitted_answers or {}
    raw_submitted_answers = raw_submitted_answers or dict(submitted_answers)
    return {
        "panel": panel,
        "editable": True,
        "params": {"signals": signals},
        "correct_answers": {},
        "submitted_answers": dict(submitted_answers),
        "partial_scores": {},
        "format_errors": {},
        "raw_submitted_answers": dict(raw_submitted_answers),
    }


def _render(element_html, data):
    old_cwd = os.getcwd()
    try:
        os.chdir(ELEMENT_DIR)
        return json.loads(pl_waveform.render(element_html, data))
    finally:
        os.chdir(old_cwd)


def _prepare_parse_grade(element_html, data):
    pl_waveform.prepare(element_html, data)
    pl_waveform.parse(element_html, data)
    pl_waveform.grade(element_html, data)


def test_submission_template_exposes_read_only_waveform_feedback_metadata() -> None:
    template = (ELEMENT_DIR / "pl-waveform.mustache").read_text()

    assert 'class="pl-waveform pl-waveform-submission-view"' in template
    assert 'data-panel="submission"' in template
    assert 'data-parse-errors="{{parse_errors_json}}"' in template
    assert "data-cell-scores" in template
    assert 'type="WaveDrom"' in template


def test_values_encode_digital_holds_and_bus_labels() -> None:
    signals = _normalize(
        [
            {
                "name": "digital",
                "editable": False,
                "values": [0, 0, 1, 1, "z", "z", "x"],
            },
            {
                "name": "bus",
                "editable": False,
                "values": ["0", "ADDR", "ADDR", "0xFF"],
            },
        ]
    )

    assert signals[0]["wave"] == "0.1.z.x"
    assert "data" not in signals[0]
    assert signals[1]["wave"] == "==.="
    assert signals[1]["data"] == ["0", "ADDR", "0xFF"]


def test_wave_data_period_and_phase_are_preserved_for_reference_rows() -> None:
    signals = _normalize(
        [
            {
                "name": "addr",
                "editable": False,
                "wave": "=.=",
                "data": ["first", "second"],
                "period": 0.5,
                "phase": 0.5,
            }
        ]
    )
    waveform = json.loads(pl_waveform._build_wavedrom(signals, 1.5))  # noqa: SLF001

    assert waveform["signal"][0] == {
        "name": "addr",
        "wave": "=.=",
        "period": 0.5,
        "phase": 0.5,
        "data": ["first", "second"],
    }


def test_editable_values_create_placeholder_and_correct_wave() -> None:
    signal = _normalize(
        [
            {
                "name": "Q",
                "editable": True,
                "start_values": ["0"],
                "values": ["1", "1", "0"],
                "end_values": ["z"],
            }
        ]
    )[0]

    assert signal["wave"] == "0xxxz"
    assert signal["correct_answers"] == ["1", "1", "0"]
    assert signal["correct_wave"] == "01.0z"
    assert signal["correct_data"] == []


def test_segment_boundaries_use_holds_for_repeated_digital_states() -> None:
    signals = _normalize(
        [
            {
                "name": "ref",
                "editable": False,
                "start_values": ["0"],
                "values": ["0", "1"],
                "end_values": ["1"],
            },
            {
                "name": "Q",
                "editable": True,
                "start_values": ["0"],
                "values": ["1", "0"],
                "end_values": ["0"],
            },
        ]
    )

    assert signals[0]["wave"] == "0.1."
    assert signals[1]["correct_wave"] == "010."


def test_submission_render_uses_holds_at_fixed_end_boundaries() -> None:
    element_html = '<pl-waveform answers-name="timing"></pl-waveform>'
    data = _base_data(
        [
            {"name": "clk", "editable": False, "wave": "lP.."},
            {
                "name": "Q",
                "editable": True,
                "start_values": ["0"],
                "values": ["1", "0"],
                "end_values": ["0"],
            },
        ],
        panel="submission",
        submitted_answers={"timing_Q_1": "1", "timing_Q_2": "0"},
    )

    _prepare_parse_grade(element_html, data)
    rendered = _render(element_html, data)
    waveform = json.loads(rendered["wavedrom_json"])

    assert waveform["signal"][1]["wave"] == "010."


def test_segment_boundaries_use_holds_for_repeated_bus_values() -> None:
    signal = _normalize(
        [
            {
                "name": "op",
                "editable": True,
                "start_values": ["IDLE"],
                "values": ["IDLE", "LOAD"],
                "end_values": ["LOAD"],
                "allowed_values": ["IDLE", "LOAD"],
            }
        ]
    )[0]

    assert signal["correct_wave"] == "=.=."
    assert signal["correct_data"] == ["IDLE", "LOAD"]


def test_bus_values_force_digital_segments_to_render_as_buses() -> None:
    signals = _normalize(
        [
            {
                "name": "ref",
                "editable": False,
                "start_values": ["0"],
                "values": ["0", "LOAD"],
                "end_values": ["1"],
            },
            {
                "name": "Q",
                "editable": True,
                "start_values": ["0"],
                "values": ["1", "0"],
                "allowed_values": ["0", "1", "LOAD"],
            },
        ]
    )

    assert signals[0]["wave"] == "=.=="
    assert signals[0]["data"] == ["0", "LOAD", "1"]
    assert signals[1]["wave"] == "=xx"
    assert signals[1]["data"] == ["0"]
    assert signals[1]["correct_wave"] == "==="
    assert signals[1]["correct_data"] == ["0", "1", "0"]


def test_submission_renders_digital_answers_as_bus_when_allowed_values_are_bus() -> None:
    element_html = '<pl-waveform answers-name="bus"></pl-waveform>'
    data = _base_data(
        [
            {
                "name": "Q",
                "editable": True,
                "start_values": ["0"],
                "values": ["1", "0"],
                "allowed_values": ["0", "1", "LOAD"],
            },
        ],
        panel="submission",
        submitted_answers={"bus_Q_1": "1", "bus_Q_2": "0"},
    )

    _prepare_parse_grade(element_html, data)
    rendered = _render(element_html, data)
    waveform = json.loads(rendered["wavedrom_json"])

    assert waveform["signal"][0]["wave"] == "==="
    assert waveform["signal"][0]["data"] == ["0", "1", "0"]


def test_editable_z_is_inferred_as_a_digital_allowed_value() -> None:
    element_html = '<pl-waveform answers-name="tri"></pl-waveform>'
    data = _base_data(
        [{"name": "Y", "editable": True, "values": ["z", "z", "1"]}],
        submitted_answers={"tri_Y_1": "Z", "tri_Y_2": "z", "tri_Y_3": "1"},
    )
    signal = _normalize(data["params"]["signals"])[0]

    assert signal["correct_wave"] == "z.1"
    assert pl_waveform._get_allowed_values(signal) == ["0", "1", "z"]  # noqa: SLF001
    assert signal["is_bus"] is False

    _prepare_parse_grade(element_html, data)

    assert data["correct_answers"] == {
        "tri_Y_1": "z",
        "tri_Y_2": "z",
        "tri_Y_3": "1",
    }
    assert json.loads(data["submitted_answers"]["tri_Y_1"]) == "z"
    assert all(score["score"] == 1 for score in data["partial_scores"].values())


def test_text_input_invalid_values_report_format_errors_during_parse() -> None:
    element_html = '<pl-waveform answers-name="timing" input-mode="text"></pl-waveform>'
    data = _base_data(
        [
            {"name": "clk", "editable": False, "wave": "lP.."},
            {
                "name": "Q",
                "editable": True,
                "start_values": ["0"],
                "values": ["1", "0", "0"],
            },
        ],
        submitted_answers={
            "timing_Q_1": "1",
            "timing_Q_2": "n",
            "timing_Q_3": "0",
        },
    )

    pl_waveform.prepare(element_html, data)
    pl_waveform.parse(element_html, data)

    invalid_message = "Invalid value. Expected binary."
    assert data["correct_answers"] == {
        "timing_Q_1": "1",
        "timing_Q_2": "0",
        "timing_Q_3": "0",
    }
    assert data["format_errors"] == {"timing_Q_2": invalid_message}
    assert data["partial_scores"] == {}

    rendered_question = _render(element_html, data)
    assert json.loads(rendered_question["parse_errors_json"]) == {
        "timing_Q_2": invalid_message
    }
    assert json.loads(rendered_question["parse_error_cells_json"]) == [
        {
            "key": "timing_Q_2",
            "signal_name": "Q",
            "cycle_num": 2,
            "abs_index": 2,
            "period": 1,
            "message": invalid_message,
        }
    ]
    assert rendered_question["has_parse_errors"] is True
    assert rendered_question["has_cell_scores"] is False
    assert json.loads(rendered_question["cell_scores_json"]) == []

    data["panel"] = "submission"
    rendered = _render(element_html, data)

    assert json.loads(rendered["parse_errors_json"]) == {"timing_Q_2": invalid_message}
    assert json.loads(rendered["parse_error_cells_json"]) == [
        {
            "key": "timing_Q_2",
            "signal_name": "Q",
            "cycle_num": 2,
            "abs_index": 2,
            "period": 1,
            "message": invalid_message,
        }
    ]
    assert rendered["has_parse_errors"] is True
    assert rendered["has_cell_scores"] is False
    assert json.loads(rendered["cell_scores_json"]) == []
    assert rendered["correct_count"] == 0
    assert rendered["total_cells"] == 3
    invalid_cell = rendered["result_rows"][0]["cells"][1]
    assert invalid_cell["submitted"] == "n"
    assert invalid_cell["incorrect"] is False
    assert invalid_cell["invalid"] is True
    assert invalid_cell["invalid_message"] == invalid_message


def test_blank_cells_report_format_errors_during_parse() -> None:
    element_html = '<pl-waveform answers-name="part1"></pl-waveform>'
    data = _base_data(
        [
            {"name": "clk", "editable": False, "wave": "lP.."},
            {
                "name": "Q",
                "editable": True,
                "start_values": ["0"],
                "values": ["1", "0", "1"],
            },
        ],
        panel="submission",
        submitted_answers={
            "part1_Q_1": "1",
            "part1_Q_2": "",
            "part1_Q_3": "0",
        },
    )

    _prepare_parse_grade(element_html, data)
    rendered = _render(element_html, data)

    invalid_message = "Invalid value. Expected binary."
    assert data["format_errors"] == {"part1_Q_2": invalid_message}
    assert data["partial_scores"] == {}
    assert rendered["has_parse_errors"] is True
    assert rendered["has_cell_scores"] is False
    assert json.loads(rendered["parse_errors_json"]) == {"part1_Q_2": invalid_message}
    assert rendered["correct_count"] == 0
    assert rendered["total_cells"] == 3
    cells = rendered["result_rows"][0]["cells"]
    assert cells[0]["correct"] is False
    assert cells[1]["unanswered"] is True
    assert cells[1]["invalid"] is True
    assert cells[1]["incorrect"] is False
    assert cells[2]["incorrect"] is False


def test_submission_feedback_uses_question_panel_score_metadata() -> None:
    element_html = '<pl-waveform answers-name="part1" feedback="element"></pl-waveform>'
    data = _base_data(
        [
            {"name": "clk", "editable": False, "wave": "lP.."},
            {
                "name": "Q",
                "editable": True,
                "start_values": ["0"],
                "values": ["1", "0", "1"],
            },
        ],
        panel="submission",
        submitted_answers={
            "part1_Q_1": "1",
            "part1_Q_2": "1",
            "part1_Q_3": "0",
        },
    )

    _prepare_parse_grade(element_html, data)
    rendered = _render(element_html, data)
    cell_scores = json.loads(rendered["cell_scores_json"])

    assert rendered["feedback"] == "element"
    assert rendered["input_mode"] == "toggle"
    assert rendered["has_cell_scores"] is True
    assert len(cell_scores) == 3
    assert sum(1 for cell in cell_scores if cell["correct"]) == 1
    assert rendered["correct_count"] == 1
    assert rendered["total_cells"] == 3
    assert rendered["score_pct"] == 33


def test_none_feedback_hides_score_metadata_in_question_and_submission() -> None:
    element_html = '<pl-waveform answers-name="part1" feedback="none"></pl-waveform>'
    signals = [
        {"name": "clk", "editable": False, "wave": "lP"},
        {"name": "Q", "editable": True, "values": ["1", "0"]},
    ]
    data = _base_data(
        signals,
        submitted_answers={"part1_Q_1": "1", "part1_Q_2": "1"},
    )
    _prepare_parse_grade(element_html, data)

    question_rendered = _render(element_html, data)
    data["panel"] = "submission"
    submission_rendered = _render(element_html, data)

    assert question_rendered["feedback"] == "none"
    assert question_rendered["has_cell_scores"] is False
    assert json.loads(question_rendered["cell_scores_json"])
    assert submission_rendered["submission"] is True
    assert submission_rendered["feedback"] == "none"
    assert submission_rendered["has_cell_scores"] is False
    assert json.loads(submission_rendered["cell_scores_json"])


def test_question_render_exposes_editable_cell_metadata() -> None:
    element_html = '<pl-waveform answers-name="part4"></pl-waveform>'
    data = _base_data(
        [
            {"name": "clk", "editable": False, "wave": "lP.."},
            {
                "name": "Y",
                "editable": True,
                "start_values": ["0"],
                "values": ["1", "1"],
                "end_values": ["0"],
            },
        ]
    )

    rendered = _render(element_html, data)

    editable_cells = rendered["editable_rows"][0]["cells"]
    assert [cell["key"] for cell in editable_cells] == ["part4_Y_1", "part4_Y_2"]
    assert [cell["abs_index"] for cell in editable_cells] == [1, 2]
    assert [cell["period"] for cell in editable_cells] == [1, 1]


def test_toggle_question_initial_x_matches_toggled_x() -> None:
    element_html = '<pl-waveform answers-name="part5"></pl-waveform>'
    data = _base_data(
        [
            {"name": "clk", "editable": False, "wave": "lP"},
            {"name": "Y", "editable": True, "values": ["x"]},
        ]
    )

    rendered = _render(element_html, data)
    editable_cell = rendered["editable_rows"][0]["cells"][0]
    row_model = json.loads(rendered["editable_row_models_json"])[0]

    assert editable_cell["toggle_value"] == "x"
    assert editable_cell["raw_value"] == "x"
    assert row_model["cells"][0]["value"] == "x"
    assert row_model["cells"][0]["is_x"] is True


def test_text_question_initial_x_allowed_still_renders_blank() -> None:
    element_html = '<pl-waveform answers-name="part5" input-mode="text"></pl-waveform>'
    data = _base_data(
        [
            {"name": "clk", "editable": False, "wave": "lP"},
            {"name": "Y", "editable": True, "values": ["x"]},
        ]
    )

    rendered = _render(element_html, data)
    editable_cell = rendered["editable_rows"][0]["cells"][0]
    row_model = json.loads(rendered["editable_row_models_json"])[0]

    assert editable_cell["has_raw_value"] is False
    assert editable_cell["raw_value"] == ""
    assert row_model["cells"][0]["value"] == ""


def test_parse_clears_stale_format_error_after_valid_submission() -> None:
    element_html = '<pl-waveform answers-name="part1" input-mode="text"></pl-waveform>'
    data = _base_data(
        [
            {"name": "Q", "editable": True, "values": ["1"]},
        ],
        submitted_answers={"part1_Q_1": "1"},
    )
    data["format_errors"]["part1_Q_1"] = "old error"

    pl_waveform.prepare(element_html, data)
    pl_waveform.parse(element_html, data)

    assert data["format_errors"] == {}
    assert json.loads(data["submitted_answers"]["part1_Q_1"]) == "1"


def test_editable_rows_support_period_metadata_and_duration() -> None:
    element_html = '<pl-waveform answers-name="half" input-mode="text"></pl-waveform>'
    data = _base_data(
        [
            {"name": "clk", "editable": False, "wave": "lP"},
            {
                "name": "Y",
                "editable": True,
                "values": ["0", "1", "1", "0"],
                "period": 0.5,
            },
        ]
    )

    pl_waveform.prepare(element_html, data)
    rendered = _render(element_html, data)
    waveform = json.loads(rendered["wavedrom_json"])
    editable_cells = rendered["editable_rows"][0]["cells"]
    row_model = json.loads(rendered["editable_row_models_json"])[0]

    assert waveform["signal"][1]["period"] == 0.5
    assert [cell["period"] for cell in editable_cells] == [0.5, 0.5, 0.5, 0.5]
    assert row_model["period"] == 0.5


def test_array_signal_name_preserves_wavedrom_display_and_uses_text_key() -> None:
    formatted_name = [
        "tspan",
        ["tspan", {"class": "info h5"}, "DATA"],
        " ",
        ["tspan", {"class": "error", "baseline-shift": "sub"}, "out"],
        " ",
        [
            "tspan",
            {"fill": "pink", "font-weight": "bold", "font-style": "italic"},
            "inv",
        ],
    ]
    element_html = '<pl-waveform answers-name="fmt"></pl-waveform>'
    data = _base_data(
        [
            {"name": "clk", "editable": False, "wave": "lP"},
            {
                "name": formatted_name,
                "editable": True,
                "values": ["1", "0"],
            },
        ]
    )

    pl_waveform.prepare(element_html, data)
    rendered = _render(element_html, data)
    waveform = json.loads(rendered["wavedrom_json"])
    row_model = json.loads(rendered["editable_row_models_json"])[0]

    assert waveform["signal"][1]["name"] == formatted_name
    assert data["correct_answers"] == {
        "fmt_DATA_out_inv_1": "1",
        "fmt_DATA_out_inv_2": "0",
    }
    assert rendered["editable_rows"][0]["signal_name"] == "DATA out inv"
    assert row_model["signal_key"] == "DATA_out_inv"
    assert row_model["signal_name"] == "DATA out inv"
    assert row_model["display_name"] == formatted_name


def test_text_mode_metadata_supports_single_and_multicharacter_values() -> None:
    element_html = '<pl-waveform answers-name="decode" input-mode="text"></pl-waveform>'
    data = _base_data(
        [
            {"name": "opcode", "editable": False, "values": ["00"]},
            {
                "name": "operation",
                "editable": True,
                "values": ["LOAD"],
                "allowed_values": ["IDLE", "LOAD", "STORE", "HOLD"],
            },
        ]
    )

    rendered = _render(element_html, data)
    editable_cell = rendered["editable_rows"][0]["cells"][0]
    row_model = json.loads(rendered["editable_row_models_json"])[0]

    assert editable_cell["text_input_maxlength"] == len("STORE")
    assert editable_cell["text_input_hint"] == "Type one of: IDLE, LOAD, STORE, HOLD"
    assert row_model["is_bus"] is True
    assert row_model["allowed_values"] == ["IDLE", "LOAD", "STORE", "HOLD"]


def test_text_mode_metadata_labels_exact_binary_values_compactly() -> None:
    element_html = '<pl-waveform answers-name="binary" input-mode="text"></pl-waveform>'
    data = _base_data(
        [
            {"name": "Q", "editable": True, "values": ["0", "1"]},
            {
                "name": "wide",
                "editable": True,
                "values": ["10", "01"],
                "bus_width": 2,
            },
            {
                "name": "reversed",
                "editable": True,
                "values": ["1", "0"],
                "allowed_values": ["1", "0"],
            },
            {
                "name": "with_x",
                "editable": True,
                "values": ["1", "0"],
                "allowed_values": ["0", "1", "x"],
            },
        ]
    )

    rendered = _render(element_html, data)
    rows = rendered["editable_rows"]

    assert rows[0]["cells"][0]["text_input_hint"] == "Type a binary value"
    assert rows[0]["cells"][0]["allowed_values_label"] == "binary"
    assert rows[1]["cells"][0]["text_input_hint"] == "Type 2 binary characters"
    assert rows[1]["cells"][0]["allowed_values_label"] == "binary"
    assert rows[2]["cells"][0]["text_input_hint"] == "Type a binary value"
    assert rows[2]["cells"][0]["allowed_values_label"] == "binary"
    assert rows[3]["cells"][0]["text_input_hint"] == "Type one of: 0, 1, x"
    assert rows[3]["cells"][0]["allowed_values_label"] == "0, 1, x"


def test_hex_allowed_values_grade_case_insensitively_and_render_as_bus() -> None:
    element_html = '<pl-waveform answers-name="hex" input-mode="text"></pl-waveform>'
    data = _base_data(
        [
            {"name": "clk", "editable": False, "wave": "lP"},
            {
                "name": "rdata",
                "editable": True,
                "values": ["A", "F"],
                "allowed_values": "hex",
            },
        ],
        panel="submission",
        submitted_answers={"hex_rdata_1": "a", "hex_rdata_2": "f"},
    )

    _prepare_parse_grade(element_html, data)
    rendered = _render(element_html, data)
    waveform = json.loads(rendered["wavedrom_json"])

    assert data["correct_answers"] == {
        "hex_rdata_1": "A",
        "hex_rdata_2": "F",
    }
    assert json.loads(data["submitted_answers"]["hex_rdata_1"]) == "A"
    assert json.loads(data["submitted_answers"]["hex_rdata_2"]) == "F"
    assert data["partial_scores"]["hex_rdata_1"]["score"] == 1
    assert data["partial_scores"]["hex_rdata_2"]["score"] == 1
    assert waveform["signal"][1]["wave"] == "=="
    assert waveform["signal"][1]["data"] == ["A", "F"]
    assert rendered["result_rows"][0]["cells"][0]["submitted"] == "A"

    data["panel"] = "question"
    rendered_question = _render(element_html, data)
    assert rendered_question["editable_rows"][0]["cells"][0]["text_input_hint"] == (
        "Type a hexadecimal value"
    )


def test_bus_width_uses_allowed_values_as_a_character_alphabet() -> None:
    element_html = '<pl-waveform answers-name="wide" input-mode="text"></pl-waveform>'
    data = _base_data(
        [
            {
                "name": "byte",
                "editable": True,
                "values": ["DE", "AD"],
                "allowed_values": "hex",
                "bus_width": 2,
            },
        ],
        panel="submission",
        submitted_answers={"wide_byte_1": "de", "wide_byte_2": "ad"},
    )

    _prepare_parse_grade(element_html, data)
    rendered = _render(element_html, data)
    waveform = json.loads(rendered["wavedrom_json"])

    assert data["correct_answers"] == {
        "wide_byte_1": "DE",
        "wide_byte_2": "AD",
    }
    assert json.loads(data["submitted_answers"]["wide_byte_1"]) == "DE"
    assert data["partial_scores"]["wide_byte_1"]["score"] == 1
    assert waveform["signal"][0]["wave"] == "=="
    assert waveform["signal"][0]["data"] == ["DE", "AD"]
    assert rendered["result_rows"][0]["cells"][0]["submitted"] == "DE"

    data["panel"] = "question"
    rendered_question = _render(element_html, data)
    assert rendered_question["editable_rows"][0]["cells"][0]["text_input_hint"] == (
        "Type 2 hexadecimal characters"
    )


@pytest.mark.parametrize(
    ("submitted", "message"),
    [
        ("D", "Expected 2 hexadecimal characters"),
        ("DOG", "Expected 2 hexadecimal characters"),
        ("DG", "Expected 2 hexadecimal characters"),
        ("", "Expected 2 hexadecimal characters"),
    ],
)
def test_bus_width_invalid_text_values_report_format_errors(
    submitted, message
) -> None:
    element_html = '<pl-waveform answers-name="wide" input-mode="text"></pl-waveform>'
    data = _base_data(
        [
            {
                "name": "byte",
                "editable": True,
                "values": ["DE"],
                "allowed_values": "hex",
                "bus_width": 2,
            },
        ],
        submitted_answers={"wide_byte_1": submitted},
    )

    pl_waveform.prepare(element_html, data)
    pl_waveform.parse(element_html, data)

    assert "wide_byte_1" in data["format_errors"]
    assert message in data["format_errors"]["wide_byte_1"]
    assert data["partial_scores"] == {}


def test_bus_width_requires_text_input_mode() -> None:
    element_html = '<pl-waveform answers-name="wide"></pl-waveform>'
    data = _base_data(
        [
            {
                "name": "byte",
                "editable": True,
                "values": ["DE"],
                "allowed_values": "hex",
                "bus_width": 2,
            },
        ],
    )

    with pytest.raises(Exception, match='input-mode="text"'):
        pl_waveform.prepare(element_html, data)


@pytest.mark.parametrize(
    ("signal", "message"),
    [
        (
            {
                "name": "D",
                "editable": True,
                "values": ["0", "2"],
                "allowed_values": ["0", "1"],
            },
            "not in allowed_values",
        ),
        (
            {
                "name": "D",
                "editable": True,
                "values": ["0", "1"],
                "allowed_values": ["0", "1", "1"],
            },
            "repeats allowed_values",
        ),
        (
            {"name": "D", "editable": False, "values": [0, 1, 2]},
            "only integer 0 and 1",
        ),
        (
            {
                "name": "D",
                "editable": True,
                "values": ["0", "2"],
                "allowed_values": [0, 1, 2],
            },
            "only integer 0 and 1",
        ),
        (
            {"name": "D", "editable": True, "values": ["0", "1"], "phase": 0.5},
            "cannot define 'phase'",
        ),
        (
            {"name": "D", "editable": True, "wave": "01"},
            "cannot define 'wave'",
        ),
        (
            {
                "name": "D",
                "editable": True,
                "values": ["10"],
                "bus_width": 0,
            },
            "positive integer",
        ),
        (
            {
                "name": "D",
                "editable": True,
                "values": ["10"],
                "bus_width": 2,
                "allowed_values": ["0", "10"],
            },
            "must be a single character",
        ),
        (
            {
                "name": "D",
                "editable": True,
                "values": ["10", "1"],
                "bus_width": 2,
            },
            "expected bus_width 2",
        ),
        (
            {
                "name": "D",
                "editable": False,
                "wave": "01",
                "values": ["0", "1"],
            },
            "cannot mix",
        ),
        (
            {
                "name": "D",
                "editable": False,
                "wave": "==",
                "data": ["only-one"],
            },
            "wave expects 2",
        ),
    ],
)
def test_invalid_signal_definitions_are_rejected(signal, message) -> None:
    with pytest.raises(Exception, match=message):
        _normalize([signal])


def test_unknown_feedback_mode_is_rejected() -> None:
    element_html = '<pl-waveform answers-name="part1" feedback="summary"></pl-waveform>'
    data = _base_data([{"name": "D", "editable": False, "values": [0]}])

    with pytest.raises(Exception, match="invalid feedback"):
        pl_waveform.prepare(element_html, data)


def test_waveform_demo_signal_sets_match_the_current_element_contract() -> None:
    spec = importlib.util.spec_from_file_location(
        "waveform_demo_server", COURSE_DIR / "questions/waveformDemo/server.py"
    )
    demo_server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo_server)

    data = {"params": {}}
    demo_server.generate(data)

    validated = 0
    answer_keys = 0
    for key, signals in data["params"].items():
        if not (
            isinstance(signals, list)
            and all(isinstance(sig, dict) and "name" in sig for sig in signals)
        ):
            continue
        normalized = _normalize(signals)
        pl_waveform._validate_signals(normalized, key)  # noqa: SLF001
        validated += 1
        answer_keys += sum(
            len(sig.get("correct_answers", []))
            for sig in normalized
            if sig.get("editable")
        )

    assert validated == 10
    assert answer_keys == 73
