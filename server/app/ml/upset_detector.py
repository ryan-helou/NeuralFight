"""Upset detection: compare ML predictions against betting odds."""


def compute_upset_score(
    ml_underdog_prob: float,
    implied_underdog_prob: float,
) -> float:
    """Compute upset score (0-100) based on how much the ML model favors the underdog
    compared to betting odds.

    Args:
        ml_underdog_prob: ML model's probability for the betting underdog.
        implied_underdog_prob: Implied probability from betting odds for the underdog.

    Returns:
        Score from 0-100. Higher = ML sees more upset potential than odds suggest.
    """
    edge = ml_underdog_prob - implied_underdog_prob
    # Scale: edge of 0.30+ maps to ~100
    score = max(0.0, min(100.0, edge * 333))
    return round(score, 1)


def compute_betting_confidence(
    ml_prob: float,
    implied_prob: float,
) -> float:
    """Compute betting confidence score (0-100).

    50 = ML agrees with odds exactly.
    100 = Strong value bet (ML gives much higher prob than odds imply).
    0 = Don't bet (ML disagrees with your side).

    Args:
        ml_prob: ML probability for the fighter you'd bet on.
        implied_prob: Implied probability from odds for that fighter.

    Returns:
        Confidence score 0-100.
    """
    edge = ml_prob - implied_prob
    # Center at 50, scale so +0.20 edge = 100, -0.20 edge = 0
    confidence = 50 + edge * 250
    return round(max(0.0, min(100.0, confidence)), 1)


def decimal_to_implied_prob(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability."""
    if decimal_odds <= 0:
        return 0.0
    return 1.0 / decimal_odds


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds to American odds."""
    if decimal_odds >= 2.0:
        return round((decimal_odds - 1) * 100)
    elif decimal_odds > 1.0:
        return round(-100 / (decimal_odds - 1))
    return 0
