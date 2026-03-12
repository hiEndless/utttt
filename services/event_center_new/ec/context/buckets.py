from __future__ import annotations

from dataclasses import dataclass

from ..contracts import Evidence, Horizon


@dataclass(frozen=True)
class EvidenceBuckets:
    short: list[Evidence]
    mid: list[Evidence]
    long: list[Evidence]


def bucket_by_horizon(evidences: list[Evidence]) -> EvidenceBuckets:
    short: list[Evidence] = []
    mid: list[Evidence] = []
    long: list[Evidence] = []

    for e in evidences:
        if e.horizon == "short":
            short.append(e)
        elif e.horizon == "mid":
            mid.append(e)
        else:
            long.append(e)

    return EvidenceBuckets(short=short, mid=mid, long=long)


@dataclass(frozen=True)
class BucketTopKPolicy:
    short_k: int = 6
    mid_k: int = 6
    long_k: int = 6
    total_k: int = 12


def select_top_k_by_bucket(
    buckets: EvidenceBuckets,
    scored: dict[int, float],
    policy: BucketTopKPolicy,
) -> list[Evidence]:
    def sort_bucket(items: list[Evidence]) -> list[Evidence]:
        return sorted(items, key=lambda e: scored.get(id(e), 0.0), reverse=True)

    selected: list[Evidence] = []
    selected.extend(sort_bucket(buckets.short)[: max(0, policy.short_k)])
    selected.extend(sort_bucket(buckets.mid)[: max(0, policy.mid_k)])
    selected.extend(sort_bucket(buckets.long)[: max(0, policy.long_k)])

    selected = sorted(selected, key=lambda e: scored.get(id(e), 0.0), reverse=True)
    return selected[: max(0, policy.total_k)]

