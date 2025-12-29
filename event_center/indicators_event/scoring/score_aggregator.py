def aggregate_scores(scores):
    total = sum(s["score"] for s in scores)

    direction = "neutral"
    if total > 0:
        direction = "bullish"
    elif total < 0:
        direction = "bearish"

    return total, direction
