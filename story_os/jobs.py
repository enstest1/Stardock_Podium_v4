"""Resumable production jobs (AUTO-001).

Owns ``episodes/<id>/job.json`` and ``episodes/<id>/snapshots/``.
A stage is skipped when it finished before with the same input hash
(SHA-256 over its input files' contents, relevant config and
``PIPELINE_VERSION``). Per-unit progress lives with the units themselves:
scene drafts in ``drafts/scenes/`` (written by StoryStructure) and line
audio in ``audio/lines/`` (AUDIO-001 cache).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

PIPELINE_VERSION = 'v5.0'
STALE_LOCK_SECONDS = 2 * 3600


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    if not path.exists():
        return 'missing'
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def inputs_hash(paths: Iterable[Path], config: Any = None) -> str:
    h = hashlib.sha256(PIPELINE_VERSION.encode())
    for p in sorted(str(x) for x in paths):
        h.update(p.encode())
        h.update(file_hash(Path(p)).encode())
    h.update(json.dumps(config, sort_keys=True, default=str).encode())
    return h.hexdigest()


class Job:
    def __init__(self, episode_dir: Path):
        self.dir = Path(episode_dir)
        self.path = self.dir / 'job.json'
        self.lock = self.dir / 'job.lock'
        self.state: Dict[str, Any] = {'pipeline_version': PIPELINE_VERSION, 'stages': {}}
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding='utf-8'))

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(self.state, indent=2), encoding='utf-8')
        os.replace(tmp, self.path)

    def acquire(self) -> None:
        if self.lock.exists():
            age = time.time() - self.lock.stat().st_mtime
            if age < STALE_LOCK_SECONDS:
                raise RuntimeError(f'job is locked by another run ({self.lock}); '
                                   'delete it if that run is dead')
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lock.write_text(json.dumps({'pid': os.getpid(), 'at': time.time()}))

    def release(self) -> None:
        try:
            self.lock.unlink()
        except FileNotFoundError:
            pass

    def snapshot(self, names=('structure.json', 'script.json'), label: str = '') -> None:
        snap = self.dir / 'snapshots'
        for n in names:
            src = self.dir / n
            if src.exists():
                snap.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, snap / f'{int(time.time())}_{label}_{n}')

    def run_stage(self, name: str, fn: Callable[[], Any], inputs: Iterable[Path] = (),
                  config: Any = None, *, force: bool = False) -> Dict[str, Any]:
        """Run ``fn`` unless already done with identical inputs."""
        ih = inputs_hash(list(inputs), config)
        rec = self.state['stages'].get(name) or {}
        if not force and rec.get('status') == 'done' and rec.get('input_hash') == ih:
            return {'skipped': True, 'result': rec.get('result')}
        self.snapshot(label=name)
        rec = {'status': 'running', 'started_at': time.time(), 'input_hash': ih}
        self.state['stages'][name] = rec
        self.save()
        try:
            result = fn()
        except Exception as e:
            rec.update(status='failed', error=str(e)[:500], finished_at=time.time())
            self.save()
            raise
        rec.update(status='done', finished_at=time.time(),
                   result=result if isinstance(result, (dict, list, str, int, float, type(None))) else None)
        self.save()
        return {'skipped': False, 'result': result}

    def invalidate_from(self, order: Iterable[str], stage: str) -> None:
        hit = False
        for s in order:
            hit = hit or s == stage
            if hit and s in self.state['stages']:
                self.state['stages'][s]['status'] = 'stale'
        self.save()
