def classify_event(total_score):
    abs_score = abs(total_score)

    if abs_score < 2:
        return "raw"
    if abs_score < 4:
        return "l0"
    if abs_score < 7:
        return "l1"
    return "final"
