"""Render the legacy (pre-v5 show) prompts with a stub LLM (BASE-003 golden).

``python -m tests.golden_legacy --write`` captures them into
``tests/fixtures/golden_legacy_prompts.json``; ``test_golden_legacy.py``
asserts the current code reproduces them byte for byte.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

FIXTURE = Path(__file__).parent / 'fixtures' / 'golden_legacy_prompts.json'


def render() -> dict:
    from story_os import llm
    calls = []

    def fake(role, system, user, **kw):
        calls.append({'role': role, 'system': system, 'user': user})
        if 'character' in system.lower() and 'creator' in system.lower():
            return 'Name: Ada\nRole: pilot\nPersonality: calm'
        return 'Setting: Bridge\nPlot: Something happens.\nKIRA: Hello there.'
    tmp = tempfile.mkdtemp()
    try:
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'x'}), \
                patch('story_structure.get_mem0_client'), \
                patch('story_structure.get_knowledge_context') as kn, \
                patch('story_structure.get_episode_memory'):
            kn.return_value.series_bible = {}
            kn.return_value.is_ready.return_value = True
            kn.return_value.get_rag_context.return_value = 'REF'
            kn.return_value.build_system_prompt.side_effect = lambda b: b
            llm.set_test_backend(fake)
            from story_structure import StoryStructure
            from story_os.asyncio_compat import run_coro
            ss = StoryStructure(episodes_dir=tmp)
            ep = ss.generate_episode_structure({'episode_id': 'ep_gold', 'theme': 'a signal',
                                                'series': 'Main Series', 'episode_number': 1,
                                                'target_duration': 5})
            ss.generate_character_cast('ep_gold')
            run_coro(ss.generate_scenes('ep_gold'))
            ep = ss.get_episode('ep_gold')
            ss._generate_scene_script(ep, ep['scenes'][0])
    finally:
        llm.set_test_backend(None)
        shutil.rmtree(tmp, ignore_errors=True)
    # outline prompts are identical except scene numbers; keep first and last
    outline = [c for c in calls if 'scene outline' in c['user']]
    keep = [c for c in calls if 'scene outline' not in c['user']] + outline[:1] + outline[-1:]
    return {'calls': keep}


if __name__ == '__main__':
    data = render()
    if '--write' in sys.argv:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(data, indent=2), encoding='utf-8')
        print('wrote', FIXTURE, len(data['calls']), 'prompts')
    else:
        print(json.dumps(data, indent=2)[:3000])
