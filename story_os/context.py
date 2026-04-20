"""
Assemble optional Story OS context blocks for LLM prompts.
"""

from __future__ import annotations

from typing import Any, Dict, List

from story_os.flags import feature_enabled
from story_os import bible_rag, io


def series_key_from_episode(episode: Dict[str, Any]) -> str:
    """Filesystem id for the episode's series."""
    return io.series_slug(episode.get('series') or 'default')


def build_prompt_enrichment(episode: Dict[str, Any]) -> str:
    """Return extra user prompt text from bible, show state, slot, RAG.

    Empty string when ``USE_STORY_OS`` is off.
    """
    if not feature_enabled('USE_STORY_OS', default=False):
        return ''

    sid = series_key_from_episode(episode)
    parts: List[str] = []

    bible = io.load_series_bible(sid)
    if bible:
        lines = [
            f"Title: {bible.title}",
            f"Themes: {', '.join(bible.themes)}",
        ]
        if bible.tone_notes:
            lines.append(f"Tone: {bible.tone_notes[:500]}")
        if bible.taboos:
            lines.append('Avoid: ' + '; '.join(bible.taboos[:12]))
        if bible.finale_notes:
            lines.append(f"Finale notes: {bible.finale_notes[:400]}")
        if bible.main_cast:
            cast_lines = []
            for cm in bible.main_cast:
                desc = f"  - {cm.name}"
                if cm.role:
                    desc += f" ({cm.role})"
                if cm.species:
                    desc += f" [{cm.species}]"
                cast_lines.append(desc)
            lines.append('Main cast:\n' + '\n'.join(cast_lines))
        parts.append('SERIES BIBLE (constraints)\n' + '\n'.join(lines))

    show = io.load_show_state(sid)
    if show:
        hook_txt = '\n'.join(h.description[:200] for h in show.unresolved_hooks[:5])
        if hook_txt:
            parts.append('OPEN HOOKS (continuity)\n' + hook_txt)
        char_bits = []
        for name, st in list(show.character_states.items())[:8]:
            loc = st.location or ''
            emo = st.emotional_beat or ''
            char_bits.append(f"- {name}: {loc} {emo}".strip())
        if char_bits:
            parts.append('CHARACTER STATE SNAPSHOT\n' + '\n'.join(char_bits))

    if feature_enabled('USE_SHOW_STATE_DIFF_PROMPTS', default=False) and show:
        parts.append(
            'SHOW STATE MODE: treat bible + hooks above as hard continuity '
            'constraints unless the episode theme explicitly retcons them.'
        )

    ep_num = episode.get('episode_number') or 0
    if ep_num:
        slot = io.load_episode_slot(sid, int(ep_num))
        if slot:
            slot_bits = [
                f"Episode slot (season {slot.season_id}, index {slot.episode_index})",
                f"Primary beat id: {slot.primary_beat_id or 'n/a'}",
            ]
            if slot.must_plant:
                slot_bits.append('Must plant: ' + '; '.join(slot.must_plant))
            if slot.must_payoff:
                slot_bits.append('Must payoff: ' + '; '.join(slot.must_payoff))
            parts.append('\n'.join(slot_bits))

    if feature_enabled('USE_BIBLE_RAG', default=False):
        q_parts = [str(episode.get('theme') or ''), str(episode.get('title') or '')]
        q = ' '.join(q_parts).strip()
        if q:
            hits = bible_rag.search_bible_chunks(sid, q, top_k=5)
            if hits:
                joined = '\n---\n'.join(h[:700] for h in hits)
                parts.append('RETRIEVED BIBLE SNIPPETS\n' + joined)

    return '\n\n'.join(parts).strip()
