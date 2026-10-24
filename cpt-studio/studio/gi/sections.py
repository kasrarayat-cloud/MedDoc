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
answer of their own followed by more fields they speak for their own line
only. A label line without
a colon ("Planned procedures", "Further management", a Word heading paragraph)
opens a plan or history section when its words say so and it ends with the
section of a note it names (procedures, plan, management, work-up ...), or
starts with the plan or the procedures and a plan word ("Procedures planned",
"Plan going forward"); never a service, an intervention or a landmark. A
numbered or bulleted line is read the same way ("2. Upcoming procedures"), so a
statement in a numbered list ("3. Further workup recommended") stays content
because it does not end with its noun.

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
# "Orders: none"). Round 4 structure:5: with an answer of their own they never open a plan section over later field
# lines (see _headings), and a no-answer value (_SEC_NO_ANSWER) is a field, as at R3B-BASE.
_SEC_FIELD_PLAN_LABELS = frozenset(('pending procedures', 'pending procedure', 'pending orders', 'orders', 'referrals',
                                    'referral', 'to do', 'to-do', 'procedure to be done', 'procedures to be done',
                                    'procedure to be performed', 'procedures to be performed',
                                    'procedures that will be performed'))
# A field's whole value when it answers nothing: "none", "N/A", "not applicable", "no", "nil" (optionally with a
# period).
_SEC_NO_ANSWER = re.compile(r'[ \t]*(?:none|n/?a|not[ \t]+applicable|no|nil)[ \t]*\.?[ \t]*', re.A | re.I)
# Round 3b's performed-today procedure labels (e7bc88a). Round 4 structure:9: answered with no answer ("Procedures
# performed today: none", or the bare label with "None" on the next line) they open no procedure section, so the
# plan items after them keep the section in force, as at R3B-BASE.
_SEC_TODAY_LABELS = frozenset(('procedure performed today', 'procedures performed today', 'procedure done today',
                               'procedures done today', 'intervention performed', 'interventions performed',
                               'intervention performed today', 'interventions performed today'))
# A key-value line ("Extent: cecum"): after a field-label line with an answer, it ends that label's reach.
_SEC_FIELD_LINE = re.compile(r'[ \t]*[A-Za-z][^:\n|]{0,39}:[ \t]*\S', re.A)
_SEC_FIELD_REACH = 3  # how many lines after a field-label line are read for the next field (bounds the work)
_PREFIX = re.compile(r'[ \t]*(?:#{1,4}[ \t]*|\*{1,2}[ \t]*|(?:\d{1,2}|[A-Za-z])[.)][ \t]+)?', re.A)
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
    if _SEC_PLAN_FIRST.match(named) and _PLAN_LABEL.search(named):
        return 'plan'  # "Procedures planned", "Plan going forward" (release:2: as at R3B-BASE)
    if not _SECTION_NOUN_LAST.search(named):
        return None
    kind = 'plan' if _PLAN_LABEL.search(line) else 'history' if _COLONLESS_HISTORY.search(line) else None
    if kind and _sec_phrase(named):
        return None if listed else 'other'  # structure:4: a finding or a statement, never history or plan
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
    content = '' if colon < 0 else line[colon + 1:]
    if label in _SEC_FIELD_PLAN_LABELS | _SEC_TODAY_LABELS and content.strip() and _SEC_NO_ANSWER.fullmatch(content):
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
_FIELD_ANSWER = re.compile(r'(?:^|[.;][ \t]+)(?P<label>[^:.;?=|\n]{1,60}?)[ \t]*'
                           r'(?P<sep>:|\?|=|[ \t][-\u2013\u2014][ \t])[ \t]*'
                           r'(?P<value>[^\s:?=|]+(?:[ \t]+[^\s:?=|]+){0,2})[ \t]*$', re.A)
# Before a dash a field's label names a thing; a clause ("Colonoscopy was performed - no EGD was done") is prose.
_LABEL_CLAUSE = re.compile(r'\b(?:was|were|is|are|has|have|had|did|does|do|will|would|shall|should|can|could|may|'
                           r'might|must)\b', re.A | re.I)
_ALONE_ANSWERS = frozenset(('no', 'not', 'never', 'none'))  # a whole answer when it is the whole value
_DENIALS = frozenset(('declined', 'declines', 'refused', 'refuses', 'denied', 'denies'))
_OPTION_ROW = re.compile(r'(?:[\u2610\u25a1\u25fb\u25fd\u274f\u2750\u2751\u2752\u2611\u2612\u2713\u2714\u25a0\u2327]'
                         r'|\[[ \t]*[xXvV*_\u2713\u2714]?[ \t]*\]|\([ \t]*[xX]?[ \t]*\)|\byes\b)[ \t/|,-]*\bno[ \t]*$',
                         re.A | re.I)
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
    declined" (a lone negation, or a short value ending in a denial)."""
    field = _FIELD_ANSWER.search(tail)
    if not field or (field.group('sep') not in ':?=' and _LABEL_CLAUSE.search(field.group('label'))):
        return False
    words = field.group('value').lower().split()
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
    if _answered(tail) or _OPTION_ROW.search(tail):
        return False
    last = _LAST_TOKEN.search(tail)
    if last is None:
        return False
    word = last.group(1).lower()
    if word in _WRAP_WORDS or last.group(1) in _WRAP_WORDS_LOWER:
        return True
    return (word in _DENIALS or bool(_OPEN_VERB.search(tail))) and not _own_clause(after)


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

    def section_at(self, pos: int) -> Section:
        index = bisect.bisect_right(self.section_starts, pos) - 1
        return self.sections[max(index, 0)]

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


def _headings(text: str, lines: list[tuple[int, int]]) -> tuple[dict, set[int], list[tuple[int, int]],
                                                                 list[tuple[int, int]], list[tuple[int, int]]]:
    """Each line's heading (or None); the lines inside an extraction block, which never open a
    section beyond themselves; (line, header line) for each block's end: the line after the blank
    line that ends it, where the section in force before the block's header resumes; and (line,
    header line) after each form-field line that opened a section of its own (_field_heading), where
    the block's own section resumes; and (line, label line) after a line labelled by one of round 3b's plan
    labels with an answer of its own (_SEC_FIELD_PLAN_LABELS) when the next line that is not blank is another field,
    where the section in force before the label line resumes: such a label speaks for its own line only. A
    performed-today label (_SEC_TODAY_LABELS) answered "None" on the next line is no heading."""
    headings, inside, resumes, field_ends, line_ends = {}, set(), [], [], []
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
            nxt = next((text[ls:le] for ls, le in lines[i + 1:i + 1 + _SEC_FIELD_REACH] if text[ls:le].strip()), '')
            if _SEC_FIELD_LINE.match(nxt):
                line_ends.append((i + 1, i))  # "Referral: Dr. B. Synthetic\nExtent: cecum" (structure:5)
    return headings, inside, resumes, field_ends, line_ends


@functools.lru_cache(maxsize=16)
def layout(text: str) -> Layout:
    lines = _lines(text)
    headings, inside, resumes, field_ends, line_ends = _headings(text, lines)
    # The marks of one line, in this order: the section in force before a block resumes (after the blank line
    # that ends it), the block's own section resumes (after a field line that opened its own), the section in
    # force before a field-label line resumes (after a label that speaks for its own line only), a heading opens.
    # So a heading wins where a resume falls on its line (the next page opens with "Findings:", an addendum's
    # header).
    resume, field_end, line_end, heading = 0, 1, 2, 3
    marks = sorted([(i, heading, h) for i, h in headings.items() if h]
                   + [(i, resume, header) for i, header in resumes if i < len(lines)]
                   + [(i, field_end, header) for i, header in field_ends if i < len(lines)]
                   + [(i, line_end, label_line) for i, label_line in line_ends if i < len(lines)],
                   key=lambda mark: mark[:2])
    line_only = {label_line for _, label_line in line_ends}
    opened, current, before_block, before_line = [], ('other', '', None), {}, {}
    for i, what, value in marks:
        if what == heading:
            if FORM_BLOCK.fullmatch(text[lines[i][0]:lines[i][1]].strip()):
                before_block[i] = current
            if i in line_only:
                before_line[i] = current
            current = value
        elif what == field_end:
            current = headings[value]
        elif what == line_end:
            current = before_line.get(value, current)
        else:
            current = before_block.get(value, current)
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
        content = ls
        if headings[i]:
            content = headings[i][2].end  # a heading's inline content may run on into the next line
            breaks.update((ls, content))
        joined = i + 1 < len(lines) and not headings[i + 1] and i not in inside \
            and not (headings[i] and FORM_BLOCK.fullmatch(text[ls:le].strip())) \
            and _soft_wrap(text, (content, le), lines[i + 1])
        if not joined:
            breaks.add(le)
    sentences = _segments(text, sorted(breaks | {0, len(text)}))
    clauses = []
    for s, e in sentences:
        cuts = {s, e}
        cuts.update(s + m.end() for m in re.finditer(';', text[s:e]))
        cuts.update(s + m.start() for m in _CLAUSE_WORD.finditer(text[s:e]))
        clauses.extend(_segments(text, sorted(cuts)))
    return Layout(text, tuple(sections), tuple(sentences), tuple(clauses), tuple(s.start for s in sections))


def _segments(text: str, cuts: list[int]) -> list[tuple[int, int]]:
    out = []
    for a, b in zip(cuts, cuts[1:]):
        span = _trimmed(text, a, b)
        if span:
            out.append(span)
    return out
