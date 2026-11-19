"""The builder's notation for constructed pass-1 answers (docs/gemini-migration/FINAL-V2.md 1.4's exact shape; step 6c of
8.1, 9.5). TEXT-ONLY and SYNTHETIC: a ``Note`` is one fixture document, segmented by contract/segment.py exactly as the
pipeline segments it, so every unit id a constructed answer cites is the unit that holds the cited words. Nothing here
decides anything: it writes JSON that extract_read reads, the checks check and pass 2 is asked about.

A fact is written ``(value, words)`` - cited at the unit holding ``words`` - or ``(value, words, link)``; a bare value is
cited at the event's own anchor unit with no located words. Every helper returns plain dicts in 1.4's LOCAL form."""
from __future__ import annotations

import copy
from typing import Any

from studio.interpretation.contract import segment

DOS = '2031-03-14'
DOS_LINE = 'Date of service: 03/14/2031'
CLINICIAN = 'Corvin Ashdale'


class Note:
    """One fixture document: its text, its units, and the citation helpers over them."""

    def __init__(self, text: str, dos: str = DOS, dos_line: str = DOS_LINE, dos_words: str = '03/14/2031',
                 clinician: str = CLINICIAN, frame_words: str = '') -> None:
        self.text = text
        self.units = segment.units(text)
        self.dos, self.dos_line, self.dos_words, self.clinician = dos, dos_line, dos_words, clinician
        self.frame_words = frame_words

    def frame_unit(self) -> str:
        """The unit that frames the document's owner and team (1.5's document frame): the documenting clinician's
        line, or - for a document that names no clinician (``clinician=''``) - the unit holding ``frame_words``, by
        default the date line: G1's ``document_frame`` admits only the units the encounter's facts cite."""
        return self.u(self.clinician or self.frame_words or self.dos_line)

    # --- units ---------------------------------------------------------------------------------------------------------

    def at(self, words: str, nth: int = 0) -> tuple[int, int]:
        """The offsets of the ``nth`` occurrence of ``words`` in the text (ValueError when it is not there)."""
        start = -1
        for _ in range(nth + 1):
            start = self.text.find(words, start + 1)
            if start < 0:
                raise ValueError(f'{words!r} (occurrence {nth}) is not in the note')
        return start, start + len(words)

    def u(self, words: str, nth: int = 0) -> str:
        """The id of the unit that holds the ``nth`` occurrence of ``words`` (ValueError when no single unit holds
        it)."""
        start, end = self.at(words, nth)
        for unit in self.units:
            if unit.start <= start and end <= unit.end:
                return unit.id
        raise ValueError(f'no single unit holds {words!r}')

    def unit(self, uid: str) -> Any:
        return next(unit for unit in self.units if unit.id == uid)

    def near(self, words: str, anchor: str) -> str:
        """The unit to cite ``words`` at for an object anchored on ``anchor``: the anchor itself when it holds them,
        else the unit holding their first occurrence."""
        unit = self.unit(anchor)
        if self.text.find(words, unit.start, unit.end) >= 0:
            return anchor
        return self.u(words)

    # --- sources and facts -----------------------------------------------------------------------------------------------

    def src(self, words: str, link: str = 'statement', nth: int = 0, cite: str = '') -> dict:
        """A source citing the unit that holds ``words`` (or the unit holding ``cite`` with ``words`` located in it)."""
        return {'units': [self.u(cite or words, nth)], 'words': words, 'link': link}

    def whole(self, uid: str, link: str = 'statement') -> dict:
        """A source citing one unit with no located words."""
        return {'units': [uid], 'words': '', 'link': link}

    def fact(self, value: str, *sources: dict, state: str = 'supported', qualifiers: tuple = (),
             options: tuple = ()) -> dict:
        return {'state': state, 'value': value, 'qualifiers': list(qualifiers), 'sources': list(sources),
                'options': [dict(option) for option in options]}

    def put(self, spec: Any, anchor: str, link: str = 'statement') -> dict:
        """A fact from the notation: a dict is taken as written; ``(value, words[, link[, state]])`` cites the unit
        holding ``words``; a bare string cites ``anchor`` with no located words."""
        if isinstance(spec, dict):
            return spec
        if isinstance(spec, str):
            return self.fact(spec, self.whole(anchor, link))
        value, words, *rest = spec
        the_link = rest[0] if rest else link
        uid = self.near(words, anchor)
        if not rest and the_link == 'statement' and uid != anchor:
            the_link = 'other_statement'  # 1.3: another statement about the same object (G1: its units exist)
        state = rest[1] if len(rest) > 1 else 'supported'
        return self.fact(value, {'units': [uid], 'words': words, 'link': the_link}, state=state)

    def slot(self, spec: Any, anchor: str, link: str = 'statement') -> list:
        """A SLOT: [] for None, else one fact."""
        return [] if spec is None else [self.put(spec, anchor, link)]

    def many(self, specs: Any, anchor: str) -> list:
        return [self.put(spec, anchor) for spec in (specs or ())]

    # --- the encounter, people, sections ---------------------------------------------------------------------------------

    def people(self, role_words: str = 'Endoscopist', name: str = '', extra: tuple = ()) -> list:
        out = [{'id': 'P1', 'name': self.src(name or self.clinician),
                'role': self.fact('documenting_clinician', self.src(role_words, cite=name or self.clinician))}]
        for number, (person, words, role) in enumerate(extra, start=2):
            out.append({'id': f'P{number}', 'name': self.src(person), 'role': self.fact(role, self.src(words))})
        return out

    def frame(self, words: str = '', unit_words: str = '') -> dict:
        return self.src(words, 'document_frame', cite=unit_words or words) if (words or unit_words) else {}

    def opening(self, **slots: Any) -> dict:
        """N0, the opening part: its start cites no unit (1.4; D199); a header part of today's encounter, done by the
        documenting team, in the documenting clinician's entry (each through the document frame)."""
        s2, s3 = self.u(self.dos_line), self.frame_unit()
        item = {'id': 'N0', 'start': {'units': [], 'words': '', 'link': 'section'}, 'end': [],
                'owner': self.fact('documenting_clinician', self.whole(s3, 'document_frame')),
                'role': [self.fact('header', self.whole(self.units[0].id, 'section'))],
                'occasion': [self.fact('on_date_of_service', self.whole(s2, 'document_frame'))],
                'performer': [self.fact('documenting_team', self.whole(s3, 'document_frame'))],
                'performer_person': []}
        item.update(slots)
        return item

    def part(self, sid: str, label: str, role: str, owner: str = 'documenting_clinician', occasion: Any = 'today',
             performer: Any = 'team', owner_words: str = '', end: tuple = (), nth: int = 0) -> dict:
        """A part opened by ``label`` (its ``nth`` occurrence: a heading whose word the title also holds): its role
        cited at the label, its owner (cited at ``owner_words`` when given, else through the document frame), its
        occasion and performer ('today' and 'team' through the frame; None silent; a notation fact otherwise)."""
        s2, s3 = self.u(self.dos_line), self.frame_unit()
        start = self.src(label, 'section', nth=nth)
        owner_fact = (self.fact(owner, self.src(owner_words, 'section')) if owner_words
                      else self.fact(owner, self.whole(s3, 'document_frame')))
        if occasion == 'today':
            occasion_slot = [self.fact('on_date_of_service', self.whole(s2, 'document_frame'))]
        else:
            occasion_slot = self.slot(occasion, start['units'][0], 'frame')
        if performer == 'team':
            performer_slot = [self.fact('documenting_team', self.whole(s3, 'document_frame'))]
        else:
            performer_slot = self.slot(performer, start['units'][0], 'frame')
        return {'id': sid, 'start': start, 'end': [self.src(words, 'section') for words in end], 'owner': owner_fact,
                'role': [self.fact(role, self.src(label, 'section', nth=nth))], 'occasion': occasion_slot,
                'performer': performer_slot, 'performer_person': []}

    # --- objects ---------------------------------------------------------------------------------------------------------

    def session(self, xid: str, kind: Any, kind_words: str, exam: str | None = None, **fields: Any) -> dict:
        """A session: its kind cited at ``kind_words``, its examination (an event id) cited there too; ``fields`` by
        1.4's names (reached, stations and device_reached as lists of notation facts)."""
        anchor = self.u(kind_words)
        # a session told only by its acts has no examination anchor, so its statement link has no units to lie in
        # (3.1 G1): its kind is another statement about it
        kind_link = 'statement' if exam is not None else 'other_statement'
        item = {'id': xid, 'examination': [], 'kind': self.put((kind, kind_words, kind_link), anchor), 'encounter': [],
                'tract': [], 'approach': [], 'through': [], 'reached': [], 'device_reached': [],
                'reached_anatomy': [], 'completion': [], 'stations': [], 'part_of_session': []}
        if exam is not None:
            item['examination'] = [self.fact(exam, self.whole(anchor))]
        for name, spec in fields.items():
            if name in ('reached', 'device_reached', 'stations'):
                item[name] = self.many(spec, anchor)
            else:
                item[name] = self.slot(spec, anchor)
        return item

    def lesion(self, lid: str, description: str, **fields: Any) -> dict:
        anchor = self.u(description)
        item = {'id': lid, 'description': self.src(description), 'multiplicity': [], 'places': [],
                'distinct_from': [], 'same_as': []}
        for name, spec in fields.items():
            item[name] = self.many(spec, anchor) if name in ('places', 'distinct_from', 'same_as') \
                else self.slot(spec, anchor)
        return item

    def anatomy(self, yid: str, type_: Any, **fields: Any) -> dict:
        words = type_[1] if isinstance(type_, tuple) else ''
        anchor = self.u(words) if words else self.units[0].id
        item = {'id': yid, 'type': self.put(type_, anchor), 'organ': [], 'subtype': [], 'joins': []}
        for name, spec in fields.items():
            item[name] = self.many(spec, anchor) if name == 'joins' else self.slot(spec, anchor)
        return item

    EVENT_TARGET = ('lesion', 'structure', 'places', 'anatomy', 'duct')
    EVENT_TECHNIQUE = ('device', 'route')
    EVENT_SCOPE = ('breadth', 'targets', 'segment', 'covers', 'excepts')
    EVENT_VISIT = ('basis', 'separately_identifiable')

    def event(self, eid: str, kind: Any, kind_words: str, status_words: str, status: Any = 'performed',
              anchor_words: str = '', nth: int = 0, **fields: Any) -> dict:
        """An event anchored on the unit holding ``kind_words`` (or ``anchor_words``): its kind cited at
        ``kind_words``, its status at ``status_words`` (a notation fact, or a value with ``status_state``);
        ``restatements`` a list of (words, role); every other field by 1.4's name, the target, technique, scope and
        visit fields flat (places, device, breadth, basis ...). A scope list (targets, segment, covers, excepts) holds
        plain values."""
        anchor = self.u(anchor_words or kind_words, nth)
        state = fields.pop('status_state', 'supported')
        status_src = fields.pop('status_source', None)
        kind_unit = self.near(kind_words, anchor)
        the_kind = kind if isinstance(kind, dict) else self.fact(kind, {'units': [kind_unit], 'words': kind_words,
                                                                        'link': 'statement'})
        if isinstance(status, dict):
            the_status = status
        else:
            source = status_src or {'units': [self.near(status_words, anchor)], 'words': status_words,
                                    'link': 'statement'}
            the_status = self.fact(status, source, state=state)
        item = {'id': eid, 'anchor': {'units': [anchor], 'kind_words': kind_words, 'status_words': status_words},
                'restatements': [], 'kind': the_kind, 'other_class': [], 'status': the_status, 'session': [],
                'date_relation': [], 'date': [], 'performer': [], 'performer_person': [],
                'target': {'lesion': [], 'structure': [], 'places': [], 'anatomy': [], 'duct': []},
                'technique': {'device': [], 'route': []}, 'purpose': [], 'cause': [], 'cause_event': [],
                'part_of': [], 'part_relation': [], 'yield': [], 'access_outcome': [],
                'scope': {'breadth': [], 'targets': [], 'segment': [], 'covers': [], 'excepts': []},
                'visit': {'basis': [], 'separately_identifiable': []}}
        for name, spec in fields.items():
            if name == 'restatements':
                item['restatements'] = [{'units': [self.u(words)], 'role': role} for words, role in spec]
            elif name == 'anchor_units':
                item['anchor']['units'] = list(spec)
            elif name in self.EVENT_TARGET:
                item['target'][name] = self.many(spec, anchor) if name == 'places' else self.slot(spec, anchor)
            elif name in self.EVENT_TECHNIQUE:
                item['technique'][name] = self.slot(spec, anchor)
            elif name in self.EVENT_SCOPE:
                item['scope'][name] = self.slot(spec, anchor) if name == 'breadth' else list(spec)
            elif name in self.EVENT_VISIT:
                item['visit'][name] = self.slot(spec, anchor)
            else:
                item[name] = self.slot(spec, anchor)
        return item

    def doubt(self, about: str, objects: tuple, words: str, basis: str = 'stated', readings: tuple = ()) -> dict:
        return {'about': about, 'objects': list(objects), 'units': [self.u(words)], 'basis': basis,
                'readings': list(readings)}

    def answer(self, sections: list, sessions: tuple = (), events: tuple = (), lesions: tuple = (),
               anatomy: tuple = (), people: list | None = None, doubts: tuple = (), role_words: str = 'Endoscopist',
               date_of_service: dict | None = None, other_dates: tuple = ()) -> dict:
        s2 = self.u(self.dos_line)
        dos = date_of_service or {'state': 'stated', 'value': self.dos,
                                  'sources': [{'units': [s2], 'words': self.dos_words, 'link': 'document_frame'}],
                                  'options': []}
        # a document that names no clinician has no documenting clinician to cite and no person P1 (an empty SLOT)
        clinician = [self.fact('P1', {'units': [self.u(self.clinician)], 'words': self.clinician,
                                      'link': 'document_frame'})] if self.clinician else []
        if people is None:
            people = self.people(role_words) if self.clinician else []
        return {'encounter': {'date_of_service': dos, 'other_dates': list(other_dates),
                              'documenting_clinician': clinician},
                'people': people,
                'sections': list(sections), 'sessions': list(sessions), 'anatomy': list(anatomy),
                'lesions': list(lesions), 'events': list(events), 'doubts': list(doubts)}


def unit_at(text: str, words: str, nth: int = 0, **header: Any) -> str:
    """The id of the unit of ``text`` that holds the ``nth`` occurrence of ``words``: an unlisted entry's unit computed
    from the document, never written by hand (a hand-written id the document does not have is dropped by appraise_read,
    and the entry then lies on no unit, 3.2.6)."""
    return Note(text, **header).u(words, nth)


def event_of(data: dict, eid: str) -> dict:
    return next(item for item in data['events'] if item['id'] == eid)


def session_of(data: dict, xid: str) -> dict:
    return next(item for item in data['sessions'] if item['id'] == xid)


def edited(data: dict, *edits: tuple) -> dict:
    """A deep copy of ``data`` with each edit applied: (family, id, path, value) where path is 'field' or
    'outer.inner' and value replaces it; (family, id, None, None) deletes the object."""
    out = copy.deepcopy(data)
    for family, oid, path, value in edits:
        items = out[family]
        index = next(i for i, item in enumerate(items) if item['id'] == oid)
        if path is None:
            del items[index]
            continue
        node = items[index]
        *outer, last = path.split('.')
        for part in outer:
            node = node[part]
        node[last] = value
    return out
