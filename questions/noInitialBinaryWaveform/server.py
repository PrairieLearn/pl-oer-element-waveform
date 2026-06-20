def generate(data):
    q_answers = ["0", "0", "1", "1"]

    data["params"]["signals"] = [
        {"name": "clk", "wave": "lP..", "editable": False},
        {
            "name": "Q",
            "editable": True,
            "correct_answers": q_answers,
        },
    ]
    data["params"]["hscale"] = 1.5
    return data
