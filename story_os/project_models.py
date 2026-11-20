"""Project and reference schemas (GEN-001; copied from the handoff's
reference/reference_models.py, executed there with pydantic 2.13.5).

Universal-studio schemas: production modes,
project config, reference sources, style profiles, influence blending,
factual claims and segment cards.

STATUS: PROPOSED reference code. Executed on 2026-11-11 with pydantic 2.13.5
(``python reference/reference_models.py`` prints OK). Cursor copies these into
``story_os/project_models.py`` (GEN-001) and ``story_os/references.py``
(REF-001/002/003).
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, model_validator

# ------------------------------------------------------- production modes ----

ProductionMode = Literal[
    'serialized_fiction', 'episodic_fiction', 'anthology',
    'standalone_drama', 'documentary', 'educational', 'conversational']

FICTION_MODES = ('serialized_fiction', 'episodic_fiction', 'anthology',
                 'standalone_drama')

# What each mode switches on. Code reads this table; it never tests the
# mode name directly, so a custom mode is just another row.
MODE_CAPABILITIES: Dict[str, Dict[str, object]] = {
    'serialized_fiction': dict(
        season_plan='arc', continuity='canon_full', beliefs=True,
        promises_horizon='series', cast='ensemble', outline='scene_cards',
        frameworks='fiction', editorial='fiction', claims=False,
        feed_type='serial'),
    'episodic_fiction': dict(
        season_plan='slate', continuity='canon_light', beliefs=True,
        promises_horizon='episode', cast='recurring', outline='scene_cards',
        frameworks='fiction', editorial='fiction', claims=False,
        feed_type='episodic'),
    'anthology': dict(
        season_plan='slate', continuity='per_episode', beliefs=True,
        promises_horizon='episode', cast='per_episode',
        outline='scene_cards', frameworks='fiction', editorial='fiction',
        claims=False, feed_type='episodic'),
    'standalone_drama': dict(
        season_plan='none', continuity='per_story', beliefs=True,
        promises_horizon='episode', cast='per_story', outline='scene_cards',
        frameworks='fiction', editorial='fiction', claims=False,
        feed_type='serial'),
    'documentary': dict(
        season_plan='slate', continuity='claims', beliefs=False,
        promises_horizon='none', cast='hosts', outline='segment_cards',
        frameworks='nonfiction', editorial='factual', claims=True,
        feed_type='episodic'),
    'educational': dict(
        season_plan='curriculum', continuity='claims', beliefs=False,
        promises_horizon='none', cast='hosts', outline='segment_cards',
        frameworks='educational', editorial='factual', claims=True,
        feed_type='serial'),
    'conversational': dict(
        season_plan='slate', continuity='claims', beliefs=False,
        promises_horizon='none', cast='hosts', outline='segment_cards',
        frameworks='conversational', editorial='factual', claims=True,
        feed_type='episodic'),
}


class ProjectConfig(BaseModel):
    """One podcast project. Everything else is scoped by ``project_id``."""
    project_id: str
    show_id: str
    title: str
    idea: str                                 # the user's one sentence
    mode: ProductionMode
    mode_source: Literal['proposed', 'user'] = 'proposed'
    mode_rationale: str = ''
    genre: str = ''                           # free text: 'gothic horror'
    audience: str = ''
    language: str = 'en'
    episode_minutes: int = 30
    original: bool = True
    publishable: bool = True
    shared_reference_projects: List[str] = Field(default_factory=list)
    schema_version: int = 1

    def capability(self, key: str):
        return MODE_CAPABILITIES[self.mode][key]


# ----------------------------------------------------------- references ----

ReferencePurpose = Literal[
    'writing_techniques',     # mode 1: how it is written
    'factual_research',       # mode 2: evidence with citations
    'world_building',         # mode 3: authorised setting / lore
    'adaptation',             # mode 4: authorised direct adaptation
]
RightsStatus = Literal['owned', 'licensed', 'public_domain',
                       'fair_reference', 'unspecified']
NEEDS_RIGHTS = {'world_building': ('owned', 'licensed', 'public_domain'),
                'adaptation': ('owned', 'licensed', 'public_domain')}


class Rights(BaseModel):
    status: RightsStatus = 'unspecified'
    holder: str = ''
    evidence: str = ''            # path / URL / statement by the user
    attribution_text: str = ''
    recorded_at: float = 0.0


class Scope(BaseModel):
    project_id: str
    show_id: Optional[str] = None
    episode_id: Optional[str] = None

    def specificity(self) -> int:
        return 2 if self.episode_id else 1 if self.show_id else 0


class ReferenceSource(BaseModel):
    source_id: str                # 'SRC-<first 12 of sha256>'
    project_id: str
    show_id: Optional[str] = None
    source_format: Literal['epub', 'pdf', 'docx', 'txt', 'md', 'html',
                           'script', 'notes', 'url']
    title: str
    author: str = ''
    purposes: List[ReferencePurpose] = Field(min_length=1)
    rights: Rights = Field(default_factory=Rights)
    ingested_at: float
    content_sha256: str
    extraction_model: str = ''
    extraction_version: str = ''
    style_profile_version: Optional[int] = None
    knowledge_classes: List[Literal['style', 'facts', 'world', 'story']] = \
        Field(default_factory=list)
    enabled: bool = True
    removed_at: Optional[float] = None      # excluded from future generation
    purged_at: Optional[float] = None       # extracted data deleted
    legacy_book_id: Optional[str] = None    # epub_processor book id

    @model_validator(mode='after')
    def _rights_for_purpose(self) -> 'ReferenceSource':
        for p in self.purposes:
            allowed = NEEDS_RIGHTS.get(p)
            if allowed and self.rights.status not in allowed:
                raise ValueError(
                    f'{p} needs rights in {allowed}; got '
                    f'{self.rights.status!r}')
        return self


# -------------------------------------------------------- style profiles ----

NUMERIC_TRAITS = (
    'pacing',               # 0 slow, lingering        .. 1 fast, clipped
    'atmosphere',           # 0 plain, neutral         .. 1 dense, immersive
    'dialogue_density',     # 0 mostly narration       .. 1 mostly dialogue
    'descriptive_density',  # 0 sparse                 .. 1 lush
    'suspense',             # 0 information given early .. 1 withheld long
    'emotional_rhythm',     # 0 even                   .. 1 wide swings
    'narrative_complexity',  # 0 single linear thread  .. 1 interwoven
    'sentence_length',      # 0 short                  .. 1 long
    'formality',            # 0 colloquial             .. 1 formal
)
CATEGORICAL_TRAITS = {
    'narrative_perspective': ('first_person', 'close_third', 'omniscient',
                              'multi_pov', 'host_addressing_listener',
                              'dialogue_only'),
    'scene_transitions': ('hard_cut', 'sound_bridge', 'narrated_link',
                          'time_stamp', 'thematic_echo'),
    'structural_method': ('linear', 'framed', 'braided', 'episodic_vignettes',
                          'countdown', 'question_led'),
    'tone': ('wry', 'earnest', 'ominous', 'warm', 'clinical', 'playful',
             'elegiac', 'urgent'),
}


class StyleProfile(BaseModel):
    """Abstract, non-expressive description of HOW something is written.
    Deliberately has no free-text field: nothing here can carry a name,
    a plot event, a quotation or an author's identity."""
    source_id: str
    version: int = 1
    numeric: Dict[str, float] = Field(default_factory=dict)
    categorical: Dict[str, str] = Field(default_factory=dict)
    measured: Dict[str, float] = Field(default_factory=dict)  # raw stats
    edited_by_user: bool = False

    @model_validator(mode='after')
    def _closed_vocabulary(self) -> 'StyleProfile':
        for k, v in self.numeric.items():
            if k not in NUMERIC_TRAITS:
                raise ValueError(f'unknown numeric trait {k!r}')
            if not 0.0 <= v <= 1.0:
                raise ValueError(f'{k} must be within 0..1')
        for k, v in self.categorical.items():
            if k not in CATEGORICAL_TRAITS:
                raise ValueError(f'unknown categorical trait {k!r}')
            if v not in CATEGORICAL_TRAITS[k]:
                raise ValueError(f'{k}={v!r} is not an allowed value')
        return self


class ReferenceBinding(BaseModel):
    """How one source influences one scope. Mirrors the user-facing JSON."""
    source_id: str
    reference_mode: ReferencePurpose
    influence: float = Field(ge=0.0, le=1.0)
    selected_traits: Dict[str, float] = Field(default_factory=dict)
    scope: Scope
    enabled: bool = True

    @model_validator(mode='after')
    def _traits_known(self) -> 'ReferenceBinding':
        for k, v in self.selected_traits.items():
            if k not in NUMERIC_TRAITS and k not in CATEGORICAL_TRAITS:
                raise ValueError(f'unknown trait {k!r}')
            if not 0.0 <= v <= 1.0:
                raise ValueError(f'weight for {k} must be within 0..1')
        return self


class TraitTrace(BaseModel):
    trait: str
    baseline: object
    value: object
    contributions: List[Tuple[str, float, object]]   # (source, weight, target)


class ResolvedStyle(BaseModel):
    numeric: Dict[str, float]
    categorical: Dict[str, str]
    trace: List[TraitTrace]


def _applicable(bindings: List[ReferenceBinding], sources: Dict[str,
                ReferenceSource], scope: Scope) -> List[ReferenceBinding]:
    out = []
    for b in bindings:
        src = sources.get(b.source_id)
        if (not b.enabled or b.reference_mode != 'writing_techniques'
                or b.influence <= 0 or src is None or not src.enabled
                or src.removed_at or src.purged_at):
            continue
        if b.scope.project_id != scope.project_id:
            continue                                  # isolation
        if b.scope.show_id and b.scope.show_id != scope.show_id:
            continue
        if b.scope.episode_id and b.scope.episode_id != scope.episode_id:
            continue
        out.append(b)
    return sorted(out, key=lambda b: b.source_id)     # order-independent


def resolve_style(baseline: StyleProfile, bindings: List[ReferenceBinding],
                  profiles: Dict[str, StyleProfile],
                  sources: Dict[str, ReferenceSource],
                  scope: Scope) -> ResolvedStyle:
    """Deterministic blend.

    numeric trait:  v = base + sum(w_i * (p_i - base)) / max(1, sum(w_i))
                    with w_i = influence_i * selected_traits_i[trait]
    categorical:    the applicable binding with the most specific scope wins,
                    then the largest weight, then the smallest source_id;
                    it replaces the baseline only if its weight >= 0.5.
    A trait a binding does not select is not influenced by that binding.
    """
    use = _applicable(bindings, sources, scope)
    numeric, categorical, trace = {}, {}, []
    for t in NUMERIC_TRAITS:
        base = baseline.numeric.get(t, 0.5)
        contrib = []
        for b in use:
            p = profiles[b.source_id].numeric.get(t)
            w = b.influence * b.selected_traits.get(t, 0.0)
            if p is not None and w > 0:
                contrib.append((b.source_id, round(w, 4), p))
        total = sum(w for _, w, _ in contrib)
        v = base + sum(w * (p - base) for _, w, p in contrib) / max(1.0, total)
        numeric[t] = round(v, 4)
        trace.append(TraitTrace(trait=t, baseline=base, value=numeric[t],
                                contributions=contrib))
    for t in CATEGORICAL_TRAITS:
        base = baseline.categorical.get(t, '')
        contrib = []
        for b in use:
            p = profiles[b.source_id].categorical.get(t)
            w = b.influence * b.selected_traits.get(t, 0.0)
            if p and w > 0:
                contrib.append((b.scope.specificity(), round(w, 4),
                                b.source_id, p))
        contrib.sort(key=lambda c: (-c[0], -c[1], c[2]))
        value = base
        if contrib and contrib[0][1] >= 0.5:
            value = contrib[0][3]
        if value:
            categorical[t] = value
        trace.append(TraitTrace(
            trait=t, baseline=base, value=value,
            contributions=[(s, w, p) for _, w, s, p in contrib]))
    return ResolvedStyle(numeric=numeric, categorical=categorical,
                         trace=trace)


BANDS = ('very low', 'low', 'moderate', 'high', 'very high')


def band(v: float) -> str:
    return BANDS[min(4, int(v * 5))]


DIRECTIVES = {
    'pacing': ('Let scenes breathe; long beats, few cuts.',
               'Unhurried; allow pauses.', 'Balanced pace.',
               'Brisk; enter scenes late, leave early.',
               'Fast and clipped; short scenes, quick exchanges.'),
    'dialogue_density': ('Carry most of it in narration.',
                         'Narration leads; dialogue punctuates.',
                         'Balance narration and dialogue.',
                         'Dialogue leads; narration only to orient.',
                         'Almost entirely dialogue and sound.'),
    'descriptive_density': ('Describe almost nothing.',
                            'One concrete detail per scene.',
                            'Describe what matters to the action.',
                            'Rich sensory description.',
                            'Lush, layered description.'),
}


def render_directives(style: ResolvedStyle) -> List[str]:
    """Turn the resolved numbers into plain writing instructions. The
    prompt never contains a percentage, an author, or a source title."""
    out = []
    for t, v in style.numeric.items():
        phrases = DIRECTIVES.get(t)
        out.append(f'{t.replace("_", " ")}: '
                   + (phrases[min(4, int(v * 5))] if phrases else band(v)))
    for t, v in style.categorical.items():
        out.append(f'{t.replace("_", " ")}: {v.replace("_", " ")}')
    return out


# ------------------------------------------------------- factual claims ----

class Citation(BaseModel):
    source_id: str
    locator: str                  # 'ch. 4 §2', 'p. 113', 'para 18'
    quote: str = Field(min_length=1)       # verified against the source


class FactClaim(BaseModel):
    claim_id: str
    project_id: str
    text: str
    kind: Literal['fact', 'figure', 'date', 'quote', 'estimate',
                  'interpretation', 'opinion']
    citations: List[Citation] = Field(default_factory=list)
    support: Literal['single_source', 'corroborated', 'contested',
                     'unsupported'] = 'unsupported'
    conflicts_with: List[str] = Field(default_factory=list)   # claim ids
    must_flag_uncertainty: bool = False
    verified_by: List[Literal['quote_match', 'judge', 'human']] = \
        Field(default_factory=list)

    @model_validator(mode='after')
    def _consistent(self) -> 'FactClaim':
        n = len({c.source_id for c in self.citations})
        if self.conflicts_with:
            self.support = 'contested'
        elif n == 0:
            self.support = 'unsupported'
        elif n == 1:
            self.support = 'single_source'
        else:
            self.support = 'corroborated'
        self.must_flag_uncertainty = (
            self.support in ('contested', 'unsupported')
            or self.kind in ('estimate', 'interpretation', 'opinion'))
        return self


class SegmentCard(BaseModel):
    """Nonfiction counterpart of SceneCard."""
    segment_number: int
    kind: Literal['cold_open', 'context', 'explanation', 'example',
                  'evidence', 'counterpoint', 'exchange', 'story',
                  'check_understanding', 'recap', 'sign_off']
    purpose: str
    speakers: List[str] = Field(min_length=1)
    key_points: List[str] = Field(min_length=1)
    claim_ids: List[str] = Field(default_factory=list)
    builds_on: List[int] = Field(default_factory=list)   # earlier segments
    listener_takeaway: str
    transition_to_next: str = ''
    sound_design: List[str] = Field(default_factory=list)


if __name__ == '__main__':
    import itertools, json, time
    now = time.time()
    # the user-facing example from the brief validates as-is
    example = {"reference_mode": "writing_techniques", "influence": 0.4,
               "selected_traits": {"pacing": 0.7, "atmosphere": 0.8,
                                   "dialogue_density": 0.3,
                                   "descriptive_density": 0.5,
                                   "narrative_complexity": 0.6},
               "scope": {"project_id": "example_horror",
                         "show_id": "the_last_station"}}
    ReferenceBinding(source_id='SRC-a', **example)

    def src(sid, **kw):
        kw.setdefault('purposes', ['writing_techniques'])
        return ReferenceSource(
            source_id=sid, project_id='example_horror', source_format='epub',
            title='t', ingested_at=now, content_sha256='0' * 64, **kw)
    sources = {'SRC-a': src('SRC-a'), 'SRC-b': src('SRC-b')}
    profiles = {
        'SRC-a': StyleProfile(source_id='SRC-a', numeric={'pacing': 0.9,
                 'atmosphere': 1.0}, categorical={'tone': 'ominous'}),
        'SRC-b': StyleProfile(source_id='SRC-b', numeric={'pacing': 0.1,
                 'dialogue_density': 0.9}, categorical={'tone': 'wry'})}
    base = StyleProfile(source_id='BASE', numeric={t: 0.5
                        for t in NUMERIC_TRAITS})
    sc = Scope(project_id='example_horror', show_id='the_last_station')
    a = ReferenceBinding(source_id='SRC-a', reference_mode='writing_techniques',
                         influence=0.5, selected_traits={'pacing': 1.0,
                         'atmosphere': 0.8, 'tone': 1.0}, scope=sc)
    b = ReferenceBinding(source_id='SRC-b', reference_mode='writing_techniques',
                         influence=1.0, selected_traits={'pacing': 0.25,
                         'dialogue_density': 1.0, 'tone': 0.4}, scope=sc)
    r = resolve_style(base, [a, b], profiles, sources, sc)
    # pacing: 0.5 + (0.5*(0.9-0.5) + 0.25*(0.1-0.5)) / max(1, 0.75) = 0.6
    assert r.numeric['pacing'] == 0.6, r.numeric['pacing']
    assert r.numeric['atmosphere'] == 0.7            # 0.5 + 0.4*0.5
    assert r.numeric['dialogue_density'] == 0.9      # weight 1.0 -> target
    assert r.numeric['suspense'] == 0.5              # nobody selected it
    assert r.categorical['tone'] == 'ominous'        # 0.5 beats 0.4, >= 0.5
    # order independence
    for perm in itertools.permutations([a, b]):
        assert resolve_style(base, list(perm), profiles, sources,
                             sc).model_dump() == r.model_dump()
    # influence 0 / disabled / other project -> baseline
    zero = a.model_copy(update={'influence': 0.0})
    off = b.model_copy(update={'enabled': False})
    other = Scope(project_id='history_doc', show_id='x')
    for bs, s in (([zero, off], sc), ([a, b], other), ([], sc)):
        rr = resolve_style(base, bs, profiles, sources, s)
        assert all(v == 0.5 for v in rr.numeric.values()) and not rr.categorical
    # removed source stops influencing
    sources['SRC-a'].removed_at = now
    assert resolve_style(base, [a, b], profiles, sources,
                         sc).numeric['atmosphere'] == 0.5
    # episode scope beats show scope for categorical traits
    sources['SRC-a'].removed_at = None
    ep = Scope(project_id='example_horror', show_id='the_last_station',
               episode_id='ep_1')
    b_ep = b.model_copy(update={'scope': ep, 'selected_traits': {'tone': 0.6}})
    assert resolve_style(base, [a, b_ep], profiles, sources,
                         ep).categorical['tone'] == 'wry'
    # prompts carry bands, never numbers, authors or titles
    text = ' '.join(render_directives(r))
    assert '%' not in text and 'SRC-' not in text
    # style profile cannot hold free text
    for bad in ({'numeric': {'pacing': 1.5}}, {'numeric': {'hero': 0.5}},
                {'categorical': {'tone': 'like Author X'}}):
        try:
            StyleProfile(source_id='x', **bad)
            raise SystemExit('profile validation failed to fire')
        except ValueError:
            pass
    # rights gate
    try:
        src('SRC-c', purposes=['world_building'])
        raise SystemExit('rights gate failed to fire')
    except ValueError:
        pass
    src('SRC-c', purposes=['world_building'],
        rights=Rights(status='owned', holder='user'))
    # claims: conflict is kept, never averaged
    c1 = FactClaim(claim_id='CL-1', project_id='p', kind='figure',
                   text='The bridge opened in 1883.',
                   citations=[Citation(source_id='SRC-a', locator='p. 12',
                                       quote='opened to traffic in 1883')],
                   conflicts_with=['CL-2'])
    assert c1.support == 'contested' and c1.must_flag_uncertainty
    c3 = FactClaim(claim_id='CL-3', project_id='p', kind='fact', text='x',
                   citations=[Citation(source_id='SRC-a', locator='1',
                                       quote='q'),
                              Citation(source_id='SRC-b', locator='2',
                                       quote='q')])
    assert c3.support == 'corroborated' and not c3.must_flag_uncertainty
    assert FactClaim(claim_id='CL-4', project_id='p', kind='fact',
                     text='y').must_flag_uncertainty
    assert set(MODE_CAPABILITIES) == set(ProductionMode.__args__)
    ProjectConfig(project_id='p', show_id='s', title='T', idea='i',
                  mode='educational').capability('claims')
    print('OK reference_models')
