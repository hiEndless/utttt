from typing import Dict, List


def auto_score(texts: List[str]) -> Dict[int, float]:
    scores: Dict[int, float] = {}
    for i, t in enumerate(texts):
        s = min(1.0, max(0.0, len(t) / 800.0))
        scores[i] = s
    return scores