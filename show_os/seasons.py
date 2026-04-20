#!/usr/bin/env python
"""
Season Arc Module for Stardock Podium.

Handles Level 2 prompt: the season-long arc that gives episodes cohesion.

Each season has:
  - arc_prompt      (the Level 2 prompt -- user-provided)
  - episode_count   (how many episodes in the season)
  - arc_beats       (LLM-generated distribution of arc milestones)
  - season_number

Workflow:
    1. python main.py new-season --show <id> --season 1 --arc "..."
    2. System generates arc_beats per episode slot
    3. Saved to data/shows/<show_id>/seasons/<season_num>/season_plan.json
    4. When generate-episode runs, it reads the arc slot for that episode
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from openai import OpenAI

from config.paths import SHOWS_DIR

logger = logging.getLogger(__name__)


ARC_BEATS_PROMPT = """
You are a showrunner planning a season of a science fiction podcast.

SERIES BIBLE (show context):
{bible_summary}

SEASON ARC PROMPT:
{arc_prompt}

SEASON LENGTH: {episode_count} episodes

Break this season arc into per-episode milestones.
Each episode should have:
  - arc_beat: what the arc demands from THIS episode (1-2 sentences)
  - tension_level: "rising" | "peak" | "resolution" | "breather"
  - arc_importance: "central" | "subplot" | "tangential"

Return ONLY valid JSON:
{{
  "arc_title": "string -- short title for this arc",
  "arc_summary": "string -- 2-3 sentence synopsis of the whole season",
  "episode_beats": [
    {{
      "episode_number": 1,
      "arc_beat": "string",
      "tension_level": "rising",
      "arc_importance": "central"
    }}
  ]
}}

Structure it like a TV season:
  - Episode 1: establish the threat/mystery
  - Mid-season: escalation, false victory or defeat
  - Late season: stakes peak
  - Finale: resolution with a new question raised for next season

Not every episode needs to be arc-central. Leave 20-30% as
"breather" or "subplot" episodes that develop character without
advancing the main arc.
"""


class SeasonPlanner:
    """Creates and manages season-level arc plans."""

    def __init__(self):
        self._init_llm()

    def _init_llm(self):
        openrouter_key = os.environ.get('OPENROUTER_API_KEY')
        openai_key = os.environ.get('OPENAI_API_KEY')
        if openrouter_key:
            self.client = OpenAI(
                base_url='https://openrouter.ai/api/v1',
                api_key=openrouter_key,
            )
            self.model = 'anthropic/claude-opus-4.5'
        elif openai_key:
            self.client = OpenAI(api_key=openai_key)
            self.model = 'gpt-4o'
        else:
            raise EnvironmentError('No LLM API key')

    def create_season(
        self,
        show_id: str,
        season_number: int,
        arc_prompt: str,
        episode_count: int = 10,
    ) -> Dict[str, Any]:
        """Create a new season plan for a show."""
        show_dir = SHOWS_DIR / show_id
        if not show_dir.exists():
            raise RuntimeError(
                f'Show not found: {show_id}. '
                'Run new-show first.')

        bible_path = show_dir / 'series_bible.json'
        with open(bible_path, encoding='utf-8') as f:
            bible = json.load(f)

        bible_summary = self._summarize_bible(bible)

        logger.info(
            'Planning Season %s for show %r',
            season_number, show_id)
        logger.info('Arc: %s...', arc_prompt[:200])

        plan = self._generate_arc_beats(
            bible_summary=bible_summary,
            arc_prompt=arc_prompt,
            episode_count=episode_count,
        )

        if not plan:
            raise RuntimeError('Failed to generate arc beats')

        season_plan = {
            'show_id': show_id,
            'season_number': season_number,
            'arc_prompt': arc_prompt,
            'episode_count': episode_count,
            'arc_title': plan.get('arc_title', ''),
            'arc_summary': plan.get('arc_summary', ''),
            'episode_beats': plan.get('episode_beats', []),
            'created_at': time.time(),
        }

        season_dir = (
            show_dir / 'seasons' / str(season_number))
        season_dir.mkdir(parents=True, exist_ok=True)
        plan_path = season_dir / 'season_plan.json'
        with open(plan_path, 'w', encoding='utf-8') as f:
            json.dump(season_plan, f, indent=2)

        show_state_path = show_dir / 'show_state.json'
        if show_state_path.exists():
            with open(show_state_path, encoding='utf-8') as f:
                state = json.load(f)
            state['current_season'] = season_number
            with open(
                show_state_path, 'w', encoding='utf-8'
            ) as f:
                json.dump(state, f, indent=2)

        logger.info(
            'Season %s plan saved: %s',
            season_number, plan_path)
        return season_plan

    def get_episode_slot(
        self,
        show_id: str,
        season_number: int,
        episode_number: int,
    ) -> Optional[Dict[str, Any]]:
        """Get the arc beat for a specific episode slot."""
        plan_path = (
            SHOWS_DIR / show_id / 'seasons'
            / str(season_number) / 'season_plan.json'
        )
        if not plan_path.exists():
            return None
        with open(plan_path, encoding='utf-8') as f:
            plan = json.load(f)
        for beat in plan.get('episode_beats', []):
            if beat.get('episode_number') == episode_number:
                return {
                    'arc_title': plan.get('arc_title'),
                    'arc_summary': plan.get('arc_summary'),
                    **beat,
                }
        return None

    # ── Internal helpers ─────────────────────────

    def _summarize_bible(self, bible: Dict[str, Any]) -> str:
        """Produce a compact bible summary for the arc prompt."""
        parts = []
        if bible.get('show_name'):
            parts.append(f"Show: {bible['show_name']}")
        if bible.get('concept'):
            parts.append(f"Concept: {bible['concept']}")
        if bible.get('tone'):
            parts.append(f"Tone: {bible['tone']}")
        if bible.get('main_cast'):
            parts.append('Main cast:')
            for c in bible['main_cast']:
                parts.append(
                    f"  - {c.get('name')}: {c.get('role')}")
        return '\n'.join(parts)

    def _generate_arc_beats(
        self,
        bible_summary: str,
        arc_prompt: str,
        episode_count: int,
    ) -> Dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are a TV season planner. '
                            'Return only valid JSON.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': ARC_BEATS_PROMPT.format(
                            bible_summary=bible_summary,
                            arc_prompt=arc_prompt,
                            episode_count=episode_count,
                        ),
                    },
                ],
                temperature=0.5,
                max_tokens=4000,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            logger.error('Arc beats generation failed: %s', e)
            return {}
