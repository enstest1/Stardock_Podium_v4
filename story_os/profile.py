"""Per-show format profile (BASE-003, amended name ``format``).

Owns: the wording that used to be hard-coded per franchise — writer and cast
personas, genre phrase, intro/outro templates, pronunciation lexicon — so
prompts and narration come from data. Projects created by ``create-podcast``
store theirs in ``data/projects/<project_id>/format.json``.

Legacy episodes (no ``project_id``) do not read this module; their prompts are
unchanged until the ``migrate-shows`` step (STORYOS-001) writes a legacy
profile that reproduces the old strings.
"""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class FormatProfile(BaseModel):
    original: bool = True
    writer_persona: str = 'an expert audio scriptwriter'
    cast_designer_persona: str = 'a character designer for audio productions'
    title_prompt_noun: str = 'episode title for this podcast'
    outline_noun: str = 'scene outline'
    script_noun: str = 'script for an audio scene'
    genre_phrase: str = 'an original audio drama'
    intro_template: str = '{show_name}. Episode {episode}: {title}.'
    outro_template: str = 'You have been listening to {show_name}.'
    pronunciation_lexicon: Dict[str, str] = Field(default_factory=dict)
    number_rules: List[str] = Field(default_factory=list)
    use_theme_music: bool = True

    def render(self, template: str, **values) -> str:
        """Fill a template; unknown placeholders are left empty, not raised."""
        class _Safe(dict):
            def __missing__(self, key):
                return ''
        return template.format_map(_Safe(**values)).strip()


_ARTICLE_VOWELS = 'aeiou'


def genre_phrase_for(genre: str, mode: str) -> str:
    """'gothic horror' + 'anthology' -> 'an original gothic horror anthology'."""
    noun = {
        'serialized_fiction': 'serialized audio drama',
        'episodic_fiction': 'audio drama',
        'anthology': 'audio anthology',
        'standalone_drama': 'audio drama',
        'documentary': 'documentary podcast',
        'educational': 'educational podcast',
        'conversational': 'conversational podcast',
    }.get(mode, 'podcast')
    words = f'original {genre.strip()} {noun}' if genre.strip() else f'original {noun}'
    return f'an {words}' if words[0] in _ARTICLE_VOWELS else f'a {words}'


def default_format(genre: str, mode: str) -> FormatProfile:
    return FormatProfile(genre_phrase=genre_phrase_for(genre, mode))
