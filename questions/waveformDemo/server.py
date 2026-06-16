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

    d_values, q_answers = _make_dff(12)
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
        {"name": "clk", "wave": "lP......", "editable": False},
        {"name": "J", "values": j_values, "period": 0.5, "editable": False},
        {"name": "K", "values": k_values, "period": 0.5, "editable": False},
        {
            "name": "Q",
            "initial": "0",
            "editable": True,
            "correct_answers": q_values,
        },
        {
            "name": "Q'",
            "initial": "1",
            "editable": True,
            "correct_answers": q_bar_values,
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
        {"name": "clk", "wave": "lP....", "editable": False},
        {"name": "D", "values": d_enable_values, "period": 0.5, "editable": False},
        {"name": "EN", "values": enable_values, "period": 0.5, "editable": False},
        {
            "name": "Q",
            "initial": "0",
            "editable": True,
            "correct_answers": q_enable_answers,
        },
    ]

    a_values = random.choices(binary_values, k=8)
    b_values = random.choices(binary_values, k=8)
    y_values = [
        "1" if a_value == "1" and b_value == "1" else "0"
        for a_value, b_value in zip(a_values, b_values)
    ]

    data["params"]["and_signals"] = [
        {"name": "clk", "wave": "lP..", "editable": False},
        {"name": "A", "values": a_values, "period": 0.5, "editable": False},
        {"name": "B", "values": b_values, "period": 0.5, "editable": False},
        {
            "name": "Y",
            "initial": y_values[0],
            "editable": True,
            "correct_answers": y_values[1:],
            "period": 0.5,
        },
    ]

    d_tri_values = random.choices(binary_values, k=12)
    en_tri_values = random.choices(binary_values, weights=[1, 2], k=12)
    en_tri_values[0] = "1"
    y_tri_answers = []

    for i in range(1, len(d_tri_values)):
        if i % 2 == 1 and i != len(d_tri_values) - 1:
            y_tri_answers.append(d_tri_values[i] if en_tri_values[i] == "1" else "x")

    data["params"]["tristate_signals"] = [
        {"name": "clk", "wave": "lP....", "editable": False},
        {"name": "EN", "values": en_tri_values, "period": 0.5, "editable": False},
        {"name": "D", "values": d_tri_values, "period": 0.5, "editable": False},
        {
            "name": "Y",
            "initial": d_tri_values[0],
            "editable": True,
            "correct_answers": y_tri_answers,
            "allowed_values": ["0", "1", "x"],
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
        {"name": "clk", "wave": "lP..", "editable": False},
        {
            "name": "raddrA",
            "wave": raddr_a_wave,
            "data": raddr_a_data,
            "period": 0.5,
            "editable": False,
        },
        {
            "name": "raddrB",
            "wave": raddr_b_wave,
            "data": raddr_b_data,
            "period": 0.5,
            "editable": False,
        },
        {
            "name": "rdataA",
            "wave": "x" * len(rdata_a_values),
            "correct_wave": "=" * len(rdata_a_values),
            "correct_answers": rdata_a_values,
            "allowed_values": HEX_VALUES,
            "period": 0.5,
            "editable": True,
        },
        {
            "name": "rdataB",
            "wave": "x" * len(rdata_b_values),
            "correct_wave": "=" * len(rdata_b_values),
            "correct_answers": rdata_b_values,
            "allowed_values": HEX_VALUES,
            "period": 0.5,
            "editable": True,
        },
    ]

    data["params"]["mixed_signals"] = [
        {"name": "clk", "wave": "lP.....", "editable": False},
        {"name": "in", "wave": "01.0.10", "editable": False},
        {
            "name": "out",
            "wave": "01xxx10",
            "correct_wave": "0110110",
            "correct_answers": ["1", "0", "1"],
            "allowed_values": ["0", "1"],
            "editable": True,
        },
    ]

    data["params"]["hscale"] = 1.5
    return data
