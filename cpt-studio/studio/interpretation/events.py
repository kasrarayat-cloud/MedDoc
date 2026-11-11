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


def supports(reading: Reading, link: mapping.CodeLink, group: Sequence[str], event: Mapping) -> bool:
    """7.3 lines 1-4, 6 and 7 (line 5, the device class, is R4's)."""
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
    events); ``unverified``: the (event, attribute) pairs a decision read and found unusable."""
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


# --- 7.4-7.6: no supporting event --------------------------------------------------------------------------------------

def _without_support(code: str, link: mapping.CodeLink, group: Sequence[str], kept: Sequence, own: tuple,
                     reading: Reading) -> Evaluation:
    candidates = [event for event in reading.events.values() if is_candidate(link, group, event)]
    positive = [event for event in candidates if value(event, 'status') in verify.POSITIVE + ('uncertain',)
                and not verified_other_time(event) and not verified_other_performer(event)]
    if positive:
        return _focused(code, link, group, positive, reading)
    decided = _exclusion(code, link, group, candidates, kept, reading)
    if decided is not None:
        return decided
    act = group_label(link, group)
    reason = wording.not_documented_reason(act)
    return Evaluation(code, link.family, link, 'uncertain', NOT_DOCUMENTED, reason,
                      read=tuple(event['id'] for event in candidates),
                      question=Question('performed_status', wording.performed_question(code), reason, (), own))


def _focused(code: str, link: mapping.CodeLink, group: Sequence[str], positive: Sequence, reading: Reading
             ) -> Evaluation:
    """7.4: the first rule that applies (h1-h5, in order), over the positive candidates in document order, decides the
    ONE question; its passages are that candidate's own (both sides of a relation for h1-h3)."""
    read = tuple(event['id'] for event in positive)
    for rule in (_h1_contradiction, _h2_doubt, _h3_unresolved, _h4_unverified, _h4_attempted, _h5_method):
        for event in positive:
            found = rule(code, link, event, reading)
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

    DECISIONS D126 (4): on the technique, only while the STATEMENT's own device is not usable. Both devices verified
    and still UNKNOWN to the pairing table - the act's device wider than the statement's ("removed with a snare" beside
    "No cold snare was used for the 6 mm sessile polyp."), or both 'other' - is no doubt on the statement's side: the
    doubt is which device the act used, and the relation keeps its technique question (C-16)."""
    statement = reading.events.get(relation['statement']) or {}
    if not _h3_denial(statement):
        return False
    attribute = relation['attribute']
    if attribute in ('target', 'scope'):
        return True
    if attribute not in _H3_STATEMENT_SIDE or not usable(event, attribute):
        return False
    return attribute != 'technique' or not usable(statement, 'technique')


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
    after a space, one further away after an ellipsis."""
    status = statement.get('status') if isinstance(statement.get('status'), Mapping) else {}
    own = reading.places(status.get('passages') or ())
    first = _h3_place(reading, statement, 'status') or (own[0] if own else None)
    if first is None:
        return statement_text(reading, statement)
    places = {(place['start'], place['end']): place
              for place in (first, _h3_place(reading, statement, 'target'), _h3_place(reading, statement, 'scope'))
              if place is not None}
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
    READY and never excluded."""
    unresolved = reading.relations_of(event['id'], (relations.UNRESOLVED,))
    if not unresolved:
        return None
    chosen, fact = [unresolved[0]], ''
    if code:  # D101: every relation of the act is read; a same-event contradiction (D86/D91/D102) is the question
        contradictions = [item for item in unresolved if _h3_asks_contradiction(reading, item, event)]
        if contradictions:  # D126 (0): every one, in the stated precedence (a stable sort keeps the stored order)
            chosen = (sorted(contradictions, key=lambda item: _h3_rank(reading, item, event))
                      if len(contradictions) > 1 else contradictions)
            fact = 'statement_scope'
    relation = chosen[0]
    fact = fact or RELATION_FACTS.get(relation['attribute'], 'performed_status')
    found = [_relation_question(reading, item, event) for item in chosen]
    act = event_label(reading, event)
    words = statement_text(reading, event)
    if fact == 'statement_scope' and _h3_denial(found[0]['statement']):  # D103, D126: the denials, each quoted whole
        said = list(dict.fromkeys(_h3_whole_statement(reading, item['statement']) for item in found))
        question = wording.scope_question(said[0], act, words, whole=True, also=said[1:])
        reason = wording.scope_reason(said[0], act, whole=True, also=said[1:])
    elif fact == 'statement_scope':  # D126 (3): no denial - D86's wording
        said = statement_text(reading, found[0]['statement'])
        question, reason = wording.scope_question(said, act, words), wording.scope_reason(said, act)
    else:
        question, reason = _attribute_question(fact, act, words)
    asked = tuple(dict.fromkeys(eid for item in found for eid in item['events']))
    shown = _spans(span for item in found for span in item['passages'])
    return {'reason': UNRESOLVED, 'relation': relation, 'question': Question(fact, question, reason, asked, shown)}


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
    decides an exclusion (C-9)."""
    for name in ('status', 'time', 'performer'):
        basis = verify.exclusion_basis(name, event.get(name))
        if not basis:
            continue
        if name == 'status' and value(event, 'status') == 'attempted_not_completed':
            continue
        return name, value(event, name), basis
    return '', '', ''


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


def _exclusion(code: str, link: mapping.CodeLink, group: Sequence[str], candidates: Sequence, kept: Sequence,
               reading: Reading) -> Optional[Evaluation]:
    if _doubted(reading, link, group, candidates):
        return None
    places = _kept_places(kept)
    partial = None
    act = group_label(link, group)
    for event in reading.events.values():
        if not concerns(link, group, event) or value(event, 'scope') == 'exceptive':  # C-7: never excludes
            continue
        name, decided, basis = deciding(event)
        if not basis:
            continue
        cover = coverage_of(reading, event, places)
        if cover == 'citation':
            words = (event[name].get('words') if isinstance(event.get(name), Mapping) else None) \
                or words_of(event, 'status', 'kind')
            text = words['text'] if words else statement_text(reading, event)
            reason = wording.exclusion_reason(act, name, decided, text)
            return Evaluation(code, link.family, link, 'not_performed', EXCLUDED, reason, read=(event['id'],),
                              exclusion=Exclusion(event['id'], name, decided, basis, words, reason, cover))
        if cover == 'partial' and partial is None:
            partial = event
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
