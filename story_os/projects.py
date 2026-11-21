"""Projects: one sentence -> a self-contained podcast project (GEN-001).

Owns ``data/projects/<project_id>/``:

- ``project.json``  ProjectConfig (mode, genre, minutes, ...)
- ``format.json``   FormatProfile (prompt wording, intro/outro templates)
- ``bible.json``    identity: logline, tone, world note, cast with voice notes
- ``voices.json``   voice config in the ``voices/voice_config.json`` shape,
                    Kokoro built-in voices only (publishable; no clones)

A project never reads the global series bible, the book RAG index or the
global voice config. Code asks ``capability(project_id, key)``; it does not
compare mode names.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from story_os.profile import FormatProfile, default_format
from story_os.project_models import FICTION_MODES, MODE_CAPABILITIES, ProjectConfig

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# Kokoro v1 built-in voices, best-rated first within each pool.
KOKORO_POOLS: Dict[str, List[str]] = {
    'female_american': ['af_heart', 'af_bella', 'af_nicole', 'af_sarah',
                        'af_nova', 'af_sky', 'af_river', 'af_jessica',
                        'af_kore', 'af_aoede', 'af_alloy'],
    'male_american': ['am_michael', 'am_fenrir', 'am_puck', 'am_adam',
                      'am_liam', 'am_onyx', 'am_echo', 'am_eric'],
    'female_british': ['bf_emma', 'bf_isabella', 'bf_alice', 'bf_lily'],
    'male_british': ['bm_george', 'bm_fable', 'bm_lewis', 'bm_daniel'],
}
EXTRA_SPEAKER_KEY = 'extra'

_KEYWORD_MODES = [
    (('interview', 'talk show', 'conversation', 'chat about', 'debate'),
     'conversational'),
    (('lesson', 'explain', 'explainer', 'learn', 'teach', 'how to',
      'for students', 'for beginners'), 'educational'),
    (('history of', 'documentary', 'true story', 'investigat'),
     'documentary'),
    (('anthology', 'tales', 'stories told', 'each episode a'), 'anthology'),
    (('season', 'serial', 'saga', 'ongoing'), 'serialized_fiction'),
]


def _data_dir() -> Path:
    from config.paths import DATA_DIR
    return Path(DATA_DIR)


def projects_dir() -> Path:
    return _data_dir() / 'projects'


def project_dir(project_id: str) -> Path:
    return projects_dir() / project_id


def slugify(text: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '_', (text or '').lower()).strip('_')
    return s[:48] or 'podcast'


def atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _json_from(raw: str) -> Dict[str, Any]:
    text = (raw or '').strip()
    m = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
    if m:
        text = m.group(1)
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end <= start:
        raise ValueError('no JSON object in response')
    return json.loads(text[start:end + 1])


# ------------------------------------------------------------ proposal ----

class _Proposal(BaseModel):
    title: str
    mode: str
    mode_rationale: str = ''
    genre: str = ''
    audience: str = ''
    episode_minutes: int = 30


def keyword_mode(idea: str) -> str:
    low = (idea or '').lower()
    for words, mode in _KEYWORD_MODES:
        if any(w in low for w in words):
            return mode
    return 'standalone_drama'


def _complete(role: str, system: str, user: str, max_tokens: int) -> str:
    from story_os import llm
    return llm.complete(role, system, user, json=True, max_tokens=max_tokens,
                        temperature=0.8)


def propose_project(idea: str, *, mode: Optional[str] = None,
                    title: Optional[str] = None,
                    minutes: Optional[int] = None) -> ProjectConfig:
    """One planner call proposing title, mode and genre; keyword fallback."""
    modes = ', '.join(MODE_CAPABILITIES)
    system = ('You are the development executive of an audio studio. You turn '
              'a one-sentence idea into an original podcast proposal. '
              'Answer with JSON only.')
    user = (f'IDEA: {idea}\n\n'
            f'Choose the production mode from: {modes}.\n'
            'Return JSON: {"title": "short original show title", "mode": "...", '
            '"mode_rationale": "one sentence", "genre": "two or three words", '
            '"audience": "who it is for", "episode_minutes": 30}\n'
            'The title and everything else must be original: no existing '
            'franchise, character or brand names.')
    proposal: Optional[_Proposal] = None
    source_note = ''
    feedback = ''
    for attempt in (1, 2):
        try:
            data = _json_from(_complete('planner', system, user + feedback, 400))
            proposal = _Proposal.model_validate(data)
            if proposal.mode not in MODE_CAPABILITIES:
                raise ValueError(f'unknown mode {proposal.mode!r}')
            break
        except (ValueError, ValidationError, json.JSONDecodeError) as e:
            proposal = None
            feedback = f'\n\nYour previous answer was invalid ({e}). Return valid JSON.'
        except Exception as e:  # no key / network
            logger.warning('Project proposal call failed: %s', e)
            break
    if proposal is None:
        proposal = _Proposal(title=(idea or 'Untitled')[:60].rstrip(' .'),
                             mode=keyword_mode(idea),
                             mode_rationale='keyword fallback')
        source_note = 'keyword fallback'
        logger.warning('Using keyword fallback for project proposal.')

    final_title = (title or proposal.title).strip()
    pid = slugify(final_title)
    return ProjectConfig(
        project_id=pid, show_id=pid, title=final_title, idea=idea,
        mode=mode or proposal.mode,
        mode_source='user' if mode else 'proposed',
        mode_rationale=proposal.mode_rationale or source_note,
        genre=proposal.genre, audience=proposal.audience,
        episode_minutes=int(minutes or proposal.episode_minutes or 30),
        original=True, publishable=True, schema_version=SCHEMA_VERSION)


# ------------------------------------------------------------ identity ----

class CastMember(BaseModel):
    name: str
    role: str = ''
    personality: str = ''
    backstory: str = ''
    voice_description: str = ''
    gender: str = 'female'
    accent: str = 'american'
    kokoro_voice: str = ''
    want: str = ''
    need: str = ''
    wound: str = ''
    false_belief: str = ''
    speech_rhythm: str = ''
    never_says: List[str] = Field(default_factory=list)
    verbal_tics: List[str] = Field(default_factory=list)


class Identity(BaseModel):
    logline: str = ''
    tone: str = ''
    world: str = ''
    dialogue_rules: List[str] = Field(default_factory=list)
    narrator_gender: str = 'male'
    narrator_accent: str = 'british'
    narrator_voice_description: str = ''
    tagline: str = ''
    intro_template: str = ''
    outro_template: str = ''
    theme_prompt: str = ''
    cast: List[CastMember] = Field(min_length=1)


def design_identity(project: ProjectConfig) -> Identity:
    """One planner call: logline, tone, world note and an original cast."""
    caps = project.capability
    cast_style = caps('cast')
    size = '2 to 4' if project.episode_minutes <= 10 else '3 to 6'
    if cast_style == 'hosts':
        size = '1 to 3 host personas (fictional, disclosed as AI personas, never real people) as the'
    system = ('You are a show creator and casting director for audio fiction. '
              'Everything you invent is original. Answer with JSON only.')
    user = (f'SHOW: {project.title}\nIDEA: {project.idea}\n'
            f'GENRE: {project.genre}\nMODE: {project.mode} (cast style: {cast_style})\n'
            f'EPISODE LENGTH: {project.episode_minutes} minutes\n\n'
            f'Design the show identity and {size} speaking characters. Audio '
            'only: give each character a voice that is easy to tell apart by '
            'ear (mix genders and accents). Names must be easy to say aloud '
            'and must not resemble famous characters.\n'
            'Return JSON: {"logline": "...", "tone": "...", '
            '"world": "two sentences about the setting", '
            '"dialogue_rules": ["three short rules for how people talk"], '
            '"narrator_gender": "male|female", "narrator_accent": '
            '"american|british", "narrator_voice_description": "...", '
            '"tagline": "one short spoken hook line for the show", '
            '"intro_template": "the spoken show opening, 1-3 short sentences, '
            'using the placeholders {show_name}, {episode} and {title}", '
            '"outro_template": "the spoken sign-off, 1-2 short sentences, '
            'may use {show_name}", '
            '"theme_prompt": "an instrumental theme-music brief: genre, '
            'instruments, tempo, mood; no artist names", "cast": [{"name": "...", "role": "...", '
            '"personality": "...", "backstory": "...", '
            '"voice_description": "pitch, pace, texture", '
            '"gender": "male|female", "accent": "american|british", '
            '"want": "what they chase", "need": "what they actually need", '
            '"wound": "the old hurt", "false_belief": "the lie they believe", '
            '"speech_rhythm": "how they talk", "never_says": ["a phrase they would never use"], '
            '"verbal_tics": ["a habit of speech"]}]}')
    feedback = ''
    last_err: Optional[Exception] = None
    for _ in (1, 2):
        try:
            return Identity.model_validate(
                _json_from(_complete('planner', system, user + feedback, 1800)))
        except (ValueError, ValidationError, json.JSONDecodeError) as e:
            last_err = e
            feedback = f'\n\nYour previous answer was invalid ({e}). Return valid JSON.'
    raise RuntimeError(f'Identity design failed twice: {last_err}')


def _canon(name: str) -> str:
    from dialogue_engine import _canonicalize_name
    return _canonicalize_name(name)


def _pool_key(gender: str, accent: str) -> str:
    g = 'male' if (gender or '').lower().startswith('m') else 'female'
    a = 'british' if (accent or '').lower().startswith('b') else 'american'
    return f'{g}_{a}'


def assign_voices(identity: Identity) -> Dict[str, Any]:
    """Distinct Kokoro voice per speaker, plus narrator and an extras voice."""
    used: set = set()

    def take(gender: str, accent: str) -> str:
        primary = KOKORO_POOLS[_pool_key(gender, accent)]
        same_gender = [v for k, pool in KOKORO_POOLS.items()
                       if k.startswith(_pool_key(gender, accent).split('_')[0])
                       for v in pool]
        for v in primary + same_gender + [v for p in KOKORO_POOLS.values() for v in p]:
            if v not in used:
                used.add(v)
                return v
        return primary[0]

    characters: Dict[str, Any] = {}
    aliases: Dict[str, str] = {}
    narrator_voice = take(identity.narrator_gender, identity.narrator_accent)
    characters['narrator'] = {'kokoro_voice': narrator_voice,
                              'display_name': 'Narrator', 'tts_engine': 'kokoro'}
    for member in identity.cast:
        key = _canon(member.name)
        voice = member.kokoro_voice or take(member.gender, member.accent)
        member.kokoro_voice = voice
        characters[key] = {'kokoro_voice': voice, 'display_name': member.name,
                           'tts_engine': 'kokoro',
                           'voice_description': member.voice_description}
        tokens = [t for t in key.split('_') if t]
        honorifics = {'dr', 'mr', 'mrs', 'ms', 'miss', 'sir', 'lady', 'lord',
                      'captain', 'capt', 'professor', 'prof', 'father', 'sister',
                      'brother', 'mother', 'aunt', 'uncle', 'old', 'the'}
        core = [t for t in tokens if t not in honorifics] or tokens
        names = {core[0], core[-1], '_'.join(core)}
        names |= {f'{h}_{core[-1]}' for h in ('mr', 'mrs', 'ms', 'miss', 'dr')}
        for alias in names:
            if alias and alias != key and alias not in characters:
                aliases.setdefault(alias, key)
    characters[EXTRA_SPEAKER_KEY] = {
        'kokoro_voice': take('female' if identity.narrator_gender.startswith('m')
                             else 'male', 'american'),
        'display_name': 'Extra', 'tts_engine': 'kokoro',
        'notes': 'Used for any speaker the script adds who is not in the cast.'}
    return {'engine_order': ['kokoro'], 'characters': characters,
            'aliases': aliases, 'publishable': True,
            '_notes': ['Project voices (GEN-001): Kokoro built-ins only.']}


def cast_voices(project_id: str, identity: Identity,
                use_llm: bool = True) -> Dict[str, Any]:
    """Cast every speaker from the voice catalog (presets or new designs)."""
    import voice_catalog as vcat
    speakers = [{'key': 'narrator', 'name': 'Narrator',
                 'gender': 'male' if identity.narrator_gender.lower().startswith('m') else 'female',
                 'accent': identity.narrator_accent,
                 'voice_description': identity.narrator_voice_description or 'show narrator',
                 'lead': True}]
    for i, m in enumerate(identity.cast):
        speakers.append({'key': _canon(m.name), 'name': m.name,
                         'gender': 'male' if m.gender.lower().startswith('m') else 'female',
                         'accent': m.accent, 'voice_description': m.voice_description,
                         'lead': i == 0})
    speakers.append({'key': EXTRA_SPEAKER_KEY, 'name': 'Extra',
                     'gender': 'female' if speakers[0]['gender'] == 'male' else 'male',
                     'accent': 'american', 'voice_description': 'incidental voices'})
    picks = vcat.cast_show(project_id, speakers, use_llm=use_llm)
    cat = vcat.load_catalog()
    voices = assign_voices(identity)          # aliases + record shape
    for key, vid in picks.items():
        entry = cat['voices'][vid]
        voices['characters'][key]['kokoro_voice'] = entry['kokoro_voice']
        voices['characters'][key]['voice_id'] = vid
    for m in identity.cast:
        m.kokoro_voice = voices['characters'][_canon(m.name)]['kokoro_voice']
    voices['_notes'] = ['Cast from voices/catalog.json (AUDIO-006): Kokoro '
                        'presets and designed blends only.']
    return voices


# ---------------------------------------------------- create / load ----

def format_from_identity(config: ProjectConfig,
                         identity: Identity) -> FormatProfile:
    """Default format plus the show's own spoken intro/outro and theme brief."""
    fmt = default_format(config.genre, config.mode)
    if identity.intro_template.strip():
        intro = identity.intro_template.strip()
        if '{title}' not in intro:
            intro += ' Episode {episode}: {title}.'
        fmt.intro_template = intro
    if identity.outro_template.strip():
        fmt.outro_template = identity.outro_template.strip()
    fmt.tagline = identity.tagline.strip()
    if 'ai' not in fmt.outro_template.lower().replace('.', ' ').split():
        fmt.outro_template = (fmt.outro_template.rstrip() +
                              ' This episode was made with AI-generated writing and voices.')
    if config.capability('claims'):
        fmt.intro_template = (fmt.intro_template.rstrip() + ' This show uses AI-generated '
                              'voices; the hosts are fictional personas.')
    fmt.theme_prompt = identity.theme_prompt.strip()
    return fmt


def create_project(config: ProjectConfig, identity: Identity,
                   fmt: Optional[FormatProfile] = None,
                   overwrite: bool = False,
                   casting: str = 'catalog') -> Path:
    d = project_dir(config.project_id)
    if (d / 'project.json').exists() and not overwrite:
        raise FileExistsError(f'Project already exists: {d}')
    fmt = fmt or format_from_identity(config, identity)
    voices = (cast_voices(config.project_id, identity) if casting == 'catalog'
              else assign_voices(identity))
    atomic_write_json(d / 'project.json', config.model_dump())
    atomic_write_json(d / 'format.json', fmt.model_dump())
    atomic_write_json(d / 'bible.json', identity.model_dump())
    atomic_write_json(d / 'voices.json', voices)
    try:
        from story_os.characters import name_clashes, profiles_from_identity
        profiles_from_identity(config.project_id, identity)
        clashes = name_clashes([m.name for m in identity.cast])
        if clashes:
            logger.warning('Cast names that may sound alike: %s', clashes)
            atomic_write_json(d / 'name_warnings.json', clashes)
    except Exception as e:
        logger.warning('Character profiles not created: %s', e)
    logger.info('Created project %s at %s', config.project_id, d)
    return d


def list_projects() -> List[ProjectConfig]:
    out = []
    if projects_dir().exists():
        for p in sorted(projects_dir().glob('*/project.json')):
            try:
                out.append(ProjectConfig.model_validate(_read_json(p)))
            except Exception as e:
                logger.warning('Skipping unreadable project %s: %s', p, e)
    return out


def load_project(project_id: str) -> ProjectConfig:
    return ProjectConfig.model_validate(
        _read_json(project_dir(project_id) / 'project.json'))


def load_format(project_id: str) -> FormatProfile:
    p = project_dir(project_id) / 'format.json'
    return FormatProfile.model_validate(_read_json(p)) if p.exists() else FormatProfile()


def load_identity(project_id: str) -> Identity:
    return Identity.model_validate(_read_json(project_dir(project_id) / 'bible.json'))


def voices_path(project_id: str) -> Path:
    return project_dir(project_id) / 'voices.json'


def capability(project_id: str, key: str):
    return load_project(project_id).capability(key)


def is_fiction(project: ProjectConfig) -> bool:
    """True when the mode's outline is scene cards (fiction pipeline)."""
    return project.capability('outline') == 'scene_cards'


def cast_as_characters(identity: Identity) -> List[Dict[str, Any]]:
    """Identity cast -> ``episode['characters']`` records."""
    out = []
    for m in identity.cast:
        out.append({'name': m.name, 'role': m.role,
                    'personality': m.personality, 'backstory': m.backstory,
                    'voice_description': m.voice_description,
                    'character_id': f'char_{_canon(m.name)}',
                    'cast_type': 'permanent'})
    return out


def format_brief(project: ProjectConfig, fmt: FormatProfile,
                 identity: Optional[Identity]) -> str:
    """Short description of the show used in planning prompts."""
    parts = [f'{project.title} is {fmt.genre_phrase}.']
    if identity is not None:
        if identity.logline:
            parts.append(f'Logline: {identity.logline}')
        if identity.tone:
            parts.append(f'Tone: {identity.tone}')
        if identity.world:
            parts.append(f'World: {identity.world}')
    return ' '.join(parts)


__all__ = ['FICTION_MODES', 'propose_project', 'design_identity',
           'assign_voices', 'create_project', 'load_project', 'load_format',
           'load_identity', 'list_projects', 'voices_path', 'capability',
           'is_fiction', 'cast_as_characters', 'format_brief', 'keyword_mode',
           'EXTRA_SPEAKER_KEY']
