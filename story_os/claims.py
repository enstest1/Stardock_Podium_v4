"""Factual research: claims, citations, conflicts, script check (REF-003).

Owns ``data/projects/<id>/refs/claims.jsonl`` (append-only; latest line per
``claim_id`` wins). Every claim carries a verified verbatim quote with a
locator. Conflicting claims are linked both ways and kept: never merged,
averaged or silently chosen (support becomes ``contested``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from story_os.project_models import Citation, FactClaim

_NUM = re.compile(r'\b\d[\d,.]*\b')
HEDGES = ('may', 'might', 'some say', 'disputed', 'estimates', 'roughly', 'about',
          'around', 'reportedly', 'it is thought', 'possibly', 'probably', 'sources differ',
          'unclear', 'contested', 'approximately')


class ClaimStore:
    def __init__(self, project_id: str):
        from story_os.references import refs_dir
        self.project_id = project_id
        self.path = refs_dir(project_id) / 'claims.jsonl'

    def append(self, claims: List[FactClaim]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'a', encoding='utf-8') as f:
            for c in claims:
                f.write(c.model_dump_json() + '\n')

    def all(self) -> Dict[str, FactClaim]:
        out: Dict[str, FactClaim] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    c = FactClaim.model_validate_json(line)
                    out[c.claim_id] = c
        return out

    def next_id(self) -> str:
        return f'CL-{len(self.all()) + 1:04d}'

    def purge_source(self, source_id: str) -> int:
        """Drop uncited claims of a source; keep ones a script cites."""
        cited = _cited_claim_ids(self.project_id)
        keep, kept = [], 0
        for c in self.all().values():
            if any(ci.source_id == source_id for ci in c.citations):
                if c.claim_id in cited:
                    kept += 1
                    keep.append(c)
                continue
            keep.append(c)
        self.path.write_text(''.join(c.model_dump_json() + '\n' for c in keep), encoding='utf-8')
        return kept


def _cited_claim_ids(project_id: str) -> set:
    from config.paths import EPISODES_DIR
    ids = set()
    for p in Path(EPISODES_DIR).glob('*/script.json'):
        try:
            s = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        for sc in s.get('scenes') or []:
            for l in sc.get('lines') or []:
                ids.update(l.get('claim_refs') or [])
    return ids


def extract_claims(project_id: str, source_id: str, max_sections: int = 8) -> List[FactClaim]:
    from story_os import llm
    from story_os.canon_extract import norm
    from story_os.projects import _json_from
    from story_os.references import load_sections_for
    store = ClaimStore(project_id)
    out: List[FactClaim] = []
    dropped = 0
    for sec in load_sections_for(project_id, source_id)[:max_sections]:
        try:
            data = _json_from(llm.complete(
                'extractor', 'You extract checkable factual claims with exact quotes. JSON only.',
                f"TEXT ({sec['locator']}):\n{sec['text']}\n\nReturn JSON: {{\"claims\": "
                '[{"text": "the claim in plain words", "kind": "fact|figure|date|quote|estimate|'
                'interpretation|opinion", "quote": "exact supporting words"}]}',
                json=True, max_tokens=1500, temperature=0.0))
        except Exception:
            continue
        for c in data.get('claims') or []:
            q = norm(c.get('quote', ''))
            if len(q.split()) < 3 or q not in norm(sec['text']):
                dropped += 1
                continue
            kind = c.get('kind') if c.get('kind') in ('fact', 'figure', 'date', 'quote', 'estimate',
                                                      'interpretation', 'opinion') else 'fact'
            claim = FactClaim(claim_id=f'CL-{len(store.all()) + len(out) + 1:04d}',
                              project_id=project_id, text=c.get('text', ''), kind=kind,
                              citations=[Citation(source_id=source_id, locator=sec['locator'],
                                                  quote=c['quote'])],
                              verified_by=['quote_match'])
            out.append(claim)
    store.append(out)
    link_conflicts(project_id)
    return out


def _entities(text: str) -> set:
    return {w.lower() for w in re.findall(r'\b[A-Z][a-z]{2,}\b', text)}


def candidate_conflicts(claims: List[FactClaim]) -> List[tuple]:
    pairs = []
    for i, a in enumerate(claims):
        for b in claims[i + 1:]:
            if {c.source_id for c in a.citations} == {c.source_id for c in b.citations}:
                continue
            shared = _entities(a.text) & _entities(b.text)
            na, nb = set(_NUM.findall(a.text)), set(_NUM.findall(b.text))
            if shared and na and nb and na != nb:
                pairs.append((a.claim_id, b.claim_id))
    return pairs


def link_conflicts(project_id: str, judge=None) -> List[tuple]:
    from story_os.canon_extract import judge_claim
    store = ClaimStore(project_id)
    claims = store.all()
    linked = []
    for a_id, b_id in candidate_conflicts(list(claims.values())):
        a, b = claims[a_id], claims[b_id]
        if b_id in a.conflicts_with:
            continue
        ok, _ = (judge or judge_claim)(f'These two statements contradict each other: '
                                       f'(1) {a.text} (2) {b.text}', '')
        if not ok:
            continue
        a = a.model_copy(update={'conflicts_with': a.conflicts_with + [b_id]})
        b = b.model_copy(update={'conflicts_with': b.conflicts_with + [a_id]})
        store.append([FactClaim.model_validate(a.model_dump()),
                      FactClaim.model_validate(b.model_dump())])
        claims = store.all()
        linked.append((a_id, b_id))
    return linked


def retrieve(project_id: str, topic: str, k: int = 8) -> List[FactClaim]:
    from story_os.references import list_sources
    live = {s.source_id for s in list_sources(project_id, purpose='factual_research')}
    want = set(re.findall(r'[a-z]{4,}', topic.lower()))
    scored = []
    for c in ClaimStore(project_id).all().values():
        if not any(ci.source_id in live for ci in c.citations):
            continue
        have = set(re.findall(r'[a-z]{4,}', c.text.lower()))
        scored.append((len(want & have), c.claim_id, c))
    return [c for s, _, c in sorted(scored, key=lambda x: (-x[0], x[1])) if s > 0][:k]


def render_claims_block(claims: List[FactClaim]) -> str:
    if not claims:
        return ('NO RESEARCH CLAIMS ARE LOADED: do not state specific facts, figures, '
                'dates or quotations; keep to general knowledge and say so.')
    rows = []
    for c in claims:
        flag = ' (SAY THIS IS UNCERTAIN / DISPUTED)' if c.must_flag_uncertainty else ''
        rows.append(f'- [[{c.claim_id}]] ({c.support}) {c.text}{flag}')
    return ('RESEARCH CLAIMS YOU MAY USE (after any sentence that uses one, keep its '
            'marker like [[CL-0001]] at the end of the line; markers are not spoken):\n'
            + '\n'.join(rows))


def check_script(script: Dict[str, Any], project_id: str) -> List[Dict[str, Any]]:
    """Factual findings: unsupported figures, mismatches, contested as settled."""
    claims = ClaimStore(project_id).all()
    findings = []
    for sc in script.get('scenes') or []:
        for l in sc.get('lines') or []:
            if l.get('type') not in ('dialogue', 'narration'):
                continue
            text = l.get('content') or ''
            refs = [r for r in l.get('claim_refs') or [] if r in claims]
            nums = set(_NUM.findall(text))
            years = {n for n in nums if re.fullmatch(r'1\d{3}|20\d{2}', n)}
            if (nums or re.search(r'\bpercent\b|%', text)) and not refs:
                findings.append({'rule': 'unsupported_claim', 'severity': 'error',
                                 'scene': sc.get('scene_number'), 'line_id': l.get('line_id'),
                                 'message': f'figure/date without a claim: {text[:80]}'})
            for r in refs:
                c = claims[r]
                cn = set(_NUM.findall(c.text))
                if nums and cn and not (nums & cn) and not years:
                    findings.append({'rule': 'figure_mismatch', 'severity': 'error',
                                     'scene': sc.get('scene_number'), 'line_id': l.get('line_id'),
                                     'message': f'{r} says {sorted(cn)}, line says {sorted(nums)}'})
                if c.must_flag_uncertainty and not any(h in text.lower() for h in HEDGES):
                    findings.append({'rule': 'contested_as_settled', 'severity': 'error',
                                     'scene': sc.get('scene_number'), 'line_id': l.get('line_id'),
                                     'message': f'{r} is {c.support} but stated as settled'})
            if re.search(r'["“][^"”]{12,}["”]', text) and not refs:
                findings.append({'rule': 'quotation_not_cited', 'severity': 'error',
                                 'scene': sc.get('scene_number'), 'line_id': l.get('line_id'),
                                 'message': 'quotation without a cited quote claim'})
    return findings


def strip_markers(line: Dict[str, Any]) -> Dict[str, Any]:
    """Move [[CL-xxxx]] markers out of the spoken text into ``claim_refs``."""
    text = line.get('content') or ''
    refs = re.findall(r'\[\[(CL-\d{4})\]\]', text)
    if refs:
        line['content'] = re.sub(r'\s*\[\[CL-\d{4}\]\]', '', text).strip()
        line['claim_refs'] = sorted(set(refs))
    return line
