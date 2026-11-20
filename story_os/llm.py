"""Role-based LLM configuration and the one shared completion call (BASE-002).

Owns: which provider/model serves each role (planner, writer, editor,
extractor, judge_a, judge_b) and the single ``complete()`` call path with
retries, fallback and usage accounting.

Config lives in ``data/llm_config.json`` (optional). With no file, every role
resolves to the models the code used before this change
(OpenRouter ``anthropic/claude-opus-4.5``, fallback OpenAI ``gpt-4o``), and a
call site's own temperature is kept, so behaviour is unchanged.

Example ``data/llm_config.json``::

    {"roles": {"writer": {"provider": "openrouter",
                          "model": "anthropic/claude-opus-5.5"},
               "editor": {"provider": "openai", "model": "gpt-4o",
                          "temperature": 0.3}},
     "fallback": {"provider": "openai", "model": "gpt-4o"}}
"""

from __future__ import annotations

import copy
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

ROLES = ('planner', 'writer', 'editor', 'extractor', 'judge_a', 'judge_b')
LEGACY_OPENROUTER_MODEL = 'anthropic/claude-opus-4.5'
LEGACY_OPENAI_MODEL = 'gpt-4o'
OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
_KEY_ENV = {'openrouter': 'OPENROUTER_API_KEY', 'openai': 'OPENAI_API_KEY'}

_DEFAULTS: Dict[str, Any] = {
    'roles': {r: {'provider': 'openrouter', 'model': LEGACY_OPENROUTER_MODEL}
              for r in ROLES},
    'fallback': {'provider': 'openai', 'model': LEGACY_OPENAI_MODEL},
}

TestBackend = Callable[..., str]
_test_backend: Optional[TestBackend] = None
_clients: Dict[str, Any] = {}
_config_cache: Dict[str, Any] = {}
last_usage: Dict[str, Any] = {}


def config_path() -> Path:
    from config.paths import DATA_DIR
    return Path(DATA_DIR) / 'llm_config.json'


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Defaults merged with ``data/llm_config.json`` (cached by mtime)."""
    p = Path(path) if path else config_path()
    mtime = p.stat().st_mtime if p.exists() else None
    key = str(p)
    hit = _config_cache.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    cfg = copy.deepcopy(_DEFAULTS)
    if mtime is not None:
        try:
            with open(p, 'r', encoding='utf-8') as f:
                user = json.load(f)
            for role, spec in (user.get('roles') or {}).items():
                cfg['roles'].setdefault(role, {}).update(spec or {})
            if user.get('fallback'):
                cfg['fallback'].update(user['fallback'])
        except (OSError, json.JSONDecodeError) as e:
            logger.error('Ignoring unreadable %s: %s', p, e)
    _config_cache[key] = (mtime, cfg)
    return cfg


def _has_key(provider: str) -> bool:
    env = _KEY_ENV.get(provider)
    return bool(env and os.environ.get(env))


def resolve(role: str, path: Optional[Path] = None) -> Dict[str, Any]:
    """Provider/model spec for ``role``; uses the fallback if its key is absent."""
    cfg = load_config(path)
    if role not in cfg['roles']:
        raise KeyError(f'Unknown LLM role {role!r}; known: {sorted(cfg["roles"])}')
    spec = dict(cfg['roles'][role])
    if not _has_key(spec.get('provider', '')) and _has_key(
            cfg['fallback'].get('provider', '')):
        spec = dict(cfg['fallback'])
    return spec


def set_test_backend(fn: Optional[TestBackend]) -> None:
    """Route every ``complete()`` call to ``fn(role, system, user, **kw)``."""
    global _test_backend
    _test_backend = fn


def client_for(provider: str):
    """Shared OpenAI-SDK client for ``provider`` (raises if no key)."""
    return _client_for(provider)


def _client_for(provider: str):
    if provider in _clients:
        return _clients[provider]
    from openai import OpenAI
    key = os.environ.get(_KEY_ENV.get(provider, ''), '')
    if not key:
        raise RuntimeError(f'No API key for provider {provider!r} '
                           f'(set {_KEY_ENV.get(provider)})')
    if provider == 'openrouter':
        client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=key)
    elif provider == 'openai':
        client = OpenAI(api_key=key)
    else:
        raise RuntimeError(f'Unsupported provider {provider!r}')
    _clients[provider] = client
    return client


def complete(role: str, system: str, user: str, *, json: bool = False,
             max_tokens: Optional[int] = None,
             temperature: Optional[float] = None,
             clients: Optional[Dict[str, Any]] = None,
             retries: int = 3) -> str:
    """One chat completion for ``role``. Raises on final failure.

    ``temperature`` is the call site's default; a ``temperature`` set for the
    role in the config file wins over it. ``clients`` lets a caller supply
    its own provider clients (StoryStructure does, so tests that patch its
    clients keep working).
    """
    if _test_backend is not None:
        return _test_backend(role, system, user, json=json,
                             max_tokens=max_tokens, temperature=temperature)
    spec = resolve(role)
    provider = spec.get('provider', 'openrouter')
    client = (clients or {}).get(provider) or _client_for(provider)
    temp = spec.get('temperature', temperature if temperature is not None
                    else 0.7)
    kwargs: Dict[str, Any] = {
        'model': spec['model'],
        'temperature': temp,
        'messages': [{'role': 'system', 'content': system},
                     {'role': 'user', 'content': user}],
    }
    mt = spec.get('max_tokens') or max_tokens
    if mt:
        kwargs['max_tokens'] = int(mt)
    if json and provider == 'openai':
        kwargs['response_format'] = {'type': 'json_object'}

    delay = 2.0
    last_err: Optional[BaseException] = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            started = time.time()
            resp = client.chat.completions.create(**kwargs)
            text = (resp.choices[0].message.content or '').strip()
            usage = getattr(resp, 'usage', None)
            last_usage.clear()
            last_usage.update({
                'role': role, 'provider': provider, 'model': spec['model'],
                'prompt_tokens': getattr(usage, 'prompt_tokens', None),
                'completion_tokens': getattr(usage, 'completion_tokens', None),
                'seconds': round(time.time() - started, 2),
            })
            _trace(role, last_usage)
            return text
        except Exception as e:  # network / rate limit / provider error
            last_err = e
            if attempt < retries:
                logger.warning('LLM %s attempt %s failed (%s); retrying in '
                               '%.0fs', role, attempt, e, delay)
                time.sleep(delay)
                delay *= 2
    raise RuntimeError(f'LLM role {role!r} failed after {retries} attempts: '
                       f'{last_err}') from last_err


def _trace(role: str, usage: Dict[str, Any]) -> None:
    try:
        from generation_trace import log_step, trace_enabled
        if trace_enabled():
            log_step(os.environ.get('STARDOCK_RUN_ID', 'llm'), f'llm.{role}',
                     dict(usage))
    except Exception:
        pass
