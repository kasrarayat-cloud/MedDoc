"""Section, sentence and clause structure of a canonical clinical text.

A section starts at a heading line ("Findings", "Procedure: Colonoscopy",
"ASSESSMENT AND PLAN:") and runs to the next heading line; text before the
first heading is an ``other`` section with no heading. Every span is a
half-open range over the canonical text, so ``text[start:end]`` is exact.

Labels in ``HEADINGS`` open a section. A key-value line such as
"Date of service: 2026-10-21" or "Extent: cecum" is content, not a heading.
A line that is only an unrecognised "Label:" also opens a section, so the text
under it never inherits the previous section's reading: a plan or history
section when the label says so ("Next procedures:", "Earlier work-up:"),
otherwise an ``other`` section with no default. A label with a verb in it is a
sentence that ends in a colon ("The following were noted:") and opens none,
unless HEADINGS lists it ("Procedures performed today:"); a performed-today
label that answers nothing ("Procedures performed today: none") opens none.
"Referral:", "Orders:", "To do:" and the other plan labels round 3b added are
field labels as often as headings: "Orders: none" is a field, and with an
answer of their own they plan their own line only. Up to the next heading, a
field after them that is one of the report's own fields of a closed list
(extent, depth of insertion, withdrawal, insertion or cecal intubation time,
preparation and its quality, BBPS, sedation, complications, EBL, findings,
retroflexion), or a landmark whose value opens by saying it was reached or
seen ("Cecum: reached without difficulty"), and names no service,
intervention or procedure by its form ("Extent: cecum") reads in the section
in force before them, and every other line is held: an ``other`` section of
its own, with no default (inside a plan or history section that section
reads every line).

A label line without a colon ("Planned procedures", "Further management", a
Word heading paragraph) opens a plan or history section when its words say so
and it ends with the section of a note it names (procedures, plan,
management, work-up ...), or is the plan or the procedures and plan words
only ("Procedures planned", "Plan going forward", never today's); never a
service, an intervention or a landmark. A numbered or bulleted line is read
the same way ("2. Upcoming procedures"), so a statement in a numbered list
("3. Further workup recommended") stays content because it does not end with
its noun. Such a line that reads as a phrase ("Changes of prior radiation
therapy", "Specimens sent for further testing") is a finding or a statement:
inside a procedure, findings or technique section it opens an ``other``
section with no default (elsewhere it opens its plan or history section, as
before), and in a numbered list it is content. A line that starts with the
plan or the procedures and a plan word but is not only that ("Procedure
completed as planned", "Procedures planned for next week"), and a numbered or
bulleted history item ("2. Prior radiation therapy"), are held the same way,
and outside a plan or history section too; another phrase line under such an
``other`` section is read as inside the section it stands in for.

The blocks extraction adds after a PDF page's text, "[PDF form fields on page
N]" and "[PDF annotation text on page N]", are ``other`` sections with no
default: their lines never open sections of their own, each line is a
sentence, and the section before the block resumes after the blank line that
ends it (unless a heading opens on that line, as the next page often does).
The one exception is a form-field line whose own label is a procedure,
findings or technique heading ("Procedure: Upper endoscopy (EGD)"): it reads
as the same printed line would, for that line only, and the block's section
resumes on the next line; a box or option value keeps it silent.
The header an addendum opens with ("ADDENDUM (revision 2, added 2026-10-22
10:00 UTC)") is likewise an ``other`` section with no default, so an addendum
never takes the reading of the section the document ended in.

In a procedure, findings or technique section, a service line after a line cut
on a plan, cancellation or denial verb that its own clause leaves without an
object ("Dr. Smith recommended", then "EUS with FNA of the pancreatic head
mass." on the next line, with or without a list marker) is held: it is an
``other`` section of its own, with no default, and the section before it
resumes on the next line.

A heading whose parts are all procedure, findings or technique headings
("Procedure and findings", "Procedure/Findings") is that kind of heading.

``tables`` is the one table model (interpretation 45): a header row of three
or more " | " cells, each a bare label, over rows of as many cells. A
procedure-summary label ("Procedure summary") straight over a summary table
(an examination column, an extent column with an extent written in it, no
dated row, no line naming its service with an earlier occasion before the next
heading) opens a procedure section in a document whose own title is a
procedure's report and names no visit; a table alone opens nothing. In a
table's data row, a cell that only answers ("No") a column whose subject is
not the row's own service ("Tissue sampled", "Polyps seen", "Antrum biopsy")
is a clause of its own; under a not-done status column ("Cancelled") a "No"
is one too, and any other answer holds the row. ``Layout.columns`` gives each
data cell its column's label, ``Layout.answer_cells`` the answer cells.
"""
from __future__ import annotations

import bisect
import functools
import re
from dataclasses import dataclass
from typing import Optional

from studio.gi import cues
from studio.types import Span

SECTION_KINDS = ('procedure', 'findings', 'technique', 'impression', 'indication', 'history', 'plan', 'assessment',
                 'exam', 'mdm', 'time', 'other')


def _kind(kind: str, *labels: str) -> dict[str, str]:
    return {label: kind for label in labels}


HEADINGS: dict[str, str] = {
    **_kind('procedure', 'procedure', 'procedures', 'procedure performed', 'procedures performed',
            'procedure done', 'procedures done', 'name of procedure', 'procedure name', 'operation',
            'operation performed', 'operations performed', 'procedure note', 'procedure report', 'endoscopy report',
            'operative note', 'operative report', 'service performed', 'services performed',
            # the same headings for this encounter's own procedures (a closed list: a bare label with a verb in
            # it is otherwise a sentence, and the text under it would inherit the previous section)
            'procedure performed today', 'procedures performed today', 'procedure done today', 'procedures done today',
            'intervention performed', 'interventions performed', 'intervention performed today',
            'interventions performed today'),
    **_kind('technique', 'technique', 'procedure technique', 'description of procedure', 'description of the procedure',
            'procedure description', 'procedure details', 'details of procedure', 'details of the procedure',
            'procedure in detail', 'procedure narrative', 'operative technique', 'description'),
    **_kind('findings', 'findings', 'endoscopic findings', 'procedure findings', 'egd findings', 'colonoscopy findings',
            'eus findings', 'ercp findings', 'sigmoidoscopy findings', 'upper endoscopy findings',
            'findings and interventions', 'specimens', 'specimen', 'specimens obtained', 'specimens collected'),
    **_kind('impression', 'impression', 'impressions', 'post-procedure impression', 'postprocedure impression',
            'post-procedure diagnosis', 'postprocedure diagnosis', 'post-procedure diagnoses', 'postoperative diagnosis',
            'post-operative diagnosis', 'final impression', 'endoscopic impression', 'summary', 'conclusion',
            'conclusions'),
    **_kind('indication', 'indication', 'indications', 'indication for procedure', 'indications for procedure',
            'indication for the procedure', 'reason for procedure', 'reason for exam', 'reason for examination',
            'reason for visit', 'reason for referral', 'referral reason', 'chief complaint', 'cc',
            'pre-procedure diagnosis', 'preprocedure diagnosis', 'preoperative diagnosis', 'pre-operative diagnosis'),
    **_kind('history', 'history', 'history of present illness', 'hpi', 'interval history', 'past medical history',
            'past surgical history', 'past medical/surgical history', 'past medical and surgical history', 'pmh',
            'psh', 'medical history', 'surgical history', 'family history', 'social history', 'past history',
            'prior procedures', 'prior endoscopy', 'previous endoscopy', 'endoscopic history', 'procedure history',
            'gi history', 'history and physical', 'pre-procedure history and physical',
            'previous procedures', 'past procedures', 'procedural history', 'prior colonoscopies',
            'previous colonoscopies', 'prior endoscopies', 'previous endoscopies', 'past endoscopy',
            'past endoscopies', 'prior studies', 'previous studies', 'endoscopy history', 'colonoscopy history',
            'prior gi procedures', 'previous gi procedures', 'prior endoscopic procedures',
            'previous endoscopic procedures'),
    **_kind('exam', 'examination', 'physical examination', 'physical exam', 'exam', 'pe', 'vital signs', 'vitals',
            'pre-procedure examination', 'pre-procedure physical examination'),
    **_kind('assessment', 'assessment', 'diagnosis', 'diagnoses', 'clinical impression', 'pre-procedure assessment'),
    **_kind('plan', 'plan', 'plans', 'recommendations', 'recommendation', 'plan of care', 'treatment plan',
            'follow-up', 'follow up', 'followup', 'assessment and plan', 'assessment/plan', 'a/p', 'a and p',
            'impression and plan', 'impression/plan', 'recommendations and plan', 'next steps', 'instructions',
            'discharge instructions', 'post-procedure instructions',
            'impression and recommendations', 'impressions and recommendations', 'impression and recommendation',
            'impression/recommendations', 'impression/recommendation', 'impressions/recommendations',
            'assessment and recommendations', 'assessment and recommendation', 'assessment/recommendations',
            'recommendations/plan', 'plan/recommendations', 'plan and recommendations', 'recommendations and follow-up',
            'follow-up plan', 'follow-up recommendations', 'post-procedure plan', 'postprocedure plan',
            'post procedure plan', 'post-procedure recommendations', 'postprocedure recommendations',
            'post-procedure care', 'disposition and plan', 'plan and disposition', 'management', 'management plan',
            'further management', 'planned procedures', 'future plan', 'future plans',
            # orders, referrals and pending procedures name what is still to be done (a closed list)
            'pending procedures', 'pending procedure', 'pending orders', 'orders', 'referrals', 'referral', 'to do',
            'to-do', 'procedure to be done', 'procedures to be done', 'procedure to be performed',
            'procedures to be performed', 'procedures that will be performed',
            # discussion, counseling and education never document a procedure done at this encounter
            'discussion', 'discussions', 'counseling', 'counselling', 'patient counseling', 'patient counselling',
            'patient education', 'education', 'counseling and education', 'education and counseling',
            'risks and benefits', 'risks, benefits and alternatives', 'risks, benefits, and alternatives',
            'risks benefits and alternatives', 'recommendations discussed', 'shared decision making',
            'shared decision-making'),
    **_kind('mdm', 'medical decision making', 'medical decision-making', 'mdm', 'decision making'),
    **_kind('time', 'time', 'total time', 'time statement', 'time spent', 'visit time', 'time documentation'),
    **_kind('other', 'medications', 'current medications', 'medication', 'allergies', 'review of systems', 'ros',
            'sedation', 'anesthesia', 'consent', 'informed consent', 'complications', 'estimated blood loss', 'ebl',
            'disposition', 'signature', 'attestation', 'instrument', 'instruments', 'equipment', 'providers', 'staff',
            'bowel preparation', 'bowel prep', 'preparation', 'prep', 'quality of preparation'),
}

# Round 3b's plan labels (75a3cfac7, e7bc88a) are field labels as often as headings ("Referral: Dr. B. Synthetic",
# "Orders: none"). Round 4 structure:5: a no-answer value (_SEC_NO_ANSWER) is a field, as at R3B-BASE. Round 4c
# regression:2 and sections:5: with an answer of their own they speak for their own line only (see layout).
_SEC_FIELD_PLAN_LABELS = frozenset(('pending procedures', 'pending procedure', 'pending orders', 'orders', 'referrals',
                                    'referral', 'to do', 'to-do', 'procedure to be done', 'procedures to be done',
                                    'procedure to be performed', 'procedures to be performed',
                                    'procedures that will be performed'))
# A field's whole value when it answers nothing: "none", "N/A", "not applicable", "no", "nil" (optionally with a
# period). gi3 fix round 1 (cost-1, the same shape found beside it): its blank runs are read once (possessive). With
# plain runs, a value that answers and goes on after a long run of blanks ("Orders: no" + 20,000 blanks + "x") was tried
# at every split of the run between the runs around the optional stop, quadratic in the run (2.0 s at 20,000 blanks,
# at 90377ec6f413 too). Every match is the same span.
_SEC_NO_ANSWER = re.compile(r'[ \t]*+(?:none|n/?a|not[ \t]++applicable|no|nil)[ \t]*+\.?+[ \t]*+', re.A | re.I)
# Round 3b's performed-today procedure labels (e7bc88a). Round 4 structure:9: answered with no answer ("Procedures
# performed today: none", or the bare label with "None" on the next line) they open no procedure section, so the
# plan items after them keep the section in force, as at R3B-BASE.
_SEC_TODAY_LABELS = frozenset(('procedure performed today', 'procedures performed today', 'procedure done today',
                               'procedures done today', 'intervention performed', 'interventions performed',
                               'intervention performed today', 'interventions performed today'))
_SEC_NO_ANSWER_LABELS = _SEC_FIELD_PLAN_LABELS | _SEC_TODAY_LABELS
# A key-value line ("Extent: cecum"): after a field-label line with an answer, it reads in the section in force before
# the label when it is one of the report's own fields (_S2_REPORT_FIELD) and names no service or intervention (see
# layout).
_SEC_FIELD_LINE = re.compile(r'[ \t]*[A-Za-z][^:\n|]{0,39}:[ \t]*\S', re.A)
# Round 4d sections:0: the report's own fields, a closed list read from the line's start to its colon: the extent and
# depth labels (cues' extent label: "Extent:", "Extent reached:", "Furthest extent reached:", "Extent of exam:", "Depth
# of insertion:"), the withdrawal, insertion and cecal intubation times, the preparation and its quality ("Prep
# quality:", "Quality of prep:", "Bowel preparation quality:", "BBPS:", "Boston Bowel Preparation Scale:"), sedation,
# complications, EBL, findings and retroflexion (the fields detect._SEC_NEXT_CELL lists). A field with any other label
# may name what the plan label orders, in words no list knows ("Right hemicolectomy: Dr. B. Synthetic", "CT
# abdomen/pelvis: with contrast", "ESD: ascending colon polyp"): it is held, never read in the section before the label.
# gi3 extent (R4): the extent and depth labels are cues' one class of extent-label words (cues.EXTENT_LABEL_WORDS), so
# this reader and routing never drift ("Deepest point reached:", "Insertion depth:").
_S2_REPORT_FIELD = re.compile(
    r'[ \t]*(?:(?:(?:the|actual|final)[ \t]+)?' + cues.EXTENT_LABEL_WORDS +
    r'|(?:(?:scope|total|cecal|cecum)[ \t]+)?(?:withdrawal|insertion|intubation)[ \t]+time'
    r'|(?:bowel[ \t]+)?prep(?:aration)?(?:[ \t]+quality)?|quality[ \t]+of[ \t]+(?:the[ \t]+)?(?:bowel[ \t]+)?prep(?:aration)?'
    r'|bbps|boston[ \t]+bowel[ \t]+prep(?:aration)?[ \t]+scale(?:[ \t]+\(bbps\))?'
    r'|sedation|complications?|ebl|estimated[ \t]+blood[ \t]+loss|findings|retroflexion)[ \t]*:', re.A | re.I)
# So does a field whose label is a landmark and whose value opens by saying it was reached or seen ("Cecum: reached",
# "Terminal ileum: intubated", "Duodenum: normal", and round 4d's second round: "Cecum: reached without difficulty",
# "Cecum: reached at 6 minutes", "Terminal ileum: intubated, normal mucosa" - the verifier's new problem 4: held, they
# read a complete procedure incomplete at a shallower landmark, where HEAD, 9a9f40301 and d05326ef read the landmark):
# the report's own landmark, never a service; the rest of the value is read by the section as at HEAD. A value that
# opens with any other word ("Ascending colon: 4 cm mass, for right hemicolectomy", "Rectum: internal hemorrhoids") is
# held.
_S2_LANDMARK_VALUE = cues.EXTENT_TAIL | frozenset(('normal', 'unremarkable', 'examined', 'inspected'))
_S2_LANDMARK_STATEMENT = frozenset(('reached', 'intubated', 'entered', 'visualized', 'visualised', 'identified', 'confirmed',
                                    'seen', 'photographed', 'photodocumented', 'documented', 'normal', 'unremarkable',
                                    'examined', 'inspected'))
_S2_VALUE_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*|\d+", re.A)
# Round 4d sections:0, second round (the verifier's new problem 6): what makes a phrase a procedure by its form, as
# routing's gi.other reader reads it (detect._PROCEDURE_WORD): "right hemicolectomy", "hemorrhoidectomy", "anoscopy",
# "rubber band ligation". A field of the closed list, or a landmark field, that names one is held too: "Extent: cecum,
# right hemicolectomy with Dr. B. Synthetic" after "Referral: Colorectal surgery" read performed and 44160 READY, where
# 4347acd24 excluded it as planned.
_S2_PROCEDURE_WORD = re.compile(r'\b(?:\w+(?:scop(?:y|ies)|ectom(?:y|ies)|otom(?:y|ies)|ostom(?:y|ies)|plast(?:y|ies)|'
                                r'centesis|pex(?:y|ies)|rrhaph(?:y|ies))|ligations?|banding|biops(?:y|ies)|injections?|'
                                r'dilat(?:ion|ation)s?|drainage|excisions?|incisions?|resections?|ablations?|sclerotherapy|'
                                r'cauterization|cautery|manometry|debridement|I[ \t]*&[ \t]*D|RBL)\b', re.A | re.I)


def _S2_landmark_field(line: str) -> bool:
    """Whether the field line names a landmark as its label and its value opens by saying it was reached or seen: the
    value's first words are of _S2_LANDMARK_VALUE, one of them a statement (_S2_LANDMARK_STATEMENT; see above)."""
    label, _, value = line.partition(':')
    label = label.strip()
    if not any(pattern.fullmatch(label) for _, _, pattern in cues.UPPER_LANDMARKS + cues.LOWER_LANDMARKS):
        return False
    for word in _S2_VALUE_WORD.finditer(value):
        lowered = word.group(0).lower()
        if lowered not in _S2_LANDMARK_VALUE:
            return False
        if lowered in _S2_LANDMARK_STATEMENT:
            return True
    return False
# The 'other' section of the lines held after such a label (round 4c regression:2, sections:5; see layout).
_SEC_PLAN_HELD_LABEL = 'line after a plan label with an answer of its own'
# A numbered part of a document ("PART 2 - PROCEDURE NOTE: ...", "Section B: Findings") is read by the label after
# its number, so a part never runs on as the section the previous part ended in (its plan, say).
DOCUMENT_PART = r'(?:PART|Part|part|SECTION|Section|section)[ \t]+(?:\d{1,2}|[IVX]{1,4}|[ivx]{1,4}|[A-Z])[ \t]*[-\u2013\u2014:.)][ \t]*'
_PREFIX = re.compile(r'[ \t]*(?:#{1,4}[ \t]*|\*{1,2}[ \t]*|(?:\d{1,2}|[A-Za-z])[.)][ \t]+|' + DOCUMENT_PART + r')?', re.A)
_CLOCK = re.compile(r'[ \t]*\d{1,2}:\d{2}', re.A)
# An unrecognised bare "Label:" (nothing after the colon) is a heading: a plan or history one
# when its words say so, otherwise "other". A sentence that ends in a colon is not a label.
_PLAN_LABEL = re.compile(r'\b(?:plans?|planned|recommend\w*|follow[- ]?up|next|future|upcoming|scheduled|'
                         r'instructions?|disposition|management|further|to\s+do)\b', re.A | re.I)
_HISTORY_LABEL = re.compile(r'\b(?:history|historical|hx|prior|previous|past|earlier|old)\b', re.A | re.I)
_LABEL_VERB = re.compile(r'\b(?:was|were|is|are|be|been|being|has|have|had|will|shall|should|would|could|can|may|'
                         r'might|did|does|do|follows|following|include[sd]?|including|noted|showed|revealed|'
                         r'performed|done)\b', re.A | re.I)


def _bare_label(raw: str) -> bool:
    words = raw.split()
    return (0 < len(words) <= 6 and words[0][0].isalpha() and not _LABEL_VERB.search(raw)
            and raw.rstrip()[-1] not in '.!?;')


# A label line without a colon is a heading only when it names a section of a note, with no service,
# intervention or landmark in it, and ends with the section noun it names: "Planned procedures", "Further
# management", "Earlier endoscopic work-up". Never a statement about one ("Further workup recommended",
# "Previous treatments failed"), a finding that names one ("Prior radiation therapy changes", "History of AS"),
# "Previous anastomosis" or "Prior polypectomy site"; a trailing aside in parentheses is set aside. A numbered or
# bulleted line is read as any line ("2. Upcoming procedures" opens a plan, as at R3B-BASE: round 4 structure:17 and
# release:2 found that round 3b's list-item guard released the planned EMR under it), and a known heading opens
# with a number ("2. Findings").
_COLONLESS_HISTORY = re.compile(r'\b(?:history|historical|hx|prior|previous|past|earlier)\b', re.A | re.I)
_SECTION_NOUN = re.compile(r'\b(?:plans?|procedures?|management|recommendations?|follow[- ]?up|instructions?|steps|'
                           r'disposition|history|work[- ]?ups?|studies|evaluations?|interventions?|appointments?|'
                           r'care|treatments?|therap(?:y|ies)|tests?|testing|imaging|records?)\b', re.A | re.I)
_SECTION_NOUN_LAST = re.compile(r'(?:' + _SECTION_NOUN.pattern + r')[ \t]*$', re.A | re.I)
# Or it starts with the noun of the plan or of the procedures, and a plan word says which: "Procedures planned",
# "Plan going forward", "Procedures recommended" (round 4 release:2: these opened a plan at R3B-BASE).
_SEC_PLAN_FIRST = re.compile(r'(?:plans?|procedures?)\b', re.A | re.I)
# Round 4c sections:2: such a line is a plan label only when every word after the noun is a plan word or this closed tail
# ("Plan going forward", "Plan from here"). A line that only starts with the words ("Procedure completed as planned",
# "Procedure for further evaluation of anemia", "Procedures planned for next week") is held like a phrase line: it
# opens an 'other' section inside a procedure, findings or technique section, never a plan (elsewhere it plans, as
# before), so neither a statement's performed polypectomy is excluded nor a longer label's planned EMR released.
_SEC_PLAN_FIRST_REST = re.compile(r'(?:(?:' + _PLAN_LABEL.pattern + r'|\b(?:going|moving|forward|from|here|onwards?|ahead)\b)'
                                  r'[ \t]*)+', re.A | re.I)
# A line that ends with its section noun but reads as a phrase is a finding or a statement, never such a label (round
# 4 structure:4, a round-2b regression): a comma, a preposition, or an -ing word after its first word ("Changes of
# prior radiation therapy", "Specimens sent for further testing", "Possible stricture, further imaging", "Retained
# stool limiting further evaluation"). It opens an 'other' section with no default, so the lines under it neither
# inherit the findings reading nor are excluded; in a numbered or bulleted list it stays content. A label that starts
# with a section's own name ("Recommendations for follow-up", "History of prior procedures", "Summary of
# recommendations") or whose comma parts all name sections ("Impression, plan") still opens its plan or history section.
_SEC_PHRASE_WORD = re.compile(r'\b(?:of|from|for|with|to|by|in|on|at|after|due|per|via|into|without|than)\b', re.A | re.I)
_SEC_LABEL_PARTICIPLES = frozenset(('upcoming', 'pending', 'ongoing', 'remaining'))
_TRAILING_ASIDE = re.compile(r'[ \t]*\([^()\n]*\)[ \t]*$', re.A)
_LIST_ITEM = re.compile(r'[ \t]*(?:(?:\d{1,2}|[A-Za-z])[.)]|\*(?!\*))[ \t]+', re.A)
# A document title is never such a label: "Office follow-up visit - progress note", "Prior procedure report".
_TITLE_WORDS = re.compile(r'\b(?:note|report|visit|consultation|encounter)\b', re.A | re.I)
FORM_BLOCK = re.compile(r'\[PDF (?P<what>form fields|annotation text) on page \d+\]', re.A)
# The header studio/jobs.py (addendum_block_text) writes before an addendum: a boundary of kind other with no
# default, so an answer never takes the parent's last section (under a Plan, "The colonoscope was advanced to the
# cecum." read uncertain and the extent hold stayed open). Only this exact header; the clock's colon kept it from
# reading as a label.
ADDENDUM_HEADER = re.compile(r'ADDENDUM \(revision \d+, added \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\)', re.A)


def _colonless_label(line: str, listed: bool = False) -> Optional[str]:
    """'plan' or 'history' when a line without a colon is a label of that kind (see above); 'other' when it would
    be one but reads as a phrase (_sec_phrase), or None for such a line in a numbered or bulleted list (``listed``)."""
    named = _TRAILING_ASIDE.sub('', line.strip().rstrip('*#').rstrip())  # "**Upcoming procedures**" names its noun
    if _TITLE_WORDS.search(line) or _service_named(line) or _act_or_place_named(line):
        return None
    plan_first = bool(_SEC_PLAN_FIRST.match(named) and _PLAN_LABEL.search(named) and not cues.TODAY.search(named))
    if plan_first:
        rest = named.split(None, 1)
        if len(rest) == 1 or _SEC_PLAN_FIRST_REST.fullmatch(rest[1]):
            return 'plan'  # "Procedures planned", "Plan going forward" (release:2: as at R3B-BASE); never today's
    if not _SECTION_NOUN_LAST.search(named):
        return 'other' if plan_first else None  # round 4c sections:2: a statement or a longer line, held
    kind = 'plan' if _PLAN_LABEL.search(line) else 'history' if _COLONLESS_HISTORY.search(line) else None
    if kind and _sec_phrase(named):
        return None if listed else 'other'  # structure:4: a finding or a statement, never history or plan
    if kind == 'history':
        # round 4c sections:4: a numbered or bulleted item that names prior therapy ("2. Prior radiation therapy") is held
        # like a phrase line, never a history section over the next item (see layout for a plan or history section).
        # Round 4d sections:5: whatever its marker - DOCX extraction writes none for a Word list ("List Number", "List
        # Bullet"), so the same item came through bare and opened a history section over the next item's polypectomy.
        # A bare line is held only inside a procedure, findings or technique section; elsewhere layout reads it as the
        # history section it opened before (it is no list item there: see the gate's ``widened``).
        return 'other'
    return kind


def _sec_phrase(named: str) -> bool:
    """Whether a colon-less line that ends with a section noun reads as a phrase, not a label (_SEC_PHRASE_WORD)."""
    words = named.split()
    first = normalize_label(words[0])
    if _SECTION_NOUN.match(named) or HEADINGS.get(first, 'findings') not in POSITIVE_KINDS:
        return False  # it starts with a section's own name: "Recommendations for follow-up", "Summary of ..."
    if ',' in named and not all(normalize_label(part) in HEADINGS or _SECTION_NOUN_LAST.search(part.strip())
                                for part in named.split(',')):
        return True
    if _SEC_PHRASE_WORD.search(named):
        return True
    for word in words[1:]:
        lowered = word.lower().strip('*#()')
        if lowered.endswith('ing') and len(lowered) > 4 and lowered not in _SEC_LABEL_PARTICIPLES \
                and not _SECTION_NOUN.fullmatch(lowered):
            return True
    return False


def _sec_phrase_heading(text: str, heading: tuple[str, str, Span]) -> bool:
    """Whether a heading is a colon-less line that reads as a phrase (_colonless_label's 'other'): no known label, no
    colon, no extraction block or addendum header."""
    kind, label, span = heading
    return kind == 'other' and label not in HEADINGS and not span.text.endswith(':') \
        and not FORM_BLOCK.fullmatch(span.text) and not ADDENDUM_HEADER.fullmatch(span.text) \
        and _service_name_only(span.text) is None  # a service line's part reads as its colon form's (layout)


def _act_or_place_named(line: str) -> bool:
    return (any(p.search(line) for _, p, _ in cues.INTERVENTIONS)
            or any(p.search(line) for _, _, p in cues.UPPER_LANDMARKS + cues.LOWER_LANDMARKS))


_TITLE_QUALIFIER = re.compile(r'\b(?:prior|previous|last|planned|scheduled|next|outside|old)\b', re.A | re.I)
_ABBREVIATIONS = frozenset({'dr', 'mr', 'mrs', 'ms', 'st', 'vs', 'approx', 'e.g', 'i.e', 'eg', 'ie', 'fig', 'etc',
                            'pt', 'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept', 'oct', 'nov', 'dec',
                            'a.m', 'p.m'})
_BIG = 1 << 62
# Clause boundaries inside a sentence; ", and the patient ..." starts a new subject.
_CLAUSE_WORD = re.compile(r'(?<=[\s,])(?:but|however|whereas|although|though|except)\b'
                          r'|(?<=,\s)and\s+(?=(?:the|she|he|they|we|i|it|this|there|patient)\b)', re.A | re.I)


@dataclass(frozen=True)
class Section:
    kind: str  # one of SECTION_KINDS
    label: str  # normalised heading label; '' for text before the first heading
    heading: Optional[Span]  # the heading text as written (label and colon)
    start: int  # heading line start (or 0)
    end: int  # next heading line start (or len(text))


def normalize_label(raw: str) -> str:
    label = raw.strip().strip('*').strip().lower().replace('&', ' and ')
    label = re.sub(r'\(s\)', 's', label)
    label = re.sub(r'\s+', ' ', label)
    return label.strip(' .:-')


def _service_named(line: str) -> bool:
    return bool(cues.FS_ABBREVIATION.search(line)) or any(p.search(line) for _, p in cues.SERVICE_PATTERNS)


# gi3 extent (R6): a heading whose parts, split on "and", "/" or ",", are all procedure, findings or technique headings
# is a heading of its first part's kind ("Procedure and findings", "Procedure/Findings", "Technique and findings"): h2-04's
# "Procedure and findings" was no heading, so its "Indications" section ran over the whole report. Any other part ("Plan")
# leaves the label to the rules below.
_COMPOSITE_SPLIT = re.compile(r'[ \t]+and[ \t]+|[ \t]*[/,][ \t]*', re.A)


def _composite_kind(label: str) -> Optional[str]:
    parts = [part for part in _COMPOSITE_SPLIT.split(label) if part]
    if len(parts) > 1 and all(HEADINGS.get(part) in POSITIVE_KINDS for part in parts):
        return HEADINGS[parts[0]]
    return None


def _heading(text: str, ls: int, le: int) -> Optional[tuple[str, str, Span]]:
    """(kind, label, heading span) when the line [ls, le) is a heading line."""
    body_start = _PREFIX.match(text, ls, le).end()
    line = text[body_start:le]
    block = FORM_BLOCK.fullmatch(line.strip())
    if block or ADDENDUM_HEADER.fullmatch(line.strip()):
        lead = len(line) - len(line.lstrip())
        return 'other', f"pdf {block.group('what')}" if block else 'addendum', Span(
            body_start + lead, body_start + lead + len(line.strip()), line.strip())
    colon = line.find(':')
    raw = line if colon < 0 else line[:colon]
    if not raw.strip() or len(raw) > 60:
        return None
    label = normalize_label(raw)
    kind = HEADINGS.get(label)
    if kind is None:
        kind = _composite_kind(label)
    content = '' if colon < 0 else line[colon + 1:]
    if label in _SEC_NO_ANSWER_LABELS and content.strip() and _SEC_NO_ANSWER.fullmatch(content):
        return None  # "Orders: none", "Procedures performed today: N/A": a field, as at R3B-BASE (structure:5, :9)
    if kind is None and colon < 0 and cues.PROCEDURE_TITLE.match(line.strip()) and _service_named(line) \
            and not _TITLE_QUALIFIER.search(line):
        kind = 'procedure'
    if kind is None and colon >= 0 and not content.strip() and _bare_label(raw):
        kind = 'plan' if _PLAN_LABEL.search(raw) else 'history' if _HISTORY_LABEL.search(raw) else 'other'
    if kind is None and colon < 0 and _bare_label(raw):
        kind = _colonless_label(raw, listed=bool(_LIST_ITEM.match(text, ls, le)))
    if kind is None or (kind == 'time' and _CLOCK.match(content)):
        return None
    lead = len(raw) - len(raw.lstrip())
    h_start = body_start + lead
    h_end = body_start + (colon + 1 if colon >= 0 else len(raw.rstrip()))
    return kind, label, Span(h_start, h_end, text[h_start:h_end])


def _lines(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    while True:
        nl = text.find('\n', start)
        if nl < 0:
            spans.append((start, len(text)))
            return spans
        spans.append((start, nl))
        start = nl + 1


# Function words a sentence cannot end on (a closed class: articles and determiners, prepositions,
# conjunctions, auxiliaries, negations): a prose line cut after one goes on in the next line whatever its
# case, so a layout break never splits "no" or "declined the" from the service named on the next line
# ("... because of time constraints, no\nEUS of the pancreatic cyst was performed today").
_WRAP_WORDS = frozenset((
    'no', 'not', 'nor', 'neither', 'never', 'without', 'w/o', 'the', 'a', 'an', 'any', 'of', 'to', 'and', 'or', 'with',
    'for', 'by', 'from', 'in', 'on', 'at', 'into', 'than', 'that', 'which', 'her', 'his', 'their', 'its', 'this',
    'further', 'additional', 'repeat', 'was', 'were', 'is', 'are', 'be', 'been', 'had', 'has', 'have', 'after', 'before',
    'during', 'under', 'via', 'per', 'but'))
# The rest of that closed class, read only as written in lower case: in capitals they are as often a month, a
# name or an abbreviation ("May", "AS", "IF", "VS", "WHO") as a word cut from the next line.
_WRAP_WORDS_LOWER = frozenset((
    'these', 'those', 'our', 'my', 'your', 'each', 'every', 'another', 'whose', 'who', 'whom', 'about', 'against',
    'among', 'as', 'between', 'despite', 'except', 'including', 'excluding', 'regarding', 'toward', 'towards', 'unlike',
    'upon', 'onto', 'versus', 'vs', 'w/', 'if', 'unless', 'because', 'although', 'whether', 'whereas', 'being', 'do',
    'does', 'did', 'will', 'would', 'shall', 'should', 'can', 'could', 'may', 'might', 'must', 'cannot'))
_LAST_TOKEN = re.compile(r'(?:^|[\s(])([A-Za-z][A-Za-z/]*)$', re.A)
# A next line that starts a list item, a field ("Date of service: ...") or a table row never continues one.
_LIST_OR_FIELD = re.compile(r'[ \t]*(?:[-*]\s|\d{1,2}[.)]\s|[A-Za-z][.)]\s|[^:\n|]{1,40}:[ \t]*\S)', re.A)
# Nor does a line that answers a field or marks an option, whatever word it ends on: its "no" is the answer, not
# a word cut from the next line ("Schatzki ring present: no", "Hiatal hernia - no", "Hiatal hernia? no",
# "Sedation: patient declined", "Biopsy taken [ ] Yes [x] No", "Biopsy taken   Yes   No").
WRAP_TAIL = 200  # only the end of a line is read for its shape (bounds the work per line)
# The LAST field on the line is read: its label may also start after a comma, a tab or a run of spaces, so two fields
# on one line, or a field after a comma, end the line too ("Hiatal hernia: no, Schatzki ring: no", "Mucosa: normal,
# hiatal hernia: no", "Hiatal hernia: no   Schatzki ring: no"; round 4 structure:1, restoring 57b4b3747).
# Its opening run of blank space is read once (possessive), so a label starts where the run ends: tried in every way of
# sharing it between the opening run, a label that may hold spaces and the space before the separator, a line whose
# last 200 characters held a long run took about a second ("Withdrawal time" + 170 spaces + "9 minutes.") and 120
# such lines took the assess stage past its limit (refutation 7c8, sk:13). What that sharing could also read - a
# separator after a run of blank space with no label of its own ("Biopsies taken.    - no") - is _FIELD_BARE_ANSWER,
# whose runs are read once too; _field_parts takes the leftmost of the two, as the one pattern did.
_FIELD_ANSWER = re.compile(r'(?:^|[.;,][ \t]++|\t[ \t]*+|[ ]{2,}+)(?P<label>[^:.;?=|\n]{1,60}?)[ \t]*'
                           r'(?P<sep>:|\?|=|[ \t][-\u2013\u2014][ \t])[ \t]*'
                           r'(?P<value>[^\s:?=|]+(?:[ \t]+[^\s:?=|]+){0,2})[ \t]*$', re.A)
_FIELD_BARE_ANSWER = re.compile(r'(?:(?:[.;,][ \t]{2,}+|\t[ \t]++|[ ]{2}[ \t]++)(?P<sep>[:?=])'
                                r'|(?:[.;,][ \t]{3,}+|\t[ \t]{2,}+|[ ]{2}[ \t]{2,}+)[-\u2013\u2014][ \t])[ \t]*'
                                r'(?P<value>[^\s:?=|]+(?:[ \t]+[^\s:?=|]+){0,2})[ \t]*$', re.A)


def _field_parts(tail: str):
    """(label, separator, value) of the last field ``tail`` ends with, or None: _FIELD_ANSWER's reading, or - where it
    starts further left - a separator after blank space with no label (label '', separator ':', '?', '=' or ' - ')."""
    field, bare = _FIELD_ANSWER.search(tail), _FIELD_BARE_ANSWER.search(tail)
    if bare is not None and (field is None or bare.start() < field.start()):
        return '', bare.group('sep') or ' - ', bare.group('value')
    return None if field is None else (field.group('label'), field.group('sep'), field.group('value'))
# Before a dash a field's label names a thing; a clause ("Colonoscopy was performed - no EGD was done") is prose.
_LABEL_CLAUSE = re.compile(r'\b(?:was|were|is|are|has|have|had|did|does|do|will|would|shall|should|can|could|may|'
                           r'might|must)\b', re.A | re.I)
_ALONE_ANSWERS = frozenset(('no', 'not', 'never', 'none'))  # a whole answer when it is the whole value
# A column answer: a whole line that is a short label, then a tab or three or more spaces, then a lone negation
# ("Hiatal hernia      no", "Hiatal hernia\tno"; round 4 structure:1). No comma or clause in the label.
_SEC_COLUMN_ANSWER = re.compile(r'[ \t]*(?P<label>[A-Za-z][^:.;,?=|\n\t]{0,58}?[^\s:.;,?=|])(?:[ \t]*\t[ \t]*|[ ]{3,})'
                                r'(?:no|none|never|not)[ \t]*', re.A | re.I)
_DENIALS = frozenset(('declined', 'declines', 'refused', 'refuses', 'denied', 'denies'))
# A spoken answer ends its sentence when the next line opens a clause of its own: "the patient said no\nColonoscopy
# was then performed", "she was asked about a biopsy and answered no\nA 6 mm polyp was removed" (a closed list of
# verbs of saying or choosing; round 4 structure:3, restoring 57b4b3747). Cut prose still runs on ("because of time
# constraints, no\nEUS of the pancreatic cyst was performed today").
_SEC_SPOKEN_VERB = r'\b(?:said|says|answered|answers|replied|replies|responded|responds|chose|chooses)'
_SEC_SPOKEN_ANSWER = re.compile(_SEC_SPOKEN_VERB + r'[ \t]+(?:no|neither|never|not)$', re.A | re.I)
# The same answer with a comma or a colon after the verb ("the patient said, no"; round 4c sections:8): the join stays
# (every base negated it), and routing holds the negation it carries across the line break (detect, the line above).
_SEC_SPOKEN_ANSWER_PUNCT = re.compile(_SEC_SPOKEN_VERB + r'[ \t]*[,:]?[ \t]+(?:no|neither|never|not)$', re.A | re.I)
# The option-row guard reads every box spelling of the shared vocabulary (studio.ingest.symbols), its unread marks,
# bare radio glyphs and an empty pair of parentheses: a line that ends on 'No' after any of them marks an option.
from studio.ingest import symbols as _BOX_SYMBOLS  # noqa: E402 (Django-free; read for _OPTION_ROW only)
_BOX_OPTION_MARK = '|'.join((_BOX_SYMBOLS.BOX_OFF_PATTERN, _BOX_SYMBOLS.BOX_ON_PATTERN, _BOX_SYMBOLS.BOX_UNREAD_PATTERN,
                             _BOX_SYMBOLS.BOX_RADIO_PATTERN, r'\(' + _BOX_SYMBOLS.BOX_PAD + r'*\)'))
_OPTION_ROW = re.compile(r'(?:' + _BOX_OPTION_MARK + r'|\byes\b)(?:[/|,-]|' + _BOX_SYMBOLS.BOX_PAD + r')*\bno(?:'
                         + _BOX_SYMBOLS.BOX_PAD + r')*$', re.A | re.I)
# A content word ends a line that goes on only where its verb still lacks what it takes, and the next line does
# not open a clause of its own: an auxiliary or a subject before the last word ("we did not perform\nEUS of the
# pancreatic cyst", "will schedule\nEUS", "she underwent\nEGD", "we recommend\nEUS") or a denial ("the patient
# declined\nEUS."); never "the patient refused\nColonoscopy was then performed".
_OPEN_VERB = re.compile(r"(?:\b(?:do|does|did|will|would|shall|should|can|could|may|might|must|cannot|has|have|had|we|"
                        r"you|they|he|she|(?:the|our|this)[ \t]+(?:patient|pt))|(?:^|[.;,][ \t]+|\b(?:and|but|then|so)"
                        r"[ \t]+)I|n't|\bnot[ \t]+to)(?:[ \t]+(?:not|never|also|then|still|again|ever|yet|already|"
                        r"[A-Za-z]+ly))*[ \t]+(?-i:[a-z][a-z'-]*)$"
                        # after a bare "to" only a verb that takes a procedure ("unable to perform\nEUS"), never a
                        # place ("referred to surgery\nColonoscopy ...")
                        r"|\bto[ \t]+(?-i:perform|undergo|schedule|reschedule|defer|forgo|forego|postpone|cancel|repeat|"
                        r"have|pursue|obtain|complete|do|attempt|consider|arrange|book|order|request|recommend|plan|"
                        r"offer|discuss|delay|hold|need|require|receive|get|avoid|skip|omit|decline|refuse)$",
                        re.A | re.I)
# Where a line's own clause ends, and the words that make it one ("Colonoscopy was then performed", "EGD
# performed"); a participle after a determiner or a preposition describes ("EUS of the dilated duct").
OWN_CLAUSE_REACH, OWN_CLAUSE_WORDS = 200, 10  # how much of the next line is read (bounds the work per line)
_CLAUSE_STOP = re.compile(r'[,;:.()!?]|\b(?:which|that|who|whom|whose|where|when|while|because|since|as|if|unless|'
                          r'although|though|whereas|until|once|but|so)\b'
                          r'|\b(?:and|or)[ \t]+(?=(?:the|she|he|they|we|i|it|this|there|patient)\b)', re.A | re.I)
_CLAUSE_WORD_TOKEN = re.compile(r"[A-Za-z][A-Za-z'/-]*", re.A)
_FINITE = frozenset(('was', 'were', 'is', 'are', 'am', 'has', 'have', 'had', 'will', 'would', 'shall', 'should', 'can',
                     'could', 'may', 'might', 'must', 'did', 'does', 'do', 'cannot', 'shows', 'reveals',
                     'demonstrates', 'appears', 'remains', 'measures', 'notes', 'confirms', 'suggests', 'contains',
                     'requires'))
_IRREGULAR_PARTICIPLES = frozenset(('done', 'taken', 'seen', 'given', 'shown', 'made', 'sent', 'held', 'kept', 'left',
                                    'found', 'begun', 'undergone', 'drawn', 'brought', 'gone'))
_DESCRIBING_BEFORE = frozenset(('the', 'a', 'an', 'this', 'that', 'these', 'those', 'its', 'her', 'his', 'their',
                                'our', 'any', 'no', 'each', 'every', 'of', 'for', 'with', 'in', 'on', 'at', 'to', 'by',
                                'from', 'into', 'under', 'over', 'after', 'before', 'during', 'without', 'via', 'per'))


def _answered(tail: str) -> bool:
    """Whether a line ends answering a field: "<label>: no", "<label> - no", "<label>? never", "<label>: patient
    declined" (a lone negation, or a short value ending in a denial), its last field read when it has two; or the
    whole line, when ``tail`` is all of it, is a column answer ("Hiatal hernia\tno")."""
    column = _SEC_COLUMN_ANSWER.fullmatch(tail)
    if column and not _LABEL_CLAUSE.search(column.group('label')):
        return True
    field = _field_parts(tail)
    if not field or (field[1] not in ':?=' and _LABEL_CLAUSE.search(field[0])):
        return False
    words = field[2].lower().split()
    return (len(words) == 1 and words[0] in _ALONE_ANSWERS) or words[-1] in _DENIALS


def _own_clause(line: str) -> bool:
    """Whether ``line`` opens a clause of its own: a finite verb or a participle predicate after its first word,
    before its first comma, stop or clause word."""
    stop = _CLAUSE_STOP.search(line, 0, OWN_CLAUSE_REACH)
    words = _CLAUSE_WORD_TOKEN.findall(line, 0, stop.start() if stop else OWN_CLAUSE_REACH)[:OWN_CLAUSE_WORDS]
    previous = ''
    for index, word in enumerate(words):
        lowered = word.lower()
        if index and (lowered in _FINITE or lowered in _IRREGULAR_PARTICIPLES
                      or (lowered.endswith('ed') and len(lowered) > 3 and '-' not in lowered
                          and previous not in _DESCRIBING_BEFORE)):
            return True
        if not lowered.endswith('ly'):
            previous = lowered
    return False


def _soft_wrap(text: str, prev: tuple[int, int], nxt: tuple[int, int]) -> bool:
    """A line break inside a sentence: the line (from ``prev[0]``, after any heading label) has no
    closing punctuation, and the next line continues in lower case; or the next line is no list item,
    field or table row, the line is prose that answers no field and marks no option, and it is cut on a
    word a sentence cannot end on (_WRAP_WORDS) or on a verb that still lacks what it takes while the next
    line opens no clause of its own (_OPEN_VERB, _DENIALS)."""
    before = text[prev[0]:prev[1]].rstrip()
    after = text[nxt[0]:nxt[1]].lstrip()
    if not before or before[-1] in '.!?:;' or not after:
        return False
    if after[0].islower():
        return True
    if ' | ' in before or ' | ' in after or _LIST_OR_FIELD.match(after) or len(before.split()) < 3:
        return False
    tail = before[-WRAP_TAIL:]
    if _answered(before if len(before) <= WRAP_TAIL else tail) or _OPTION_ROW.search(tail):
        return False
    last = _LAST_TOKEN.search(tail)
    if last is None:
        return False
    word = last.group(1).lower()
    if word in _WRAP_WORDS or last.group(1) in _WRAP_WORDS_LOWER:
        return not (_SEC_SPOKEN_ANSWER.search(tail) and _own_clause(after))
    return (word in _DENIALS or bool(_OPEN_VERB.search(tail))) and not _own_clause(after)


# A line cut after a verb the closed lists above do not know (round 4 structure:11, an open class): it ends without
# closing punctuation on a word the declared plan or cancellation cues read (cues.PLANNED_CLAUSE, cues.CANCELLED_CLAUSE:
# "Dr. Smith recommended", "the endoscopist deferred", "Dr. Smith ordered"), or on a denial and a bare "to <verb>" ("The
# family declined to authorize"); its last clause names no service or intervention before that word ("Repeat colonoscopy
# recommended" speaks of its own); and the next line names one but opens no clause of its own ("EUS with fine-needle
# aspiration of the pancreatic head mass."). That next line is HELD, never read as performed: it opens an 'other'
# section of its own, with no default, and the section in force resumes after it (see layout). It is never joined, so
# no plan or cancellation is read into it either: a layout rule may only hold.
_SEC_HELD_LABEL = 'line after an unfinished clause'
_SEC_CLAUSE_EDGE = re.compile(r'[;,]', re.A)
# Round 4c sections:9: the next line is read without its list marker ("- EUS with FNA ...", "1. EUS ...", "A. EUS ...");
# only a table row stays exempt. A field is held like any service line ("- EUS: FNA of the pancreatic head mass"; a field
# that names no service, "Date of service: ...", is never held). (A lower-case letter marker, "a) EUS ...", joins the cut
# line instead, so the cut verb's own cue reads the service.)
_SEC_LIST_MARK = re.compile(r'[ \t]*(?:[-*\u2022]|\(?\d{1,2}[.)]|\(?[A-Za-z][.)])[ \t]+', re.A)
_SEC_DENIAL_TO_END = re.compile(r'\b(?:declined|declines|refused|refuses|denied|denies)[ \t]+to[ \t]+[a-z][a-z-]*$', re.A)
_SEC_LAST_WORD = re.compile(r'(?<![A-Za-z-])([A-Za-z][A-Za-z-]*)$', re.A)


def _sec_act_named(line: str) -> bool:
    return _service_named(line) or any(p.search(line) for _, p, _ in cues.INTERVENTIONS)


def _sec_held_after(text: str, prev: tuple[int, int], nxt: tuple[int, int]) -> bool:
    """Whether the line ``nxt`` is held because the line before it (from ``prev[0]``, after any heading label) is cut
    after a plan, cancellation or denial verb that its own clause leaves without an object (see above). Read only when
    _soft_wrap does not join the two lines; only the ends of the lines are read (bounds the work per line)."""
    before = text[prev[0]:prev[1]].rstrip()
    if not before or before[-1] in '.!?:;,':
        return False
    tail = before[-WRAP_TAIL:]
    cue = _SEC_DENIAL_TO_END.search(tail)
    if cue is None:
        cue = _SEC_LAST_WORD.search(tail)
        if cue is None or not any(pattern.fullmatch(cue.group(1)) for _, pattern in cues.PLANNED_CLAUSE + cues.CANCELLED_CLAUSE):
            return False
    after = text[nxt[0]:nxt[1]].strip()
    mark = _SEC_LIST_MARK.match(after)
    after = after[mark.end():] if mark else after
    if not after or (after[0].islower() and not mark) or ' | ' in tail or ' | ' in after[:OWN_CLAUSE_REACH] \
            or _own_clause(after) or not _sec_act_named(after[:OWN_CLAUSE_REACH]) or _answered(tail) \
            or _OPTION_ROW.search(tail):
        return False
    offset = len(before) - len(tail)
    stops = [b - prev[0] - offset for b in _sentence_breaks(text, prev[0] + offset, prev[1])]
    clause = max([0] + [x for x in stops if x <= cue.start()] + [m.end() for m in _SEC_CLAUSE_EDGE.finditer(tail, 0, cue.start())])
    return not _sec_act_named(tail[clause:cue.start()])


_STOP = re.compile(r'[.!?](?=\s)')
_WORD_BEFORE = re.compile(r'([A-Za-z][A-Za-z.]{0,10})$')
_NEXT_CHAR = re.compile(r'\s*(\S)')


def _sentence_breaks(text: str, start: int, end: int) -> list[int]:
    """Positions inside one line where a sentence ends."""
    breaks = []
    for m in _STOP.finditer(text, start, end):
        q = m.start()
        if text[q] == '.':
            word = _WORD_BEFORE.search(text, max(start, q - 12), q)
            follow = _NEXT_CHAR.match(text, q + 1, end)
            if word and (word.group(1).lower() in _ABBREVIATIONS or len(word.group(1)) == 1):
                continue
            if follow and follow.group(1).islower():
                continue
        breaks.append(q + 1)
    return breaks


def _trimmed(text: str, start: int, end: int) -> Optional[tuple[int, int]]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


@dataclass(frozen=True)
class Layout:
    """Sections, sentences and clauses of one text, indexed once."""
    text: str
    sections: tuple[Section, ...]
    sentences: tuple[tuple[int, int], ...]
    clauses: tuple[tuple[int, int], ...]
    section_starts: tuple[int, ...]
    # gi3 extent: the text's tables (the one table model, tables()); each table data cell as (start, end, its column's
    # label), in text order; and the starts of the service parts a reporting service line opened (_reporting_heads)
    tables: tuple['Table', ...] = ()
    columns: tuple[tuple[int, int, str], ...] = ()
    reporting_parts: frozenset = frozenset()
    # gi3 fix round 1 (EXT-5): the answer cells that answer their own column, each a clause of its own, in text order
    answer_cells: tuple[tuple[int, int], ...] = ()

    def section_at(self, pos: int) -> Section:
        index = bisect.bisect_right(self.section_starts, pos) - 1
        return self.sections[max(index, 0)]

    def column_at(self, pos: int) -> Optional[tuple[int, int, str]]:
        """(start, end, column label) of the table data cell that holds ``pos``, else None."""
        index = bisect.bisect_right(self.columns, (pos, _BIG, '')) - 1
        if index >= 0 and self.columns[index][0] <= pos < self.columns[index][1]:
            return self.columns[index]
        return None

    def in_table_header(self, pos: int) -> bool:
        """Whether ``pos`` lies on a table's header line: its cells are column labels, never statements."""
        index = bisect.bisect_right(self.tables, pos, key=lambda table: table.header[0]) - 1
        return index >= 0 and self.tables[index].header[0] <= pos < self.tables[index].header[1]

    def answers_its_column(self, start: int, end: int) -> bool:
        """Whether [start, end) lies inside a table data cell that only answers its own column (gi3 fix round 1, EXT-5:
        such a clause says nothing of the row's service, so a passage that spans the row never takes its answer)."""
        index = bisect.bisect_right(self.answer_cells, (start, _BIG)) - 1
        return index >= 0 and self.answer_cells[index][0] <= start and end <= self.answer_cells[index][1]

    def sentence_for(self, start: int, end: int) -> tuple[int, int]:
        return _first_overlap(self.sentences, start, end)

    def window(self, clause: tuple[int, int], start: int, end: int, reach: int) -> tuple[int, int]:
        """The part of a clause within ``reach`` characters of [start, end), cut at
        whitespace so no word is split (a regex reads a cut as the end of the text)."""
        cs, ce = clause
        inner_lo, inner_hi = max(cs, start), min(ce, end)
        lo, hi = max(cs, start - reach), min(ce, end + reach)
        if lo > cs:
            space = re.search(r'\s', self.text[lo:inner_lo])
            lo = lo + space.end() if space else inner_lo
        if hi < ce:
            spaces = [m.start() for m in re.finditer(r'\s', self.text[inner_hi:hi])]
            hi = inner_hi + spaces[-1] if spaces else inner_hi
        return lo, hi

    def clauses_for(self, start: int, end: int) -> list[tuple[int, int]]:
        """Every clause that overlaps [start, end); the span itself when it overlaps none."""
        found = [c for c in _window(self.clauses, start, end) if c[0] < max(end, start + 1) and c[1] > start]
        return found or [_first_overlap(self.clauses, start, end)]


def _window(spans: tuple[tuple[int, int], ...], start: int, end: int) -> tuple[tuple[int, int], ...]:
    low = max(bisect.bisect_right(spans, (start, _BIG)) - 1, 0)
    high = bisect.bisect_left(spans, (end + 1, -1))
    return spans[low:high + 1]


def _first_overlap(spans: tuple[tuple[int, int], ...], start: int, end: int) -> tuple[int, int]:
    for span in _window(spans, start, end):
        if span[0] < max(end, start + 1) and span[1] > start:
            return span
    return (start, end)


def split_sections(text: str) -> tuple[Section, ...]:
    return layout(text).sections


# Session 7c8d38da, GI round 2, extent (held-out ho-01): a service's name standing alone on its line ("Upper
# Endoscopy", "COLONOSCOPY", "Esophagogastroduodenoscopy (EGD)", "**Colonoscopy**"; no list marker, no colon, neither
# run on into nor running on into the next line) is no heading, so an "Indications" section ran over the narratives
# under "Upper Endoscopy" and "Colonoscopy", every statement there was held as an indication's, and no extent was read.
# Such a line now ends the indication in force, and opens exactly the 'other' section, with no default, that its colon
# form ("Colonoscopy:") opens there, when all of these hold (see layout):
# - the report names that service as its own above it, in a procedure section that is no plan, history or cancellation
#   ("Procedures: Esophagogastroduodenoscopy with biopsies; colonoscopy with cold snare polypectomy", "Colonoscopy
#   Report"; _declared_services), never with an earlier occasion of its own ("Procedures: Colonoscopy 2019", "prior
#   colonoscopy"; _names_another_occasion): a note that never does (an office visit's "Reason for visit" over a pasted
#   earlier report) may tell another time under it;
# - the indication has said something of its own first (_indication_said): one organised by service sub-headings
#   ("Indications" / "Colonoscopy" / "Screening, average risk.") keeps what they head;
# - the part it heads reports what was done, says no intent, marks no clause as today's, and nothing in the report says
#   another account of the examination may be the day's (_reporting_heads, narrowed in the fix round: a second part of
#   the same service, an examination's course or a today's heading after it, a label-like line between two accounts
#   inside it, a landmark both reached and not reached): a part that says why is the indication's, and one that marks
#   its today's statements mixes times, which the indication's per-clause reading keeps apart;
# - no procedure, findings or technique heading follows it: such a report's own narrative has its section further on.
# Each such line ends the part the one before it opened; one that does not open a part of its own hands its part back
# to the indication. Anywhere else it is content, as before (inside a plan or a history it names an item of that
# section).
_SVC_HEAD_ASIDE = re.compile(r'[ \t]*\(([^()\n]{1,20})\)[ \t]*$', re.A)
_NOT_TODAYS = tuple(pattern for _, pattern in cues.PLANNED_CLAUSE + cues.HISTORICAL_CLAUSE + cues.CANCELLED_CLAUSE)


def _service_name_only(body: str) -> Optional[str]:
    """The family when ``body`` (a line without its markup) is that one family's name and nothing else, optionally with
    a parenthesised abbreviation of the same family ("Esophagogastroduodenoscopy (EGD)"); else None. Never a status or
    other aside ("Colonoscopy (not performed)", "ERCP (UNSUCCESSFUL)"), a longer line ("Colonoscopy with biopsy"), a
    label ("Colonoscopy:", a heading already) or two services ("EGD and colonoscopy")."""
    name = body.strip()
    if not name or ':' in name or len(name) > 70:
        return None
    aside = _SVC_HEAD_ASIDE.search(name)
    bare = name[:aside.start()].rstrip() if aside else name
    families = [family for family, pattern in cues.SERVICE_PATTERNS if pattern.fullmatch(bare)]
    if len(families) != 1 or (aside and not dict(cues.SERVICE_PATTERNS)[families[0]].fullmatch(aside.group(1).strip())):
        return None
    return families[0]


def _service_head(text: str, ls: int, le: int) -> Optional[tuple[str, str, Span]]:
    """(family, normalised label, the name's span) when the line [ls, le) is a service's name and nothing else (see
    _service_name_only) under markdown emphasis or heading marks at most, with no list marker ("1. Colonoscopy",
    "- EGD")."""
    line = text[ls:le]
    if len(line) > 80 or _LIST_ITEM.match(line) or _SEC_LIST_MARK.match(line):
        return None
    body = line.strip(' \t*#')
    family = _service_name_only(body)
    if family is None:
        return None
    start = ls + line.index(body)
    return family, normalize_label(body), Span(start, start + len(body), body)


def _indication_said(text: str, lines: list[tuple[int, int]], line_starts: list[int], section: tuple, i: int,
                     firsts: dict) -> bool:
    """Whether the indication in force (``section``: kind, label, heading span) says something of its own before line
    ``i`` that is no service's name: an answer after its heading label ("Indication: Iron deficiency anemia."), or a first
    content line that is not itself a service line. ``firsts`` keeps each indication's first content line (found once)."""
    span = section[2]
    if span is None:
        return False
    head = bisect.bisect_right(line_starts, span.start) - 1
    if head < 0 or head >= i:
        return False
    if text[span.end:lines[head][1]].strip():
        return True
    if head not in firsts:
        firsts[head] = next((j for j in range(head + 1, len(lines)) if text[lines[j][0]:lines[j][1]].strip()), None)
    first = firsts[head]
    return first is not None and first < i and _service_head(text, *lines[first]) is None


def _runs(lines: list[tuple[int, int]], joins: list[bool]) -> tuple[list[int], list[int]]:
    """For each line, where the run of lines it belongs to starts and ends: a line and the lines its sentence runs on
    into or from (``joins``, a soft wrap: a PDF's 90-character lines), so that a reader of one line reads the run the
    other forms write on one line. Two passes over the lines."""
    starts, ends = [0] * len(lines), [0] * len(lines)
    for k, (ls, _) in enumerate(lines):
        starts[k] = starts[k - 1] if k > 0 and joins[k - 1] else ls
    for k in range(len(lines) - 1, -1, -1):
        ends[k] = ends[k + 1] if k + 1 < len(lines) and joins[k] else lines[k][1]
    return starts, ends


def _declared_services(text: str, lines: list[tuple[int, int]], headings: dict, candidates: dict,
                       runs: tuple[list[int], list[int]]) -> dict[int, frozenset]:
    """For each service line of ``candidates`` (line index -> _service_head), the services the report names as its own
    above it: on a line of a procedure section (a procedure heading line, "Procedures: EGD with biopsies; colonoscopy
    ...", "Colonoscopy Report", and the lines under it up to the next heading, a list of the procedures performed
    included) whose run of lines (``runs``, _runs) carries no planned, historical or cancelled cue (cues' own
    vocabularies: "Procedures: EGD planned"), each name read in its own item (to the next semicolon or the run's end)
    with no earlier occasion of its own (_names_another_occasion). One pass over the lines up to the last service line,
    linear in the text (GI round 2, second fix round, cost: the differential round's DM-1 and edges-1 measured the whole
    run reread for each of its lines and names): a run's cues are read once, for its first line that names a service,
    and kept for its other lines; a line that names none declares nothing, whatever its run says."""
    declared, found, in_procedure = {}, set(), False
    cued, memo = {}, {}  # a run's start -> whether the run carries a cue; what _names_another_occasion reads once
    for i in range(max(candidates) + 1):
        if i in candidates:
            declared[i] = frozenset(found)
        if headings[i]:
            in_procedure = headings[i][0] == 'procedure'
        if in_procedure:
            ls, le = lines[i]
            names = [(family, m) for family, pattern in cues.SERVICE_PATTERNS for m in pattern.finditer(text, ls, le)]
            if not names:
                continue
            rs, re_ = runs[0][i], runs[1][i]
            if rs not in cued:  # the lines of one run share its start, its end and so its answer
                cued[rs] = any(pattern.search(text, rs, re_) for pattern in _NOT_TODAYS)
            if cued[rs]:
                continue
            found |= {family for family, m in names
                      if not _names_another_occasion(text, rs, re_, m.start(), m.end(), memo)}
    return declared


# GI round 2 fix round (extent; the refutation lens's observation A3): a procedure line that names the service with an
# earlier occasion of its own ("Procedures: Colonoscopy 2019 (tubular adenoma).", "Procedures: prior colonoscopy with
# polypectomy.", "Procedure: Colonoscopy on 03/14/2024 by Dr. Synthetic.", "Procedures: Upper endoscopy with biopsies;
# colonoscopy (2024).") declares no service of the day's: an office note over a pasted report read the report's
# narrative as performed at the visit. A historical word right before the name (cues.HISTORICAL_PRE, the vocabulary that
# reads a service name as another time's), or a year or a numeric date in the name's own item, says so. A date the item
# shares with the day's own date is no exception: such a name is held, as before the stand-alone heading was read.
_ITEM_DATE = re.compile(r'\b(?:19|20)\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b', re.A)
# The second fix round (cost): a cues._pre match before a name ends where the name starts and spans at most a trigger of
# six words and five fillers, words as cues._pre separates them ([\s,]); routing's bounded pre-trigger reading keeps
# twice that (detect.PRE_WORDS, the same value). So the historical words are searched from that many of the run's words
# back, which finds exactly what a search from the run's start finds, and the semicolons that end a name's item are
# found by bisection: a run's words and semicolons are read once for every name in it, an item's date once for every
# name in the item.
_PRE_WORDS = 24
_PRE_WORD = re.compile(r'[^\s,]+', re.A)
_ITEM_EDGE = re.compile(';')


def _names_another_occasion(text: str, ls: int, le: int, start: int, end: int, memo: dict) -> bool:
    """Whether the service name at [start, end) on the procedure line's run [ls, le) names an earlier occasion (see
    above). ``memo`` (_declared_services) keeps each run's word starts and semicolons, by the run's start, and each
    item's date answer, by the item."""
    if ls not in memo:
        memo[ls] = ([m.start() for m in _PRE_WORD.finditer(text, ls, le)],
                    [m.start() for m in _ITEM_EDGE.finditer(text, ls, le)])
    words, semicolons = memo[ls]
    back = bisect.bisect_left(words, start) - _PRE_WORDS
    if any(pattern.search(text, words[back] if back >= 0 else ls, start) for _, pattern in cues.HISTORICAL_PRE):
        return True
    # the item: from the run's last semicolon before the name (text.rfind(';', ls, start)) to its first one after the
    # name (text.find(';', end, le)), or the run's ends
    before, after = bisect.bisect_left(semicolons, start), bisect.bisect_left(semicolons, end)
    item = (semicolons[before - 1] + 1 if before else ls, semicolons[after] if after < len(semicolons) else le)
    if item not in memo:
        memo[item] = bool(_ITEM_DATE.search(text, *item))
    return memo[item]


def _reporting_heads(text: str, lines: list[tuple[int, int]], headings: dict, candidates: dict,
                     joins: list[bool], runs: tuple[list[int], list[int]]) -> set[int]:
    """The service lines among ``candidates`` under which that service's own report begins: the part a line heads (to
    the next heading or service line) states what was done (cues.PERFORMED_CLAUSE, the statements an indication holds),
    states no intent (cues.INTENT) and has no clause that says today (cues.TODAY); and nothing in the report says that
    another account of the examination may be the day's (GI round 2 fix round, extent: the refutation lens's EXT-R1 to
    EXT-R3, each held as at 2b82889f):
    - no other line of the same service heads a part in the same section (two accounts of one service);
    - nothing after the part, from the first heading that follows it, narrates an examination's course (cues.COURSE:
      "Examination" / "The colonoscope was advanced to the hepatic flexure ...", under "Today:", "Impression",
      "Results:" or any other heading), no section there that is no summary of the report (_SUMMARY_KINDS: an
      impression, an assessment or a plan restates the report's outcomes, "Two adenomas were removed.") states an act
      (_ACT: "Results:" / "One adenoma was removed with a hot snare."), and no heading after it says today in its own
      label ("Today:");
    - no label-like line stands alone inside the part between two statements of what was done ("Comparison with the
      prior report", "Colonoscopy on 2026-10-20"; _two_accounts);
    - no landmark the part states as reached is stated as not reached in the part, or after it from the first heading
      that follows (_landmark_reads: "The cecum was not reached." then "advanced to the cecum");
    - an intent anywhere in the part ("... removed with a cold snare. This was a screening examination.") keeps it the
      indication's, where the intent reader reads a clause that names no service.
    A part a later service line of another family follows is read alone: that line heads its own service's part ("Upper
    Endoscopy" / "Colonoscopy"). Each part is read once and every later-text question is one comparison with a position
    found in one pass, so the work is linear in the text."""
    today = [m.start() for m in cues.TODAY.finditer(text)]
    starts = sorted(candidates)
    bounds = sorted(i for i, h in headings.items() if h)
    line_starts = [ls for ls, _ in lines]
    last_course = max((m.start() for m in cues.COURSE.finditer(text)), default=-1)
    last_today_head = max((i for i in bounds if cues.TODAY.search(headings[i][2].text)), default=-1)
    last_act_head = max((h for n, h in enumerate(bounds) if headings[h][0] not in _SUMMARY_KINDS
                         and _ACT.search(text, lines[h][0], lines[bounds[n + 1]][0] if n + 1 < len(bounds) else len(text))),
                        default=-1)
    reads = _landmark_reads(text, line_starts, runs)
    read_at = [pos for pos, _, _ in reads]
    last_denied = {label: pos for pos, label, reached in reads if not reached}  # sorted: the last one stays
    services = {}  # (section between headings, family) -> how many service lines head a part there
    for i in starts:
        key = (bisect.bisect_right(bounds, i), candidates[i][0])
        services[key] = services.get(key, 0) + 1
    reporting = set()
    for n, i in enumerate(starts):
        at = bisect.bisect_right(bounds, i)
        later = bounds[at] if at < len(bounds) else len(lines)
        stop = min(later, starts[n + 1] if n + 1 < len(starts) else len(lines))
        lo, hi = lines[i][1], lines[stop][0] if stop < len(lines) else len(text)
        after = lines[later][0] if later < len(lines) else len(text)  # where the first heading after the part opens
        if not any(pattern.search(text, lo, hi) for _, pattern in cues.PERFORMED_CLAUSE):
            continue  # it heads no account of what was done
        if cues.INTENT.search(text, lo, hi):
            continue  # it says why: the indication's own reading
        t = bisect.bisect_left(today, lo)
        if t < len(today) and today[t] < hi:
            continue  # it marks its today's statements apart from the rest
        if services[(at, candidates[i][0])] > 1 or last_course >= after or last_today_head > i or last_act_head > i:
            continue  # another account: a second part of the service, a later course, today's heading or later act
        if _two_accounts(text, lines, joins, i + 1, stop, lo, hi):
            continue  # a label-like line between two accounts in the part
        part = reads[bisect.bisect_left(read_at, lo):bisect.bisect_left(read_at, hi)]
        reached = {label for _, label, was_reached in part if was_reached}
        if reached & {label for _, label, was_reached in part if not was_reached} \
                or any(last_denied.get(label, -1) >= after for label in reached):
            continue  # a landmark it reaches is also not reached: two occasions
        reporting.add(i)
    return reporting


_PART_ACCOUNT = tuple(pattern for _, pattern in cues.PERFORMED_CLAUSE) + (cues.COURSE,)
# An act with its object ("was removed", "were taken", "was placed"): cues.PERFORMED_CLAUSE's own entry for one, not its
# statements that the procedure happened ("was performed", "underwent", "tolerated the procedure"), which a later
# section of the same report also makes. The section kinds that restate the report's outcomes rather than tell it.
_ACT = dict(cues.PERFORMED_CLAUSE)['was advanced']
_SUMMARY_KINDS = ('impression', 'assessment', 'plan')


def _two_accounts(text: str, lines: list[tuple[int, int]], joins: list[bool], first: int, stop: int, lo: int,
                  hi: int) -> bool:
    """Whether the part [lo, hi) (lines ``first`` to ``stop`` - 1) holds a label-like line standing alone (no colon,
    cell or tab, neither run on into nor running on, _bare_label: "Comparison with the prior report", "Previous report
    (2021)", "Colonoscopy on 2026-10-20") with a statement of what was done (cues.PERFORMED_CLAUSE or cues.COURSE) both
    before and after it: the part may run from one account into another's. A location or measurement line between two
    statements ("Transverse colon", "Withdrawal time 9 minutes") holds the part too: held, as at 2b82889f."""
    marks = sorted(m.start() for pattern in _PART_ACCOUNT for m in pattern.finditer(text, lo, hi))
    if len(marks) < 2:
        return False
    for j in range(first, stop):
        ls, le = lines[j]
        if marks[0] < ls and marks[-1] >= le and not joins[j] and not (j > 0 and joins[j - 1]):
            body = text[ls:le].strip(' \t*#')
            if body and not any(c in body for c in ':|\t') and _bare_label(body):
                return True
    return False


_READ_WINDOW = 120


def _landmark_reads(text: str, line_starts: list[int], runs: tuple[list[int], list[int]]) -> list[tuple[int, str, bool]]:
    """(position, landmark label, reached) for each landmark mention the text states as reached (True) or as not
    reached or not passed (False), read in its run of lines (``runs``, _runs: "The cecum was not" / "reached." on a
    PDF's two lines reads as on one) with detect._landmarks's reach and denial cues in its order (a reach beyond the
    landmark, then a denial, then a reach); a mention that states neither is left out. Sorted by position. Read only to
    hold a part (_reporting_heads), never to read a landmark: detect._landmarks reads them."""
    reads = []
    for table in (cues.UPPER_LANDMARKS, cues.LOWER_LANDMARKS):
        for label, _, pattern in table:
            for m in pattern.finditer(text):
                k = bisect.bisect_right(line_starts, m.start()) - 1
                ls, le = runs[0][k], runs[1][k]
                pre, post = text[max(ls, m.start() - _READ_WINDOW):m.start()], text[m.end():min(le, m.end() + _READ_WINDOW)]
                if cues.REACHED_BEYOND.search(pre):
                    reads.append((m.start(), label, True))
                elif cues.NOT_REACHED_BEFORE.search(pre) or cues.NOT_REACHED_AFTER.search(post) \
                        or cues.REACHED_DEPTH_DENIED.search(pre):
                    reads.append((m.start(), label, False))
                elif cues.REACHED_BEFORE.search(pre) or cues.REACHED_AFTER.search(post) \
                        or cues.REACHED_DEPTH.search(pre):
                    reads.append((m.start(), label, True))
    reads.sort()
    return reads


POSITIVE_KINDS = ('procedure', 'findings', 'technique')
# A form-field value that is a box's or an option's state: the field stays silent whatever its label.
_STATE_VALUE = re.compile(r'(?:not[ \t]+)?checked|unchecked|no[ \t]+option[ \t]+selected|yes|no|none|done|performed|'
                          r'not[ \t]+done|not[ \t]+performed|on|off', re.A | re.I)


def _field_heading(text: str, ls: int, le: int) -> Optional[tuple[str, str, Span]]:
    """The heading a form-field line opens for itself alone: its own label is a procedure, findings or
    technique heading in HEADINGS ("Procedure: Upper endoscopy (EGD)"), so its value reads as the same
    printed line would. Never a box's or an option's state ("Procedure: checked"), never another kind (a
    "Plan:" field is content), and never another field: the block's section resumes on the next line."""
    heading = _heading(text, ls, le)
    if heading is None or heading[0] not in POSITIVE_KINDS or HEADINGS.get(heading[1]) != heading[0]:
        return None
    value = text[heading[2].end:le].strip().rstrip('.').strip()
    return heading if value and not _STATE_VALUE.fullmatch(value) else None


# gi3 extent: the ONE table model (interpretation 45), read by this layout (Layout.columns and the summary label below)
# and by the documented-service inventory. Extraction writes a Word table's row as one line, its cells joined with " | "
# (studio.ingest.docx). A header row is a line of three or more cells, each a bare label: a letter first, at most five
# words, no digit, no sentence punctuation and no answer word ("Examination | Instrument | Furthest point reached |
# Tissue sampled"); its FIRST cell may instead be a numbering column ("#", "No.", "No", "Item" or empty) before the two
# worded labels at least that the other cells then are ("# | Examination | Extent"). One or more rows with as many cells
# follow it, and a line with another count of cells ends the table. A cell holding a digit ("Size 5 mm") or an answer
# ("Yes") makes a line no header row: it is a data row, and with no header over it no table. The cells are split on
# " | " exactly as extraction joins them, so an empty cell is a cell ("Colonoscopy |  | Cecum").
TABLE_CELL_SEPARATOR = ' | '
_TABLE_MIN_CELLS = 3  # a header row's cells at least (two cells are a key and its value: "Extent | Cecum")
# A header cell's own shape (no digit, no sentence punctuation: . , ; : ! ?); its words are counted apart.
_TABLE_LABEL = re.compile(r'[A-Za-z][^0-9.,;:!?]*', re.A)
_TABLE_LABEL_WORDS = 5
# A cell that is only an answer (a closed class: yes, no, none, nil, n/a, not applicable, y, n; and, as a data cell, a
# dash): no header cell is one, and a data cell that holds one answers its own column (layout's answer cells).
# gi3 fix round 1 (cost-1): the blank runs are read once (possessive). With plain runs, a cell that answers and then goes
# on after a long run of blanks ("no" + 100,000 blanks + "x") was tried at every split of the run between the two runs
# around the optional stop, quadratic in the run: at a quarter of the paste cap the context stage took 48 s, so a
# member's date answer (15 s) was refused. Every match is the same span.
_TABLE_ANSWER = r'(?:yes|no|none|nil|n/?a|not[ \t]++applicable|y|n)'
_TABLE_ANSWER_WORD = re.compile(_TABLE_ANSWER, re.A | re.I)
_TABLE_ANSWER_CELL = re.compile(r'[ \t]*+(?:' + _TABLE_ANSWER + r'|[-\u2013\u2014]++)[ \t]*+\.?+[ \t]*+', re.A | re.I)
# The first cell of a numbering column, as written (any case) and as normalize_label gives it.
_TABLE_NUMBERING = frozenset(('#', 'no.', 'no', 'item', ''))
_TABLE_NUMBERING_LABELS = frozenset(normalize_label(cell) for cell in _TABLE_NUMBERING)


@dataclass(frozen=True)
class Table:
    """A header-row table: its header line's span, each header cell's label (normalize_label) in column order, and each
    data row's cell spans (as many as labels, in column order; a cell's span runs between its separators)."""
    header: tuple[int, int]
    labels: tuple[str, ...]
    rows: tuple[tuple[tuple[int, int], ...], ...]


def _cells(text: str, ls: int, le: int) -> list[tuple[int, int]]:
    """The spans of the cells of the line [ls, le), split on TABLE_CELL_SEPARATOR (one cell when it holds none)."""
    out, pos, width = [], ls, len(TABLE_CELL_SEPARATOR)
    found = text.find(TABLE_CELL_SEPARATOR, pos, le)
    while found >= 0:
        out.append((pos, found))
        pos = found + width
        found = text.find(TABLE_CELL_SEPARATOR, pos, le)
    out.append((pos, le))
    return out


def _table_label(cell: str) -> bool:
    """Whether a header cell is a bare label (see above)."""
    body = cell.strip()
    return bool(_TABLE_LABEL.fullmatch(body)) and len(body.split()) <= _TABLE_LABEL_WORDS \
        and not _TABLE_ANSWER_WORD.fullmatch(body)


def _header_labels(text: str, cells: list[tuple[int, int]]) -> Optional[tuple[str, ...]]:
    """The normalised labels of a header row's cells, or None when the cells make no header row (see above). With three
    cells or more, a numbering first cell always has two worded labels after it."""
    if len(cells) < _TABLE_MIN_CELLS or not all(_table_label(text[a:b]) for a, b in cells[1:]):
        return None
    first = text[cells[0][0]:cells[0][1]]
    if not (_table_label(first) or first.strip().lower() in _TABLE_NUMBERING):
        return None
    return tuple(normalize_label(text[a:b]) for a, b in cells)


@functools.lru_cache(maxsize=16)
def tables(text: str) -> tuple[Table, ...]:
    """Every header-row table of ``text``, in document order (see above). One pass over the lines: each line's
    separators are counted once as a row and at most once more as a header (linear in the text)."""
    return _tables(text, _lines(text))


def _tables(text: str, lines: list[tuple[int, int]]) -> tuple[Table, ...]:
    found, i = [], 0
    while i < len(lines):
        ls, le = lines[i]
        shaped = text.count(TABLE_CELL_SEPARATOR, ls, le) >= _TABLE_MIN_CELLS - 1  # a cheap count before the split
        labels = _header_labels(text, _cells(text, ls, le)) if shaped else None
        if labels is not None:
            rows, j = [], i + 1
            while j < len(lines) and text.count(TABLE_CELL_SEPARATOR, *lines[j]) == len(labels) - 1:
                rows.append(tuple(_cells(text, *lines[j])))
                j += 1
            if rows:
                found.append(Table((ls, le), labels, tuple(rows)))
                i = j
                continue
        i += 1
    return tuple(found)


# gi3 extent (R2): a data cell that holds only an answer ("No", "None", "-") answers its own column's header, never the
# row: under a column whose label names neither the row's performance or status, nor a landmark, nor an extent
# (_column_sense: "Tissue sampled", "Complications", "Biopsies"), it is a clause of its own (layout), so it never denies or
# doubts the service or a landmark in another cell (h2-01: the "No" that answers "Tissue sampled" doubted the colonoscopy
# row). Every other cell reads with its row as before: a status answer ("Performed | No"), a date ("Planned date |
# 2026-11-12"), a comment ("Comments | Cancelled before insertion") still speaks for the row's service.
# gi3 fix round 1 (EXT-4, EXT-7): a column speaks for the row only when the row's own service is its subject: its label
# names nothing but the service's performance or status (_ROW_STATUS), the reach of a landmark (_ROW_REACH, a landmark of
# cues' tables: "Cecum reached", "Terminal ileum intubated", "Terminal ileum"), an extent (cues.EXTENT_HEADER), the
# service itself or its examination (cues.SERVICE_PATTERNS, _ROW_SERVICE_NOUN), and function words. A label that names
# anything else names a subject of its own - a finding ("Polyps seen", "Lesions visualized", "Bleeding seen"), an act or
# the place of one ("Antrum biopsy", "Retroflexion in rectum", "Biopsy performed") - and an answer under it answers that
# subject alone: the built rule read a finding's "seen", or a landmark word inside an act's label, as the row's, so the
# "No" that said no polyps were seen, or no antral biopsy was taken, doubted the examination itself (45378 and 43235
# held). The not-done statuses (_ROW_NOT_DONE: "Cancelled", "Aborted", "Not performed", "Incomplete", "Cecum not reached")
# speak for the row with the opposite sense: a negative answer under one ("Cancelled | No") says the service was not
# called off, so it is a clause of its own and never doubts the service; any other answer ("Cancelled | Yes", a dash, an
# empty cell) states, or may state, that it did not happen, which no word of the row's own says, so the row is held
# (layout): its services are asked, never read performed (n1: "Cancelled | No" doubted the EGD done with its biopsies, and
# "Cancelled | Yes" left the cancelled colonoscopy performed). All three are closed classes of the words such a header
# writes; a word outside them makes the column its own subject's, the reading before this round's tables for any other
# cell.
_ROW_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*", re.A)
_ROW_STATUS = re.compile(r'status|state|perform\w*|done|complet\w*|outcome|attempt\w*|undertaken|carried|out|today|'
                         r'results?', re.A | re.I)
_ROW_NOT_DONE = re.compile(r'cancel\w*|abort\w*|postpon\w*|defer\w*|terminat\w*|discontinu\w*|halt\w*|stopped|'
                           r'interrupt\w*|abandon\w*|called|off|incomplete|fail\w*|unsuccessful|no-show', re.A | re.I)
# A negation turns a status or a reach to the not-done sense ("Not performed", "Cecum not reached") and a not-done status
# back ("Not cancelled"). A status that names both senses ("Status (completed/cancelled)") is a two-valued status
# column: its cell names the status itself, so it speaks for the row as written. The answer options a header may print
# beside its label ("Completed (Y/N)") are no subject of their own.
_ROW_NEGATION = frozenset(('not', 'never'))
_ROW_OPTION = frozenset(('y', 'n', 'yes', 'no'))
_ROW_REACH = re.compile(r'reach\w*|intubat\w*|seen|visuali[sz]\w*|examined|entered|identified|inspected|confirmed|'
                        r'photographed|photodocumented|documented', re.A | re.I)
_ROW_SERVICE_NOUN = frozenset(('procedure', 'procedures', 'examination', 'examinations', 'exam', 'study', 'service',
                               'endoscopy'))
_ROW_FUNCTION = frozenset(('the', 'a', 'an', 'of', 'to', 'in', 'on', 'at', 'and', 'or', 'was', 'were', 'is', 'been'))
_ROW_IGNORED = _ROW_SERVICE_NOUN | _ROW_FUNCTION | _ROW_OPTION
COLUMN_OWN, COLUMN_ROW, COLUMN_NOT_DONE = 'own', 'row', 'not done'
# A negative answer alone in a cell ("No", "None", "N/A"): under a not-done column it says the service was not called
# off. Its blank runs are read once, as _TABLE_ANSWER_CELL's are.
_TABLE_NEGATIVE_CELL = re.compile(r'[ \t]*+(?:no|none|nil|n/?a|not[ \t]++applicable|n)[ \t]*+\.?+[ \t]*+', re.A | re.I)
# The 'other' section of a table row held for its not-done status column (layout; detect reads it as a hold).
TABLE_ROW_HELD_LABEL = 'table row answering a not-done status column'


def _column_sense(label: str) -> str:
    """COLUMN_OWN when an answer-only data cell under the column ``label`` answers that column alone, COLUMN_ROW when it
    speaks for the row's service, COLUMN_NOT_DONE when it speaks for the row with the opposite sense (see above)."""
    if cues.EXTENT_HEADER.fullmatch(label):
        return COLUMN_ROW
    rest = label
    for _, _, pattern in cues.UPPER_LANDMARKS + cues.LOWER_LANDMARKS:
        rest = pattern.sub(' ', rest)
    landmark = rest != label
    for _, pattern in cues.SERVICE_PATTERNS:
        rest = pattern.sub(' ', rest)
    status = stopped = negated = False
    for word in _ROW_WORD.findall(rest):
        if word.lower() in _ROW_NEGATION:
            negated = True
        elif _ROW_NOT_DONE.fullmatch(word):
            stopped = True
        elif _ROW_STATUS.fullmatch(word) or _ROW_REACH.fullmatch(word):
            status = True
        elif word.lower() not in _ROW_IGNORED:
            return COLUMN_OWN  # a subject of its own: a finding, an act, an instrument, a date
    if stopped and status:
        return COLUMN_ROW  # a two-valued status: "Status (completed/cancelled)"
    if stopped != negated and (stopped or status or landmark):
        return COLUMN_NOT_DONE  # "Cancelled", "Not performed", "Cecum not reached"
    return COLUMN_ROW if status or landmark or stopped else COLUMN_OWN


# gi3 extent (R1): a procedure-summary label (a closed list) straight over a summary table opens a procedure section (h2-01:
# "Procedure summary" over "Examination | Instrument | Furthest point reached | Tissue sampled" was no heading, so the
# "Indications" section ran over the table and both services' parts, and every statement there read as an indication's).
# A summary table's first worded column names the examination (SERVICE_COLUMNS; a numbering column may stand before it),
# a later column is an extent label (cues.EXTENT_HEADER: an extent is written only once the examination is done), and no
# row carries a date (_ITEM_DATE: a table of planned or earlier procedures dates its rows). The label stands bare on its
# line ("Procedure summary") or with its colon and nothing after it ("Procedure summary:", otherwise an 'other' heading);
# blank lines may stand between it and the table. It never opens inside a plan or a history section, nor inside an
# 'other' section that stands in for a procedure, findings or technique section (layout). A table alone opens nothing
# (an office note's undated table of an outside colonoscopy has the same shape), and neither does the label over prose:
# a table is never by itself evidence that a service was done today.
PROCEDURE_SUMMARY_LABELS = frozenset(('procedure summary', 'procedures summary', 'summary of procedure',
                                      'summary of procedures', 'procedural summary', 'procedure overview',
                                      'procedures overview', 'examination summary', 'examinations summary'))
SERVICE_COLUMNS = frozenset(('examination', 'examinations', 'exam', 'exams', 'procedure', 'procedures', 'service',
                             'services', 'study', 'studies', 'endoscopy', 'endoscopies'))


# gi3 extent (R1, built): two conditions the adversarial probes of the investigated design asked for, both narrowing it
# back to the reading at 90377ec6f413 (the table stays the section's in force, so its services are asked):
# - a row states an extent under the extent column: its cell opens with a landmark or a depth ("the" or "a" at most
#   before it; detect._extent_column's own test). An extent column is evidence only once an extent is written in it: a
#   pre-procedure note's form with the column blank ("Colonoscopy | Adult colonoscope | -") read the booked colonoscopy
#   as performed;
# - no line from the table's first row to the next heading or table names one of the table's own services with an
#   earlier occasion of its own (_names_another_occasion, round 2's reader for procedure lines): an office note that
#   pasted an outside report's "Procedure summary" table ("The outside colonoscopy above was reviewed with the
#   patient.") read the outside colonoscopy as performed today. Each table's reach ends where the next table's header
#   starts, so the lines are read once.
_CELL_LEAD = re.compile(r'[ \t]*+(?:(?:the|a)[ \t]++)*+', re.A | re.I)
_STATED_DEPTH = re.compile(r'(?:approximately[ \t]+|about[ \t]+|~[ \t]*)?\d{1,3}[ \t]*cm\b', re.A | re.I)


def _states_an_extent(text: str, a: int, b: int) -> bool:
    """Whether the cell [a, b) opens with a landmark or a depth, "the" or "a" at most before it (see above)."""
    at = _CELL_LEAD.match(text, a, b).end()
    return bool(_STATED_DEPTH.match(text, at, b)) \
        or any(pattern.match(text, at, b) for _, _, pattern in cues.UPPER_LANDMARKS + cues.LOWER_LANDMARKS)


def _another_occasion_in_reach(text: str, lines: list[tuple[int, int]], line_starts: list[int], headings: dict,
                               table: Table, column: int, limit: int) -> bool:
    """Whether a line from the table's first row up to the next heading line or ``limit`` (the next table's header)
    names one of the services of the table's examination column (``column``) with an earlier occasion of its own."""
    families = {family for row in table.rows for family, pattern in cues.SERVICE_PATTERNS
                if pattern.search(text, *row[column])}
    patterns = [pattern for family, pattern in cues.SERVICE_PATTERNS if family in families]
    memo, j = {}, bisect.bisect_left(line_starts, table.rows[0][0][0])
    while patterns and j < len(lines) and lines[j][0] < limit and not headings[j]:
        ls, le = lines[j]
        if any(_names_another_occasion(text, ls, le, m.start(), m.end(), memo)
               for pattern in patterns for m in pattern.finditer(text, ls, le)):
            return True
        j += 1
    return False


# gi3 integration (interpretation 44's markers): the label opens nothing in a document whose own head titles it an
# office or clinic encounter's note (cues.EM_TITLE among its first context.TITLE_LINES non-blank lines, not led by a
# word naming another occurrence: the visit-title marker routing reads). An office visit documents the visit; a
# procedure-summary table in its note, with nothing saying whose or when, is a pasted report's ("Office Visit -
# progress note" over "Procedure summary" / "Examination | Instrument | Furthest point reached" / "Colonoscopy | Adult
# colonoscope | Cecum" read the colonoscopy as performed today), so the table stays the section's in force, as at
# 90377ec6f413, and its services are asked.
@functools.lru_cache(maxsize=1)
def _head_terms() -> tuple[int, re.Pattern]:
    """context.TITLE_LINES, and the words that lead a title naming another occurrence (detect's own reading of
    context._HEADING_OCCURRENCE: "Next", "Scheduled", "Prior", ...), read once."""
    from studio.gi import context  # local: context imports this module
    return context.TITLE_LINES, re.compile(r'\b(?:' + context._HEADING_OCCURRENCE.pattern + r')\b', re.A | re.I)


def _office_titled(text: str) -> bool:
    """Whether the document's own head titles it an office or clinic encounter's note (see above)."""
    head_lines, other = _head_terms()
    count = 0
    for m in re.finditer(r'[^\n]+', text):
        if not text[m.start():m.end()].strip():
            continue
        count += 1
        title = cues.EM_TITLE.match(text, m.start(), m.end())
        if title is not None and not other.search(text, m.start(), title.start('title')):
            return True
        if count == head_lines:
            return False
    return False


# gi3 fix round 1 (EXT-1, EXT-3): refusing office titles alone failed open. cues.EM_TITLE's class (an office, clinic,
# follow-up or return note or visit) holds none of "Progress Note", "Office progress note", "Gastroenterology
# Consultation", "New Patient Visit", "Telehealth Visit" or "Established patient visit", so under each of them a pasted
# colonoscopy's summary table opened a procedure section: the colonoscopy read performed today and 45385 went ready, or
# the visit's 99213 and 99204 were asked about a same-day procedure. The class of visit titles is open; a miss in it
# reads a pasted report as today's. So the label now needs positive evidence too: the document's own title - the first
# line of its head (context.TITLE_LINES non-blank lines; its markup and a closing aside set apart, no cell or tab in it)
# that is shaped as a title, ending with a document noun (_TITLE_NOUN_END) or opening with a report noun and its
# separator (_REPORT_HEAD) - is a procedure's report: a service's or an endoscopy's report or note ("Colonoscopy report",
# "Combined upper and lower endoscopy report", "ERCP Procedure Note", "Colonoscopy Report - Surveillance"), a procedure
# or operative report or note, or a report heading over its service ("Procedure report - flexible sigmoidoscopy",
# "PROCEDURE NOTE: EGD WITH BAND LIGATION"). A title that names another occurrence (_head_terms, _TITLE_QUALIFIER), a visit (_NOT_REPORT_TITLE's first
# part: "Colonoscopy consultation note"), another kind of report (pathology, imaging, discharge) or a note before or after
# a procedure ("Pre-procedure note", "Post-procedure note") is none. A document whose title is anything else, or that has
# none, keeps the table in the section in force, so its services are asked, as at 90377ec6f413: a miss in this class can
# only over-ask. The office-title refusal above stays (interpretation 48(c)). The line above the label is not read for an
# earlier occasion: a procedure report's indication names earlier examinations as a matter of course ("prior
# colonoscopy 2019"), and its summary is still today's; whose document it is, its title says.
_TITLE_NOUN_END = re.compile(r'\b(?:report|note|notes|record|visit|consultation|consult|encounter|evaluation|letter|'
                             r'summary)$', re.A | re.I)
_REPORT_HEAD = re.compile(r"(?:[A-Za-z][\w&/,()+'.-]*[ \t]+){0,6}?(?:report|note|summary)[ \t]*[:\u2013\u2014-]",
                          re.A | re.I)
# A report heading that names no service before its separator, only the report's kind ("Procedure report - ..."): the
# service is then named after it. Any other words before the separator must name the procedure themselves ("Note: ..."
# is no title).
_REPORT_KIND = re.compile(r'(?:procedure|operative|endoscopy|endoscopic)[ \t]+(?:report|note|summary)[ \t]*'
                          r'[:\u2013\u2014-]', re.A | re.I)
_REPORT_NOUN_END = re.compile(r'\b(?:report|note)$', re.A | re.I)
_PROCEDURE_REPORT_END = re.compile(r'\b(?:procedure|operative)[ \t]+(?:report|note)$', re.A | re.I)
_ENDOSCOPY_WORD = re.compile(r'\bendoscop\w*', re.A | re.I)
_NOT_REPORT_TITLE = re.compile(r'\b(?:visits?|consult\w*|encounters?|progress|follow[- ]?up|return|revisit|telehealth|'
                               r'telemedicine|pathology|histology|histopathology|cytology|radiology|imaging|laboratory|'
                               r'lab|discharge)\b'
                               r'|\b(?:pre|post)[- ]?(?:procedur\w*|op\w*|endoscop\w*|an(?:a)?esthe\w*|sedation)',
                               re.A | re.I)
_TITLE_LENGTH = 100  # a longer title is none; a head line four times longer is not read (bounds the work per line)
_NON_BLANK = re.compile(r'\S')


def _report_title(body: str) -> Optional[bool]:
    """None when ``body`` (a head line without its markup and closing aside) is not shaped as a title; else whether it
    titles the document a procedure's report (see above)."""
    if not body or len(body) > _TITLE_LENGTH or '|' in body or '\t' in body:
        return None
    report_head = _REPORT_HEAD.match(body)
    if report_head is None and not _TITLE_NOUN_END.search(body):
        return None
    if _head_terms()[1].search(body) or _TITLE_QUALIFIER.search(body) or _NOT_REPORT_TITLE.search(body):
        return False
    procedure = _service_named(body) or bool(_ENDOSCOPY_WORD.search(body))
    if report_head is not None:
        head = report_head.group(0)
        return _service_named(head) or bool(_ENDOSCOPY_WORD.search(head)) \
            or (procedure and bool(_REPORT_KIND.fullmatch(head)))
    return bool(_REPORT_NOUN_END.search(body)) and (procedure or bool(_PROCEDURE_REPORT_END.search(body)))


def _report_titled(text: str) -> bool:
    """Whether the document's own title, the first title-shaped line of its head, is a procedure's report (see above)."""
    head_lines = _head_terms()[0]
    count = 0
    for m in re.finditer(r'[^\n]+', text):
        if not _NON_BLANK.search(text, m.start(), m.end()):
            continue
        count += 1
        if m.end() - m.start() <= 4 * _TITLE_LENGTH:
            body = _TRAILING_ASIDE.sub('', text[m.start():m.end()].strip().strip('*#').strip())
            titled = _report_title(body.strip().strip('*#').strip())  # "**Colonoscopy report** (amended)"
            if titled is not None:
                return titled
        if count == head_lines:
            return False
    return False


def _summary_opens(text: str, lines: list[tuple[int, int]], headings: dict,
                   found: tuple[Table, ...]) -> dict[int, tuple[str, str, Span]]:
    """For each procedure-summary label line over a summary table (see above), the procedure section it opens."""
    opens, line_starts = {}, [ls for ls, _ in lines]
    if not found or _office_titled(text) or not _report_titled(text):  # gi3 fix round 1 (EXT-1, EXT-3)
        return opens
    for n, table in enumerate(found):
        column = 1 if table.labels[0] in _TABLE_NUMBERING_LABELS else 0  # the examination column
        extents = [k for k in range(column + 1, len(table.labels)) if cues.EXTENT_HEADER.fullmatch(table.labels[k])]
        if table.labels[column] not in SERVICE_COLUMNS or not extents \
                or not any(_states_an_extent(text, *row[k]) for row in table.rows for k in extents) \
                or any(_ITEM_DATE.search(text, row[0][0], row[-1][1]) for row in table.rows) \
                or _another_occasion_in_reach(text, lines, line_starts, headings, table, column,
                                              found[n + 1].header[0] if n + 1 < len(found) else len(text)):
            continue
        above = bisect.bisect_left(line_starts, table.header[0]) - 1
        while above >= 0 and not text[lines[above][0]:lines[above][1]].strip():
            above -= 1
        if above < 0:
            continue
        ls, le = lines[above]
        heading = headings[above]
        if heading is None:
            body = text[ls:le].strip(' \t*#')
            if normalize_label(body) in PROCEDURE_SUMMARY_LABELS:
                start = ls + text[ls:le].index(body)
                opens[above] = ('procedure', normalize_label(body), Span(start, start + len(body), body))
        elif heading[0] == 'other' and heading[1] in PROCEDURE_SUMMARY_LABELS and heading[2].text.endswith(':') \
                and not text[heading[2].end:le].strip():
            opens[above] = ('procedure', heading[1], heading[2])
    return opens


def _headings(text: str, lines: list[tuple[int, int]]) -> tuple[dict, set[int], list[tuple[int, int]],
                                                                 list[tuple[int, int]], list[tuple[int, int]]]:
    """Each line's heading (or None); the lines inside an extraction block, which never open a
    section beyond themselves; (line, header line) for each block's end: the line after the blank
    line that ends it, where the section in force before the block's header resumes; and (line,
    header line) after each form-field line that opened a section of its own (_field_heading), where
    the block's own section resumes; and the lines labelled by one of round 3b's plan labels with an answer of
    their own (_SEC_FIELD_PLAN_LABELS), which speak for their own line only (see layout). A performed-today label
    (_SEC_TODAY_LABELS) answered "None" on the next line is no heading."""
    headings, inside, resumes, field_ends, field_labels = {}, set(), [], [], []
    header, fields = None, False
    for i, (ls, le) in enumerate(lines):
        block = FORM_BLOCK.fullmatch(text[ls:le].strip())
        if block:
            headings[i], header, fields = _heading(text, ls, le), i, block.group('what') == 'form fields'
            continue
        headings[i] = None
        if header is None:
            headings[i] = _heading(text, ls, le)
        elif text[ls:le].strip():
            inside.add(i)
            headings[i] = _field_heading(text, ls, le) if fields else None
            if headings[i]:
                field_ends.append((i + 1, header))
        else:
            resumes.append((i + 1, header))
            header = None
    for i, heading in headings.items():
        if heading and heading[1] in _SEC_TODAY_LABELS and not text[heading[2].end:lines[i][1]].strip():
            answer = next((text[ls:le] for ls, le in lines[i + 1:i + 3] if text[ls:le].strip()), '')
            if _SEC_NO_ANSWER.fullmatch(answer):
                headings[i] = None  # "Procedures performed today:\nNone" (structure:9)
                continue
        if heading and heading[1] in _SEC_FIELD_PLAN_LABELS and i not in inside and i + 1 < len(lines) \
                and lines[i + 1][0] < len(text) and text[heading[2].end:lines[i][1]].strip():
            field_labels.append(i)  # "Referral: Dr. B. Synthetic", "Orders: CBC" (structure:5; round 4c sections:5)
    return headings, inside, resumes, field_ends, field_labels


@functools.lru_cache(maxsize=16)
def layout(text: str) -> Layout:
    lines = _lines(text)
    headings, inside, resumes, field_ends, field_labels = _headings(text, lines)
    joins, held = [], []  # whether each line runs on into the next; the lines held after an unfinished clause
    for i, (ls, le) in enumerate(lines):
        content = headings[i][2].end if headings[i] else ls  # a heading's inline content may run on
        open_end = i + 1 < len(lines) and not headings[i + 1] and i not in inside \
            and not (headings[i] and FORM_BLOCK.fullmatch(text[ls:le].strip()))
        joins.append(open_end and _soft_wrap(text, (content, le), lines[i + 1]))
        if open_end and not joins[-1] and i + 1 not in inside and _sec_held_after(text, (content, le), lines[i + 1]):
            held.append(i + 1)  # structure:11: it opens an 'other' section for itself alone
    # Round 4c regression:2 and sections:5. One of round 3b's plan labels with an answer of its own ("Referral: Dr. B.
    # Synthetic", "Orders: CBC") plans its own line, with the lines its sentence runs on into, and nothing after it:
    # round 4b's plan ran on over the prose after it (the performed polypectomy was excluded), and its resume before a
    # field read a planned field as performed ("EMR: ascending colon polyp at a tertiary center", 45390 ready). Up to
    # the next heading, a field line of the report's own fields (_S2_REPORT_FIELD) that names no service or intervention
    # ("Extent: cecum") reads in the section in force before the label, as round 4b's structure:5 repair wanted; every
    # other run of lines (a line and the lines its sentence runs on into) is HELD in an 'other' section of its own
    # (_SEC_PLAN_HELD_LABEL): it may be what the label orders or today's ("Interventions: cold snare polypectomy"), and no
    # word list tells which. Round 4d sections:0: a field naming a service no list knows ("Right hemicolectomy: Dr. B.
    # Synthetic", 44160 READY) resumed too; only the closed list of the report's own fields resumes now, with a landmark
    # field that states the landmark reached or seen, and (second round) none that names a procedure by its form
    # (_S2_PROCEDURE_WORD: "Extent: cecum, right hemicolectomy with Dr. B. Synthetic"). Inside a plan or history section
    # nothing is held: that section reads every line (see the gate below).
    # gi3 extent (R2, R3) and gi3 fix round 1 (EXT-4, EXT-5, EXT-7): every data cell of every table, with its column's
    # label; the clause cuts around each answer cell that answers its own column (_column_sense), on both sides, so it is
    # a clause of its own, and those cells (Layout.answer_cells); and the rows held for a not-done status column, which
    # are held like a line after an unfinished clause, each in an 'other' section of its own (TABLE_ROW_HELD_LABEL).
    found_tables = tables(text)
    line_starts = [ls for ls, _ in lines]
    columns, cell_cuts, answer_cells, held_labels = [], [], [], {i: _SEC_HELD_LABEL for i in held}
    for table in found_tables:
        senses = [_column_sense(label) for label in table.labels]  # each column's label is read once
        for row in table.rows:
            hold = False
            for k, (a, b) in enumerate(row):
                columns.append((a, b, table.labels[k]))
                if senses[k] == COLUMN_NOT_DONE and not _TABLE_NEGATIVE_CELL.fullmatch(text, a, b):
                    hold = True  # "Cancelled | Yes": the row may say its service did not happen
                elif k and (senses[k] == COLUMN_OWN and _TABLE_ANSWER_CELL.fullmatch(text, a, b)
                            or senses[k] == COLUMN_NOT_DONE):
                    cell_cuts.extend((row[k - 1][1], a))
                    if k + 1 < len(row):
                        cell_cuts.extend((b, row[k + 1][0]))
                    cell = _trimmed(text, a, b)
                    if cell:
                        answer_cells.append(cell)
            if hold:
                held_labels.setdefault(bisect.bisect_right(line_starts, row[0][0]) - 1, TABLE_ROW_HELD_LABEL)
    held = sorted(held_labels)
    line_ends, plan_runs, taken = [], [], set(held)
    for label_line in field_labels:
        end = next((j for j in range(label_line + 1, len(lines)) if headings[j]), len(lines))
        j = label_line
        while j + 1 < end and joins[j]:
            j += 1
        line_ends.append((j + 1, label_line))
        j += 1
        while j < end:
            first = j
            while j + 1 < end and joins[j]:
                j += 1
            line = text[lines[first][0]:lines[first][1]]
            if line.strip() and not (first == j and _SEC_FIELD_LINE.match(line)
                                     and (_S2_REPORT_FIELD.match(line) or _S2_landmark_field(line))
                                     and not _sec_act_named(line) and not _S2_PROCEDURE_WORD.search(line)):
                first += first in taken  # a line held after an unfinished clause keeps its own hold
                if first <= j:
                    plan_runs.append((first, j))
            j += 1
    # The marks of one line, in this order: the section in force before a block resumes (after the blank line
    # that ends it), the block's own section resumes (after a field line that opened its own), the section in
    # force before a field-label line or a held line resumes (after a label that speaks for its own line only, or
    # the line after an unfinished clause), a held line opens its own 'other' section, a heading opens. So a heading
    # wins where a resume falls on its line (the next page opens with "Findings:", an addendum's header).
    # A service line (session 7c8d38da GI round 2, extent; see _service_name_only) comes last on its line, and after it
    # a bare procedure-summary label (gi3 extent, R1; _summary_opens), which no heading or service line shares.
    resume, field_end, line_end, held_open, heading, service_line, summary_open = 0, 1, 2, 3, 4, 5, 6
    # Its candidates: a service's name standing alone, never on a heading line, inside an extraction block, held by
    # another rule, run on into or running on, nor before a procedure, findings or technique heading.
    last_positive = max((i for i, h in headings.items() if h and h[0] in POSITIVE_KINDS), default=-1)
    held_lines = set(held) | {first for first, _ in plan_runs}
    candidates = {}
    for i, (ls, le) in enumerate(lines):
        if headings[i] or i in inside or i in held_lines or joins[i] or (i > 0 and joins[i - 1]) or i < last_positive:
            continue
        head = _service_head(text, ls, le)
        if head is not None:
            candidates[i] = head
    service_lines, reporting = {}, set()  # line -> (whether the report names its service as its own, its part's section)
    if candidates:
        runs = _runs(lines, joins)
        declared = _declared_services(text, lines, headings, candidates, runs)
        service_lines = {i: (head[0] in declared[i], ('other', head[1], head[2])) for i, head in candidates.items()}
        reporting = _reporting_heads(text, lines, headings, candidates, joins, runs)
    firsts = {}
    summaries = _summary_opens(text, lines, headings, found_tables)  # a label with its colon is a heading line already
    marks = sorted([(i, heading, h) for i, h in headings.items() if h]
                   + [(i, summary_open, h) for i, h in summaries.items() if not headings[i]]
                   + [(i, service_line, i) for i in service_lines]
                   + [(i, held_open, ('other', held_labels[i], None)) for i in held]
                   + [(i + 1, line_end, i) for i in held if i + 1 < len(lines)]
                   + [(first, held_open, ('other', _SEC_PLAN_HELD_LABEL, None)) for first, _ in plan_runs]
                   + [(last + 1, line_end, first) for first, last in plan_runs if last + 1 < len(lines)]
                   + [(i, resume, header) for i, header in resumes if i < len(lines)]
                   + [(i, field_end, header) for i, header in field_ends if i < len(lines)]
                   + [(i, line_end, label_line) for i, label_line in line_ends if i < len(lines)],
                   key=lambda mark: mark[:2])
    line_only = {label_line for _, label_line in line_ends} | set(held) | {first for first, _ in plan_runs}
    # A phrase line (structure:4) and a held line (structure:11) only ever stand in for a procedure, findings or
    # technique section. In any other section the reading of 4347acd24 stands: a held line takes the section in force,
    # and a phrase line opens the plan or history section it opened then. The 'other' section such a line opens inside
    # one of those sections stands in for it, so the next phrase or held line is read as inside it too (round 4c
    # sections:6: the second of two phrase lines opened a plan or history section). The lines round 4c holds like a
    # phrase line (a statement that starts with the plan or the procedures, a numbered history item: sections:2,
    # sections:4) open the plan or history section of a phrase line only inside a plan or history section; elsewhere
    # (an impression, an indication, the text before the first heading) they are held too, because 4347acd24 read them
    # as content there, and a silent line there takes its family's reading.
    gated = {i for i, h in headings.items() if h and _sec_phrase_heading(text, h)} | set(held) \
        | {first for first, _ in plan_runs}
    widened = {i for i in gated if headings.get(i) and (_SEC_PLAN_FIRST.match(headings[i][1])
                                                        or _LIST_ITEM.match(text, *lines[i]))} \
        | {first for first, _ in plan_runs}
    opened, current, before_block, before_line, skipped = [], ('other', '', None), {}, {}, set()
    enclosed = False  # whether the 'other' section in force stands in for a procedure, findings or technique section
    service_part, indication = None, None  # the part a service line opened, and the indication it ended
    reporting_lines = set()  # gi3 extent (R9): the lines whose service line opened that service's own part
    for i, what, value in marks:
        positive = current[0] in POSITIVE_KINDS or enclosed
        if what == summary_open or (what == heading and i in summaries):  # gi3 extent (R1)
            if current[0] not in ('plan', 'history') and not enclosed:
                current, enclosed = summaries[i], False
                opened.append((i, current))
                continue
            if what == summary_open:
                continue  # inside a plan or a history section it is content; with its colon, the heading it was
        if what == service_line:
            declared_here, section = service_lines[value]
            opens = declared_here and value in reporting
            if current is not service_part:
                if not opens or current[0] != 'indication' or enclosed \
                        or not _indication_said(text, lines, line_starts, current, i, firsts):
                    continue  # content, as before: it ends only an indication that has said something of its own
                indication = current
            current, enclosed = (section if opens else indication), False  # its own part, or the indication's again
            service_part = current if opens else None
            if opens:
                reporting_lines.add(i)
            opened.append((i, current))
            continue
        if what in (heading, held_open) and i in gated and not positive \
                and (i not in widened or current[0] in ('plan', 'history')):
            if what == held_open:
                skipped.add(i)
                continue
            value = ('plan' if _PLAN_LABEL.search(value[1]) else 'history', value[1], value[2])
        if what == line_end and value in skipped:
            continue
        if what in (heading, held_open):
            if what == heading and FORM_BLOCK.fullmatch(text[lines[i][0]:lines[i][1]].strip()):
                before_block[i] = (current, enclosed)
            if i in line_only:
                before_line[i] = (current, enclosed)
            current, enclosed = value, i in gated and positive
        elif what == field_end:
            current, enclosed = headings[value], False
        elif what == line_end:
            current, enclosed = before_line.get(value, (current, enclosed))
        else:
            current, enclosed = before_block.get(value, (current, enclosed))
        opened.append((i, current))
    sections: list[Section] = []
    first = lines[opened[0][0]][0] if opened else len(text)
    if first > 0 or not opened:
        sections.append(Section('other', '', None, 0, first))
    for n, (i, (kind, label, span)) in enumerate(opened):
        start = lines[i][0]
        end = lines[opened[n + 1][0]][0] if n + 1 < len(opened) else len(text)
        if end > start or n + 1 == len(opened):
            sections.append(Section(kind, label, span, start, end))

    breaks: set[int] = set()
    for i, (ls, le) in enumerate(lines):
        breaks.update(_sentence_breaks(text, ls, le))
        if headings[i]:
            breaks.update((ls, headings[i][2].end))
        if not joins[i]:
            breaks.add(le)
    sentences = _segments(text, sorted(breaks | {0, len(text)}))
    # gi3 extent (R2, R3): the clause cuts around each answer cell that answers its own column (found above)
    cell_cuts.sort()
    clauses = []
    for s, e in sentences:
        cuts = {s, e}
        cuts.update(s + m.end() for m in re.finditer(';', text[s:e]))
        cuts.update(s + m.start() for m in _CLAUSE_WORD.finditer(text[s:e]))
        cuts.update(cell_cuts[bisect.bisect_right(cell_cuts, s):bisect.bisect_left(cell_cuts, e)])
        clauses.extend(_segments(text, sorted(cuts)))
    if cell_cuts:
        clauses = [c for c in clauses if text[c[0]:c[1]].strip(' \t|')]  # a separator between two cuts says nothing
    # gi3 extent (R9): the parts the reporting service lines opened (detect._answers_silently reads a label there)
    part_starts = {lines[i][0] for i in reporting_lines}
    reporting_parts = frozenset(section.start for section in sections if section.start in part_starts)
    return Layout(text, tuple(sections), tuple(sentences), tuple(clauses), tuple(s.start for s in sections),
                  found_tables, tuple(sorted(columns)), reporting_parts, tuple(sorted(answer_cells)))


def _segments(text: str, cuts: list[int]) -> list[tuple[int, int]]:
    out = []
    for a, b in zip(cuts, cuts[1:]):
        span = _trimmed(text, a, b)
        if span:
            out.append(span)
    return out
