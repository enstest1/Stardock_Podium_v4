"""Lint, editor pass, bounded revision, candidate premises.

QUALITY-001 (lint + editor + one bounded revision round), QUALITY-004
(audio-first clarity rules) and WRITERS-001 (three premises, Python screen,
pairwise ranking). Rule sets are chosen by the mode's ``editorial``
capability. The editor never writes replacement text itself: it returns
patches (scene + line ids + instruction) and the writer regenerates the
scene from its card with that instruction.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_SCENE_SHARE = 0.30
MAX_PATCHES = 12


def _f(rule, severity, msg, scene=None, line_id=None):
    return {'rule': rule, 'severity': severity, 'message': msg,
            'scene': scene, 'line_id': line_id}


def _spoken(script):
    for sc in script.get('scenes') or []:
        for ln in sc.get('lines') or []:
            if ln.get('type') in ('dialogue', 'narration'):
                yield sc, ln


def lint(script: Dict[str, Any], cast: List[str], *, editorial: str = 'fiction',
         store=None) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    tokens = {t.lower() for c in cast for t in c.replace('.', '').split()}
    spoken_text = ' '.join((ln.get('content') or '') for _, ln in _spoken(script)).lower()
    total_words = len(spoken_text.split()) or 1
    narr_words = sum(len((ln.get('content') or '').split()) for _, ln in _spoken(script)
                     if ln.get('type') == 'narration')
    openings = {}
    dead = set()
    if store is not None:
        for c in store.query('state_changes'):
            if c.get('irreversible') and c['attribute'] == 'condition':
                dead.add(c['entity'].split()[0].lower())
    for sc in script.get('scenes') or []:
        n = sc.get('scene_number')
        lines = sc.get('lines') or []
        speakers = {(l.get('character') or '').strip() for l in lines if l.get('type') == 'dialogue'}
        speakers.discard('')
        if not speakers:
            findings.append(_f('no_dialogue', 'warning', 'scene has no spoken dialogue', n))
        limit = 4 if editorial == 'fiction' else 3
        if len(speakers) > limit:
            findings.append(_f('too_many_speakers', 'warning',
                               f'{len(speakers)} speakers in one scene is hard to follow by ear', n))
        for sp in speakers:
            first = sp.replace('.', '').split()
            if tokens and not any(t.lower() in tokens for t in first):
                findings.append(_f('unknown_speaker', 'error', f'{sp} is not in the cast', n))
            if first and first[0].lower() in dead:
                findings.append(_f('canon_contradiction', 'error',
                                   f'{sp} speaks but canon says they are gone/dead', n))
        spoken_lines = [l for l in lines if l.get('type') in ('dialogue', 'narration')]
        if spoken_lines:
            key = ' '.join((spoken_lines[0].get('content') or '').lower().split()[:4])
            if key and key in openings:
                findings.append(_f('repeated_opening', 'warning',
                                   f'opens like scene {openings[key]}', n))
            openings.setdefault(key, n)
        for l in lines:
            text = (l.get('content') or '')
            lid = l.get('line_id')
            if l.get('type') == 'sound_effect':
                from audio_timeline import speech_in_cue
                if speech_in_cue(text):
                    findings.append(_f('speech_in_cue', 'error',
                                       'spoken words inside a sound cue', n, lid))
            if l.get('type') == 'description' and editorial == 'fiction':
                new = [w for w in re.findall(r'[a-z]{5,}', text.lower()) if w not in spoken_text]
                if len(new) >= 4:
                    findings.append(_f('description_only_information', 'warning',
                                       'description carries information the listener never hears',
                                       n, lid))
            if l.get('type') not in ('dialogue', 'narration'):
                continue
            words = text.split()
            if len(words) > 45:
                findings.append(_f('long_line', 'warning', f'{len(words)} words in one line', n, lid))
            initials = [w[0].lower() for w in re.findall(r'[A-Za-z]+', text)]
            run = 1
            for a, b in zip(initials, initials[1:]):
                run = run + 1 if a == b and a not in 'aeiou' else 1
                if run >= 4:
                    findings.append(_f('tongue_twister', 'warning',
                                       'four words in a row start with the same consonant', n, lid))
                    break
            if re.search(r'\b\d{3,}\b|\b[A-Z]{3,}\b', text):
                findings.append(_f('read_aloud', 'info', 'numerals/abbreviation: check TTS reading', n, lid))
            if editorial != 'fiction' and len(re.findall(r',', text)) >= 4:
                findings.append(_f('long_list', 'warning', 'list of more than four items', n, lid))
        card = sc.get('card') or {}
        turn_words = {w for w in re.findall(r'[a-z]{5,}', (card.get('turn') or '').lower())}
        scene_text = ' '.join((l.get('content') or '') for l in lines).lower()
        if turn_words and len([w for w in turn_words if w in scene_text]) < max(1, len(turn_words) // 4):
            findings.append(_f('turn_off_page', 'warning',
                               "the card's turn is not audible in the scene", n))
    if editorial == 'fiction' and narr_words / total_words > 0.25:
        findings.append(_f('narration_share', 'warning',
                           f'narration is {round(100 * narr_words / total_words)}% of spoken words'))
    return findings


EDITOR_CHECKLIST = {
    'fiction': [
        'Does every scene turn (something is different at the end)?',
        'Does each character sound like themselves and want something?',
        'Is any information the listener needs only described, not heard?',
        'Are there lines that explain what was already clear (on-the-nose)?',
        'Does the ending land the episode question and leave one hook?',
        'Is anything repeated without development?',
    ],
    'factual': [
        'Is any claim unsupported or stated with more certainty than the evidence?',
        'Is a term used before it is defined?',
        'Does the recap match the stated objectives?',
        'Is any person, quote or institution invented?',
    ],
}


def editor_review(script: Dict[str, Any], findings: List[Dict[str, Any]],
                  editorial: str = 'fiction') -> List[Dict[str, Any]]:
    from story_os import llm
    from story_os.projects import _json_from
    body = []
    for sc in script.get('scenes') or []:
        body.append(f"--- SCENE {sc.get('scene_number')}")
        for l in sc.get('lines') or []:
            who = l.get('character') or ('NARRATOR' if l.get('type') == 'narration' else l.get('type', '').upper())
            body.append(f"[{l.get('line_id', '')[:8]}] {who}: {l.get('content', '')}")
    checklist = '\n'.join(f'- {q}' for q in EDITOR_CHECKLIST.get(editorial, EDITOR_CHECKLIST['fiction']))
    lint_txt = '\n'.join(f"- scene {f['scene']}: {f['rule']}: {f['message']}" for f in findings[:20])
    user = (f'SCRIPT:\n' + '\n'.join(body) + f'\n\nAUTOMATIC FINDINGS:\n{lint_txt or "(none)"}\n\n'
            f'CHECKLIST:\n{checklist}\n\nReturn at most {MAX_PATCHES} patches for the most '
            'important problems only. Do NOT write replacement dialogue; give an '
            'instruction. Cite line ids. If the script is good, return no patches.\n'
            'Return JSON: {"patches": [{"scene_number": 2, "line_ids": ["ab12cd34"], '
            '"problem": "...", "instruction": "..."}]}')
    raw = llm.complete('editor', 'You are a script editor for audio drama. You are '
                       'specific and brief. JSON only.', user, json=True,
                       max_tokens=1800, temperature=0.2)
    try:
        patches = _json_from(raw).get('patches') or []
    except Exception:
        patches = []
    return [p for p in patches if isinstance(p, dict) and p.get('instruction')][:MAX_PATCHES]


def plan_revision(script: Dict[str, Any], patches: List[Dict[str, Any]]) -> Dict[str, Any]:
    scenes = [sc.get('scene_number') for sc in script.get('scenes') or []]
    by_scene: Dict[int, List[str]] = {}
    for p in patches:
        n = p.get('scene_number')
        if n in scenes:
            by_scene.setdefault(n, []).append(p['instruction'])
    cap = max(1, int(len(scenes) * MAX_SCENE_SHARE))
    if len(by_scene) > cap:
        return {'status': 'needs_reoutline', 'scenes': sorted(by_scene), 'cap': cap}
    return {'status': 'revise', 'scenes': by_scene, 'cap': cap}


def run_edit_round(episode_id: str) -> Dict[str, Any]:
    """Lint -> editor -> regenerate at most 30% of scenes once -> save."""
    from story_structure import get_story_structure
    from script_line_ids import ensure_script_line_ids
    from story_os import projects
    from story_os.canon_store import CanonStore
    ss = get_story_structure()
    ep = ss.get_episode(episode_id)
    script = ep.get('script') or {}
    project = projects.load_project(ep['project_id'])
    editorial = project.capability('editorial')
    cast = [c.get('name', '') for c in ep.get('characters') or []]
    findings = lint(script, cast, editorial=editorial, store=CanonStore.for_episode(ep))
    patches = editor_review(script, findings, editorial)
    plan = plan_revision(script, patches)
    report = {'findings_before': findings, 'patches': patches, 'plan': plan, 'revised': []}
    try:
        from draft_store import save_script_draft
        save_script_draft(episode_id, script, label='before_edit')
    except Exception as e:
        logger.debug('draft snapshot skipped: %s', e)
    if plan['status'] == 'revise' and plan['scenes']:
        ctx = ss._project_context(ep)
        scenes = ep.get('scenes') or []
        for i, sc_script in enumerate(script['scenes']):
            n = sc_script.get('scene_number')
            if n not in plan['scenes']:
                continue
            scene = next((s for s in scenes if s.get('scene_number') == n), None)
            if scene is None:
                continue
            instr = 'EDITOR NOTES TO FIX IN THIS VERSION:\n- ' + '\n- '.join(plan['scenes'][n])
            new = ss._generate_project_scene_script(
                ep, scene, ctx, extra_preamble=instr,
                previous_scene_script=script['scenes'][i - 1] if i > 0 else None,
                next_scene=scenes[i + 1] if i + 1 < len(scenes) else None)
            if new.get('lines'):
                script['scenes'][i] = new
                report['revised'].append(n)
        ensure_script_line_ids(script)
        ep['script'] = script
        ss._save_episode(ep)
        ss._save_script(episode_id, script)
    report['findings_after'] = lint(script, cast, editorial=editorial,
                                    store=CanonStore.for_episode(ep))
    qdir = ss.episodes_dir / episode_id / 'quality'
    qdir.mkdir(parents=True, exist_ok=True)
    with open(qdir / 'edit_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    return report


# ------------------------------------------------------------ premises ----

def propose_premises(context: str, n: int = 3) -> List[Dict[str, Any]]:
    from story_os import llm
    from story_os.projects import _json_from
    system = 'You are a writers room pitching episode premises. JSON only.'
    user = (f'{context}\n\nPitch {n} different premises for this episode. They must '
            'differ in protagonist, obstacle type and ending type.\nReturn JSON: '
            '{"premises": [{"logline": "...", "protagonist": "Name", "obstacle_type": '
            '"person|nature|society|self|mystery|time", "ending_type": '
            '"win|loss|bittersweet|twist|open"}]}')
    feedback = ''
    for _ in (1, 2):
        try:
            items = _json_from(llm.complete('planner', system, user + feedback, json=True,
                                            max_tokens=1200, temperature=0.9)).get('premises') or []
        except Exception:
            items = []
        items = [p for p in items if isinstance(p, dict) and p.get('logline')]
        problems = premise_problems(items, n)
        if not problems:
            return items
        feedback = '\n\nRejected: ' + '; '.join(problems) + '. Return the JSON again.'
    return items


def premise_problems(items: List[Dict[str, Any]], n: int) -> List[str]:
    out = []
    if len(items) < n:
        out.append(f'need {n} premises')
    for key in ('protagonist', 'obstacle_type', 'ending_type'):
        vals = [str(p.get(key, '')).lower() for p in items]
        if len(set(vals)) < len(vals):
            out.append(f'two premises share the same {key}')
    return out


def screen(items: List[Dict[str, Any]], store=None) -> List[Dict[str, Any]]:
    """Drop premises built on someone canon says is gone/dead."""
    if store is None:
        return items
    gone = {c['entity'].split()[0].lower() for c in store.query('state_changes')
            if c.get('irreversible') and c['attribute'] == 'condition'}
    return [p for p in items if str(p.get('protagonist', '')).split()[0].lower() not in gone] or items[:1]


def choose_premise(context: str, store=None, use_judge: bool = True) -> Optional[Dict[str, Any]]:
    from story_os import judge
    items = screen(propose_premises(context), store)
    if not items:
        return None
    if use_judge and len(items) > 1:
        order = judge.rank([p['logline'] for p in items],
                           'Which premise makes the more gripping, original audio episode?',
                           context[:800])
        best = items[order[0]]
        best['ranking'] = order
        return best
    return items[0]
