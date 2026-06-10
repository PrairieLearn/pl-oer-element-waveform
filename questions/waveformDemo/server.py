import random


HEX_VALUES = list("0123456789ABCDEF")


def _make_dff(iters):
    """Generate a randomised D flip-flop: returns (D_vals, Q_by_cycle)."""
    V = ["0", "1"]
    D_vals = random.choices(V, k=iters)
    Q_by_cycle = []
    for i in range(1, iters):
        if (i % 2) == 1 and i != iters - 1:
            Q_by_cycle.append(D_vals[i])
    return D_vals, Q_by_cycle


def _encode_binary(values):
    wave = [values[0]]
    for idx in range(1, len(values)):
        wave.append("." if values[idx] == values[idx - 1] else values[idx])
    return "".join(wave)


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
    V = ["0", "1"]

    ITERS_DFF = 12

    # Reference: independent data, Q pre-computed as a non-editable wave
    D_ref, Q_ref_cycle = _make_dff(ITERS_DFF)
    prev = "0"
    q_chars = ["0"]
    for v in Q_ref_cycle:
        q_chars.append("." if v == prev else v)
        prev = v
    Q_ref_wave = "".join(q_chars)

    data["params"]["ref_signals"] = [
        {"name": "clk", "wave": "lP....", "editable": False},
        {"name": "D", "values": D_ref, "period": 0.5, "editable": False},
        {"name": "Q", "wave": Q_ref_wave, "editable": False},
    ]

    # Part 1: D flip-flop (cell feedback)
    D_vals, Q_dff = _make_dff(ITERS_DFF)

    data["params"]["dff_signals"] = [
        {"name": "clk", "wave": "lP....", "editable": False},
        {"name": "D", "values": D_vals, "period": 0.5, "editable": False},
        {
            "name": "Q",
            "initial": "0",
            "editable": True,
            "correct_answers": Q_dff,
        },
    ]

    # Part 2: JK flip-flop (row feedback)
    ITERS_JK = 16
    J = random.choices(V, k=ITERS_JK)
    K = random.choices(V, k=ITERS_JK)

    Q2_state = "0"
    Q2 = []
    Q2bar = []
    for i in range(1, ITERS_JK):
        if (i % 2) == 1 and i != ITERS_JK - 1:
            j, k = J[i], K[i]
            if j == "0" and k == "1":
                Q2_state = "0"
            elif j == "1" and k == "0":
                Q2_state = "1"
            elif j == "1" and k == "1":
                Q2_state = "1" if Q2_state == "0" else "0"
            Q2.append(Q2_state)
            Q2bar.append("1" if Q2_state == "0" else "0")

    data["params"]["jk_signals"] = [
        {"name": "clk", "wave": "lP......", "editable": False},
        {"name": "J", "values": J, "period": 0.5, "editable": False},
        {"name": "K", "values": K, "period": 0.5, "editable": False},
        {
            "name": "Q",
            "initial": "0",
            "editable": True,
            "correct_answers": Q2,
        },
        {
            "name": "Q'",
            "initial": "1",
            "editable": True,
            "correct_answers": Q2bar,
        },
    ]

    # Part 3: D flip-flop with enable (table feedback)
    ITERS_EN = 12
    D3 = random.choices(V, k=ITERS_EN)
    EN = random.choices(V, weights=[1, 2], k=ITERS_EN)

    Q3_state = "0"
    Q3 = []
    Q3bar = []
    for i in range(1, ITERS_EN):
        if (i % 2) == 1 and i != ITERS_EN - 1:
            if EN[i] == "1":
                Q3_state = D3[i]
            Q3.append(Q3_state)
            Q3bar.append("1" if Q3_state == "0" else "0")

    data["params"]["dffen_signals"] = [
        {"name": "clk", "wave": "lP....", "editable": False},
        {"name": "D", "values": D3, "period": 0.5, "editable": False},
        {"name": "EN", "values": EN, "period": 0.5, "editable": False},
        {
            "name": "Q",
            "initial": "0",
            "editable": True,
            "correct_answers": Q3,
        },
        {
            "name": "Q'",
            "initial": "1",
            "editable": True,
            "correct_answers": Q3bar,
        },
    ]

    # Part 4: 2-input AND gate — sub-cycle (period=0.5) inputs and output,
    # demonstrating multiple answer boxes inside one clock period.
    ITERS_AND = 8
    A = random.choices(V, k=ITERS_AND)
    B = random.choices(V, k=ITERS_AND)
    Y_and = ["1" if a == "1" and b == "1" else "0" for a, b in zip(A, B)]

    data["params"]["subcycle_signals"] = [
        {"name": "clk", "wave": "lP..", "editable": False},
        {"name": "A", "values": A, "period": 0.5, "editable": False},
        {"name": "B", "values": B, "period": 0.5, "editable": False},
        {
            "name": "Y",
            "initial": Y_and[0],
            "editable": True,
            "correct_answers": Y_and[1:],
            "period": 0.5,
        },
    ]

    # Part 5: AND gate with toggle mode + period=0.5 — same circuit as Part 4
    # but uses input-mode="toggle" to show interactive sub-cycle toggle cells.
    ITERS_AND6 = 8
    A6 = random.choices(V, k=ITERS_AND6)
    B6 = random.choices(V, k=ITERS_AND6)
    Y_and6 = ["1" if a == "1" and b == "1" else "0" for a, b in zip(A6, B6)]

    data["params"]["subcycle_toggle_signals"] = [
        {"name": "clk", "wave": "lP..", "editable": False},
        {"name": "A", "values": A6, "period": 0.5, "editable": False},
        {"name": "B", "values": B6, "period": 0.5, "editable": False},
        {
            "name": "Y",
            "initial": Y_and6[0],
            "editable": True,
            "correct_answers": Y_and6[1:],
            "period": 0.5,
        },
    ]

    # Part 6: tri-state buffer — output is D when EN=1, else high-impedance (x).
    # Demonstrates allowed_values=["0","1","x"] so students can enter x.
    ITERS_TRISTATE = 12
    D5 = random.choices(V, k=ITERS_TRISTATE)
    EN5 = random.choices(["0", "1"], weights=[1, 2], k=ITERS_TRISTATE)
    EN5[0] = "1"  # ensure a known (non-x) initial output

    Y5_answers = []
    for i in range(1, ITERS_TRISTATE):
        if (i % 2) == 1 and i != ITERS_TRISTATE - 1:
            Y5_answers.append(D5[i] if EN5[i] == "1" else "x")

    data["params"]["tristate_signals"] = [
        {"name": "clk", "wave": "lP....", "editable": False},
        {"name": "EN", "values": EN5, "period": 0.5, "editable": False},
        {"name": "D", "values": D5, "period": 0.5, "editable": False},
        {
            "name": "Y",
            "initial": D5[0],
            "editable": True,
            "correct_answers": Y5_answers,
            "allowed_values": ["0", "1", "x"],
        },
    ]

    # Part 7: register file read timing with hex-valued bus answers.
    ITERS_REG_READ = 8
    w_en_vals = random.choices(["0", "1"], weights=[1, 4], k=ITERS_REG_READ)
    waddr_vals = random.choices(["0", "1", "2", "3"], k=ITERS_REG_READ)
    wdata_vals = random.choices(HEX_VALUES, k=ITERS_REG_READ)
    raddr_a_vals = random.choices(["0", "1", "2", "3"], k=ITERS_REG_READ)
    raddr_b_vals = random.choices(["0", "1", "2", "3"], k=ITERS_REG_READ)

    reg_data = random.choices(HEX_VALUES, k=4)
    for reg_idx, value in enumerate(reg_data):
        data["params"][f"regread_reg{reg_idx}"] = value

    rdata_a = []
    rdata_b = []
    for idx in range(ITERS_REG_READ):
        rdata_a.append(reg_data[int(raddr_a_vals[idx])])
        rdata_b.append(reg_data[int(raddr_b_vals[idx])])

        if idx > 0 and (idx % 2) == 1 and idx != ITERS_REG_READ - 1 and w_en_vals[idx] == "1":
            reg_data[int(waddr_vals[idx])] = wdata_vals[idx]

    waddr_wave, waddr_data = _encode_bus(waddr_vals)
    wdata_wave, wdata_data = _encode_bus(wdata_vals)
    raddr_a_wave, raddr_a_data = _encode_bus(raddr_a_vals)
    raddr_b_wave, raddr_b_data = _encode_bus(raddr_b_vals)

    data["params"]["regfile_read_hex_signals"] = [
        {"name": "clk", "wave": "lP..", "editable": False},
        {"name": "w_en", "wave": _encode_binary(w_en_vals), "period": 0.5, "editable": False},
        {"name": "waddr", "wave": waddr_wave, "data": waddr_data, "period": 0.5, "editable": False},
        {"name": "wdata", "wave": wdata_wave, "data": wdata_data, "period": 0.5, "editable": False},
        {"name": "raddrA", "wave": raddr_a_wave, "data": raddr_a_data, "period": 0.5, "editable": False},
        {"name": "raddrB", "wave": raddr_b_wave, "data": raddr_b_data, "period": 0.5, "editable": False},
        {
            "name": "rdataA",
            "wave": "x" * ITERS_REG_READ,
            "correct_wave": "=" * ITERS_REG_READ,
            "correct_answers": rdata_a,
            "allowed_values": HEX_VALUES,
            "period": 0.5,
            "editable": True,
        },
        {
            "name": "rdataB",
            "wave": "x" * ITERS_REG_READ,
            "correct_wave": "=" * ITERS_REG_READ,
            "correct_answers": rdata_b,
            "allowed_values": HEX_VALUES,
            "period": 0.5,
            "editable": True,
        },
    ]

    # Part 8: register file write timing with hex-valued register-state answers.
    ITERS_REG_WRITE = 12
    reset_vals = ["1"] + ["0"] * (ITERS_REG_WRITE - 1)
    write_en_vals = random.choices(["0", "1"], weights=[1, 4], k=ITERS_REG_WRITE)
    write_addr_vals = random.choices(["0", "1", "2", "3"], k=ITERS_REG_WRITE)
    write_data_vals = random.choices(HEX_VALUES, k=ITERS_REG_WRITE)

    write_reg_data = ["0", "0", "0", "0"]
    reg_history = [[value] for value in write_reg_data]

    for idx in range(1, ITERS_REG_WRITE):
        if (idx % 2) == 1 and idx != ITERS_REG_WRITE - 1:
            if write_en_vals[idx] == "1":
                write_reg_data[int(write_addr_vals[idx])] = write_data_vals[idx]
            for reg_idx, value in enumerate(write_reg_data):
                reg_history[reg_idx].append(value)

    write_addr_wave, write_addr_data = _encode_bus(write_addr_vals)
    write_data_wave, write_data_data = _encode_bus(write_data_vals)
    answer_len = len(reg_history[0])

    data["params"]["regfile_write_hex_signals"] = [
        {"name": "clk", "wave": "lP....", "editable": False},
        {"name": "reset", "values": reset_vals, "period": 0.5, "editable": False},
        {"name": "w_en", "wave": _encode_binary(write_en_vals), "period": 0.5, "editable": False},
        {"name": "waddr", "wave": write_addr_wave, "data": write_addr_data, "period": 0.5, "editable": False},
        {"name": "wdata", "wave": write_data_wave, "data": write_data_data, "period": 0.5, "editable": False},
    ]

    for reg_idx, answers in enumerate(reg_history):
        data["params"]["regfile_write_hex_signals"].append(
            {
                "name": f"reg{reg_idx}",
                "wave": "x" * answer_len,
                "correct_wave": "=" * answer_len,
                "correct_answers": answers,
                "allowed_values": HEX_VALUES,
                "editable": True,
            }
        )

    # Part 10: hex toggle — small register read with toggle input mode.
    # Each cycle the read port samples from a 4-entry register file; student
    # toggles through hex values 0-F to fill in the output bus.
    ITERS_HEX_TOG = 6
    reg_tog = random.choices(HEX_VALUES, k=4)
    raddr_tog = random.choices(["0", "1", "2", "3"], k=ITERS_HEX_TOG)
    rdata_tog = [reg_tog[int(a)] for a in raddr_tog]

    raddr_tog_wave, raddr_tog_data = _encode_bus(raddr_tog)

    data["params"]["hex_toggle_signals"] = [
        {"name": "clk", "wave": "lP..", "editable": False},
        {"name": "raddr", "wave": raddr_tog_wave, "data": raddr_tog_data, "period": 0.5, "editable": False},
        {
            "name": "rdata",
            "wave": "x" * ITERS_HEX_TOG,
            "correct_wave": "=" * ITERS_HEX_TOG,
            "correct_answers": rdata_tog,
            "allowed_values": HEX_VALUES,
            "period": 0.5,
            "editable": True,
        },
    ]
    data["params"]["hex_toggle_reg"] = reg_tog

    # Part 9: mixed fixed/editable/fixed row in text mode.
    # Pattern: first 2 fixed cells, then 3 editable cells, then 2 fixed cells.
    data["params"]["mixed_fixed_edit_fixed_signals"] = [
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
