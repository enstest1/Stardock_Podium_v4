"""
Agentic multi-pass script generation (plan → draft → QA metadata).

Uses ``StoryStructure.complete_text`` for a compact beat plan, then
``generate_episode_script`` with that plan as ``extra_preamble``. Optional
JSONL tracing when ``USE_GENERATION_TRACE`` is on.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from story_os.flags import feature_enabled

logger = logging.getLogger(__name__)


def should_use_agentic_pipeline() -> bool:
    """Return True if agentic script path is enabled."""
    return feature_enabled('USE_AGENTIC_PIPELINE', default=False)


def run_agentic_episode_script(episode_id: str) -> Dict[str, Any]:
    """Plan, generate full script, save draft snapshot, run script QA.

    Args:
        episode_id: Episode identifier.

    Returns:
        Script dict (same shape as legacy ``generate_episode_script``).
    """
    from generation_trace import log_step, new_run_id
    from story_os.context import build_prompt_enrichment
    from story_structure import get_story_structure

    ss = get_story_structure()
    run_id = new_run_id()
    log_step(run_id, 'agentic_start', {'episode_id': episode_id})

    episode = ss.get_episode(episode_id)
    if not episode:
        log_step(run_id, 'error', {'reason': 'episode_not_found'})
        logger.error('Agentic script: episode not found %s', episode_id)
        return {}

    enrich = ''
    try:
        enrich = build_prompt_enrichment(episode)
    except Exception as e:
        logger.warning('Agentic enrich failed: %s', e)

    cast = ', '.join(
        (c.get('name') or '').strip()
        for c in (episode.get('characters') or [])
        if (c.get('name') or '').strip()
    )
    plan_user = (
        f"Episode title: {episode.get('title')}\n"
        f"Theme: {episode.get('theme')}\n"
        f"Characters: {cast or '(none)'}\n\n"
        f"STORY OS CONTEXT:\n{enrich or '(none)'}\n\n"
        "Write a concise beat plan for THIS episode only. "
        "Bullet list: Scene N — goal — conflict — turn. "
        "Stay under 400 words. No dialogue."
    )
    plan = ss.complete_text(
        'You are a story director for serialized prestige audio drama.',
        plan_user,
        max_tokens=700,
    )
    if not plan:
        logger.warning('Agentic plan empty; proceeding with script only.')
    log_step(run_id, 'plan_done', {'plan_chars': len(plan)})

    preamble = ''
    if plan:
        preamble = (
            'AGENTIC EPISODE PLAN (follow closely; do not contradict):\n'
            f'{plan}\n\n'
        )

    script = ss.generate_episode_script(episode_id, extra_preamble=preamble)
    scene_count = 0
    if isinstance(script, dict):
        scene_count = len(script.get('scenes') or [])
    log_step(run_id, 'script_done', {'scenes': scene_count})

    try:
        from draft_store import save_script_draft
        save_script_draft(episode_id, script, 'post_agentic')
    except Exception as e:
        logger.debug('Draft snapshot skipped: %s', e)

    try:
        from quality_checker import get_quality_checker
        qc = get_quality_checker().check_episode_quality(
            episode_id,
            {'check_script': True, 'check_audio': False},
        )
        log_step(
            run_id,
            'quality_done',
            {
                'overall': qc.get('overall_quality'),
                'issues': len(qc.get('issues') or []),
            },
        )
        ep2 = ss.get_episode(episode_id)
        if ep2 is not None:
            ep2.setdefault('metadata', {})['last_agentic_qc'] = {
                'overall_quality': qc.get('overall_quality'),
                'script_quality': qc.get('script_quality'),
                'issue_count': len(qc.get('issues') or []),
            }
            ss._save_episode(ep2)
    except Exception as e:
        logger.warning('Agentic QA pass failed: %s', e)

    return script


def run_agentic_script_placeholder(episode_id: str) -> Dict[str, Any]:
    """Backward-compatible name; delegates to ``run_agentic_episode_script``."""
    if not should_use_agentic_pipeline():
        return {}
    return run_agentic_episode_script(episode_id)
