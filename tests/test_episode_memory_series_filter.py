"""Unit tests for series-matching logic used in continuity retrieval."""


def _match_series(series: str, series_meta) -> bool:
    """Mirror episode_memory.get_previous_episode_context filter."""
    if not series:
        return True
    if series_meta is None or series_meta == '':
        return True
    return series_meta == series


def test_legacy_memory_without_series_matches():
    assert _match_series('Main Series', None) is True
    assert _match_series('Main Series', '') is True


def test_explicit_series_must_equal():
    assert _match_series('Main Series', 'Main Series') is True
    assert _match_series('Main Series', 'Other') is False
