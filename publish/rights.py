"""Rights gate (PUB-003): nothing goes live unless every item is cleared or
explicitly waived by name and date.

Waivers: ``data/projects/<id>/waivers.json`` =
``[{"item": "<exact blocking text>", "by": "name", "date": "YYYY-MM-DD", "reason": "..."}]``.
Deny-list for franchise / brand terms: ``data/publish_denylist.json``
(``{"terms": [...]}``; configurable, data not code).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class NotPublishable(RuntimeError):
    pass


def _denylist() -> List[str]:
    from config.paths import DATA_DIR
    p = Path(DATA_DIR) / 'publish_denylist.json'
    return json.loads(p.read_text(encoding='utf-8')).get('terms', []) if p.exists() else []


def build_rights_report(episode_id: str) -> Dict[str, Any]:
    from story_structure import get_episode
    from story_os import projects
    from config.paths import EPISODES_DIR
    ep = get_episode(episode_id) or {}
    pid = ep.get('project_id')
    blocking: List[str] = []
    info: Dict[str, Any] = {'episode_id': episode_id, 'project_id': pid}
    if not pid:
        blocking.append('legacy episode (no project): not publishable')
        return {**info, 'blocking': blocking, 'publishable': False}
    project = projects.load_project(pid)
    fmt = projects.load_format(pid)
    info['original'] = project.original
    if not project.original:
        blocking.append('project is not original (legacy / derivative show)')
    # voices / engines
    voices = json.loads(projects.voices_path(pid).read_text(encoding='utf-8'))
    engines = set(voices.get('engine_order') or [])
    for key, v in (voices.get('characters') or {}).items():
        if v.get('speaker_wav') or v.get('tts_engine') == 'xtts':
            engines.add('xtts')
    info['engines'] = sorted(engines)
    if 'xtts' in engines:
        blocking.append('XTTS voice cloning (Coqui CPML, non-commercial) is in use')
    # audio assets and theme
    rep_p = Path(EPISODES_DIR) / episode_id / 'audio' / 'audio_report.json'
    audio = json.loads(rep_p.read_text(encoding='utf-8')) if rep_p.exists() else {}
    for desc in audio.get('assets_not_cleared_for_commercial_use') or []:
        blocking.append(f'sound asset not cleared for commercial use: {desc}')
    tr = fmt.theme_rights or {}
    if tr and tr.get('commercial_ok') != 'yes':
        blocking.append(f"theme music not cleared ({tr.get('provider')}, {tr.get('plan_tier', '')})")
    if not fmt.theme_intro_path:
        info['theme'] = 'studio default theme (bundled asset; check its licence)'
        blocking.append('bundled studio theme music: licence unknown')
    if audio.get('blocking'):
        blocking += [f'audio QA: {b}' for b in audio['blocking']]
    # references (snapshot)
    snap_p = Path(EPISODES_DIR) / episode_id / 'reference_snapshot.json'
    if snap_p.exists():
        snap = json.loads(snap_p.read_text(encoding='utf-8'))
        info['references'] = [{'source_id': s['source_id'], 'purposes': s['purposes'],
                               'rights': s['rights']['status']} for s in snap.get('sources', [])]
        for s in snap.get('sources', []):
            if set(s['purposes']) & {'world_building', 'adaptation'} and \
                    s['rights']['status'] not in ('owned', 'licensed', 'public_domain'):
                blocking.append(f"reference {s['source_id']} used for world/adaptation without rights")
            if 'adaptation' in s['purposes'] and not s['rights'].get('attribution_text'):
                blocking.append(f"adaptation {s['source_id']} has no attribution text")
    # claims
    if project.capability('claims'):
        from story_os.claims import ClaimStore
        claims = ClaimStore(pid).all()
        used = {r for sc in (ep.get('script') or {}).get('scenes', [])
                for l in sc.get('lines') or [] for r in l.get('claim_refs') or []}
        for cid in sorted(used):
            c = claims.get(cid)
            if c and c.support == 'unsupported' and 'human' not in c.verified_by:
                blocking.append(f'unsupported claim {cid} not signed off by a human')
    # disclosure + deny-list
    disclosure = ' '.join([fmt.intro_template, fmt.outro_template]).lower()
    info['ai_disclosure'] = 'ai' in re.findall(r'[a-z]+', disclosure)
    if not info['ai_disclosure']:
        blocking.append('no AI disclosure in the intro/outro; add one to format.json')
    text = ' '.join([ep.get('title', ''), ep.get('theme', '')] + [
        l.get('content', '') for sc in (ep.get('script') or {}).get('scenes', [])
        for l in sc.get('lines') or []]).lower()
    for term in _denylist():
        if re.search(rf'\b{re.escape(term.lower())}\b', text):
            blocking.append(f'deny-listed term in title/script: {term!r}')
    return {**info, 'blocking': blocking, 'publishable': not blocking}


def load_waivers(project_id: str) -> List[Dict[str, Any]]:
    from story_os.projects import project_dir
    p = project_dir(project_id) / 'waivers.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []


def assert_publishable(report: Dict[str, Any],
                       waivers: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Raise unless every blocking item is waived (name + date). Returns waivers used."""
    waivers = waivers or []
    used, left = [], []
    for item in report['blocking']:
        w = next((w for w in waivers if w.get('item') == item and w.get('by') and w.get('date')), None)
        (used if w else left).append(w or item)
    if left:
        raise NotPublishable('Blocked:\n- ' + '\n- '.join(left))
    return used
