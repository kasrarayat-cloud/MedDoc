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
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Sequence

from studio.gi import catalogue, profiles
from studio.interpretation import ENGINE_VERSION
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

NEW_FACTS = ('event_time', 'event_performer', 'act_target', 'technique', 'statement_scope', 'act_method', 'procedure')
MISSING = {
    'event_time': 'whether the act was done at this encounter',
    'event_performer': 'who performed the act',
    'act_target': 'which lesion or site the act was done on',
    'technique': 'which technique was used',
    'statement_scope': 'whether a statement in the document applies to this act',
    'act_method': 'by which method the lesion was removed',
    'procedure': 'in which procedure the act was done',
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


def scope_question(statement: str, act: str, words: str = '', whole: bool = False) -> str:
    """FINAL 7.4 h3 (scope) and ADJUDICATION C-10: whether a statement applies to an act. ``whole`` (DECISIONS D103,
    h3's question): the statement is quoted uncut - it is one passage, which the read bounds to 600 characters - so the
    words that make it a denial are never cut off the end of a long sentence."""
    said = quote(statement, len(statement) + 1) if whole else quote(statement, 120)
    if words:
        return f'Does {said} apply to the {act} ({quote(words, 120)})?'
    return f'Does {said} apply to the {act} this code accounts for?'


def scope_reason(statement: str, act: str, whole: bool = False) -> str:
    said = quote(statement, len(statement) + 1) if whole else quote(statement, 140)
    return (f'The document states {said}; CPT Studio could not confirm from the document whether that statement '
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
