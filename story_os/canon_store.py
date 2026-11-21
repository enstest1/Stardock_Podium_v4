"""Append-only canon ledger + rebuildable SQLite index (CANON-001).

Owns ``<root>/canon/``::

    events.jsonl state_changes.jsonl beliefs.jsonl relationships.jsonl
    promises.jsonl corrections.jsonl   (append-only, never rewritten)
    index.sqlite                       (derived; delete and rebuild any time)

This module is the ONLY writer of the ledger files (a test greps for it).
Status changes and supersessions are appended to ``corrections.jsonl`` as
ops; ``promises.jsonl`` may hold several lines per promise, the latest wins.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from story_os.canon_models import ID_FIELD, KIND_FILES

_TABLES = tuple(KIND_FILES)


@contextmanager
def _locked_append(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        if os.name == 'nt':
            import msvcrt
            f.seek(0, 2)
            pos = f.tell()
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield f
                f.flush()
                os.fsync(f.fileno())
            finally:
                f.seek(pos)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield f
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


class CanonStore:
    """Ledger for one show (or one episode, for per-episode continuity)."""

    def __init__(self, root: Path):
        self.dir = Path(root) / 'canon'

    @classmethod
    def for_episode(cls, episode: Dict[str, Any]) -> Optional['CanonStore']:
        """Store for a project episode according to its continuity capability."""
        pid = episode.get('project_id')
        if not pid:
            return None
        from story_os import projects
        cont = projects.load_project(pid).capability('continuity')
        if cont in ('canon_full', 'canon_light'):
            return cls(projects.project_dir(pid))
        if cont in ('per_episode', 'per_story'):
            from config.paths import EPISODES_DIR
            return cls(Path(EPISODES_DIR) / episode['episode_id'])
        return None

    # ----------------------------------------------------------- writes --
    def _file(self, kind: str) -> Path:
        return self.dir / f'{kind}.jsonl'

    def append(self, kind: str, records: Iterable[Any]) -> int:
        model = KIND_FILES[kind]
        n = 0
        with _locked_append(self._file(kind)) as f:
            for r in records:
                rec = r if isinstance(r, model) else model.model_validate(r)
                f.write(rec.model_dump_json() + '\n')
                n += 1
        return n

    def _op(self, op: Dict[str, Any]) -> None:
        op = {**op, 'at': op.get('at', time.time())}
        with _locked_append(self.dir / 'corrections.jsonl') as f:
            f.write(json.dumps(op, sort_keys=True) + '\n')

    def set_status(self, episode_id: str, status: str) -> None:
        self._op({'op': 'status', 'episode_id': episode_id, 'status': status})

    def correct(self, kind: str, record_id: str, new_record: Any, reason: str) -> None:
        self.append(kind, [new_record])
        new_id = getattr(new_record, ID_FIELD[kind], None) or new_record[ID_FIELD[kind]]
        self._op({'op': 'supersede', 'kind': kind, 'id': record_id,
                  'by': new_id, 'reason': reason})

    # ------------------------------------------------------------ reads --
    def _read(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]

    def records(self, kind: str) -> List[Dict[str, Any]]:
        """Replay a kind with corrections applied (latest line per id)."""
        idf = ID_FIELD[kind]
        latest: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for rec in self._read(self._file(kind)):
            if rec[idf] not in latest:
                order.append(rec[idf])
            latest[rec[idf]] = rec
        status: Dict[str, str] = {}
        superseded = set()
        for op in self._read(self.dir / 'corrections.jsonl'):
            if op['op'] == 'status':
                status[op['episode_id']] = op['status']
            elif op['op'] == 'supersede' and op.get('kind') == kind:
                superseded.add(op['id'])
        out = []
        for rid in order:
            rec = dict(latest[rid])
            if rec['episode_id'] in status:
                rec['status'] = status[rec['episode_id']]
            if rid in superseded:
                rec['status'] = 'superseded'
            out.append(rec)
        return out

    def query(self, kind: str, *, include_draft_episode: Optional[str] = None,
              **where) -> List[Dict[str, Any]]:
        rows = []
        for r in self.records(kind):
            ok = r['status'] == 'canon' or (
                include_draft_episode and r['episode_id'] == include_draft_episode
                and r['status'] == 'draft')
            if ok and all(r.get(k) == v for k, v in where.items()):
                rows.append(r)
        return rows

    def next_number(self, kind: str, prefix: str) -> int:
        idf = ID_FIELD[kind]
        return 1 + sum(1 for r in self._read(self._file(kind))
                       if str(r.get(idf, '')).startswith(prefix))

    # --------------------------------------------------- derived queries --
    def mistaken_about(self, event_id: str) -> List[str]:
        return sorted({b['holder'] for b in self.query('beliefs')
                       if b.get('about_event_id') == event_id and b['truth'] == 'false'})

    def beliefs_of(self, holder: str, **kw) -> List[Dict[str, Any]]:
        h = holder.strip().lower()
        return [b for b in self.query('beliefs', **kw) if b['holder'].lower() == h]

    def open_promises(self, horizons=('season', 'series'), **kw) -> List[Dict[str, Any]]:
        return [p for p in self.query('promises', **kw)
                if p['state'] in ('open', 'developed') and p['horizon'] in horizons]

    def character_state(self, name: str, **kw) -> Dict[str, str]:
        """Latest value per attribute for an entity, replayed in ledger order."""
        state: Dict[str, str] = {}
        n = name.strip().lower()
        for c in self.query('state_changes', **kw):
            if c['entity'].strip().lower() == n:
                state[c['attribute']] = c['after']
        return state

    def continuity_brief(self, limit: int = 12) -> str:
        """Compact canon summary for planning prompts (ledger-first context)."""
        ev = self.query('events')[-limit:]
        lines = []
        if ev:
            lines.append('ESTABLISHED FACTS (canon):')
            lines += [f"- [{e['event_id']}] {e['summary']}" for e in ev]
        ents = sorted({c['entity'] for c in self.query('state_changes')})
        states = [(e, self.character_state(e)) for e in ents]
        if states:
            lines.append('CURRENT STATE:')
            lines += [f"- {e}: " + '; '.join(f'{k}={v}' for k, v in s.items())
                      for e, s in states if s]
        mis = [b for b in self.query('beliefs') if b['truth'] == 'false']
        if mis:
            lines.append('MISTAKEN BELIEFS (dramatic irony available):')
            lines += [f"- {b['holder']} wrongly {b['stance']}: {b['proposition']}"
                      for b in mis[-6:]]
        prom = self.open_promises(horizons=('episode', 'season', 'series'))
        if prom:
            lines.append('OPEN PROMISES TO THE AUDIENCE (develop or pay off):')
            lines += [f"- [{p['promise_id']}] ({p['kind']}, {p['horizon']}) {p['statement']}"
                      for p in prom[-8:]]
        return '\n'.join(lines)

    # ------------------------------------------------------------ index --
    def rebuild_index(self) -> Path:
        """Drop and recreate index.sqlite from the ledger (deterministic)."""
        db_path = self.dir / 'index.sqlite'
        self.dir.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()
        con = sqlite3.connect(db_path)
        try:
            for kind in _TABLES:
                con.execute(f'CREATE TABLE {kind} (id TEXT PRIMARY KEY, '
                            'episode_id TEXT, status TEXT, body TEXT)')
                for r in self.records(kind):
                    con.execute(f'INSERT INTO {kind} VALUES (?,?,?,?)',
                                (r[ID_FIELD[kind]], r['episode_id'], r['status'],
                                 json.dumps(r, sort_keys=True)))
            con.commit()
        finally:
            con.close()
        return db_path
