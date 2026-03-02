from __future__ import annotations


TIER_ORDER = {
    "IRON": 0,
    "BRONZE": 1,
    "SILVER": 2,
    "GOLD": 3,
    "PLATINUM": 4,
    "EMERALD": 5,
    "DIAMOND": 6,
    "MASTER": 7,
    "GRANDMASTER": 8,
    "CHALLENGER": 9,
}

DIV_ORDER = {"IV": 1, "III": 2, "II": 3, "I": 4}


def rank_sort_key(tier: str | None, division: str | None, lp: int | None) -> tuple[int, int, int]:
    if tier is None:
        return (-1, 0, 0)
    t = TIER_ORDER.get(tier.upper(), -1)
    d = 0 if division is None else DIV_ORDER.get(division.upper(), 0)
    p = 0 if lp is None else int(lp)
    return (t, d, p)