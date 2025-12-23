from typing import Dict, List


def crowd_state_compactor(crowd: Dict) -> Dict:
    """
    Compress full crowd structure analysis into a low-noise crowd_state object.
    This output is intended ONLY for risk / confidence / veto adjustment.
    """

    summary = crowd.get("market_participant_summary", {})
    sentiment_by_tf = crowd.get("sentiment_by_timeframes", {})
    funding = crowd.get("funding_analysis", {})
    consistency = crowd.get("cross_timeframe_consistency", {})

    # ---------- bias ----------
    bias = summary.get("overall_bias", "neutral")
    if bias not in {"long", "short"}:
        bias = "neutral"

    # ---------- crowding_level ----------
    crowding_level = "low"
    if summary.get("overall_strength") == "strong":
        if "crowded long" in summary.get("structural_risks", []):
            crowding_level = "high"
        else:
            crowding_level = "medium"

    # ---------- fragility ----------
    fragility = "low"
    if summary.get("overall_stability") == "volatile":
        fragility = "high"
    elif summary.get("overall_stability") == "medium":
        fragility = "medium"

    # ---------- behavioral_divergence ----------
    divergence_notes = consistency.get("conflicts", [])
    behavioral_divergence = any(
        "divergence" in note for note in divergence_notes
    )

    # ---------- funding_pressure ----------
    funding_pressure = "none"
    if "potential funding squeeze" in summary.get("structural_risks", []):
        funding_pressure = "potential_squeeze"

    if funding.get("volatility") == "high" and funding.get("trend") in {"up", "spiking"}:
        funding_pressure = "active_squeeze"

    # ---------- consistency ----------
    alignment = consistency.get("sentiment_alignment", "")
    if alignment == "aligned" and not behavioral_divergence:
        tf_consistency = "aligned"
    elif behavioral_divergence:
        tf_consistency = "conflicted"
    else:
        tf_consistency = "mixed"

    return {
        "bias": bias,
        "crowding_level": crowding_level,
        "fragility": fragility,
        "behavioral_divergence": behavioral_divergence,
        "funding_pressure": funding_pressure,
        "consistency": tf_consistency
    }
