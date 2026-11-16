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
catalogue and types, for its slot types; and, since D225, the engine's text-free anatomy for one refusal -
STRUCTURE_PLACE refuses a place that STRUCT:pfc does not set apart, by the engine's own ``in_regions`` over the
catalogue's DEFINING_TARGET_APART, so the sentence and the rule it explains read one region table. It reads no document
text for it.

**D225** (DECISIONS; repair r3c of step 3c, for refute-4a-r2 P5, P6, P7, P10 and P11): six ids join Message, each with
its builder, and three fields join Slots (attribute, unlisted_what, unlisted_kind) - every earlier id, field and
sentence is unchanged. A contradicted attribute other than the status is a conflict about that attribute
(CONFLICT_ATTRIBUTE), 3.2.6 rule 2's item names the unlisted entry's kind and quotes its own unit (UNLISTED_EVIDENCE),
LOWER's stoma class asks its approach (EXAMINATION_ROUTE) and explains another one (EXAMINATION_APPROACH), XCHG's
two-act duct question names the act whose duct is unknown (SAME_DUCT), and STRUCT:pfc's explanation names the place it
sets apart (STRUCTURE_PLACE). The engine's mirror (engine/questions.MessageId and Fill) is step r4a's. A conflict about
a session's attribute is about the session, named by its service (``family``), never about the act the item names, whose
kind only keys the fact (SESSION_ATTRIBUTES); and the act's label never states the contested value
(CONTESTED_LABEL_PARTS) - the second round of repair r3c (refute-r3c-r1 P1, P6).

**D246** (DECISIONS; repair r3c of the waves 5-6 rulings, wording's half of "every item the engine makes is worded":
the lead's L1, refute-5c-r2 R2-03, r4a Q4 and R4): forms and one id are added, and every earlier id, field, constant and
sentence keeps its text - MESSAGES' ``needs`` relax only for the four ids that gain a form (DOUBT, STATEMENT_SCOPE,
SAME_DUCT, BASE_INCLUDED), whose builders refuse what is still left unworded. BASE_INCLUDED names the codes beside the
base code when no act is in doubt (``listed`` empty,
``codes`` given), and SEPARATE_EM the same-day codes when the procedure day has no act to list (``listed`` and
``possible`` empty, ``codes`` given): each sentence states only that the codes are proposed, never that an act they
account for was done. DOUBT, SAME_DUCT and STATEMENT_SCOPE name an act, or a statement, that has no units (its spans
``()``) without a quote - D160 (3)'s rule, which procedure_question already follows: empty words are never quoted (r4a Q4
option (a)); units that hold no words are still refused, a binding failure. SYNTHETIC_ACT (rank 2, performed_status, a
question) words 3.2.6 rule 3's synthetic act - an act the document states that CPT Studio's reading does not account for
- by its own kind ('an act' when it names none) and its own unit, so the act is never said to be in doubt, which DOUBT's
sentence says and which is untrue of an act the document states (r4a R4 (a)). Step r4a maps the synthetic act's witness
to it and mirrors the id in engine/questions.MessageId.

**D254, D257, D258** (DECISIONS; repair r3c of round w8r - every slot an item can carry has a true form for its
absence): every builder words every value its slots can hold. MESSAGES' ``needs`` name only the slots every item of the
message carries by construction - the held code, the R6 label's family, a conflict's act and attribute, an unlisted
entry's nature, the stoma EUS class - each with its reason in CARRIED; ``build`` refuses one of those left empty, or a
span the revision holds no words at (a binding failure), and nothing else: every other slot has its absence form, and a
value the message's own fact contradicts is worded as its absence (rule 1). An act no kind names (Kind.OTHER, or a kind
not established) is NO_KIND_LABEL, 'another act', its article included, wherever a kind is turned into words (rule 2;
the requirement group names only kinds that name an act). ENTEROSCOPY_APPROACH without an approach names no route, and
BASE_INCLUDED, BASE_EXPLAINED and SEPARATE_EM have a true form with nothing to name (rule 3). BASE_WITHIN names the whole
by its own family (``whole_family``) and a whole only possibly done (``whole_possible``) as possibly performed on the
date of service, its performance not established (D257: two optional Slots fields, appended). UNLISTED_SCOPE (rank 2,
performed_status, a question) asks whether the held session's examination is documented as done, quoting a statement that
names no procedure session, never saying the examination is in doubt or denied (D258); ENTEROSCOPY_THROUGH (rank 8,
procedure, a question) asks an enteroscopy's route part when only the anatomy it was passed through is unknown (D253 QX
(ii)). Both ids are appended; step r4a maps the holds to them and mirrors them in engine/questions.MessageId, and the two
Slots fields in its Fill.

**D266, D267** (DECISIONS; repair r3c of round w9r - a denial is worded as a denial, and one label and only known words
in every item): DOUBT words an unlisted DENIAL (``unlisted_what``, which step r4a fills for a carded entry as for one
with no card), of any kind or none, as a statement that the act was not done (D266's DENIAL_STATED; since D281, a
statement that an act was not done, DENIAL_SCOPE, its bearing on the act not asserted), quoting the denial and
never saying the document leaves the act in doubt; an ACT there reads as SYNTHETIC_ACT's sentence over the entry's own
kind. UNLISTED_SCOPE and DOUBT keep a true form with no quote of the examination for a Fill that gives none (step r4a
quotes it only when that examination is possibly done on the date of service). BUNDLED with a requirement group that
names no act words the code itself, as NOT_DOCUMENTED and METHOD do. A route the Fill marks as only possible - the new
optional Slots field ``possible_approaches``, appended: a doubted or unresolved through, or an anatomy entry whose type is
not established - is worded as possible, "possibly through a pouch or a stoma" (ENTEROSCOPY_ROUTE), or as a stoma not
established (EXAMINATION_ROUTE), never "the documented stoma" or "the documented pouch" (refute-r4a-r2 F5; D254 rule
1); step r4a fills it (classes.doubted_routes) and mirrors it in its Fill. customer_api.held_fact_words (step r3c's
other file) words 'conflict:other' as 'another act' and a procedure-keyed held fact by the item's message.

**D280-D284** (DECISIONS; step f3w of AMENDMENT-2's build round, which owns the whole module by D291 - build list B1,
B3, B5, B6, B7): two ids are appended and two optional Slots fields; every earlier id, field and constant keeps its
place. DIGITAL_SCOPE (D280.3) words every hold resting on an examination whose device claims manual without establishing
it as D258 asks: the held session's examination by its service, quoting its own words (``words``: only an examination
that may be quoted, never the claimed one), asked whether it is "documented as performed, in full or in part, on the
date of service" (DONE_IN_PART); the reason quotes the claimed examination's own words (``statements``' first) as a
statement whose technique CPT Studio could not confirm, and states its open fact - by the held fact's RANK row
(``held``) and attribute: not established as done on the date of service, its date or its performer not established,
told only in another role's entry (``owner``), left in doubt, the document's statements about it disagreeing (its sides,
``statements``' rest), more than one technique stated (``techniques``); with no attribute (a pair whose statement it
is), whether it is about that examination. Its clarification keeps the held fact's key: fact_key reads it from
``held`` (one RANK row, one key) and, for a conflict, ``act`` (engine/questions.py, step f3w's, mirrors the id and both
fields). ADDON (D284, G3-15) words an add-on held by its ADDON row from ``code`` and ``codes`` alone - none of its
primary codes is counted for this encounter -, quoting nothing and asking no fact of the add-on's act, with a true form
for no codes. D281: DOUBT words a rule-4 DENIAL as a statement that an act was not done whose bearing on the act
CPT Studio could not confirm (B5, G3-10), never "states that <the act> was not done"; DOUBT's question about the held
session's examination (an examination named by its service) and UNLISTED_SCOPE's say row 7's done, DONE_IN_PART (B6,
G3-27); and ANOTHER_ENTRY names the code's group ("this code accounts for") only for the code's own act, a session's
examination with no group by the item's act (B3, G1-05 (ii)).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, replace
from datetime import date
from enum import Enum, unique
from types import MappingProxyType
from typing import Optional, Sequence, TypeVar

from studio.gi import catalogue, profiles
from studio.interpretation import ENGINE_VERSION
from studio.interpretation.contract.types import (Approach, Attribute, Device, Extent, Kind, Landmark, Owner,
                                                  SessionKind, Span, Station, Tract, UnlistedWhat)
from studio.interpretation.engine import anatomy as engine_anatomy
from studio.interpretation.engine import catalogue as engine_catalogue
from studio.interpretation.engine import requirements as engine_requirements
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
    # D225 (repair r3c; refute-4a-r2 P5, P6, P7, P10, P11): appended, so every earlier member keeps its place
    CONFLICT_ATTRIBUTE = 'conflict_attribute'  # 1 Q: a contradicted attribute, named, each side's own sentence quoted
    UNLISTED_EVIDENCE = 'unlisted_evidence'  # 2 Q: 3.2.6 rule 2, the unlisted entry's kind named and its unit quoted
    EXAMINATION_ROUTE = 'examination_route'  # 8 Q: LOWER's stoma class, its approach not established
    EXAMINATION_APPROACH = 'examination_approach'  # 8 E: LOWER's stoma class, another approach established
    SAME_DUCT = 'same_duct'  # 11 Q: XCHG, two acts, naming the act whose duct is not established
    STRUCTURE_PLACE = 'structure_place'  # 12 E: STRUCT:pfc, the biliary or hepatic place it sets apart named
    # D246 (repair r3c; r4a R4 (a)): appended, so every earlier member keeps its place
    SYNTHETIC_ACT = 'synthetic_act'  # 2 Q: 3.2.6 rule 3's synthetic act, its own kind named and its own unit quoted
    # D258 and D253 QX (ii) (repair r3c of round w8r): appended, so every earlier member keeps its place
    UNLISTED_SCOPE = 'unlisted_scope'  # 2 Q: a statement naming no procedure session, the held session's examination asked
    ENTEROSCOPY_THROUGH = 'enteroscopy_through'  # 8 Q: ENT's route part, only the anatomy passed through not established
    # D280.3 and D284 (step f3w of AMENDMENT-2's build round): appended, so every earlier member keeps its place
    DIGITAL_SCOPE = 'digital_scope'  # Q, the held fact's own key and rank: a claimed digital examination's hold
    ADDON = 'addon'  # 4 Q: an add-on its ADDON row holds, from codes alone (TEXT_FREE)


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
    both missing. attribute (D225): the attribute a contradicted fact is about (the held fact's own). unlisted_what,
    unlisted_kind (D225): what an unlisted entry is (an act, a denial or a doubt) and its kind, None when the entry
    names none (3.2.6: events.unlisted's what and kind). whole_family, whole_possible (D257, repair r3c of round w8r):
    the family of the session a base-within hold's code is (possibly) part of - BASE_WITHIN names that whole by it - and
    whether that whole is only possibly done, not established (its sentence then states it as possibly performed on the
    date of service, its performance not established). possible_approaches (D267, repair r3c of round w9r; refute-r4a-r2
    F5): the routes the encounter's anatomy only possibly opens - a doubted or unresolved through, or an anatomy entry
    whose type is not established (engine/classes.doubted_routes) - each worded as possible (ENTEROSCOPY_ROUTE), or as
    not established (EXAMINATION_ROUTE), never as "the documented stoma" or "the documented pouch"; ``approaches`` holds
    the routes it establishes (classes.routes). A route in both is worded as possible: the sentence never states more
    than the marker allows. held, techniques (D280.3, step f3w of AMENDMENT-2's build round): the RANK row of the held
    fact a DIGITAL_SCOPE item rests on - its clarification keeps that fact's key (fact_key: the row's one fact key, or
    conflict:<act>), and its reason states the open fact the row and ``attribute`` name -, and whether the document
    states more than one technique for the examination it quotes (an overfilled or contradicted device).

    D254 rule 1: a builder refuses only when a slot every item of its message carries by construction is missing
    (MESSAGES' ``needs``, each with its reason in CARRIED); every other slot has a form for its absence.

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
    attribute: Attribute | None = None
    unlisted_what: UnlistedWhat | None = None
    unlisted_kind: Kind | None = None
    whole_family: SessionKind | None = None
    whole_possible: bool = False
    possible_approaches: tuple[Approach, ...] = ()
    held: engine_requirements.Rank | None = None
    techniques: bool = False

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
    'attribute': (Attribute, False), 'unlisted_what': (UnlistedWhat, False), 'unlisted_kind': (Kind, False),
    'whole_family': (SessionKind, False), 'whole_possible': (bool, False), 'possible_approaches': (Approach, True),
    'held': (engine_requirements.Rank, False), 'techniques': (bool, False),
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
    the Slots fields every item of the message carries by construction (D254 rule 1; CARRIED gives each one's reason) -
    the only slots it is never worded without; words, its builder: (slots, revision text) -> (question, reason)."""
    fact: str
    kind: ItemKind
    rank: int | None
    needs: tuple[str, ...]
    words: Callable[[Slots, str], tuple[str, str]]


# --- labels over slots ----------------------------------------------------------------------------------------------
#
# D254 rule 2 (repair r3c of round w8r): an act no kind names - Kind.OTHER, or a kind not established (``act`` None) -
# has one label wherever these builders turn a kind into words: NO_KIND_LABEL, 'another act'. Its article is part of
# it, so no builder puts 'the', 'a' or 'this' before it (``_the``, ``_this``, ``_a``), and a sentence that starts with
# it reads "Another act ...". A requirement group - what the code accounts for, never an act of the document - names
# only its kinds that name an act (group_phrase), and a builder whose group names none words the code instead.

NO_KIND_LABEL = 'another act'


def named_kind(kind: Kind | None) -> bool:
    """Whether ``kind`` names an act (D254 rule 2): every Kind but OTHER; None, a kind not established, names none."""
    return kind is not None and kind is not Kind.OTHER


def kind_words(kind: Kind | None) -> str:
    """``kind`` in words: its event_kind_label, else NO_KIND_LABEL (its article included) for an act no kind names."""
    return event_kind_label(kind.value) if kind is not None and kind is not Kind.OTHER else NO_KIND_LABEL


def _the(label: str, named: bool) -> str:
    """``label`` after 'the', or alone when it is an act no kind names (its article is part of NO_KIND_LABEL)."""
    return f'the {label}' if named else label


def _this(label: str, named: bool) -> str:
    return f'this {label}' if named else label


def _a(label: str, named: bool) -> str:
    return with_article(label) if named else label


def _capital(text: str) -> str:
    """A sentence's first letter capitalized (CPT Studio's own label, which opens the sentence)."""
    return text[:1].upper() + text[1:]


def _act_label(text: str, kind: Kind | None, family: SessionKind | None, device: Device | None,
               lesion: tuple[Span, ...], place: Landmark | None) -> str:
    """act_phrase's label from its parts (CONFLICT_ATTRIBUTE leaves out the parts a conflict contests, by passing
    them empty)."""
    if kind is Kind.EXAMINATION:
        service = SESSION_SERVICES.get(family) if family is not None else None
        label = kind_label(service) if service else 'examination'
    else:
        label = kind_words(kind)
    if device is not None and device not in (Device.ENDOSCOPE, Device.OTHER):
        named = landmark_label(device.value)
        if named and named not in label:
            label = f'{label} ({named})'
    lesion_words = ' '.join(span_text(text, lesion).split()) if lesion else ''
    if lesion_words:
        return f'{label} of the {lesion_words}'
    where = landmark_label(place.value) if place is not None else ''
    return f'{label} at the {where}' if where else label


def act_phrase(text: str, slots: Slots) -> str:
    """events.event_label over text-free facts: the act's label (an examination's is its session's service), its device
    where the label does not name it, then 'of the' its lesion's own words, else 'at the' its place. D254 rule 2: an act
    no kind names (Kind.OTHER, or ``act`` None: a kind not established) is labelled NO_KIND_LABEL, 'another act'."""
    return _act_label(text, slots.act, slots.family, slots.device, slots.lesion, slots.place)


def the_act(text: str, slots: Slots) -> str:
    """act_phrase with its article: 'the <label>', or the label alone for an act no kind names (D254 rule 2)."""
    return _the(act_phrase(text, slots), named_kind(slots.act))


def group_phrase(slots: Slots) -> str:
    """events.group_label over kinds: what the code's requirement group names - for an examination, its session's
    service (the EUS examination's own label in the EUS family), else its acts' labels joined by 'or'. D254: only the
    kinds that name an act; '' when the group names none (each builder then words the code instead)."""
    kinds = tuple(kind for kind in slots.group if named_kind(kind))
    if not kinds:
        return ''
    if all(kind is Kind.EXAMINATION for kind in kinds):
        if slots.family is SessionKind.EUS:
            return act_label('eus_exam')
        service = SESSION_SERVICES.get(slots.family) if slots.family is not None else None
        return kind_label(service) if service else 'examination'
    return ' or '.join(dict.fromkeys(event_kind_label(kind.value) for kind in kinds))


def _unit_words(text: str, spans: tuple[Span, ...], message: str, name: str) -> str:
    """The words at an act's or a statement's units, '' when it has no units (D246; D160 (3): an act or a statement with
    no units is named without a quote, never with an empty one). Units that hold no words are refused: every item's spans
    are units of the revision it was made on (segment's units are trimmed and never empty; the store refuses words that
    are not the revision's slice), so a span the revision holds no words at is a binding failure, never a shorter quote."""
    if not spans:
        return ''
    words = span_text(text, spans)
    if not words.strip():
        raise ValueError(f'{message} quotes {name}, whose spans hold no words.')
    return words


def _words(slots: Slots, text: str, message: str = 'an item') -> str:
    """The act's own statement (``words``), '' when it has no units."""
    return _unit_words(text, slots.words, message, 'words')


def _sides(text: str, statements: tuple[tuple[Span, ...], ...], message: str) -> list[str]:
    """Each statement's words, in order: a statement with no units left out, the same words (whitespace aside) once."""
    found = (_unit_words(text, statement, message, 'statements') for statement in statements)
    return list(dict.fromkeys(' '.join(item.split()) for item in found if item))


def _shown(words: str, limit: int = 120) -> str:
    """' (“words”)' after a label, cut at ``limit``; '' for no words (D160 (3): nothing quoted, no empty brackets)."""
    return f' ({quote(words, limit)})' if words else ''


def _whole_shown(words: str) -> str:
    """' (“words”)' uncut (assess._whole); '' for no words."""
    return f' ({_whole(words)})' if words else ''


def _reach(slots: Slots) -> str:
    """The reached point's label; '' when none is given, or the point names no place (Extent.OTHER)."""
    return landmark_label(slots.reached.value) if slots.reached is not None else ''


# --- the builders: (slots, text) -> (question, reason) ----------------------------------------------------------------
#
# D254 rule 1 (repair r3c of round w8r): each builder words every value its slots can hold; it requires only the slots
# MESSAGES' ``needs`` name (CARRIED gives each one's reason). A slot left empty gets its absence form, true for its state
# and naming nothing CPT Studio does not know: no quote for an act or a statement with no units, NO_KIND_LABEL for an
# act no kind names, the code for a requirement group that names no act, no clause for a reach, a route, a place or a
# technique that is not given. A slot whose value the message cannot name truly - a tract, a station, a place, an
# approach or a stated technique that the message's own established fact contradicts - is worded as its absence: the
# sentence states the message's fact and never that value.

_HOLD_RULE = '(internal profile rule; NCCI procedure-to-procedure edits are not connected)'


def _conflict(s: Slots, text: str) -> tuple[str, str]:
    """FINAL 7.4 h1 (v1's conflict_question and conflict_reason, worded through the_act): the act's own sentence and the
    first statement with units, each quoted when it has units."""
    act = the_act(text, s)
    done = _words(s, text, 'conflict')
    denied = next(iter(_sides(text, s.statements, 'conflict')), '')
    return (f'The record states {act} both as performed and as not performed. Which is correct for this encounter?',
            f'One statement documents {act} as done{_shown(done, 140)}; another states it was not done'
            f'{_shown(denied, 140)}. Both are kept; neither is chosen.')


def _conflict_fact(s: Slots, text: str) -> tuple[str, str]:
    """A contradicted fact: the statements that disagree, each quoted once; with one statement (or none) with units,
    CONFLICT_ATTRIBUTE's one-sentence form (or its form with nothing quoted) about the act."""
    act = the_act(text, s)
    said = _sides(text, s.statements, 'conflict_fact')
    if not said:
        return (f'The document is not consistent about {act}. Which is correct for this encounter?',
                f'The document is not consistent about {act}. Each value it states is kept; none is chosen.')
    if len(said) == 1:
        return (f'The document is not consistent about {act} ({quote(said[0], 120)}). Which is correct for this '
                'encounter?',
                f'The document is not consistent about {act} ({quote(said[0], 140)}). Each value it states is kept; '
                'none is chosen.')
    asked = join([quote(item, 120) for item in said])
    kept = '; '.join(quote(item, 140) for item in said)
    rest = 'Both are kept; neither is chosen.' if len(said) == 2 else 'Each is kept; none is chosen.'
    return (f'Statements in the document disagree about {act}: {asked}. Which is correct for this encounter?',
            f'Statements in the document disagree about {act} ({kept}). {rest}')


def _doubt(s: Slots, text: str) -> tuple[str, str]:
    """The act's status in doubt (rank 2): v1's doubt_question over the act's own words and doubt_reason over the doubt's
    passage (its first statement with units), else the act's words. D246 (r4a Q4 option (a); D160 (3)): an act with no
    units is named without a quote, and so is the reason's passage when neither has units - never an empty quote.

    D266 (repair r3c of round w9r; refute-r3c-r1 F3): the reason words the unlisted entry the hold rests on by its own
    nature (``unlisted_what``, which step r4a fills for a carded entry as for one with no card). A DENIAL - carded or
    not, of any kind or none - is a statement that an act was not done (DENIAL_SCOPE, D281 below), quoting the denial:
    its first statement with units, never the act's own sentence, which states the act; with none, nothing is quoted.
    It is never said to leave the act in doubt. An ACT (no Fill gives DOUBT one: step r4a words 3.2.6 rule 3's
    synthetic act by SYNTHETIC_ACT) is SYNTHETIC_ACT's sentence over the entry's own kind (``unlisted_kind``) and
    statement, never "in doubt" (D246). A DOUBT, or no entry named, reads as before. The question is v1's in every case: whether the act was
    done (D266's first half: the act's own sentence is quoted only when the Fill gives it).

    D281 (step f3w; build list B5, G3-10): every DOUBT whose entry is a DENIAL comes from 3.2.6 rule 4's pair, unresolved
    statement_scope by construction, so its reason never asserts the denial's scope: "The document states “<denial>”, a
    statement that an act was not done (DENIAL_SCOPE); CPT Studio could not confirm from the document whether it is about
    <the act>." - with no statement units, "The document states that an act was not done; ...". Never "states that <the
    act> was not done", and never "leaves ... in doubt". And (B6, G3-27) where the question asks whether the held
    session's examination was done - the act an examination named by its service (``family`` given) - it says row 7's
    done: "is documented as performed, in full or in part, on the date of service" (DONE_IN_PART), true of a begun
    examination too; every other act keeps v1's question."""
    act = the_act(text, s)
    words = _words(s, text, 'doubt')
    if s.act is Kind.EXAMINATION and s.family is not None:  # the held session's examination (B6): row 7's done
        question = f'Confirm whether {act}{_shown(words)} is {DONE_IN_PART}.'
    else:
        question = f'Confirm whether {act}{_shown(words)} was done on the date of service.'
    stated = next(iter(_sides(text, s.statements, 'doubt')), '')
    if s.unlisted_what is UnlistedWhat.DENIAL:  # B5: a statement that an act was not done, its scope not asserted
        about = f'CPT Studio could not confirm from the document whether it is about {act}'
        return question, (f'The document states {quote(stated, 140)}, {DENIAL_SCOPE}; {about}.' if stated
                          else f'The document states that an act was not done; {about}.')
    if s.unlisted_what is UnlistedWhat.ACT:
        kind = _a(kind_words(s.unlisted_kind), named_kind(s.unlisted_kind))
        return question, f'The document documents {kind}{_shown(stated, 140)}, {SYNTHETIC_UNACCOUNTED}.'
    passage = stated or words
    reason = f'The document leaves {act} in doubt: {quote(passage, 140)}.' if passage else \
        f'The document leaves {act} in doubt.'
    return question, reason


# D281 (step f3w; build list B5, G3-10), replacing D266's DENIAL_STATED ('states that {act} was not done', untrue of a
# rule-4 denial whose scope is unresolved): what DOUBT's reason calls an unlisted denial - a statement that AN act was not
# done; which act it is about is the open fact the reason states after it
DENIAL_SCOPE = 'a statement that an act was not done'
# D281 (B6, G3-27): row 7's done, as a question about the held session's examination says it (a begun examination is
# done for row 7: evaluate._done_rows, combination.session_done) - UNLISTED_SCOPE, the session's DOUBT and DIGITAL_SCOPE
DONE_IN_PART = 'documented as performed, in full or in part, on the date of service'


def _scope(s: Slots, text: str) -> tuple[str, str]:
    """Whether a statement applies to the act (rank 3): v1's scope_question and scope_reason (every statement quoted
    uncut, DECISIONS D103; the act's own words quoted when it has units, else "this code accounts for"). D246: a
    statement with no units is named, never quoted; with none that has units, the statement is the document's,
    unquoted."""
    act = the_act(text, s)
    said = _sides(text, s.statements, 'statement_scope')
    words = _words(s, text, 'statement_scope')
    applies = f'{act}{_shown(words)}' if words else f'{act} this code accounts for'
    if not said:
        return (f'Does a statement in the document apply to {applies}?',
                f'CPT Studio could not confirm whether a statement in the document applies to {act}.')
    quoted = [quote(item, len(item) + 1) for item in said]
    asked = quoted[0] if len(quoted) == 1 else ', '.join(quoted[:-1]) + ' or ' + quoted[-1]
    if len(quoted) > 1:  # DECISIONS D126: every statement the question asks about
        reason = (f'The document states {join(quoted)}; CPT Studio could not confirm from the document whether those '
                  f'statements apply to {act}.')
    else:
        reason = (f'The document states {quoted[0]}; CPT Studio could not confirm from the document whether that '
                  f'statement applies to {act}.')
    return f'Does {asked} apply to {applies}?', reason


def _status(s: Slots, text: str) -> tuple[str, str]:
    act = the_act(text, s)
    return (f'Was {act}{_shown(_words(s, text, "status"))} done on the date of service?',
            f'CPT Studio could not confirm from the document that {act} was done.')


def _not_documented(s: Slots, text: str) -> tuple[str, str]:
    """FINAL 7.6: no act of the code's kind documented as done; with a group that names no act, the code's."""
    group = group_phrase(s)
    reason = (not_documented_reason(group) if group else
              f"CPT Studio's reading of the document records no act that {s.code} accounts for documented as done on "
              'the date of service.')
    return performed_question(s.code), reason


def _attempted(s: Slots, text: str) -> tuple[str, str]:
    """ADJUDICATION C-9 (v1's attempted_question and attempted_reason, worded through the_act)."""
    act = the_act(text, s)
    return (f'{_capital(act)} was begun and not completed. Confirm whether {s.code} describes what was done on the date '
            'of service.',
            f'The document states {act} was begun and not completed{_shown(_words(s, text, "attempted"), 140)}. Kept for '
            'review: not treated as completed and not excluded.')


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
    act = the_act(text, s)
    return (f'In whose entry is {act}{_shown(_words(s, text, "entry"))} documented: the note of the physician who '
            'performed the procedure, or another entry?',
            f'CPT Studio could not confirm from the document whose entry {act} is told in.')


# The entry an act told only in another role's entry is named by, when its owner is not given (or is the documenting
# clinician, whom ANOTHER_ENTRY's fact excludes): the fact itself, naming no role
OTHER_ENTRY = "an entry other than the physician's note"


def _another_entry(s: Slots, text: str) -> tuple[str, str]:
    """events.another_role_hold's question and detail (copied), its entry named by the owner of the part that tells
    the act (OTHER_ENTRY when no other role is given); the detail's opening clause (the session's acts listed) is left
    out; the group's acts, else the act. D281 (step f3w; build list B3, G1-05 (ii)): the code's group, "this code
    accounts for", only for the code's own act (row 5); a session's examination the code's group does not name (row 7:
    the examination told only in another role's entry, read on another act's row) is named by the item's act, never as
    what this code accounts for - "The colonoscopy is documented only in the nursing entry (...)". Keyed on that row-7
    case alone, so the code's own act of a kind not established keeps its group's name."""
    entry = OWNER_ENTRIES.get(s.owner, OTHER_ENTRY) if s.owner is not None else OTHER_ENTRY
    name = service_phrase(s.family)
    own = not (s.act is Kind.EXAMINATION and Kind.EXAMINATION not in s.group)  # B3: the code's own act (row 5)
    group = group_phrase(s) if own else ''
    accounts = ' this code accounts for' if own else ''
    what = f'the {group}' if group else the_act(text, s)
    passage = _shown(_words(s, text, 'another_entry'))
    return (f'{_capital(what)} is documented only in {entry}{passage}. Was it performed in this {name} on the date of '
            'service?',
            f'{_capital(what)}{accounts} is documented only in {entry}{passage}, not by the physician performing the '
            f'{name}. {HELD}')


def _time(s: Slots, text: str) -> tuple[str, str]:
    act = the_act(text, s)
    return (f'Was {act}{_shown(_words(s, text, "time"))} done at this encounter?',
            f'CPT Studio could not confirm from the document when {act} was done.')


def _time_beside_visit(s: Slots, text: str) -> tuple[str, str]:
    """assess's C-3 question of an undatable procedure beside an E/M (copied)."""
    question, reason = _time(s, text)
    return (question, f'{reason} A procedure done on the date of service would need a significant, separately '
                      'identifiable visit beside it.')


def _performer(s: Slots, text: str) -> tuple[str, str]:
    act = the_act(text, s)
    return (f'Was {act}{_shown(_words(s, text, "performer"))} done by the documenting endoscopist or the endoscopy '
            'team?',
            f'CPT Studio could not confirm from the document who performed {act}.')


def _procedure(s: Slots, text: str) -> tuple[str, str]:
    """v1's procedure_question (D160 (3): empty words never quoted) and procedure_reason, worded through the_act."""
    act = the_act(text, s)
    return (f'In which procedure was {act}{_shown(_words(s, text, "procedure"))} done?',
            f'CPT Studio could not confirm from the document in which procedure {act} was done.')


def _another_tract(s: Slots, text: str) -> tuple[str, str]:
    """assess._eus_code_hold's D171 (2) tract hold (copied), for either luminal tract. A session placed in the
    pancreatobiliary tract is said by the rule it fails - the code needs it placed in the code's own tract - never as a
    place no code of that tract describes. D254: a session tract that is not given, or that is the code's own (which the
    message's fact contradicts), is worded as "another tract than" the code's; the code's tract when it is not given
    (or is no luminal tract) as the endoscopic ultrasound this code describes; the place and the words when given."""
    required = s.required_tract
    tract = s.tract if s.tract is not None and s.tract is not required else None
    needed = EUS_TRACT_WORDS.get(required) if required is not None else None
    needed = needed or (f'an endoscopic ultrasound placed in {TRACT_PLACES[required]}' if required is not None
                        else 'the endoscopic ultrasound this code describes')
    place = landmark_label(s.place.value) if s.place is not None else ''
    words = _words(s, text, 'another_tract')
    if place and words:
        where = f' (the {place}: {_whole(words)})'
    else:
        where = f' (the {place})' if place else _whole_shown(words)
    why = ''
    if tract is None:
        placed = (f'another tract than {TRACT_PLACES[required]}' if required is not None
                  else 'another tract than the one this code describes')
    else:
        placed = TRACT_PLACES[tract]
        if required is not None and tract in EUS_TRACT_WORDS and required in EUS_TRACT_WORDS:
            why = f', which no {required.value} endoscopic ultrasound code describes'
        elif required is not None:
            why = f', and this code needs it placed in {TRACT_PLACES[required]}'
    return (f'The documented endoscopic ultrasound is placed in {placed}{where}. Was {needed} performed on the date of '
            'service?',
            f'{s.code} accounts for {needed}; the document places this endoscopic ultrasound in {placed}{where}{why}. '
            f'{HELD}')


# --- the enteroscopy class items (classes.class_hold's forms, copied; D254 rules 1 and 3, D253 QX (ii)) ---------------


_ENT = 'an enteroscopy class item'  # what a refusal of an enteroscopy class item's spans names (any of the four items)


def _enteroscopy_required(s: Slots) -> str:
    """The class words of the code's enteroscopy class (classes.CLASS_WORDS); the enteroscopy the code describes when no
    class is given."""
    exam_class = s.enteroscopy_class
    return ENTEROSCOPY_CLASS_WORDS[exam_class] if exam_class is not None else 'the enteroscopy this code describes'


def _route_told(s: Slots, text: str, words: str, message: str) -> tuple[str, str]:
    """The route's own words, quoted after the route (160 and 120 characters) when they are not the examination's own
    sentence (``words``), which is quoted once."""
    passage = _unit_words(text, s.approach_words, message, 'approach_words')
    passage = '' if ' '.join(passage.split()) == ' '.join(words.split()) else passage
    return _shown(passage, 160), _shown(passage, 120)


def _enteroscopy_class(s: Slots, text: str) -> tuple[str, str]:
    """classes.class_hold's class and incomplete forms (copied), with the examination's own route when it is given
    (ROUTE_WORDS: every approach, D254 rule 1 - refute-r4a-r2 recorded the transanal route left unnamed). D254 rule 1
    (r4a's R4): a reach that is not given (or names no place) leaves the reach clause out."""
    required, reached = _enteroscopy_required(s), _reach(s)
    words = _words(s, text, _ENT)
    said, shown = _shown(words, 160), _shown(words, 120)
    if s.incomplete:
        documented = (f'The enteroscopy is documented as reaching the {reached}{said} and as incomplete' if reached
                      else f'The enteroscopy is documented{said} as incomplete')
        return (f'The documented enteroscopy{shown} is stated to be incomplete. Was {required} performed on the date of '
                'service?',
                f'{documented}; {s.code} accounts for {required}, which CPT Studio could not find in the document.')
    route = ROUTE_WORDS[s.approach] if s.approach is not None else ''
    told, told_q = _route_told(s, text, words, _ENT) if route else ('', '')
    if reached:
        asked = f'The documented enteroscopy{shown} reached the {reached}' + (f' {route}{told_q}' if route else '') + '.'
        documented = f'The enteroscopy is documented as reaching the {reached}{said}' + (f' {route}{told}' if route
                                                                                          else '')
    elif route:
        asked = f'The documented enteroscopy{shown} was passed {route}{told_q}.'
        documented = f'The enteroscopy is documented{said} as passed {route}{told}'
    else:
        asked = f'CPT Studio could not find {required} in the documented enteroscopy{shown}.'
        documented = f'The enteroscopy is documented{said}'
    tail = 'Was it performed on the date of service?' if not (reached or route) else \
        f'Was {required} performed on the date of service?'
    return (f'{asked} {tail}',
            f'{documented}; {s.code} accounts for {required}, which CPT Studio could not find in the document.')


def _enteroscopy_approach(s: Slots, text: str) -> tuple[str, str]:
    """ENT's approach explanation: classes.class_hold's class form naming the examination's established route. D254 rule
    3: without ``approach`` (a denied or unstated route - refute-r4a-r2 A1), the class is worded without naming a route,
    saying only that CPT Studio could not confirm the route the code describes; the incomplete form is the class's."""
    if s.approach is not None or s.incomplete:
        return _enteroscopy_class(s, text)
    required, reached = _enteroscopy_required(s), _reach(s)
    words = _words(s, text, _ENT)
    said, shown = _shown(words, 160), _shown(words, 120)
    unknown = 'CPT Studio could not confirm from the document the route this code describes'
    if reached:
        asked = f'The documented enteroscopy{shown} reached the {reached}; {unknown}.'
        documented = f'The enteroscopy is documented as reaching the {reached}{said}'
    else:
        asked = f'{unknown} for the documented enteroscopy{shown}.'
        documented = f'The enteroscopy is documented{said}'
    return (f'{asked} Was {required} performed on the date of service?',
            f'{documented}; {s.code} accounts for {required}, which CPT Studio could not find in the document.')


def _route_anatomy(s: Slots) -> tuple[list[str], list[str]]:
    """(the anatomy of each route the encounter's anatomy establishes, the anatomy of each it only possibly opens),
    each sorted, for the routes a question names (APPROACH_ANATOMY: a stoma, a pouch). D267 (repair r3c of round w9r;
    refute-r4a-r2 F5): a route the Fill marks as only possible (``possible_approaches``) is never among the established
    ones, whatever ``approaches`` holds - it is never "the documented stoma" or "the documented pouch"."""
    possible = {APPROACH_ANATOMY[way] for way in s.possible_approaches if way in APPROACH_ANATOMY}
    established = {APPROACH_ANATOMY[way] for way in s.approaches if way in APPROACH_ANATOMY} - possible
    return sorted(established), sorted(possible)


def _enteroscopy_route(s: Slots, text: str) -> tuple[str, str]:
    """classes.class_hold's route form (copied): the route not established beside the encounter's stoma or pouch. D254
    rule 1 (r4a's R4): with no reach given, the reach clause is left out. D267 (refute-r4a-r2 F5): the routes only
    possibly opened (``possible_approaches``: a doubted or unresolved through, or an entry whose type is not established)
    are one alternative worded as possible - "possibly through a pouch or a stoma" - after the routes the anatomy
    establishes ("through the documented stoma"): the possibility is the route's, so the words are true whether the
    anatomy itself or only the passage through it is not established, and never "the documented pouch"."""
    required, reached = _enteroscopy_required(s), _reach(s)
    words = _words(s, text, _ENT)
    said, shown = _shown(words, 160), _shown(words, 120)
    established, possible = _route_anatomy(s)
    routes = [f'through the documented {name}' for name in established]
    if possible:
        routes.append('possibly through ' + ' or '.join(f'a {name}' for name in possible))
    ways = ' or '.join(routes) or 'through a stoma or pouch'
    unknown = f'CPT Studio could not confirm from the document whether it was passed through the mouth or {ways}'
    if reached:
        also, also_shown = (' and as incomplete', ' and is stated to be incomplete') if s.incomplete else ('', '')
        asked = f'The documented enteroscopy{shown} reached the {reached}{also_shown}; {unknown}.'
        documented = f'The enteroscopy is documented as reaching the {reached}{said}{also}'
    elif s.incomplete:
        asked = f'The documented enteroscopy{shown} is stated to be incomplete; {unknown}.'
        documented = f'The enteroscopy is documented{said} as incomplete'
    else:
        asked = (f'CPT Studio could not confirm from the document whether the documented enteroscopy{shown} was passed '
                 f'through the mouth or {ways}.')
        documented = f'The enteroscopy is documented{said}'
    return (f'{asked} Was {required} performed on the date of service?',
            f'{documented}, and {unknown}; {s.code} accounts for {required}, which CPT Studio could not find in the '
            'document.')


THROUGH_UNKNOWN = 'CPT Studio could not confirm from the document the altered anatomy it was passed through'


def _enteroscopy_through(s: Slots, text: str) -> tuple[str, str]:
    """ENT's route part when only the anatomy the enteroscopy was passed through is not established (D253 QX (ii):
    "asked by the route's own question", never "In which procedure was the enteroscopy done?"): the class's route form
    naming that one unknown - the altered anatomy it was passed through (ATTRIBUTE_PHRASES' through) - beside the reach
    and the established route when they are given."""
    required, reached = _enteroscopy_required(s), _reach(s)
    words = _words(s, text, _ENT)
    said, shown = _shown(words, 160), _shown(words, 120)
    route = ROUTE_WORDS[s.approach] if s.approach is not None else ''
    told, told_q = _route_told(s, text, words, _ENT) if route else ('', '')
    if reached:
        asked = (f'The documented enteroscopy{shown} reached the {reached}' + (f', passed {route}{told_q}' if route
                                                                                else '') + f'; {THROUGH_UNKNOWN}.')
        documented = f'The enteroscopy is documented as reaching the {reached}{said}' + (f', passed {route}{told}' if
                                                                                          route else '')
    elif route:
        asked = f'The documented enteroscopy{shown} was passed {route}{told_q}; {THROUGH_UNKNOWN}.'
        documented = f'The enteroscopy is documented{said} as passed {route}{told}'
    else:
        asked = (f'CPT Studio could not confirm from the document the altered anatomy the documented enteroscopy{shown} '
                 'was passed through.')
        documented = f'The enteroscopy is documented{said}'
    return (f'{asked} Was {required} performed on the date of service?',
            f'{documented}, and {THROUGH_UNKNOWN}; {s.code} accounts for {required}, which CPT Studio could not find in '
            'the document.')


def _method(s: Slots, text: str) -> tuple[str, str]:
    """FINAL 7.4 h5: the lesion's own words, else its place, else 'lesion'; the group's acts, else the code's method."""
    lesion = ' '.join(span_text(text, s.lesion).split()) if s.lesion else ''
    if not lesion:
        place = landmark_label(s.place.value) if s.place is not None else ''
        lesion = f'lesion at the {place}' if place else 'lesion'
    group = group_phrase(s)
    reason = method_reason(group) if group else ('The document states a removal without its method; CPT Studio could '
                                                 'not confirm from the document the method this code accounts for.')
    return method_question(lesion), reason


def _technique(s: Slots, text: str) -> tuple[str, str]:
    act = the_act(text, s)
    question = f'Which technique was used for {act}{_shown(_words(s, text, "technique"))}?'
    if s.technique is None:
        return question, f'CPT Studio could not confirm from the document which technique was used for {act}.'
    return (question, f'This code accounts for a {TECHNIQUE_WORDS[s.technique.value]}; CPT Studio could not confirm from '
                      f'the document the technique of {act}.')


def _stated_technique(s: Slots, text: str) -> tuple[str, str]:
    act = the_act(text, s)
    return (f'Which technique was used for {act}{_shown(_words(s, text, "stated_technique"))}?',
            f'CPT Studio could not confirm from the document which technique was used for {act}.')


def _another_technique(s: Slots, text: str) -> tuple[str, str]:
    """v1's another_technique (reconcile.py:307-316): the stated technique (a dilation of another technique when it is
    not given, or is the code's own, which the message's fact contradicts) and the code's (the technique this code
    accounts for when not given)."""
    technique = s.technique
    stated = (TECHNIQUE_WORDS[s.stated.value] if s.stated is not None and s.stated is not technique
              else 'dilation of another technique')
    words = _words(s, text, 'another_technique')
    name = service_phrase(s.family)
    if technique is None:
        return (f'The documented dilation{_shown(words)} states a {stated}. Was the technique this code accounts for '
                'performed on the date of service?',
                f'The {name} is documented as performed with a {stated}{_shown(words, 160)}; CPT Studio could not find '
                'in the document the technique this code accounts for.')
    required = TECHNIQUE_WORDS[technique.value]
    return (f'The documented dilation{_shown(words)} states a {stated}. Was a {required} performed on the date of '
            'service?',
            f'The {name} is documented as performed with a {stated}{_shown(words, 160)}; this code accounts for a '
            f'{required}, which CPT Studio could not find in the document.')


def _route_question(s: Slots, text: str) -> tuple[str, str]:
    act, words = the_act(text, s), _words(s, text, 'route')
    return (act, f'Was {act}{_whole_shown(words)} an EUS-guided transmural injection or fiducial placement, or a '
                 'submucosal injection of the wall?')


def _route(s: Slots, text: str) -> tuple[str, str]:
    act, question = _route_question(s, text)
    return (question, f'{s.code} describes {TRANSMURAL_WORDS}; CPT Studio could not confirm from the document how {act} '
                      f'reached the tissue. {HELD}')


def _wall_injection(s: Slots, text: str) -> tuple[str, str]:
    """assess._eus_code_hold's D171 (4) hold (copied): the route established submucosal."""
    _, question = _route_question(s, text)
    this = _this(act_phrase(text, s), named_kind(s.act))
    return (question, f'{s.code} describes {TRANSMURAL_WORDS}; the document describes {this} as an injection of the '
                      f'wall{_shown(_words(s, text, "wall_injection"), 160)}, a submucosal injection rather than a '
                      f'transmural one. {HELD}')


def _act_target(s: Slots, text: str) -> tuple[str, str]:
    act = the_act(text, s)
    return (f'Which lesion or site was {act}{_shown(_words(s, text, "act_target"))} done on?',
            f'CPT Studio could not confirm from the document which lesion or site {act} was done on.')


def _site(s: Slots, text: str) -> tuple[str, str]:
    """D29: the structure of a dilation not established; v1's site_reason, the code's site class when it is given."""
    question, _ = _act_target(s, text)
    act = the_act(text, s)
    structure = f'CPT Studio could not confirm from the document which structure {act} was done on.'
    if s.site is None:
        return question, structure
    return question, f'This code accounts for a {SITE_WORDS[s.site.value]}; {structure}'


def _another_site(s: Slots, text: str) -> tuple[str, str]:
    """v1's another_site (DECISIONS D29): the dilation's place outside the code's site class - "another site" when no
    place is given, or the place given is inside the class (which the message's fact contradicts)."""
    site = s.site
    place = landmark_label(s.place.value) if s.place is not None else ''
    if place and site is not None and s.place in engine_catalogue.SITE_CLASSES[site]:
        place = ''
    at = f'at the {place}' if place else 'at another site'
    words = _words(s, text, 'another_site')
    name = service_phrase(s.family)
    if site is None:
        return (f'The documented dilation{_shown(words)} is {at}. Was the dilation this code accounts for performed on '
                'the date of service?',
                f'The {name} is documented as performed with a dilation {at}{_shown(words, 160)}; CPT Studio could not '
                'find in the document the site this code accounts for.')
    required = SITE_WORDS[site.value]
    return (f'The documented dilation{_shown(words)} is {at}. Was a {required} performed on the date of service?',
            f'The {name} is documented as performed with a dilation {at}{_shown(words, 160)}; this code accounts for a '
            f'{required}, which CPT Studio could not find in the document.')


def _duct(s: Slots, text: str) -> tuple[str, str]:
    """XCHG's duct: the two-act form when the counterpart and its words are given, else the act's own."""
    act, own = the_act(text, s), _words(s, text, 'duct')
    if s.whole is not None and s.whole_words:
        other = _the(kind_words(s.whole), named_kind(s.whole))
        theirs = _unit_words(text, s.whole_words, 'duct', 'whole_words')
        return (f'Were {act}{_shown(own)} and {other}{_shown(theirs)} done in the same duct?',
                f'CPT Studio could not confirm from the document that {act} and {other} were done in the same duct.')
    return (f'In which duct was {act}{_shown(own)} done?',
            f'CPT Studio could not confirm from the document in which duct {act} was done.')


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


_PFC_WORDS = ('describes the transmural drainage of a pancreatic fluid collection (a pseudocyst or walled-off '
              'necrosis)')  # defining_target_hold's (v1's) words, copied


def _structure_parts(s: Slots, text: str, message: str) -> tuple[str, str, str]:
    """(the act after 'this', its quoted words, the question) of a STRUCT:pfc item (v1's defining_target_hold, with
    the act's kind label only)."""
    label, named = kind_words(s.act), named_kind(s.act)
    words = _words(s, text, message)
    return (_this(label, named), _shown(words, 160),
            f'Which structure was {_the(label, named)}{_shown(words, 160)} done on: a pancreatic fluid collection (a '
            'pseudocyst or walled-off necrosis), or another structure?')


def _structure(s: Slots, text: str) -> tuple[str, str]:
    this, _, question = _structure_parts(s, text, 'structure')
    return (question, f'{s.code} {_PFC_WORDS}; CPT Studio could not confirm from the document which structure {this} '
                      f'was done on. {HELD}')


def _another_structure(s: Slots, text: str) -> tuple[str, str]:
    """STRUCT:pfc's structure established as another: the place the document gives the act, "another structure" when
    none is given."""
    this, _, question = _structure_parts(s, text, 'another_structure')
    place = landmark_label(s.place.value) if s.place is not None else ''
    where = f'at the {place}' if place else 'at another structure'
    return question, f'{s.code} {_PFC_WORDS}; the document places {this} {where}. {HELD}'


def _named_stations(stations: Sequence[Station]) -> tuple[str, str]:
    upper = engine_catalogue.UPPER_STATIONS
    named = join([f'the {station.value}' for station in upper if station in stations])
    missing = join([f'the {station.value}' for station in upper if station not in stations])
    return named, missing


def _eus_required(s: Slots) -> str:
    """The class words of the code's EUS class (_eus_class_words); the endoscopic ultrasound examination the code
    describes when no class is given."""
    return (_eus_class_words(s.code, s.exam_class) if s.exam_class is not None
            else 'the endoscopic ultrasound examination this code describes')


def _stations(s: Slots, text: str) -> tuple[str, str]:
    """STATIONS and LIMITED unresolved: which upper-tract stations were examined. Where some stations are established
    examined and not all three, assess's D171 (3) and D177 (4) wording (copied) names them."""
    words = _words(s, text, 'stations')
    exam_class = s.exam_class or engine_catalogue.EusClass.FULL
    named_in = [station for station in engine_catalogue.UPPER_STATIONS if station in s.stations]
    exam = 'The documented endoscopic ultrasound examination'
    if exam_class is engine_catalogue.EusClass.FULL and len(named_in) == 1:
        return (f'{exam}{_whole_shown(words)} names one station only, the {named_in[0].value}. Was '
                f'{FULL_STATIONS_WORDS} performed on the date of service?',
                f'{exam} names one station only, the {named_in[0].value}{_shown(words, 160)}; {s.code} accounts for '
                f'{FULL_STATIONS_WORDS}, which CPT Studio could not find in the document. {HELD}')
    if exam_class is engine_catalogue.EusClass.FULL and 1 < len(named_in) < len(engine_catalogue.UPPER_STATIONS):
        named, missing = _named_stations(named_in)
        return (f'{exam}{_whole_shown(words)} names {named}, not {missing}. Was {FULL_STATIONS_WORDS} performed on the '
                'date of service?',
                f'{exam} names {named}, not {missing}{_shown(words, 160)}; {s.code} accounts for {FULL_STATIONS_WORDS}, '
                f'which CPT Studio could not find in the document. {HELD}')
    required = FULL_STATIONS_WORDS if exam_class is engine_catalogue.EusClass.FULL else _eus_class_words(s.code,
                                                                                                         exam_class)
    return (f'Which parts of the upper tract (the esophagus, the stomach, the duodenum) were examined in the endoscopic '
            f'ultrasound examination{_shown(words)}?',
            f'{s.code} accounts for {required}; CPT Studio could not confirm from the document which parts of the upper '
            f'tract were examined. {HELD}')


def _station_class(s: Slots, text: str) -> tuple[str, str]:
    """STATIONS and LIMITED established otherwise: an upper station established not examined (the full class; assess's
    D171 (3) wording, copied), or all three established examined (a limited class). D254: neither given - the class the
    stations do not fit, named by the code's class (or the examination the code describes)."""
    words = _words(s, text, 'station_class')
    exam = 'The documented endoscopic ultrasound examination'
    denied = [station for station in s.denied if station in engine_catalogue.UPPER_STATIONS]
    if denied:
        region = denied[0].value
        return (f'The document states that the {region} was not examined{_whole_shown(words)}. Was '
                f'{FULL_STATIONS_WORDS} performed on the date of service?',
                f'The document states that the {region} was not examined{_shown(words, 160)}; {s.code} accounts for '
                f'{FULL_STATIONS_WORDS}, which CPT Studio could not find in the document. {HELD}')
    if all(station in s.stations for station in engine_catalogue.UPPER_STATIONS):
        required = _eus_class_words(s.code, engine_catalogue.EusClass.LIMITED)
        named, _ = _named_stations(s.stations)
        return (f'{exam}{_whole_shown(words)} names {named}. Was {required} performed on the date of service?',
                f'{exam} names {named}{_shown(words, 160)}; {s.code} accounts for {required}, which CPT Studio could '
                f'not find in the document. {HELD}')
    required = _eus_required(s)
    return (f'CPT Studio could not find {required} in the documented endoscopic ultrasound examination{_shown(words)}. '
            'Was it performed on the date of service?',
            f'{s.code} accounts for {required}, which CPT Studio could not find in the document. {HELD}')


def _examination_class(s: Slots, text: str) -> tuple[str, str]:
    """wording.examination_class_hold's two forms (copied; equal to it wherever the class words are its own: tested),
    with the class words chosen first - the limited class as CPT states it for 43237 and 43238 (DECISIONS D171 (3)).
    D254: with no reach given the reach clause is left out; with no class, the examination the code describes."""
    required, reached = _eus_required(s), _reach(s)
    words = _words(s, text, 'examination_class')
    said, shown = _shown(words, 160), _shown(words, 120)
    if s.incomplete:
        documented = (f'The endoscopic ultrasound examination is documented as reaching the {reached}{said} and as '
                      'incomplete' if reached else f'The endoscopic ultrasound examination is documented{said} as '
                                                   'incomplete')
        return (f'The documented endoscopic ultrasound examination{shown} is stated to be incomplete. Was {required} '
                'performed on the date of service?',
                f'{documented}; {s.code} accounts for {required}, which CPT Studio could not find in the document.')
    if reached:
        return (f'The documented endoscopic ultrasound examination{shown} reached the {reached}. Was {required} '
                'performed on the date of service?',
                f'The endoscopic ultrasound examination is documented as reaching the {reached}{said}; {s.code} accounts '
                f'for {required}, which CPT Studio could not find in the document.')
    return (f'CPT Studio could not find {required} in the documented endoscopic ultrasound examination{shown}. Was it '
            'performed on the date of service?',
            f'The endoscopic ultrasound examination is documented{said}; {s.code} accounts for {required}, which CPT '
            'Studio could not find in the document.')


def _yield(s: Slots, text: str) -> tuple[str, str]:
    act, words = the_act(text, s), _words(s, text, 'yield')
    return (f'Was any stone, calculus, debris or sludge removed with {act}{_shown(words)}?',
            f'CPT Studio could not confirm from the document what {act} retrieved{_shown(words, 140)}. {HELD}')


def _nothing_retrieved(s: Slots, text: str) -> tuple[str, str]:
    """ercp._nothing_retrieved_hold (copied)."""
    act, words = the_act(text, s), _words(s, text, 'nothing_retrieved')
    return (f'Was any stone, calculus, debris or sludge removed with {act}{_shown(words)}?',
            f'The document states that nothing was retrieved with {act}{_shown(words, 140)}. CPT Studio does not read a '
            f'sweep or an extraction that retrieved nothing as a removal of stones or debris. {HELD}')


# The part questions of every rule that asks (v1's BUNDLING_QUESTIONS and PART_QUESTIONS, worded through the act with its
# article and each quote optional: tests/v2/test_wording.py pins each equal to v1's where both quotes are given);
# a rule that always bundles (the clip, the cannulation) or none asks whether the act was part of another act (D181's
# act_part).
PART_FORMS: Mapping[Bundling, str] = MappingProxyType({
    Bundling.BIOPSY_OF_REMOVED_LESION: 'Was {act}{part} taken from the lesion that was removed{whole}, or from another '
                                       'lesion?',
    Bundling.RESECTION_TECHNIQUE: 'Was {act}{part} part of the resection of that lesion{whole}, or of another lesion?',
    Bundling.LIFT_INJECTION: 'Was {act}{part} made to lift the lesion that was resected{whole}, or given for another '
                             'reason or lesion?',
    Bundling.PROCEDURAL_ADJUNCT: 'Was {act}{part} done as part of the removal{whole} - at the site it removed, or for the '
                                 'bleeding it caused - or on another lesion or site?',
    Bundling.DRAINAGE_STEP: 'Was {act}{part} a separate sampling, or a step of the transmural drainage{whole}?',
    Bundling.STENT_INCLUDED: 'Was {act}{part} done in the duct of the stent placement{whole}, or in the other duct?',
})
PART_OF_ANOTHER = 'Was {act}{part} part of another act documented with it{whole}?'


def _part(s: Slots, text: str) -> tuple[str, str]:
    """act_part and the bundling identity (PART, BUNDLING_TARGET): the rule's question, the part named by its kind and
    quoted, its whole quoted; v1's bundling_reason. With no rule that asks, whether the act was part of another act,
    and a reason that says only that."""
    rule = s.bundling
    kind = _the(kind_words(s.act), named_kind(s.act))
    part = _words(s, text, 'part')
    whole = _unit_words(text, s.whole_words, 'part', 'whole_words')
    asks = rule is not None and rule in PART_FORMS
    template = PART_FORMS[rule] if rule is not None and asks else PART_OF_ANOTHER
    question = template.format(act=kind, part=_shown(part), whole=_shown(whole))
    act = the_act(text, s)
    if not asks:
        return (question, f'CPT Studio could not confirm from the document whether {act} is part of another act '
                          'documented with it.')
    return (question, f'Whether {act} is part of another act documented with it depends on which lesion it was done on, '
                      'which CPT Studio could not confirm from the document.')


def _cause(s: Slots, text: str) -> tuple[str, str]:
    """act_cause unresolved: the causes contract.types.Cause names - an act of this session, a lesion present before
    it, an earlier procedure, or none (spontaneous)."""
    act, said = the_act(text, s), _shown(_words(s, text, 'cause'))
    other = 'or was the bleeding from a lesion present before it, from an earlier procedure, or spontaneous'
    if s.whole is not None and s.whole_words:
        whole = _the(kind_words(s.whole), named_kind(s.whole))
        theirs = _unit_words(text, s.whole_words, 'cause', 'whole_words')
        question = (f'Did {whole}{_shown(theirs)} at this procedure cause the bleeding {act}{said} treated, '
                    f'{other}?')
    else:
        question = f'Did an act of this procedure cause the bleeding {act}{said} treated, {other}?'
    return question, f'CPT Studio could not confirm from the document what caused the bleeding {act} treated.'


def _bundled(s: Slots, text: str) -> tuple[str, str]:
    """wording.act_included (v1's, worded through its parts): the explanation naming the whole act's rule (none named
    when no rule is given), the parts listed (each by its kind; the act when none is listed) and the group's acts.
    D267 (repair r3c of round w9r; refute-r3c-r1 F6): a group that names no act (``()``, or only Kind.OTHER) words the
    code itself, as _not_documented and _method do - "the documented act that 45385 accounts for" (this code's, when no
    code is given) - never a bare 'act' standing for a kind ("The act documented ...")."""
    why = BUNDLING_WHY[s.bundling] if s.bundling is not None else ''
    listed = ('; '.join(dict.fromkeys(kind_words(kind) for kind in s.listed)) if s.listed
              else act_phrase(text, s))
    group = group_phrase(s)
    name = service_phrase(s.family)
    words = _words(s, text, 'bundled')
    rule = f': {why}' if why else '.'
    done = f'The {name} is documented as performed with {listed}, which is part of another documented act{rule}'
    if group:
        return (f'The {group} documented{_shown(words)} is part of another procedure documented with it. Was a separate '
                f'{group} performed on the date of service?',
                f'{done} No separate {group} is documented for this code.')
    code = s.code or 'this code'
    return (f'The documented act{_shown(words)} that {code} accounts for is part of another procedure documented with '
            f'it. Was a separate act that {code} accounts for performed on the date of service?',
            f'{done} No separate act that {code} accounts for is documented.')


def _same_day_subject(labels: Sequence[str], possible: Sequence[str]) -> str:
    """checks._same_day_subject (copied)."""
    parts = []
    for items, phrase in ((labels, 'documented as performed on the same date'),
                          (possible, 'possibly performed on the same date (its performance is not established)')):
        if items:
            parts.append(f'{join(items)} {"is" if len(items) == 1 else "are"} {phrase}')
    return '; '.join(parts)


SEPARATE_EM_UNNAMED = ('A significant, separately identifiable E/M service beside a procedure on the same date is not '
                       'established by this document.')  # D254 rule 3: SEPARATE_EM with nothing to name


def _separate_em(s: Slots, text: str) -> tuple[str, str]:
    """checks.separate_em_clarification (copied): the question, and same_day_reason over the same-day acts, each named
    by its kind (D254 rule 2: an act no kind names is NO_KIND_LABEL, "Another act ..." when it opens the sentence). D246
    (refute-5c-r2 R2-03): when the procedure day has no act to list, the reason names the same-day codes (``codes``) as
    proposed - never as done. D254 rule 3: with nothing to name, SEPARATE_EM_UNNAMED."""
    labels = list(dict.fromkeys(kind_words(kind) for kind in s.listed))
    possible = list(dict.fromkeys(kind_words(kind) for kind in s.possible))
    if not labels and not possible:
        codes = tuple(dict.fromkeys(s.codes))
        if not codes:
            return SEPARATE_EM_QUESTION, SEPARATE_EM_UNNAMED
        return (SEPARATE_EM_QUESTION, f'{join(codes)} {"is" if len(codes) == 1 else "are"} proposed for the same '
                                      'date; a significant, separately identifiable E/M service is not established by '
                                      'this document.')
    subject = _same_day_subject(labels, possible)
    return (SEPARATE_EM_QUESTION, f'{_capital(subject)}; a significant, separately identifiable E/M service is not '
                                  'established by this document.')


def _separate_em_denied(s: Slots, text: str) -> tuple[str, str]:
    return (SEPARATE_EM_QUESTION, f'The document states that the visit was not a significant, separately identifiable '
                                  f'service beside the procedure{_shown(_words(s, text, "separate_em_denied"), 140)}.')


def _base_included(s: Slots, text: str) -> tuple[str, str]:
    """combination.base_hold's act form (copied), each act in doubt marked (classes.IN_DOUBT) and named by its kind (D254
    rule 2: NO_KIND_LABEL for an act no kind names - R3C1-03's "from act" is gone). D246 (5c's R8, the lead's L1): with
    no act in doubt (``listed`` empty), the codes beside it, stated only as proposed. D254 rule 3: with nothing to name
    (no act listed, no code - an act in doubt that no kind names: refute-r3c-r1 R3C1-01, refute-r4d-r2 P4), the act form
    over NO_KIND_LABEL - the act the hold rests on, no kind naming it."""
    if not s.listed and s.codes:
        codes = tuple(dict.fromkeys(s.codes))
        one = len(codes) == 1
        return (BASE_QUESTION.format(code=s.code, included=', '.join(codes)),
                f'{join(codes)} {"is" if one else "are"} also proposed for the documented {service_phrase(s.family)}; '
                f'{s.code} is normally not reported separately from {"it" if one else "them"} {_HOLD_RULE}. {HELD}')
    kinds = s.listed or (Kind.OTHER,)
    included = ', '.join(dict.fromkeys(f'{kind_words(kind)}{IN_DOUBT}' for kind in kinds))
    return (BASE_QUESTION.format(code=s.code, included=included),
            f'The documented {service_phrase(s.family)} includes {included}, which this diagnostic code does not '
            f'account for (internal profile rule). {HELD}')


def _base_explained(s: Slots, text: str) -> tuple[str, str]:
    """combination.base_hold (copied): beside the interventions the codes name, or the acts it does not account for,
    each named by its kind (D254 rule 2). D254 rule 3: with neither (an established act that no kind names: refute-5b-r1
    F1's EUS act of kind other), the act form over NO_KIND_LABEL."""
    name = service_phrase(s.family)
    if s.codes:
        included = ', '.join(s.codes)
        reason = (f'The documented {name} has interventions that {included} account for; its diagnostic examination is '
                  f'normally included in them {_HOLD_RULE}. {HELD}')
    else:
        included = ', '.join(dict.fromkeys(kind_words(kind) for kind in (s.listed or (Kind.OTHER,))))
        reason = (f'The documented {name} includes {included}, which this diagnostic code does not account for '
                  f'(internal profile rule). {HELD}')
    return BASE_QUESTION.format(code=s.code, included=included), reason


def _whole_noun(family: SessionKind) -> str:
    """The whole a base-within code's session is part of, by its own family (D257): its service, else its noun (an E/M
    of another setting is a visit), else 'procedure'."""
    service = SESSION_SERVICES.get(family)
    return kind_label(service) if service else SESSION_NOUNS.get(family, 'procedure')


def _base_within(s: Slots, text: str) -> tuple[str, str]:
    """combination.base_within_hold (copied) with DECISIONS D257 (refute-r4d-r2 P5): the whole is named by its own family
    (``whole_family``) - the endoscopic portion of an endoscopic ultrasound, as v1 words it, and part of any other whole
    - and never as an endoscopic ultrasound it is not; with no family given, another procedure. A whole only possibly
    done (``whole_possible``) is stated as possibly performed on the date of service, its performance not established,
    and the code's session as possibly its part. ``codes``: the whole's counted codes."""
    within = s.codes
    coded = f', which {", ".join(within)} {"accounts" if len(within) == 1 else "account"} for' if within else ''
    possible = s.whole_possible
    if s.whole_family is not None:
        whole = f'the {_whole_noun(s.whole_family)}'
        portion = 'the endoscopic portion of' if s.whole_family is SessionKind.EUS else 'part of'
        named = f'{portion} {whole} documented with it'
    else:
        whole = 'the procedure it may be part of' if possible else 'the procedure it is part of'
        named = 'part of another procedure documented with it'
    state = ', possibly performed on the date of service (its performance is not established)' if possible else ''
    return (f'Is {s.code} reported separately from {", ".join(within) or whole} for this examination?',
            f'The documented {service_phrase(s.family)} {"may be" if possible else "is"} {named}{state}{coded}; that '
            f'examination is normally included in it, not reported separately {_HOLD_RULE}. {HELD}')


def _competing(s: Slots, text: str) -> tuple[str, str]:
    """combination.competing_hold (copied); with no rival given (read time's item_slots names none), the code alone,
    another proposed code said only possibly to account for its act."""
    service = service_phrase(s.family) if s.family is not None else 'service'
    if not s.codes:
        return (f'{s.code} is proposed for a documented act that another proposed code may also account for. Reject the '
                'code or codes the documentation does not support; the one left is then ready for review.',
                f'{s.code} is proposed for one documented act of the {service} that another proposed code may also '
                'account for. CPT Studio does not choose between them: each is held for the reviewer, not excluded, '
                'until the others are rejected.')
    codes = join([s.code, *s.codes])
    return (f'{codes} are proposed for the same documented act. Reject the code or codes the documentation does not '
            'support; the one left is then ready for review.',
            f'{codes} are each proposed for one same documented act of the {service}. CPT Studio does not choose '
            'between them: each is held for the reviewer, not excluded, until the others are rejected.')


def _service_date(s: Slots, text: str) -> tuple[str, str]:
    said = _sides(text, s.statements, 'service_date')
    if len(said) >= 2:
        dates = '; '.join(quote(item, 140) for item in said)
        return (SERVICE_DATE_QUESTION, f'The document states more than one date of service ({dates}); every service and '
                                       'every dated reference check depends on it.')
    return SERVICE_DATE_QUESTION, SERVICE_DATE_REASON


# --- D225 (repair r3c): the items step r4a words for refute-4a-r2 P5, P6, P7, P10 and P11 -----------------------------
#
# Each sentence names the act and the fact that is actually unknown, true in every state its slots allow. D254 (repair
# r3c of round w8r): a slot that contradicts the message is worded as its absence, never refused.


# What a contradicted attribute is about, for every Attribute (CONFLICT_ATTRIBUTE; P7), each read after 'about': '{act}'
# is the act the item names (act_phrase, less CONTESTED_LABEL_PARTS: a lesion's or a section's fact names the act it is
# about); '{session}' is the session a session's attribute is about, named by its service (session_label: refute-r3c-r1
# P1 - the held fact of a session's attribute is keyed by the act it holds, conflict:<that act's kind>, while the fact
# itself is the session's, so the act never stands in for the session).
ATTRIBUTE_PHRASES: Mapping[Attribute, str] = MappingProxyType({
    Attribute.DATE_OF_SERVICE: 'the date of service',
    Attribute.OTHER_DATES_ROLE: 'what a date the document gives refers to',
    Attribute.DOCUMENTING_CLINICIAN: 'who documented this encounter',
    Attribute.ROLE: 'the role of a person or of a part of the document',
    Attribute.OWNER: 'whose entry a part of the document is',
    Attribute.OCCASION: 'when the acts a part of the document tells were done',
    Attribute.PERFORMER: 'who performed the {act}',
    Attribute.PERFORMER_PERSON: 'who performed the {act}',
    Attribute.EXAMINATION: 'which documented act was the {session} itself',
    Attribute.KIND: 'what was done',
    Attribute.ENCOUNTER: 'whether the {session} was part of this encounter',
    Attribute.TRACT: 'which part of the digestive tract the {session} examined',
    Attribute.APPROACH: 'the route of the {session}',
    Attribute.THROUGH: 'the altered anatomy the {session} was passed through',
    Attribute.REACHED: 'how far the {session} reached',
    Attribute.DEVICE_REACHED: 'how far a device reached in the {session}',
    Attribute.REACHED_ANATOMY: 'which altered anatomy the {session} reached',
    Attribute.COMPLETION: 'whether the {session} was completed',
    Attribute.STATIONS: 'which parts the {session} examined',
    Attribute.PART_OF_SESSION: 'whether the {session} was part of another procedure',
    Attribute.TYPE: 'what altered anatomy the document records',
    Attribute.ORGAN: 'which organ an altered anatomy the document records is in',
    Attribute.SUBTYPE: 'what kind of anastomosis the document records',
    Attribute.JOINS: 'what an anastomosis the document records joins',
    Attribute.MULTIPLICITY: 'whether the lesion of the {act} is one lesion or a group',
    Attribute.PLACES: 'where the lesion of the {act} lies',
    Attribute.DISTINCT_FROM: 'whether the lesion of the {act} is distinct from another lesion',
    Attribute.SAME_AS: 'whether the lesion of the {act} is the same as another lesion',
    Attribute.RESTATEMENTS_ROLE: 'whether another passage restates the {act}',
    Attribute.OTHER_CLASS: 'what kind of service the {act} was',
    Attribute.STATUS: 'whether the {act} was done',
    Attribute.SESSION: 'which procedure the {act} was done in',
    Attribute.DATE_RELATION: 'when the {act} was done',
    Attribute.DATE: 'the date of the {act}',
    Attribute.TARGET_LESION: 'which lesion the {act} was done on',
    Attribute.TARGET_STRUCTURE: 'which structure the {act} was done on',
    Attribute.TARGET_PLACES: 'where the {act} was done',
    Attribute.TARGET_ANATOMY: 'which altered anatomy the {act} was done at',
    Attribute.TARGET_DUCT: 'which duct the {act} was done in',
    Attribute.TECHNIQUE_DEVICE: 'which device was used for the {act}',
    Attribute.TECHNIQUE_ROUTE: 'how the {act} reached the tissue',
    Attribute.PURPOSE: 'why the {act} was done',
    Attribute.CAUSE: 'what caused the bleeding the {act} treated',
    Attribute.CAUSE_EVENT: 'which act caused the bleeding the {act} treated',
    Attribute.PART_OF: 'whether the {act} was part of another act',
    Attribute.PART_RELATION: 'how the {act} was part of another act',
    Attribute.YIELD: 'what the {act} retrieved',
    Attribute.ACCESS_OUTCOME: 'whether the {act} achieved access',
    Attribute.SCOPE_BREADTH: 'how much a statement in the document covers',
    Attribute.SCOPE_TARGETS: 'what a statement in the document is about',
    Attribute.SCOPE_SEGMENT: 'which segment a statement in the document covers',
    Attribute.SCOPE_COVERS: 'which acts a statement in the document covers',
    Attribute.SCOPE_EXCEPTS: 'which acts a statement in the document leaves out',
    Attribute.VISIT_BASIS: 'the basis for the level of the {act}',
    Attribute.VISIT_SEPARATELY_IDENTIFIABLE: 'whether the {act} was a significant, separately identifiable service',
    Attribute.ENTRY: 'whose entry the {act} is told in',
})
# contract/types.Attribute's session attributes (its "a session" group; kind, which an event shares, is worded with no
# subject): a conflict about one is about the session, '{session}' in ATTRIBUTE_PHRASES, never '{act}' (refute-r3c-r1
# P1); the act's own sentence is never quoted as one of its sides.
SESSION_ATTRIBUTES = frozenset({Attribute.EXAMINATION, Attribute.ENCOUNTER, Attribute.TRACT, Attribute.APPROACH,
                                Attribute.THROUGH, Attribute.REACHED, Attribute.DEVICE_REACHED,
                                Attribute.REACHED_ANATOMY, Attribute.COMPLETION, Attribute.STATIONS,
                                Attribute.PART_OF_SESSION})
# The parts of the act's label (act_phrase) that state the value a conflict about each attribute contests
# (refute-r3c-r1 P6): left out of that conflict's sentence, so it never states one side's value as the act's - a device
# conflict names no device, a place or lesion conflict no place and no lesion words.
CONTESTED_LABEL_PARTS: Mapping[Attribute, tuple[str, ...]] = MappingProxyType({
    Attribute.TECHNIQUE_DEVICE: ('device',),
    Attribute.TARGET_PLACES: ('place', 'lesion'),
    Attribute.TARGET_LESION: ('place', 'lesion'),
    Attribute.PLACES: ('place', 'lesion'),
    Attribute.MULTIPLICITY: ('lesion',),
    Attribute.DISTINCT_FROM: ('lesion',),
    Attribute.SAME_AS: ('lesion',),
})
# The noun of a session whose family names no service (SESSION_SERVICES): an E/M of another setting is a visit; any
# other such session (sedation, another GI service, a service outside the GI profiles) is a procedure (session_label).
SESSION_NOUNS: Mapping[SessionKind, str] = MappingProxyType({SessionKind.EM_OTHER: 'visit'})
# What an unlisted entry on a code's evidence states (UNLISTED_EVIDENCE; P11), by its nature; '{kind}' is its kind
# with its article ('an act' when it names none)
UNLISTED_STATED: Mapping[UnlistedWhat, str] = MappingProxyType({
    UnlistedWhat.ACT: 'documents {kind}', UnlistedWhat.DENIAL: 'states that {kind} was not done',
    UnlistedWhat.DOUBT: 'leaves {kind} in doubt'})
# Every approach as a route (EXAMINATION_APPROACH; P5): APPROACH_WORDS' three (classes.ROUTE_PHRASES), and the others
# in their form
ROUTE_WORDS: Mapping[Approach, str] = MappingProxyType({
    Approach.ORAL: 'through the mouth', Approach.TRANSNASAL: 'through the nose', Approach.TRANSANAL: 'through the anus',
    Approach.THROUGH_STOMA: 'through a stoma', Approach.THROUGH_POUCH: 'through a pouch',
    Approach.THROUGH_GASTROSTOMY: 'through a gastrostomy', Approach.PERCUTANEOUS: 'through the skin'})
# FINAL-V2 4.3 LOWER: the EUS class that needs a route of its own - the stoma class, the approach through_stoma beside
# an anatomy entry of type stoma (P5)
EUS_CLASS_ROUTES: Mapping[engine_catalogue.EusClass, Approach] = MappingProxyType({
    engine_catalogue.EusClass.STOMA: Approach.THROUGH_STOMA})
# XCHG's acts (D105, D127), and why their duct decides the code: ercp.exchange_question's two reasons (copied; pinned)
STENT_KINDS = frozenset({Kind.STENT, Kind.STENT_REMOVAL, Kind.STENT_EXCHANGE})
EXCHANGE_PAIR_RULE = ('A stent removed and replaced in the same duct at one session is one stent exchange (43276), not '
                      'a removal (43275) and a placement (43274).')
EXCHANGE_PART_RULE = ('A removal or a placement that is part of a stent exchange is reported with the exchange '
                      '(43276), not separately (43275, 43274).')
# STRUCT:pfc's sentence of the place it sets apart (D120, D136, D145: no supported place biliary or hepatic)
APART_PLACE_RULE = ('CPT Studio does not read an act placed in the biliary tree or the liver as the drainage of a '
                    'pancreatic fluid collection.')


def with_article(label: str) -> str:
    """``label`` (CPT Studio's own act label, never the document's words) with its indefinite article."""
    return f'{"an" if label[:1].lower() in "aeiou" else "a"} {label}'


def session_label(s: Slots) -> str:
    """The session a session attribute's conflict is about (refute-r3c-r1 P1): its service, from ``family`` (Slots: the
    session's kind), as act_phrase names an examination; for a family that names no service, its noun (an E/M of another
    setting is a visit), else 'examination' when the act is the examination itself, else 'procedure' - never the act the
    item names, whose kind only keys the fact, and never a profile's capitalised label inside a sentence."""
    service = SESSION_SERVICES.get(s.family) if s.family is not None else None
    if service:
        return kind_label(service)
    if s.family is not None and s.family in SESSION_NOUNS:
        return SESSION_NOUNS[s.family]
    return 'examination' if s.act is Kind.EXAMINATION else 'procedure'



# ATTRIBUTE_PHRASES with the act through its article (D254 rule 2): each phrase's 'the {act}' (every '{act}' in the table
# follows 'the ': tested) read as '{act}', which the_act fills - 'the snare removal', or NO_KIND_LABEL alone.
_ATTRIBUTE_FORMS: Mapping[Attribute, str] = MappingProxyType({
    attribute: phrase.replace('the {act}', '{act}') for attribute, phrase in ATTRIBUTE_PHRASES.items()})


def _conflict_attribute(s: Slots, text: str) -> tuple[str, str]:
    """A contradicted attribute (D225, P7), named: each side's own sentence quoted once (two sides in one sentence quote
    it once); for an act's attribute the act's own sentence when the sides carry none of their own; never "performed and
    not performed". A session's attribute is the session's (session_label), and the act's own sentence is no side of it:
    with no side's sentence, nothing is quoted (refute-r3c-r1 P1). The act's label leaves out what the conflict contests
    (CONTESTED_LABEL_PARTS; P6). D254: a side with no units is no side, and with no sentence at all - for an act's
    attribute too - nothing is quoted."""
    attribute = _req(s.attribute, 'attribute')
    contested = CONTESTED_LABEL_PARTS.get(attribute, ())
    label = _act_label(text, s.act, s.family, None if 'device' in contested else s.device,
                       () if 'lesion' in contested else s.lesion, None if 'place' in contested else s.place)
    what = _ATTRIBUTE_FORMS[attribute].format(act=_the(label, named_kind(s.act)), session=session_label(s))
    of_session = attribute in SESSION_ATTRIBUTES
    said = _sides(text, s.statements, 'conflict_attribute')
    if not said and not of_session:
        said = _sides(text, (s.words,), 'conflict_attribute')
    if not said:
        return (f'The document is not consistent about {what}. Which is correct for this encounter?',
                f'The document is not consistent about {what}. Each value it states is kept; none is chosen.')
    if len(said) == 1:
        return (f'The document is not consistent about {what} ({quote(said[0], 120)}). Which is correct for this '
                'encounter?',
                f'The document is not consistent about {what} ({quote(said[0], 140)}). Each value it states is kept; '
                'none is chosen.')
    asked = join([quote(item, 120) for item in said])
    kept = '; '.join(quote(item, 140) for item in said)
    rest = 'Both are kept; neither is chosen.' if len(said) == 2 else 'Each is kept; none is chosen.'
    return (f'Statements in the document disagree about {what}: {asked}. Which is correct for this encounter?',
            f'Statements in the document disagree about {what} ({kept}). {rest}')


def _unlisted_evidence(s: Slots, text: str) -> tuple[str, str]:
    """3.2.6 rule 2's item (D225, P11): the unlisted entry on the code's evidence, by its own nature and kind (never the
    code's act said to be in doubt; D254 rule 2: an entry of no kind is NO_KIND_LABEL), quoting its own unit. D254: an
    entry with no units is named without a quote; the units of several statements are its one passage, each run once
    (span_text), as one statement's several units are."""
    kind = s.unlisted_kind
    stated = UNLISTED_STATED[_req(s.unlisted_what, 'unlisted_what')].format(
        kind=_a(kind_words(kind), named_kind(kind)))
    unit = _unit_words(text, tuple(span for statement in s.statements for span in statement), 'unlisted_evidence',
                       'statements')
    return (f'The evidence passage of {s.code}{_shown(unit, 120)} {stated}. {performed_question(s.code)}',
            f'The evidence passage of {s.code}{_shown(unit, 140)} {stated}, which CPT Studio\'s reading of the document '
            f'does not account for. {HELD}')


def _eus_route(s: Slots) -> tuple[Approach | None, str]:
    """The route the slots' EUS class needs (EUS_CLASS_ROUTES: the stoma class's; None for a class that needs none of
    its own) and the class words."""
    exam_class = _req(s.exam_class, 'exam_class')
    return EUS_CLASS_ROUTES.get(exam_class), _eus_class_words(s.code, exam_class)


_EXAM = 'The documented endoscopic ultrasound examination'


def _examination_passed(s: Slots, text: str, approach: Approach, required: str, message: str) -> tuple[str, str]:
    """EXAMINATION_APPROACH's form (P5): the examination passed by ``approach``, the class words, its route words quoted
    when they are not its own sentence."""
    words = _words(s, text, message)
    said, told = _route_told(s, text, words, message)
    return (f'{_EXAM}{_shown(words)} was passed {ROUTE_WORDS[approach]}{told}. Was {required} performed on the date of '
            'service?',
            f'The endoscopic ultrasound examination is documented as passed {ROUTE_WORDS[approach]}{said}; {s.code} '
            f'accounts for {required}, which CPT Studio could not find in the document.')


def _examination_route(s: Slots, text: str) -> tuple[str, str]:
    """LOWER's stoma class (D225, P5; RANK row 8, "approach for a class"): its approach not established - or established
    through the stoma while the stoma itself (an anatomy entry of type stoma) is not - asked as the route, never as R6's
    extent sentence. ``approaches``: the routes the encounter's anatomy opens (a stoma entry established). D254: an
    approach established otherwise than the class's route is worded as not established (the class's route is what the
    question asks); the route and the stoma both given - the item still asks the route - as the stoma it was passed
    through not confirmed; a class that needs no route of its own as the route of the examination not confirmed (or
    passed by the approach given). D267 (repair r3c of round w9r; refute-r4a-r2 F5): a stoma the Fill marks as only
    possible (``possible_approaches``) is worded as one not established - "through a stoma", "that the patient has a
    stoma" - never as "the documented stoma": the stoma class reads no through (its route is the approach beside an
    anatomy entry of type stoma), so a stoma only possible here is one whose type is not established."""
    route, required = _eus_route(s)
    words = _words(s, text, 'examination_route')
    shown = _shown(words)
    if route is None:
        if s.approach is not None:
            return _examination_passed(s, text, s.approach, required, 'examination_route')
        return (f'CPT Studio could not confirm from the document the route of the documented endoscopic ultrasound '
                f'examination{shown}. Was {required} performed on the date of service?',
                f'{s.code} accounts for {required}; CPT Studio could not confirm from the document the route of the '
                f'endoscopic ultrasound examination. {HELD}')
    anatomy = APPROACH_ANATOMY[route]
    documented = anatomy in _route_anatomy(s)[0]
    if s.approach is not route:
        way = f'through the documented {anatomy}' if documented else ROUTE_WORDS[route]
        reached = _reach(s)
        unknown = (f'{_EXAM}{shown} reached the {reached}; CPT Studio could not confirm from the document whether it was '
                   f'passed {way}.' if reached else
                   f'CPT Studio could not confirm from the document whether the documented endoscopic ultrasound '
                   f'examination{shown} was passed {way}.')
        return (f'{unknown} Was {required} performed on the date of service?',
                f'{s.code} accounts for {required}; CPT Studio could not confirm from the document whether the '
                f'endoscopic ultrasound examination was passed {way}. {HELD}')
    said, told = _route_told(s, text, words, 'examination_route')
    missing = (f'that it was passed through the documented {anatomy}' if documented
               else f'that the patient has a {anatomy}')
    return (f'{_EXAM}{shown} is stated to be passed {ROUTE_WORDS[route]}{told}; CPT Studio could not confirm from the '
            f'document {missing}. Was {required} performed on the date of service?',
            f'{s.code} accounts for {required}; the document states that the endoscopic ultrasound examination was '
            f'passed {ROUTE_WORDS[route]}{said}, and CPT Studio could not confirm from the document {missing}. {HELD}')


def _examination_approach(s: Slots, text: str) -> tuple[str, str]:
    """LOWER's stoma class (D225, P5): an approach established other than the class's - the class explanation, in
    EXAMINATION_CLASS's form, naming the route; the examination's route words quoted when they are not its own
    sentence. D254 rule 3's reading for this class: with no other approach given (none, or the class's own, which the
    message's fact contradicts), the class is worded without naming a route."""
    route, required = _eus_route(s)
    approach = s.approach if s.approach is not None and s.approach is not route else None
    if approach is not None:
        return _examination_passed(s, text, approach, required, 'examination_approach')
    words = _words(s, text, 'examination_approach')
    return (f'CPT Studio could not confirm from the document that the documented endoscopic ultrasound examination'
            f'{_shown(words)} was passed by the route this code describes. Was {required} performed on the date of '
            'service?',
            f'The endoscopic ultrasound examination is documented{_shown(words, 160)}; {s.code} accounts for '
            f'{required}, which CPT Studio could not find in the document.')


def _same_duct(s: Slots, text: str) -> tuple[str, str]:
    """XCHG's two-act duct question (D225, P6; DUCT's two-act form): ``act`` is the act whose duct is not established
    and ``whole`` its counterpart, so the reason names the act whose duct is unknown - never the code's own act whose
    duct is supported - and why the duct decides the code (ercp.exchange_question's reasons). D246 (r4a Q4 option (a);
    D160 (3)): an act with no units is named without a quote, either act of the two. D254: either act may name no kind
    (NO_KIND_LABEL); the exchange's reason is given only for the pair it is about (a removal and a placement; an
    exchange beside a removal or a placement)."""
    kind, other = s.act, s.whole
    act, counterpart = the_act(text, s), _the(kind_words(other), named_kind(other))
    if kind is not None and other is not None and kind is not other and {kind, other} <= STENT_KINDS:
        rule = f' {EXCHANGE_PART_RULE if Kind.STENT_EXCHANGE in (kind, other) else EXCHANGE_PAIR_RULE}'
    else:
        rule = ''
    own = _unit_words(text, s.words, 'same_duct', 'words')
    theirs = _unit_words(text, s.whole_words, 'same_duct', 'whole_words')
    return (f'Were {act}{_shown(own)} and {counterpart}{_shown(theirs)} done in the same duct?',
            f'CPT Studio could not confirm from the document in which duct {act} was done.{rule} {HELD}')


def _structure_place(s: Slots, text: str) -> tuple[str, str]:
    """STRUCT:pfc (43240; D225, P10): the explanation naming the place the rule read - a supported place biliary or
    hepatic, which sets the act apart from a pancreatic fluid collection's drainage (APART_PLACE_RULE). D254: any other
    place given is named without that rule - the rule never said of a place it does not set apart - and no place as
    "another structure"."""
    this, said, question = _structure_parts(s, text, 'structure_place')
    place = s.place
    if place is not None and engine_anatomy.in_regions(place, engine_catalogue.DEFINING_TARGET_APART):
        return (question, f'{s.code} {_PFC_WORDS}; the document places {this} at the {landmark_label(place.value)}{said}. '
                          f'{APART_PLACE_RULE} {HELD}')
    label = landmark_label(place.value) if place is not None else ''
    where = f'at the {label}' if label else 'at another structure'
    return question, f'{s.code} {_PFC_WORDS}; the document places {this} {where}{said}. {HELD}'


# --- D246 (repair r3c): 3.2.6 rule 3's synthetic act (r4a R4 (a)) ----------------------------------------------------

SYNTHETIC_UNACCOUNTED = "which CPT Studio's reading of the document does not account for"


def _synthetic_act(s: Slots, text: str) -> tuple[str, str]:
    """3.2.6 rule 3's synthetic act (D246; r4a R4 (a), Q3): a kept unlisted ACT - an act the document states that CPT
    Studio's reading does not account for - named by its own kind, as UNLISTED_EVIDENCE names an unlisted entry's kind
    (D254 rule 2: NO_KIND_LABEL when it names none: ``act`` empty, or Kind.OTHER), and quoting its own unit (``words``).
    Only the kind: a device, a place, a lesion or a session's service is no fact of an entry CPT Studio's reading does
    not hold - an unlisted examination is "an examination", never the session it may be told in, which the reading does
    account for. The act is never said to be in doubt (DOUBT's sentence, true for an unlisted doubt), which is untrue of
    an act the document states. With no units, the act is named without a quote (D160 (3); r4a Q4 option (a))."""
    kind = _a(kind_words(s.act), named_kind(s.act))
    words = _unit_words(text, s.words, 'synthetic_act', 'words')
    return (f'The document documents {kind}{_shown(words)}, {SYNTHETIC_UNACCOUNTED}. Confirm whether it was done on the '
            'date of service.',
            f'The document documents {kind}{_shown(words, 140)}, {SYNTHETIC_UNACCOUNTED}. {HELD}')


# --- D258 (repair r3c of round w8r): a statement that names no session (r4a QP2, QD; r4c Q1) --------------------------

UNLISTED_SCOPE_UNNAMED = 'which names no procedure session'


def _unlisted_scope(s: Slots, text: str) -> tuple[str, str]:
    """DECISIONS D258: 3.2.6 rule 4's pair of a statement that names no procedure session (a kept unlisted doubt or
    denial with no card, or a card naming a session the FactSet does not hold) with the held session's examination.
    The question names that examination by its service (``family``; 'examination' when none is given), quoting its own
    sentence (``words``), and asks whether it is documented as done on the date of service - a member's "documented"
    releases, "not documented" excludes; the reason quotes the statement (``statements``) and says it names no
    procedure session. It never says the document leaves that examination in doubt or denies it, and it names no nature
    of the statement (a doubt, a denial). With no statement of units, the statement is named, not quoted. D281 (step
    f3w; build list B6, G3-27): "documented as done" says row 7's done, "documented as performed, in full or in part, on
    the date of service" (DONE_IN_PART), so a member asked about a begun examination never answers "Not documented"
    truthfully."""
    noun = _session_noun(s)
    words = _words(s, text, 'unlisted_scope')
    said = _sides(text, s.statements, 'unlisted_scope')
    if not said:
        stated = 'A statement in the document names no procedure session'
        about = 'it is'
    elif len(said) == 1:
        stated = f'The document states {quote(said[0], 140)}, {UNLISTED_SCOPE_UNNAMED}'
        about = 'it is'
    else:
        stated = f'The document states {join([quote(item, 140) for item in said])}, which name no procedure session'
        about = 'they are'
    return (f'Is the {noun}{_shown(words)} {DONE_IN_PART}?',
            f'{stated}; CPT Studio could not confirm from the document whether {about} about the {noun}. {HELD}')


def _session_noun(s: Slots) -> str:
    """The held session's examination as UNLISTED_SCOPE and DIGITAL_SCOPE name it: its service (``family``), a visit for
    an E/M of another setting (SESSION_NOUNS), else 'examination' (no family given: any session's)."""
    service = SESSION_SERVICES.get(s.family) if s.family is not None else None
    if service:
        return kind_label(service)
    return SESSION_NOUNS.get(s.family, 'examination') if s.family is not None else 'examination'


# --- D280.3 and D284 (step f3w of AMENDMENT-2's build round; build list B1, B7) --------------------------------------

DIGITAL_UNCONFIRMED = 'a statement whose technique CPT Studio could not confirm from the document'
DIGITAL_TECHNIQUES = ' (the document states more than one technique for it)'


def _digital_open(s: Slots, noun: str, sides: Sequence[str]) -> str:
    """DIGITAL_SCOPE's open fact (D280.3), said of the claimed examination ("it"): with no ``attribute`` - a pair whose
    statement it is - whether it is about the held session's examination (D258's clause); else by the held fact's RANK
    row (``held``) and attribute: a conflict its sides (or, with one side or none, that the document is not consistent
    about that attribute), a doubt "left in doubt", another role's entry (``owner``; whose entry, when none is given), its
    date, its performer; at any other row the procedure it was done in or what was done when its session or its kind is
    the attribute, "not established as done on the date of service" for its status, else D258's clause. Each true for
    every state its slots allow."""
    rank, attribute = s.held, s.attribute
    about = f'CPT Studio could not confirm from the document whether it is about the {noun}'
    if attribute is None:
        return about
    if rank is engine_requirements.Rank.CONFLICT:
        what = _ATTRIBUTE_FORMS[attribute].format(act='it', session=session_label(s))
        if len(sides) > 1:
            return f'statements in the document disagree about {what} ({"; ".join(quote(item, 140) for item in sides)})'
        if sides:
            return f'the document is not consistent about {what} ({quote(sides[0], 140)})'
        return f'the document is not consistent about {what}'
    if rank is engine_requirements.Rank.DOUBT:
        return 'the document leaves it in doubt'
    if rank is engine_requirements.Rank.ENTRY:
        entry = OWNER_ENTRIES.get(s.owner) if s.owner is not None else None
        if entry:
            return f'it is told only in {entry}'
        return 'CPT Studio could not confirm from the document whose entry it is told in'
    if rank is engine_requirements.Rank.TIME:
        return 'CPT Studio could not confirm from the document when it was done'
    if rank is engine_requirements.Rank.PERFORMER:
        return 'CPT Studio could not confirm from the document who performed it'
    if attribute is Attribute.SESSION:
        return 'CPT Studio could not confirm from the document in which procedure it was done'
    if attribute is Attribute.KIND:
        return 'CPT Studio could not confirm from the document what was done'
    if rank is engine_requirements.Rank.STATUS:
        return 'it is not established as done on the date of service'
    return about


def _digital_scope(s: Slots, text: str) -> tuple[str, str]:
    """DECISIONS D280.3 (build list B1): a hold resting on an examination whose device claims manual without establishing
    it, asked as D258 asks. The question names the held session's examination by its service (``family``; 'examination'
    when none is given) and asks whether it is documented as performed, in full or in part, on the date of service
    (DONE_IN_PART), quoting only ``words`` - the session's examination that may be quoted, never the claimed one. The
    reason quotes the claimed examination's own words (``statements``' first) as a statement whose technique CPT Studio
    could not confirm (with ``techniques``, that the document states more than one), and states its open fact
    (``_digital_open``; a conflict's sides are ``statements``' rest, each quoted once). It never asks about the claimed
    examination itself - a truthful "Not documented" about it would exclude the code (D258) - and never names it by the
    session's service. With no statement units, it is named, not quoted."""
    noun = _session_noun(s)
    words = _words(s, text, 'digital_scope')
    first = next(iter(_sides(text, s.statements[:1], 'digital_scope')), '')
    sides = _sides(text, s.statements[1:], 'digital_scope')  # a conflict's sides, the claimed one's own among them
    if sides == [' '.join(first.split())]:  # its one side is the statement already quoted: quoted once
        sides = []
    techniques = DIGITAL_TECHNIQUES if s.techniques else ''
    stated = (f'The document states {quote(first, 140)}, {DIGITAL_UNCONFIRMED}{techniques}' if first else
              f'A statement in the document names an examination whose technique CPT Studio could not confirm from '
              f'the document{techniques}')
    return (f'Is the {noun}{_shown(words)} {DONE_IN_PART}?', f'{stated}; {_digital_open(s, noun, sides)}. {HELD}')


def _or_codes(codes: Sequence[str]) -> str:
    """Codes joined by 'or' (one of them is what an add-on needs)."""
    return codes[0] if len(codes) == 1 else ', '.join(codes[:-1]) + ' or ' + codes[-1]


def _addon(s: Slots, text: str) -> tuple[str, str]:
    """DECISIONS D284 (G3-15; build list B7): an add-on code its ADDON row holds - none of its primary codes is counted
    for this encounter - from ``code`` and ``codes`` alone (TEXT_FREE: it reads no document text, quotes nothing and asks
    no fact of the add-on's act), true whether no primary was proposed, the reviewer rejected it or a member's answer
    excluded it. ``codes``: its primary codes (engine/assess.primaries); with none given, "a primary code" (D254 rule 1's
    true absence form). A member's "Not documented" says that none is documented, which is what it excludes on."""
    codes = tuple(dict.fromkeys(s.codes))
    if codes:
        primary = f'one of its primary codes ({_or_codes(codes)}), and none of them'
        asked = 'Is one of them'
    else:
        primary = 'a primary code, and none'
        asked = 'Is one'
    return (f'{s.code} is reported only together with {primary} is counted for this encounter. {asked} documented as '
            'performed on the date of service?',
            f'{s.code} is an add-on code: it is reported only together with {primary} is counted for this encounter. '
            f'{HELD}')


_Q, _E = ItemKind.QUESTION, ItemKind.EXPLANATION


def _spec(fact: str, kind: ItemKind, rank: int | None, needs: tuple[str, ...],
          words: Callable[[Slots, str], tuple[str, str]]) -> MessageSpec:
    return MessageSpec(fact, kind, rank, needs, words)


# D254 rule 1 (repair r3c of round w8r): why every item of a message carries each slot its ``needs`` names - the only
# slots a builder may refuse to word without (engine/questions.py, step r4a's file, and studio/interpretation/overlay.py,
# step 5c's, are what make them).
CARRIED: Mapping[str, str] = MappingProxyType({
    'code': "questions.fill sets Fill.code to CodeFacts.code, the held proposal's own code, and overlay.item_slots "
            'passes fill.code (every message but service_date, whose encounter-scope item_slots gives Slots())',
    'family': 'questions.fill sets Fill.family to CodeFacts.family, a required SessionKind - only _own_entry (doubt, '
              "synthetic_act) clears it - and overlay.item_slots passes fill.family (the R6 and member-context items' "
              'label, recognised_only)',
    'act': "a conflict's fact key is conflict:<kind> (questions.fact_of finds a kind in every conflict key) and "
           "questions._specific sets Fill.act to that kind (_conflict_kind; the examination for a session's attribute) - "
           'the conflict items, whose fact key fact_key builds from it; and digital_scope, whose Fill.act '
           "questions._digital_fill always sets (the held conflict's kind, else the examination)",
    'attribute': 'questions.message_of gives conflict_attribute only for a held fact whose attribute is set (and item '
                 "turns a conflict_fact into it only then); questions._specific copies held.attribute",
    'unlisted_what': 'questions._refined gives unlisted_evidence only for a held fact in raised.evidence, and '
                     "questions._specific copies that entry's what (UnlistedStatement.what is required)",
    'exam_class': "questions.message_of gives examination_route and examination_approach only when the code's EUS class "
                  'is the stoma class (_stoma_route), and Fill.exam_class is CodeFacts.exam_class',
    'held': "questions._refined gives digital_scope only for a held fact resting on a claimed digital examination, and "
            "questions._digital_fill sets Fill.held to that held fact's RANK row (every held fact a rule raises on an "
            'examination or a pair carries one) and Fill.act to its conflict kind, else the examination (D280.3)',
})

# Every message id's entry (FINAL-V2 4.8's RANK rows; 4.3's unmet and established-otherwise columns). ``needs`` (D254 rule
# 1): only slots CARRIED names - the code, the R6 label's family, a conflict's act and attribute, an unlisted entry's
# nature, the stoma EUS class.
MESSAGES: Mapping[Message, MessageSpec] = MappingProxyType({
    Message.CONFLICT: _spec('conflict', _Q, 1, ('act',), _conflict),
    Message.CONFLICT_FACT: _spec('conflict', _Q, 1, ('act',), _conflict_fact),
    Message.DOUBT: _spec('performed_status', _Q, 2, (), _doubt),
    Message.STATEMENT_SCOPE: _spec('statement_scope', _Q, 3, (), _scope),
    Message.STATUS: _spec('performed_status', _Q, 4, (), _status),
    Message.NOT_DOCUMENTED: _spec('performed_status', _Q, 4, ('code',), _not_documented),
    Message.ATTEMPTED: _spec('performed_status', _E, 4, ('code',), _attempted),
    Message.UNPROFILED: _spec('performed_status', _E, 4, ('code',), _unprofiled),
    Message.NOT_LINKED: _spec('performed_status', _E, 4, ('code',), _not_linked),
    Message.RECOGNISED_ONLY: _spec('performed_status', _E, 4, ('code', 'family'), _recognised_only),
    Message.UNRECONCILED: _spec('performed_status', _E, 4, ('code',), _unreconciled),
    Message.ENTRY: _spec('event_entry', _Q, 5, (), _entry),
    Message.ANOTHER_ENTRY: _spec('event_entry', _E, 5, (), _another_entry),
    Message.TIME: _spec('event_time', _Q, 6, (), _time),
    Message.TIME_BESIDE_VISIT: _spec('event_time', _Q, 6, (), _time_beside_visit),
    Message.PERFORMER: _spec('event_performer', _Q, 7, (), _performer),
    Message.PROCEDURE: _spec('procedure', _Q, 8, (), _procedure),
    Message.ANOTHER_TRACT: _spec('procedure', _E, 8, ('code',), _another_tract),
    Message.ENTEROSCOPY_ROUTE: _spec('procedure', _Q, 8, ('code',), _enteroscopy_route),
    Message.ENTEROSCOPY_APPROACH: _spec('procedure', _E, 8, ('code',), _enteroscopy_approach),
    Message.METHOD: _spec('act_method', _Q, 9, (), _method),
    Message.TECHNIQUE: _spec('technique', _Q, 10, (), _technique),
    Message.STATED_TECHNIQUE: _spec('technique', _Q, 10, (), _stated_technique),
    Message.ANOTHER_TECHNIQUE: _spec('technique', _E, 10, (), _another_technique),
    Message.ROUTE: _spec('technique', _Q, 10, ('code',), _route),
    Message.WALL_INJECTION: _spec('technique', _E, 10, ('code',), _wall_injection),
    Message.ACT_TARGET: _spec('act_target', _Q, 11, (), _act_target),
    Message.SITE: _spec('act_target', _Q, 11, (), _site),
    Message.ANOTHER_SITE: _spec('act_target', _E, 11, (), _another_site),
    Message.DUCT: _spec('act_target', _Q, 11, (), _duct),
    Message.TARGET: _spec('target', _Q, 12, ('family',), _r6('target')),
    Message.STRUCTURE: _spec('target', _Q, 12, ('code',), _structure),
    Message.ANOTHER_STRUCTURE: _spec('target', _E, 12, ('code',), _another_structure),
    Message.STATIONS: _spec('exam_stations', _Q, 13, ('code',), _stations),
    Message.STATION_CLASS: _spec('exam_stations', _E, 13, ('code',), _station_class),
    Message.EXTENT: _spec('extent', _Q, 14, ('family',), _r6('extent')),
    Message.EXAMINATION_CLASS: _spec('extent', _E, 14, ('code',), _examination_class),
    Message.ENTEROSCOPY_CLASS: _spec('extent', _E, 14, ('code',), _enteroscopy_class),
    Message.YIELD: _spec('act_yield', _Q, 15, (), _yield),
    Message.NOTHING_RETRIEVED: _spec('act_yield', _E, 15, (), _nothing_retrieved),
    Message.CANNULATION: _spec('cannulation', _Q, 16, ('family',), _r6('cannulation')),
    Message.PART: _spec('act_part', _Q, 17, (), _part),
    Message.BUNDLING_TARGET: _spec('act_target', _Q, 17, (), _part),
    Message.CAUSE: _spec('act_cause', _Q, 17, (), _cause),
    Message.BUNDLED: _spec('performed_status', _E, 18, (), _bundled),
    Message.EM_BASIS: _spec('em_basis', _Q, 19, ('family',), _r6('em_basis')),
    Message.SEPARATE_EM: _spec('separate_em', _Q, 20, (), _separate_em),
    Message.SEPARATE_EM_DENIED: _spec('separate_em', _E, 20, (), _separate_em_denied),
    Message.BASE_INCLUDED: _spec('base_included', _Q, 21, ('code',), _base_included),
    Message.BASE_EXPLAINED: _spec('base_included', _E, 21, ('code',), _base_explained),
    Message.BASE_WITHIN: _spec('base_included', _E, 21, ('code',), _base_within),
    Message.COMPETING: _spec('competing_codes', _Q, 22, ('code',), _competing),
    Message.SETTING: _spec('setting', _Q, 23, ('family',), _setting),
    Message.PATIENT_STATUS: _spec('patient_status', _Q, 23, ('family',), _r6('patient_status')),
    Message.SERVICE_DATE: _spec('service_date', _Q, None, (), _service_date),
    # D225 (repair r3c): refute-4a-r2 P7, P11, P5 (question and explanation), P6, P10
    Message.CONFLICT_ATTRIBUTE: _spec('conflict', _Q, 1, ('act', 'attribute'), _conflict_attribute),
    Message.UNLISTED_EVIDENCE: _spec('performed_status', _Q, 2, ('code', 'unlisted_what'), _unlisted_evidence),
    Message.EXAMINATION_ROUTE: _spec('procedure', _Q, 8, ('code', 'exam_class'), _examination_route),
    Message.EXAMINATION_APPROACH: _spec('procedure', _E, 8, ('code', 'exam_class'), _examination_approach),
    Message.SAME_DUCT: _spec('act_target', _Q, 11, (), _same_duct),
    Message.STRUCTURE_PLACE: _spec('target', _E, 12, ('code',), _structure_place),
    # D246 (repair r3c): r4a R4 (a) - 3.2.6 rule 3's synthetic act (its kind and its unit, each optional)
    Message.SYNTHETIC_ACT: _spec('performed_status', _Q, 2, (), _synthetic_act),
    # D258 and D253 QX (ii) (repair r3c of round w8r)
    Message.UNLISTED_SCOPE: _spec('performed_status', _Q, 2, (), _unlisted_scope),
    Message.ENTEROSCOPY_THROUGH: _spec('procedure', _Q, 8, ('code',), _enteroscopy_through),
    # D280.3 and D284 (step f3w): DIGITAL_SCOPE's row is D258's (performed_status, rank 2, a question), the shape it is
    # asked in; its clarification keeps the HELD fact's key and rank (fact_key reads ``held`` and ``act``)
    Message.DIGITAL_SCOPE: _spec('performed_status', _Q, 2, ('held', 'act'), _digital_scope),
    Message.ADDON: _spec('performed_status', _Q, 4, ('code',), _addon),
})


def fact_key(message: Message, slots: Slots) -> str:
    """The questions.FORM fact key of ``message``'s item: conflict:<the act's kind> for a conflict (RANK's rank 1),
    else MESSAGES' fact. DIGITAL_SCOPE (D280.3: "the clarification keeps the held fact's key; a message may take its key
    from the item") takes the held fact's: its RANK row's fact key (``held``; RANK names one for each row a
    DIGITAL_SCOPE item rests on - the first for a row of several), conflict:<act> for the conflict row."""
    spec = MESSAGES[message]
    if message is Message.DIGITAL_SCOPE:
        rank = _req(slots.held, 'held')
        key = engine_requirements.RANK[rank][0]
        if key is engine_requirements.FactKey.CONFLICT:
            return f'conflict:{_req(slots.act, "act").value}'
        return str(key.value)
    return f'conflict:{_req(slots.act, "act").value}' if spec.fact == 'conflict' else spec.fact


def build(message: Message, slots: Slots, text: str) -> Worded:
    """The item of ``message`` in CPT Studio's words, from ``slots`` and the revision ``text`` (FINAL-V2 4.8): its fact
    key, kind, question and reason. ValueError - never a fallback sentence - when ``message`` is not a Message, a slot
    every item of the message carries by construction is empty (MESSAGES' ``needs``, CARRIED: D254 rule 1 - after it a
    refusal is a programming error, rule 5), or a span it quotes holds no words or reaches past the text (a span the
    item's revision does not hold: a binding failure)."""
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
