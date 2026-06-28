import random


HEX_VALUES = list("0123456789ABCDEF")


def _make_dff(iters):
    values = ["0", "1"]
    d_values = random.choices(values, k=iters)
    q_answers = []

    for i in range(1, len(d_values)):
        if i % 2 == 1 and i != len(d_values) - 1:
            q_answers.append(d_values[i])

    return d_values, q_answers


def _encode_bus(values):
    wave = ["="]
    data = [values[0]]
    for idx in range(1, len(values)):
        if values[idx] == values[idx - 1]:
            wave.append(".")
        else:
            wave.append("=")
            data.append(values[idx])
    return "".join(wave), data


def generate(data):
    binary_values = ["0", "1"]
    opcode_labels = {
        "00": "IDLE",
        "01": "LOAD",
        "10": "STORE",
        "11": "HOLD",
    }

    d_values, q_answers = _make_dff(12)
    data["params"]["signals"] = [
        {"name": "clk", "editable": False, "wave": "lP...."},
        {"name": "D", "editable": False, "values": d_values, "period": 0.5},
        {
            "name": "Q",
            "editable": True,
            "start_values": ["0"],
            "values": q_answers,
        },
    ]

    j_values = random.choices(binary_values, k=16)
    k_values = random.choices(binary_values, k=16)
    q_state = "0"
    q_values = []
    q_bar_values = []

    for i in range(1, len(j_values)):
        if i % 2 == 1 and i != len(j_values) - 1:
            j_value = j_values[i]
            k_value = k_values[i]

            if j_value == "0" and k_value == "1":
                q_state = "0"
            elif j_value == "1" and k_value == "0":
                q_state = "1"
            elif j_value == "1" and k_value == "1":
                q_state = "1" if q_state == "0" else "0"

            q_values.append(q_state)
            q_bar_values.append("1" if q_state == "0" else "0")

    data["params"]["jk_signals"] = [
        {"name": "clk", "editable": False, "wave": "lP......"},
        {"name": "J", "editable": False, "values": j_values, "period": 0.5},
        {"name": "K", "editable": False, "values": k_values, "period": 0.5},
        {
            "name": "Q",
            "editable": True,
            "start_values": ["0"],
            "values": q_values,
        },
        {
            "name": "Q'",
            "editable": True,
            "start_values": ["1"],
            "values": q_bar_values,
        },
    ]

    d_enable_values = random.choices(binary_values, k=12)
    enable_values = random.choices(binary_values, weights=[1, 2], k=12)
    q_enable_state = "0"
    q_enable_answers = []

    for i in range(1, len(d_enable_values)):
        if i % 2 == 1 and i != len(d_enable_values) - 1:
            if enable_values[i] == "1":
                q_enable_state = d_enable_values[i]
            q_enable_answers.append(q_enable_state)

    data["params"]["enable_signals"] = [
        {"name": "clk", "editable": False, "wave": "lP...."},
        {"name": "D", "editable": False, "values": d_enable_values, "period": 0.5},
        {"name": "EN", "editable": False, "values": enable_values, "period": 0.5},
        {
            "name": "Q",
            "editable": True,
            "start_values": ["0"],
            "values": q_enable_answers,
        },
    ]

    a_values = random.choices(binary_values, k=8)
    b_values = random.choices(binary_values, k=8)
    y_values = [
        "1" if a_value == "1" and b_value == "1" else "0"
        for a_value, b_value in zip(a_values, b_values)
    ]

    data["params"]["and_signals"] = [
        {"name": "clk", "editable": False, "wave": "lP.."},
        {"name": "A", "editable": False, "values": a_values, "period": 0.5},
        {"name": "B", "editable": False, "values": b_values, "period": 0.5},
        {
            "name": "Y",
            "editable": True,
            "values": y_values,
            "period": 0.5,
        },
    ]

    d_tri_values = random.choices(binary_values, k=12)
    en_tri_values = random.choices(binary_values, weights=[1, 2], k=12)
    en_tri_values[0] = "1"
    y_tri_answers = []

    for i in range(1, len(d_tri_values)):
        if i % 2 == 1 and i != len(d_tri_values) - 1:
            y_tri_answers.append(d_tri_values[i] if en_tri_values[i] == "1" else "z")

    data["params"]["tristate_signals"] = [
        {"name": "clk", "editable": False, "wave": "lP...."},
        {"name": "EN", "editable": False, "values": en_tri_values, "period": 0.5},
        {"name": "D", "editable": False, "values": d_tri_values, "period": 0.5},
        {
            "name": "Y",
            "editable": True,
            "start_values": [d_tri_values[0]],
            "values": y_tri_answers,
            "allowed_values": ["0", "1", "z", "x"],
        },
    ]

    register_values = random.choices(HEX_VALUES, k=4)
    for reg_idx, value in enumerate(register_values):
        data["params"][f"reg{reg_idx}"] = value

    raddr_a_values = random.choices(["0", "1", "2", "3"], k=8)
    raddr_b_values = random.choices(["0", "1", "2", "3"], k=8)
    rdata_a_values = [register_values[int(addr)] for addr in raddr_a_values]
    rdata_b_values = [register_values[int(addr)] for addr in raddr_b_values]
    raddr_a_wave, raddr_a_data = _encode_bus(raddr_a_values)
    raddr_b_wave, raddr_b_data = _encode_bus(raddr_b_values)

    data["params"]["reg_read_signals"] = [
        {"name": "clk", "editable": False, "wave": "lP......"},
        {
            "name": "raddrA",
            "editable": False,
            "wave": raddr_a_wave,
            "data": raddr_a_data,
            "phase": 0.5,
        },
        {
            "name": "raddrB",
            "editable": False,
            "wave": raddr_b_wave,
            "data": raddr_b_data,
            "phase": 0.5,
        },
        {
            "name": "rdataA",
            "editable": True,
            "values": rdata_a_values,
            "allowed_values": "hex",
        },
        {
            "name": "rdataB",
            "editable": True,
            "values": rdata_b_values,
            "allowed_values": "hex",
        },
    ]

    data["params"]["mixed_signals"] = [
        {"name": "clk", "editable": False, "wave": "lP....."},
        {"name": "in", "editable": False, "wave": "01.0.10"},
        {
            "name": "out",
            "editable": True,
            "start_values": ["0", "1"],
            "values": ["1", "0", "1"],
            "end_values": ["1", "0"],
        },
    ]

    opcode_values = random.choices(list(opcode_labels), k=5)
    data["params"]["decode_signals"] = [
        {"name": "opcode", "editable": False, "values": opcode_values},
        {
            "name": "operation",
            "editable": True,
            "values": [opcode_labels[opcode] for opcode in opcode_values],
            "allowed_values": list(opcode_labels.values()),
        },
    ]

    nibble_values = ["".join(random.choices(binary_values, k=4)) for _ in range(4)]
    hex_byte_values = ["".join(random.choices(HEX_VALUES, k=2)) for _ in range(4)]
    data["params"]["fixed_width_signals"] = [
        {
            "name": "bin[3:0]",
            "editable": True,
            "values": nibble_values,
            "bus_width": 4,
        },
        {
            "name": "hex[7:0]",
            "editable": True,
            "values": hex_byte_values,
            "allowed_values": "hex",
            "bus_width": 2,
        },
    ]

    formatted_input_values = random.choices(binary_values, k=4)
    formatted_output_values = [
        "1" if value == "0" else "0" for value in formatted_input_values
    ]
    data["params"]["formatted_name_signals"] = [
        {"name": "clk", "editable": False, "wave": "lP.."},
        {"name": "input", "editable": False, "values": formatted_input_values},
        {
            "name": [
                "tspan",
                ["tspan", {"class": "info h5"}, "DATA"],
                " ",
                ["tspan", {"class": "error", "baseline-shift": "sub"}, "out"],
                " ",
                [
                    "tspan",
                    {
                        "fill": "pink",
                        "font-weight": "bold",
                        "font-style": "italic",
                    },
                    "inv",
                ],
            ],
            "editable": True,
            "values": formatted_output_values,
        },
    ]

    data["params"]["hscale"] = 1.5
    return data
