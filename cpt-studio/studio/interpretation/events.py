"""The per-code rule of the events engine (design/FINAL.md 7.2-7.6, as design/ADJUDICATION.md C-1, C-6, C-7, C-9 and
C-10 amend it): one proposed code against the persisted event inventory - its candidates, its supporting events, its
dependencies, the relations that decide it, its exclusion, and the ONE focused question that holds it. Pure: it reads
the inventory's stored attributes (values, states, the literals of their own words) and the code's kept evidence
spans, never the revision text for meaning (P6), and it produces no value (P2).

THE RULE, in order (7.2): R1 (scope and exact evidence) is the caller's - a code failing it is never evaluated. Then:
- R2 a link route (mapping.code_link): (a) the catalogue, (b) an unreconciled act; route (c) is REMOVED (C-6), so a code
  with no catalogue profile or of another family is held, never READY ("outside CPT Studio's coding profiles; review
  required").
- R3 a SUPPORTING event (7.3) for each of the code's requirement groups (``requirements``): the examination kinds are the
  SESSION, never an act (C-1), so a code whose covers hold an examination kind and others needs a supporting event of
  EACH other kind; any other code needs one of its kinds (a tattoo and an injection are one act) - of its DEFINING kinds
  where DECISIONS D27 narrows it (mapping.DEFINING: the kinds no other code of its family accounts for alone; 43265 is
  matched by a lithotripsy, never by the stone extraction 43264 accounts for), so a code with no supporting event of a
  defining kind takes R3's failure path over those kinds (with none of them stated at all: 7.6, not documented, naming
  the defining act). An event supports when
  it is a candidate (its catalogue kind maps into the group, or is an umbrella covering it, in the code's family - any
  family on route (b)) and: its kind and family are usable (verified, or default-accepted, and not opened); its status is
  a usable ``performed`` - or, for a code that accounts for the examination itself (a base code, an examination-only
  EUS code), a usable ``attempted_not_completed`` (verified by its failure marker; the 52/53 consideration); its time is
  a usable ``current_encounter`` and its performer a usable ``documenting_team`` (an explicit unknown is absent, never a
  match: C6); it is not a positive removal umbrella (line 5: no method-specific code rests on one); and it is the
  positive side of no CONTRADICTION, DOUBT or UNRESOLVED relation.
- When a group has no supporting event: 7.4 (a positive candidate: held, ONE focused question, h1-h5 in order over the
  candidates in document order), else 7.5 (a decisive statement: EXCLUDED, reinstatable), else 7.6 (not documented:
  held). C-9: for a code that does not account for the examination, an act begun and not completed is a HOLD
  (performed_status and the 52/53 consideration), never an exclusion.
- R4 the dependencies beyond R3: the device class when the profile names a technique (a verified device of that class;
  another class is the "dilation of another technique" hold, an absent or unverified device the technique question);
  then, for a site-specific dilation code (DECISIONS D29, mapping.DILATION_SITES), the site class of the dilation: its
  target landmark verified - directly, or as the verified site of its verified lesion - in the code's class (esophageal,
  or gastric and duodenal). A dilation verified outside the class supports nothing ("dilation at another site", held);
  one whose place is not verified, is a surgically made place (an anastomosis, unless DECISIONS D34 places it: the
  encounter's one anastomosis at the place its anatomy entry's own type words give) or is verified both in and outside
  the class asks which structure was dilated (act_target). Never excluded.
- R5 bundling (7.7, through coverage): every supporting act part of another documented act holds the code with the
  legacy "part of another documented act" sentence; an act whose bundling depends on an unresolved identity holds it
  with act_target.
R6-R9 (required facts, the date, the combination rules, the reference checks) are the assessment's (assess.py), over
this module's Evaluation.

7.5 EXCLUSION (D5, tightened; Engine A's "only event of its kind" arm is rejected): with no supporting event and no
positive candidate, a DECISIVE event D excludes the code only when (1) D concerns the code's acts - its kind in the group
or an umbrella covering it, its kind and family usable; (2) D's deciding attribute passed its deterministic check
(verify.exclusion_basis: status not_performed by a negator, planned by a planning marker; time earlier or future by a
compared date literal or a time marker; performer another clinician by a titled or credentialed name, another facility
by a name or a facility marker) - the exclusion records ``basis``; an exceptive statement never excludes (C-7), and an
act begun and not completed never does (C-9); (3) D covers the code BY CITATION ONLY (coverage_of): a kept span of the
code overlaps D's own passages and EVERY kept span lies within the union of D's own attribute word spans - exactly
C-10's kind, status, time and target (COVERING). A citation that overlaps D but reaches words no D word covers, in
that span or in another span of the code, gives a statement_scope question instead (C-10); and a BROAD statement
(not_performed, all_of_kind usable, current_encounter usable, its family's session resolved) has no cover of its own:
one the code does not cite gives the statement_scope question, never an exclusion (C-7, which governs FINAL 7.5 (3)
and the 7.12 v5 row); (4) nothing doubts the code's kinds (no uncertain candidate, no DOUBT relation on a candidate or
from a statement of its kinds).

THE OMISSION CASE (P4): Gemini drops a current act and the proposer cites that act's own passage; only a historical or
denied statement of the kind exists elsewhere, in the same sentence, or cited beside the act in a second span of the
code, or a broad current denial stands elsewhere. Coverage fails (no citation of the statement, or a citation reaching
words the statement's own words do not cover), so the code is held, never excluded.

Imports nothing from studio.gi but the reference tables, through mapping (FINAL 3.1).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Optional

from studio.interpretation import identity, lexicon, mapping, relations, verify, wording
from studio.interpretation import ercp  # DECISIONS D105, D106: the ERCP rules over the per-code rule (evaluate's)

ATTRIBUTES = ('procedure', 'kind', 'technique', 'target', 'time', 'performer', 'status', 'scope', 'purpose')
BLOCKING = (relations.CONTRADICTION, relations.DOUBT, relations.UNRESOLVED)
# The attributes whose words an exclusion's coverage reads: exactly ADJUDICATION C-10's list - the deciding event's kind,
# status, time and target. A kept span reaching any other word (a performer's name, a facility, a quantifier outside the
# status words) gives the statement_scope question, never an exclusion.
COVERING = ('kind', 'status', 'time', 'target')
# The event's own statement: the passages of the act itself (what a question quotes and a support shows).
OWN = ('kind', 'status', 'target')

# Evaluation.reason values.
SUPPORTED, INCOMPLETE = 'supported', 'incomplete'
NOT_LINKED, UNPROFILED = 'not_linked', 'unprofiled'
CONFLICT, DOUBT, UNRESOLVED, UNVERIFIED, ATTEMPTED, METHOD = (
    'conflict', 'doubt', 'unresolved', 'unverified', 'attempted', 'method')
EXCLUDED, STATEMENT_SCOPE, NOT_DOCUMENTED = 'excluded', 'statement_scope', 'not_documented'
TECHNIQUE, ANOTHER_TECHNIQUE, BUNDLED, BUNDLING_IDENTITY = 'technique', 'another_technique', 'bundled', 'bundling'
SITE, ANOTHER_SITE = 'site', 'another_site'  # D29: a dilation's site not established, or verified outside the class
SESSION = 'session'  # D31: a supported code whose session's examination an open question of Gemini's names

# DECISIONS D31: who did a session, when, and whether it was done are properties of the SESSION, and Gemini's doubt of no
# named attribute ('other') is a doubt of whatever it names. An open question about one of these that names a session's
# examination event holds every code that session supports, asking that question (the fact each asks). An act-level
# question (kind, target, technique, ...) holds its own act only, as before: it opens that attribute of each event it
# names (normalize._read_openings).
SESSION_ABOUT = MappingProxyType({'performer': 'event_performer', 'time': 'event_time', 'status': 'performed_status',
                                  'other': 'performed_status'})


# --- the stored inventory, as this engine reads it -------------------------------------------------------------------

class Reading:
    """One stored event inventory (store.StoredInventory, normalize.Inventory, or a mapping of its content), indexed for
    the engine. Read-only by convention: nothing here changes a record. It answers what identity.lesion_facts and
    relations.Context read of a Draft (``lesions``, ``events``, ``passages_of``), so their pure rules read it as they
    read the inventory while it was made."""

    def __init__(self, events: Mapping, encounter_facts: Mapping, open_questions: Sequence = ()):
        self.passages = {record['id']: record for record in events['passages']}
        self.lesions = {record['id']: record for record in events['lesions']}
        self.events = {record['id']: record for record in events['events']}
        self.relations = list(events['relations'])
        self.encounter = encounter_facts
        self.open_questions = list(open_questions)
        self.order = {eid: index for index, eid in enumerate(self.events)}
        self.by_event: dict = {}
        self.by_statement: dict = {}
        for relation in self.relations:
            self.by_event.setdefault(relation['event'], []).append(relation)
            self.by_statement.setdefault(relation['statement'], []).append(relation)
        self._facts = None
        self._context = None

    @classmethod
    def of(cls, inventory) -> 'Reading':
        if isinstance(inventory, Reading):
            return inventory
        if isinstance(inventory, Mapping):
            return cls(inventory['events'], inventory['encounter_facts'], inventory.get('open_questions') or ())
        return cls(inventory.events, inventory.encounter_facts, inventory.open_questions)

    def passages_of(self, span: Mapping) -> list:
        """The located or ambiguous passages one of whose places holds ``span`` (normalize.Draft.passages_of)."""
        return [pid for pid, record in self.passages.items() if record['state'] != 'unlocated' and any(
            place['start'] <= span['start'] and span['end'] <= place['end'] for place in record['spans'])]

    def places(self, pids) -> list:
        """The located places of passages ``pids`` (every place of an ambiguous one), each {start, end, text}."""
        out = []
        for pid in pids:
            record = self.passages.get(pid)
            if record and record['state'] != 'unlocated':
                out.extend({'start': place['start'], 'end': place['end'], 'text': place['text']}
                           for place in record['spans'])
        return out

    @property
    def lesion_facts(self) -> dict:
        if self._facts is None:
            self._facts = identity.lesion_facts(self)
        return self._facts

    @property
    def context(self) -> relations.Context:
        if self._context is None:
            self._context = relations.Context(self)
        return self._context

    def relations_of(self, event_id: str, types=BLOCKING) -> list:
        return [relation for relation in self.by_event.get(event_id, ()) if relation['type'] in types]


# --- reading one event -------------------------------------------------------------------------------------------------

def usable(event: Mapping, name: str) -> bool:
    return verify.usable(event.get(name))


def value(event: Mapping, name: str):
    record = event.get(name)
    return record.get('value') if isinstance(record, Mapping) else None


def words_of(event: Mapping, *names) -> Optional[dict]:
    """The first of ``names``' own words spans the event has (status, kind, ... by default)."""
    for name in names or ('status', 'kind', 'target', 'time', 'performer'):
        record = event.get(name)
        if isinstance(record, Mapping) and isinstance(record.get('words'), Mapping):
            return record['words']
    return None


def own_passages(event: Mapping, names=OWN) -> list:
    ids = []
    for name in names:
        record = event.get(name)
        if isinstance(record, Mapping):
            ids.extend(record.get('passages') or ())
    return list(dict.fromkeys(ids))


def all_passages(event: Mapping) -> list:
    return own_passages(event, ATTRIBUTES)


def statement_text(reading: Reading, event: Mapping) -> str:
    """The event's own words to quote: its status words, else its kind words, else its first own located passage."""
    span = words_of(event, 'status', 'kind')
    if span is not None:
        return span['text']
    places = reading.places(own_passages(event))
    return places[0]['text'] if places else ''


def anchors(reading: Reading, event: Mapping) -> list:
    """The event's own statement in the document: the places of its kind, status and target passages, each once, in
    document order (FINAL 7.11 ``source``; 7.8 the unresolved items' evidence)."""
    seen, out = set(), []
    for place in sorted(reading.places(own_passages(event)), key=lambda item: (item['start'], item['end'])):
        key = (place['start'], place['end'])
        if key not in seen:
            seen.add(key)
            out.append(place)
    return out


def verified_other_time(event: Mapping) -> bool:
    return usable(event, 'time') and value(event, 'time') in ('earlier_encounter', 'future')


def verified_other_performer(event: Mapping) -> bool:
    return usable(event, 'performer') and value(event, 'performer') in ('other_clinician', 'other_facility')


def done(event: Mapping) -> bool:
    """Performed (or begun) at this encounter by the documenting team, every one of those attributes usable: what a
    reportable event and a session's examination are (7.8)."""
    return (usable(event, 'status') and value(event, 'status') in verify.POSITIVE
            and usable(event, 'time') and value(event, 'time') == 'current_encounter'
            and usable(event, 'performer') and value(event, 'performer') == 'documenting_team')


# --- labels (CPT Studio's words over the event's stored values and the document's own slices) --------------------------

def lesion_words(reading: Reading, lesion_id: str) -> str:
    """A lesion as CPT Studio names it: its own description (the document's slice), with its verified site."""
    lesion = reading.lesions.get(lesion_id)
    if lesion is None:
        return ''
    text = ' '.join(lesion['words']['text'].split()) if lesion.get('words') else ''
    site = lesion.get('site') or {}
    where = wording.landmark_label(site.get('value', '')) if verify.usable(site) else ''
    if where and where not in text.lower():
        text = f'{text} in the {where}' if text else where
    return text


def event_label(reading: Reading, event: Mapping) -> str:
    """reconcile.describe_act's form over an event: its act label, its verified device where the label does not name
    it, and the verified lesion it was done on, else its verified site."""
    kind = event.get('catalogue_kind') or ''
    if kind in mapping.EXAMINATION_KINDS:
        label = wording.kind_label(mapping.service_kind(event.get('family', ''))) if kind == mapping.EXAMINATION \
            else wording.act_label(kind)
        if not label or label == 'examination':
            label = 'examination'
    else:
        label = wording.event_kind_label(kind or value(event, 'kind') or 'other')
    device = value(event, 'technique') if usable(event, 'technique') else ''
    device = wording.landmark_label(device) if device not in ('', 'not_stated', 'other', 'endoscope') else ''
    if device and device not in label:
        label = f'{label} ({device})'
    lesion = identity.verified_lesion(event)
    words = lesion_words(reading, lesion) if lesion else ''
    if words:
        return f'{label} of the {words}'
    place = wording.landmark_label(mapping.target_landmark(event))
    return f'{label} at the {place}' if place else label


def group_label(link: mapping.CodeLink, group: Sequence[str]) -> str:
    """What a code's requirement group names: the session's service for an examination, else its acts."""
    if all(kind in mapping.EXAMINATION_KINDS for kind in group):
        service = mapping.service_kind(link.family)
        if group and group[0] == mapping.EUS_EXAMINATION:
            return wording.act_label(mapping.EUS_EXAMINATION)
        return wording.kind_label(service) if service else 'examination'
    return ' or '.join(dict.fromkeys(wording.act_label(kind) for kind in group))


def service_label(family: str) -> str:
    service = mapping.service_kind(family)
    return wording.kind_label(service) if service else wording.family_label(family)


# --- the requirement groups (C-1) --------------------------------------------------------------------------------------

def requirements(link: mapping.CodeLink) -> tuple:
    """The code's requirement groups, each needing a supporting event of one of its kinds (module docstring)."""
    if not link.linked:
        return ()
    if link.route == mapping.UNRECONCILED_ROUTE:
        return (tuple(link.kinds),)
    if link.acts and any(kind in mapping.EXAMINATION_KINDS for kind in link.kinds):
        # C-1: each act besides the examination, which is the session (an EUS code's acts are its D27 defining kinds)
        return tuple((kind,) for kind in link.acts)
    kinds = link.defining or link.kinds  # D27: only an event of a defining kind matches a code it narrows
    return (tuple(kinds),) if kinds else ()


def accounted(link: mapping.CodeLink) -> tuple:
    """The kinds a code accounts for, as CPT Studio names them: its defining kinds where D27 narrows it, else the acts
    besides the examination, else its kinds."""
    return link.defining or link.acts or link.kinds


def examination_code(link: mapping.CodeLink) -> bool:
    """Whether the code accounts for the examination itself (a base code, an examination-only EUS code): an examination
    begun and not completed supports it, with the 52/53 consideration (7.3 line 2)."""
    return link.base or (bool(link.kinds) and all(kind in mapping.EXAMINATION_KINDS for kind in link.kinds))


def is_candidate(link: mapping.CodeLink, group: Sequence[str], event: Mapping) -> bool:
    """7.3: an event of a kind in the group, or of an umbrella covering it, of the code's family (route (a)); on route
    (b), of a kind in the group with its verified target in the code's regions, in any family."""
    if not link.linked:
        return False
    kind = event.get('catalogue_kind') or ''
    if link.route == mapping.UNRECONCILED_ROUTE:
        return kind in group and mapping.in_regions(mapping.target_landmark(event), link.regions)
    if event.get('family') != link.family:
        return False
    return any(mapping.covers(kind, wanted) for wanted in group)


DIGITAL = 'manual'  # the device of a digital examination (FINAL 5.6, E13): the one examination that is no session


def endoscopic_examination(event: Mapping) -> bool:
    """Whether an examination event can be its endoscopic family's session (FINAL 5.6, E13: "the session's examination is
    the colonoscopy"): any examination but one of an endoscopic family whose device is VERIFIED as ``manual`` - a digital
    rectal examination read as the family's examination is no session and supports no base code. E13 names that
    technique only: an examination whose verified device is any other class (an echoendoscope read as ``other``, a
    balloon enteroscope) is its family's session, and an unstated or unverified device never sets one apart."""
    if event.get('family') not in mapping.ENDOSCOPIC_FAMILIES:
        return True
    return not (usable(event, 'technique') and value(event, 'technique') == DIGITAL)


def defining_fit(reading: Reading, link: mapping.CodeLink, event: Mapping) -> bool:
    """DECISIONS D136 (the round-5 review of D120, problem 1): whether ``event`` meets the code's defining-target
    requirement (mapping.defining_target, D120), read with the record of the lesion its target is verified to be
    (identity.verified_lesion): True for every code but 43240, whose drainage must be of a pancreatic fluid collection -
    its usable target's words or its verified lesion's words name one, and no verified place of it is biliary or in the
    liver. A drainage that misses it never supports 43240: 'EUS-guided transmural drainage of the gallbladder was
    performed from the duodenal bulb with a 15 mm lumen-apposing metal stent.' (its target verified at the gallbladder),
    a bile duct's, a liver abscess's or one whose target is not verified holds 43240, never READY - d353e64df READY; the
    installed release holds every 43240. DECISIONS D145 (the round-5c review of D136, problem 1): read after R3, by
    evaluate, as D29's site class is - a supporting drainage that misses it is kept out of the code's support, and with
    none left the code takes _target_hold's target question - no longer in supports, where it sent the drainage to
    7.4's last-resort question, whether it was done."""
    lesion = identity.verified_lesion(event)
    return mapping.defining_target(link.code, event, reading.lesions.get(lesion) if lesion else None)


def supports(reading: Reading, link: mapping.CodeLink, group: Sequence[str], event: Mapping) -> bool:
    """7.3 lines 1-4, 6 and 7 (line 5, the device class, is R4's; the code's defining target is read after R3 -
    DECISIONS D145: defining_fit, in evaluate)."""
    if not is_candidate(link, group, event) or (event.get('catalogue_kind') or '') in mapping.UMBRELLAS:
        return False
    if event.get('catalogue_kind') in mapping.EXAMINATION_KINDS and not endoscopic_examination(event):
        return False
    if not usable(event, 'kind') or (link.route == mapping.CATALOGUE_ROUTE and not usable(event, 'procedure')):
        return False
    allowed = verify.POSITIVE if examination_code(link) else ('performed',)
    if not (usable(event, 'status') and value(event, 'status') in allowed):
        return False
    if not (usable(event, 'time') and value(event, 'time') == 'current_encounter'):
        return False
    if not (usable(event, 'performer') and value(event, 'performer') == 'documenting_team'):
        return False
    return not reading.relations_of(event['id'])


# --- what the rule decides -------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Question:
    """The one focused question of a held code: its fact (questions.MISSING's or wording.NEW_FACTS'), CPT Studio's
    question and reason, the events it concerns and the document's spans it quotes ({start, end, text})."""
    fact: str
    question: str
    reason: str
    events: tuple = ()
    passages: tuple = ()


@dataclass(frozen=True)
class Exclusion:
    """A decisive statement that excludes the code (7.5): its event, the deciding attribute and value, the basis
    (literal | marker; C1), the deciding words and CPT Studio's reason."""
    event: str
    attribute: str
    value: str
    basis: str
    words: Optional[dict]
    reason: str
    cover: str  # 'citation': the code's kept spans lie within the statement's own words (C-7, C-10; no other cover)


@dataclass(frozen=True)
class Evaluation:
    """What the per-code rule decided for one code. ``state``: performed | incomplete | not_performed | uncertain (the
    code's support state, FINAL 7.11); ``reason``: this module's reason constants; ``supporting``: E*(C), the event ids
    the code accounts for (empty when held or excluded); ``read``: every event the decision read (its fingerprint's
    events); ``unverified``: the (event, attribute) pairs a decision read and found unusable; ``second``: a held code's
    second question, which assess asks as its own clarification after ``question`` (DECISIONS D161: _target_hold's target
    question; DECISIONS D168 (3): ercp.role_second's exchange or retrieval question beside the another_role hold)."""
    code: str
    family: str
    link: mapping.CodeLink
    state: str
    reason: str
    detail: str
    supporting: tuple = ()
    read: tuple = ()
    question: Optional[Question] = None
    exclusion: Optional[Exclusion] = None
    relation: Optional[dict] = None
    incomplete_words: str = ''  # the failure-marker words of an examination begun and not completed (R-4)
    attempted: bool = False  # C-9: a non-examination code's act begun and not completed (the 52/53 consideration)
    unverified: tuple = ()
    bundled: tuple = field(default=())  # (event id, why) of supporting acts part of another documented act
    second: Optional[Question] = None  # D161: _target_hold's target question beside 7.4's; D168 (3): ercp.role_second's

    @property
    def held(self) -> bool:
        return self.state == 'uncertain'

    @property
    def excluded(self) -> bool:
        return self.state == 'not_performed'


def _spans(items) -> tuple:
    out, seen = [], set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        key = (item['start'], item['end'])
        if key not in seen:
            seen.add(key)
            out.append({'start': item['start'], 'end': item['end'], 'text': item['text']})
    return tuple(out)


def _kept_places(kept) -> tuple:
    return _spans({'start': span.start, 'end': span.end, 'text': span.text} for span in kept)


def evaluate(code: str, kept: Sequence, reading: Reading, link: Optional[mapping.CodeLink] = None) -> Evaluation:
    """The per-code rule (module docstring) for ``code`` in scope with its kept exact evidence ``kept``
    (types.EvidenceSpan, already verified against the revision text by checks.exact_evidence)."""
    ruled = ercp.ruled(code, kept, reading, link)  # DECISIONS D105, D106: the ERCP rules over this rule's evaluation
    if ruled is not None:
        return ruled
    from studio.interpretation import coverage  # bundling is coverage's (7.7); coverage reads this module

    link = link if link is not None else mapping.code_link(code)
    family = link.family
    own = _kept_places(kept)
    if not link.linked or not requirements(link):  # no route, or a route naming no act: held, never READY (C-6)
        unprofiled = link.reason == mapping.UNPROFILED
        reason = wording.not_linked_reason(code, unprofiled)
        return Evaluation(code, family, link, 'uncertain', UNPROFILED if unprofiled else NOT_LINKED, reason,
                          question=Question('performed_status', wording.performed_question(code), reason, (), own))
    if mapping.recognised_only(link):  # DECISIONS D80: recognised, not assessed - held, never READY, never excluded
        return recognised_only_hold(code, link, own)
    supporting: list = []
    for group in requirements(link):
        found = [event for event in reading.events.values() if supports(reading, link, group, event)]
        if not found:
            return _without_support(code, link, group, kept, own, reading)
        supporting.extend(event for event in found if event not in supporting)
    doubt = session_doubt(reading, supporting)
    if doubt is not None:  # DECISIONS D31: Gemini's open question on the session's examination holds the session
        return _session_hold(code, link, supporting, reading, *doubt)
    name = service_label(family)
    if link.technique:  # R4: the device class of a technique-specific code
        fitting = [event for event in supporting if mapping.code_technique(event) == link.technique]
        if not fitting:
            return _technique_hold(code, link, supporting, reading, own, name)
        supporting = fitting
    site = mapping.DILATION_SITES.get(code, '') if link.route == mapping.CATALOGUE_ROUTE else ''
    if site:  # R4 (D29): the site class of a site-specific dilation code
        fitting = [event for event in supporting if site_fit(reading, event, site) == FITS]
        if not fitting:
            return _site_hold(code, link, supporting, reading, name, site)
        supporting = fitting
    fitting = [event for event in supporting if defining_fit(reading, link, event)]
    if not fitting:  # D145 (D136): the code's defining target - 43240's drainage is of a pancreatic fluid collection
        return _target_hold(code, link, supporting, reading)
    supporting = fitting
    own_acts, doubts, bundled = [], [], []
    for event in supporting:  # R5: bundling (7.7)
        why = coverage.bundled_reason(reading, event)
        doubt = coverage.bundling_doubt(reading, event)
        if why:
            bundled.append((event, why))
        elif doubt is not None:
            doubts.append((event, doubt))
        else:
            own_acts.append(event)
    read = tuple(event['id'] for event in supporting)
    if not own_acts and doubts:
        event, relation = doubts[0]
        whole = reading.events.get(relation['statement'])
        act = event_label(reading, event)
        question = wording.bundling_question(relation['reason'], wording.event_kind_label(event['catalogue_kind']),
                                             statement_text(reading, event),
                                             statement_text(reading, whole) if whole else '')
        places = anchors(reading, event) + (anchors(reading, whole) if whole else [])
        return Evaluation(code, family, link, 'uncertain', BUNDLING_IDENTITY, wording.bundling_reason(act), read=read,
                          question=Question('act_target', question, wording.bundling_reason(act),
                                            (event['id'],) + ((whole['id'],) if whole else ()), _spans(places)),
                          relation=relation)
    if not own_acts:
        event, why = bundled[0]
        what = group_label(link, accounted(link))
        listed = '; '.join(event_label(reading, item) for item, _ in bundled[:4])
        detail, question = wording.act_included(name, 'performed', listed, why, what, statement_text(reading, event))
        return Evaluation(code, family, link, 'uncertain', BUNDLED, detail, read=read,
                          question=Question('performed_status', question, detail, (event['id'],),
                                            _spans(anchors(reading, event))),
                          bundled=tuple((item['id'], reason) for item, reason in bundled))
    held = another_role_hold(code, link, own_acts, reading, read, name, bundled)  # DECISIONS D124
    if held is not None:  # DECISIONS D168 (3): the ERCP rules' question about its own acts is the hold's second
        return ercp.role_second(held, own_acts, kept, reading)
    performed = [event for event in own_acts if value(event, 'status') == 'performed']
    labels = [event_label(reading, event) for event in own_acts[:4]]
    if not performed:  # an examination begun and not completed (7.3 line 2): its failure-marker words (R-4)
        words = words_of(own_acts[0], 'status')
        return Evaluation(code, family, link, 'incomplete', INCOMPLETE,
                          f'The {name} is documented as begun and not completed'
                          + (f': {wording.quote(words["text"])}.' if words else '.'),
                          supporting=tuple(event['id'] for event in own_acts), read=read,
                          incomplete_words=words['text'] if words else '',
                          bundled=tuple((item['id'], reason) for item, reason in bundled))
    if examination_code(link) and not link.acts:
        detail = f'The {name} is documented as performed on the date of service.'
    else:
        detail = f'The {name} is documented as performed with {"; ".join(labels)}.'
    return Evaluation(code, family, link, 'performed', SUPPORTED, detail,
                      supporting=tuple(event['id'] for event in own_acts), read=read,
                      bundled=tuple((item['id'], reason) for item, reason in bundled))


def recognised_only_hold(code: str, link: mapping.CodeLink, own: tuple) -> Evaluation:
    """DECISIONS D80 (the round-3 refutation, finding 19): a code on the catalogue route of a RECOGNISED-ONLY family
    (mapping.recognised_only: gi.sedation's 99152 and 99153) is not assessed by CPT Studio. Whatever the inventory
    states - a sedation Gemini reads as performed by the documenting team today, one of 8 minutes with no observer, on a
    3-year-old, or one stated not done - the code is held with the performed_status question
    (wording.performed_question, the question route (d)'s hold asks under C-6), quoting its own cited passages;
    never READY, and never excluded (only a member's answer or a reviewer's decision settles it). The service.status and
    events.match checks carry the detail: the service is recognised and listed for review, not assessed, and the
    catalogue's own list of what the family requires documented is named as not checked. It reads no event (``read``
    is empty) and accounts for none (E* is empty), as route (d)'s hold: the decision is the family's, not the
    document's."""
    needs = mapping.documentation(link.family)
    detail = (f'{wording.family_label(link.family)} is recognised by CPT Studio and listed for review, not assessed: no '
              f'service profile in this release reconciles {code} with the documented acts.'
              + (f' What it needs documented is not checked: {"; ".join(needs)}.' if needs else '')
              + ' Held for the reviewer, not excluded.')
    return Evaluation(code, link.family, link, 'uncertain', mapping.RECOGNISED_ONLY, detail,
                      question=Question('performed_status', wording.performed_question(code), detail, (), own))


# --- DECISIONS D124: an act documented only in another role's entry ---------------------------------------------------

ANOTHER_ROLE = 'another_role'  # Evaluation.reason of another_role_hold (the installed release's reason, engine.py:964)
# another_role_hold's own tables, read case-folded with straight apostrophes and single spaces (its fold): the forms of
# services.ROLE_HEADINGS and ROLE_LABEL (c2e53f8e), re-typed - the legacy reader is never called on the new path, and
# this module holds no pattern (tests.test_interpretation_assess.Imports). Per role, its NAMES (a label with its colon:
# "Nurse:", "RN:", "Pathology:", "Anesthesia:"), the names that head an entry alone on their line ("NURSING",
# "Pathology:"), and its ENTRY phrases, a name, a middle and an entry word ("Nursing note", "Nursing procedure record",
# "Pathology report", "Anesthesia record") or an entry form of no name ("Procedure checklist"). A name is a whole
# label: followed by no letter, digit or apostrophe. An entry phrase ends where no ASCII letter or digit joins it
# ("Nursing note's ..." holds the phrase, "Nursing notebook" does not: DECISIONS D139). That is services.ROLE_HEADINGS'
# \b but for '_', which \b counts as a word character under re.A: "Nursing note_x" heads an entry here and not there, a
# hold where the installed release is READY (a cost, DECISIONS D139 and D146).
# The nursing names cover services._NURSE (c2e53f8e) in full, generated longest first (DECISIONS D146): each optional
# lead - pre-procedure, intra-procedure and recovery as there, and D124's post-procedure - with each name, and 'lpn'
# (ROLE_LABEL's), so "Recovery nurse's note" is a nursing heading, as there.
_ROLE_NURSE = tuple(sorted({lead + nurse for lead in ('pre-procedure ', 'preprocedure ', 'intra-procedure ',
                                                      'intraprocedure ', 'post-procedure ', 'postprocedure ',
                                                      'recovery ', '')
                            for nurse in ('nursing', "nurse's", 'nurses', 'nurse', 'rn')} | {'lpn'},
                           key=lambda nurse: (-len(nurse), nurse)))
_ROLE_FORMS = (  # (role, names, heading names, entry names, entry middles, entry words, entry forms of no name): each
    # list longest first
    ('nursing', _ROLE_NURSE, _ROLE_NURSE, _ROLE_NURSE,
     ('pre-procedure ', 'intra-procedure ', 'post-procedure ', 'preprocedure ', 'intraprocedure ', 'postprocedure ',
      'procedure ', ''),
     ('documentation', 'assessment', 'flow sheet', 'flowsheet', 'checklist', 'comments', 'entries', 'records',
      'comment', 'handoff', 'summary', 'record', 'report', 'entry', 'notes', 'note'),
     ('procedure checklist',)),
    ('anesthesia', ('anaesthesiologist', 'anesthesiologist', 'anaesthetist', 'anesthetist', 'anaesthesia', 'anesthesia',
                    'crna'), ('anaesthesia', 'anesthesia'), ('anaesthesia', 'anesthesia', 'sedation'), ('',),
     ('record', 'report', 'note'), ()),
    ('pathology', ('surgical pathology', 'pathology'), ('surgical pathology', 'pathology'),
     ('surgical pathology', 'pathology'), ('',), ('addendum', 'results', 'result', 'report'), ()),
    ('radiology', (), (), ('radiology', 'imaging'), ('',), ('results', 'result', 'report'), ()),
)
# An entry phrase that opens its line heads an entry when at most this many characters follow it, whatever they are
# (services.ROLE_HEADINGS' [^\n]{0,60}$, c2e53f8e: "Pathology Report: Final", "Nursing note - recovery"): DECISIONS D139
_ROLE_HEADING_TAIL = 60
# A line its own author's label opens ("Endoscopist: ...", "Physician addendum: ...") is the physician's own line.
_ROLE_PHYSICIAN = (('performing physician', 'proceduralist', 'endoscopist', 'physician', 'attending', 'surgeon', 'md'),
                   (' attestation', ' statement', ' addendum', ' comment', ' note', ''))
_ROLE_LEAD = ' \t-*#>•·'  # what may open a line before its label: a bullet, a heading mark
_ROLE_DASHES = '-–—'
# What role_of trims from a line's ends: ASCII whitespace only, as services' patterns read a line under re.A (\s is
# [ \t\n\r\f\v]), so a line a no-break or other Unicode space opens or ends ("\xa0Findings") is no next heading,
# as it is no GENERIC_HEADING there (DECISIONS D146)
_ROLE_SPACE = ' \t\r\f\v'
# services.ROLE_SIGNATURE (c2e53f8e), re-typed (DECISIONS D146): read only in the label an act's passage, or its line,
# opens with, closed by a colon before the act's own words, and case-blind over ASCII letters only (re.A | re.I). Its
# words: (nursing) a record word, 'by' within 60 characters after it and a nurse word within 60 after 'by' and its
# space ("Documented by Jo Rowe, RN:"), or 'nursing', its space and an entry word ("Per nursing note:"); (anesthesia) an
# anesthetist word with a record word within 40 characters after it ("CRNA documented:"). No reach crosses a period or a
# line break ([^.\n]).
_ROLE_SIGNATURE = (('recorded', 'entered', 'documented', 'completed', 'charted'), ('rn', 'lpn', 'nurse'),
                   ('checklist', 'entry', 'note', 'handoff'), ('crna', 'anesthesiologist', 'anaesthetist'),
                   ('recorded', 'documented', 'charted'))
# The next heading, which ends an entry: services.GENERIC_HEADING's shape (c2e53f8e) - a line of at most 61 characters
# opening with a capital or a digit, of letters, digits and these marks only, at most a closing colon. No apostrophe:
# GENERIC_HEADING's [A-Za-z0-9 /&,()\-] allows none, so "Patient's vital signs stable throughout" ends no entry (D139)
_ROLE_HEADING_MARKS = frozenset(" /&,()-")


def another_role_hold(code: str, link: mapping.CodeLink, own_acts: Sequence, reading: Reading, read: tuple,
                      name: str, bundled: Sequence = ()) -> Optional[Evaluation]:
    """DECISIONS D124 (the round-4 parity audit, colon-sig gap 0; owner directive 2026-11-06, item 2: other-provider
    acts stay distinct from completed current services): a code the per-code rule would support is held, never READY,
    when every act it accounts for (its supporting events but the examination, which is the session: C-1) is documented
    only in another role's entry - a nursing note, an anesthesia record, a pathology report, a radiology report - as the
    installed release's engine._another_roles_hold holds it (c2e53f8e engine.py:948-973). None otherwise: an act with
    any statement passage outside such entries leaves the code as it is, and so does a code that accounts for no act (a
    base code, an examination-only EUS code: the installed release's match lists no act for them either).

    An act is told only in another role's entry when EVERY located place of its statement - its kind's and status's own
    passages, where the act itself is stated (OWN's target passages may be where the physician describes the LESION:
    "Findings: A 6 mm polyp in the sigmoid colon." beside "Nurse: The polyp was removed with a cold snare.") - lies in
    one: the passage begins with a role label (label_of: "Nurse:", "RN:", "Nursing note", "Pathology:", "Pathology
    report", "Anesthesia:", "Anesthesia record" and the like, as whole labels, after any characters that are not ASCII
    letters, digits or '_' ("– Nurse:", as services.ROLE_LABEL's ^\\W* reads it: DECISIONS D146) - never "Nursing
    staff:", "Pathology from jars 1-3 ...", "Anesthesia, equipment, and quality measures"); or, read from the document's
    lines, the line it stands on opens with such a label, or is a role's heading line (heading_of: an entry phrase
    opening its line and followed by at most 60 characters of anything, as services.ROLE_HEADINGS reads it - DECISIONS
    D139), or follows one with no heading between (heading_end: the next heading ends the entry, never the entry's own
    heading line; a blank line does not; a line is trimmed of ASCII whitespace only, so "\\xa0Findings" ends nothing:
    D146), and is no line the physician's own label opens (physician); or, when none of these places it in an entry,
    the label the passage or its line opens with, closed by a colon before the act's own words, holds another role's
    signature (signed: services.ROLE_SIGNATURE, "Documented by Jo Rowe, RN:", "Per nursing note:" - D146), on a line
    the physician's label opens too ("Endoscopist: see below. Documented by Jo Rowe, RN: ..."). The lines
    are ``reading.text``: the revision text the assessment receives (assess.assess hands it over); a reading without it
    (the review overlay's counted codes, a unit test's Reading) reads the passages' own labels and signatures only, and
    so is a place the text does not hold verbatim.

    This is no evidence binding (ADJUDICATION EB1): it reads none of Gemini's values and changes none - the act stays
    performed, current and the documenting team's - and it only ever turns a supported code into a hold, with ONE
    question (FINAL 7.4): performed_status, naming the entry and quoting the act's first passage in it, worded as the
    installed release words it. Never an exclusion, and the act stays the code's read event (coverage counts it as
    accounted for, as the installed release's held match keeps its acts). It matches no pattern (this module imports no
    re: tests.test_interpretation_assess.Imports): its labels are compared as case-folded strings."""
    acts = [event for event in own_acts if (event.get('catalogue_kind') or '') not in mapping.EXAMINATION_KINDS]
    if not acts:
        return None
    text = getattr(reading, 'text', None)
    text = text if isinstance(text, str) else None

    def fold(line: str) -> str:  # case folded, a curly apostrophe straight, single spaces, no leading bullet or mark
        return ' '.join(line.replace('’', "'").casefold().split()).lstrip(_ROLE_LEAD)

    def whole(rest: str) -> bool:  # what follows a name or a phrase: no letter, digit or apostrophe joins it
        return not rest or not (rest[0].isalnum() or rest[0] == "'")

    def phrase_end(rest: str) -> bool:  # what follows an entry phrase: no ASCII letter or digit joins it ("Nursing
        return not rest or not (rest[0].isascii() and rest[0].isalnum())  # note's"; D139; ROLE_HEADINGS' \b but '_')

    def unlead(line: str) -> str:  # from its first ASCII letter, digit or '_' (ROLE_LABEL's ^\W* under re.A: D146)
        for index, char in enumerate(line):
            if char.isascii() and (char.isalnum() or char == '_'):
                return line[index:]
        return ''

    def entry_rest(folded: str, form: tuple) -> Optional[str]:  # what follows the form's entry phrase folded opens with
        for entry_name in form[3]:
            if not folded.startswith(entry_name + ' '):
                continue
            rest = folded[len(entry_name) + 1:]
            for middle in form[4]:
                if not rest.startswith(middle):
                    continue
                tail = rest[len(middle):]
                for word in form[5]:
                    if tail.startswith(word) and phrase_end(tail[len(word):]):
                        return tail[len(word):]
        for phrase in form[6]:  # an entry form of no name ("Procedure checklist": DECISIONS D139)
            if folded.startswith(phrase) and phrase_end(folded[len(phrase):]):
                return folded[len(phrase):]
        return None

    def label_of(line: str) -> str:
        """The role whose label ``line`` (a passage, or a line) opens with - a name and its colon ("Nurse:", "RN:",
        "Pathology:"), or an entry phrase followed by its end, a colon, a bracket or a dash ("Nursing note: ...",
        "Pathology report (final): ...") - else ''. Read as fold reads it, and then from its first ASCII letter, digit
        or '_' (unlead): a label may follow any characters that are not these ("– Nurse:", "◦ Nurse:", "▪ Nurse:"), as
        services.ROLE_LABEL's ^\\W* reads it under re.A (DECISIONS D146); no label the first reading finds is
        lost."""
        for folded in dict.fromkeys((fold(line), fold(unlead(line)))):
            for form in _ROLE_FORMS:
                for label in form[1]:
                    if folded.startswith(label) and whole(folded[len(label):]) \
                            and folded[len(label):].lstrip().startswith(':'):
                        return form[0]
                rest = entry_rest(folded, form)
                if rest is not None and (not rest.strip() or rest.lstrip()[0] in ':(' + _ROLE_DASHES):
                    return form[0]
        return ''

    def heading_of(line: str) -> str:
        """The role whose entry heading ``line`` is: the whole line a heading name ("NURSING", "Nursing:",
        "Pathology:"); or an entry phrase opening it and followed by at most _ROLE_HEADING_TAIL characters of anything,
        as services.ROLE_HEADINGS reads it (DECISIONS D139: "Pathology Report: Final", "Nursing note - recovery",
        "NURSING NOTE (Jo Rowe, RN) 08:30", "Procedure checklist"), counted on the folded line, which holds no more
        characters than the line itself but for what case folding adds ("ß" is "ss"), so that is allowed; or
        followed by at most a bracketed note ("(Delphine Oakes, LPN)", "(final)"), a date or a time after a colon or a
        dash ("Nursing note: 10/14/2026 08:30") and a closing colon - else ''. A line opening with an entry phrase is
        therefore never read as the NEXT heading (heading_end): it is this entry's own heading, or it is longer than
        any heading of either kind."""
        folded = fold(line)
        grown = len(line.replace('’', "'").casefold()) - len(line)
        for form in _ROLE_FORMS:
            if any(folded.startswith(head) and folded[len(head):].strip() in ('', ':') for head in form[2]):
                return form[0]
            rest = entry_rest(folded, form)
            if rest is None:
                continue
            if len(rest) <= _ROLE_HEADING_TAIL + grown:  # DECISIONS D139
                return form[0]
            rest = rest.strip()
            if rest.startswith('('):
                close = rest.find(')')
                if close < 0 or close > 61 or '(' in rest[1:close]:
                    continue
                rest = rest[close + 1:].strip()
            if rest and rest[0] in ':' + _ROLE_DASHES:
                when = rest[1:].strip()
                for suffix in ('a.m.', 'p.m.', 'am', 'pm'):
                    if when.endswith(suffix) and when[:1].isdigit():
                        when = when[:-len(suffix)].strip()
                if not when or (when[0].isdigit() and all(char.isdigit() or char in '/.:- ' for char in when)):
                    rest = ''
            if rest in ('', ':'):
                return form[0]
        return ''

    def physician(line: str) -> bool:  # the line opens with the physician's own label ("Endoscopist:", ...)
        folded = fold(line)
        names, kinds = _ROLE_PHYSICIAN
        return any(folded.startswith(label + kind) and folded[len(label + kind):].lstrip().startswith(':')
                   for label in names for kind in kinds)

    def heading_end(line: str) -> bool:  # a heading of any kind (_ROLE_HEADING_MARKS), which ends the entry above it
        body = line.lstrip(' \t-*#')
        body = body[:-1] if body.endswith(':') else body
        return (2 <= len(body) <= 61 and body[0].isascii() and (body[0].isupper() or body[0].isdigit())
                and all((char.isascii() and char.isalnum()) or char in _ROLE_HEADING_MARKS for char in body))

    def sentence_end(source: str, start: int, end: int) -> int:
        """DECISIONS D165 (1): the index of the last sentence end in ``source[start:end]`` by the engine's own boundary -
        '.', '!' or '?' (ercp.SENTENCE_ENDS) followed by whitespace or by the end of ``source``, as ercp._sentences ends a
        sentence; never a word list - else -1."""
        while True:
            stop = max(source.rfind(mark, start, end) for mark in ercp.SENTENCE_ENDS)
            if stop < 0 or stop + 1 == len(source) or source[stop + 1].isspace():
                return stop
            end = stop

    def signed(source: str, at: int, begin: int) -> str:
        """The role whose signature (_ROLE_SIGNATURE: services.ROLE_SIGNATURE, c2e53f8e) stands in the label closed by
        a colon before ``at`` (the act's own words) - the text of ``source`` from the start of the line on which the
        act's passage begins (``begin``), not only of ``at``'s own line, up to its last colon before ``at``, as the
        installed release reads the sentence up to its last colon before the act, its line wraps kept ("Documented by
        Jo Rowe, RN: A 6 mm polyp ...", "Per nursing note: ...", and either one hard-wrapped before the act's own words:
        DECISIONS D152): anesthesia when both roles' signatures stand in it (the installed release's last match), else
        nursing, else ''. The reaches are ROLE_SIGNATURE's: its [^.\\n] ones - a record word within 60 characters before
        'by', a nurse word within 60 after 'by' and its space, an anesthetist word within 40 before a record word -
        cross no period and no line break, and the space after 'by' or 'nursing' (\\s+ under re.A) may hold a line break
        (D152). A signature anywhere else in the sentence names no role ("..., placed in formalin and documented by Jo
        Rowe, RN": DECISIONS D146).

        DECISIONS D158 (round 5f; colon4's K6): the label on ``at``'s own line is read first, as before D152 - the text
        of that line up to its last colon before ``at`` - and the role it names is the role; only where it names none
        is the label read from the line the passage begins on. So a role the act's own line names is never renamed by
        a label on a line above it: 'CRNA charted the sedation:' / 'Documented by Jo Rowe, RN: <the act>', cited as
        one passage, names the nursing entry, as the act's line and the installed release name it (its sentence begins
        after the line a colon ends), not anesthesia (both roles' signatures in one label). It decides no hold: a label
        that names a role on the act's line names one on the passage's lines too.

        DECISIONS D165 (round 5g; review:colon5 problems 2-4):
        (1) the label is read for the act's SENTENCE, not only from the line its passage begins on. A passage that begins
        mid-sentence - the text from the previous sentence end to the passage's start holds more than whitespace, by the
        engine's own sentence boundaries (ercp.SENTENCE_ENDS followed by whitespace, as ercp._sentences ends one; never a
        word list) - is read from the start of the line its sentence begins on, by the same rules (D152, D158). So a
        hard-wrapped sentence Gemini cites as one passage per line is read as the installed release reads it whole:
        'Documented by Jo Rowe, RN: Sigmoid colon, 30 cm: 10 mm sessile polyp, removed en bloc with a cold' / 'snare and
        retrieved (jar 3).', cited as two passages, names the nursing entry for the second as for the first. It only
        reads a longer label, so it never loses a role the passage's own lines name.
        (2) NOT INTEGRATED (round 5g integration; review:colon6 problem 0, critical): the physician's own label on the act's
        line was to be read as the act's role, a judged restoration of colon5's recorded cost. Its early return released
        holds both 05a881a75 and c2e53f8e keep: an act stated only on the signed line above, whose kind and status words
        stand on a physician-labelled field line. The cost stays recorded (a hold where c2e53f8e is READY).
        (3) the lines above the act's own are read one by one, the nearest first, and the first whose label names a role
        names it; only where none does is the whole label read (a signature whose \\s+ spans a line break). So 'CRNA
        charted the sedation:' / 'Documented by Jo Rowe, RN: A 6 mm ...' / 'was removed with a cold snare.' names the
        nursing entry, as the installed release does. It changes the entry named, never whether one is."""
        records, nurses, entries, anesthetists, charted = _ROLE_SIGNATURE

        def word(part: str, index: int) -> bool:  # an ASCII letter, digit or '_' at ``index`` (\w under re.A)
            return 0 <= index < len(part) and part[index].isascii() and (part[index].isalnum() or part[index] == '_')

        def standing(part: str, terms) -> list:  # (start, end) of each of ``terms`` standing whole in it (\b...\b)
            out = []
            for term in terms:
                index = part.find(term)
                while index >= 0:
                    if not word(part, index - 1) and not word(part, index + len(term)):
                        out.append((index, index + len(term)))
                    index = part.find(term, index + 1)
            return out

        space = _ROLE_SPACE + '\n'  # re.A's \s, a line break too: the label may now span lines (D152)

        def spaced(part: str, term: str) -> list:  # (start, end of its space) of each ``term`` a word starts, \s+ after
            out = []
            index = part.find(term)
            while index >= 0:
                end = index + len(term)
                if not word(part, index - 1) and end < len(part) and part[end] in space:
                    while end < len(part) and part[end] in space:
                        end += 1
                    out.append((index, end))
                index = part.find(term, index + 1)
            return out

        def read(head: str) -> str:  # the role the signature in ``head`` up to its last colon names, else ''
            colon = head.rfind(':')
            if colon < 0:
                return ''
            label = ''.join(chr(ord(char) + 32) if 'A' <= char <= 'Z' else char for char in head[:colon])  # re.A | re.I
            role = ''
            for part in label.split('.'):  # no reach crosses a period, nor ([^.\n]) a line break (D152)
                ended = {end for _, end in standing(part, records)}
                nurse_at = {start for start, _ in standing(part, nurses)}
                if any(any(end in ended and '\n' not in part[end:by]  # a record word within 60 before 'by'
                           for end in range(by - 60, by + 1))
                       and any(start in nurse_at and '\n' not in part[after:start]  # a nurse word within 60 after
                               for start in range(after, after + 61))
                       for by, after in spaced(part, 'by')) \
                        or any(part.startswith(entry, after) and not word(part, after + len(entry))
                               for _, after in spaced(part, 'nursing') for entry in entries):
                    role = 'nursing'
                anesthetist_end = {end for _, end in standing(part, anesthetists)}
                if any(any(end in anesthetist_end and '\n' not in part[end:start]
                           for end in range(start - 40, start + 1))
                       for start, _ in standing(part, charted)):
                    return 'anesthesia'
            return role

        def sentence_start(index: int) -> int:  # where the sentence ``index`` lies in begins (D165 (1))
            start = sentence_end(source, 0, index) + 1  # after the previous sentence end
            while start < index and source[start].isspace():
                start += 1
            return start  # ``index`` itself when only whitespace lies between: the passage begins its sentence

        own_line = source.rfind('\n', 0, at) + 1  # the act's own line, read first: its role is kept (D158)
        role = read(source[own_line:at])
        if role:
            return role
        first = source.rfind('\n', 0, min(begin, at)) + 1  # the line the passage begins on (D152)
        first = min(first, source.rfind('\n', 0, sentence_start(min(begin, at))) + 1)  # its sentence's (D165 (1))
        # every signature holds one of these words, so a line or a span above the act's line holding none of them names
        # no role: skipping it changes nothing (str.lower folds every ASCII letter read folds), only the work done
        anchors = records + anesthetists + ('nursing',)
        if not any(term in source[first:own_line].lower() for term in anchors):
            return ''
        stop = own_line - 1  # the line break that ends the line above the act's own
        while stop >= first:  # the nearest labelled line first (D165 (3))
            start = source.rfind('\n', 0, stop) + 1
            if any(term in source[start:stop].lower() for term in anchors):
                role = read(source[start:stop])
                if role:
                    return role
            stop = start - 1
        return read(source[first:at])  # a label spanning lines (\s+ after 'by': D152)

    def words_at(place: Mapping, event: Mapping) -> Optional[int]:
        """Where the act's own words begin in ``place``: the earliest of its kind's and status's words that begin in
        it, each read after the last colon inside them - words that open at a label ("Documented by Jo Rowe, RN: A 6 mm
        sessile polyp in the sigmoid colon was removed" as the status words) leave the label before that colon to
        signed, as the installed release reads the label before its own act mention (DECISIONS D152) - else None."""
        starts = []
        for record in (event.get('kind'), event.get('status')):
            words = record.get('words') if isinstance(record, Mapping) else None
            if isinstance(words, Mapping) and place['start'] <= words['start'] < place['end']:
                inner = str(words.get('text') or '').rfind(':')
                starts.append(words['start'] + inner + 1 if inner >= 0 else words['start'])
        return min(starts) if starts else None

    def words_later(place: Mapping, event: Mapping) -> Optional[int]:
        """DECISIONS D165 (1): where the act's own words begin after ``place`` (which holds none of them) in the
        sentence the place ends in - the earliest of its kind's and status's words that begin after the place, each read
        after the last colon inside them as words_at reads them, with no sentence end (sentence_end) from the place's
        last character to them - else None. So a wrapped sentence's label line, cited as a passage of its own, is read
        with the label of the sentence the act's words close ('Documented by Jo Rowe, RN: A 6 mm sessile polyp in the
        sigmoid colon' / 'was removed with a cold snare.', its kind's and status's words on the second line); read on the
        revision text only."""
        starts = []
        for record in (event.get('kind'), event.get('status')):
            words = record.get('words') if isinstance(record, Mapping) else None
            if isinstance(words, Mapping) and words['start'] >= place['end']:
                inner = str(words.get('text') or '').rfind(':')
                starts.append(words['start'] + inner + 1 if inner >= 0 else words['start'])
        if text is None or not starts:
            return None
        last = max(0, place['start'] + len(place['text'].rstrip()) - 1)  # the place's last character
        return min(starts) if sentence_end(text, last, min(starts)) < 0 else None

    def role_of(place: Mapping, event: Mapping) -> str:
        own = words_at(place, event)  # its kind's and status's words (the place's start where neither stands in it)
        role = label_of(place['text'])
        lead = len(place['text']) - len(place['text'].lstrip())  # where the passage's own text begins (D152)
        if role or text is None or text[place['start']:place['end']] != place['text']:
            return role or (signed(place['text'], own - place['start'], lead) if own is not None else '')
        at = place['start'] + lead

        def by_sentence() -> str:  # the label closed before the act's words (D146), else its sentence's (D165 (1))
            role = signed(text, at if own is None else own, at)
            later = words_later(place, event) if not role and own is None else None
            return signed(text, later, at) if later is not None else role

        start = text.rfind('\n', 0, at) + 1
        stop = text.find('\n', at)
        line = text[start:len(text) if stop < 0 else stop].strip(_ROLE_SPACE)  # ASCII whitespace only (D146)
        if physician(line):  # the physician's line - unless a signature label closes before the act's words (D146)
            return by_sentence()
        role = label_of(line) or heading_of(line)
        while not role and start > 0:  # the lines above, up to the nearest heading
            above_end = start - 1
            start = text.rfind('\n', 0, above_end) + 1
            above = text[start:above_end].strip(_ROLE_SPACE)
            if not above:
                continue
            role = heading_of(above)
            if not role and heading_end(above):
                break
        return role or by_sentence()  # no entry places it: its signature (D146)

    roles: set = set()
    shown: list = []
    for event in acts:
        places = sorted(reading.places(own_passages(event, ('kind', 'status'))),
                        key=lambda item: (item['start'], item['end']))
        if not places:
            return None
        found = [role_of(place, event) for place in places]
        if not all(found):
            return None
        roles.update(found)
        shown.extend(places)
    what = group_label(link, accounted(link))
    entry = wording.join(sorted(roles))
    passage = f' ({wording.quote(shown[0]["text"], 120)})' if shown else ''
    labels = [event_label(reading, event) for event in own_acts[:4]]
    detail = (f'The {name} is documented as performed with {"; ".join(labels)}. But the {what} it accounts for is '
              f'documented only in the {entry} entry{passage}, not by the physician performing the {name}. Held for '
              'the reviewer, not excluded.')
    question = (f'The {what} is documented only in the {entry} entry{passage}. Was it performed in this {name} on the '
                'date of service?')
    return Evaluation(code, link.family, link, 'uncertain', ANOTHER_ROLE, detail, read=read,
                      question=Question('performed_status', question, detail, tuple(event['id'] for event in acts),
                                        _spans(sorted(shown, key=lambda item: (item['start'], item['end'])))),
                      bundled=tuple((item['id'], why) for item, why in bundled))


def session_examination(event: Mapping, families) -> bool:
    """D31: whether ``event`` is the examination of a session of one of ``families`` as Gemini states it - an
    examination (or the EUS examination) of that family, stated performed or begun at this encounter. Its VALUES are
    read, not their states: the open question itself may leave them open. A digital examination is no session (FINAL
    5.6, E13)."""
    return (event.get('family') in families and event.get('catalogue_kind') in mapping.EXAMINATION_KINDS
            and value(event, 'status') in verify.POSITIVE and value(event, 'time') == 'current_encounter'
            and endoscopic_examination(event))


def session_doubt(reading: Reading, supporting: Sequence) -> Optional[tuple]:
    """D31: (the open question, the examination event it names) of the first of Gemini's open questions, in its order,
    that is about the performer, the time, the status or 'other' (SESSION_ABOUT) and names the examination of the
    session a supporting event belongs to (its family's); None when none does. A question about another attribute, or
    naming only acts, holds nothing here: it opens the attributes it names, as before."""
    families = frozenset(event.get('family') for event in supporting if event.get('family'))
    for question in reading.open_questions:
        if question.get('about') not in SESSION_ABOUT:
            continue
        for eid in question.get('events') or ():
            event = reading.events.get(eid)
            if event is not None and session_examination(event, families):
                return question, event
    return None


def _session_hold(code: str, link: mapping.CodeLink, supporting: Sequence, reading: Reading, question: Mapping,
                  examination: Mapping) -> Evaluation:
    """D31: the code is held with Gemini's own question about its session, asked of the session - who performed it,
    when, whether it was done, or (an unnamed doubt) whether it was done as documented - quoting the question's own
    passages (else the examination's own statement). Never excluded and never READY; the acts stay its reading."""
    about = question['about']
    service = service_label(examination.get('family', ''))
    places = reading.places(question.get('passages') or ()) or anchors(reading, examination)
    words = places[0]['text'] if places else statement_text(reading, examination)
    text, reason = wording.session_question(about, service, words)
    read = tuple(dict.fromkeys([examination['id']] + [event['id'] for event in supporting]))
    return Evaluation(code, link.family, link, 'uncertain', SESSION, reason, read=read,
                      question=Question(SESSION_ABOUT[about], text, reason, (examination['id'],), _spans(places)))


def _technique_hold(code: str, link: mapping.CodeLink, supporting: Sequence, reading: Reading, own: tuple,
                    name: str) -> Evaluation:
    """R4: no supporting act of the code's own technique. A verified device of another class is the "dilation of
    another technique" hold (reconcile.py:307-316; FINAL 7.4 h6) - never excluded; an absent or unverified device asks
    which technique was used."""
    required = wording.TECHNIQUE_WORDS.get(link.technique, link.technique)
    read = tuple(event['id'] for event in supporting)
    other = next((event for event in supporting if mapping.code_technique(event)), None)
    if other is not None:
        stated = wording.TECHNIQUE_WORDS.get(mapping.code_technique(other), 'dilation of another technique')
        words = statement_text(reading, other)
        detail, question = wording.another_technique(name, stated, required, words)
        return Evaluation(code, link.family, link, 'uncertain', ANOTHER_TECHNIQUE, detail, read=read,
                          question=Question('technique', question, detail, (other['id'],),
                                            _spans(anchors(reading, other))))
    event = supporting[0]
    act = event_label(reading, event)
    reason = wording.technique_reason(act, required)
    unverified = tuple((item['id'], 'technique') for item in supporting if not usable(item, 'technique')
                       and value(item, 'technique') != 'not_stated')
    return Evaluation(code, link.family, link, 'uncertain', TECHNIQUE, reason, read=read,
                      question=Question('technique', wording.technique_question(act, statement_text(reading, event)),
                                        reason, (event['id'],), _spans(anchors(reading, event))),
                      unverified=unverified)


# D29: how a dilation's verified places stand to a site class (mapping.SITE_CLASSES).
FITS, OUTSIDE, UNSETTLED = 'fits', 'outside', 'unsettled'


def site_places(reading: Reading, event: Mapping) -> tuple:
    """D29: the event's verified places - its target landmark when verified and placed (mapping.target_landmark; an
    anastomosis at the place the encounter's one anastomosis takes, DECISIONS D34: relations.Context.target_place), then
    the site of its verified lesion when that site is verified and placed - each once."""
    places = [reading.context.target_place(event)]
    lesion = identity.verified_lesion(event)
    site = (reading.lesions.get(lesion) or {}).get('site') if lesion else None
    if verify.usable(site) and site.get('value') not in lexicon.UNPLACED_LANDMARKS:
        places.append(site['value'])
    return tuple(dict.fromkeys(place for place in places if place))


def site_fit(reading: Reading, event: Mapping, site: str) -> str:
    """D29: FITS when a verified place of the event is in the site class and none is verified outside it; OUTSIDE when
    every verified place lies outside it and none is a surgically made place (whose position in the tract cannot be
    told, lexicon.ALTERED_LANDMARKS); UNSETTLED otherwise - no verified place, a surgically made one (an anastomosis
    D34 does not place), or places on both sides of the class."""
    landmarks = mapping.SITE_CLASSES[site]
    places = site_places(reading, event)
    inside = [place for place in places if place in landmarks]
    outside = [place for place in places if place not in landmarks and place not in lexicon.ALTERED_LANDMARKS]
    if inside and not outside:
        return FITS
    if outside and len(outside) == len(places):
        return OUTSIDE
    return UNSETTLED


def _site_hold(code: str, link: mapping.CodeLink, supporting: Sequence, reading: Reading, name: str,
               site: str) -> Evaluation:
    """R4 (D29): no supporting dilation is verified in the code's site class. One whose place is not settled asks which
    structure was dilated (act_target); with every one verified outside the class, the "dilation at another site" hold,
    in the "dilation of another technique" hold's form. Never excluded."""
    required = wording.SITE_WORDS[site]
    read = tuple(event['id'] for event in supporting)
    unsettled = next((event for event in supporting if site_fit(reading, event, site) == UNSETTLED), None)
    if unsettled is None:
        other = supporting[0]
        detail, question = wording.another_site(name, wording.landmark_label(site_places(reading, other)[0]), required,
                                                statement_text(reading, other))
        return Evaluation(code, link.family, link, 'uncertain', ANOTHER_SITE, detail, read=read,
                          question=Question('act_target', question, detail, (other['id'],),
                                            _spans(anchors(reading, other))))
    act = event_label(reading, unsettled)
    reason = wording.site_reason(act, required)
    unverified = tuple((item['id'], 'target') for item in supporting if not usable(item, 'target')
                       and value(item, 'target') != 'not_stated')
    return Evaluation(code, link.family, link, 'uncertain', SITE, reason, read=read,
                      question=Question('act_target', wording.target_question(act, statement_text(reading, unsettled)),
                                        reason, (unsettled['id'],), _spans(anchors(reading, unsettled))),
                      unverified=unverified)


def _target_hold(code: str, link: mapping.CodeLink, supporting: Sequence, reading: Reading) -> Evaluation:
    """DECISIONS D145 (the round-5c review of D136, problem 1, high): no supporting act meets the code's defining target
    (defining_fit: D120's requirement, 43240's drainage of a pancreatic fluid collection). Called in evaluate after R3
    and R4, as D29's _site_hold is - the code is held, never READY and never excluded - with the TARGET question (fact
    'target') of one such act: the first whose target is not verified (reason SITE: CPT Studio could not confirm which
    structure it was done on), else the first (ANOTHER_SITE: its target verified, and no pancreatic fluid collection).
    The question quotes the act's own sentence - the sentence of its own passages that holds its target words,
    else its kind or its status words (ercp.statement_sentence) - and its reason says what the code describes and where
    the document places the act, never that it was not confirmed as done: R3 verified it performed. As D136 built it the
    drainage supported nothing, so 'EUS-guided transmural drainage of the gallbladder was performed from the duodenal bulb
    with a 15 mm lumen-apposing metal stent.' took 7.4's last resort ('Was the drainage (stent) at the gallbladder (“was
    performed”) done on the date of service?', whose reason said CPT Studio could not confirm it was done), and beside
    an EUS examination whose own target is verified 43240 asked no target at all; the installed release asks its
    target. Asked whatever the examination's target.

    DECISIONS D156 (2) (round 5e; the round-5d review of D145, problem 0): before the hold, 7.4's reading (_focused) over
    the positive candidates - _without_support's: stated positive or uncertain, neither verified at another time nor by
    another performer - that do not support the code but DO meet its defining target is kept: its question, its reason,
    its relation, its unverified attributes and its 52/53 consideration (attempted) are the code's, and the hold's
    target question is asked beside it - after it, in the code's one question (an Evaluation asks one). Its facts are
    7.4's. The code reads what the hold reads (its supporting acts), so coverage lists and asks what it did. With D145's
    hold alone, 'EUS-guided transmural drainage of the pseudocyst was attempted but failed.' beside 'EUS-guided
    transmural drainage of the common bile duct was performed ...' (43240 cited on either) asked only which structure
    the bile duct drainage was done on: the failed pseudocyst drainage, which e5628be56 asked about ('... was begun and
    not completed. Confirm whether 43240 describes what was done on the date of service.') with the 52/53
    consideration, was in no question of the assessment. Never a release: the code stays held.

    DECISIONS D161 (round 5f; the round-5e review of D156, problems 0-2): the two are TWO questions. 7.4's is the code's
    question - its own fact, words and reason, its passages as 7.4 gave them (D143's STATEMENT and LEAD marks kept,
    never re-spanned), then the hold's events and passages after its own, so the code names and shows what D156's one
    question did - and the hold's target question is the evaluation's ``second``, which assess asks as its own
    clarification (fact 'target'). D156 asked both in one question of 7.4's fact: where R6 asks no structure examined
    (the EUS examination's own target given as the landmark it was advanced to, 'stomach'), 4f82e5056's target question
    was only words inside a performed_status question, and a member's (code, family, fact) row for it was gone; and the
    re-spanned passages lost D143's marks, so the statement_scope row about two denials showed one of them. 7.4 reads
    the candidates that meet the defining target, and - with none in any group - those whose target is not usable
    (unverified, unlocated or absent): 'EUS-guided transmural drainage of the pseudocyst was attempted but failed.'
    whose target words 'the pseudocyst' Gemini tied to no lesion (unverified, landmark_missing) met neither, so beside
    the bile duct's drainage it was in no question and had no 52/53 consideration, where e5628be56 and the installed
    release ask about it. Never beside a candidate that meets the target: one question (7.4's first rule that applies)
    would then name the other act - 'Later, EUS-guided transmural drainage of the pseudocyst was performed ...' (its
    target tied to no lesion) read beside the failed drainage of the verified pseudocyst asks the first one's time and
    drops the failed one's performed_status and its 52/53 consideration. A candidate whose target is verified elsewhere
    (a gallbladder's) is still not read: 43240 cannot describe it. Never a release."""
    read = tuple(event['id'] for event in supporting)
    unsettled = next((event for event in supporting if not usable(event, 'target')), None)
    event = unsettled if unsettled is not None else supporting[0]
    places = site_places(reading, event) if unsettled is None else ()
    sentence = next((found for found in (ercp.statement_sentence(reading, event, name)
                                         for name in ('target', 'kind', 'status')) if found is not None), None)
    words = sentence['text'] if sentence is not None else statement_text(reading, event)
    reason, question = wording.defining_target_hold(code, wording.event_kind_label(event.get('catalogue_kind') or ''),
                                                    wording.landmark_label(places[0]) if places else '', words)
    unverified = tuple((item['id'], 'target') for item in supporting if not usable(item, 'target')
                       and value(item, 'target') != 'not_stated')
    target = Question('target', question, reason, (event['id'],), _spans(anchors(reading, event)))

    def positive(group):  # _without_support's positive candidates (repeated in place) that do not support the code
        return [item for item in reading.events.values() if is_candidate(link, group, item)
                and value(item, 'status') in verify.POSITIVE + ('uncertain',) and not verified_other_time(item)
                and not verified_other_performer(item) and not supports(reading, link, group, item)]

    # D156 (2): 7.4 over those that meet the defining target; D161 (2): with none in any group, those whose target
    # is not usable - never beside one that meets it, whose question 7.4's one question would then displace
    for reads in (lambda item: defining_fit(reading, link, item), lambda item: not usable(item, 'target')):
        for group in requirements(link):
            fitting = [item for item in positive(group) if reads(item)]
            if fitting:
                break
        else:
            continue
        kept = _focused(code, link, group, fitting, reading)
        first = kept.question
        shown = {(span['start'], span['end']) for span in first.passages}  # D161 (3): 7.4's passages as they are
        asked = Question(first.fact, first.question, first.reason, tuple(dict.fromkeys(first.events + target.events)),
                         tuple(first.passages) + tuple(span for span in target.passages
                                                       if (span['start'], span['end']) not in shown))
        return Evaluation(code, link.family, link, 'uncertain', kept.reason, f'{first.reason} {target.reason}',
                          read=read, question=asked, relation=kept.relation, attempted=kept.attempted,
                          unverified=tuple(dict.fromkeys(kept.unverified + unverified)),
                          second=target)  # D161 (1): the hold's target question, its own clarification
    return Evaluation(code, link.family, link, 'uncertain', SITE if unsettled is not None else ANOTHER_SITE, reason,
                      read=read, question=target, unverified=unverified)


# --- 7.4-7.6: no supporting event --------------------------------------------------------------------------------------

def _without_support(code: str, link: mapping.CodeLink, group: Sequence[str], kept: Sequence, own: tuple,
                     reading: Reading) -> Evaluation:
    """7.4-7.6 for a code no event supports. DECISIONS D157 (round 5f): an act of the code's kind IN DOUBT
    (_kind_in_doubt: a bleeding control in doubt, no candidate of any code) never lets a denial the code cites alone
    exclude it (_exclusion, D157 (2)); and the code held not documented beside it names that act as the act its
    question is about (Question.events, support['question_events']; its fact, words, reason and passages unchanged),
    so coverage.in_doubt_questions passes the act's (family, fact) service slot to an act in doubt no code's question
    names (D157 (3)): "At that time, cautery was applied to the ulcer base." (in doubt) before "At that time, biopsies
    of the gastric antrum were taken with cold forceps." with 43255 asks the biopsy's "done at this encounter?", whose
    answer decides the missing 43239, as f9013e12e and e5628be56 ask it."""
    candidates = [event for event in reading.events.values() if is_candidate(link, group, event)]
    positive = [event for event in candidates if value(event, 'status') in verify.POSITIVE + ('uncertain',)
                and not verified_other_time(event) and not verified_other_performer(event)]
    if positive:
        return _focused(code, link, group, positive, reading)
    in_doubt = _kind_in_doubt(reading, link, group)  # D157
    decided = _exclusion(code, link, group, candidates, kept, reading, in_doubt)
    if decided is not None:
        return decided
    act = group_label(link, group)
    reason = wording.not_documented_reason(act)
    return Evaluation(code, link.family, link, 'uncertain', NOT_DOCUMENTED, reason,
                      read=tuple(event['id'] for event in candidates),
                      question=Question('performed_status', wording.performed_question(code), reason,
                                        tuple(event['id'] for event in in_doubt), own))  # D157 (3): the act it is about


def _focused(code: str, link: mapping.CodeLink, group: Sequence[str], positive: Sequence, reading: Reading
             ) -> Evaluation:
    """7.4: the first rule that applies (h1-h5, in order), over the positive candidates in document order, decides the
    ONE question; its passages are that candidate's own (both sides of a relation for h1-h3).

    DECISIONS D143 (4), per D89 (a doubt never takes another doubt's question): a doubt h2 finds never displaces the
    same-event contradictions h3 asks of the act it doubts - the one question then asks them and the doubt together
    (_h3_beside_doubt)."""
    read = tuple(event['id'] for event in positive)
    for rule in (_h1_contradiction, _h2_doubt, _h3_unresolved, _h4_unverified, _h4_attempted, _h5_method):
        for event in positive:
            found = rule(code, link, event, reading)
            if found is not None and rule is _h2_doubt:  # D143 (4): the denial is asked beside the doubt
                found = _h3_beside_doubt(code, event, reading, found, positive) or found
            if found is not None:
                return Evaluation(code, link.family, link, 'uncertain', found['reason'], found['question'].reason,
                                  read=read, question=found['question'], relation=found.get('relation'),
                                  attempted=found.get('attempted', False),
                                  unverified=tuple(found.get('unverified', ())))
    event = positive[0]
    act = event_label(reading, event)
    reason = wording.status_reason(act)
    return Evaluation(code, link.family, link, 'uncertain', UNVERIFIED, reason, read=read,
                      question=Question('performed_status', wording.status_question(act, statement_text(reading, event)),
                                        reason, (event['id'],), _spans(anchors(reading, event))))


def _relation_question(reading: Reading, relation: Mapping, event: Mapping) -> dict:
    statement = reading.events.get(relation['statement']) or {}
    places = reading.places(relation.get('passages') or ()) or (anchors(reading, statement) + anchors(reading, event))
    return {'events': tuple(dict.fromkeys((event['id'], relation['statement']))), 'passages': _spans(places),
            'statement': statement}


def _h1_contradiction(code, link, event, reading):
    for relation in reading.relations_of(event['id'], (relations.CONTRADICTION,)):
        found = _relation_question(reading, relation, event)
        act = wording.event_kind_label(event['catalogue_kind'])
        reason = wording.conflict_reason(act, statement_text(reading, event), statement_text(reading, found['statement']))
        return {'reason': CONFLICT, 'relation': relation,
                'question': Question(f'conflict:{event["catalogue_kind"] or value(event, "kind")}',
                                     wording.conflict_question(act), reason, found['events'], found['passages'])}
    return None


def _h2_doubt(code, link, event, reading):
    for relation in reading.relations_of(event['id'], (relations.DOUBT,)):
        found = _relation_question(reading, relation, event)
        act = event_label(reading, event)
        words = statement_text(reading, found['statement'])
        return {'reason': DOUBT, 'relation': relation,
                'question': Question('performed_status', wording.doubt_question(act, statement_text(reading, event)),
                                     wording.doubt_reason(act, words), found['events'], found['passages'])}
    if value(event, 'status') == 'uncertain':
        act = event_label(reading, event)
        words = statement_text(reading, event)
        return {'reason': DOUBT,
                'question': Question('performed_status', wording.doubt_question(act, words),
                                     wording.doubt_reason(act, words), (event['id'],),
                                     _spans(anchors(reading, event)))}
    return None


# relations.ATTRIBUTES -> the fact a question about it names (FINAL 7.4 h3)
RELATION_FACTS = {'time': 'event_time', 'performer': 'event_performer', 'target': 'act_target',
                  'technique': 'technique', 'scope': 'statement_scope', 'status': 'performed_status',
                  'procedure': 'procedure', 'kind': 'performed_status', 'part_of': 'performed_status'}


# DECISIONS D102: the attributes on which an UNRESOLVED relation from a denial asks the contradiction only while the
# ACT's own value of that attribute is usable - the unknown side is then the statement's own (its family or session, its
# time, its performer, its device)
_H3_STATEMENT_SIDE = ('procedure', 'time', 'performer', 'technique')


def _h3_denial(statement: Mapping) -> bool:
    """DECISIONS D86: a statement whose status is not_performed, in any state, or whose own status words hold a negator
    (verify's negation_marker literal)."""
    status = statement.get('status')
    negating = isinstance(status, Mapping) and bool((status.get('literals') or {}).get('negators'))
    return value(statement, 'status') == 'not_performed' or negating


def _h3_asks_contradiction(reading: Reading, relation: Mapping, event: Mapping) -> bool:
    """Whether an UNRESOLVED relation of the positive ``event`` is, for a code, a same-event contradiction - asked as
    whether its statement applies to the act (statement_scope): its statement is a denial (D86), and it rests on the
    target (D86 as D91 narrows it, whichever side is unknown), on the scope (whether the statement concerns the act at
    all, which FINAL 7.4 h3 already asks as statement_scope), or (DECISIONS D102) on the procedure, the time, the
    performer or the technique while the act's OWN value of that attribute is usable - the unknown side is then the
    statement's, and the act's own attribute question would ask what is verified, with a reason that is not true. A
    relation whose act side is the unusable one keeps that attribute's question (D91), and a status, kind or part_of
    relation keeps performed_status (D91).

    DECISIONS D143 (2) withdraws D126 (4), which on the technique had asked the contradiction only while the
    STATEMENT's own device was not usable: the act's device usable asks it whatever the statement's own device, as
    d353e64df did. "No cold snare was used for the 6 mm sessile polyp." beside "A 6 mm sessile polyp in the sigmoid
    colon was removed with a snare." asks whether that denial applies to the snare removal (statement_scope), never
    only which technique was used: the installed release asks conflict:snare there, and against that expectation a
    technique question alone is a dropped question (score_fresh.verdict's adjudication reads statement_scope as the
    contradiction). The technique question is not asked beside it: the code has one question (FINAL 7.4)."""
    statement = reading.events.get(relation['statement']) or {}
    if not _h3_denial(statement):
        return False
    attribute = relation['attribute']
    if attribute in ('target', 'scope'):
        return True
    return attribute in _H3_STATEMENT_SIDE and usable(event, attribute)


# DECISIONS D126 (0): the precedence of an act's same-event contradictions, in the one question of its code
_H3_SAME_SITE, _H3_TARGET, _H3_OTHER = 0, 1, 2


def _h3_rank(reading: Reading, relation: Mapping, event: Mapping) -> int:
    """DECISIONS D126 (0): where a same-event contradiction stands among the act's several. _H3_SAME_SITE: the act's
    SAME-SITE denial - the pairing table's own target row (relations.target_row) reads the statement as the act's own
    target (its place contains every place of the act's, it names the act's verified lesion, or it covers every act of
    its kind in the act's session), and what is unknown is its own procedure, time, performer, device or kind (D102):
    "During withdrawal, no polypectomy was performed in the sigmoid colon." beside the sigmoid snare. _H3_TARGET: a
    TARGET denial (D86) - whether its place or lesion is the act's is the unknown: "No polypectomy was performed in the
    prior segment.". _H3_OTHER: any other - a scope the statement leaves unresolved, a session the table cannot resolve,
    a denial whose own site is unknown as well."""
    if relation['attribute'] == 'target':
        return _H3_TARGET
    row = relations.target_row(reading.context, reading.events.get(relation['statement']) or {}, event)
    return _H3_SAME_SITE if (row.attribute, row.result) == ('target', relations.SAME) else _H3_OTHER


# DECISIONS D126 (1): two places of one statement at most this many characters apart are one sentence across a hard
# wrap (the line break between them: "\n", or "\r\n"); further apart, the quote marks what it leaves out ("…")
_H3_WRAP = 2


def _h3_place(reading: Reading, statement: Mapping, name: str) -> Optional[dict]:
    """The place, among the statement's own passages of attribute ``name`` and then all its others, that holds that
    attribute's own words; None when they are not located."""
    record = statement.get(name)
    words = record.get('words') if isinstance(record, Mapping) else None
    if not isinstance(words, Mapping):
        return None
    for place in reading.places(record.get('passages') or ()) + reading.places(all_passages(statement)):
        if place['start'] <= words['start'] and words['end'] <= place['end']:
            return place
    return None


def _h3_unlocated(reading: Reading, statement: Mapping, name: str) -> list:
    """DECISIONS D143 (3): the located places of the attribute's own passages when Gemini gave its words and they do
    not locate in them (its reasons hold words_unlocated) - no place holds the words, so the statement is quoted with
    those passages whole; [] otherwise."""
    record = statement.get(name)
    if not isinstance(record, Mapping) or isinstance(record.get('words'), Mapping) \
            or 'words_unlocated' not in (record.get('reasons') or ()):
        return []
    return reading.places(record.get('passages') or ())


def _h3_quoted(reading: Reading, statement: Mapping) -> list:
    """The places a statement_scope question quotes of ``statement`` (_h3_whole_statement): the place holding its
    status words (else its status's first located passage), then - each once, in document order - the places holding
    its target's and its scope's words (D126 (1)) and its scope's own passages when Gemini's scope words do not locate
    (D143 (3), _h3_unlocated). [] without a status place. DECISIONS D143 (1): the status place first - the lead a
    question about several statements shows the statement by (_h3_shown)."""
    status = statement.get('status') if isinstance(statement.get('status'), Mapping) else {}
    own = reading.places(status.get('passages') or ())
    first = _h3_place(reading, statement, 'status') or (own[0] if own else None)
    if first is None:
        return []
    places = {(place['start'], place['end']): place
              for place in (first, _h3_place(reading, statement, 'target'), _h3_place(reading, statement, 'scope'),
                            *_h3_unlocated(reading, statement, 'scope'))
              if place is not None}
    lead = (first['start'], first['end'])
    return [places[lead]] + [places[key] for key in sorted(places) if key != lead]


def _h3_whole_statement(reading: Reading, statement: Mapping) -> str:
    """DECISIONS D103: what a statement_scope question quotes - the statement whole, never its status words alone: the
    text of the place, among its own passages (its status's first), that holds its status words - the sentence, clause
    or line Gemini cited, as the document words it. Without located status words: the first located place of its
    status's passages, else statement_text.

    DECISIONS D126 (1): and the places that hold its target's and its scope's own words with it - the whole SENTENCE
    across a hard wrap, never one wrapped line: "No biopsy, snare resection, ablation, or balloon dilation was performed
    on" / "this splenic-flexure lesion during the present encounter." (FRESH-2 C2MEM-023 r1) is quoted as the one
    sentence, which says what the statement is about. Each place once, in document order: a place within another adds
    nothing, one overlapping or touching another adds the rest of its text, one a line break away (_H3_WRAP) follows
    after a space, one further away after an ellipsis.

    DECISIONS D143 (3): a scope whose words do not locate adds its own passages whole (_h3_unlocated), so the sentence
    is quoted across the wrap there too: FRESH-1 C2MEM-031 r3's E17 ("... they were not taken from any" / its next
    line), whose scope words Gemini gave are in neither line, is quoted as its two scope passages joined, never the
    status words' one line."""
    quoted = _h3_quoted(reading, statement)
    if not quoted:
        return statement_text(reading, statement)
    places = {(place['start'], place['end']): place for place in quoted}
    text, end = '', None
    for start, stop in sorted(places):
        place = places[(start, stop)]
        if end is None:
            text, end = place['text'], stop
        elif stop <= end:
            continue
        elif start <= end:
            text, end = text + place['text'][end - start:], stop
        else:
            text, end = text + (' ' if start - end <= _H3_WRAP else ' … ') + place['text'], stop
    return text


def _h3_contradictions(reading: Reading, event: Mapping) -> list:
    """DECISIONS D101, D126 (0): the act's same-event contradictions among its UNRESOLVED relations
    (_h3_asks_contradiction), in the stated precedence (_h3_rank: a stable sort keeps the stored order); [] with
    none."""
    found = [item for item in reading.relations_of(event['id'], (relations.UNRESOLVED,))
             if _h3_asks_contradiction(reading, item, event)]
    return sorted(found, key=lambda item: _h3_rank(reading, item, event)) if len(found) > 1 else found


# DECISIONS D143 (1): a relation's statement side (relations._passages: the statement's status, kind, scope and target
# passages), whose places a question about several statements names by their statement
_H3_STATEMENT_OWN = ('status', 'kind', 'scope', 'target')


def _h3_shown(reading: Reading, found: Sequence, event: Mapping) -> tuple:
    """DECISIONS D143 (1): the passages of a question about SEVERAL statements - every one's, in the question's order
    (each relation's, both sides), each once, exactly as before - with every place of a statement's own passages
    naming that statement (questions.STATEMENT; a place two statements share is named by the first), and the place
    the question quotes it by, its status place (_h3_quoted), marked as its lead (questions.LEAD); so is the act's
    (``event``'s) place holding its status words, else its kind words. The statement_scope question's member row reads
    them (validation.questions.passages): one passage of each statement - its lead - then the act's, before a second
    passage of any. The installed release's row shows every statement of a conflict; PER_SOURCE (2) alone had shown
    the first two passages here, so a third statement (finding 3's prior-segment denial beside the framed and device
    denials) or the second statement beside a hard-wrapped first one (S2w over two lines) was in the question and not
    in the row. The order is unchanged, so every other question of the code, whose row reads the source as before,
    shows what it showed."""
    from studio.validation import questions  # the key the member's row reads (a field only the new path sets)
    act_lead = _h3_place(reading, event, 'status') or _h3_place(reading, event, 'kind')
    act_key = (act_lead['start'], act_lead['end']) if act_lead is not None else None
    out, seen = [], set()
    for item in found:
        statement = item['statement']
        own = {(place['start'], place['end'])
               for place in reading.places(own_passages(statement, _H3_STATEMENT_OWN))}
        lead = {(place['start'], place['end']) for place in _h3_quoted(reading, statement)[:1]}
        for span in item['passages']:
            key = (span['start'], span['end'])
            if key in seen:
                continue
            seen.add(key)
            entry = {'start': span['start'], 'end': span['end'], 'text': span['text']}
            if key in own and statement.get('id'):
                entry[questions.STATEMENT] = statement['id']
                if key in lead:
                    entry[questions.LEAD] = True
            elif key == act_key:
                entry[questions.LEAD] = True
            out.append(entry)
    return tuple(out)


def _h3_contradiction_question(reading: Reading, event: Mapping, chosen: Sequence,
                               doubt: Optional[Mapping] = None) -> dict:
    """The code's one statement_scope question over the act's same-event contradictions ``chosen``, in their
    precedence (D126 (0)) - and, DECISIONS D143 (4), the DOUBT relation ``doubt`` h2 found on the act, after them:
    whether any of their statements applies to the act, each quoted whole (D103, D126 (1)) and once; its events and
    passages every one's, in that order (a question about several statements names each passage's statement:
    _h3_shown). The relation recorded is the first contradiction."""
    found = [_relation_question(reading, item, event) for item in chosen]
    if doubt is not None:
        found.append(_relation_question(reading, doubt, event))
    act = event_label(reading, event)
    words = statement_text(reading, event)
    said = list(dict.fromkeys(_h3_whole_statement(reading, item['statement']) for item in found))
    question = wording.scope_question(said[0], act, words, whole=True, also=said[1:])
    reason = wording.scope_reason(said[0], act, whole=True, also=said[1:])
    asked = tuple(dict.fromkeys(eid for item in found for eid in item['events']))
    shown = (_h3_shown(reading, found, event) if len(found) > 1
             else _spans(span for item in found for span in item['passages']))
    return {'reason': UNRESOLVED, 'relation': chosen[0],
            'question': Question('statement_scope', question, reason, asked, shown)}


def _h3_beside_doubt(code: str, event: Mapping, reading: Reading, doubt: Mapping, positive: Sequence
                     ) -> Optional[dict]:
    """DECISIONS D143 (4), per D89 (a doubt never takes another doubt's question): the doubt h2 found never displaces
    the same-event contradictions (_h3_contradictions) of the act it doubts. The doubt is ``doubt``, h2's finding on
    ``event``: a DOUBT relation of the act ``event``, or - the doubting statement listed before the act, itself a
    positive candidate - ``event``'s own uncertain status, whose DOUBT relations name the acts it doubts (among
    ``positive``, in their order). With any contradiction of such an act, the code's one question asks them, in their
    precedence, and the doubt's statement after them (statement_scope, which the scoring adjudication reads as asking a
    contradiction and a performed_status alike) - None otherwise (h2's question stands), or with no code
    (focus_question reads h1-h3 directly).

    The input: an undated note's 'On 11/09/2026, a 6 mm sessile polyp in the sigmoid colon was removed with a cold
    snare.' (its day a pending check), 'Impression: No polypectomy was performed.' (D128 stores UNRESOLVED(time)) and
    'It is unclear whether the sigmoid polyp was removed completely.' (DOUBT), the member's date 2026-11-09: h2 had
    asked performed_status quoting the doubt alone, and the denial was shown nowhere; the installed release asks
    conflict:snare (its conflicts check warns), and the document dated 11/09/2026 asks conflict:snare (h1).

    DECISIONS D150 (1): in BOTH branches the acts read are every positive act the doubting statement doubts - its
    DOUBT relations (the statement of the relation h2 found, else ``event`` itself) whose act is among ``positive`` -
    h2's own act first, then the others in ``positive``'s order. D143 read only the act h2 met when h2 found a DOUBT
    relation, so a doubt of two removals displaced the denial of the other: the undated note's 'A 6 mm sessile polyp
    in the sigmoid colon was removed with a cold snare.', 'On 11/09/2026, a 4 mm sessile polyp in the rectum was
    removed with a cold snare.', 'No polypectomy of the rectal polyp was performed.' (UNRESOLVED(time) beside the
    rectal snare) and 'It is unclear whether any polyp was removed.' (DOUBT of both removals), the member's date
    2026-11-09: with the doubting event listed after the removals, h2 met the sigmoid removal's DOUBT first and asked
    performed_status about it, and the rectal denial was asked and shown nowhere; with it listed first, the rectal
    denial was asked beside the doubt. The installed release asks conflict:snare in both orders. Now both orders ask
    whether the rectal denial or the doubt applies to the rectal snare."""
    if not code:
        return None
    relation = doubt.get('relation')
    doubting = relation['statement'] if relation is not None else event['id']  # D150 (1): one reading, both branches
    order = {item['id']: index for index, item in enumerate(positive)}
    doubted = sorted(((reading.events[item['event']], item) for item in reading.by_statement.get(doubting, ())
                      if item['type'] == relations.DOUBT and item['event'] in order),
                     key=lambda pair: (pair[0]['id'] != event['id'], order[pair[0]['id']]))
    for act, item in doubted:
        contradictions = _h3_contradictions(reading, act)
        if contradictions:
            return _h3_contradiction_question(reading, act, contradictions, doubt=item)
    return None


def _h3_unresolved(code, link, event, reading):
    """FINAL 7.4 h3: the candidate is the positive side of an UNRESOLVED relation, which asks the fact of the attribute
    it rests on (RELATION_FACTS) - unless, for a code, the relation is a same-event contradiction
    (_h3_asks_contradiction): its statement is a DENIAL (DECISIONS D86: a statement whose status is not_performed, in
    any state, or whose own status words hold a negator) that may be of the act - on its target (D86, as D91 narrows
    it), on its scope, or on an attribute whose unknown side is the statement's own (D102: the act's own procedure,
    time, performer or technique is usable). The document then states the act done and states a denial that may be of
    it, and the code's one question is that contradiction: whether the statement applies to the act (statement_scope,
    naming both). "No polypectomy was performed in the prior segment." beside a verified sigmoid snare had asked which
    lesion the snare was done on (C1CL3-001), and "without submucosal injection" beside "Lift: submucosal injection x2."
    which site the injection was done on; "During withdrawal, no polypectomy was performed in the sigmoid colon." (its
    own time unanchored) asked when the snare, verified as today's, was done (D102).

    DECISIONS D101: EVERY UNRESOLVED relation of the act is read, not only the first stored: when any of them is a
    same-event contradiction, that is the code's question, whatever order the relations were stored in. A framed
    earlier denial or a denial of another device listed before C1CL3-001's prior-segment denial had asked the snare's
    own time or technique, and the prior-segment sentence was shown nowhere. With no contradiction, the first relation
    stored asks its attribute's fact, as before.

    DECISIONS D126 (0), which replaces D101's "the first resting on the target, else the first stored": the code's ONE
    question (FINAL 7.4) asks EVERY same-event contradiction of the act, in a stated precedence (_h3_rank, stable over
    the stored order): the act's same-site denials first, then the target denials, then the others - whether any of
    their statements applies to the act. Its events and passages are every one's, in that order, so none is hidden and
    none is dropped. D101's target-first rule asked "No polypectomy was performed in the prior segment." beside the
    sigmoid snare and showed "During withdrawal, no polypectomy was performed in the sigmoid colon." nowhere, in either
    sentence order; the installed release asks conflict:snare in both. One contradiction asks as before.

    DECISIONS D103: a statement_scope question and its reason quote the statement WHOLE (_h3_whole_statement: the
    passage its status words are stated in; D126 (1): with its target's and scope's, across a hard wrap), never only its
    status words, so a statement about other findings reads as what it says ("... small internal hemorrhoids were
    incidental findings and required no therapy.", never "required no therapy"). D126 (3): a DENIAL's statement - D103
    is about denials; a statement_scope question whose statement is no denial (a doubt's unresolved scope, on either
    arm) keeps D86's wording: statement_text, cut as before.

    A doubt, a planned act a claim names and a positive event (a claim that two acts are one) keep their attribute's
    question. So does focus_question's service-scope question about an event no code depends on (FINAL 7.8; ``code``
    ''), which reads the first relation stored: coverage.in_doubt_questions asks one question per family and fact, so
    moving that question to statement_scope dropped it where the family's codes ask statement_scope (FRESH-2 C2MEM-031
    r1: the balloon dilation's "done at this encounter?"). Only the question changes: the code is held as before, never
    READY and never excluded.

    DECISIONS D143: the contradictions' question is _h3_contradiction_question's (a question about several
    statements names each passage's statement, (1)); (2) the technique arm is d353e64df's again
    (_h3_asks_contradiction); (3) a scope whose words do not locate is quoted by its own passages
    (_h3_whole_statement); (4) h2's doubt never displaces the contradictions of the act it doubts (_focused,
    _h3_beside_doubt)."""
    unresolved = reading.relations_of(event['id'], (relations.UNRESOLVED,))
    if not unresolved:
        return None
    # D101: every relation of the act is read; a same-event contradiction (D86/D91/D102) is the question - D126 (0):
    # every one, in the stated precedence
    contradictions = _h3_contradictions(reading, event) if code else []
    if contradictions:
        return _h3_contradiction_question(reading, event, contradictions)
    relation = unresolved[0]
    fact = RELATION_FACTS.get(relation['attribute'], 'performed_status')
    found = _relation_question(reading, relation, event)
    act = event_label(reading, event)
    words = statement_text(reading, event)
    if fact == 'statement_scope' and _h3_denial(found['statement']):  # D103: a denial, quoted whole
        said = _h3_whole_statement(reading, found['statement'])
        question = wording.scope_question(said, act, words, whole=True)
        reason = wording.scope_reason(said, act, whole=True)
    elif fact == 'statement_scope':  # D126 (3): no denial - D86's wording
        said = statement_text(reading, found['statement'])
        question, reason = wording.scope_question(said, act, words), wording.scope_reason(said, act)
    else:
        question, reason = _attribute_question(fact, act, words)
    return {'reason': UNRESOLVED, 'relation': relation,
            'question': Question(fact, question, reason, found['events'], _spans(found['passages']))}


def _attribute_question(fact: str, act: str, words: str) -> tuple:
    if fact == 'event_time':
        return wording.time_question(act, words), wording.time_reason(act)
    if fact == 'event_performer':
        return wording.performer_question(act, words), wording.performer_reason(act)
    if fact == 'procedure':
        return wording.procedure_question(act, words), wording.procedure_reason(act)
    if fact == 'act_target':
        return wording.target_question(act, words), wording.target_reason(act)
    if fact == 'technique':
        return wording.technique_question(act, words), wording.technique_unresolved_reason(act)
    return wording.status_question(act, words), wording.status_reason(act)


# 7.3 lines 1-3, in order: the attribute an unusable value of which decides h4, and the fact it names.
LINE_FACTS = (('procedure', 'procedure'), ('kind', 'performed_status'), ('status', 'performed_status'),
              ('time', 'event_time'), ('performer', 'event_performer'))


def _h4_unverified(code, link, event, reading):
    for name, fact in LINE_FACTS:
        if name == 'procedure' and link.route != mapping.CATALOGUE_ROUTE:
            continue
        if usable(event, name):
            continue
        act = event_label(reading, event)
        question, reason = _attribute_question(fact, act, statement_text(reading, event))
        return {'reason': UNVERIFIED, 'unverified': ((event['id'], name),),
                'question': Question(fact, question, reason, (event['id'],), _spans(anchors(reading, event)))}
    return None


def _h4_attempted(code, link, event, reading):
    """C-9: for a code that does not account for the examination, an act begun and not completed is a hold, with the
    52/53 consideration - never an exclusion and never support."""
    if value(event, 'status') != 'attempted_not_completed' or examination_code(link):
        return None
    act = event_label(reading, event)
    words = statement_text(reading, event)
    return {'reason': ATTEMPTED, 'attempted': True,
            'question': Question('performed_status', wording.attempted_question(code, act),
                                 wording.attempted_reason(act, words), (event['id'],), _spans(anchors(reading, event)))}


def _h5_method(code, link, event, reading):
    if (event.get('catalogue_kind') or '') not in mapping.UMBRELLAS:
        return None
    lesion = identity.verified_lesion(event)
    what = lesion_words(reading, lesion) if lesion else ''
    if not what:
        place = wording.landmark_label(mapping.target_landmark(event))
        what = f'lesion at the {place}' if place else 'lesion'
    act = group_label(link, accounted(link))
    reason = wording.method_reason(act)
    return {'reason': METHOD,
            'question': Question('act_method', wording.method_question(what), reason, (event['id'],),
                                 _spans(anchors(reading, event)))}


def focus_question(reading: Reading, event: Mapping) -> Optional[Question]:
    """The 7.4 question about one event no code depends on (FINAL 7.8: an in_doubt item's service-scope question):
    h1-h3 and h5 over the event, else h4 over its own statement's attributes; None when nothing in it is in doubt."""
    link = mapping.CodeLink(code='', route=mapping.CATALOGUE_ROUTE, family=event.get('family', ''),
                            kinds=(event.get('catalogue_kind') or '',))
    for rule in (_h1_contradiction, _h2_doubt, _h3_unresolved, _h4_unverified, _h5_method):
        found = rule('', link, event, reading)
        if found is not None:
            return found['question']
    return None


# --- 7.5: exclusion ------------------------------------------------------------------------------------------------------

def concerns(link: mapping.CodeLink, group: Sequence[str], event: Mapping) -> bool:
    """7.5 (1): the statement's kind is in the group or an umbrella covering it, its kind usable, and its family the
    code's, usable (route (a)); on route (b), a statement of the group's kind at the code's regions."""
    if not usable(event, 'kind'):
        return False
    if link.route == mapping.UNRECONCILED_ROUTE:
        return is_candidate(link, group, event)
    return (event.get('family') == link.family and usable(event, 'procedure')
            and any(mapping.covers(event.get('catalogue_kind') or '', wanted) for wanted in group))


def deciding(event: Mapping) -> tuple:
    """7.5 (2): (attribute, value, basis) of the statement's deciding attribute, the first of status, time and performer
    with a deterministic basis (verify.exclusion_basis); ('', '', '') when none. An act begun and not completed never
    decides an exclusion (C-9). DECISIONS D169 (1) (round 5g, narrowing only; refute6 families finding[0]): the TIME
    basis is read with the one currency rule, facts.day_of (_off_the_date) - an act whose time it does not place OFF the
    date of service is never excluded for its time, so one rule has one answer. "Earlier today, I performed a flexible
    sigmoidoscopy to 40 cm, ..." (earlier_encounter worded "Earlier today", verified by its marker) was ON for the E/M of
    the same assessment (separate_em: "Flexible sigmoidoscopy is documented as performed on the same date") while 45330
    was EXCLUDED "at an earlier encounter, not on the date of service"; now the time decides nothing and the code is held
    (7.6, not documented) - never excluded, as c2e53f8e never excludes it (READY there for "Earlier today", held for
    "Earlier in the day" and "Earlier this morning"). Status and performer bases are read as before: another clinician's
    titled name still excludes."""
    for name in ('status', 'time', 'performer'):
        basis = verify.exclusion_basis(name, event.get(name))
        if not basis:
            continue
        if name == 'status' and value(event, 'status') == 'attempted_not_completed':
            continue
        if name == 'time' and not _off_the_date(event):  # D169 (1): never excluded for a time placed ON the date
            continue
        return name, value(event, name), basis
    return '', '', ''


def _off_the_date(event: Mapping) -> bool:
    """DECISIONS D169 (1): whether facts.day_of places ``event`` OFF the date of service - the time basis deciding reads.
    Read with no effective date: a time that has an exclusion basis is a usable earlier_encounter or future time, which
    day_of places ON only by its own words (a same-day word, a frame, D162's frame anywhere, D169 (2)'s clock time and
    this date's words) - never by a date literal, since a usable earlier or future time's literals all compare unequal to
    the date it was judged against (verify.time_words: otherwise date_mismatch, so unusable) and day_of reads no frame
    beside a literal - so the answer is the effective date's (assess judges every time against it, verify.rejudged), and
    the E/M's day (combination.procedure_day) gives the same. Imported here because facts imports nothing of events."""
    from studio.interpretation import facts

    return facts.day_of(event, None) == facts.OFF


def broad(reading: Reading, event: Mapping) -> bool:
    """A broad statement: a current denial of every act of its kind in its own session (C-8). As ADJUDICATION C-7
    decides it, it covers no code its kept spans do not cite: uncited, it is asked about (statement_scope)."""
    return (usable(event, 'status') and value(event, 'status') == 'not_performed'
            and usable(event, 'scope') and value(event, 'scope') == 'all_of_kind'
            and usable(event, 'time') and value(event, 'time') == 'current_encounter'
            and event.get('family') not in reading.context.unresolved_sessions)


def _overlaps(one: Mapping, two: Mapping) -> bool:
    return one['start'] < two['end'] and two['start'] < one['end']


def within_words(span: Mapping, words: Sequence[Mapping]) -> bool:
    """C-10: whether every word of ``span`` (each letter or digit) lies inside one of ``words``' spans."""
    for offset, char in enumerate(span['text']):
        if not char.isalnum():
            continue
        position = span['start'] + offset
        if not any(item['start'] <= position < item['end'] for item in words):
            return False
    return True


def coverage_of(reading: Reading, event: Mapping, kept: Sequence[Mapping]) -> str:
    """7.5 (3) as ADJUDICATION C-7 and C-10 amend it: whether the statement covers the code its kept spans cite.
    - 'citation': a kept span overlaps the statement's own passages and EVERY kept span lies within the union of its own
      attribute words (COVERING: kind, status, time, target) - the code is cited for that statement and for nothing
      else (C-10);
    - 'partial', the statement_scope question: a kept span overlaps its passages but some kept span - that one or
      another - reaches words no word of it covers (C-10: the code may cite an act Gemini omitted); or the statement is
      a BROAD one (a current denial of every act of its kind) that no kept span overlaps (C-7: a broad statement has no
      cover of its own);
    - '': no kept span overlaps it, and it is no broad statement: the code was not cited for it (7.6)."""
    places = reading.places(all_passages(event))
    if not any(_overlaps(span, place) for span in kept for place in places):
        return 'partial' if broad(reading, event) else ''
    words = [event[name]['words'] for name in COVERING
             if isinstance(event.get(name), Mapping) and isinstance(event[name].get('words'), Mapping)]
    return 'citation' if all(within_words(span, words) for span in kept) else 'partial'


def _doubted(reading: Reading, link: mapping.CodeLink, group: Sequence[str], candidates: Sequence) -> bool:
    """7.5 (4): an uncertain candidate, or a DOUBT relation on a candidate or from a statement of the group's kinds."""
    if any(value(event, 'status') == 'uncertain' for event in candidates):
        return True
    ids = {event['id'] for event in candidates}
    for relation in reading.relations:
        if relation['type'] != relations.DOUBT:
            continue
        statement = reading.events.get(relation['statement']) or {}
        if relation['event'] in ids or any(mapping.covers(statement.get('catalogue_kind') or '', wanted)
                                           for wanted in group):
            return True
    return False


def _kind_in_doubt(reading: Reading, link: mapping.CodeLink, group: Sequence[str]) -> list:
    """DECISIONS D157 (2): the acts of the code's kind IN DOUBT in the encounter that are no candidate of it - each
    bleeding control in doubt (mapping.POSSIBLE_BLEEDING_CONTROL: D115's clip or injection, D142's bleeding_control
    kind, whose own words state no bleeding) stated here (positive or uncertain, verified neither at another time nor by
    another performer) that, read as the bleeding control it may be, is a candidate of the group (is_candidate: of the
    code's family); in the reading's order. Structural - the act's catalogue kind against the code's link - never its
    words. Such an act matches no code (D115), so a candidate reading never sees it; read as an absence it lets a denial
    decide the code."""
    return [event for event in reading.events.values()
            if event.get('catalogue_kind') == mapping.POSSIBLE_BLEEDING_CONTROL
            and value(event, 'status') in verify.POSITIVE + ('uncertain',)
            and not verified_other_time(event) and not verified_other_performer(event)
            and is_candidate(link, group, {**event, 'catalogue_kind': mapping.BLEEDING_CONTROL})]


def _exclusion(code: str, link: mapping.CodeLink, group: Sequence[str], candidates: Sequence, kept: Sequence,
               reading: Reading, in_doubt: Sequence = ()) -> Optional[Evaluation]:
    """7.5. DECISIONS D157 (2) (round 5f; D154's class (iv), and the round-5e review of D154, problem 2): while an act
    of the code's kind is IN DOUBT in the encounter (``in_doubt``: _kind_in_doubt), a denial of the kind the code cites
    alone (cover 'citation') never excludes it - a doubt is never a fact (D87), so it cannot be outweighed into "not
    done". The code is held with the question 7.4 asks of the acts in doubt as of its candidates (_focused's h1-h5:
    the same-event contradiction naming the act and the denial, the act's unverified time ...), which is the question
    f9013e12e asked where D149's key read the act as a control done; when none of h1-h5 applies (_focused's last resort,
    reason UNVERIFIED with nothing unverified), with the statement_scope question on that denial, as on a partial
    cover, naming the denial and the acts in doubt. "A 12 mm clean-based ulcer was seen in the gastric antrum." /
    "Cautery was applied to the ulcer base." (in doubt, D142) / "No other bleeding control was required." with 43255
    citing only the denial was excluded on e5628be56 (f9013e12e held it statement_scope; c2e53f8e holds it
    performed_status); so was D115's "Two hemostatic clips were placed across the ulcer." with the same denial on every
    new-path head. Either way the decision reads the denial alone (``read``), so the acts in doubt stay listed in doubt
    (reconcile lists no act a code reads). A denial with no act of the kind in doubt beside it decides as before."""
    if _doubted(reading, link, group, candidates):
        return None
    places = _kept_places(kept)
    partial = cited = None
    act = group_label(link, group)
    for event in reading.events.values():
        if not concerns(link, group, event) or value(event, 'scope') == 'exceptive':  # C-7: never excludes
            continue
        name, decided, basis = deciding(event)
        if not basis:
            continue
        cover = coverage_of(reading, event, places)
        if cover == 'citation' and in_doubt:  # D157 (2): beside an act of the kind in doubt, asked - never decided
            cited = cited or event
            continue
        if cover == 'citation':
            words = (event[name].get('words') if isinstance(event.get(name), Mapping) else None) \
                or words_of(event, 'status', 'kind')
            text = words['text'] if words else statement_text(reading, event)
            reason = wording.exclusion_reason(act, name, decided, text)
            return Evaluation(code, link.family, link, 'not_performed', EXCLUDED, reason, read=(event['id'],),
                              exclusion=Exclusion(event['id'], name, decided, basis, words, reason, cover))
        if cover == 'partial' and partial is None:
            partial = event
    if cited is not None:  # D157 (2): never decided. Read stays the denial's alone, as on a partial cover - an act a
        # code reads is never listed in doubt (reconcile) - so the acts in doubt stay listed
        found = _focused(code, link, group, in_doubt, reading)  # 7.4 over the acts in doubt, as over candidates
        if found.reason != UNVERIFIED or found.unverified:  # h1-h5 asks of one (not the last resort): f9013e12e's
            return Evaluation(code, link.family, link, 'uncertain', found.reason, found.detail, read=(cited['id'],),
                              question=found.question, relation=found.relation, attempted=found.attempted,
                              unverified=found.unverified)
        statement = statement_text(reading, cited)  # else the statement_scope question on the cited denial
        reason = wording.scope_reason(statement, act)
        ids = (cited['id'],) + tuple(item['id'] for item in in_doubt)
        shown = anchors(reading, cited) + [place for item in in_doubt for place in anchors(reading, item)]
        return Evaluation(code, link.family, link, 'uncertain', STATEMENT_SCOPE, reason, read=(cited['id'],),
                          question=Question('statement_scope', wording.scope_question(statement, act), reason, ids,
                                            _spans(shown + list(places))))
    if partial is None:
        return None
    statement = statement_text(reading, partial)
    reason = wording.scope_reason(statement, act)
    return Evaluation(code, link.family, link, 'uncertain', STATEMENT_SCOPE, reason, read=(partial['id'],),
                      question=Question('statement_scope', wording.scope_question(statement, act), reason,
                                        (partial['id'],), _spans(anchors(reading, partial) + list(places))))


# --- support (FINAL 7.11, contract 9.3) ----------------------------------------------------------------------------------

def support_spans(reading: Reading, evaluation: Evaluation, kept: Sequence) -> dict:
    """How the code's kept spans relate to E*'s own passages, by offset overlap only (contract 9.3): 'pass' when one
    overlaps them, 'warn' when none does (CPT Studio's own located passages are then shown), 'not_applicable' for a code
    with no supporting event. ``supporting`` and ``unrelated`` are indices into ``kept``; ``source`` E*'s own passage
    spans. It never decides a status."""
    events = [reading.events[eid] for eid in evaluation.supporting if eid in reading.events]
    source = []
    for event in events:
        source.extend(anchors(reading, event))
    source = list(_spans(sorted(source, key=lambda item: (item['start'], item['end']))))
    supporting, unrelated = [], []
    for index, span in enumerate(kept):
        place = {'start': span.start, 'end': span.end}
        (supporting if any(_overlaps(place, item) for item in source) else unrelated).append(index)
    if not events:
        return {'status': 'not_applicable', 'supporting': [], 'unrelated': list(range(len(kept))), 'source': [],
                'detail': 'Not checked: no documented event supports this code.'}
    what = wording.join(list(dict.fromkeys(event_label(reading, event) for event in events[:3])))
    if supporting and not unrelated:
        detail, status = f'Every cited passage shows the {what}.', 'pass'
    elif supporting:
        detail, status = (f'{len(supporting)} of {len(kept)} cited passages show the {what}; {len(unrelated)} cite '
                          'text that does not.'), 'pass'
    elif source:
        detail, status = (f'None of the cited passages shows the {what}; CPT Studio shows the passages that do: '
                          + '; '.join(wording.quote(item['text'], 120) for item in source[:2]) + '.'), 'warn'
    else:
        detail, status = f'No passage shows the {what}.', 'fail'
    return {'status': status, 'supporting': supporting, 'unrelated': unrelated, 'source': source[:4], 'detail': detail}


def basis_of(reading: Reading, evaluation: Evaluation) -> list:
    """The fingerprint's events (FINAL 7.11): (id, its usable attributes' values, their words' texts) of every event the
    decision read, in document order."""
    out = []
    for eid in sorted(set(evaluation.supporting) | set(evaluation.read), key=lambda item: reading.order.get(item, 0)):
        event = reading.events.get(eid)
        if event is None:
            continue
        values = {name: event[name]['value'] for name in ATTRIBUTES
                  if isinstance(event.get(name), Mapping) and verify.usable(event[name])}
        texts = sorted({event[name]['words']['text'] for name in ATTRIBUTES if isinstance(event.get(name), Mapping)
                        and isinstance(event[name].get('words'), Mapping)})
        out.append([eid, values, texts])
    return out
