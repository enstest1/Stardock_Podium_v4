"""Tests for story_os.llm role config (BASE-002). No network."""
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from story_os import llm


@pytest.fixture(autouse=True)
def _reset():
    llm.set_test_backend(None)
    llm._config_cache.clear()
    yield
    llm.set_test_backend(None)
    llm._config_cache.clear()


def test_defaults_reproduce_legacy_models(tmp_path):
    cfg = llm.load_config(tmp_path / 'missing.json')
    for role in llm.ROLES:
        assert cfg['roles'][role]['model'] == 'anthropic/claude-opus-4.5'
        assert cfg['roles'][role]['provider'] == 'openrouter'
    assert cfg['fallback'] == {'provider': 'openai', 'model': 'gpt-4o'}


def test_file_overrides_one_role(tmp_path):
    p = tmp_path / 'llm_config.json'
    p.write_text(json.dumps({'roles': {'editor': {
        'provider': 'openai', 'model': 'gpt-x', 'temperature': 0.1}}}))
    cfg = llm.load_config(p)
    assert cfg['roles']['editor']['model'] == 'gpt-x'
    assert cfg['roles']['writer']['model'] == 'anthropic/claude-opus-4.5'


def test_fallback_when_primary_key_missing(tmp_path):
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'k'}, clear=True):
        spec = llm.resolve('writer', tmp_path / 'missing.json')
    assert spec == {'provider': 'openai', 'model': 'gpt-4o'}


def test_unknown_role_raises(tmp_path):
    with pytest.raises(KeyError):
        llm.resolve('nope', tmp_path / 'missing.json')


def test_test_backend_short_circuits():
    seen = {}

    def fake(role, system, user, **kw):
        seen.update(role=role, user=user, **kw)
        return 'ok'
    llm.set_test_backend(fake)
    assert llm.complete('judge_a', 's', 'u', max_tokens=5) == 'ok'
    assert seen['role'] == 'judge_a' and seen['max_tokens'] == 5


def test_call_site_temperature_kept_unless_config_sets_one(tmp_path):
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=' hi '))]
    with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'k'}, clear=True), \
            patch.object(llm, 'config_path', return_value=tmp_path / 'x.json'):
        out = llm.complete('writer', 's', 'u', temperature=0.65,
                           max_tokens=10, clients={'openrouter': client})
    assert out == 'hi'
    kw = client.chat.completions.create.call_args.kwargs
    assert kw['temperature'] == 0.65
    assert kw['model'] == 'anthropic/claude-opus-4.5'
    assert kw['max_tokens'] == 10


def test_fails_over_to_fallback_on_billing_error(tmp_path):
    class Billing(Exception):
        status_code = 402
    primary, backup = MagicMock(), MagicMock()
    primary.chat.completions.create.side_effect = Billing('no credits')
    backup.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='from backup'))]
    with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'k',
                                 'OPENAI_API_KEY': 'k'}, clear=True), \
            patch.object(llm, 'config_path', return_value=tmp_path / 'x.json'):
        out = llm.complete('writer', 's', 'u', clients={
            'openrouter': primary, 'openai': backup})
    assert out == 'from backup'
    assert primary.chat.completions.create.call_count == 1  # no retry on 402
    assert backup.chat.completions.create.call_args.kwargs['model'] == 'gpt-4o'
