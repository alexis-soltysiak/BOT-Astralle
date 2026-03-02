from app.features.leaderboards.selectors import rank_sort_key


def test_rank_sort_key_unranked_bottom() -> None:
    assert rank_sort_key(None, None, None) < rank_sort_key("IRON", "IV", 0)


def test_rank_sort_key_higher_tier_wins() -> None:
    assert rank_sort_key("GOLD", "IV", 0) > rank_sort_key("SILVER", "I", 99)


def test_rank_sort_key_division_order() -> None:
    assert rank_sort_key("PLATINUM", "I", 0) > rank_sort_key("PLATINUM", "II", 999)