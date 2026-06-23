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


def test_submission_template_renders_waveform_without_card_or_label_header() -> None:
    template = (ELEMENT_DIR / "pl-waveform.mustache").read_text()

    assert "pl-waveform-submission-section" not in template
    assert "pl-waveform-submission-header" not in template
    assert "pl-waveform-submission-label" not in template
    assert "{{#label}}" not in template
    assert "data-cell-scores" in template
    assert "data-feedback-element" not in template
    assert "data-feedback-rows" not in template
    assert "fb_table" not in template


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
    assert signals[1]["wave"] == "0=.="
    assert signals[1]["data"] == ["ADDR", "0xFF"]


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


def test_editable_z_is_inferred_as_a_digital_allowed_value() -> None:
    element_html = '<pl-waveform answers-name="tri"></pl-waveform>'
    data = _base_data(
        [{"name": "Y", "editable": True, "values": ["z", "z", "1"]}],
        submitted_answers={"tri_Y_1": "Z", "tri_Y_2": "z", "tri_Y_3": "1"},
    )
    signal = _normalize(data["params"]["signals"])[0]

    assert signal["correct_wave"] == "z.1"
    assert pl_waveform._get_allowed_values(signal) == ["0", "1", "z"]  # noqa: SLF001
    assert pl_waveform._uses_bus_rendering(signal) is False  # noqa: SLF001

    _prepare_parse_grade(element_html, data)

    assert data["correct_answers"] == {
        "tri_Y_1": "z",
        "tri_Y_2": "z",
        "tri_Y_3": "1",
    }
    assert json.loads(data["submitted_answers"]["tri_Y_1"]) == "z"
    assert all(score["score"] == 1 for score in data["partial_scores"].values())


def test_prepare_parse_grade_scores_and_reports_invalid_cells() -> None:
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

    _prepare_parse_grade(element_html, data)

    assert data["correct_answers"] == {
        "timing_Q_1": "1",
        "timing_Q_2": "0",
        "timing_Q_3": "0",
    }
    assert data["format_errors"] == {}
    assert data["partial_scores"]["timing_Q_1"]["score"] == 1
    assert data["partial_scores"]["timing_Q_2"]["score"] == 0
    assert data["partial_scores"]["timing_Q_3"]["score"] == 1

    data["panel"] = "submission"
    rendered = _render(element_html, data)

    assert rendered["correct_count"] == 2
    assert rendered["total_cells"] == 3
    invalid_cell = rendered["result_rows"][0]["cells"][1]
    assert invalid_cell["submitted"] == "n"
    assert invalid_cell["incorrect"] is True
    assert invalid_cell["invalid"] is True
    assert invalid_cell["invalid_message"] == "Invalid value. Expected one of: 0, 1."


def test_unanswered_cells_score_zero_without_invalid_feedback() -> None:
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

    assert rendered["correct_count"] == 1
    assert rendered["total_cells"] == 3
    assert rendered["score_pct"] == 33
    cells = rendered["result_rows"][0]["cells"]
    assert cells[0]["correct"] is True
    assert cells[1]["unanswered"] is True
    assert cells[1]["invalid"] is False
    assert cells[2]["incorrect"] is True


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
        ["tspan", {"fill": "#0d6efd", "font-weight": "bold"}, "DATA"],
        " ",
        ["tspan", {"fill": "#dc3545", "baseline-shift": "sub"}, "out"],
        " ",
        ["tspan", {"fill": "#198754", "font-style": "italic"}, "inv"],
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

    assert waveform["signal"][1]["name"] == "<b>DATA</b> <sub>out</sub> <i>inv</i>"
    assert data["correct_answers"] == {
        "fmt_DATA_out_inv_1": "1",
        "fmt_DATA_out_inv_2": "0",
    }
    assert rendered["editable_rows"][0]["signal_name"] == "DATA out inv"
    assert row_model["signal_key"] == "DATA_out_inv"
    assert row_model["signal_name"] == "DATA out inv"
    assert row_model["display_name"] == "<b>DATA</b> <sub>out</sub> <i>inv</i>"
    assert json.loads(rendered["formatted_names_json"]) == [
        {
            "label": "DATA out inv",
            "rendered_name": "<b>DATA</b> <sub>out</sub> <i>inv</i>",
            "name": formatted_name,
        }
    ]


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


def test_old_table_feedback_mode_is_rejected() -> None:
    element_html = '<pl-waveform answers-name="part1" feedback="table"></pl-waveform>'
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

    assert validated == 9
    assert answer_keys == 65
