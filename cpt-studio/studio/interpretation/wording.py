"""CPT Studio's words for the events engine (design/FINAL.md 3.1, 7.4-7.11; design/ADJUDICATION.md R-4): the act, service
and lesion labels, the new facts' questions, the exclusion and hold sentences, the summaries and rationale sentences.

Copied, never called. The legacy words this engine keeps - the act and service labels (reconcile.py:46-82), the incomplete
consideration, the separate-E/M consideration, the dated-check note and the code-count sentences (checks.py), the member
answer's check and reason and its fingerprint (engine.py:5278-5300, 5438), the fallback performed question
(engine.py:3327), the "part of another documented act" hold (reconcile.py:268-289), the dilation-technique hold
(reconcile.py:307-316), the conflict question (reconcile.py:252-258) and the alternatives' notes (rationale.py) - are
copied here, because the modules that hold them are denied on the new path (FINAL 10.1) or are denied by function
(checks.py, R-5). tests/test_interpretation_assess.py (WordingPinned) pins every copy equal to its original through a
test-only import - the three reconcile sentences by building them with the legacy reconcile.match itself, the member
answer's exclusion with the legacy engine's own _MemberAnswers, the inline fallback question against
engine._proposal's source - so a drift in either is seen. The other sentences here are CPT Studio's own wording, not
copies (the conflict's reason over two events, the new facts' questions, the exclusion reasons).
``service.incomplete`` is worded here from the event's own failure-marker words (R-4): checks.incomplete_check reads
a legacy status outcome and is not allowed on the new path, so only its id, label, status, source and closing
sentence are kept and pinned.

Every sentence names no provider, model, vendor or reader (P10; customer_api.FORBIDDEN): what CPT Studio could not
confirm is CPT Studio's reading, never a statement that the document leaves it out. Quotes are the document's own slices.
Pure and Django-free; imports nothing from studio.gi but the reference tables.

**Design v2** (docs/gemini-migration/FINAL-V2.md 4.8, 5.6; DECISIONS D181, D182; step 3c of 8.1), at the end of this
module and additive only - every v1 name above keeps its value and its code: the five new question facts join NEW_FACTS
and MISSING (D181); quote_span, the design's ``wording.quote(span)``, slices the revision for a question after the
decision; and the message ids (Message) with their builders (build, question, explanation) turn the engine's text-free
item - a message id and its Slots of enumeration members, codes and integer spans - into CPT Studio's fixed question and
reason, the only place the document's words join it. The v2 part imports contract/types.py and the engine's text-free
catalogue and types, for its slot types only.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from datetime import date
from enum import Enum, unique
from types import MappingProxyType
from typing import Optional, Sequence, TypeVar

from studio.gi import catalogue, profiles
from studio.interpretation import ENGINE_VERSION
from studio.interpretation.contract.types import (Approach, Device, Extent, Kind, Landmark, Owner, SessionKind, Span,
                                                  Station, Tract)
from studio.interpretation.engine import catalogue as engine_catalogue
from studio.interpretation.engine.types import ItemKind
from studio.types import Check, sha256_json

# --- labels (copied from reconcile.py:46-82; pinned equal) --------------------------------------------------------------

ACT_LABELS = {
    'biopsy': 'forceps biopsy', 'hot_biopsy': 'hot forceps removal', 'snare': 'snare removal', 'emr': 'endoscopic '
    'mucosal resection', 'esd': 'endoscopic submucosal dissection', 'ablation': 'ablation', 'bleeding_control':
    'bleeding control', 'clip': 'clip placement', 'tattoo': 'submucosal tattoo', 'injection': 'submucosal injection',
    'band_ligation': 'band ligation', 'dilation': 'dilation', 'stent': 'stent placement', 'foreign_body':
    'foreign-body removal', 'sphincterotomy': 'sphincterotomy', 'stone_extraction': 'stone removal', 'lithotripsy':
    'lithotripsy', 'cholangioscopy': 'cholangioscopy', 'cannulation': 'cannulation', 'peg': 'gastrostomy (PEG) '
    'placement', 'tube_replacement': 'feeding-tube replacement', 'tube_placement': 'tube placement', 'specimen': 'specimen collection',
    'myotomy': 'myotomy', 'decompression': 'decompression', 'fundoplication': 'transoral fundoplication',
    'capsule_study': 'capsule study', 'manometry': 'manometry', 'ph_monitoring': 'pH / impedance monitoring',
    'rectal_sensation': 'rectal sensation and compliance testing', 'moderate_sedation': 'moderate sedation',
    'fna': 'fine-needle aspiration or biopsy', 'eus_exam': 'endosonographic examination', 'em_visit': 'office visit',
    'drainage': 'drainage', 'stent_removal': 'stent removal', 'stent_exchange': 'stent exchange',
    'pressure_measurement': 'pressure measurement', 'balloon_expulsion': 'balloon expulsion test',
}
SERVICE_LABELS = {'egd': 'upper endoscopy', 'esophagoscopy': 'esophagoscopy', 'poem': 'peroral endoscopic myotomy',
                  'colonoscopy': 'colonoscopy', 'flex_sig': 'flexible sigmoidoscopy', 'eus': 'endoscopic ultrasound',
                  'ercp': 'ERCP', 'enteroscopy': 'enteroscopy', 'capsule': 'capsule endoscopy',
                  'manometry': 'manometry', 'ph_study': 'pH / impedance study', 'anorectal_testing':
                  'anorectal testing', 'feeding_tube': 'feeding-tube procedure', 'office_em': 'office / outpatient '
                  'visit'}
# The event model's own kinds, which the legacy act table does not name (the examination is the session; the umbrellas
# are statements about every act they cover; an E/M's prolonged time).
EVENT_LABELS = {'examination': 'examination', 'removal': 'removal', 'intervention': 'intervention',
                'em_prolonged': 'prolonged visit time', 'other': 'act'}


def act_label(kind: str) -> str:
    """reconcile.act_label (copied): a catalogue act kind's label."""
    return ACT_LABELS.get(kind, kind.replace('_', ' '))


def kind_label(kind: str) -> str:
    """reconcile.kind_label (copied): a service kind's label."""
    return SERVICE_LABELS.get(kind, kind.replace('_', ' '))


def event_kind_label(kind: str) -> str:
    """The label of an event's catalogue kind, the event model's own kinds included."""
    return ACT_LABELS.get(kind) or EVENT_LABELS.get(kind) or kind.replace('_', ' ')


def landmark_label(landmark: str) -> str:
    return '' if landmark in ('', 'not_stated', 'other') else landmark.replace('_', ' ')


def family_label(family: str) -> str:
    profile = profiles.PROFILES.get(family)
    return profile.label if profile is not None else family


# --- small helpers (copied from checks.py: excerpt, _join, plural; pinned equal) ----------------------------------------

EXCERPT_CHARS = 160


def excerpt(text: str) -> str:
    flat = ' '.join(text.split())
    return flat if len(flat) <= EXCERPT_CHARS else flat[:EXCERPT_CHARS - 1].rstrip() + '…'


def join(items: Sequence[str]) -> str:
    items = list(items)
    if len(items) <= 2:
        return ' and '.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def plural(count: int, word: str) -> str:
    return f'{count} {word}' + ('' if count == 1 else 's')


def quote(text: str, limit: int = 160) -> str:
    """reconcile.quote over a text (copied): the document's words in curly quotes, cut at ``limit``."""
    flat = ' '.join(str(text).split())
    return f'“{flat[:limit - 1]}…”' if len(flat) > limit else f'“{flat}”'


def service_name(code: str, family: str) -> str:
    """checks.service_name (copied; denied on the new path): the family's label, or the code's own wording when the
    family has no GI profile."""
    profile = profiles.PROFILES.get(family)
    return profile.label if profile is not None and profile.supported else f'the service reported as {code}'


# --- sources ------------------------------------------------------------------------------------------------------------

SOURCE = f'cpt-studio:{catalogue.CATALOGUE_VERSION}'  # reconcile.SOURCE
EVENTS_SOURCE = f'cpt-studio:{ENGINE_VERSION}'  # a check this engine reads from the event inventory
STATUS_SOURCE = 'cpt-studio:status@1'  # checks.STATUS_SOURCE
CONTEXT_SOURCE = 'cpt-studio:context@1'  # checks.CONTEXT_SOURCE
EM_SOURCE = 'cpt-studio:em-procedure@1'  # checks.EM_SOURCE
COVERAGE_SOURCE = 'cpt-studio:coverage@1'  # checks.COVERAGE_SOURCE
PROVIDER_SOURCE = 'cpt-studio:provider@1'  # checks.PROVIDER_SOURCE
EM_FAMILIES = ('gi.office_em', 'gi.em_other')  # checks.EM_FAMILIES

# --- copied constants (pinned equal) ------------------------------------------------------------------------------------

PROPOSAL_DATE_CHECK = Check('context.service_date', 'Service date', 'fail',
                            'No usable date of service; this proposal waits on the encounter-level service date '
                            'question and date-dependent checks cannot run.', CONTEXT_SOURCE)
SEPARATE_EM_CONSIDERATION = ('Modifier 25 is a consideration only if a significant, separately identifiable E/M '
                             'service is documented; CPT Studio never assigns it.')
UNKNOWN_DATE_NOTE = 'Service date unknown; dated references cannot be applied.'  # reference.store.UNKNOWN_DATE_NOTE
MAX_LISTED_CODE = 10  # engine.MAX_LISTED_CODE: what a stored proposal code holds; codes are never truncated
NO_EVIDENCE = 'No exact source evidence'  # engine.NO_EVIDENCE


def incomplete_consideration(code: str, pfs: Optional[dict], release: str) -> str:
    """checks.incomplete_consideration (copied; denied on the new path): the 52/53 consideration, never assigned."""
    text = ('Incomplete procedure: whether modifier 52 or 53 applies, or whether a different code describes the '
            'service actually performed, depends on the documented extent reached, the documented reason the '
            'procedure was not completed and the applicable payer rules, which are not connected to CPT Studio. '
            'No modifier is assigned.')
    if pfs and '53' in pfs.get('modifier_rows', ()):
        text += f' CMS PFS {release} carries a separate row for {code} with modifier 53.'
    return text


def global_days_note(entries: Sequence[tuple[str, str]], release: str, unavailable: str) -> str:
    """checks.global_days_note (copied; denied on the new path). ``entries``: (code, global days) of the same-day
    procedure codes that have a PFS row."""
    if entries:
        listed = ', '.join(f'{code} {days}' for code, days in entries)
        return f'CMS PFS global days ({release}): {listed}.'
    return f'Global days are not verified: {unavailable}'


def unlisted_codes(count: int, limit: int, returned_by: str = 'The provider') -> str:
    """checks.unlisted_codes (copied; denied on the new path)."""
    pronoun = 'it is' if count == 1 else 'they are'
    return (f'{returned_by} returned {plural(count, "code")} that cannot be listed: empty, or longer than {limit} '
            f'characters (a CPT code has five). {pronoun[0].upper()}{pronoun[1:]} not shown and never truncated.')


def unlisted_codes_check(count: int, limit: int) -> Check:
    """checks.unlisted_codes_check (copied; denied on the new path)."""
    return Check('provider.unlisted', 'Provider codes not listed', 'warn', unlisted_codes(count, limit),
                 PROVIDER_SOURCE)


def response_problems(problems: Sequence[str], response: str = 'the provider response') -> str:
    """checks.response_problems (copied)."""
    return f'{plural(len(problems), "problem")} reading {response}: ' + '; '.join(problems)


# --- the incomplete examination (R-4: worded from the event's failure-marker words) ------------------------------------

def incomplete_check(words: str) -> Check:
    """service.incomplete for an examination documented as begun and not completed, from its own failure-marker words
    (R-4), in checks.incomplete_check's sentence."""
    return Check('service.incomplete', 'Incomplete procedure documented', 'warn',
                 f'Documented as incomplete: {quote(words)}. Kept for review: not treated as completed and not excluded.',
                 STATUS_SOURCE)


# --- the dilation technique (reconcile.py:201-203, 307-316; pinned equal) ---------------------------------------------

TECHNIQUE_WORDS = {catalogue.BALLOON: 'balloon dilation',
                   catalogue.WIRE_BOUGIE: 'dilation with dilators passed over a guide wire',
                   'bougie': 'dilation with an unguided bougie'}

# --- the new facts (contract 9.4): what each names, in plain words (questions.MISSING's form) ---------------------------
# Design v2 (FINAL-V2 4.8; DECISIONS D181, step 3c): the five new question facts join both, after v1's seven and with
# their MISSING sentences verbatim - the path v1 already uses (customer_api.FACT_WORDS and answers read MISSING).

NEW_FACTS = ('event_time', 'event_performer', 'act_target', 'technique', 'statement_scope', 'act_method', 'procedure',
             'event_entry', 'exam_stations', 'act_yield', 'act_cause', 'act_part')
MISSING = {
    'event_time': 'whether the act was done at this encounter',
    'event_performer': 'who performed the act',
    'act_target': 'which lesion or site the act was done on',
    'technique': 'which technique was used',
    'statement_scope': 'whether a statement in the document applies to this act',
    'act_method': 'by which method the lesion was removed',
    'procedure': 'in which procedure the act was done',
    'event_entry': 'whose entry the act is told in',
    'exam_stations': 'which parts of the upper tract were examined',
    'act_yield': 'what the extraction retrieved',
    'act_cause': 'what caused the bleeding the act treated',
    'act_part': 'whether the act was part of another act',
}


def performed_question(code: str) -> str:
    """engine.py:3323-3328's question, for a code whose act CPT Studio's reading does not establish."""
    return f'Confirm whether {code} is supported by what was done on the date of service.'


def not_documented_reason(act: str) -> str:
    """FINAL 7.6: no act of the code's kind documented as done."""
    return f"CPT Studio's reading of the document records no {act} documented as done on the date of service."


def not_linked_reason(code: str, unprofiled: bool) -> str:
    """FINAL 7.2 R2 as ADJUDICATION C-6 amends it: which documented act the code accounts for is not established."""
    if unprofiled:
        return (f'{code} is outside CPT Studio\'s coding profiles; review required. Which documented act {code} '
                'accounts for is not established.')
    return f'Which documented act {code} accounts for is not established.'


def conflict_question(act: str) -> str:
    """FINAL 7.4 h1 (reconcile.py:252-258's question)."""
    return f'The record states the {act} both as performed and as not performed. Which is correct for this encounter?'


def conflict_reason(act: str, done: str, denied: str) -> str:
    return (f'One statement documents the {act} as done ({quote(done, 140)}); another states it was not done '
            f'({quote(denied, 140)}). Both are kept; neither is chosen.')


def doubt_question(act: str, words: str) -> str:
    return f'Confirm whether the {act} ({quote(words, 120)}) was done on the date of service.'


def doubt_reason(act: str, words: str) -> str:
    return f'The document leaves the {act} in doubt: {quote(words, 140)}.'


def time_question(act: str, words: str) -> str:
    return f'Was the {act} ({quote(words, 120)}) done at this encounter?'


def time_reason(act: str) -> str:
    return f'CPT Studio could not confirm from the document when the {act} was done.'


def performer_question(act: str, words: str) -> str:
    return f'Was the {act} ({quote(words, 120)}) done by the documenting endoscopist or the endoscopy team?'


def performer_reason(act: str) -> str:
    return f'CPT Studio could not confirm from the document who performed the {act}.'


def procedure_question(act: str, words: str) -> str:
    """The act's procedure question, quoting its words. DECISIONS D160 (3) (the round-5e review of D153, problem 5):
    empty words are never quoted - an act whose target Gemini left absent asked 'In which procedure was the forceps
    biopsy (“”) done?'."""
    if not ' '.join(str(words or '').split()):
        return f'In which procedure was the {act} done?'
    return f'In which procedure was the {act} ({quote(words, 120)}) done?'


def procedure_reason(act: str) -> str:
    return f'CPT Studio could not confirm from the document in which procedure the {act} was done.'


def status_question(act: str, words: str) -> str:
    return f'Was the {act} ({quote(words, 120)}) done on the date of service?'


def status_reason(act: str) -> str:
    return f'CPT Studio could not confirm from the document that the {act} was done.'


def session_question(about: str, service: str, words: str) -> tuple[str, str]:
    """(question, reason) of a code held because CPT Studio's reading asks about the whole session it belongs to
    (DECISIONS D31): who performed it, when, or whether it was done - the attribute's own question about the session -
    or, for a doubt of no named attribute, whether it was done as this encounter's service. ``words`` is the passage
    the reading's question quotes."""
    if about == 'performer':
        return (performer_question(service, words),
                f'{performer_reason(service)} Every code of that session is held until it is confirmed.')
    if about == 'time':
        return (time_question(service, words),
                f'{time_reason(service)} Every code of that session is held until it is confirmed.')
    if about == 'status':
        return (status_question(service, words),
                f'{status_reason(service)} Every code of that session is held until it is confirmed.')
    return (f'Confirm whether the {service} ({quote(words, 120)}) was done on the date of service by the documenting '
            'endoscopist or the endoscopy team.',
            f"CPT Studio's reading of the document leaves the {service} in doubt: {quote(words, 140)}. Every code of "
            'that session is held until it is confirmed.')


def target_question(act: str, words: str) -> str:
    return f'Which lesion or site was the {act} ({quote(words, 120)}) done on?'


def target_reason(act: str) -> str:
    return f'CPT Studio could not confirm from the document which lesion or site the {act} was done on.'


BUNDLING_QUESTIONS = {
    'biopsy_of_removed_lesion': 'Was the {act} ({part}) taken from the lesion that was removed ({whole}), or from another '
                                'lesion?',
    'resection_technique': 'Was the {act} ({part}) part of the resection of that lesion ({whole}), or of another lesion?',
    'lift_injection': 'Was the {act} ({part}) made to lift the lesion that was resected ({whole}), or given for another '
                      'reason or lesion?',
    'procedural_adjunct': 'Was the {act} ({part}) done as part of the removal ({whole}) - at the site it removed, or for '
                          'the bleeding it caused - or on another lesion or site?',
}


def bundling_question(rule: str, act: str, part: str, whole: str) -> str:
    """FINAL 7.7 "Unresolved identity": the act_target question of a code whose act may be part of another."""
    template = BUNDLING_QUESTIONS.get(rule, BUNDLING_QUESTIONS['biopsy_of_removed_lesion'])
    return template.format(act=act, part=quote(part, 120), whole=quote(whole, 120))


def bundling_reason(act: str) -> str:
    return (f'Whether the {act} is part of another act documented with it depends on which lesion it was done on, which '
            'CPT Studio could not confirm from the document.')


def technique_question(act: str, words: str) -> str:
    return f'Which technique was used for the {act} ({quote(words, 120)})?'


def technique_unresolved_reason(act: str) -> str:
    """FINAL 7.4 h3 (C-16): a statement of another technique beside an act whose own device is not established."""
    return f'CPT Studio could not confirm from the document which technique was used for the {act}.'


def technique_reason(act: str, required: str) -> str:
    return (f'This code accounts for a {required}; CPT Studio could not confirm from the document the technique of the '
            f'{act}.')


def another_technique(name: str, stated: str, required: str, words: str) -> tuple[str, str]:
    """(detail, question) of a dilation of another technique than the code's (reconcile.py:307-316, copied)."""
    return (f'The {name} is documented as performed with a {stated} ({quote(words)}); this code accounts for a '
            f'{required}, which CPT Studio could not find in the document.',
            f'The documented dilation ({quote(words, 120)}) states a {stated}. Was a {required} performed on the date '
            'of service?')


def another_site(name: str, place: str, required: str, words: str) -> tuple[str, str]:
    """(detail, question) of a dilation verified at a place outside the code's site class (DECISIONS D29), in
    another_technique's form: held, never excluded."""
    return (f'The {name} is documented as performed with a dilation at the {place} ({quote(words)}); this code accounts '
            f'for a {required}, which CPT Studio could not find in the document.',
            f'The documented dilation ({quote(words, 120)}) is at the {place}. Was a {required} performed on the date of '
            'service?')


# --- the site of a dilation (DECISIONS D29; R4) and the EUS examination class (D28; R6): CPT Studio's own words --------

SITE_WORDS = {'esophageal': 'dilation of the esophagus', 'gastric_duodenal': 'dilation of the stomach or duodenum'}


def site_reason(act: str, required: str) -> str:
    """D29: a dilation whose structure CPT Studio could not establish (no verified place, a surgically made place, or
    places on both sides of the code's site class); its question is target_question's."""
    return (f'This code accounts for a {required}; CPT Studio could not confirm from the document which structure the '
            f'{act} was done on.')


def defining_target_hold(code: str, act: str, place: str, words: str) -> tuple[str, str]:
    """(reason, question) of a code held because no act it rests on meets its defining target (DECISIONS D145, over
    D120's requirement: mapping.DEFINING_TARGETS names 43240 alone, the transmural drainage of a pancreatic fluid
    collection). The reason says what the code describes and where the document places the ``act`` - ``place``, the
    label of its verified place, or '' when CPT Studio could not confirm which structure it was done on - never that
    the act was not confirmed as done; the question asks its target (fact 'target'), quoting the act's own sentence
    (``words``)."""
    where = (f'the document places this {act} at the {place}' if place
             else f'CPT Studio could not confirm from the document which structure this {act} was done on')
    return (f'{code} describes the transmural drainage of a pancreatic fluid collection (a pseudocyst or walled-off '
            f'necrosis); {where}. Held for the reviewer, not excluded.',
            f'Which structure was the {act} ({quote(words)}) done on: a pancreatic fluid collection (a pseudocyst or '
            'walled-off necrosis), or another structure?')


EXAMINATION_CLASS_WORDS = {'full': 'a full endoscopic ultrasound examination (to the duodenum or beyond)',
                           'limited': 'a limited endoscopic ultrasound examination (short of the duodenum)',
                           'sigmoidoscopic': 'an endoscopic ultrasound examination through a flexible sigmoidoscopy (the '
                                             'rectum and the sigmoid colon, up to part of the descending colon)',
                           'colonoscopic': 'an endoscopic ultrasound examination through a colonoscopy (beyond the '
                                           'splenic flexure)',
                           'stoma': 'an endoscopic ultrasound examination through a colonoscopy by way of a stoma'}
EXAMINATION_CLASS_CHECK = ('facts.examination_class', 'Endoscopic ultrasound examination class')


def examination_class_hold(code: str, exam_class: str, reached: str, words: str,
                           incomplete: bool = False) -> tuple[str, str]:
    """(reason, question) of a code whose EUS examination class the verified reach of its session does not fit
    (DECISIONS D28, D43), in another_technique's form: the code is held, never excluded, by it. ``incomplete``: the
    examination is stated incomplete (D43), whatever its reach."""
    required = EXAMINATION_CLASS_WORDS[exam_class]
    said, shown = (f' ({quote(words)})', f' ({quote(words, 120)})') if words else ('', '')
    if incomplete:
        return (f'The endoscopic ultrasound examination is documented as reaching the {reached}{said} and as incomplete; '
                f'{code} accounts for {required}, which CPT Studio could not find in the document.',
                f'The documented endoscopic ultrasound examination{shown} is stated to be incomplete. Was {required} '
                'performed on the date of service?')
    return (f'The endoscopic ultrasound examination is documented as reaching the {reached}{said}; {code} accounts for '
            f'{required}, which CPT Studio could not find in the document.',
            f'The documented endoscopic ultrasound examination{shown} reached the {reached}. Was {required} performed '
            'on the date of service?')


def scope_question(statement: str, act: str, words: str = '', whole: bool = False, also: Sequence[str] = ()) -> str:
    """FINAL 7.4 h3 (scope) and ADJUDICATION C-10: whether a statement applies to an act. ``whole`` (DECISIONS D103,
    h3's question): the statement is quoted uncut - it is its own passages, which the read bounds to 600 characters
    each - so the words that make it a denial are never cut off the end of a long sentence. ``also`` (DECISIONS D126,
    h3's question): the act's other same-event contradictions' statements, after ``statement`` in their precedence -
    the one question asks whether any of them applies, so none is dropped."""
    quoted = [quote(item, len(item) + 1) if whole else quote(item, 120) for item in (statement, *also)]
    said = quoted[0] if len(quoted) == 1 else ', '.join(quoted[:-1]) + ' or ' + quoted[-1]
    if words:
        return f'Does {said} apply to the {act} ({quote(words, 120)})?'
    return f'Does {said} apply to the {act} this code accounts for?'


def scope_reason(statement: str, act: str, whole: bool = False, also: Sequence[str] = ()) -> str:
    quoted = [quote(item, len(item) + 1) if whole else quote(item, 140) for item in (statement, *also)]
    if len(quoted) > 1:  # DECISIONS D126: every statement the question asks about
        return (f'The document states {join(quoted)}; CPT Studio could not confirm from the document whether those '
                f'statements apply to the {act}.')
    return (f'The document states {quoted[0]}; CPT Studio could not confirm from the document whether that statement '
            f'applies to the {act}.')


def method_question(lesion: str) -> str:
    """FINAL 7.4 h5: a removal whose method is not stated, for a method-specific code."""
    return f'By which method was the {lesion} removed?'


def method_reason(act: str) -> str:
    return (f'The document states a removal without its method; this code accounts for a {act}, which CPT Studio could '
            'not confirm from the document.')


def attempted_reason(act: str, words: str) -> str:
    """ADJUDICATION C-9: a non-base code's act begun and not completed - held, never excluded."""
    return (f'The document states the {act} was begun and not completed ({quote(words, 140)}). Kept for review: not '
            'treated as completed and not excluded.')


def attempted_question(code: str, act: str) -> str:
    return (f'The {act} was begun and not completed. Confirm whether {code} describes what was done on the date of '
            'service.')


# --- exclusions (D5, FINAL 7.5) -----------------------------------------------------------------------------------------

def exclusion_reason(act: str, attribute: str, value: str, words: str) -> str:
    """FINAL 7.5: the exclusion reason quoting D's deciding words in CPT Studio's words, reinstatable."""
    said = quote(words)
    if attribute == 'status' and value == 'planned':
        sentence = f'The document states the {act} as planned, not as done on the date of service: {said}.'
    elif attribute == 'time' and value == 'earlier_encounter':
        sentence = f'The document places the {act} at an earlier encounter, not on the date of service: {said}.'
    elif attribute == 'time' and value == 'future':
        sentence = f'The document places the {act} after the date of service: {said}.'
    elif attribute == 'performer' and value == 'other_facility':
        sentence = f'The document states the {act} was done at another facility: {said}.'
    elif attribute == 'performer':
        sentence = f'The document states the {act} was done by another clinician: {said}.'
    else:
        sentence = f'The document states the {act} was not done: {said}.'
    return f'{sentence} Reinstate if this code is supported.'


# --- the "part of another documented act" hold (reconcile.py:268-289; pinned equal) ------------------------------------

def act_included(name: str, status: str, listed: str, why: str, what: str, words: str) -> tuple[str, str]:
    """(detail, question) of a code whose every act is part of another documented act (reconcile.match 'act_included',
    copied)."""
    return (f'The {name} is documented as {status} with {listed}, which is part of another documented act: {why} No '
            f'separate {what} is documented for this code.',
            f'The {what} documented ({quote(words, 120)}) is part of another procedure documented with it. Was a '
            f'separate {what} performed on the date of service?')


# --- member answers (engine.py:5278-5300 and _MemberAnswers._excluded; pinned equal) -----------------------------------

MEMBER_ANSWER_CHECK = 'member.answer'
MEMBER_ANSWER_SOURCE = 'cpt-studio:member-answer@1'
MEMBER_ANSWER_LABELS = {'not_documented': 'Not documented', 'cannot_confirm': 'Cannot confirm'}
NOT_APPLIED = 'not_applied'
OVERLAY_READ = 'read_by_the_review_overlay'


def answered_fingerprint(fingerprint: str, found, status: str) -> str:
    """engine.answered_fingerprint (copied): a proposal a member's answer excluded keeps a fingerprint of its own."""
    return sha256_json({'unanswered': fingerprint, 'checks': sorted([check.id, check.status] for check in found),
                        'status': status})


def member_answer_reason(value: str, what: str) -> str:
    return (f'The member answered "{MEMBER_ANSWER_LABELS[value]}" to {what}; this code is excluded by that answer until '
            'it is withdrawn.')


# --- alternatives (rationale.py, copied) ----------------------------------------------------------------------------------

def _listing(role: str, parent_code: Optional[str], unlisted_parent: bool = False) -> str:
    if role == 'alternative':
        if parent_code:
            return f'alternative to {parent_code}'
        return 'alternative to a provider code that is not listed' if unlisted_parent else 'alternative'
    if role == 'candidate':
        return 'candidate'
    return f'code listed with role “{role}”'


def alternative_rationale(*, provider: str, role: str, parent_code: Optional[str], evidence_count: int,
                          unlisted_parent: bool = False, not_added: str = '') -> str:
    """rationale.alternative_rationale (copied)."""
    if role == 'selected' and not_added:
        text = f'Selected by {provider}; not added as a proposal: {not_added}. Informational only.'
    else:
        text = (f'Listed by {provider} as {_listing(role, parent_code, unlisted_parent)}; the provider did not select '
                'it. Informational only.')
    if evidence_count:
        text += f' {plural(evidence_count, "exact evidence passage")}.'
    return text


def alternative_note(role: str, parent_code: Optional[str], *, unlisted_parent: bool = False,
                     not_added: str = '') -> str:
    """rationale.alternative_note (copied)."""
    if role == 'selected' and not_added:
        return (f'Selected by the provider in the bounded second review, but not added as a proposal: {not_added}. '
                'Candidates and alternatives cannot be approved.')
    return (f'Provider {_listing(role, parent_code, unlisted_parent)}; not selected. Candidates and alternatives '
            'cannot be approved.')


# --- the rationale of a decidable proposal (CPT Studio's words; FINAL 7.11) -------------------------------------------

STATE_PHRASES = {'performed': 'performed', 'incomplete': 'incomplete (performed in part)',
                 'uncertain': 'not established as performed', 'not_performed': 'not performed on the date of service'}
MEMBER_ENTERED = 'Entered by a workspace member as encounter metadata (not clinical documentation)'  # checks


def selected_rationale(*, lead: str, evidence_count: int, family: str, state: str, events: Sequence[str],
                       facts: Sequence[tuple[str, str]], entered: Sequence[tuple[str, str]] = ()) -> str:
    """Who proposed the code (``lead``, its first sentence), how much exact evidence links it, its family, the state
    CPT Studio's reading of the documented events gives it and the documented facts with their values - nothing else."""
    parts = [lead, f'{plural(evidence_count, "exact evidence passage")}.']
    profile = profiles.PROFILES.get(family)
    if profile is not None and not profile.supported:
        parts.append(f'{profile.label}, which has no GI profile in this release.')
    elif profile is not None:
        parts.append(f'Family: {profile.label}.')
    parts.append(f'Status: {STATE_PHRASES.get(state, state)}.')
    if events:
        parts.append(f'Documented: {"; ".join(events)}.')
    for heading, pairs in (('Documented facts', facts), (MEMBER_ENTERED, entered)):
        if pairs:
            parts.append(f'{heading}: ' + '; '.join(f'{name.replace("_", " ")} = {excerpt(str(value))}'
                                                    for name, value in pairs) + '.')
    return ' '.join(parts)


# --- the dated-reference note (checks.unavailable_reason, copied) -------------------------------------------------------

def unavailable_reason(kind_label: str, sources, kind: str, service_date: Optional[date]) -> str:
    """checks.unavailable_reason (copied): why no source of ``kind`` was applied for the date."""
    from studio.reference.store import source_applies  # the reference package is allowed on the new path

    if service_date is None:
        return UNKNOWN_DATE_NOTE
    installed = [s for s in sources if s.kind == kind]
    if not installed:
        return f'No {kind_label} source is installed.'
    covering = [s for s in installed if source_applies(s, service_date)]
    if covering:
        return (f'{len(covering)} installed {kind_label} releases cover {service_date.isoformat()}; none was applied '
                'because the applicable release is ambiguous.')
    windows = '; '.join(f'{s.release} {s.effective_start} to {s.effective_end}' for s in installed)
    return f'No installed {kind_label} release covers {service_date.isoformat()} (installed: {windows}).'


# ======================================================================================================================
# Design v2 (docs/gemini-migration/FINAL-V2.md 4.8, 5.6; DECISIONS D181, D182; step 3c of 8.1): the words of a held
# code's one item. Additive: nothing above is changed or called differently; v1's builders are reused as they are.
# ======================================================================================================================

_T = TypeVar('_T')

# --- quote(span): the revision's own words, after the decision (FINAL-V2 1.7, 4.1, 5.6) --------------------------------


def _runs(spans: Span | Sequence[Span], length: int) -> list[tuple[int, int]]:
    """The non-empty runs ``spans`` cover, in document order, overlapping or touching spans merged into one run.
    ValueError when an item is not a Span or reaches past ``length``."""
    items = (spans,) if isinstance(spans, Span) else tuple(spans)
    for item in items:
        if not isinstance(item, Span):
            raise ValueError(f'A quoted span is a contract Span; got {item!r}.')
        if item.end > length:
            raise ValueError(f'The span ({item.start}, {item.end}) reaches past the revision text ({length}).')
    runs: list[tuple[int, int]] = []
    for item in sorted(set(items)):
        if item.start == item.end:
            continue
        if runs and item.start <= runs[-1][1]:
            runs[-1] = (runs[-1][0], max(runs[-1][1], item.end))
        else:
            runs.append((item.start, item.end))
    return runs


def span_text(text: str, spans: Span | Sequence[Span]) -> str:
    """The revision's own words at ``spans`` (FINAL-V2 1.7: the engine reads integer spans; the text is sliced here,
    after the decision): each covered run once, in document order, the runs joined by one space. ValueError when an
    item is not a Span or reaches past ``text`` - never clamped: a span the revision does not hold is a binding failure,
    never a shorter quote."""
    if not isinstance(text, str):
        raise ValueError('The revision text is a str.')
    return ' '.join(text[start:end] for start, end in _runs(spans, len(text)))


def quote_span(text: str, spans: Span | Sequence[Span], limit: int = 160) -> str:
    """The design's ``wording.quote(span)`` (FINAL-V2 1.7, 4.1; 5.6's allowlist: display, nothing branches on what it
    returns): the document's words at ``spans`` in curly quotes, cut at ``limit`` by v1's quote. Named quote_span
    because ``quote(text, limit)`` is v1's, which v1's modules call and which stays unchanged."""
    return quote(span_text(text, spans), limit)


def _whole(text: str) -> str:
    """assess._whole (copied): the document's words in curly quotes, uncut."""
    return quote(text, len(text) + 1)


def _req(value: _T | None, name: str) -> _T:
    if value is None:
        raise ValueError(f'The slot {name} is needed here.')
    return value


# --- the display tables the item sentences read (copied where v1 has them; each pinned equal by test) ------------------

HELD = 'Held for the reviewer, not excluded.'  # assess.HELD (copied)
EXTENT_NOT_FOUND = 'CPT Studio could not find how far the examination reached'  # checks.EXTENT_NOT_FOUND (copied)
# mapping.SERVICE_KIND (copied, keyed by the session kind): the service label of a family's examination
SESSION_SERVICES: Mapping[SessionKind, str] = MappingProxyType({
    SessionKind.EGD: 'egd', SessionKind.COLONOSCOPY: 'colonoscopy', SessionKind.FLEX_SIG: 'flex_sig',
    SessionKind.EUS: 'eus', SessionKind.ERCP: 'ercp', SessionKind.ENTEROSCOPY: 'enteroscopy',
    SessionKind.CAPSULE: 'capsule', SessionKind.MOTILITY: 'manometry', SessionKind.REFLUX: 'ph_study',
    SessionKind.ANORECTAL: 'anorectal_testing', SessionKind.FEEDING_TUBE: 'feeding_tube',
    SessionKind.OFFICE_EM: 'office_em'})
# checks.FACT_QUESTIONS (copied): the R6 and member-context questions, by fact
R6_QUESTIONS: Mapping[str, str] = MappingProxyType({
    'setting': '{label}: confirm the place of service (for example office or hospital outpatient).',
    'patient_status': '{label}: confirm whether the patient is new or established.',
    'em_basis': '{label}: confirm whether the visit level rests on total time on the date of service or on medical '
                'decision making.',
    'extent': '{label}: confirm the furthest extent reached.',
    'target': '{label}: confirm the structure examined.',
    'cannulation': '{label}: confirm whether, and which, duct was cannulated.',
})
# Why each R6 or member-context fact is asked, in CPT Studio's words: what it could not confirm (the extent's is
# checks.fact_clarifications' own), or, for member context (D3: never read from the document), what is not entered.
R6_REASONS: Mapping[str, str] = MappingProxyType({
    'extent': EXTENT_NOT_FOUND + '; the {label} profile requires it.',
    'target': 'CPT Studio could not confirm the structure examined; the {label} profile requires it.',
    'cannulation': 'CPT Studio could not confirm whether cannulation was achieved; the {label} profile requires it.',
    'em_basis': 'CPT Studio could not confirm the basis for the visit level; the {label} profile requires it.',
    'setting': 'The place of service is not entered for this encounter; the {label} profile requires it.',
    'patient_status': 'Whether the patient is new or established is not entered for this encounter; the {label} '
                      'profile requires it.',
})
SETTING_AND_STATUS_QUESTION = ('{label}: confirm the place of service (for example office or hospital outpatient) and '
                               'whether the patient is new or established.')
SETTING_AND_STATUS_REASON = ('The place of service and whether the patient is new or established are not entered for '
                             'this encounter; the {label} profile requires them.')
SERVICE_DATE_QUESTION = 'Confirm the date of service for this encounter.'  # checks.service_date_clarification's
SERVICE_DATE_REASON = ('CPT Studio could not confirm the date of service; every service and every dated reference '
                       'check depends on it.')
# checks.SEPARATE_EM_QUESTION (copied)
SEPARATE_EM_QUESTION = ('Was a significant, separately identifiable evaluation and management service performed on '
                        'the date of service, beyond the usual pre-procedure assessment? If so, add that '
                        'documentation.')
BASE_QUESTION = 'Is {code} reported separately from {included} for this examination?'  # classes.BASE_QUESTION
IN_DOUBT = ' (stated in doubt)'  # classes.IN_DOUBT (copied)
# assess.py's EUS words (DECISIONS D171; copied), and the lower tract's in UPPER_TRACT_WORDS' form
EGD_LIMITED_WORDS = ('an endoscopic ultrasound examination limited to the esophagus, the stomach or the duodenum (and '
                     'adjacent structures)')
FULL_STATIONS_WORDS = 'an endoscopic ultrasound examination including the esophagus, the stomach and the duodenum'
UPPER_TRACT_WORDS = 'an endoscopic ultrasound through an upper endoscopy (the esophagus, the stomach or the duodenum)'
LOWER_TRACT_WORDS = ('an endoscopic ultrasound through a flexible sigmoidoscopy or a colonoscopy (the rectum or the '
                     'colon)')
EUS_TRACT_WORDS: Mapping[Tract, str] = MappingProxyType({Tract.UPPER: UPPER_TRACT_WORDS, Tract.LOWER: LOWER_TRACT_WORDS})
TRACT_PLACES: Mapping[Tract, str] = MappingProxyType({Tract.UPPER: 'the upper tract', Tract.LOWER: 'the lower tract',
                                                      Tract.PANCREATOBILIARY: 'the pancreatobiliary tract'})
TRANSMURAL_WORDS = ('an EUS-guided transmural injection (of a diagnostic or therapeutic substance, or of fiducial '
                    'markers)')  # assess._eus_code_hold's D171 (4) words (copied)
# classes.CLASS_WORDS and ROUTE_PHRASES (copied, keyed by the engine's class and the contract's approach)
ENTEROSCOPY_CLASS_WORDS: Mapping[engine_catalogue.EnteroscopyClass, str] = MappingProxyType({
    engine_catalogue.EnteroscopyClass.JEJUNAL: 'a small-bowel enteroscopy past the second portion of the duodenum that '
                                               'stops short of the ileum',
    engine_catalogue.EnteroscopyClass.ILEAL: 'a small-bowel enteroscopy past the second portion of the duodenum that '
                                             'reaches the ileum',
    engine_catalogue.EnteroscopyClass.STOMA: 'an examination of the ileum through a stoma',
    engine_catalogue.EnteroscopyClass.POUCH: 'an endoscopic examination of a small-intestinal pouch'})
APPROACH_WORDS: Mapping[Approach, str] = MappingProxyType({
    Approach.ORAL: 'through the mouth', Approach.THROUGH_STOMA: 'through a stoma',
    Approach.THROUGH_POUCH: 'through a pouch'})
APPROACH_ANATOMY: Mapping[Approach, str] = MappingProxyType({Approach.THROUGH_STOMA: 'stoma',
                                                            Approach.THROUGH_POUCH: 'pouch'})
# whose entry an act is told in, when it is not the documenting clinician's (4.8's "documented only in the anesthesia
# entry"; v1's another_role_hold named the nursing, anesthesia, pathology and radiology entries alike)
OWNER_ENTRIES: Mapping[Owner, str] = MappingProxyType({
    Owner.NURSING: 'the nursing entry', Owner.ANESTHESIA: 'the anesthesia entry', Owner.PATHOLOGY: 'the pathology entry',
    Owner.RADIOLOGY: 'the radiology entry', Owner.OTHER_CLINICIAN: "another clinician's entry",
    Owner.OUTSIDE_RECORD: 'an outside record', Owner.PATIENT_REPORTED: "the patient's own account",
    Owner.ADMINISTRATIVE: 'an administrative entry'})


@unique
class Bundling(Enum):
    """The bundling rule an item about a part names (FINAL-V2 4.7; v1's BUNDLING_QUESTIONS keys and coverage's
    reasons): the rules that can ask (the first six) and the kinds that are always bundled (clip, cannulation)."""
    BIOPSY_OF_REMOVED_LESION = 'biopsy_of_removed_lesion'
    RESECTION_TECHNIQUE = 'resection_technique'
    LIFT_INJECTION = 'lift_injection'
    PROCEDURAL_ADJUNCT = 'procedural_adjunct'
    DRAINAGE_STEP = 'drainage_step'
    STENT_INCLUDED = 'stent_included'
    CLIP = 'clip'
    CANNULATION = 'cannulation'


_COMMON_BUNDLED = dict(catalogue.COMMON_BUNDLED)
# Why a part is not reported on its own: the catalogue's COMMON_BUNDLED sentences, and coverage's and assess's own
# (coverage.PROCEDURAL_ADJUNCT, coverage.STENT_INCLUDED, assess._step_reason's part words; copied)
BUNDLING_WHY: Mapping[Bundling, str] = MappingProxyType({
    Bundling.BIOPSY_OF_REMOVED_LESION: _COMMON_BUNDLED['biopsy_of_removed_lesion'],
    Bundling.RESECTION_TECHNIQUE: _COMMON_BUNDLED['resection_technique'],
    Bundling.LIFT_INJECTION: _COMMON_BUNDLED['lift_injection'],
    Bundling.PROCEDURAL_ADJUNCT: ('An ablation or a control of bleeding done as part of a removal at the same session - '
                                  'on the lesion it removes, or of the bleeding it causes - is part of that removal, '
                                  'not a separate service (internal profile rule).'),
    Bundling.DRAINAGE_STEP: ('The needle access and aspiration of a collection that is drained are part of that '
                             'drainage, which its code accounts for, not a separate service (internal profile rule).'),
    Bundling.STENT_INCLUDED: ('A sphincterotomy or a dilation done at the same ERCP as a stent placement or exchange in '
                              'the same duct is part of that stent service (the stent code includes sphincterotomy and '
                              'pre- and post-dilation, when performed); one of the other duct is a separate service '
                              '(internal profile rule).'),
    Bundling.CLIP: _COMMON_BUNDLED['clip'],
    Bundling.CANNULATION: _COMMON_BUNDLED['cannulation'],
})
# The part questions of the two rules v1's BUNDLING_QUESTIONS does not hold (the drainage step: assess's D171 (1)
# question in its form; the stent's duct, D45); v1's four are asked by v1's bundling_question, unchanged.
PART_QUESTIONS: Mapping[Bundling, str] = MappingProxyType({
    Bundling.DRAINAGE_STEP: 'Was the {act} ({part}) a separate sampling, or a step of the transmural drainage ({whole})?',
    Bundling.STENT_INCLUDED: 'Was the {act} ({part}) done in the duct of the stent placement ({whole}), or in the other '
                             'duct?',
})


def family_slug(family: SessionKind) -> str:
    """engine/derive.family_slug (copied; pinned equal): a family's gi.profiles slug."""
    if family is SessionKind.OTHER_GI:
        return 'gi.other'
    if family is SessionKind.NOT_GI:
        return 'gi.unsupported'
    return f'gi.{family.value}'


def service_phrase(family: SessionKind | None) -> str:
    """events.service_label over a session kind: the service label of its examination, else its profile's label;
    'procedure' when no family is named."""
    if family is None:
        return 'procedure'
    service = SESSION_SERVICES.get(family)
    return kind_label(service) if service else family_label(family_slug(family))


def profile_label(family: SessionKind) -> str:
    """The family's profile label (checks.FACT_QUESTIONS' {label})."""
    return family_label(family_slug(family))


def _eus_class_words(code: str, exam_class: engine_catalogue.EusClass) -> str:
    """The class words of an EUS code (EXAMINATION_CLASS_WORDS), the limited class as CPT states it for an EGD's limited
    EUS codes (43237, 43238: DECISIONS D171 (3))."""
    if (exam_class is engine_catalogue.EusClass.LIMITED and code.isdigit()
            and int(code) in engine_catalogue.EGD_LIMITED_EUS_CODES):
        return EGD_LIMITED_WORDS
    return EXAMINATION_CLASS_WORDS[exam_class.value]


# --- the message ids (FINAL-V2 4.8, D182: each held code carries ONE item, a question or an explanation) ---------------


@unique
class Message(Enum):
    """The message id of a held code's one item (FINAL-V2 4.8; engine/questions.py, step 4a, chooses it with RANK): each
    names one fixed question and reason, built by ``build`` from its Slots and the revision text. MESSAGES gives each
    id its fact key (questions.FORM's, as RANK writes it), its kind (a question when the requirement is unresolved, an
    explanation when an established fact fails it) and its RANK row; tests/v2/test_wording_v2.py holds every item
    engine/requirements.RULES can raise to an id of the same rank, fact key and kind."""
    CONFLICT = 'conflict'  # 1 Q: a CONTRADICTION relation on the deciding act (done, and stated not done)
    CONFLICT_FACT = 'conflict_fact'  # 1 Q: a contradicted fact - two statements disagree (or pass 2's counter-evidence)
    DOUBT = 'doubt'  # 2 Q: the act's status in doubt
    STATEMENT_SCOPE = 'statement_scope'  # 3 Q: whether a statement applies to the act
    STATUS = 'status'  # 4 Q: the act's status not established
    NOT_DOCUMENTED = 'not_documented'  # 4 Q: no act of the code's kind documented as done (7.6)
    ATTEMPTED = 'attempted'  # 4 E: begun and not completed on a code that is not an examination's (C-9)
    UNPROFILED = 'unprofiled'  # 4 E: route (d), no profile (C-6)
    NOT_LINKED = 'not_linked'  # 4 E: route (d), which act the code accounts for not established (C-6)
    RECOGNISED_ONLY = 'recognised_only'  # 4 E: D80
    UNRECONCILED = 'unreconciled'  # 4 E: route (b), never READY (D197)
    ENTRY = 'entry'  # 5 Q: whose entry the act is told in
    ANOTHER_ENTRY = 'another_entry'  # 5 E: told only in another role's entry
    TIME = 'time'  # 6 Q
    TIME_BESIDE_VISIT = 'time_beside_visit'  # 6 Q: an undatable act beside an E/M (C3+SEP)
    PERFORMER = 'performer'  # 7 Q
    PROCEDURE = 'procedure'  # 8 Q: the session not established
    ANOTHER_TRACT = 'another_tract'  # 8 E: TRACT, the session's tract is the other one
    ENTEROSCOPY_ROUTE = 'enteroscopy_route'  # 8 Q: ENT, the approach not established beside a stoma or pouch
    ENTEROSCOPY_APPROACH = 'enteroscopy_approach'  # 8 E: ENT, the approach established and not the class's
    METHOD = 'method'  # 9 Q: a positive umbrella beside a method-specific code
    TECHNIQUE = 'technique'  # 10 Q: TECH, the act's technique not established
    STATED_TECHNIQUE = 'stated_technique'  # 10 Q: a statement of a technique beside an act whose own is not established
    ANOTHER_TECHNIQUE = 'another_technique'  # 10 E: TECH, another class
    ROUTE = 'route'  # 10 Q: ROUTE (43253), the route not established
    WALL_INJECTION = 'wall_injection'  # 10 E: ROUTE, submucosal
    ACT_TARGET = 'act_target'  # 11 Q
    SITE = 'site'  # 11 Q: SITE, the structure not established
    ANOTHER_SITE = 'another_site'  # 11 E: SITE, outside the class
    DUCT = 'duct'  # 11 Q: XCHG, the duct
    TARGET = 'target'  # 12 Q: R6:target
    STRUCTURE = 'structure'  # 12 Q: STRUCT:pfc, the structure not established
    ANOTHER_STRUCTURE = 'another_structure'  # 12 E: STRUCT:pfc, another structure
    STATIONS = 'stations'  # 13 Q: STATIONS, LIMITED
    STATION_CLASS = 'station_class'  # 13 E: a station negated (full), all three examined (limited)
    EXTENT = 'extent'  # 14 Q: R6:extent, COLFULL, the class reach
    EXAMINATION_CLASS = 'examination_class'  # 14 E: LOWER and the EUS classes, a misfit reach
    ENTEROSCOPY_CLASS = 'enteroscopy_class'  # 14 E: ENT, a misfit reach or an incomplete deeper class
    YIELD = 'yield'  # 15 Q: YIELD
    NOTHING_RETRIEVED = 'nothing_retrieved'  # 15 E: YIELD negated
    CANNULATION = 'cannulation'  # 16 Q: R6:cannulation
    PART = 'part'  # 17 Q: act_part
    BUNDLING_TARGET = 'bundling_target'  # 17 Q: act_target (bundling identity)
    CAUSE = 'cause'  # 17 Q: act_cause
    BUNDLED = 'bundled'  # 18 E: part of another act (the explanation naming the whole)
    EM_BASIS = 'em_basis'  # 19 Q
    SEPARATE_EM = 'separate_em'  # 20 Q: C3+SEP
    SEPARATE_EM_DENIED = 'separate_em_denied'  # 20 E: separately_identifiable denied, the denial quoted
    BASE_INCLUDED = 'base_included'  # 21 Q: beside acts in doubt
    BASE_EXPLAINED = 'base_explained'  # 21 E: beside interventions coded, or acts it does not account for
    BASE_WITHIN = 'base_within'  # 21 E: the endoscopic portion of an EUS
    COMPETING = 'competing'  # 22 Q
    SETTING = 'setting'  # 23 Q (member context, D3)
    PATIENT_STATUS = 'patient_status'  # 23 Q (member context, D3)
    SERVICE_DATE = 'service_date'  # unranked Q: the encounter-scope date question


@dataclass(frozen=True, slots=True)
class Slots:
    """What an item's sentence names, text-free (FINAL-V2 4.1: enumeration members, codes and integer spans): the
    engine fills it, and ``build`` slices the revision for its spans after the decision. Every field is optional; each
    message needs the fields MESSAGES names (``build`` refuses one left empty).

    code: the code held (CPT Studio's own: a proposed code). act: the act's kind; device, lesion (the lesion's own words)
    and place make its label (act_phrase). words: the act's own statement (its anchor units). statements: each statement
    a question quotes (a denial, a scope statement, the two sides of a conflict, a doubt's passage), each its spans.
    whole, whole_words: the act a part belongs to (bundling) or a counterpart (a duct, a cause). group: the kinds the
    code accounts for. family: the session's kind. technique, stated: the code's and the act's technique class. site:
    the code's site class. exam_class, enteroscopy_class, reached, incomplete: an examination class, the reach the
    session's facts give, and an examination stated incomplete. owner: the entry an act is told in. stations: the
    stations established examined; denied: those established not examined. tract, required_tract: the session's tract
    and the code's. approach, approach_words: the examination's own route and its words; approaches: the routes the
    encounter's anatomy opens. bundling: the bundling rule. listed: the acts listed (the parts bundled, the same-day
    procedures, the acts a base code does not account for); possible: the acts possibly performed. codes: the other
    codes named (the interventions coded, the rival codes). both: the member context's setting and patient status are
    both missing.

    ValueError when a field holds anything but its type (a span list a str, a kind a string), or a code is not a code's
    shape (ASCII letters and digits, at most MAX_LISTED_CODE): a sentence is never built from an untyped value."""
    code: str = ''
    act: Kind | None = None
    device: Device | None = None
    lesion: tuple[Span, ...] = ()
    place: Landmark | None = None
    words: tuple[Span, ...] = ()
    statements: tuple[tuple[Span, ...], ...] = ()
    whole: Kind | None = None
    whole_words: tuple[Span, ...] = ()
    group: tuple[Kind, ...] = ()
    family: SessionKind | None = None
    technique: engine_catalogue.TechniqueClass | None = None
    stated: engine_catalogue.TechniqueClass | None = None
    site: engine_catalogue.SiteClass | None = None
    exam_class: engine_catalogue.EusClass | None = None
    enteroscopy_class: engine_catalogue.EnteroscopyClass | None = None
    reached: Extent | None = None
    incomplete: bool = False
    owner: Owner | None = None
    stations: tuple[Station, ...] = ()
    denied: tuple[Station, ...] = ()
    tract: Tract | None = None
    required_tract: Tract | None = None
    approach: Approach | None = None
    approach_words: tuple[Span, ...] = ()
    approaches: tuple[Approach, ...] = ()
    bundling: Bundling | None = None
    listed: tuple[Kind, ...] = ()
    possible: tuple[Kind, ...] = ()
    codes: tuple[str, ...] = ()
    both: bool = False

    def __post_init__(self) -> None:
        for field in fields(self):
            expected, many = _SLOT_TYPES[field.name]
            value = getattr(self, field.name)
            if many:
                if not isinstance(value, tuple) or not all(_typed(item, expected) for item in value):
                    raise ValueError(f'Slots.{field.name} is a tuple of {expected}; got {value!r}.')
            elif not _typed(value, expected):
                raise ValueError(f'Slots.{field.name} is a {expected}; got {value!r}.')
        if not all(_code_shaped(code) for code in (*((self.code,) if self.code else ()), *self.codes)):
            raise ValueError(f'A code is ASCII letters and digits, at most {MAX_LISTED_CODE}; got {self.code!r}, '
                             f'{self.codes!r}.')


def _code_shaped(code: str) -> bool:
    return code.isascii() and code.isalnum() and len(code) <= MAX_LISTED_CODE


def _typed(value: object, expected: object) -> bool:
    if expected == 'spans':
        return isinstance(value, tuple) and all(isinstance(item, Span) for item in value)
    if expected is bool:
        return type(value) is bool
    if expected is str:
        return type(value) is str
    return value is None or isinstance(value, expected)  # type: ignore[arg-type]


# Each Slots field's type: (the type, whether the field is a tuple of it); 'spans' is a tuple of Spans.
_SLOT_TYPES: Mapping[str, tuple[object, bool]] = MappingProxyType({
    'code': (str, False), 'act': (Kind, False), 'device': (Device, False), 'lesion': (Span, True),
    'place': (Landmark, False), 'words': (Span, True), 'statements': ('spans', True), 'whole': (Kind, False),
    'whole_words': (Span, True), 'group': (Kind, True), 'family': (SessionKind, False),
    'technique': (engine_catalogue.TechniqueClass, False), 'stated': (engine_catalogue.TechniqueClass, False),
    'site': (engine_catalogue.SiteClass, False), 'exam_class': (engine_catalogue.EusClass, False),
    'enteroscopy_class': (engine_catalogue.EnteroscopyClass, False), 'reached': (Extent, False),
    'incomplete': (bool, False), 'owner': (Owner, False), 'stations': (Station, True), 'denied': (Station, True),
    'tract': (Tract, False), 'required_tract': (Tract, False), 'approach': (Approach, False),
    'approach_words': (Span, True), 'approaches': (Approach, True), 'bundling': (Bundling, False),
    'listed': (Kind, True), 'possible': (Kind, True), 'codes': (str, True), 'both': (bool, False),
})
# The Slots fields that hold spans: a message that needs one needs words at it, not only a span.
_SPAN_FIELDS = frozenset({'lesion', 'words', 'whole_words', 'approach_words'})


@dataclass(frozen=True, slots=True)
class Worded:
    """A held code's item in CPT Studio's words: its message id, its fact key (questions.FORM's; conflict:<kind> for a
    conflict), its kind, the question the member is asked (Clarification.question) and the reason it is held - the
    explanation of an explanation item (Clarification.reason)."""
    message: Message
    fact: str
    kind: ItemKind
    question: str
    reason: str


@dataclass(frozen=True, slots=True)
class MessageSpec:
    """One message id's entry: fact, its questions.FORM fact key ('conflict' is written conflict:<kind>); kind, question
    or explanation; rank, its RANK row (engine/requirements.Rank's value; None for the unranked service_date); needs,
    the Slots fields it is never worded without; words, its builder: (slots, revision text) -> (question, reason)."""
    fact: str
    kind: ItemKind
    rank: int | None
    needs: tuple[str, ...]
    words: Callable[[Slots, str], tuple[str, str]]


# --- labels over slots ----------------------------------------------------------------------------------------------


def act_phrase(text: str, slots: Slots) -> str:
    """events.event_label over text-free facts: the act's label (an examination's is its session's service), its device
    where the label does not name it, then 'of the' its lesion's own words, else 'at the' its place."""
    kind = _req(slots.act, 'act')
    if kind is Kind.EXAMINATION:
        service = SESSION_SERVICES.get(slots.family) if slots.family is not None else None
        label = kind_label(service) if service else 'examination'
    else:
        label = event_kind_label(kind.value)
    device = slots.device
    if device is not None and device not in (Device.ENDOSCOPE, Device.OTHER):
        named = landmark_label(device.value)
        if named and named not in label:
            label = f'{label} ({named})'
    lesion = ' '.join(span_text(text, slots.lesion).split()) if slots.lesion else ''
    if lesion:
        return f'{label} of the {lesion}'
    place = landmark_label(slots.place.value) if slots.place is not None else ''
    return f'{label} at the {place}' if place else label


def group_phrase(slots: Slots) -> str:
    """events.group_label over kinds: what the code's requirement group names - for an examination, its session's
    service (the EUS examination's own label in the EUS family), else its acts' labels joined by 'or'."""
    kinds = slots.group
    if not kinds:
        raise ValueError('The slot group is needed here.')
    if all(kind is Kind.EXAMINATION for kind in kinds):
        if slots.family is SessionKind.EUS:
            return act_label('eus_exam')
        service = SESSION_SERVICES.get(slots.family) if slots.family is not None else None
        return kind_label(service) if service else 'examination'
    return ' or '.join(dict.fromkeys(event_kind_label(kind.value) for kind in kinds))


def _words(slots: Slots, text: str) -> str:
    return span_text(text, slots.words)


def _statement(text: str, slots: Slots, index: int) -> str:
    return span_text(text, slots.statements[index])


# --- the builders: (slots, text) -> (question, reason) ----------------------------------------------------------------


def _conflict(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    return conflict_question(act), conflict_reason(act, _words(s, text), _statement(text, s, 0))


def _conflict_fact(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    said = [span_text(text, statement) for statement in s.statements]
    if len(said) < 2:
        raise ValueError('conflict_fact quotes the statements that disagree: at least two.')
    asked = join([quote(item, 120) for item in said])
    kept = '; '.join(quote(item, 140) for item in said)
    rest = 'Both are kept; neither is chosen.' if len(said) == 2 else 'Each is kept; none is chosen.'
    return (f'Statements in the document disagree about the {act}: {asked}. Which is correct for this encounter?',
            f'Statements in the document disagree about the {act} ({kept}). {rest}')


def _doubt(s: Slots, text: str) -> tuple[str, str]:
    act, words = act_phrase(text, s), _words(s, text)
    return doubt_question(act, words), doubt_reason(act, _statement(text, s, 0) if s.statements else words)


def _scope(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    said = [span_text(text, statement) for statement in s.statements]
    words = _words(s, text) if s.words else ''
    return (scope_question(said[0], act, words, whole=True, also=said[1:]),
            scope_reason(said[0], act, whole=True, also=said[1:]))


def _status(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    return status_question(act, _words(s, text)), status_reason(act)


def _not_documented(s: Slots, text: str) -> tuple[str, str]:
    return performed_question(s.code), not_documented_reason(group_phrase(s))


def _attempted(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    return attempted_question(s.code, act), attempted_reason(act, _words(s, text))


def _unprofiled(s: Slots, text: str) -> tuple[str, str]:
    return performed_question(s.code), not_linked_reason(s.code, True)


def _not_linked(s: Slots, text: str) -> tuple[str, str]:
    return performed_question(s.code), not_linked_reason(s.code, False)


def _recognised_only(s: Slots, text: str) -> tuple[str, str]:
    """events.recognised_only_hold's detail (copied): the family is recognised and listed for review, not assessed."""
    slug = family_slug(_req(s.family, 'family'))
    entry = catalogue.entry(slug)
    needs = tuple(entry.documentation) if entry is not None else ()
    reason = (f'{family_label(slug)} is recognised by CPT Studio and listed for review, not assessed: no service profile '
              f'in this release reconciles {s.code} with the documented acts.'
              + (f' What it needs documented is not checked: {"; ".join(needs)}.' if needs else '') + f' {HELD}')
    return performed_question(s.code), reason


def _unreconciled(s: Slots, text: str) -> tuple[str, str]:
    return (performed_question(s.code),
            f'{s.code} is matched to the documented acts by their place alone: no service profile in this release '
            f'reconciles it with them, so it is never ready for approval (DECISIONS D197). {HELD}')


def _entry(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    return (f'In whose entry is the {act} ({quote(_words(s, text), 120)}) documented: the note of the physician who '
            'performed the procedure, or another entry?',
            f'CPT Studio could not confirm from the document whose entry the {act} is told in.')


def _another_entry(s: Slots, text: str) -> tuple[str, str]:
    """events.another_role_hold's question and detail (copied), its entry named by the owner of the part that tells
    the act; the detail's opening clause (the session's acts listed) is left out."""
    owner = _req(s.owner, 'owner')
    if owner not in OWNER_ENTRIES:
        raise ValueError(f'{owner.value} is no other entry than the documenting clinician\'s.')
    entry, name = OWNER_ENTRIES[owner], service_phrase(s.family)
    what = group_phrase(s) if s.group else act_phrase(text, s)
    passage = f' ({quote(_words(s, text), 120)})'
    return (f'The {what} is documented only in {entry}{passage}. Was it performed in this {name} on the date of '
            'service?',
            f'The {what} this code accounts for is documented only in {entry}{passage}, not by the physician performing '
            f'the {name}. {HELD}')


def _time(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    return time_question(act, _words(s, text)), time_reason(act)


def _time_beside_visit(s: Slots, text: str) -> tuple[str, str]:
    """assess's C-3 question of an undatable procedure beside an E/M (copied)."""
    act = act_phrase(text, s)
    return (time_question(act, _words(s, text)),
            f'{time_reason(act)} A procedure done on the date of service would need a significant, separately '
            'identifiable visit beside it.')


def _performer(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    return performer_question(act, _words(s, text)), performer_reason(act)


def _procedure(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    return procedure_question(act, _words(s, text) if s.words else ''), procedure_reason(act)


def _another_tract(s: Slots, text: str) -> tuple[str, str]:
    """assess._eus_code_hold's D171 (2) tract hold (copied), for either luminal tract. A session placed in the
    pancreatobiliary tract is said by the rule it fails - the code needs it placed in the code's own tract - never as a
    place no code of that tract describes, which would be false of an upper endoscopic ultrasound of the pancreas or
    the bile ducts (recorded as a question)."""
    tract, required = _req(s.tract, 'tract'), _req(s.required_tract, 'required_tract')
    if tract is required or required not in EUS_TRACT_WORDS:
        raise ValueError('another_tract names a session tract other than the code\'s upper or lower tract.')
    place = landmark_label(s.place.value) if s.place is not None else ''
    where = (f'the {place}: ' if place else '') + _whole(_words(s, text))
    needed, placed = EUS_TRACT_WORDS[required], TRACT_PLACES[tract]
    why = (f'which no {required.value} endoscopic ultrasound code describes' if tract in EUS_TRACT_WORDS
           else f'and this code needs it placed in {TRACT_PLACES[required]}')
    return (f'The documented endoscopic ultrasound is placed in {placed} ({where}). Was {needed} performed on the date '
            'of service?',
            f'{s.code} accounts for {needed}; the document places this endoscopic ultrasound in {placed} ({where}), '
            f'{why}. {HELD}')


def _enteroscopy_parts(s: Slots, text: str) -> tuple[str, str, str, str]:
    required = ENTEROSCOPY_CLASS_WORDS[_req(s.enteroscopy_class, 'enteroscopy_class')]
    reached = landmark_label(_req(s.reached, 'reached').value)
    words = _words(s, text) if s.words else ''
    said, shown = (f' ({quote(words)})', f' ({quote(words, 120)})') if words else ('', '')
    return required, reached, said, shown


def _enteroscopy_class(s: Slots, text: str) -> tuple[str, str]:
    """classes.class_hold's class and incomplete forms (copied), with the examination's own route when it is named."""
    required, reached, said, shown = _enteroscopy_parts(s, text)
    if s.incomplete:
        return (f'The documented enteroscopy{shown} is stated to be incomplete. Was {required} performed on the date of '
                'service?',
                f'The enteroscopy is documented as reaching the {reached}{said} and as incomplete; {s.code} accounts '
                f'for {required}, which CPT Studio could not find in the document.')
    way = ('', '')
    if s.approach is not None and s.approach in APPROACH_WORDS and s.approach_words:
        route = span_text(text, s.approach_words)
        way = (f' {APPROACH_WORDS[s.approach]} ({quote(route)})', f' {APPROACH_WORDS[s.approach]} ({quote(route, 120)})')
    return (f'The documented enteroscopy{shown} reached the {reached}{way[1]}. Was {required} performed on the date of '
            'service?',
            f'The enteroscopy is documented as reaching the {reached}{said}{way[0]}; {s.code} accounts for {required}, '
            'which CPT Studio could not find in the document.')


def _enteroscopy_route(s: Slots, text: str) -> tuple[str, str]:
    """classes.class_hold's route form (copied): the route not established beside the encounter's stoma or pouch."""
    required, reached, said, shown = _enteroscopy_parts(s, text)
    names = sorted({APPROACH_ANATOMY[way] for way in s.approaches if way in APPROACH_ANATOMY})
    ways = ' or '.join(f'through the documented {name}' for name in names) or 'through a stoma or pouch'
    also, also_shown = (' and as incomplete', ' and is stated to be incomplete') if s.incomplete else ('', '')
    return (f'The documented enteroscopy{shown} reached the {reached}{also_shown}; CPT Studio could not confirm from the '
            f'document whether it was passed through the mouth or {ways}. Was {required} performed on the date of '
            'service?',
            f'The enteroscopy is documented as reaching the {reached}{said}{also}, and CPT Studio could not confirm from '
            f'the document whether it was passed through the mouth or {ways}; {s.code} accounts for {required}, which '
            'CPT Studio could not find in the document.')


def _method(s: Slots, text: str) -> tuple[str, str]:
    lesion = ' '.join(span_text(text, s.lesion).split()) if s.lesion else ''
    if not lesion:
        place = landmark_label(s.place.value) if s.place is not None else ''
        lesion = f'lesion at the {place}' if place else 'lesion'
    return method_question(lesion), method_reason(group_phrase(s))


def _technique(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    required = TECHNIQUE_WORDS[_req(s.technique, 'technique').value]
    return technique_question(act, _words(s, text)), technique_reason(act, required)


def _stated_technique(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    return technique_question(act, _words(s, text)), technique_unresolved_reason(act)


def _another_technique(s: Slots, text: str) -> tuple[str, str]:
    technique = _req(s.technique, 'technique')
    if s.stated is technique:
        raise ValueError('another_technique names a stated technique other than the code\'s.')
    stated = TECHNIQUE_WORDS[s.stated.value] if s.stated is not None else 'dilation of another technique'
    detail, question = another_technique(service_phrase(s.family), stated, TECHNIQUE_WORDS[technique.value],
                                         _words(s, text))
    return question, detail


def _route_question(s: Slots, text: str) -> tuple[str, str]:
    act, words = act_phrase(text, s), _words(s, text)
    return (act, f'Was the {act} ({_whole(words)}) an EUS-guided transmural injection or fiducial placement, or a '
                 'submucosal injection of the wall?')


def _route(s: Slots, text: str) -> tuple[str, str]:
    act, question = _route_question(s, text)
    return (question, f'{s.code} describes {TRANSMURAL_WORDS}; CPT Studio could not confirm from the document how the '
                      f'{act} reached the tissue. {HELD}')


def _wall_injection(s: Slots, text: str) -> tuple[str, str]:
    """assess._eus_code_hold's D171 (4) hold (copied): the route established submucosal."""
    act, question = _route_question(s, text)
    return (question, f'{s.code} describes {TRANSMURAL_WORDS}; the document describes this {act} as an injection of the '
                      f'wall ({quote(_words(s, text))}), a submucosal injection rather than a transmural one. {HELD}')


def _act_target(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    return target_question(act, _words(s, text)), target_reason(act)


def _site(s: Slots, text: str) -> tuple[str, str]:
    act = act_phrase(text, s)
    return target_question(act, _words(s, text)), site_reason(act, SITE_WORDS[_req(s.site, 'site').value])


def _another_site(s: Slots, text: str) -> tuple[str, str]:
    place = landmark_label(_req(s.place, 'place').value)
    if not place:
        raise ValueError('another_site names a place outside the code\'s site class.')
    detail, question = another_site(service_phrase(s.family), place, SITE_WORDS[_req(s.site, 'site').value],
                                    _words(s, text))
    return question, detail


def _duct(s: Slots, text: str) -> tuple[str, str]:
    act, said = act_phrase(text, s), quote(_words(s, text), 120)
    if s.whole is not None and s.whole_words:
        other = event_kind_label(s.whole.value)
        return (f'Were the {act} ({said}) and the {other} ({quote(span_text(text, s.whole_words), 120)}) done in the '
                'same duct?',
                f'CPT Studio could not confirm from the document that the {act} and the {other} were done in the same '
                'duct.')
    return (f'In which duct was the {act} ({said}) done?',
            f'CPT Studio could not confirm from the document in which duct the {act} was done.')


def _r6(fact: str) -> Callable[[Slots, str], tuple[str, str]]:
    def words(s: Slots, text: str) -> tuple[str, str]:
        label = profile_label(_req(s.family, 'family'))
        return R6_QUESTIONS[fact].format(label=label), R6_REASONS[fact].format(label=label)
    return words


def _setting(s: Slots, text: str) -> tuple[str, str]:
    if s.both:  # R6:context: its text names patient status too when both are missing (4.3)
        label = profile_label(_req(s.family, 'family'))
        return SETTING_AND_STATUS_QUESTION.format(label=label), SETTING_AND_STATUS_REASON.format(label=label)
    return _r6('setting')(s, text)


def _structure(s: Slots, text: str) -> tuple[str, str]:
    reason, question = defining_target_hold(s.code, event_kind_label(_req(s.act, 'act').value), '', _words(s, text))
    return question, reason


def _another_structure(s: Slots, text: str) -> tuple[str, str]:
    place = landmark_label(_req(s.place, 'place').value)
    if not place:
        raise ValueError('another_structure names the place the document gives the act.')
    reason, question = defining_target_hold(s.code, event_kind_label(_req(s.act, 'act').value), place, _words(s, text))
    return question, reason


def _named_stations(stations: Sequence[Station]) -> tuple[str, str]:
    upper = engine_catalogue.UPPER_STATIONS
    named = join([f'the {station.value}' for station in upper if station in stations])
    missing = join([f'the {station.value}' for station in upper if station not in stations])
    return named, missing


def _stations(s: Slots, text: str) -> tuple[str, str]:
    """STATIONS and LIMITED unresolved: which upper-tract stations were examined. Where some stations are established
    examined and not all three, assess's D171 (3) and D177 (4) wording (copied) names them."""
    words = _words(s, text)
    exam_class = s.exam_class or engine_catalogue.EusClass.FULL
    named_in = [station for station in engine_catalogue.UPPER_STATIONS if station in s.stations]
    if exam_class is engine_catalogue.EusClass.FULL and len(named_in) == 1:
        return (f'The documented endoscopic ultrasound examination ({_whole(words)}) names one station only, the '
                f'{named_in[0].value}. Was {FULL_STATIONS_WORDS} performed on the date of service?',
                f'The documented endoscopic ultrasound examination names one station only, the {named_in[0].value} '
                f'({quote(words)}); {s.code} accounts for {FULL_STATIONS_WORDS}, which CPT Studio could not find in the '
                f'document. {HELD}')
    if exam_class is engine_catalogue.EusClass.FULL and 1 < len(named_in) < len(engine_catalogue.UPPER_STATIONS):
        named, missing = _named_stations(named_in)
        return (f'The documented endoscopic ultrasound examination ({_whole(words)}) names {named}, not {missing}. Was '
                f'{FULL_STATIONS_WORDS} performed on the date of service?',
                f'The documented endoscopic ultrasound examination names {named}, not {missing} ({quote(words)}); '
                f'{s.code} accounts for {FULL_STATIONS_WORDS}, which CPT Studio could not find in the document. {HELD}')
    required = FULL_STATIONS_WORDS if exam_class is engine_catalogue.EusClass.FULL else _eus_class_words(s.code,
                                                                                                         exam_class)
    return (f'Which parts of the upper tract (the esophagus, the stomach, the duodenum) were examined in the endoscopic '
            f'ultrasound examination ({quote(words, 120)})?',
            f'{s.code} accounts for {required}; CPT Studio could not confirm from the document which parts of the upper '
            f'tract were examined. {HELD}')


def _station_class(s: Slots, text: str) -> tuple[str, str]:
    """STATIONS and LIMITED established otherwise: a station established not examined (the full class; assess's D171
    (3) wording, copied), or all three established examined (a limited class)."""
    words = _words(s, text)
    if s.denied:
        region = s.denied[0].value
        return (f'The document states that the {region} was not examined ({_whole(words)}). Was {FULL_STATIONS_WORDS} '
                'performed on the date of service?',
                f'The document states that the {region} was not examined ({quote(words)}); {s.code} accounts for '
                f'{FULL_STATIONS_WORDS}, which CPT Studio could not find in the document. {HELD}')
    if all(station in s.stations for station in engine_catalogue.UPPER_STATIONS):
        required = _eus_class_words(s.code, engine_catalogue.EusClass.LIMITED)
        named, _ = _named_stations(s.stations)
        return (f'The documented endoscopic ultrasound examination ({_whole(words)}) names {named}. Was {required} '
                'performed on the date of service?',
                f'The documented endoscopic ultrasound examination names {named} ({quote(words)}); {s.code} accounts '
                f'for {required}, which CPT Studio could not find in the document. {HELD}')
    raise ValueError('station_class names a station established not examined, or all three established examined.')


def _examination_class(s: Slots, text: str) -> tuple[str, str]:
    """wording.examination_class_hold's two forms (copied; equal to it wherever the class words are its own: tested),
    with the class words chosen first - the limited class as CPT states it for 43237 and 43238 (DECISIONS D171 (3)) -
    rather than assess's replacement inside the finished sentence, which also rewrote the document's quoted words when
    they held the class words."""
    exam_class = _req(s.exam_class, 'exam_class')
    required = _eus_class_words(s.code, exam_class)
    reached = landmark_label(_req(s.reached, 'reached').value)
    words = _words(s, text) if s.words else ''
    said, shown = (f' ({quote(words)})', f' ({quote(words, 120)})') if words else ('', '')
    if s.incomplete:
        return (f'The documented endoscopic ultrasound examination{shown} is stated to be incomplete. Was {required} '
                'performed on the date of service?',
                f'The endoscopic ultrasound examination is documented as reaching the {reached}{said} and as incomplete; '
                f'{s.code} accounts for {required}, which CPT Studio could not find in the document.')
    return (f'The documented endoscopic ultrasound examination{shown} reached the {reached}. Was {required} performed '
            'on the date of service?',
            f'The endoscopic ultrasound examination is documented as reaching the {reached}{said}; {s.code} accounts for '
            f'{required}, which CPT Studio could not find in the document.')


def _yield(s: Slots, text: str) -> tuple[str, str]:
    act, words = act_phrase(text, s), _words(s, text)
    return (f'Was any stone, calculus, debris or sludge removed with the {act} ({quote(words, 120)})?',
            f'CPT Studio could not confirm from the document what the {act} retrieved ({quote(words, 140)}). {HELD}')


def _nothing_retrieved(s: Slots, text: str) -> tuple[str, str]:
    """ercp._nothing_retrieved_hold (copied)."""
    act, words = act_phrase(text, s), _words(s, text)
    return (f'Was any stone, calculus, debris or sludge removed with the {act} ({quote(words, 120)})?',
            f'The document states that nothing was retrieved with the {act} ({quote(words, 140)}). CPT Studio does not '
            f'read a sweep or an extraction that retrieved nothing as a removal of stones or debris. {HELD}')


def _part(s: Slots, text: str) -> tuple[str, str]:
    rule = _req(s.bundling, 'bundling')
    kind, part, whole = event_kind_label(_req(s.act, 'act').value), _words(s, text), span_text(text, s.whole_words)
    if rule.value in BUNDLING_QUESTIONS:
        question = bundling_question(rule.value, kind, part, whole)
    elif rule in PART_QUESTIONS:
        question = PART_QUESTIONS[rule].format(act=kind, part=quote(part, 120), whole=quote(whole, 120))
    else:
        raise ValueError(f'{rule.value} is always bundled; nothing about it is asked.')
    return question, bundling_reason(act_phrase(text, s))


def _cause(s: Slots, text: str) -> tuple[str, str]:
    """act_cause unresolved: the causes contract.types.Cause names - an act of this session, a lesion present before
    it, an earlier procedure, or none (spontaneous)."""
    act, said = act_phrase(text, s), quote(_words(s, text), 120)
    other = 'or was the bleeding from a lesion present before it, from an earlier procedure, or spontaneous'
    if s.whole is not None and s.whole_words:
        whole = event_kind_label(s.whole.value)
        question = (f'Did the {whole} ({quote(span_text(text, s.whole_words), 120)}) at this procedure cause the '
                    f'bleeding the {act} ({said}) treated, {other}?')
    else:
        question = f'Did an act of this procedure cause the bleeding the {act} ({said}) treated, {other}?'
    return question, f'CPT Studio could not confirm from the document what caused the bleeding the {act} treated.'


def _bundled(s: Slots, text: str) -> tuple[str, str]:
    """wording.act_included (v1's, unchanged): the explanation naming the whole act's rule."""
    why = BUNDLING_WHY[_req(s.bundling, 'bundling')]
    listed = ('; '.join(dict.fromkeys(event_kind_label(kind.value) for kind in s.listed)) if s.listed
              else act_phrase(text, s))
    detail, question = act_included(service_phrase(s.family), 'performed', listed, why, group_phrase(s),
                                    _words(s, text))
    return question, detail


def _same_day_subject(labels: Sequence[str], possible: Sequence[str]) -> str:
    """checks._same_day_subject (copied)."""
    parts = []
    for items, phrase in ((labels, 'documented as performed on the same date'),
                          (possible, 'possibly performed on the same date (its performance is not established)')):
        if items:
            parts.append(f'{join(items)} {"is" if len(items) == 1 else "are"} {phrase}')
    return '; '.join(parts)


def _separate_em(s: Slots, text: str) -> tuple[str, str]:
    """checks.separate_em_clarification (copied): the question, and same_day_reason over the same-day acts."""
    labels = [event_kind_label(kind.value) for kind in s.listed]
    possible = [event_kind_label(kind.value) for kind in s.possible]
    if not labels and not possible:
        raise ValueError('separate_em names the same-day procedures (listed or possible).')
    subject = _same_day_subject(labels, possible)
    return (SEPARATE_EM_QUESTION, f'{subject[:1].upper()}{subject[1:]}; a significant, separately identifiable E/M '
                                  'service is not established by this document.')


def _separate_em_denied(s: Slots, text: str) -> tuple[str, str]:
    return (SEPARATE_EM_QUESTION, f'The document states that the visit was not a significant, separately identifiable '
                                  f'service beside the procedure ({quote(_words(s, text), 140)}).')


def _base_included(s: Slots, text: str) -> tuple[str, str]:
    """combination.base_hold's act form (copied), each act in doubt marked (classes.IN_DOUBT)."""
    if not s.listed:
        raise ValueError('base_included names the acts in doubt beside the code.')
    included = ', '.join(dict.fromkeys(f'{event_kind_label(kind.value)}{IN_DOUBT}' for kind in s.listed))
    return (BASE_QUESTION.format(code=s.code, included=included),
            f'The documented {service_phrase(s.family)} includes {included}, which this diagnostic code does not '
            f'account for (internal profile rule). {HELD}')


def _base_explained(s: Slots, text: str) -> tuple[str, str]:
    """combination.base_hold (copied): beside the interventions the codes name, or the acts it does not account for."""
    name = service_phrase(s.family)
    if s.codes:
        included = ', '.join(s.codes)
        reason = (f'The documented {name} has interventions that {included} account for; its diagnostic examination is '
                  'normally included in them (internal profile rule; NCCI procedure-to-procedure edits are not '
                  f'connected). {HELD}')
    elif s.listed:
        included = ', '.join(dict.fromkeys(event_kind_label(kind.value) for kind in s.listed))
        reason = (f'The documented {name} includes {included}, which this diagnostic code does not account for '
                  f'(internal profile rule). {HELD}')
    else:
        raise ValueError('base_explained names the codes or the acts beside the code.')
    return BASE_QUESTION.format(code=s.code, included=included), reason


def _base_within(s: Slots, text: str) -> tuple[str, str]:
    """combination.base_within_hold (copied)."""
    within = s.codes
    coded = f', which {", ".join(within)} {"accounts" if len(within) == 1 else "account"} for' if within else ''
    return (f'Is {s.code} reported separately from {", ".join(within) or "the endoscopic ultrasound"} for this '
            'examination?',
            f'The documented {service_phrase(s.family)} is the endoscopic portion of the endoscopic ultrasound '
            f'documented with it{coded}; that examination is normally included in it, not reported separately '
            f'(internal profile rule; NCCI procedure-to-procedure edits are not connected). {HELD}')


def _competing(s: Slots, text: str) -> tuple[str, str]:
    """combination.competing_hold (copied)."""
    codes = join([s.code, *s.codes])
    service = service_phrase(s.family) if s.family is not None else 'service'
    return (f'{codes} are proposed for the same documented act. Reject the code or codes the documentation does not '
            'support; the one left is then ready for review.',
            f'{codes} are each proposed for one same documented act of the {service}. CPT Studio does not choose '
            'between them: each is held for the reviewer, not excluded, until the others are rejected.')


def _service_date(s: Slots, text: str) -> tuple[str, str]:
    said = [span_text(text, statement) for statement in s.statements]
    if len(said) >= 2:
        dates = '; '.join(quote(item, 140) for item in said)
        return (SERVICE_DATE_QUESTION, f'The document states more than one date of service ({dates}); every service and '
                                       'every dated reference check depends on it.')
    return SERVICE_DATE_QUESTION, SERVICE_DATE_REASON


_Q, _E = ItemKind.QUESTION, ItemKind.EXPLANATION
_ACT = ('act', 'words')


def _spec(fact: str, kind: ItemKind, rank: int | None, needs: tuple[str, ...],
          words: Callable[[Slots, str], tuple[str, str]]) -> MessageSpec:
    return MessageSpec(fact, kind, rank, needs, words)


# Every message id's entry (FINAL-V2 4.8's RANK rows; 4.3's unmet and established-otherwise columns).
MESSAGES: Mapping[Message, MessageSpec] = MappingProxyType({
    Message.CONFLICT: _spec('conflict', _Q, 1, _ACT + ('statements',), _conflict),
    Message.CONFLICT_FACT: _spec('conflict', _Q, 1, ('act', 'statements'), _conflict_fact),
    Message.DOUBT: _spec('performed_status', _Q, 2, _ACT, _doubt),
    Message.STATEMENT_SCOPE: _spec('statement_scope', _Q, 3, ('act', 'statements'), _scope),
    Message.STATUS: _spec('performed_status', _Q, 4, _ACT, _status),
    Message.NOT_DOCUMENTED: _spec('performed_status', _Q, 4, ('code', 'group'), _not_documented),
    Message.ATTEMPTED: _spec('performed_status', _E, 4, ('code',) + _ACT, _attempted),
    Message.UNPROFILED: _spec('performed_status', _E, 4, ('code',), _unprofiled),
    Message.NOT_LINKED: _spec('performed_status', _E, 4, ('code',), _not_linked),
    Message.RECOGNISED_ONLY: _spec('performed_status', _E, 4, ('code', 'family'), _recognised_only),
    Message.UNRECONCILED: _spec('performed_status', _E, 4, ('code',), _unreconciled),
    Message.ENTRY: _spec('event_entry', _Q, 5, _ACT, _entry),
    Message.ANOTHER_ENTRY: _spec('event_entry', _E, 5, _ACT + ('owner', 'family'), _another_entry),
    Message.TIME: _spec('event_time', _Q, 6, _ACT, _time),
    Message.TIME_BESIDE_VISIT: _spec('event_time', _Q, 6, _ACT, _time_beside_visit),
    Message.PERFORMER: _spec('event_performer', _Q, 7, _ACT, _performer),
    Message.PROCEDURE: _spec('procedure', _Q, 8, ('act',), _procedure),
    Message.ANOTHER_TRACT: _spec('procedure', _E, 8, ('code', 'words', 'tract', 'required_tract'), _another_tract),
    Message.ENTEROSCOPY_ROUTE: _spec('procedure', _Q, 8, ('code', 'enteroscopy_class', 'reached'), _enteroscopy_route),
    Message.ENTEROSCOPY_APPROACH: _spec('procedure', _E, 8, ('code', 'enteroscopy_class', 'reached', 'approach',
                                                             'approach_words'), _enteroscopy_class),
    Message.METHOD: _spec('act_method', _Q, 9, ('group',), _method),
    Message.TECHNIQUE: _spec('technique', _Q, 10, _ACT + ('technique',), _technique),
    Message.STATED_TECHNIQUE: _spec('technique', _Q, 10, _ACT, _stated_technique),
    Message.ANOTHER_TECHNIQUE: _spec('technique', _E, 10, ('words', 'technique', 'family'), _another_technique),
    Message.ROUTE: _spec('technique', _Q, 10, ('code',) + _ACT, _route),
    Message.WALL_INJECTION: _spec('technique', _E, 10, ('code',) + _ACT, _wall_injection),
    Message.ACT_TARGET: _spec('act_target', _Q, 11, _ACT, _act_target),
    Message.SITE: _spec('act_target', _Q, 11, _ACT + ('site',), _site),
    Message.ANOTHER_SITE: _spec('act_target', _E, 11, ('words', 'place', 'site', 'family'), _another_site),
    Message.DUCT: _spec('act_target', _Q, 11, _ACT, _duct),
    Message.TARGET: _spec('target', _Q, 12, ('family',), _r6('target')),
    Message.STRUCTURE: _spec('target', _Q, 12, ('code',) + _ACT, _structure),
    Message.ANOTHER_STRUCTURE: _spec('target', _E, 12, ('code',) + _ACT + ('place',), _another_structure),
    Message.STATIONS: _spec('exam_stations', _Q, 13, ('code', 'words'), _stations),
    Message.STATION_CLASS: _spec('exam_stations', _E, 13, ('code', 'words'), _station_class),
    Message.EXTENT: _spec('extent', _Q, 14, ('family',), _r6('extent')),
    Message.EXAMINATION_CLASS: _spec('extent', _E, 14, ('code', 'exam_class', 'reached'), _examination_class),
    Message.ENTEROSCOPY_CLASS: _spec('extent', _E, 14, ('code', 'enteroscopy_class', 'reached'), _enteroscopy_class),
    Message.YIELD: _spec('act_yield', _Q, 15, _ACT, _yield),
    Message.NOTHING_RETRIEVED: _spec('act_yield', _E, 15, _ACT, _nothing_retrieved),
    Message.CANNULATION: _spec('cannulation', _Q, 16, ('family',), _r6('cannulation')),
    Message.PART: _spec('act_part', _Q, 17, _ACT + ('whole_words', 'bundling'), _part),
    Message.BUNDLING_TARGET: _spec('act_target', _Q, 17, _ACT + ('whole_words', 'bundling'), _part),
    Message.CAUSE: _spec('act_cause', _Q, 17, _ACT, _cause),
    Message.BUNDLED: _spec('performed_status', _E, 18, _ACT + ('family', 'group', 'bundling'), _bundled),
    Message.EM_BASIS: _spec('em_basis', _Q, 19, ('family',), _r6('em_basis')),
    Message.SEPARATE_EM: _spec('separate_em', _Q, 20, (), _separate_em),
    Message.SEPARATE_EM_DENIED: _spec('separate_em', _E, 20, ('words',), _separate_em_denied),
    Message.BASE_INCLUDED: _spec('base_included', _Q, 21, ('code', 'listed'), _base_included),
    Message.BASE_EXPLAINED: _spec('base_included', _E, 21, ('code',), _base_explained),
    Message.BASE_WITHIN: _spec('base_included', _E, 21, ('code',), _base_within),
    Message.COMPETING: _spec('competing_codes', _Q, 22, ('code', 'codes'), _competing),
    Message.SETTING: _spec('setting', _Q, 23, ('family',), _setting),
    Message.PATIENT_STATUS: _spec('patient_status', _Q, 23, ('family',), _r6('patient_status')),
    Message.SERVICE_DATE: _spec('service_date', _Q, None, (), _service_date),
})


def fact_key(message: Message, slots: Slots) -> str:
    """The questions.FORM fact key of ``message``'s item: conflict:<the act's kind> for a conflict (RANK's rank 1),
    else MESSAGES' fact."""
    spec = MESSAGES[message]
    return f'conflict:{_req(slots.act, "act").value}' if spec.fact == 'conflict' else spec.fact


def build(message: Message, slots: Slots, text: str) -> Worded:
    """The item of ``message`` in CPT Studio's words, from ``slots`` and the revision ``text`` (FINAL-V2 4.8): its fact
    key, kind, question and reason. ValueError - never a fallback sentence - when ``message`` is not a Message, a slot
    the message needs is empty, a span it quotes holds no words or reaches past the text, or the slots contradict the
    message (an explanation of a misfit naming a fit)."""
    if not isinstance(message, Message):
        raise ValueError(f'{message!r} is not a message id.')
    if not isinstance(slots, Slots) or not isinstance(text, str):
        raise ValueError('An item is built from Slots and the revision text.')
    spec = MESSAGES[message]
    for name in spec.needs:
        value = getattr(slots, name)
        if value is None or value == '' or value == ():
            raise ValueError(f'{message.value} needs the slot {name}.')
        if name in _SPAN_FIELDS and not span_text(text, value).strip():
            raise ValueError(f'{message.value} quotes {name}, whose spans hold no words.')
        if name == 'statements' and not all(span_text(text, statement).strip() for statement in value):
            raise ValueError(f'{message.value} quotes statements, and one holds no words.')
    question, reason = spec.words(slots, text)
    return Worded(message, fact_key(message, slots), spec.kind, question, reason)


def question(message: Message, slots: Slots, text: str) -> str:
    """The question builder: what the member is asked about ``message``'s item (build's question)."""
    return build(message, slots, text).question


def explanation(message: Message, slots: Slots, text: str) -> str:
    """The explanation builder: why the code is held (build's reason) - the explanation of an explanation item, the
    reason of a question."""
    return build(message, slots, text).reason
