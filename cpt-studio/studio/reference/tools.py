"""CPT Studio's CMS reference tools for the harness participants (HARNESS.md 11.2, 12.2).

In both phases a model participant may call two tools. CPT Studio answers them here, from its own installed sources:
nothing is fetched from the web and no vendor tool is involved. ``executor(workspace)`` returns the callable the tool
loop (studio/participants/loop.py) is given, ``execute_tool(name, arguments) -> (result, refs)``:

- ``cms_code_facts(codes, date_of_service)``: for each code - at most 32 per call, deduplicated and sorted, each four
  digits and then a digit or a capital letter - the PFS indicators of its unmodified row (status, global days, multiple
  procedure, endoscopic base, PC/TC) and the practitioner MUE (value, adjudication indicator with its label, rationale),
  from the installed reference store (studio.reference.store): from the source of each kind that covers
  date_of_service, or from every release held when it is "". Each source is named with its key, kind, release,
  effective window and the sha256 of the publisher's file. Where no installed source covers the date, two cover it (the
  applicable release is ambiguous, as the reconciliation's lookup reads it), or a source does not list the code,
  CPT Studio says so in its own sentence (``notes``). Refs: ``fact:<source_key>:<code>:<field>`` for every fact
  returned (the field as the store names it: status, global_days, mult_proc, endo_base, pctc, value, mai, rationale).
- ``cms_policy_passages(topic, codes)``: every imported passage of the topic (POLICY_TOPICS maps prompt.POLICY_TOPICS
  onto the passages' own topics), verbatim from studio.reference.passages, each with its passage_key, source key,
  kind, release, effective window, section and page, its own sha256 and the sha256 of the publisher's file it was read
  from. The codes are checked as for cms_code_facts and named back; they select nothing (the participant reads which
  passage applies). Refs: each passage_key returned.

``service_date_hint`` narrows only what a call itself leaves undated: cms_policy_passages names no date, so with a hint
each kind's passages come from the one passage source covering that date (none, with a note, when none or two do). The
pipeline passes none: a participant's requests carry no date (HARNESS.md 3), so its tool results never depend on the
encounter's context either, and a reused run's answers stay the answers to its own requests.

What it never does: return a descriptor - the store holds none, and a result in which any text has a code followed by
an opening parenthesis or '--' (the passage import's own guard, passages.CODE_THEN_DESCRIPTION) is refused whole; call
the network; truncate a result (the loop refuses one over PARTICIPANT_MAX_TOOL_RESULT_BYTES with its own sentence); or
read anything but the installed rows and the arguments, so the same store and arguments give the same result and refs.
An unknown tool, a bad argument or a store error is CPT Studio's own sentence, ``{'error': ...}`` with no refs.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Callable, Optional

from studio.models import ReferenceCodeFact, ReferenceSource
from studio.participants import prompt
from studio.reference import passages as reference_passages
from studio.reference.store import KIND_LABELS, LOOKUP_KINDS, MUE, PFS, applied_sources, source_info

log = logging.getLogger(__name__)

CODE_FACTS, POLICY_PASSAGES = (tool['name'] for tool in prompt.TOOLS)
TOOL_NAMES = (CODE_FACTS, POLICY_PASSAGES)
MAX_CODES = 32
CODE = re.compile(r'[0-9]{4}[0-9A-Z]')
_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
# The fields each kind's facts are returned with, in this order, and their labels (the reconciliation's own words).
FIELDS = {PFS: reference_passages.PFS_FIELDS, MUE: reference_passages.MUE_FIELDS}
_PREFIX = {PFS: 'pfs', MUE: 'mue'}
# prompt.POLICY_TOPICS -> the passage topics (studio.reference.passages.TOPICS) each one returns, in retrieval order.
POLICY_TOPICS = {
    'pfs_indicator_definitions': ('pfs.status', 'pfs.global_days', 'pfs.mult_proc', 'pfs.endo_base', 'pfs.pctc'),
    'ncci_endoscopy_rules': ('ncci.endoscopy',),
    'multiple_endoscopy_payment': ('claims.multiple_endoscopy',),
}
if tuple(POLICY_TOPICS) != tuple(prompt.POLICY_TOPICS):  # the tool's own enumeration: a topic added there is mapped
    raise RuntimeError('studio.reference.tools.POLICY_TOPICS no longer maps prompt.POLICY_TOPICS.')

UNKNOWN_TOOL = f'CPT Studio has no tool by that name; its tools are {CODE_FACTS} and {POLICY_PASSAGES}.'
NOT_AN_OBJECT = 'The arguments must be a JSON object.'
CODES_LIST = 'codes must be a list of CPT code numbers, each a string.'
NO_CODE = f'Give 1 to {MAX_CODES} CPT code numbers.'
TOO_MANY = f'Give at most {MAX_CODES} different codes in one call; this call names {{count}}.'
BAD_CODES = ('Each code must be five characters, four digits and then a digit or a capital letter (for example '
             '45385); {count} of the codes given {verb} not.')
BAD_DATE = 'date_of_service must be a date written YYYY-MM-DD, or "" for every release held.'
BAD_TOPIC = 'topic must be one of ' + ', '.join(prompt.POLICY_TOPICS[:-1]) + f' or {prompt.POLICY_TOPICS[-1]}.'
STORE_ERROR = 'CPT Studio could not read its reference store for this call; nothing was returned.'
DESCRIPTOR = ('CPT Studio could not return this result: a text in it has the form of a code description, and code '
              'descriptions are never returned.')


def executor(workspace, *, service_date_hint: Optional[date] = None) -> Callable[[str, dict], tuple[dict, list]]:
    """``execute_tool(name, arguments) -> (result, refs)`` for one participant phase of ``workspace``. The reference
    store is installation-wide, so the workspace selects nothing; it names whose call a store error was (the log).
    ``service_date_hint``: see the module docstring (the pipeline passes none)."""
    if service_date_hint is not None and (not isinstance(service_date_hint, date)
                                          or hasattr(service_date_hint, 'hour')):
        raise TypeError('service_date_hint must be a date or None.')
    label = str(getattr(workspace, 'pk', workspace))

    def execute_tool(name, arguments) -> tuple[dict, list]:
        if name not in TOOL_NAMES:
            return {'error': UNKNOWN_TOOL}, []
        try:
            if name == CODE_FACTS:
                result, refs = _code_facts(arguments)
            else:
                result, refs = _policy_passages(arguments, service_date_hint)
        except Exception:  # noqa: BLE001 - logged; the participant is given CPT Studio's sentence, never internals
            log.exception('the reference tool %s failed for workspace %s', name, label)
            return {'error': STORE_ERROR}, []
        if 'error' not in result and _has_descriptor_form(result):
            log.error('the reference tool %s refused a result with a descriptor-shaped text (workspace %s)', name,
                      label)
            return {'error': DESCRIPTOR}, []
        return result, refs

    return execute_tool


# --- arguments -------------------------------------------------------------------------------------------------------

class _Refused(Exception):
    """A bad argument: the message is CPT Studio's sentence for the participant."""


def _fields(arguments, names: tuple[str, ...]) -> dict:
    if not isinstance(arguments, dict):
        raise _Refused(NOT_AN_OBJECT)
    if set(arguments) != set(names):
        raise _Refused(f'The arguments must be exactly {" and ".join(names)}.')
    return arguments


def _codes(value, *, required: bool) -> list[str]:
    """The codes named, deduplicated and sorted; a bad list refuses the whole call."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise _Refused(CODES_LIST)
    codes = sorted(set(value))
    if required and not codes:
        raise _Refused(NO_CODE)
    if len(codes) > MAX_CODES:
        raise _Refused(TOO_MANY.format(count=len(codes)))
    bad = sum(1 for code in codes if not CODE.fullmatch(code))
    if bad:
        raise _Refused(BAD_CODES.format(count=bad, verb='is' if bad == 1 else 'are'))
    return codes


def _date(value) -> Optional[date]:
    """The date of service named, or None for "" (every release held)."""
    if value == '':
        return None
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise _Refused(BAD_DATE)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _Refused(BAD_DATE) from None


# --- cms_code_facts --------------------------------------------------------------------------------------------------

def _code_facts(arguments) -> tuple[dict, list]:
    try:
        given = _fields(arguments, ('codes', 'date_of_service'))
        codes, day = _codes(given['codes'], required=True), _date(given['date_of_service'])
    except _Refused as exc:
        return {'error': str(exc)}, []
    sources = sorted((source_info(row) for row in ReferenceSource.objects.filter(kind__in=LOOKUP_KINDS)),
                     key=lambda s: (s.kind, s.effective_start, s.key))
    rows: dict[tuple[str, str], dict[str, dict]] = {}
    for key, code, modifier, facts in (ReferenceCodeFact.objects.filter(source__kind__in=LOOKUP_KINDS, code__in=codes)
                                       .values_list('source__key', 'code', 'modifier', 'facts')):
        rows.setdefault((key, code), {})[modifier] = facts
    entries, refs = [], []
    for code in codes:
        found, notes = [], []
        for kind in LOOKUP_KINDS:
            for source in _sources_for(kind, sources, day, code, notes):
                listed = rows.get((source.key, code), {})
                if '' not in listed:
                    notes.append(_unlisted(code, source.release, listed))
                    continue
                row = listed['']
                facts = [{'ref': f'fact:{source.key}:{code}:{field}', 'field': field,
                          'label': reference_passages.FACT_LABELS[f'{_PREFIX[kind]}.{field}'], 'value': row[field]}
                         for field in FIELDS[kind] if field in row]
                refs += [fact['ref'] for fact in facts]
                found.append({'source_key': source.key, 'kind': source.kind, 'release': source.release,
                              'effective_start': source.effective_start, 'effective_end': source.effective_end,
                              'sha256': source.sha256, 'facts': facts})
        entries.append({'code': code, 'sources': found, 'notes': notes})
    held = f'the release covering {day.isoformat()}' if day is not None else 'every release held'
    return {'tool': CODE_FACTS, 'date_of_service': day.isoformat() if day is not None else '', 'releases': held,
            'codes': entries}, refs


def _sources_for(kind: str, sources, day: Optional[date], code: str, notes: list) -> list:
    """The sources of ``kind`` a call reads: the one covering ``day``, or every one held when ``day`` is None; a note
    says why there is none (as store.build_reference words it for the reconciliation's lookup)."""
    label = KIND_LABELS[kind]
    held = [source for source in sources if source.kind == kind]
    if day is None:
        if not held:
            notes.append(f'{code}: no {label} source is installed.')
        return held
    applied = applied_sources(held, day).get(kind)
    if applied is not None:
        return [applied]
    covering = [s.key for s in held
                if date.fromisoformat(s.effective_start) <= day <= date.fromisoformat(s.effective_end)]
    if covering:
        notes.append(f'{code}: {len(covering)} installed {label} sources cover {day.isoformat()} '
                     f'({", ".join(covering)}); none was used because the applicable release is ambiguous.')
    else:
        notes.append(f'{code}: no installed {label} source covers {day.isoformat()}.')
    return []


def _unlisted(code: str, release: str, listed: dict) -> str:
    if listed:
        return (f'{code} is listed in {release} only with modifier(s) {", ".join(sorted(listed))}; it has no '
                'unmodified row.')
    return f'{code} is not listed in {release}.'


# --- cms_policy_passages ---------------------------------------------------------------------------------------------

def _policy_passages(arguments, hint: Optional[date]) -> tuple[dict, list]:
    try:
        given = _fields(arguments, ('topic', 'codes'))
        if given['topic'] not in POLICY_TOPICS:
            raise _Refused(BAD_TOPIC)
        codes = _codes(given['codes'], required=False)
    except _Refused as exc:
        return {'error': str(exc)}, []
    topics = POLICY_TOPICS[given['topic']]
    kinds = list(dict.fromkeys(reference_passages.TOPICS[topic] for topic in topics))
    loaded = [p for p in reference_passages.load_passages() if p['topic'] in topics]
    held = {}
    for passage in loaded:
        held.setdefault(passage['source_key'], passage)
    notes, allowed = [], set()
    for kind in kinds:
        of_kind = sorted((p for p in held.values() if p['kind'] == kind),
                         key=lambda p: (p['effective_start'], p['source_key']))
        label = reference_passages.KIND_LABELS[kind]
        if not of_kind:
            notes.append(f'No {label} passages of this topic are installed.')
            continue
        if hint is None:
            allowed |= {p['source_key'] for p in of_kind}
            continue
        covering = [p['source_key'] for p in of_kind
                    if date.fromisoformat(p['effective_start']) <= hint <= date.fromisoformat(p['effective_end'])]
        if len(covering) == 1:
            allowed.add(covering[0])
        elif covering:
            notes.append(f'{len(covering)} {label} passage sources cover {hint.isoformat()} ({", ".join(covering)}); '
                         'none was used because the applicable one is ambiguous.')
        else:
            notes.append(f'No {label} passage source covers {hint.isoformat()}.')
    order = {topic: index for index, topic in enumerate(topics)}
    chosen = sorted((p for p in loaded if p['source_key'] in allowed),
                    key=lambda p: (order[p['topic']], p['effective_start'], p['source_key'], p['passage_key']))
    shown = [{'ref': p['passage_key'], 'passage_key': p['passage_key'], 'source_key': p['source_key'],
              'kind': p['kind'], 'release': p['release'], 'effective_start': p['effective_start'],
              'effective_end': p['effective_end'], 'section': p['section'], 'page': p['page'], 'topic': p['topic'],
              'topic_value': p['topic_value'], 'sha256': p['sha256'], 'source_sha256': p['source_sha256'],
              'text': p['text']} for p in chosen]
    return ({'tool': POLICY_PASSAGES, 'topic': given['topic'], 'codes': codes, 'passages': shown, 'notes': notes},
            list(dict.fromkeys(item['ref'] for item in shown)))


# --- what a stored result returned (the API's references; HARNESS.md 12.6) -------------------------------------------

def retrieved_references(result) -> list[dict]:
    """Every reference a stored tool result returned, one per ref in the result's order: ``{ref, kind, source_key,
    release, effective_start, effective_end}`` (HARNESS.md 12.6), read from a result this module made; [] for an error
    result or anything else."""
    if not isinstance(result, dict) or 'error' in result:
        return []
    out = []
    if result.get('tool') == CODE_FACTS:
        for entry in _dicts(result.get('codes')):
            for source in _dicts(entry.get('sources')):
                for fact in _dicts(source.get('facts')):
                    if isinstance(fact.get('ref'), str):
                        out.append({'ref': fact['ref'], **{name: source.get(name) for name in _DATED}})
    elif result.get('tool') == POLICY_PASSAGES:
        for passage in _dicts(result.get('passages')):
            if isinstance(passage.get('ref'), str):
                out.append({'ref': passage['ref'], **{name: passage.get(name) for name in _DATED}})
    return out


_DATED = ('kind', 'source_key', 'release', 'effective_start', 'effective_end')


def _dicts(value) -> list:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _has_descriptor_form(value) -> bool:
    pending = [value]
    while pending:
        node = pending.pop()
        if isinstance(node, str):
            if reference_passages.CODE_THEN_DESCRIPTION.search(node):
                return True
        elif isinstance(node, dict):
            pending.extend(node.keys())
            pending.extend(node.values())
        elif isinstance(node, (list, tuple)):
            pending.extend(node)
    return False
