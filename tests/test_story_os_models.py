"""Tests for Story OS Pydantic models."""

from story_os.models import ShowState, SeriesBible


def test_show_state_defaults():
    s = ShowState(series_id='s1')
    d = s.model_dump()
    assert d['series_id'] == 's1'
    assert d['active_threads'] == []


def test_series_bible_round_trip():
    b = SeriesBible(
        series_id='s1',
        title='Test',
        themes=['hope', 'exploration'],
    )
    b2 = SeriesBible.model_validate(b.model_dump())
    assert b2.themes == ['hope', 'exploration']
