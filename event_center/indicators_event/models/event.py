def classify_event(total_score: float) -> int:
    abs_score = abs(total_score)
    if abs_score < 2:
        return 1  # raw
    if abs_score < 4:
        return 2  # l0
    if abs_score < 7:
        return 3  # l1
    return 4      # final
