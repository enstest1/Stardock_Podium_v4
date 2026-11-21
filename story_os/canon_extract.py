"""Evidence-cited canon extraction with verification (CANON-002, -003, -004).

Pipeline per scene: number the lines (L0001...), ask the extractor role for
events / state changes / beliefs / relationship deltas / promises, each with
``line_ids`` and a verbatim ``quote``; verify every quote in Python against
the cited lines; re-ask once with the rejections; send irreversible changes
(dead / destroyed / gone) and promise pay-offs to a single-claim judge; write
accepted records as ``draft``. ``approve_episode`` promotes them to canon.

Beliefs (CANON-003): characters present in a scene ``know`` its events;
what a character *says* happened is stored as a ``claims`` belief, never as
a fact. Promise closure (CANON-004) is judged only when nominated.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any, Dict, List, Tuple

from story_os.canon_models import (Belief, CanonEvent, Evidence, Promise,
                                   RelationshipDelta, StateChange, Verification)
from story_os.canon_store import CanonStore

logger = logging.getLogger(__name__)

IRREVERSIBLE = re.compile(r'\b(dead|died|killed|destroyed|gone|lost forever|'
                          r'murdered|drowned)\b', re.I)

EXTRACT_SYSTEM = (
    'You are a continuity editor. From one scene of an audio script you '
    'record only what the script actually establishes. Every item cites the '
    'line ids it comes from and copies an exact quote (at least three words) '
    'from one of those lines. Answer with JSON only.')

EXTRACT_RULES = """Rules:
- events: things that HAPPEN on the page (actions, discoveries, decisions, reveals). Not plans, not templates, not themes.
- If a character SAYS something happened, that is a belief with stance "claims" held by the speaker, not an event.
- state_changes: lasting changes to a person, place or object (attribute = condition | location | possession | role | knowledge).
- beliefs: what a named character now knows/believes/suspects/denies. truth: "true" if the scene shows it, "false" if the scene shows it is wrong, else "unknown".
- relationships: a clear shift between two named characters.
- promises: questions or set-ups the story now owes the audience. horizon: scene | episode | season | series.
- Use only names from the cast list. Skip anything you cannot quote.
Return JSON:
{"events":[{"kind":"action","summary":"...","actors":["..."],"line_ids":["L0003"],"quote":"..."}],
 "state_changes":[{"entity":"...","attribute":"condition","before":"","after":"...","line_ids":[],"quote":""}],
 "beliefs":[{"holder":"...","proposition":"...","stance":"claims","truth":"unknown","line_ids":[],"quote":""}],
 "relationships":[{"a":"...","b":"...","dimension":"trust","direction":"down","reason":"...","line_ids":[],"quote":""}],
 "promises":[{"kind":"mystery","statement":"...","horizon":"season","line_ids":[],"quote":""}],
 "pays_off":[{"promise_id":"...","line_ids":[],"quote":""}]}"""


def norm(text: str) -> str:
    t = unicodedata.normalize('NFKC', text or '')
    t = t.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    t = re.sub(r'[^\w\s\']', ' ', t.lower())
    return re.sub(r'\s+', ' ', t).strip()


def number_lines(scene: Dict[str, Any], start: int = 1) -> Tuple[str, Dict[str, Dict[str, Any]]]:
    """Render a scene with short ids. Returns (text, short_id -> line)."""
    out, mapping = [], {}
    n = start
    for line in scene.get('lines') or []:
        content = (line.get('content') or '').strip()
        if not content:
            continue
        sid = f'L{n:04d}'
        n += 1
        mapping[sid] = line
        who = (line.get('character') or line.get('speaker') or
               ('NARRATOR' if line.get('type') == 'narration' else line.get('type', '').upper()))
        out.append(f'{sid} {who}: {content}')
    return '\n'.join(out), mapping


def verify_item(item: Dict[str, Any], mapping: Dict[str, Dict[str, Any]],
                cast: List[str]) -> List[str]:
    """Reasons to reject (empty = accepted)."""
    reasons = []
    ids = item.get('line_ids') or []
    quote = norm(item.get('quote', ''))
    if not ids:
        reasons.append('no line_ids')
    unknown_ids = [i for i in ids if i not in mapping]
    if unknown_ids:
        reasons.append(f'line ids not in this scene: {unknown_ids}')
    if len(quote.split()) < 3:
        reasons.append('quote shorter than three words')
    elif not any(quote in norm(mapping[i].get('content', '')) for i in ids if i in mapping):
        reasons.append('quote not found in the cited lines')
    known = {c.strip().lower() for c in cast} | {'audience'}
    for field in ('holder', 'a', 'b', 'entity'):
        v = item.get(field)
        if v and field != 'entity' and v.strip().lower() not in known:
            reasons.append(f'unknown character {v!r}')
    for name in item.get('actors') or []:
        if name.strip().lower() not in known:
            reasons.append(f'unknown character {name!r}')
    return reasons


def _llm(system: str, user: str, max_tokens: int = 2500) -> str:
    from story_os import llm
    return llm.complete('extractor', system, user, json=True,
                        max_tokens=max_tokens, temperature=0.0)


def _parse(raw: str) -> Dict[str, Any]:
    from story_os.projects import _json_from
    try:
        return _json_from(raw)
    except Exception:
        return {}


def judge_claim(claim: str, lines_text: str) -> Tuple[bool, str]:
    system = ('You check one claim against script lines. Answer JSON only: '
              '{"supported": true|false, "line": "the exact supporting line or empty"}')
    data = _parse(_llm(system, f'CLAIM: {claim}\n\nLINES:\n{lines_text}', 300))
    return bool(data.get('supported')), str(data.get('line', ''))[:200]


SECTIONS = ('events', 'state_changes', 'beliefs', 'relationships', 'promises')


def extract_scene(scene: Dict[str, Any], cast: List[str], open_promises: List[Dict[str, Any]],
                  start: int = 1) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]], Dict[str, Dict], int]:
    text, mapping = number_lines(scene, start)
    prom_block = ''
    if open_promises:
        prom_block = ('\nOPEN PROMISES (list in pays_off only if these lines answer one):\n'
                      + '\n'.join(f"- {p['promise_id']}: {p['statement']}" for p in open_promises))
    user = (f"CAST: {', '.join(cast)}\nSCENE {scene.get('scene_number')}:\n{text}\n"
            f"{prom_block}\n\n{EXTRACT_RULES}")
    accepted: Dict[str, List[Dict[str, Any]]] = {k: [] for k in SECTIONS + ('pays_off',)}
    rejected: List[Dict[str, Any]] = []
    raw = _parse(_llm(EXTRACT_SYSTEM, user))
    for attempt in (1, 2):
        bad = []
        for section in SECTIONS + ('pays_off',):
            for item in raw.get(section) or []:
                if not isinstance(item, dict):
                    continue
                reasons = verify_item(item, mapping, cast)
                if reasons:
                    bad.append({'section': section, 'item': item, 'reasons': reasons})
                else:
                    accepted[section].append(item)
        for b in bad:
            b['attempt'] = attempt
        rejected += bad
        if not bad or attempt == 2:
            break
        fix = '\n'.join(f"- {b['section']}: {json.dumps(b['item'])[:200]} -> {'; '.join(b['reasons'])}"
                        for b in bad[:10])
        raw = _parse(_llm(EXTRACT_SYSTEM, user + '\n\nThese items were rejected; '
                          'return ONLY corrected versions of them (same JSON shape), '
                          'or omit any you cannot quote exactly:\n' + fix))
    return accepted, rejected, mapping, start + len(mapping)


def extract_episode(episode: Dict[str, Any], script: Dict[str, Any],
                    store: CanonStore) -> Dict[str, Any]:
    """Extract, verify and write draft records for one episode."""
    eid = episode['episode_id']
    num = int(episode.get('episode_number') or 0)
    season = int(episode.get('season_number') or 1)
    prefix = f's{season:02d}e{num:02d}'
    cast = [c.get('name', '') for c in episode.get('characters') or []]
    first_names = [c.split()[0] for c in cast if c]
    cast_all = sorted(set(cast + first_names))
    alias = {}
    for full in cast:
        for tok in [full] + full.split():
            alias.setdefault(tok.strip(' .').lower(), full)

    def cname(n):
        return alias.get((n or '').strip(' .').lower(), n)
    report: Dict[str, Any] = {'episode_id': eid, 'scenes': [], 'accepted': {},
                              'rejected': 0, 'judged': []}
    counters = {k: store.next_number(k, f'{k[:2].upper()}-{prefix}') for k in SECTIONS}
    open_prom = store.open_promises(horizons=('episode', 'season', 'series'),
                                    include_draft_episode=eid)
    start = 1
    for scene in script.get('scenes') or []:
        acc, rej, mapping, start = extract_scene(scene, cast_all, open_prom, start)
        present = sorted({cname((l.get('character') or '').strip()) for l in mapping.values()
                          if l.get('type') == 'dialogue'} - {''})
        for section in acc.values():
            for item in section:
                for f in ('holder', 'a', 'b', 'entity'):
                    if item.get(f):
                        item[f] = cname(item[f])
                if item.get('actors'):
                    item['actors'] = [cname(a) for a in item['actors']]
        lines_text = '\n'.join(f"{k} {v.get('content', '')}" for k, v in mapping.items())

        def ev(item):
            ids = [mapping[i].get('line_id') or i for i in item['line_ids']]
            return Evidence(episode_id=eid, line_ids=ids, quote=item['quote'])

        def nid(kind):
            n = counters[kind]
            counters[kind] += 1
            return f'{kind[:2].upper()}-{prefix}-{n:03d}'
        base = dict(episode_id=eid, episode_number=num,
                    scene_number=int(scene.get('scene_number') or 0))
        events = [CanonEvent(event_id=nid('events'), kind=i.get('kind', 'action')
                             if i.get('kind') in CanonEvent.model_fields['kind'].annotation.__args__ else 'action',
                             summary=i.get('summary', ''), actors=i.get('actors') or [],
                             witnesses=present, evidence=ev(i),
                             verification=Verification(quote_ok=True), **base)
                  for i in acc['events'] if i.get('summary')]
        changes = []
        for i in acc['state_changes']:
            irreversible = bool(IRREVERSIBLE.search(i.get('after', '')))
            ver = Verification(quote_ok=True)
            if irreversible:
                ok, why = judge_claim(f"{i.get('entity')} is now {i.get('after')}", lines_text)
                ver.judged, ver.judge_reason = ok, why
                report['judged'].append({'claim': f"{i.get('entity')}: {i.get('after')}", 'ok': ok})
                if not ok:
                    continue
            changes.append(StateChange(change_id=nid('state_changes'),
                                       entity=i.get('entity', ''), attribute=i.get('attribute', 'condition'),
                                       before=i.get('before', ''), after=i.get('after', ''),
                                       irreversible=irreversible, evidence=ev(i),
                                       verification=ver, **base))
        beliefs = []
        for i in acc['beliefs']:
            stance = i.get('stance') if i.get('stance') in ('knows', 'believes', 'suspects', 'denies', 'claims') else 'believes'
            truth = i.get('truth') if i.get('truth') in ('true', 'false', 'unknown') else 'unknown'
            beliefs.append(Belief(belief_id=nid('beliefs'), holder=i.get('holder', ''),
                                  proposition=i.get('proposition', ''), stance=stance,
                                  truth=truth, evidence=ev(i),
                                  verification=Verification(quote_ok=True), **base))
        # witnesses know what happened in front of them (CANON-003)
        for e in events:
            for w in e.witnesses:
                beliefs.append(Belief(belief_id=nid('beliefs'), holder=w,
                                      proposition=e.summary, stance='knows', truth='true',
                                      about_event_id=e.event_id, evidence=e.evidence,
                                      verification=Verification(quote_ok=True), **base))
        rels = [RelationshipDelta(delta_id=nid('relationships'), a=i.get('a', ''), b=i.get('b', ''),
                                  dimension=i.get('dimension') if i.get('dimension') in
                                  ('trust', 'affection', 'respect', 'fear', 'rivalry', 'obligation') else 'trust',
                                  direction='up' if i.get('direction') == 'up' else 'down',
                                  reason=i.get('reason', ''), evidence=ev(i),
                                  verification=Verification(quote_ok=True), **base)
                for i in acc['relationships'] if i.get('a') and i.get('b')]
        proms = [Promise(promise_id=nid('promises'),
                         kind=i.get('kind') if i.get('kind') in ('question', 'mystery', 'setup', 'threat', 'vow', 'secret', 'goal') else 'question',
                         statement=i.get('statement', ''),
                         horizon=i.get('horizon') if i.get('horizon') in ('scene', 'episode', 'season', 'series') else 'episode',
                         planted_in=eid, evidence=ev(i),
                         verification=Verification(quote_ok=True), **base)
                 for i in acc['promises'] if i.get('statement')]
        paid = []
        known_open = {p['promise_id']: p for p in open_prom}
        for i in acc['pays_off']:
            p = known_open.get(i.get('promise_id'))
            if not p:
                continue
            ok, why = judge_claim(f"These lines answer: {p['statement']}", lines_text)
            report['judged'].append({'claim': f"pays {p['promise_id']}", 'ok': ok})
            if ok:
                upd = dict(p, state='paid', paid_by=eid, status='draft',
                           evidence=ev(i).model_dump(), episode_id=eid)
                paid.append(Promise.model_validate(upd))
        for kind, recs in (('events', events), ('state_changes', changes), ('beliefs', beliefs),
                           ('relationships', rels), ('promises', proms + paid)):
            if recs:
                store.append(kind, recs)
            report['accepted'][kind] = report['accepted'].get(kind, 0) + len(recs)
        report['rejected'] += len(rej)
        report['scenes'].append({'scene': scene.get('scene_number'), 'accepted': {
            k: len(v) for k, v in acc.items()}, 'rejected': [
            {'section': r['section'], 'reasons': r['reasons']} for r in rej]})
    store.rebuild_index()
    return report


def approve_episode(store: CanonStore, episode_id: str) -> None:
    store.set_status(episode_id, 'canon')
    store.rebuild_index()


def omniscience_check(script: Dict[str, Any], store: CanonStore,
                      episode_id: str) -> List[Dict[str, Any]]:
    """Flag lines where a speaker states a canon fact they cannot know (CANON-003).

    Deterministic part: a speaker asserting the distinctive words of an event
    they neither witnessed nor were told about. Words that occur in more than
    5 % of events (names, places, recurring props) don't count as distinctive.
    The ledger is read once per call. The LLM check of the spec is left for
    when the fixture oracle exists.
    """
    from collections import Counter
    events = store.query('events')
    if not events:
        return []
    words = [{w for w in norm(e['summary']).split() if len(w) > 4} for e in events]
    df = Counter(w for ws in words for w in ws)
    cap = max(2, int(0.05 * len(events)))
    keys = [{w for w in ws if df[w] <= cap} for ws in words]
    known: Dict[str, set] = {}
    for b in store.query('beliefs'):
        if b.get('about_event_id'):
            known.setdefault(b['holder'].strip().lower(), set()).add(b['about_event_id'])
    present = [{a.lower() for a in e['actors']} | {w.lower() for w in e.get('witnesses', [])}
               for e in events]
    issues = []
    for scene in script.get('scenes') or []:
        for line in scene.get('lines') or []:
            who = (line.get('character') or '').strip()
            if not who:
                continue
            wl = who.lower()
            said = set(norm(line.get('content', '')).split())
            kn = known.get(wl, set())
            for e, key, pres in zip(events, keys, present):
                if len(key) >= 3 and len(key & said) >= max(3, int(0.7 * len(key)))                         and e['event_id'] not in kn and wl not in pres:
                    issues.append({'line_id': line.get('line_id'), 'speaker': who,
                                   'event_id': e['event_id'], 'severity': 'error'})
    return issues
