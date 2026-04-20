#!/usr/bin/env python3
"""
Re-parse an existing ``script.json`` with the current parser.

When ``story_structure._parse_script_lines`` is improved (for example to
understand a new LLM output style) there is no need to re-run the
expensive multi-minute LLM generation for an episode that has already
produced a script whose *content* is good but whose structural
classification (dialogue vs description vs sound_effect, which speaker
each line belongs to) is wrong.

This CLI rebuilds the raw per-scene text from the existing line records,
feeds it through the current parser, and writes the re-parsed result
back to disk. The original file is preserved as
``script.backup-<timestamp>.json`` alongside the new one.

Typical usage::

    python cli/reparse_script.py ep_7ba65dfe

The episode id must correspond to an ``episodes/<id>/script.json``
directory produced by ``cli_entrypoint.py generate-script``.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from story_structure import get_story_structure
from script_line_ids import ensure_script_line_ids

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def _reconstruct_scene_text(scene: dict) -> str:
    """Rebuild the raw screenplay text that produced ``scene['lines']``.

    The parser operates on double-newline separated paragraphs, so each
    existing line record is emitted as its own paragraph. Dialogue lines
    are re-wrapped in the markdown speaker-header form so they survive a
    round-trip through the parser (and can be re-classified if they are
    currently misclassified as ``description``).
    """
    chunks: list[str] = []
    for line in scene.get('lines', []) or []:
        ltype = line.get('type')
        content = (line.get('content') or '').strip()
        if not content:
            continue

        if ltype == 'dialogue':
            character = (
                line.get('character') or line.get('speaker') or ''
            ).strip()
            if character:
                chunks.append(f"**{character.upper()}**\n{content}")
            else:
                chunks.append(content)
        elif ltype == 'narration':
            chunks.append(f"**NARRATOR**\n{content}")
        elif ltype == 'sound_effect':
            chunks.append(f"({content})")
        else:
            chunks.append(content)

    return "\n\n".join(chunks)


def reparse_script(
    episode_id: str,
    *,
    episodes_root: Path = Path('episodes'),
) -> int:
    """Re-parse ``episodes/<episode_id>/script.json`` in place.

    Returns 0 on success, non-zero on failure.
    """
    episode_dir = episodes_root / episode_id
    script_path = episode_dir / 'script.json'
    if not script_path.is_file():
        logger.error("script.json not found: %s", script_path)
        return 1

    with script_path.open('r', encoding='utf-8') as f:
        script = json.load(f)

    scenes = script.get('scenes') or []
    if not scenes:
        logger.error("No scenes in %s", script_path)
        return 1

    story = get_story_structure()
    total_before = sum(len(sc.get('lines') or []) for sc in scenes)

    new_scenes = []
    for scene in scenes:
        raw_text = _reconstruct_scene_text(scene)
        new_lines = story._parse_script_lines(raw_text)
        rebuilt = dict(scene)
        rebuilt['lines'] = new_lines
        new_scenes.append(rebuilt)

    script['scenes'] = new_scenes
    ensure_script_line_ids(script)

    total_after = sum(len(sc.get('lines') or []) for sc in new_scenes)
    dialogue_after = sum(
        1
        for sc in new_scenes
        for ln in sc['lines']
        if ln.get('type') == 'dialogue'
    )
    description_after = sum(
        1
        for sc in new_scenes
        for ln in sc['lines']
        if ln.get('type') == 'description'
    )
    narration_after = sum(
        1
        for sc in new_scenes
        for ln in sc['lines']
        if ln.get('type') == 'narration'
    )
    sfx_after = sum(
        1
        for sc in new_scenes
        for ln in sc['lines']
        if ln.get('type') == 'sound_effect'
    )

    backup_path = episode_dir / (
        f"script.backup-{int(time.time())}.json"
    )
    backup_path.write_text(
        script_path.read_text(encoding='utf-8'), encoding='utf-8')
    logger.info("Backed up original to %s", backup_path)

    with script_path.open('w', encoding='utf-8') as f:
        json.dump(script, f, indent=2)

    logger.info("Re-parsed %s", script_path)
    logger.info(
        "Line counts — before: %d | after: %d "
        "(dialogue=%d, description=%d, narration=%d, sound_effect=%d)",
        total_before,
        total_after,
        dialogue_after,
        description_after,
        narration_after,
        sfx_after,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Re-parse an existing episode script.json with the current "
            "parser (no LLM calls)."
        ),
    )
    parser.add_argument(
        'episode_id', help='Episode id, e.g. ep_7ba65dfe')
    parser.add_argument(
        '--episodes-root', default='episodes',
        help='Episodes root directory (default: episodes)')
    args = parser.parse_args()
    return reparse_script(
        args.episode_id, episodes_root=Path(args.episodes_root))


if __name__ == '__main__':
    sys.exit(main())
