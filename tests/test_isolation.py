"""GEN-003 / T18: project isolation for Mem0 and project files."""
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import mem0_client as M


class FakeMem0:
    def __init__(self):
        self.rows = []

    def add(self, content, user_id=None, metadata=None, infer=None):
        self.rows.append({'memory': content, 'user_id': user_id, 'metadata': metadata})
        return {'ok': True}

    def search(self, query, user_id=None, limit=5, **kw):
        uid = user_id or (kw.get('filters') or {}).get('user_id')
        return [r for r in self.rows if r['user_id'] == uid][:limit]


def _client():
    c = object.__new__(M.Mem0Client)
    c.client = FakeMem0()
    return c


def test_ns_rules():
    assert M.ns('show_a', 'refs') == 'show_a:refs'
    assert M.ns(M.LEGACY_PROJECT, 'refs') == 'reference_materials'
    with pytest.raises(ValueError):
        M.ns(None, 'refs')


def test_bound_clients_cannot_see_each_other():
    base = _client()
    a, b = base.for_project('show_a'), base.for_project('show_b')
    a.add_reference_material('A secret', source='x')
    b.add_reference_material('B secret', source='y')
    ids = {r['user_id'] for r in base.client.rows}
    assert ids == {'show_a:refs', 'show_b:refs'}
    assert all(r['metadata']['project_id'] in ('show_a', 'show_b') for r in base.client.rows)
    a_rows = base.client.search('secret', user_id=a._ns('refs'))
    assert [r['memory'] for r in a_rows] == ['A secret']
    with pytest.raises(ValueError):
        base.add_reference_material('no project', source='z')     # unbound refuses
    legacy = base.for_project(M.LEGACY_PROJECT)
    legacy.add_episode_memory('old show', episode_id='e1')
    assert base.client.rows[-1]['user_id'] == 'episodes'


def test_no_global_namespace_literals_left():
    root = Path(__file__).resolve().parents[1]
    bad = []
    pat = re.compile(r"user_id\s*=\s*['\"](reference_materials|episodes|characters|"
                     r"story_structures|voice_registry)['\"]")
    for py in root.glob('*.py'):
        if pat.search(py.read_text(encoding='utf-8', errors='ignore')):
            bad.append(py.name)
    for py in (root / 'story_os').glob('*.py'):
        if pat.search(py.read_text(encoding='utf-8', errors='ignore')):
            bad.append(py.name)
    assert bad == [], bad


def test_project_files_are_isolated(tmp_path):
    from unittest.mock import patch
    from story_os import projects
    from story_os.canon_store import CanonStore
    from story_os.project_models import ProjectConfig
    with patch('config.paths.DATA_DIR', tmp_path):
        for pid in ('a', 'b'):
            projects.create_project(
                ProjectConfig(project_id=pid, show_id=pid, title=pid, idea='i',
                              mode='serialized_fiction'),
                projects.Identity.model_validate({'cast': [{'name': f'Host {pid}'}]}),
                casting='simple')
        sa = CanonStore.for_episode({'project_id': 'a', 'episode_id': 'e'})
        sb = CanonStore.for_episode({'project_id': 'b', 'episode_id': 'e'})
        assert sa.dir != sb.dir and 'a' in sa.dir.parts and 'b' in sb.dir.parts
        assert projects.voices_path('a') != projects.voices_path('b')
