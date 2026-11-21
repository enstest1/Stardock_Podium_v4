"""BASE-003: legacy prompts and TTS normalisation are byte-identical after
franchise text moved from code to data/shows/legacy_format.json."""
import json
import re
from pathlib import Path

FIX = Path(__file__).parent / 'fixtures'


def test_legacy_prompts_byte_identical():
    from tests.golden_legacy import render
    golden = json.loads((FIX / 'golden_legacy_prompts.json').read_text(encoding='utf-8'))
    assert render() == golden


def test_legacy_tts_normalisation_identical():
    import tts_pronunciation as T
    T.set_active_show(None)
    for s in json.loads((FIX / 'golden_tts_normalize.json').read_text(encoding='utf-8'))['samples']:
        assert T.normalize_tts_text(s['text']) == s['expected']


def test_project_rules_replace_legacy_rules():
    import tts_pronunciation as T
    T.set_active_show({'Oyelaran': 'oh-yeh-LAH-ran'}, [])
    try:
        out = T.normalize_tts_text('Oyelaran met a Vulcan, Stardate 12.5')
        assert out == 'oh-yeh-LAH-ran met a Vulcan, Stardate 12.5'
    finally:
        T.set_active_show(None)


def test_no_franchise_words_in_code():
    root = Path(__file__).resolve().parents[1]
    pat = re.compile(r'star trek|starfleet|stardate|celestial temple|gamma quadrant|bajor|'
                     r'klingon|vulcan|transporter|shuttlecraft|trek', re.I)
    skip = {'tests', 'cli', '.venv', '.venv-xtts', 'site-packages', '__pycache__'}
    hits = []
    for py in root.rglob('*.py'):
        rel = py.relative_to(root)
        if set(rel.parts) & skip or rel.name.startswith('register_voices') \
                or rel.as_posix() == 'story_os/migrate.py':
            continue
        for i, line in enumerate(py.read_text(encoding='utf-8', errors='ignore').splitlines(), 1):
            if pat.search(line):
                hits.append(f'{rel}:{i}: {line.strip()[:80]}')
    assert hits == [], '\n'.join(hits)
