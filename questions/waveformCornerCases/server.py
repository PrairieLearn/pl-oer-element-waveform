HEX_VALUES = list("0123456789ABCDEF")


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
    reset_vals = ["1", "1", "0", "0", "0", "1", "0", "0"]
    en_vals = ["1", "1", "1", "0", "1", "1", "1", "1"]
    d_vals = ["0", "1", "1", "0", "1", "0", "1", "1"]
    data["params"]["dff_signals"] = [
        {"name": ["tspan", {"class": "h4"}, " clk"], "wave": "P...", "editable": False},
        {
            "name": ["tspan", {"class": "h4"}, " reset"],
            "values": reset_vals,
            "period": 0.5,
            "editable": False,
        },
        {
            "name": ["tspan", {"class": "h4"}, " en"],
            "values": en_vals,
            "period": 0.5,
            "editable": False,
        },
        {
            "name": ["tspan", {"class": "error h4"}, " D"],
            "values": d_vals,
            "period": 0.5,
            "editable": False,
        },
        {
            "name": ["tspan", {"class": "error h4"}, " Q"],
            "start_values": ["0"],
            "values": ["0", "1", "1", "0", "1", "1", "0"],
            "period": 0.5,
            "editable": True,
        },
    ]

    waddr_values = ["1", "1", "1", "0", "0", "1", "1", "0"]
    wdata_values = ["00", "00", "A5", "A5", "3C", "3C", "12", "12"]
    raddr_a_values = ["0", "0", "1", "1", "1", "0", "0", "0"]
    raddr_b_values = ["1", "1", "0", "0", "1", "1", "0", "0"]
    waddr_wave, waddr_data = _encode_bus(waddr_values)
    wdata_wave, wdata_data = _encode_bus(wdata_values)
    data["params"]["regfile_signals"] = [
        {
            "name": ["tspan", {"class": "info h4"}, "clk"],
            "wave": "P...",
            "editable": False,
        },
        {
            "name": ["tspan", {"class": "success h4"}, "waddr"],
            "wave": waddr_wave,
            "data": waddr_data,
            "period": 0.5,
            "editable": False,
        },
        {
            "name": ["tspan", {"class": "error h4"}, "wdata"],
            "wave": wdata_wave,
            "data": wdata_data,
            "period": 0.5,
            "editable": False,
        },
        {
            "name": ["tspan", {"class": "success h4"}, "raddrA"],
            "values": raddr_a_values,
            "period": 0.5,
            "editable": False,
        },
        {
            "name": ["tspan", {"class": "success h4"}, "raddrB"],
            "values": raddr_b_values,
            "period": 0.5,
            "editable": False,
        },
        {
            "name": ["tspan", {"class": "error h4"}, "accum"],
            "start_values": ["00"],
            "values": ["00", "A5", "3C"],
            "allowed_values": "hex",
            "bus_width": 2,
            "editable": True,
        },
        {
            "name": ["tspan", {"class": "error h4"}, "nibble"],
            "start_values": ["0"],
            "values": ["0", "F", "3"],
            "allowed_values": "hex",
            "bus_width": 1,
            "editable": True,
        },
    ]

    data["params"]["overlap_signals"] = [
        {"name": "clk", "wave": "P....", "editable": False},
        {"name": "A", "values": ["0", "1", "1", "0", "1"], "editable": True},
        {"name": "X", "wave": "01.0.", "editable": False},
        {
            "name": "State",
            "start_values": ["W", "A", "S"],
            "values": ["D", "A"],
            "allowed_values": ["W", "A", "S", "D"],
            "editable": True,
        },
        {
            "name": "SAB",
            "start_values": ["X"],
            "values": ["1", "X", "0", "X"],
            "allowed_values": ["0", "1", "X"],
            "editable": True,
        },
    ]

    proc_wave = "x=.x=.x=.x.."
    bus_wave = "=.x=.x=.x..."
    data["params"]["msi_signals"] = [
        {"name": "clk", "wave": "P.....", "editable": False},
        {
            "name": "proc",
            "wave": proc_wave,
            "data": ["load", "store", "evict"],
            "period": 0.5,
            "editable": False,
        },
        {
            "name": "bus",
            "wave": bus_wave,
            "data": ["GETS", "GETX", "UPGRADE"],
            "period": 0.5,
            "editable": False,
        },
        {
            "name": "State",
            "start_values": ["I"],
            "values": ["S", "M", "S", "I", "M"],
            "allowed_values": ["I", "S", "M"],
            "editable": True,
        },
        {
            "name": "Writeback",
            "start_values": ["0"],
            "values": ["0", "1", "0", "0", "1"],
            "editable": True,
        },
        {
            "name": "Source",
            "start_values": ["0"],
            "values": ["0", "1", "1", "0", "0"],
            "editable": True,
        },
    ]

    return data
