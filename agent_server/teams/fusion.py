from typing import Dict, List, Tuple


def weighted_fusion(texts: List[str], weights: Dict[str, float], names: List[str]) -> Tuple[str, Dict[str, float]]:
    norm = sum(weights.get(n, 0.0) for n in names) or 1.0
    w = [weights.get(n, 0.0) / norm for n in names]
    parts = []
    for i, t in enumerate(texts):
        parts.append(f"[{names[i]}:{w[i]:.2f}] {t}")
    return "\n".join(parts), {n: w[i] for i, n in enumerate(names)}