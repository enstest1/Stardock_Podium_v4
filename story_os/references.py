"""Reference registry, technique profiles, world import, lifecycle.

REF-001 registry on the existing ingestion path (EPUB via epub_processor;
txt/md/html here; pdf/docx when pypdf / python-docx are installed),
REF-002 closed-vocabulary style profiles + bindings + directives,
REF-004 authorised world building (rights-gated canon import),
REF-005 enable/disable/remove/purge + per-episode snapshots.

Files under ``data/projects/<id>/refs/``::
  index.json                 {source_id: ReferenceSource}
  <source_id>/sections.json  [{locator, title, text}]
  <source_id>/profile.json   StyleProfile (writing_techniques only)
  bindings.json              [ReferenceBinding]
  audit.jsonl                one line per state change (append-only)

A technique reference reaches prompts only as rendered directives: never its
text, title, author or names. ``unspecified`` rights are never permission
for world building or adaptation (model validator).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from story_os.project_models import (CATEGORICAL_TRAITS, NUMERIC_TRAITS,
                                     ReferenceBinding, ReferenceSource, Rights,
                                     Scope, StyleProfile, render_directives,
                                     resolve_style)

logger = logging.getLogger(__name__)

FORMATS = {'.epub': 'epub', '.pdf': 'pdf', '.docx': 'docx', '.txt': 'txt',
           '.md': 'md', '.markdown': 'md', '.html': 'html', '.htm': 'html'}


def refs_dir(project_id: str) -> Path:
    from story_os.projects import project_dir
    return project_dir(project_id) / 'refs'


def _load_index(project_id: str) -> Dict[str, Any]:
    p = refs_dir(project_id) / 'index.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def _save_index(project_id: str, idx: Dict[str, Any]) -> None:
    from story_os.projects import atomic_write_json
    atomic_write_json(refs_dir(project_id) / 'index.json', idx)


def audit(project_id: str, event: Dict[str, Any]) -> None:
    p = refs_dir(project_id) / 'audit.jsonl'
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'at': time.time(), **event}, sort_keys=True) + '\n')


# -------------------------------------------------------------- loaders ----

def _split_text(text: str, max_chars: int = 3000) -> List[Dict[str, str]]:
    parts = re.split(r'\n(?=#{1,3}\s)', text)
    out = []
    for i, part in enumerate(parts, 1):
        title = part.strip().split('\n', 1)[0].lstrip('# ').strip()[:80]
        body = part.strip()
        for j in range(0, len(body), max_chars):
            out.append({'locator': f'section {i}' + (f'.{j // max_chars + 1}' if len(body) > max_chars else ''),
                        'title': title, 'text': body[j:j + max_chars]})
    return [s for s in out if s['text'].strip()]


def load_sections(path: Path) -> List[Dict[str, str]]:
    fmt = FORMATS.get(path.suffix.lower())
    if fmt in ('txt', 'md'):
        return _split_text(path.read_text(encoding='utf-8', errors='replace'))
    if fmt == 'html':
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(path.read_text(encoding='utf-8', errors='replace'), 'html.parser')
        return _split_text(soup.get_text('\n'))
    if fmt == 'epub':
        from epub_processor import get_processor
        proc = get_processor()
        info = proc.process_epub(str(path))
        chapters = proc.get_book_chapters(info.get('book_id') or info.get('id'))
        out = []
        for i, ch in enumerate(chapters, 1):
            text = ch.get('text') or ch.get('content') or ''
            for s in _split_text(text):
                out.append({'locator': f'ch. {i} ' + s['locator'],
                            'title': ch.get('title', ''), 'text': s['text']})
        return out
    if fmt == 'pdf':
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise RuntimeError('PDF references need: pip install pypdf') from e
        return [{'locator': f'p. {i}', 'title': '', 'text': (pg.extract_text() or '')}
                for i, pg in enumerate(PdfReader(str(path)).pages, 1)
                if (pg.extract_text() or '').strip()]
    if fmt == 'docx':
        try:
            import docx
        except ImportError as e:
            raise RuntimeError('DOCX references need: pip install python-docx') from e
        return _split_text('\n'.join(p.text for p in docx.Document(str(path)).paragraphs))
    raise ValueError(f'unsupported reference format: {path.suffix}')


# ------------------------------------------------------------- registry ----

def add_reference(path: str, project_id: str, purposes: List[str], *,
                  rights: str = 'unspecified', holder: str = '', evidence: str = '',
                  attribution: str = '', title: Optional[str] = None, author: str = '',
                  extract: bool = True) -> ReferenceSource:
    p = Path(path)
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    sid = 'SRC-' + sha[:12]
    idx = _load_index(project_id)
    if sid in idx and not idx[sid].get('removed_at'):
        return ReferenceSource.model_validate(idx[sid])      # idempotent
    src = ReferenceSource(                                   # validates rights
        source_id=sid, project_id=project_id, source_format=FORMATS.get(p.suffix.lower(), 'notes'),
        title=title or p.stem, author=author, purposes=purposes,
        rights=Rights(status=rights, holder=holder, evidence=evidence,
                      attribution_text=attribution, recorded_at=time.time()),
        ingested_at=time.time(), content_sha256=sha)
    sections = load_sections(p)
    d = refs_dir(project_id) / sid
    d.mkdir(parents=True, exist_ok=True)
    (d / 'sections.json').write_text(json.dumps(sections, ensure_ascii=False), encoding='utf-8')
    idx[sid] = src.model_dump()
    _save_index(project_id, idx)
    audit(project_id, {'op': 'add', 'source_id': sid, 'purposes': purposes, 'rights': rights})
    if extract:
        run_extractors(project_id, sid)
    return ReferenceSource.model_validate(_load_index(project_id)[sid])


def run_extractors(project_id: str, source_id: str) -> Dict[str, Any]:
    """Only the extractors for the selected purposes run (no Mem0 sync)."""
    src = load_source(project_id, source_id)
    out: Dict[str, Any] = {}
    if 'writing_techniques' in src.purposes:
        out['style'] = extract_style_profile(project_id, source_id).model_dump()
    if 'factual_research' in src.purposes:
        from story_os.claims import extract_claims
        out['claims'] = len(extract_claims(project_id, source_id))
    if 'world_building' in src.purposes:
        out['world_events'] = import_world(project_id, source_id)
    return out


def load_source(project_id: str, source_id: str) -> ReferenceSource:
    return ReferenceSource.model_validate(_load_index(project_id)[source_id])


def load_sections_for(project_id: str, source_id: str) -> List[Dict[str, str]]:
    p = refs_dir(project_id) / source_id / 'sections.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []


def list_sources(project_id: str, *, enabled_only: bool = True,
                 purpose: Optional[str] = None) -> List[ReferenceSource]:
    """The only way other modules find references (project + explicit shares)."""
    from story_os.projects import load_project
    pids = [project_id]
    try:
        pids += list(load_project(project_id).shared_reference_projects)
    except Exception:
        pass
    out = []
    for pid in pids:
        for rec in _load_index(pid).values():
            src = ReferenceSource.model_validate(rec)
            if src.removed_at or (enabled_only and not src.enabled):
                continue
            if purpose and purpose not in src.purposes:
                continue
            if pid != project_id and src.purposes != ['factual_research'] and \
                    'writing_techniques' not in src.purposes:
                continue          # sharing is references-only (facts/technique)
            out.append(src)
    return out


def _update(project_id: str, source_id: str, op: str, **fields) -> None:
    idx = _load_index(project_id)
    idx[source_id].update(fields)
    ReferenceSource.model_validate(idx[source_id])
    _save_index(project_id, idx)
    audit(project_id, {'op': op, 'source_id': source_id, **fields})


def set_enabled(project_id: str, source_id: str, enabled: bool) -> None:
    _update(project_id, source_id, 'enable' if enabled else 'disable', enabled=enabled)


def remove(project_id: str, source_id: str) -> None:
    _update(project_id, source_id, 'remove', removed_at=time.time())


def purge(project_id: str, source_id: str) -> Dict[str, Any]:
    """Delete extracted data; keep the record, the audit log and anything an
    approved episode cites (claims referenced by a script, source canon)."""
    from story_os.claims import ClaimStore
    d = refs_dir(project_id) / source_id
    kept = ClaimStore(project_id).purge_source(source_id)
    if d.exists():
        shutil.rmtree(d)
    _update(project_id, source_id, 'purge', purged_at=time.time(),
            removed_at=time.time())
    return {'kept_cited_claims': kept}


# ------------------------------------------------------- style (REF-002) ----

def measure(text: str) -> Dict[str, float]:
    sentences = [s for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    words = text.split()
    quoted = sum(len(q.split()) for q in re.findall(r'["“]([^"”]+)["”]', text))
    return {'avg_sentence_words': round(len(words) / max(1, len(sentences)), 2),
            'dialogue_ratio': round(quoted / max(1, len(words)), 3),
            'words_sampled': float(len(words))}


# Deterministic mappings (documented constants).
SENTENCE_LEN_SHORT, SENTENCE_LEN_LONG = 8.0, 28.0      # words -> 0 .. 1
DIALOGUE_LOW, DIALOGUE_HIGH = 0.05, 0.6                 # ratio -> 0 .. 1


def _scale(v, lo, hi):
    return round(max(0.0, min(1.0, (v - lo) / (hi - lo))), 3)


def name_candidates(text: str) -> List[str]:
    caps = re.findall(r'\b([A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})?)\b', text)
    common = {'The', 'And', 'But', 'She', 'They', 'This', 'That', 'There', 'When', 'Then',
              'What', 'His', 'Her', 'Its', 'You', 'Chapter', 'Section'}
    return sorted(n for n, c in Counter(caps).items() if c >= 3 and n not in common)


def name_leak_guard(profile: StyleProfile, text: str) -> List[str]:
    blob = json.dumps(profile.model_dump()) + ' ' + ' '.join(
        render_directives(resolve_style(profile, [], {}, {}, Scope(project_id='x'))))
    return [n for n in name_candidates(text) if n.lower() in blob.lower()]


def extract_style_profile(project_id: str, source_id: str) -> StyleProfile:
    from story_os import llm
    from story_os.projects import _json_from
    sections = load_sections_for(project_id, source_id)
    sample = '\n\n'.join(s['text'] for s in sections[:: max(1, len(sections) // 6)][:6])[:12000]
    stats = measure(sample)
    vocab = {k: list(v) for k, v in CATEGORICAL_TRAITS.items()}
    system = ('You describe HOW a text is written using only a fixed vocabulary. '
              'Never output names, titles, plot or quotations. JSON only.')
    user = (f'TEXT SAMPLE:\n{sample}\n\nScore each numeric trait 0..1: {list(NUMERIC_TRAITS)}. '
            f'Pick one value for each categorical trait from: {json.dumps(vocab)}.\n'
            'Return JSON: {"numeric": {...}, "categorical": {...}}')
    data = _json_from(llm.complete('extractor', system, user, json=True,
                                   max_tokens=600, temperature=0.0))
    numeric = {k: float(v) for k, v in (data.get('numeric') or {}).items()
               if k in NUMERIC_TRAITS and isinstance(v, (int, float))}
    numeric['sentence_length'] = _scale(stats['avg_sentence_words'],
                                        SENTENCE_LEN_SHORT, SENTENCE_LEN_LONG)
    numeric['dialogue_density'] = _scale(stats['dialogue_ratio'], DIALOGUE_LOW, DIALOGUE_HIGH)
    categorical = {k: v for k, v in (data.get('categorical') or {}).items()
                   if k in CATEGORICAL_TRAITS and v in CATEGORICAL_TRAITS[k]}
    profile = StyleProfile(source_id=source_id, numeric=numeric,
                           categorical=categorical, measured=stats)
    leaks = name_leak_guard(profile, sample)
    if leaks:
        raise ValueError(f'style profile leaks names: {leaks}')
    (refs_dir(project_id) / source_id / 'profile.json').write_text(
        json.dumps(profile.model_dump(), indent=2), encoding='utf-8')
    audit(project_id, {'op': 'profile', 'source_id': source_id})
    return profile


def load_bindings(project_id: str) -> List[ReferenceBinding]:
    p = refs_dir(project_id) / 'bindings.json'
    return [ReferenceBinding.model_validate(b) for b in
            json.loads(p.read_text(encoding='utf-8'))] if p.exists() else []


def bind(project_id: str, source_id: str, influence: float,
         traits: Dict[str, float], *, episode_id: Optional[str] = None) -> ReferenceBinding:
    from story_os.projects import atomic_write_json
    b = ReferenceBinding(source_id=source_id, reference_mode='writing_techniques',
                         influence=influence, selected_traits=traits,
                         scope=Scope(project_id=project_id, show_id=project_id,
                                     episode_id=episode_id))
    rest = [x for x in load_bindings(project_id)
            if not (x.source_id == source_id and x.scope.episode_id == episode_id)]
    atomic_write_json(refs_dir(project_id) / 'bindings.json',
                      [x.model_dump() for x in rest + [b]])
    audit(project_id, {'op': 'bind', 'source_id': source_id, 'influence': influence,
                       'episode_id': episode_id})
    return b


def style_directives(project_id: str, episode_id: Optional[str] = None) -> List[str]:
    """Rendered directives for a scope ([] when no technique reference is bound)."""
    bindings = load_bindings(project_id)
    if not bindings:
        return []
    sources = {s.source_id: s for s in list_sources(project_id, purpose='writing_techniques')}
    profiles = {}
    for sid in sources:
        p = refs_dir(project_id) / sid / 'profile.json'
        if p.exists():
            profiles[sid] = StyleProfile.model_validate(json.loads(p.read_text(encoding='utf-8')))
    bindings = [b for b in bindings if b.source_id in profiles]
    if not bindings:
        return []
    baseline = StyleProfile(source_id='BASELINE')
    resolved = resolve_style(baseline, bindings, profiles, sources,
                             Scope(project_id=project_id, show_id=project_id,
                                   episode_id=episode_id))
    touched = {t.trait for t in resolved.trace if t.contributions}
    lines = render_directives(resolved)
    return [l for l in lines if l.split(':')[0].replace(' ', '_') in touched]


def snapshot(project_id: str, episode_id: str, episodes_dir: Path) -> Path:
    """REF-005: what references shaped this episode (kept forever)."""
    snap = {'at': time.time(), 'sources': [s.model_dump() for s in list_sources(project_id)],
            'bindings': [b.model_dump() for b in load_bindings(project_id)],
            'directives': style_directives(project_id, episode_id)}
    p = Path(episodes_dir) / episode_id / 'reference_snapshot.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snap, indent=2), encoding='utf-8')
    return p


# ------------------------------------------------------- world (REF-004) ----

def import_world(project_id: str, source_id: str, max_sections: int = 6) -> int:
    """Rights-gated: quoted facts become canon events with origin='source'."""
    from story_os import llm
    from story_os.canon_extract import norm
    from story_os.canon_models import CanonEvent, Evidence, Verification
    from story_os.canon_store import CanonStore
    from story_os.projects import _json_from, project_dir
    src = load_source(project_id, source_id)
    if src.rights.status not in ('owned', 'licensed', 'public_domain'):
        raise PermissionError('world building needs owned, licensed or public_domain rights')
    store = CanonStore(project_dir(project_id))
    n = 0
    for sec in load_sections_for(project_id, source_id)[:max_sections]:
        data = _json_from(llm.complete(
            'extractor', 'You extract established world facts with exact quotes. JSON only.',
            f"TEXT ({sec['locator']}):\n{sec['text']}\n\nReturn JSON: {{\"facts\": "
            '[{"summary": "...", "actors": [], "quote": "exact words from the text"}]}',
            json=True, max_tokens=1500, temperature=0.0))
        for f in data.get('facts') or []:
            q = norm(f.get('quote', ''))
            if len(q.split()) < 3 or q not in norm(sec['text']):
                continue
            n += 1
            store.append('events', [CanonEvent(
                event_id=f'EV-{source_id}-{n:03d}', episode_id=f'REF:{source_id}',
                summary=f.get('summary', ''), actors=f.get('actors') or [],
                origin='source', source_id=source_id, status='draft',
                evidence=Evidence(episode_id=f'REF:{source_id}', line_ids=[sec['locator']],
                                  quote=f['quote']),
                verification=Verification(quote_ok=True))])
    store.set_status(f'REF:{source_id}', 'canon')
    store.rebuild_index()
    audit(project_id, {'op': 'world_import', 'source_id': source_id, 'events': n})
    return n
