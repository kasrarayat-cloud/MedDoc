"""Labelled procedure paragraphs: one section fact for routing, the documented-service reader and the admission.

Completion repair, 2026-11-06 (U2, and U12's section fact; HARNESS.md "Completion repair (2026-11-06)"). A procedure
report may write each of its procedures as a paragraph labelled with the service's name, after its Indications line:

    Indications: Food impaction; surveillance after prior adenomas.
    Upper endoscopy: The gastroscope was advanced under direct visualization into the esophagus. ...
    Colonoscopy: The colonoscope was introduced through the anus and advanced to the cecum. ...
    Impression: ...

``sections.layout`` opens no section for such a label (a label with text after its colon is content), so the
Indications ran on over both narratives, routing held every performance cue there, read no extent, and the services
reader folded that doubt over its own reading. The layout is the context reader's frozen input for the date of service
(ops/gi4/freeze.py), so it is not changed here. Instead this module computes, once per text, the RELEASED labelled
paragraphs, and from them a derived layout (``clinical_layout``) that every clinical reader reads: routing's analysis,
the checks that read routing's layout, the services reader's section reads, the admission's held-section and
report-section reads. ``sections.layout(text)`` is never changed, and where nothing is released the derived layout IS
``sections.layout(text)`` (the same object), so every other document reads exactly as before.

The earlier attempt (F-SECTIONS L, harness repair 3) changed sections.py itself and was dropped after two refutation
cycles; its counterexamples (tests/fixtures/gi4/completion/corpus.json group A, "F-SECTIONS L" and "F-SECTIONS T")
are the acceptance set of the rules below. A paragraph is released only when ALL of these hold; any doubt keeps the
base reading (the Indications' hold), which is the safe side.

- P1, the document is a procedure report, read from its head (its first lines up to its first section heading with a
  colon; a report title the layout reads as a heading is read here as a title): a title line that is a GI procedure
  report's own title (_PROCEDURE_REPORT_TITLE, an allow-list grammar, so an unknown title word fails closed:
  "Gastroenterology Procedure Report", "Upper Endoscopy Report", "Procedure report (fictional)"), and no head title
  line names another kind of document (a clinic, office, telehealth, consult, anesthesia, pre-operative, orders,
  records, review, copy or draft document: _NOT_A_PROCEDURE_REPORT, with routing's own title-hold words); or, with no
  title line at all, a head made only of fields whose labels are a procedure report's own (_HEAD_FIELDS, an
  allow-list). Either way the document carries no office E/M structure (an E/M heading, an MDM, time or examination
  section, an office, clinic or telehealth visit named: cues.EM_VISIT).
- P2, the label is exactly one GI service's name (sections._service_name_only: "Upper endoscopy", "COLONOSCOPY",
  "Esophagogastroduodenoscopy (EGD)"), the label line starts a sentence of its own (the layout runs it on from no line
  above), and that first sentence narrates the label's scope's own course from the colon on: "[frame,] the|a|an
  [modifier] <instrument> was|were [adverb] introduced|advanced|inserted|passed", the instrument mapped to the label's
  family by the services reader's own mapping (services.INSTRUMENT_FAMILY; a bare "endoscope" names no family). A
  generic instrument ("the endoscope", "the scope") counts when the same sentence names the label's family's tract
  alone - its landmarks or its route in ("through the mouth ... to the second part of the duodenum" for an EGD; "through
  the anus ... to the cecum" for a colonoscopy) - refutation cycle 1, so a report that names its scope generically is
  read as one that names it by the service. The
  frame and the modifiers are allow-lists of today's procedure steps ("After repositioning,") and instrument kinds
  ("pediatric"): anything else before the instrument ("Previously,", "At the referring hospital,", "(outside)") fails.
- P3, the label's family fits the report: a head title naming families names this one; a procedure line ("Procedure:
  ...", a procedure heading with a colon) naming families names this one, with no other time, place, agent or source on
  it; the family has no second labelled paragraph and no positive section of its own elsewhere (a procedure, findings
  or technique body naming it or its instrument: a second narrative of one family is another occasion); a report with a
  positive section of its own besides the paragraph's declares the family on a procedure line; and the tract fits
  (_tract_misfit): no released paragraph names a site its own family's instrument cannot reach, and no site outside the
  history, plan and indication sections lies beyond every released, declared or titled family ("Upper endoscopy: ..."
  then "Findings: A 9 mm sigmoid colon polyp was removed": nothing in that report is released).
- P4, the containing section is an indication-type section whose heading line carries its own content (an empty heading
  directly introducing the paragraph makes the paragraph that heading's content), or a positive (procedure, findings,
  technique) section, or the paragraph directly follows a paragraph released here in the same section; a paragraph after
  one that is not released is never released.
- N1, no sentence of the paragraph states another time (a date, a year, a month or weekday, a time unit outside a
  future form, a past-time word), another place (outside, referring, a facility noun, a proper name after at/in/from/per),
  another agent (Dr., a person noun, "by" anything but a landmark, per, according to, reportedly) or another source (a
  report, a record, a chart, a copy, documentation); every sentence or clause whose subject is the examination ("This
  examination", "The procedure", a service name; "It" at a sentence's start) says only what an allow-list of today's
  predicates says (normal, complete, well tolerated, performed under sedation, a future form, ...); a later sentence
  naming the examination anywhere else ("The patient had this colonoscopy when she was 50.") holds, unless it says the
  patient tolerated it or that it had no complications; and no other family's service is named in the paragraph outside
  its frame of today's steps (the derived layout would read it as performed too). A future or plan word about a sub-act does not block ("not
  resected today; it will be referred for endoscopic mucosal resection"). A negative quantifier over what came before
  ("None of this was done today.") holds whatever its predicate (refutation cycle 1).
- N2, no later sentence that names the paragraph's family, an examination noun or "above" states another time (outside
  a plan section or a future form), place, agent or source ("Note: the colonoscopy above was performed in 2025 and is
  copied for reference."), and the family is named again nowhere after it but in the report's impression, assessment or
  plan sections and other labelled paragraphs ("Note: this colonoscopy belongs to another patient.").
- N3, the containing section's own text before its first labelled paragraph announces nothing (follows, below, as
  follows, attached, copied, a summary ...); names no examination noun or the family with a hold signal; in an
  indication, names no other occasion of the family by routing's own reading (detect.named_as_another_occasion: "She had
  a colonoscopy", "the index colonoscopy", "Her last colonoscopy"; a consent or a discussion of it is none); and does not
  end on a line that introduces what follows (a colon), nor on an unterminated line that may run on into the label (it
  ends on a function word or a determiner's phrase, or states a hold signal: "Surveillance after an outside").

What the release promises is layout parity (refutation cycle 2, 2026-11-06; HARNESS.md "Completion repair"): a released
paragraph reads no more permissively than its heading twin - the same text with "Colonoscopy: <narrative>" written
"Procedure: Colonoscopy" and the narrative under it - and a held one keeps the stricter base reading. Every false READY
both refutation cycles found here had a heading twin the installed release reads READY too, so cycle 1's readers that
made the labelled layout stricter than its twin (N3's deixis, present-occasion and attribution reads, N2's summary
dating, P4's first-summary rule) bought no safety over the heading form and held ordinary reports ("Pre-procedure
assessment: ASA class II.", "This is a 58-year-old man referred from an outside hospital."); they are removed, and a
generic scope's frame of today's steps is registered as a named scope's is (S8). The one difference measured is the
documented-service reader's: a released paragraph is a report part of its label's family, so an act its heading twin
drops for want of a part family (a food bolus with two families present and no site: stage 1's U1 binding) is bound to
it, as its corpus entry requires; P2 and P3 make every act of a released paragraph its family's (the instrument, the
tract). tests/test_completion_parity.py checks the parity over the corpus and both cycles' inputs.

A paragraph runs from its label line to the next line that opens a layout section or another label line ("Word:" with
content: sections._bare_label), whichever comes first; a blank line inside it is the narrative's own (its lines after
it are read by N1 and the tract rule like the rest), and what follows its end must be the report's own structure (N2). The released set is a pure function of the text:
it never reads the service date.

The corroborated release (the structure round, 2026-11-08, U18). Two of N1's readings are open-world: a place
preposition whose object no allow-list anchors (_unanchored_place: "the wire mark was noted at the bite block") and a
temporal adjunct no step of today's anchors (_TEMPORAL_LEAD: "while the wire was held in place"). They hold on a word the
allow-lists do not know, and the refuted repairs measured that no reading of the words themselves can tell "at the bite
block" from "at the army base" (lexical twins). So they are never read better here; instead, a paragraph they alone hold
(no other reading of N1, every other condition as installed) is released when the REPORT ITSELF states the paragraph's
acts as today's, independently of the paragraph, by its own structure (_corroborated):
- C1, the declaration: one of the report's procedure lines (P3's reading: a procedure heading with a colon and no other
  time, place, agent or source on it) lists, in an item naming the paragraph's family alone and stating no doubt, an
  act kind (services.ACTS) the paragraph states ("Procedures: EGD with dilation and biopsies; colonoscopy with
  polypectomy");
- C2, the summary: an impression or assessment sentence bound to the family (the sites it names lie in the family's
  reach, or it names the family's service, or the report declares that family alone), read on its own text as today's
  and undoubted (no hold signal by N1's own narrative reading, no word of the services reader's negation, hedge,
  cancellation, plan, history, incompleteness, hypothetical or failure tables), restates that same act kind; and the
  paragraph states it in a plain statement of its own (an act predicate in the act's clause, no such doubt word, no
  open-world reading in the sentence) - the act is stated three times by the report, never only named or denied;
- C3, the coverage: every act kind the paragraph states (but one its own "not <participle>" denies) is listed for the
  family or restated by such a summary sentence, so no act the report does not itself declare is read as today's
  through the release; each sentence carrying an open-world reading states today's procedure content (the scope, an
  act, a site in the family's reach) and is otherwise a plain statement - a sentence that says nothing of the procedure
  ("Everything was done on the cruise ship.") can only frame the whole account, and holds; and where the paragraph has
  a future word, each sentence is read on its own words for a closed signal (one sentence's future word never exempts
  another's time words);
- C4, one occasion: P3's sole narrative of the family, N2 and N3 hold as installed, and no section before the
  paragraph's own names an undated other occasion of the family by routing's own reading;
- C5, the twin's section (u18c cycle 2): the paragraph's procedure section is exactly its heading twin's - no layout
  section starts inside it, and it ends at the end of the text, at a line opening a layout section with a heading, or
  at the label line of a paragraph released with it (_ends_as_its_twin); and the twin's own layout (sections.layout of
  the twin text) opens exactly that section (_twin_disagrees: computed, never predicted - a layout rule that reads a line
  by the section in force is the twin's own). A report field or any other line after it ("Retroflexion: ...",
  "Withdrawal time: ...", which N2 accepts) would lie inside the twin's procedure section and outside the paragraph,
  where the twin reads it as today's procedure ("The procedure was aborted.") and the release would not: such a
  paragraph is not corroborated.
A paragraph after one released this way passes P4 only by its own C1-C5 (a release never lifts another paragraph by
itself), and P4 is read again after every withdrawal. A tract misfit returns the installed decisions.
Every closed reading keeps holding exactly as installed - dates, months, time and past words, other places, agents and
"by", sources, proper places, reported speech, examination subjects, the negative quantifier, another family - and so
do P1-P3, N2 and N3: a paragraph this release does not release keeps its installed reason. Its work is bounded
(CORROBORATED_DOCUMENT, CORROBORATED_PARAGRAPH, SUMMARY_READ, PROCEDURE_LINES_READ; each bound only withholds a release)
and linear: one predicate search per clause.

The computed heading twin (u18d, U18's changed approach; the block comment before _twin_parity). C1-C5 only PROPOSE: the
corroborated release's candidates stand only where the installed readers, run on the document's heading twin (every
released paragraph's "<L>: " written "PROCEDURE: <L>" and a newline), read every compared fact - the clinical layout,
routing's families, mentions, facts and analysis, the span readers on the released paragraphs, the documented services
with their acts and parts, the decisions of the paragraphs held - exactly as they read the document with the release;
on any difference every corroborated release of the document is withdrawn and it reads as installed. Corroboration's two
refuted cycles had reasoned that parity reader by reader and leaked at the readers nobody reasoned about; here it is
computed, never predicted. A corroborated paragraph is read as its twin's heading line reads, by three structural
choices the comparison then checks: the services reader's parts are the installed ones (installed_released: the
paragraph is no labelled report part of its family, as the twin's "PROCEDURE: <L>" line opens none - so a site-less act
in it binds as its twin binds it), the clinical layout cuts the label's words off as a sentence of their own
(_heading_split: routing reads the label against the narrative's first sentence, as the twin reads its heading), and
the services reader reads the label as it reads the twin's line (services._corroborated_labels).

Cost: one pass over the lines; every per-paragraph question is answered by bisection over positions found once per
text (signals, mentions, sentences), so the work is linear in the text whatever the number of labels.
"""
from __future__ import annotations

import bisect
import contextvars
import functools
import itertools
import re
from dataclasses import dataclass, replace
from typing import Optional

from studio.gi import cues
from studio.gi import sections as gi_sections
from studio.gi.sections import Layout, Section
from studio.types import Span

FLAGS = re.A | re.I

# --- P2: the label line --------------------------------------------------------------------------------------------
LABEL_READ = 100  # a label and its colon lie in a line's first characters (a line is never read further for one)
_LABEL_MARKS = ' \t*_#'


def _label_at(line: str) -> Optional[tuple[str, int, int]]:
    """(the label as written, its start, where the value after its colon starts) when ``line`` opens with a label - at
    most LABEL_READ characters, letters first, emphasis or heading marks around it set aside - a colon and a value of
    its own ("Colonoscopy: The colonoscope ...", "**COLONOSCOPY:** ..."); None otherwise. Read procedurally, so a long
    run of blanks costs its length once."""
    colon = line.find(':', 0, LABEL_READ)
    if colon < 0:
        return None
    lead = len(line) - len(line.lstrip(_LABEL_MARKS))
    label = line[lead:colon].rstrip(_LABEL_MARKS)
    if not label or not label[0].isalpha() or '|' in label:
        return None
    value = colon + 1
    while value < len(line) and line[value] in _LABEL_MARKS:
        value += 1
    if value >= len(line):
        return None
    return label, lead, value


_SERVICE_NAMES = '|'.join(f'(?:{pattern.pattern})' for _, pattern in cues.SERVICE_PATTERNS)
# Today's procedure steps that may open the first sentence before its instrument (an allow-list: anything else fails).
_FRAME = (r'(?:(?:after|following)[ \t\n]++(?:(?:the[ \t\n]++)?(?:patient[ \t\n]++)?repositioning(?:[ \t\n]++(?:of[ \t\n]++)?the[ \t\n]++'
          r'patient)?|(?:completion[ \t\n]++of[ \t\n]++)?(?:the[ \t\n]++)?(?:' + _SERVICE_NAMES + r'))'
          # the walk round (2026-11-07, finding 1): informed consent and a time-out, today's first steps
          r'|(?:after|following)[ \t\n]++(?:(?:informed|written)[ \t\n]++)?consent(?:[ \t\n]++was[ \t\n]++obtained)?'
          r'(?:[ \t\n]++and[ \t\n]++(?:a[ \t\n]++)?time-?[ \t\n]?out)?'
          r'|next|then|subsequently|thereafter|afterwards?'
          r'|with[ \t\n]++the[ \t\n]++patient[ \t\n]++in[ \t\n]++the[ \t\n]++(?:left|right)[ \t\n]++lateral(?:[ \t\n]++decubitus)?[ \t\n]++position)'
          r'[ \t\n]*+,[ \t\n]*+')
# Instrument kinds that may stand before the instrument (an allow-list).
_INSTRUMENT_MODIFIER = (r'(?:(?:adult|pediatric|paediatric|standard|slim|ultrathin|ultra-thin|high-definition|hd|'
                        r'variable-stiffness|therapeutic|diagnostic|video|flexible)[ \t\n]++){0,2}')
_COURSE_VERB = r'(?P<verb>introduced|advanced|inserted|passed)'
_COURSE_ADVERB = r'(?:(?:then|carefully|gently|subsequently|easily|successfully|readily)[ \t\n]++)?'

# --- N1, N2, N3: another time, place, agent or source (each a hold signal; any one blocks) ---------------------------
# The walk round (2026-11-07, finding 1; a fresh blind report): N1 held ordinary narrative on four words that cannot place
# the procedure in time or place - "After informed consent and a time-out, the gastroscope ...", "removed with the last
# dilator", "On a second look ...", "stopped on its own", "Digital rectal examination was normal." Each now reads as what
# it is: informed consent a step of today's procedure (_TODAYS_STEP); "last" another time only as a determiner of a time
# or an occasion, or before a participle of having been seen or done (_LAST_TIME); a look, a pass and an attempt today's
# handling, and "on its own" an idiom (_PP_SPECIFIC, _PP_IDIOM); an examination another examination's name qualifies is
# not the procedure (_EXAM_TOLERATED). Every other reading of N1 is unchanged and still fails closed.
_YEAR = r'\b(?:19|20)\d{2}s?\b|\B\'\d{2}s\b'
_MONTH_NAMES = (r'\b(?:January|February|March|April|June|July|August|September|October|November|December|Jan|Feb|Mar|'
                r'Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b\.?|\bMay\b(?![ \t]++(?:be|have|need|require|also)\b)')
_WEEKDAY = r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b'
_TIME_UNIT = (r'\b(?:days?|weeks?|months?|years?|decades?|fortnights?|visits?|occasions?|sessions?|admissions?|'
              r'encounters?|appointments?|hospitali[sz]ations?|stays?|dates?|childhood|youth|adolescence|infancy|'
              r'pregnanc(?:y|ies)|lifetime|era)\b')
_PAST_WORD = (r'\b(?:previously|previous|prior|earlier|before|beforehand|ago|formerly|former|recently|recent|yesterday|'
              r'last|initially|initial|originally|original|index|remote|historically|historical|already|since|once)\b'
              r'|\b(?:back|by|until|till|since|from)[ \t\n]++then\b|\bthen[ \t]*+[.;!?](?=\s|$)|\bat[ \t\n]++that[ \t\n]++time\b'
              r'|\b(?:at|by)[ \t\n]++(?:the[ \t\n]++)?age[ \t\n]++(?:of[ \t\n]++)?\d{1,3}\b|\b\d{1,3}[ \t\n-]++years?[ \t\n-]++old\b'
              r'|\bas[ \t\n]++an?[ \t\n]++(?:child|teenager|teen|young[ \t\n]++adult|student|baby|infant|adolescent)\b'
              r'|\bwhen[ \t\n]++(?:she|he|they|the[ \t\n]++patient)[ \t\n]++(?:was|were|had|lived|moved|worked|visited|stayed)\b'
              r'|\bin[ \t]++the[ \t]++past\b|\bpast[ \t]++(?:history|procedures?|examinations?|exams?|stud(?:y|ies)|visits?|'
              r'years?|months?|weeks?)\b')
_OTHER_PLACE = (r'\b(?:outside|elsewhere|referring|transferring|sending|outlying|external|offsite|off-site|OSH|abroad|'
                r'overseas)\b'
                r'|\b(?:hospitals?|facilit(?:y|ies)|cent(?:er|re)s?|clinics?|institutions?|institutes?|practices?|'
                r'offices?|departments?|infirmar(?:y|ies)|emergency[ \t]++(?:room|department)|ED|ER)\b')
_AGENT = (r'\b(?:Dr|Drs|Doctor)\b|\bper[ \t]++|\baccording[ \t]++to\b|\breported(?:ly)?\b|\bdocumented[ \t]++by\b'
          r'|\b(?:surgeons?|gastroenterologists?|endoscopists?|physicians?|doctors?|fellows?|residents?|colleagues?|'
          r'providers?|teams?|anesthesiologists?|anaesthetists?|anesthetists?|crnas?|technicians?|nurses?)\b')
_SOURCE = (r'\b(?:reports?|records?|cop(?:y|ies|ied)|pasted|reproduced|duplicat\w*|transcri\w*|scanned|faxed|received|'
           r'attached|enclosed|appended|imported|excerpt\w*|referrals?|summar(?:y|ies|ized|ised)|charts?|files?|'
           r'documented|documentation|examples?|templates?|hypothetical|simulated|illustrative)\b')
# Another place, agent or occasion by its determiner ("at another site", "a different provider", "on another day").
_ANOTHER = (r'\b(?:another|other|different|separate)[ \t\n]++(?:site|location|unit|campus|building|city|state|country|town|'
            r'institution|cent(?:er|re)|hospital|facility|clinic|practice|provider|physician|doctor|surgeon|'
            r'gastroenterologist|endoscopist|team|occasion|day|date|time|visit|encounter|admission|procedure|examination|'
            r'exam|study|patient)s?\b')
_LANDMARK_NAMES = '|'.join(f'(?:{p.pattern})' for _, _, p in cues.UPPER_LANDMARKS + cues.LOWER_LANDMARKS)
# "by" before a landmark identifies the landmark ("identified by the appendiceal orifice"); any other "by" names an
# agent or a manner, and holds (the safe side).
_BY_AGENT = re.compile(r'\bby[ \t\n]++(?!(?:both[ \t\n]++)?(?:the[ \t\n]++)?(?:' + _LANDMARK_NAMES + r'))', FLAGS)
# A proper name after a place preposition ("At Synthetic Valley Medical Center", "from Mercy"): read with case.
_PROPER_PLACE = re.compile(r'\b(?:[Aa]t|[Ii]n|[Ff]rom|[Pp]er)[ \t\n]++(?:the[ \t\n]++)?[A-Z][a-z]{2,}', re.A)
_MONTH = re.compile(_MONTH_NAMES, re.A)
# The same signals without the time ones (a plan section's or a future form's time is the plan's).
_NOT_TIME_SIGNALS = re.compile('|'.join(f'(?:{p})' for p in (_OTHER_PLACE, _AGENT, _SOURCE, _ANOTHER)), FLAGS)
_TIME_SIGNALS = re.compile('|'.join(f'(?:{p})' for p in (_YEAR, _WEEKDAY, _TIME_UNIT, _PAST_WORD)), FLAGS)
_LAST_TIME = re.compile(r'last[ \t\n]++(?:(?:' + _TIME_UNIT + r')|(?:' + _WEEKDAY + r')|(?:' + _MONTH_NAMES + r')'
                        r'|(?:time|night|occasion|visit|admission|appointment|procedure|examination|exam|endoscopy|scope)s?\b'
                        r'|(?:' + _SERVICE_NAMES + r')'
                        r'|(?:seen|done|performed|examined|evaluated|scoped|treated|had|underwent|undergone)\b)', FLAGS)
# A temporal adjunct ("during ...", "while ...", "after ...", "following ...", "upon ...", "at the time/end of ...") tells
# another time unless it anchors to one of today's procedure steps, the scope, or the examination itself (an allow-list:
# "after lavage", "during withdrawal", "following the upper endoscopy", "at the time of the procedure"); anything else -
# "during her pregnancy", "after her surgery", "while traveling" - holds. ("When she was ..." is _PAST_WORD's; a bare
# "when" opens today's steps too - "When the cecum was reached, ..." - and is not read here.)
_TEMPORAL_LEAD = re.compile(r'\b(?:during|while|after|following|upon|at[ \t\n]++the[ \t\n]++(?:time|end|conclusion|'
                            r'completion|close|start|beginning|outset)[ \t\n]++of)[ \t\n]++', FLAGS)
_TODAYS_STEP = re.compile(
    r'(?:(?:the|this|its|each|both|further|careful|gentle|scope|initial[ \t\n]++scope|complete|completion[ \t\n]++of[ \t\n]++the|'
    r'endoscopic|balloon|snare|informed|written)[ \t\n]++){0,3}(?:withdrawal|insertion|intubation|retroflexion|lavage|irrigation|suction(?:ing)?|'
    r'consent|'
    r'clearance|repositioning|dilation|dilatation|injection|resection|polypectomy|biops(?:y|ies)|deflation|inflation|'
    r'retrieval|removal|cleaning|washing|advancement|passage|entry|extubation|sedation|induction|insufflation|'
    r'decompression|examination|exam|procedure|procedures|endoscopy|inspection|evaluation|clipping|tattooing|'
    r'cannulation|sphincterotomy|aspiration|traversal|reinsertion|reintroduction|time-?out|withdrawing|inserting|'
    r'advancing|retroflexing|suctioning|irrigating|scope|colonoscope|gastroscope|endoscope|sigmoidoscope|instrument|'
    + r'(?:' + '|'.join(f'(?:{pattern.pattern})' for _, pattern in cues.SERVICE_PATTERNS) + r'))\b', FLAGS)
# N1's place reading (the paragraph's own narrative, and N2's for an impression, assessment or findings sentence about
# the procedure; plan and indication sentences are read by the classes above, N3's allow-lists and routing's own
# occasion reading). A place preposition ("in", "on", "at", "from", "into", "within" ...) in
# today's account takes a clinical object: an anatomical site or landmark (services.ANATOMY, cues' landmark tables) or a lesion, possibly behind
# position words ("in the mid and distal esophagus", "at the base of the polyp"); a handling, view, position, condition
# or measurement noun ("in two pieces", "on retroflexed view", "in stable condition", "at 30 cm"); one of today's rooms
# or sites behind a clinical word ("in the endoscopy suite", "at the polypectomy site"); or an idiom ("in place", "in
# addition", "in order to"). These are allow-lists: any other object - "on the cruise ship", "in her twenties",
# "at home", "at the edge of the city", "in the area where she was traveling" - may be another place or time, and holds.
# A time phrase is the time reader's, which reads the same span: a temporal adjunct ("at the time of", "at the end of")
# or a time word heading the object ("in 3 to 5 years", "at that time", "in 2019").
_PLACE_PREP = re.compile(r'\b(?:in|on|at|aboard|near|from|into|onto|inside|within|throughout|beside|behind|along|'
                         r'across|toward|towards)[ \t\n]++', FLAGS)
_PP_CLAUSE_MARK = re.compile(r'[,;:()]|\.(?!\d)')
_PP_NUMWORD = r'(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)'
_PP_NUMBER = (r'(?:\d+(?:\.\d+)?(?:[ \t]*+(?:-|to|or)[ \t]*+\d+(?:\.\d+)?)?|' + _PP_NUMWORD + r'(?:[ \t]++(?:to|or)[ \t]++'
              + _PP_NUMWORD + r')?)')
_PP_MOD = (r'(?:the|a|an|this|these|those|that|its|each|every|both|several|multiple|many|few|separate|direct|standard|'
           r'usual|routine|similar|stable|good|fair|poor|satisfactory|excellent|adequate|left|right|lateral|decubitus|'
           r'supine|prone|opposite|same|piecemeal|first|second|third|all|either|retroflexed|retroflex|forward|white|'
           r'narrow-band|narrow|band|close|careful|maximal|maximum|greatest|largest|single|digital|rectal|random|'
           r'various|and|or|&|'
           + _PP_NUMBER + r')')
_PP_SPECIFIC = (r'(?:pieces?|fragments?|jars?|containers?|bottles?|cups?|specimens?|formalin|views?|positions?|fashion|'
                r'manner|sequence|order|levels?|tips?|imaging|light|nbi|chromoendoscopy|proximity|segments?|'
                r'quadrants?|intervals?|walls?|sides?|aspects?|folds?|lumen|bases?|margins?|edges?|cent(?:er|re)|'
                r'periphery|stalks?|heads?|surfaces?|fields?|condition|defects?|beds?|retroflexion|withdrawal|insertion|'
                r'cm|mm|centimet(?:er|re)s?|millimet(?:er|re)s?|minutes?|seconds?|o\'clock|diameter|length|size|'
                r'dimensions?|extent|width|caliber|calibre|images?|photos?|photographs?|pictures?|patients?|'
                r'procedures?|examinations?|exams?|inspection|visuali[sz]ation|evaluation|palpation|looks?|'
                r'pass(?:es)?|attempts?|'
                r'this[ \t\n]++(?:time|point))')
_PP_LESION = (r'(?:polyps?|polypoid|lesions?|mass(?:es)?|ulcers?|ulcerations?|erosions?|tumou?rs?|nodules?|strictures?|'
              r'stenos[ie]s|diverticul(?:um|a)|h(?:a)?emorrhoids?|varices|varix|scars?|clips?|tattoos?|stents?|sutures?|'
              r'staples?|mucosa|vessels?|stool|fluid|debris|blood|clots?|bleeding|hernias?|anastomos[ie]s|pouch|stoma|'
              r'verge|lines?|bulb|remnant|(?:ge|g-e|gastro-?(?:o)?esophageal|esophagogastric|squamocolumnar|ileocecal|'
              r'ileocolic|anorectal|dentate|pectinate|z)[ \t\n-]*+(?:junction|line|valve)|incisors|teeth|hiatus|'
              r'(?:diaphragmatic[ \t\n]++)?pinch|flexure|incisura|angularis|orifice|sphincter|submucosa|submucosal|'
              r'muscularis|serosa|mucosal)')
# Today's instruments and accessories as an object ("in the trap", "into the channel", "in a retrieval net"), with up to
# two words of their own before them ("a Roth net", "the suction trap").
_PP_DEVICE = (r'(?:snares?|nets?|baskets?|traps?|forceps|channels?|scopes?|endoscopes?|colonoscopes?|gastroscopes?|'
              r'catheters?|caps?|hoods?|balloons?|wires?|guidewires?|needles?|probes?|devices?|instruments?|tubes?|'
              r'overtubes?|syringes?|loops?|bags?)')
_PP_GENERIC = r'(?:sites?|areas?|regions?|locations?|rooms?|suites?|units?|bays?|labs?|laborator(?:y|ies))'
_PP_CLINICAL_MOD = (r'(?:polypectomy|biopsy|biopsies|resection|mucosectomy|emr|esd|injection|tattoo|tattooed|clip|'
                    r'clipped|cautery|cauterized|ablation|ablated|treated|dilation|dilatation|dilated|anastomotic|'
                    r'surgical|bleeding|same|recovery|procedure|endoscopy|endoscopic|gi|operating|exam|examination)')
# A noun is the object's head only where the object ends with it: not before "of", "where", "when" or a possessive
# ("at the edge of the city", "in two pieces where ...", "in the patient's home" are read by the anchored path); a site
# or a room also not before a relative word ("at the site that she visited").
_PP_END = r'\b(?![\'’]|[ \t\n]++(?:of|where|when)\b)'
_PP_END_GENERIC = r'\b(?![\'’]|[ \t\n]++(?:of|where|which|that|who|when)\b)'
_PP_OBJECT_OK = re.compile(
    r'(?:' + _PP_MOD + r'[ \t\n,-]++){0,6}(?:(?:' + _PP_SPECIFIC + r'|' + _PP_LESION + r')' + _PP_END + r'|(?:'
    + _PP_CLINICAL_MOD + r'[ \t\n-]++){1,2}' + _PP_GENERIC + _PP_END_GENERIC + r')'
    + r'|(?:' + _PP_MOD + r'[ \t\n,-]++){1,6}(?:sites?|areas?|regions?|locations?)' + _PP_END_GENERIC
    + r'|(?:the|a|an)[ \t\n]++(?:[\w-]++[ \t\n]++){0,2}?(?:fashion|manner|' + _PP_DEVICE + r')' + _PP_END
    + r'|(?:the|a|an|this|our)[ \t\n]++(?:(?!(?:where|when|which|that|who|whom|whose)\b)[\w-]++[ \t\n]++){0,3}?'
    + r'(?:patients?|wom[ae]n|m[ae]n|gentlem[ae]n|lad(?:y|ies)|males?|females?|individuals?|persons?|adults?)'
    + _PP_END_GENERIC, FLAGS)
# A clock time is the paragraph's own timing ("The cecum was reached at 10:05").
_PP_CLOCK = re.compile(r'\d{1,2}:\d{2}(?:[ \t]*+(?:am|pm|a\.m\.|p\.m\.))?(?!\d)|\d{3,4}[ \t]*+(?:hours|hrs|h)\b', FLAGS)
_PP_IDIOM = re.compile(
    r'(?:place|situ|total|addition|order|turn|tandem|part|full|general|particular|summary|brief|least|most|once|all|'
    r'first|times|rest|view|sequence)\b(?![ \t\n]++of\b)'
    r'|(?:its|their|his|her)[ \t\n]++own\b'
    r'|keeping[ \t\n]++with\b|order[ \t\n]++to\b|preparation[ \t\n]++for\b|addition[ \t\n]++to\b'
    r'|(?:combination|conjunction|comparison|contrast)[ \t\n]++(?:with|to)\b|response[ \t\n]++to\b'
    r'|normal[ \t\n]++limits\b|(?:proximal|distal)[ \t\n]++to[ \t\n]++(?:proximal|distal)\b', FLAGS)
# The words that may stand before an anatomical, landmark or lesion anchor: the modifiers above, a possessive, "of", and
# position words ("the base of the polyp", "the rest of the colon", "her sigmoid colon").
_PP_LEAD = re.compile(
    r'(?:(?:' + _PP_MOD + r'|her|his|their|our|the[ \t\n]++patient[\'’]s|of|proximal|distal|mid|middle|upper|lower|'
    r'entire|whole|remaining|rest|remainder|visualized|visible|examined|ascending|descending|transverse|terminal|'
    r'anterior|posterior|medial|greater|lesser|fourth|portion|part|segment|level|aspect|side|wall|surface|lumen|area|'
    r'region|base|edge|margin|stalk|head|tip|cent(?:er|re)|periphery|floor|roof|apex|vicinity)[ \t\n,-]++){0,8}', FLAGS)
_PP_LESION_AT = re.compile(_PP_LESION + r'\b', FLAGS)
_PP_HEAD_WORD = re.compile(r'[\w\'-]*+', FLAGS)
# Reported speech in the paragraph: another source ("as she recalls", "the patient reports that ...", "the daughter
# says ...", "the note states ..."); a participle after a noun ("the polyp described above", "a lesion noted on CT") is
# read the same way, the safe side.
_REPORTED_SPEECH = re.compile(r'\b(?:she|he|they|(?:the|her|his|their)[ \t\n]++\w+)[ \t\n]++(?:recalls?|'
                              r'recalled|remembers?|remembered|reports?|reported|states?|stated|says|said|told|describes?|'
                              r'described|believes?|believed|thinks|thought|notes|noted[ \t\n]++that)\b', FLAGS)
# A time unit in a future form is the plan's ("in 3 years", "repeat in six weeks"), never another occasion's.
_FUTURE_UNIT = re.compile(r'\b(?:in|within|after)[ \t]++(?:about[ \t]++|approximately[ \t]++)?(?:\d{1,3}(?:[ \t]*+-[ \t]*+\d{1,3})?'
                          r'|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|a[ \t]++few|few|several)[ \t]++'
                          + _TIME_UNIT, FLAGS)
_FUTURE_CLAUSE = re.compile(r'\b(?:will|shall)\b|\b(?:is|are)[ \t]++(?:to[ \t]++be|planned|scheduled|recommended)\b'
                            r'|\b(?:repeat|return|next|future|follow-?up|surveillance|recommend\w*|plan(?:ned|s)?|'
                            r'schedul\w*)\b', FLAGS)
# N3: how an indication may name a labelled paragraph's family (an allow-list: any other mention holds) - in a sentence
# of consent or discussion ("Risks and benefits of upper endoscopy and colonoscopy were discussed."), qualified by an
# intent ("Screening colonoscopy"), or followed by its reason ("Colonoscopy for anemia", "... to evaluate ...").
_CONSENT_SENTENCE = re.compile(r'\b(?:risks?|benefits?|alternatives?|consent\w*|explained|discussed|informed|agreed)\b',
                               FLAGS)
_INTENT_BEFORE = re.compile(r'\b(?:screening|surveillance|diagnostic|therapeutic|average[ -]risk|high[ -]risk|elective|'
                            r'urgent|emergent|open[ -]access)[ \t\n]*+$', FLAGS)
_REASON_AFTER = re.compile(r'(?:[ \t\n]*+(?:,|and|&|/|plus)[ \t\n]*+(?:(?:an?|the)[ \t\n]++)?(?:' + _SERVICE_NAMES + r'))*'
                           r'[ \t\n]*+(?:,[ \t\n]*+)?(?:for|to[ \t\n]++(?:evaluate|assess|investigate|rule[ \t\n]++out|'
                           r'exclude)|due[ \t\n]++to|because[ \t\n]++of)\b', FLAGS)
_SOURCE_SIGNAL = re.compile(_SOURCE, FLAGS)
# What announces the paragraph that follows as a copy, a summary or another record (N3).
_ANNOUNCE = re.compile(r'\bas[ \t]++follows\b|\bfollows?\b(?![- \t]*+up\b)|\bbelow\b|\bthe[ \t]++following[ \t]*+:|\bhere(?:after|under|with)\b'
                       r'|\b(?:attached|enclosed|appended|reproduced|copied|pasted|transcribed|excerpted|quoted)\b'
                       r'|\bsummar(?:y|ies|ized|ised)\b'
                       # completion repair (integration): an account announced as coming next ("She had a colonoscopy in
                       # 2020, described next"), which the dated-occasion exemption below must never release
                       r'|\b(?:described|detailed|outlined|recounted|presented|reported|documented|listed|shown|given)'
                       r'[ \t]++(?:next|here|later|hereafter)\b', FLAGS)
# A year or a date in a text (an ISO date, m/d/y, a bare year): no reader of this module's own (refutation cycle 2
# removed cycle 1's summary dating, which read it); kept because services._earlier_date (acts, refutation cycle 1) reads
# it, with _document_day below.
_DATE_IN_TEXT = re.compile(r'\b(?P<y4>(?:19|20)\d{2})-(?P<m1>\d{1,2})-(?P<d1>\d{1,2})\b'
                           r'|\b(?P<m2>\d{1,2})/(?P<d2>\d{1,2})/(?P<y2>(?:19|20)?\d{2})\b'
                           r'|\b(?P<y>(?:19|20)\d{2})s?\b')
_NEGATIVE_SUBJECT = re.compile(r'[ \t\n]*+(?:none|nothing|neither|no[ \t\n]++(?:part|portion|step)s?|not[ \t\n]++(?:one|any))'
                               r'[ \t\n]++of[ \t\n]++(?:this|that|these|those|it|them|the[ \t\n]++(?:above|foregoing|'
                               r'procedures?|examinations?|exams?|steps?|findings))\b', FLAGS)
_DETERMINERS = frozenset(('a', 'an', 'the', 'her', 'his', 'their', 'its', 'this', 'that', 'these', 'those', 'any', 'no',
                          'our', 'my', 'your', 'some', 'each', 'every', 'another'))
# An examination noun: the examination itself, by a generic noun or by any service's name.
_EXAM_NOUN = (r'(?:examinations?|exams?|procedures?|stud(?:y|ies)|tests?|cases?|endoscop(?:y|ies)|narratives?|accounts?|'
              r'descriptions?|' + _SERVICE_NAMES + ')')
_EXAM_SUBJECT = re.compile(r'[ \t\n]*+(?:(?:the|this|that|these|those|today\'?s|said|same|present|current|above|both|each|'
                           r'either|neither|her|his|their|its)[ \t\n]++)?(?:(?:entire|whole|upper|lower|diagnostic|'
                           r'screening|surveillance)[ \t\n]++)?' + _EXAM_NOUN + r'\b(?![ \t\n]*+(?:-|of\b))', FLAGS)
_PRONOUN_SUBJECT = re.compile(r'[ \t\n]*+(?:it|this|that|the[ \t\n]++(?:above|foregoing|aforementioned|preceding)|all[ \t\n]++'
                              r'(?:of[ \t\n]++)?(?:this|the[ \t\n]++above))[ \t\n]++(?=(?:was|were|is|are|had|has|took|occurred|happened|'
                              r'showed|revealed|demonstrated)\b)', FLAGS)
# What an examination subject may say in today's own narrative (an allow-list; any other predicate holds).
_EXAM_PREDICATE_OK = re.compile(
    r'[ \t\n]++(?:(?:was|were|is|are)[ \t\n]++(?:then[ \t\n]++|also[ \t\n]++)?(?:otherwise[ \t\n]++)?(?:normal|unremarkable|'
    r'complete|completed|uncomplicated|well[ -]tolerated|tolerated[ \t\n]++well|successful|satisfactory|adequate|good|fair|'
    r'limited|difficult|technically[ \t\n]++(?:adequate|satisfactory|successful|difficult|challenging)|without[ \t\n]++'
    r'(?:complications?|difficulty|incident))\b'
    r'|(?:was|were)[ \t\n]++(?:then[ \t\n]++)?(?:performed|done|completed)(?:[ \t\n]*+(?:$|[.;,])|[ \t\n]++(?:under[ \t\n]++'
    r'(?:monitored[ \t\n]++anesthesia[ \t\n]++care|mac|moderate[ \t\n]++sedation|conscious[ \t\n]++sedation|deep[ \t\n]++'
    r'sedation|general[ \t\n]++anesthesia|propofol(?:[ \t\n]++sedation)?|sedation)|with[ \t\n]++the[ \t\n]++patient[ \t\n]++'
    r'in[ \t\n]++the[ \t\n]++(?:left|right)[ \t\n]++lateral(?:[ \t\n]++decubitus)?[ \t\n]++position|without[ \t\n]++'
    r'(?:complications?|difficulty|incident))[ \t\n]*+(?:$|[.;]))'
    r'|(?:will|shall)[ \t\n]++be\b|(?:is|are)[ \t\n]++(?:to[ \t\n]++be|planned|scheduled|recommended)\b'
    r'|(?:showed|revealed|demonstrated)\b)', FLAGS)
# An examination named anywhere in a later sentence of the paragraph (its subject, its object): such a sentence may say
# only what the subject allow-list says, or that the patient tolerated it ("The patient tolerated both procedures
# ..."); anything else about the examination ("The patient had this colonoscopy when she was 50.") holds.
_EXAM_MENTION = re.compile(r'\b' + _EXAM_NOUN + r'\b', FLAGS)
_EXAM_TOLERATED = re.compile(r'[ \t\n]*+(?:(?:(?:a|the)[ \t\n]++)?(?:digital[ \t\n]++rectal|rectal|physical|abdominal|perianal|'
                             r'anal|pelvic|cardiopulmonary|neurologic(?:al)?)[ \t\n]++(?:examination|exam)\b'
                             r'|(?:the[ \t\n]++)?(?:patient|she|he)[ \t\n]++tolerated[ \t\n]++(?:(?:the|both|this|all|each)'
                             r'[ \t\n]++)?' + _EXAM_NOUN + r'\b'
                             r'|there[ \t\n]++(?:were|was)[ \t\n]++no[ \t\n]++(?:(?:immediate|apparent|other)[ \t\n]++)?'
                             r'complications?[ \t\n]++(?:of|from|during|after)[ \t\n]++(?:the|this)[ \t\n]++' + _EXAM_NOUN
                             + r'[ \t\n]*+[.;]?[ \t\n]*+$)', FLAGS)
# A pronoun subject at a sentence's start may also tell the scope's course ("It was advanced to the cecum.").
_PRONOUN_PREDICATE_OK = re.compile(r'(?:was|were)[ \t\n]++(?:then[ \t\n]++)?(?:advanced|withdrawn|passed|introduced|'
                                   r'inserted|reached|intubated|retroflexed)\b', FLAGS)

# --- P1: the document's head ---------------------------------------------------------------------------------------
_TITLE_PREFIX = (r'(?:gastroenterology|gastrointestinal|gi|digestive|endoscopy|endoscopic|outpatient|inpatient|'
                 r'ambulatory|screening|surveillance|diagnostic|therapeutic)')
_TITLE_CORE = (r'(?:procedures?|endoscopy|endoscopic|(?:' + _SERVICE_NAMES + r')(?:[ \t]*+(?:,|and|&|/|with|plus)[ \t]*+(?:'
               + _SERVICE_NAMES + r'))*)')
_PROCEDURE_REPORT_TITLE = re.compile(r'(?:' + _TITLE_PREFIX + r'[ \t]++){0,3}' + _TITLE_CORE
                                     + r'(?:[ \t]++procedures?)?[ \t]++(?:report|note)', FLAGS)
_SAFE_ASIDE = re.compile(r'[ \t]*+\([ \t]*+(?:fictional|synthetic|final)[ \t]*+\)[ \t]*+$', FLAGS)
_NOT_A_PROCEDURE_REPORT = re.compile(
    r'\b(?:clinic|office|telehealth|telemedicine|virtual|video|telephone|phone|consult\w*|an(?:a)?esthe\w*|pre-?op\w*|'
    r'pre-?procedure|post-?op\w*|h[ \t]*+&[ \t]*+p|history|physical|orders?|nursing|nurse|discharge|progress|letters?|'
    r'correspondence|referrals?|records?|outside|external|prior|previous|cop(?:y|ia|ies|ied)|duplicates?|drafts?|'
    r'templates?|addend\w*|requests?|requested|pathology|radiology|imaging|summary|review\w*|education|instructions?|'
    r'consent|booking|scheduling|follow[- ]?up|visit|encounter|admission|emergency|triage|void|error|unsigned|'
    r'preliminary|amended|planned|scheduled|cancel\w*|awaiting|pending)\b', FLAGS)
# The fields a procedure report's head carries (an allow-list: a head with any other field, untitled, fails closed).
_HEAD_FIELDS = frozenset((
    'date of service', 'date of procedure', 'procedure date', 'service date', 'date', 'exam date', 'examination date',
    'patient', 'patient name', 'name', 'mrn', 'medical record number', 'dob', 'date of birth', 'age', 'sex', 'gender',
    'endoscopist', 'proceduralist', 'performing physician', 'performing endoscopist', 'physician', 'attending',
    'attending physician', 'gastroenterologist', 'referring physician', 'referring provider', 'facility', 'location',
    'place of service', 'setting', 'room', 'sedation', 'anesthesia', 'anesthesia type', 'assistant', 'nurse', 'fellow',
    'procedure', 'procedures', 'procedure performed', 'procedures performed'))
_EM_LABELS = frozenset(('chief complaint', 'cc', 'reason for visit', 'history of present illness', 'hpi',
                        'review of systems', 'ros', 'medical decision making', 'medical decision-making', 'mdm',
                        'decision making'))


@dataclass(frozen=True)
class LabelledParagraph:
    """A released labelled procedure paragraph: [start, end) runs from its label line's start to the start of the line
    that ends it; ``label`` is the label as written with its colon; ``family`` the label's routing family.
    ``corroborated``: released by the corroborated release (the module docstring), never by the installed conditions -
    services._labelled_parts reads it, so such a paragraph changes the kind of no part outside itself."""
    start: int
    end: int
    family: str
    label: Span
    corroborated: bool = False


@dataclass(frozen=True)
class _Candidate:
    start: int
    end: int
    family: str
    label: Span
    body: int  # where the narrative starts (after the colon)
    section: int  # index of the frozen layout section the label line lies in


def _instrument_family(word: str) -> str:
    from studio.gi import services as gi_services  # local: services is the instrument mapping's owner
    return gi_services._instrument_family(word)


def _instruments_pattern() -> str:
    from studio.gi import services as gi_services
    return gi_services.INSTRUMENTS.pattern


@functools.lru_cache(maxsize=1)
def _course_start() -> re.Pattern:
    """P2's first-sentence shape (built once: the instrument names are the services reader's own)."""
    return re.compile(r'(?P<frame>' + _FRAME + r')?(?:the|a|an)[ \t\n]++' + _INSTRUMENT_MODIFIER + r'(?P<instrument>'
                      + _instruments_pattern() + r')[ \t\n]++(?:was|were)[ \t\n]++' + _COURSE_ADVERB + _COURSE_VERB
                      + r'\b', FLAGS)


# P2 (refutation cycle 1): a generic instrument ("The endoscope was inserted through the mouth and advanced ... to the
# second part of the duodenum", "The scope was advanced to the cecum") names no family by its name; its course names
# the tract it went through - the landmark tables (cues.UPPER_LANDMARKS / LOWER_LANDMARKS) and the routes in - and the
# label's family is the one that tract fits (an upper tract for an EGD; a lower one for a colonoscopy or a flexible
# sigmoidoscopy). A course that names both tracts, or neither, fails (the safe side).
_GENERIC_INSTRUMENT = r'(?:endoscope|scope|instrument)'
_UPPER_ROUTE = re.compile(r'\b(?:(?:through|via|into)[ \t\n]++the[ \t\n]++(?:mouth|oropharynx|hypopharynx)|orally|per[ \t\n]++os|'
                          r'transoral(?:ly)?)\b', FLAGS)
_LOWER_ROUTE = re.compile(r'\b(?:(?:through|via|into)[ \t\n]++the[ \t\n]++(?:anus|anal[ \t\n]++canal)|per[ \t\n]++(?:rectum|anum)|'
                          r'transanal(?:ly)?)\b', FLAGS)
_TRACT_OF = {'gi.egd': 'upper', 'gi.colonoscopy': 'lower', 'gi.flex_sig': 'lower'}


@functools.lru_cache(maxsize=1)
def _generic_course_start() -> re.Pattern:
    return re.compile(r'(?P<frame>' + _FRAME + r')?(?:the|a|an)[ \t\n]++' + _INSTRUMENT_MODIFIER + r'(?P<instrument>'
                      + _GENERIC_INSTRUMENT + r')[ \t\n]++(?:was|were)[ \t\n]++' + _COURSE_ADVERB + _COURSE_VERB + r'\b',
                      FLAGS)


def _course_tract(text: str, start: int, end: int) -> str:
    """'upper' or 'lower' when [start, end) names landmarks or routes of that tract alone; '' otherwise."""
    upper = bool(_UPPER_ROUTE.search(text, start, end)) or any(p.search(text, start, end) for _, _, p in cues.UPPER_LANDMARKS)
    lower = bool(_LOWER_ROUTE.search(text, start, end)) or any(p.search(text, start, end) for _, _, p in cues.LOWER_LANDMARKS)
    return 'upper' if upper and not lower else 'lower' if lower and not upper else ''


def _signals(text: str, start: int, end: int, time: bool = True, narrative: bool = False,
             open_world: bool = True) -> bool:
    """Whether [start, end) states another time (``time``), place, agent or source (the hold signals above); a time
    unit in a future form, or any time in a future clause, is the plan's and does not count. ``narrative`` reads a
    labelled paragraph's own account (N1), or a summary sentence about the procedure (N2): every place adjunct anchors
    to today's anatomy or handling, and no person's reported speech. ``open_world`` False sets aside the two open-world
    readings - the narrative place object no allow-list anchors and the temporal adjunct no step of today's anchors - and
    nothing else; only the corroborated release asks (the structure round, U18): every caller keeps the default."""
    if _NOT_TIME_SIGNALS.search(text, start, end) or _BY_AGENT.search(text, start, end) \
            or _PROPER_PLACE.search(text, start, end):
        return True
    if narrative and (_REPORTED_SPEECH.search(text, start, end)
                      or (open_world and _unanchored_place(text, start, end))):
        return True
    if not time:
        return False
    from studio.gi import context as gi_context  # local: the date reader's own date mentions (read only)
    if gi_context.find_dates(text[start:end]) or _MONTH.search(text, start, end):
        return True
    for m in (_TEMPORAL_LEAD.finditer(text, start, end) if open_world else ()):
        if _TODAYS_STEP.match(text, m.end(), end) is None:
            return True  # "during her pregnancy", "after her surgery": a time no step of today's procedure anchors
    future = _FUTURE_CLAUSE.search(text, start, end) is not None
    for m in _TIME_SIGNALS.finditer(text, start, end):
        if m.group(0).lower() == 'last' and _LAST_TIME.match(text, m.start(), end) is None:
            continue  # the walk round (finding 1): "with the last dilator" - an ordinal of a thing, no time
        if future and not re.fullmatch(_PAST_WORD, m.group(0), FLAGS):
            continue  # "it will be referred in 6 weeks": the plan's time
        if not re.fullmatch(_PAST_WORD, m.group(0), FLAGS) and any(
                f.start() <= m.start() < f.end() for f in _FUTURE_UNIT.finditer(text, max(start, m.start() - 40),
                                                                                  min(end, m.end()))):
            continue  # "in 3 years": a future form
        return True
    return False


# A determiner-led noun phrase coordinated after an allowed object, before the clause mark, is read as an object of the
# same preposition ("in the sigmoid colon and the basement", "in the colon wall and her home"); a finite verb after the
# coordinator makes it a clause of its own ("and the remainder of the examination was normal"), whose own prepositions
# are read where they stand.
_PP_COORD = re.compile(r'[ \t\n]++(?:and|or|&|as[ \t\n]++well[ \t\n]++as|plus)[ \t\n]++(?=(?:the|a|an|her|his|their|our|this|'
                       r'that|these|those|its)\b)', FLAGS)
_PP_FINITE = re.compile(r'\b(?:was|were|is|are|be|been|being|had|has|have|did|does|do|could|would|will|can|may|might|'
                        r'should|shall|must|appeared|appears|showed|shows|revealed|reveals|demonstrated|demonstrates)\b',
                        FLAGS)


def _object_end(text: str, pos: int, stop: int, anchors: list, anchor_starts: list) -> Optional[int]:
    """Where the allowed object that starts at ``pos`` ends (``stop`` for an idiom), or None when the allow-lists above
    do not anchor it. ``anchors`` are the paragraph's anatomical and landmark matches (start, end), sorted, read once
    per paragraph; ``anchor_starts`` their starts (bisection)."""
    if _PP_IDIOM.match(text, pos, stop):
        return stop
    ok = _PP_OBJECT_OK.match(text, pos, stop)
    if ok is not None:
        return ok.end()
    lead = _PP_LEAD.match(text, pos, stop).end()
    lesion = _PP_LESION_AT.match(text, lead, stop)
    if lesion is not None:
        return lesion.end()  # "at the base of the polyp", "on the stalk of the polyp"
    k = bisect.bisect_left(anchor_starts, pos)
    if k < len(anchors) and anchors[k][0] <= lead:
        return anchors[k][1]  # "in the sigmoid colon", "in the mid and distal esophagus", "in the rest of the colon"
    return None


def _unanchored_place(text: str, start: int, end: int) -> bool:
    """Whether a place preposition in [start, end) takes an object the allow-lists above do not anchor (N1), or a
    coordinated object they do not anchor (the first of _unanchored_places)."""
    return next(_unanchored_places(text, start, end), None) is not None


def _unanchored_places(text: str, start: int, end: int):
    """The position of each place preposition in [start, end) whose object, or a coordinated object, the allow-lists
    above do not anchor, in order. The object is read up to a clause mark, at most 60 characters and the end of the word
    there (40 more at most); one pass of the anatomy and landmark tables over the paragraph, bisection per object
    (linear). The structure round: a generator, so the corroborated release can place each one in its sentence;
    _unanchored_place reads its first, exactly as before."""
    from studio.gi import services as gi_services
    anchors: Optional[list] = None
    anchor_starts: list = []
    for m in _PLACE_PREP.finditer(text, start, end):
        if _TEMPORAL_LEAD.match(text, m.start(), end) or _PP_CLOCK.match(text, m.end(), end):
            continue  # "at the time of the examination", "at the end of the procedure": the time reader's; "at 10:05"
        stop = min(end, m.end() + 60)
        mark = _PP_CLAUSE_MARK.search(text, m.end(), stop)
        if mark is not None:
            stop = mark.start()
        elif stop < end:
            stop = _PP_HEAD_WORD.match(text, stop, min(end, stop + 40)).end()  # never a cut word: "base|ment"
            if stop < end and _PP_HEAD_WORD.match(text, stop, stop + 1).end() > stop:
                yield m.start()  # a word runs on past the window: the object cannot be read (the safe side)
                continue
        lead = _PP_LEAD.match(text, m.end(), stop).end()
        head = _PP_HEAD_WORD.match(text, lead, stop).end()
        if any(m.start() <= t.start() < max(head, m.end() + 1)
               for t in itertools.chain(_TIME_SIGNALS.finditer(text, m.start(), stop), _MONTH.finditer(text, m.start(), stop))):
            continue  # "in 3 to 5 years", "at that time", "in 2019", "on Monday": a time heads the object (the time reader's)
        if anchors is None:
            anchors = sorted((h.start(), -h.end()) for _, _, p in gi_services.ANATOMY + cues.UPPER_LANDMARKS
                             + cues.LOWER_LANDMARKS for h in p.finditer(text, start, end))
            anchors = [(a, -b) for a, b in anchors]  # by start, the longest first
            anchor_starts = [a for a, _ in anchors]
        at = _object_end(text, m.end(), stop, anchors, anchor_starts)
        while at is not None and at < stop:
            coordinated = _PP_COORD.search(text, at, stop)
            if coordinated is None or _PP_FINITE.search(text, coordinated.end(), stop):
                break
            at = _object_end(text, coordinated.end(), stop, anchors, anchor_starts)
        if at is None:
            yield m.start()


def _exam_subject_holds(text: str, s: int, e: int, sentence_start: bool) -> bool:
    """Whether the sentence or clause [s, e) has the examination as its subject and says something an allow-list of
    today's predicates does not (N1). A pronoun subject ("It", "This", "That") is read at a sentence's start only. A
    negative quantifier over what came before ("None of this was done today.", "Nothing of the above ...") denies it,
    whatever its predicate (refutation cycle 1)."""
    if _NEGATIVE_SUBJECT.match(text, s, e):
        return True
    m = _EXAM_SUBJECT.match(text, s, e)
    if m is not None:
        return _EXAM_PREDICATE_OK.match(text, m.end(), e) is None
    if sentence_start:
        p = _PRONOUN_SUBJECT.match(text, s, e)
        if p is not None:
            return (_EXAM_PREDICATE_OK.match(text, p.end() - 1, e) is None
                    and _PRONOUN_PREDICATE_OK.match(text, p.end(), e) is None)
    return False


@dataclass(frozen=True)
class _Head:
    procedure_report: bool
    title_families: frozenset
    body_start: int = 0  # where the head ends: the first line that is neither a title line nor a head field


@functools.lru_cache(maxsize=16)
def _head(text: str) -> _Head:
    """P1 and P3's title families: the document's head is its first lines (at most sections.PROCEDURE_HEAD_LINES
    non-empty ones) up to its first section heading that is not a title line (a report title the layout reads as a
    procedure heading, "Upper Endoscopy Report", has no colon and is read here as a title). Bounded: those lines, each
    at most 200 characters read."""
    lay = gi_sections.layout(text)
    titles, fields, positive, denied, seen = [], [], False, False, 0
    pos, size = 0, len(text)
    while pos < size and seen < gi_sections.PROCEDURE_HEAD_LINES:
        nl = text.find('\n', pos)
        end = size if nl < 0 else nl
        section = lay.section_at(pos)
        if section.heading is not None and section.start == pos and ':' in section.heading.text:
            break  # the body's first heading ("Indications:", "Sedation:", "Procedure:")
        line = text[pos:min(end, pos + 200)].strip().strip('#*_>').strip()
        if line:
            seen += 1
            field = _label_at(line)
            if field is not None and len(field[0]) <= 60:
                fields.append(' '.join(field[0].lower().split()))
            elif line[-1] in '.!?;' or len(line) > 100:
                break  # a sentence: the body has begun
            else:
                titles.append(line)
        if nl < 0:
            pos = size
            break
        pos = nl + 1
    body_start = pos
    from studio.gi import detect  # local: detect imports this module (routing's own title-hold words)
    for line in titles:
        if _NOT_A_PROCEDURE_REPORT.search(line) or detect._GI4_TITLE_HOLD.search(line) \
                or gi_sections.AROUND_PROCEDURE_WORDS.search(line):
            denied = True
        bare = _SAFE_ASIDE.sub('', line)
        bare = re.sub(r'[ \t]++[-–—|:][ \t]++|[ \t]{2,}', ' ', bare).strip()
        if _PROCEDURE_REPORT_TITLE.fullmatch(bare):
            positive = True
    families = frozenset(f for line in titles for f, pattern in cues.SERVICE_PATTERNS if pattern.search(line))
    # the walk round (2026-11-07, finding 1): an E/M visit a plan section names ("Clinic visit in four weeks") is a later
    # visit, never this document's own structure; named anywhere else it still is
    em = (any(s.kind in ('mdm', 'time', 'exam') or s.label in _EM_LABELS for s in lay.sections)
          or any(lay.section_at(m.start()).kind != 'plan' for m in cues.EM_VISIT.finditer(text)))
    if em or denied:
        return _Head(False, families, body_start)
    if positive:
        return _Head(True, families, body_start)
    untitled = not titles and bool(fields) and all(label in _HEAD_FIELDS for label in fields)
    return _Head(untitled, families, body_start)


def _candidates(text: str, lay: Layout) -> list[_Candidate]:
    """Every label line naming one GI service with narrative after its colon (not a layout heading), with the paragraph
    it opens. One pass over the lines."""
    lines = gi_sections._lines(text)
    section_starts = set(lay.section_starts)
    found: list[tuple[int, str, Span, int]] = []  # (line index, family, label span, body start)
    ends: list[bool] = []  # per line: whether it ends a paragraph running before it
    for i, (ls, le) in enumerate(lines):
        line = text[ls:min(le, ls + LABEL_READ + 200)]  # a label's line is read in its first characters only
        stripped = line.strip()
        label = _label_at(line) if stripped else None
        ends.append(ls in section_starts
                    or (label is not None and len(label[0]) <= 60 and gi_sections._bare_label(label[0])))
        if label is None or len(label[0]) > 70 or gi_sections._heading(text, ls, le) is not None:
            continue
        family = gi_sections._service_name_only(label[0].strip())
        if family is None:
            continue
        lead = ls + label[1]
        colon = ls + line.index(':', label[1])
        found.append((i, family, Span(lead, colon + 1, text[lead:colon + 1]), ls + label[2]))
    out = []
    for n, (i, family, label, body) in enumerate(found):
        j = i + 1
        while j < len(lines) and not ends[j]:
            j += 1
        start = lines[i][0]
        end = lines[j][0] if j < len(lines) else len(text)
        index = bisect.bisect_right(lay.section_starts, start) - 1
        out.append(_Candidate(start, end, family, label, body, max(index, 0)))
    return out


@dataclass
class _Index:
    """Positions read once per text, for the per-paragraph questions (bisection only)."""
    sentence_starts: list
    sentences: tuple
    clause_starts: list
    clauses: tuple
    announce: list  # starts of _ANNOUNCE matches
    signalled: dict  # family or '*' -> sorted starts of sentences that name it (or an examination noun) with a signal
    positive_families: dict  # family -> set of indexes of positive layout sections that name it or its instrument


def _index(text: str, lay: Layout) -> _Index:
    sentence_starts = [s for s, _ in lay.sentences]
    clause_starts = [s for s, _ in lay.clauses]
    announce = [m.start() for m in _ANNOUNCE.finditer(text)]
    signalled: dict[str, list[int]] = {}
    mentions = sorted((m.start(), m.end(), family) for family, pattern in cues.SERVICE_PATTERNS
                      for m in pattern.finditer(text))
    nouns = [m.start() for m in re.finditer(r'\b(?:examinations?|exams?|procedures?|stud(?:y|ies)|endoscop(?:y|ies)|'
                                            r'above)\b', text, FLAGS)]
    seen: set = set()
    for pos, family in [(s, f) for s, _, f in mentions] + [(p, '*') for p in nouns]:
        k = bisect.bisect_right(sentence_starts, pos) - 1
        if k < 0 or (k, family) in seen:
            continue
        seen.add((k, family))
        s, e = lay.sentences[k]
        if not s <= pos < e:
            continue
        e = min(e, s + 400)  # a sentence is read in its first 400 characters (bounded work per sentence)
        kind = lay.section_at(s).kind
        plan = kind == 'plan'
        # an impression, assessment or findings sentence about the procedure is read as the paragraph's own narrative
        # ("Polyp removed during the procedure on the cruise ship."); a plan's places are the plan's, an indication's
        # are read by N3's own allow-lists
        if _signals(text, s, e, time=not plan, narrative=kind in ('impression', 'assessment', 'findings')):
            signalled.setdefault(family, []).append(s)
    for family in signalled:
        signalled[family].sort()
    positive_families: dict[str, set] = {}
    for n, (lo, hi) in _positive_bodies(text, lay).items():  # each body read once per family (linear)
        for family, pattern in cues.SERVICE_PATTERNS:
            if pattern.search(text, lo, hi):
                positive_families.setdefault(family, set()).add(n)
        from studio.gi import services as gi_services
        for m in gi_services.INSTRUMENTS.finditer(text, lo, hi):
            named = _instrument_family(m.group(0))
            if named:
                positive_families.setdefault(named, set()).add(n)
    return _Index(sentence_starts, lay.sentences, clause_starts, lay.clauses, announce, signalled, positive_families)


@functools.lru_cache(maxsize=16)
def _document_day(text: str):
    """The document's own date of service by the context reader. No reader of this module's own (refutation cycle 2
    removed cycle 1's summary dating); kept for services._earlier_date (acts, refutation cycle 1)."""
    from studio.gi import context as gi_context  # local: the context reader is only needed here
    return gi_context.service_date_of(text)


def _positive_bodies(text: str, lay: Layout) -> dict:
    """The report's own positive (procedure, findings, technique) sections, by index, with the range of each that is
    the body's: a section the layout opens at a head title line ("Upper Endoscopy Report") counts only from where the
    head ends, and not at all when nothing but the head lies in it."""
    body = _head(text).body_start
    out = {}
    for n, section in enumerate(lay.sections):
        if section.kind not in gi_sections.POSITIVE_KINDS or _procedure_line(text, section):
            continue
        lo = max(section.start, body)
        if lo < section.end and text[lo:section.end].strip():
            out[n] = (lo, section.end)
    return out


# The walk round (2026-11-07, finding 1): a procedure line - a procedure heading whose content lies on its heading line
# alone and states nothing ("Procedures: Esophagogastroduodenoscopy with Savary dilation; colonoscopy") - is the report's
# declaration of its families (P3, _procedure_lines), never a positive section of its own: counted as one it held the very
# families it declares. A heading line that states something ("Procedure: The colonoscope was advanced ...") stays a body.
_STATES = re.compile(r'\b(?:was|were|is|are|been|had|has|have)\b', FLAGS)
PROCEDURE_LINE_READ = 400  # a heading line is read in its first characters (bounded)


def _procedure_line(text: str, section: Section) -> bool:
    if section.kind != 'procedure' or section.heading is None or ':' not in section.heading.text:
        return False
    line_end = text.find('\n', section.heading.start)
    line_end = section.end if line_end < 0 or line_end > section.end else line_end
    if text[line_end:section.end].strip():
        return False  # lines below the heading line: a body
    return not _STATES.search(text, section.heading.start, min(line_end, section.heading.start + PROCEDURE_LINE_READ))


def _any_between(sorted_starts: list, lo: int, hi: int) -> bool:
    k = bisect.bisect_left(sorted_starts, lo)
    return k < len(sorted_starts) and sorted_starts[k] < hi


def _procedure_lines(text: str, lay: Layout) -> tuple[frozenset, bool]:
    """(the families the report's procedure sections' heading lines name, whether one of those lines names a family with
    another time, place, agent or source on it)."""
    families, doubted = set(), False
    for section in lay.sections:
        if section.kind != 'procedure' or section.heading is None or ':' not in section.heading.text:
            continue  # a report title the layout reads as a procedure heading is the head's (P1, P3's title families)
        line_end = text.find('\n', section.heading.start)
        line_end = len(text) if line_end < 0 else line_end
        lo, hi = section.heading.start, min(line_end, section.heading.start + 400)
        named = {f for f, pattern in cues.SERVICE_PATTERNS if pattern.search(text, lo, hi)}
        if named and _signals(text, lo, hi):
            doubted = True
        families |= named
    return frozenset(families), doubted


def _family_regions(family: str) -> frozenset:
    """The anatomical regions (services.ANATOMY's) a family's instrument reaches: the services reader's own
    FAMILY_REGIONS, and for an EUS and an ERCP the upper tract and the organs each examines (a closed table: a region
    no family reaches holds, the safe side)."""
    from studio.gi import services as gi_services
    if family in gi_services.FAMILY_REGIONS:
        return frozenset(gi_services.FAMILY_REGIONS[family])
    return {'gi.eus': gi_services.UPPER | {'pancreas', 'biliary', 'node', 'liver'},
            'gi.ercp': frozenset(('esophagus', 'stomach', 'duodenum', 'biliary', 'pancreas'))}.get(family, frozenset())


def _regions_in(text: str, lo: int, hi: int) -> set:
    """The regions of the anatomy named in [lo, hi) (services.ANATOMY, first match wins as the reader reads it)."""
    from studio.gi import services as gi_services
    return {region for _, region, _, _ in gi_services._anatomy_in(text, lo, hi)}


def _tract_misfit(text: str, lay: Layout, kept: list, declared: frozenset) -> bool:
    """P3, the tract: whether the report narrates a site no family accounts for, outside its history, plan and
    indication sections - a site in a released paragraph its own family's instrument cannot reach, or a site elsewhere
    (a Findings line, an Impression) that neither a released family, a family declared on a procedure line nor a family
    the title names reaches ("Upper endoscopy: The gastroscope was advanced ..." then "Findings: A 9 mm sigmoid colon
    polyp was removed with a cold snare."). Such a report's labels do not account for its narrative, so nothing in it is
    released. Linear: one anatomy pass over the paragraphs and one over the other sections."""
    reach = set()
    for c in kept:
        own = _family_regions(c.family)
        if _regions_in(text, c.start, c.end) - own:
            return True
        reach |= own
    for family in declared:
        reach |= _family_regions(family)
    starts = [c.start for c in kept]
    for section in lay.sections:
        if section.kind in ('history', 'plan', 'indication') or section.heading is None:
            continue
        pos, i = section.start, max(bisect.bisect_right(starts, section.start) - 1, 0)
        while pos < section.end:  # the section's text outside the released paragraphs, gap by gap
            while i < len(kept) and kept[i].end <= pos:
                i += 1
            if i < len(kept) and kept[i].start <= pos:
                pos = kept[i].end
                continue
            stop = min(section.end, kept[i].start if i < len(kept) else section.end)
            if _regions_in(text, pos, stop) - reach:
                return True
            pos = stop
    return False


# P2 (the walk round, 2026-11-07, finding 1; the approach changed after its refutation): the installed rule - the label
# line's first sentence opens with the scope's own course, after at most an allow-listed frame of today's steps (_FRAME,
# now with informed consent and a time-out) - with one closed extension: the course may follow at most
# PREPARATION_SENTENCES opening sentences, each one of the two preparation statements reports write before the
# instrument goes in (_PREPARATION: the patient's position, a digital rectal examination). The round's first form took
# any frame of 160 characters and any two opening sentences naming no service or instrument; its refutation released a
# hedged course ("It is unclear whether the colonoscope was advanced to the cecum ..."), a denial ("Colonoscopy: Not
# performed.") and another time ("The next year, ..."). Nothing in the release reads status, so it admits only shapes
# that state none; anything else refuses, as installed.
PREPARATION_SENTENCES = 2
_PREPARATION = re.compile(
    r'[ \t\n]*+(?:'
    r'(?:the[ \t\n]++)?patient[ \t\n]++was[ \t\n]++(?:placed|positioned|turned)[ \t\n]++(?:in|into|to|on)[ \t\n]++'
    r'(?:(?:the|a|his|her)[ \t\n]++)?(?:(?:left|right)[ \t\n]++lateral(?:[ \t\n]++decubitus)?|supine|prone)'
    r'(?:[ \t\n]++position)?'
    r'|(?:(?:a|the)[ \t\n]++)?digital[ \t\n]++rectal[ \t\n]++exam(?:ination)?[ \t\n]++was[ \t\n]++'
    r'(?:performed|done|normal|unremarkable)(?:[ \t\n]++and[ \t\n]++was[ \t\n]++(?:normal|unremarkable))?'
    r')[ \t\n]*+\.[ \t\n]*+', FLAGS)


def _own_course(text: str, lo: int, hi: int, family: str) -> Optional[bool]:
    """Whether the sentence [lo, hi) opens (after its own whitespace) with the label's scope's own course (True), with
    another family's (False), or with no course (None) - the installed P2 shape, at the sentence's start."""
    lo += len(text[lo:hi]) - len(text[lo:hi].lstrip())
    m = _course_start().match(text, lo, hi)
    named = _instrument_family(m.group('instrument')) if m is not None else ''
    if named:
        return named == family
    # refutation cycle 1: a generic instrument (a bare "endoscope", "scope") - the tract its course names decides
    g = _generic_course_start().match(text, lo, hi)
    if g is not None:
        return bool(_TRACT_OF.get(family)) and _course_tract(text, g.end(), hi) == _TRACT_OF[family]
    return None


def _first_sentence_ok(text: str, c: _Candidate, ix: _Index) -> bool:
    """P2: the label line starts a sentence of its own, and the paragraph narrates the scope's own course with the label's
    family's instrument - in its first sentence from the colon on, or after at most PREPARATION_SENTENCES preparation
    statements (_PREPARATION)."""
    k = bisect.bisect_right(ix.sentence_starts, c.body) - 1
    if k < 0:
        return False
    s, e = ix.sentences[k]
    if not s <= c.body < e or s < c.start:
        return False  # the layout runs the label line on from the line above: a sentence's continuation, no label
    for step in range(PREPARATION_SENTENCES + 1):
        if k + step >= len(ix.sentences):
            return False
        lo, hi = ix.sentences[k + step]
        lo, hi = (c.body if step == 0 else lo), min(hi, c.end)
        if lo >= hi:
            return False
        found = _own_course(text, lo, hi, c.family)
        if found is not None:
            return found
        if not _PREPARATION.fullmatch(text, lo, hi):
            return False  # neither the course nor a preparation statement: refused, as installed
    return False


def _paragraph_holds(text: str, c: _Candidate, ix: _Index, frames: tuple = (), open_world: bool = True) -> bool:
    """N1: another time, place, agent or source anywhere in the paragraph, an examination subject saying what the
    allow-list does not, or another family's service named in it outside its frame of today's steps (the derived layout
    reads the paragraph as the label's procedure section, which would read that service as performed too: "Sigmoidoscopy
    showed diverticula." inside a colonoscopy paragraph). Linear in the paragraph. ``open_world`` False: every reading
    but the two open-world ones (_signals), for the corroborated release."""
    if _signals(text, c.start, c.end, narrative=True, open_world=open_world):
        return True
    for family, pattern in cues.SERVICE_PATTERNS:
        if family == c.family:
            continue
        for m in pattern.finditer(text, c.body, c.end):
            if not any(lo <= m.start() < hi for lo, hi in frames):
                return True
    if c.family != 'gi.flex_sig' and cues.FS_ABBREVIATION.search(text, c.body, c.end):
        return True
    # refutation cycle 3 (parity C3-4): another family's instrument anywhere in the paragraph ("Upper endoscopy: ... The
    # gastroscope was withdrawn. The colonoscope was then introduced. A 6 mm sessile polyp was removed ...") - the
    # derived layout would bind that examination's site-less acts to the label's family, which its heading twin does not
    from studio.gi import services as gi_services  # local: services is the instrument mapping's owner
    for m in gi_services.INSTRUMENTS.finditer(text, c.body, c.end):
        family = _instrument_family(m.group(0))
        if family and family != c.family:
            return True
    lo = bisect.bisect_left(ix.sentence_starts, c.body)
    first = bisect.bisect_right(ix.sentence_starts, c.body) - 1
    for k in range(max(lo, first + 1), len(ix.sentences)):
        s, e = ix.sentences[k]
        if s >= c.end:
            break
        e = min(e, c.end)
        if _exam_subject_holds(text, s, e, sentence_start=True):
            return True
        if _EXAM_MENTION.search(text, s, e) and not _EXAM_TOLERATED.match(text, s, e) \
                and not (_EXAM_SUBJECT.match(text, s, e) and not _exam_subject_holds(text, s, e, sentence_start=True)):
            return True  # the examination named as anything but an allow-listed subject or the tolerated object
    for k in range(bisect.bisect_left(ix.clause_starts, c.body), len(ix.clauses)):
        s, e = ix.clauses[k]
        if s >= c.end:
            break
        if s > c.body and _exam_subject_holds(text, s, min(e, c.end), sentence_start=False):
            return True
    return False


def _announced(text: str, lay: Layout, c: _Candidate, first: _Candidate, ix: _Index) -> bool:
    """N3: the containing section's own text before its first labelled paragraph ([section start, first's start))
    announces what follows, names the family or an examination noun with a hold signal, or ends on an introducing
    line."""
    section = lay.sections[c.section]
    lo, hi = section.start, first.start
    if _any_between(ix.announce, lo, hi):
        return True
    from studio.gi import detect  # local: detect imports this module
    if section.kind == 'indication' and _SOURCE_SIGNAL.search(text, lo, hi):
        return True  # a record, a report, a copy ... named in the indication
    # Completion repair (integration, 2026-11-06): an indication whose every mention of the family is an earlier occasion
    # its own clause dates before the service date ("Surveillance; history of adenomatous polyps on colonoscopy in
    # 2022.", "Personal history of colon polyps (last colonoscopy 2022).") names that occasion as history, which by its
    # date is not today's account; the labelled paragraph after it, with no other time, place, agent or back-reference
    # of its own (N1, N2) and announced by nothing (the announcement, introducing-line and run-on checks below still
    # apply), is read as it is read under a "Procedure:" heading - today's. The base read the heading form so; the
    # labelled form was held. An undated mention ("Hx colonoscopy.", "Follow-up after colonoscopy.", "Review of
    # colonoscopy.") still holds, as builder R1 pinned it.
    dated_history = section.kind == 'indication' and detect.dated_earlier_occasions_only(text, c.family, lo, hi)
    if section.kind == 'indication' and not dated_history and _unlisted_family_mention(text, c.family, lo, hi, ix):
        return True  # the family named outside the allow-list
    if section.kind == 'indication' and not dated_history and detect.named_as_another_occasion(text, c.family, lo, hi):
        # an indication naming another occasion of the family ("She had a colonoscopy", "the index colonoscopy", "Her
        # last colonoscopy", "underwent a colonoscopy"): its account may be that occasion's. A positive section's
        # procedure line naming the family is the report's declaration (P3 reads its other time, place, agent, source)
        return True
    if _any_between(ix.signalled.get('*', []), lo, hi):
        return True
    for k in range(bisect.bisect_left(ix.signalled.get(c.family, []), lo), len(ix.signalled.get(c.family, []))):
        if dated_history:
            break  # each of the family's signalled sentences here is one of those dated earlier occasions
        s = ix.signalled[c.family][k]
        if s >= hi:
            break
        e = ix.sentences[bisect.bisect_right(ix.sentence_starts, s) - 1][1]
        if not detect.past_negation_only(text, s, e):
            return True  # the family named with a hold signal ("prior", a year ...), never as "no prior colonoscopy"
    before = text[lo:hi].rstrip()
    if before.endswith(':'):
        return True  # a line that introduces what follows ("Reason for referral:", "Her 2019 study:")
    line = before[before.rfind('\n') + 1:].strip()
    if line and line[-1] not in '.!?)"\'':
        # an unterminated last line may run on into the label ("Indications: Surveillance after an outside" then
        # "Colonoscopy: ..."): it holds when it ends on a function word or a determiner's phrase, or states a hold
        # signal of its own (sections' closed class of the words a sentence cannot end on)
        words = re.findall(r"[A-Za-z][A-Za-z'/-]*", line)
        last = words[-1].lower() if words else ''
        if last in gi_sections._WRAP_WORDS or last in gi_sections._WRAP_WORDS_LOWER \
                or (len(words) >= 2 and words[-2].lower() in _DETERMINERS) \
                or _signals(line, 0, len(line)):
            return True
    return False


def _unlisted_family_mention(text: str, family: str, lo: int, hi: int, ix: _Index) -> bool:
    """N3: whether the family's name occurs in [lo, hi) other than in a sentence of consent or discussion, qualified by
    an intent, or followed by its reason (the allow-list above). Bounded: each mention's own sentence, at most 400
    characters of it, and 40 characters before it."""
    from studio.gi import detect  # local: detect imports this module
    pattern = dict(cues.SERVICE_PATTERNS)[family]
    for m in pattern.finditer(text, lo, hi):
        k = bisect.bisect_right(ix.sentence_starts, m.start()) - 1
        s, e = ix.sentences[k] if k >= 0 else (lo, hi)
        if _CONSENT_SENTENCE.search(text, s, min(e, s + 400)):
            continue
        if detect.past_negation_only(text, m.start(), m.end()):
            continue  # "no prior colonoscopy": it denies another occasion
        if _INTENT_BEFORE.search(text, max(s, m.start() - 40), m.start()) or _REASON_AFTER.match(text, m.end(), e):
            continue
        return True
    return False


def _referred_back(c: _Candidate, ix: _Index) -> bool:
    """N2: a later sentence naming the family, an examination noun or 'above' with a hold signal."""
    return any(_any_between(ix.signalled.get(key, []), c.end, 1 << 62) for key in (c.family, '*'))


_SUMMARY_KINDS = ('impression', 'assessment', 'plan')


def _stray_mentions(text: str, lay: Layout, candidates: list) -> dict:
    """N2: per family, the sorted starts of the mentions of its name outside every labelled paragraph candidate and
    outside the report's summary sections (an impression, an assessment, a plan restate or plan the report's services):
    a later one names the family again in the report's own text ("Note: this colonoscopy is another patient's."), so
    the paragraph may be another occasion's account. One pass over the mentions, bisection for the candidates."""
    starts = [c.start for c in candidates]
    found: dict[str, list[int]] = {}
    for family, pattern in cues.SERVICE_PATTERNS:
        for m in pattern.finditer(text):
            k = bisect.bisect_right(starts, m.start()) - 1
            if k >= 0 and candidates[k].start <= m.start() < candidates[k].end:
                continue
            if lay.section_at(m.start()).kind in _SUMMARY_KINDS:
                continue
            found.setdefault(family, []).append(m.start())
    for family in found:
        found[family].sort()
    return found


FRAME_REACH = 600  # characters after a candidate's colon its first-sentence frame and course are read in, at most


def _frame_end(c: _Candidate, sentence_end: int) -> int:
    """Where a candidate's frame read stops (refutation cycle 3, parity C3-5): its first sentence's end, never past the
    candidate's own end nor FRAME_REACH after its colon - soft-wrapped label lines run into one layout sentence, and
    each candidate had read to that sentence's end, quadratic in the text (a 73 KB paste took 67 s). A frame cut short
    is only a frame not found: another family's mention there is then not excused (the safe side)."""
    return min(sentence_end, c.end, c.body + FRAME_REACH)


def _framed_course(text: str, c: _Candidate, e: int) -> Optional[re.Match]:
    """The candidate's first-sentence course from its colon to ``e``, read for its frame of today's steps: the named
    instrument's course shape (_course_start); else a generic instrument's course that P2 accepts by its tract
    (refutation cycle 2, S8: "After the upper endoscopy, the scope was introduced through the anus ..." frames today's
    sequence as "After the upper endoscopy, the colonoscope ..." does, and its heading twin reads so)."""
    m = _course_start().match(text, c.body, e)
    if m is None and _TRACT_OF.get(c.family):
        g = _generic_course_start().match(text, c.body, e)
        if g is not None and _course_tract(text, g.end(), e) == _TRACT_OF[c.family]:
            return g
    return m


def _frames(text: str, candidates: list, ix: _Index) -> tuple:
    """The spans of the candidates' first-sentence frames of today's steps (P2's allow-list: "After the upper
    endoscopy, the colonoscope ..."): a mention of another family there is today's sequence, never another occasion."""
    spans = []
    for c in candidates:
        k = bisect.bisect_right(ix.sentence_starts, c.body) - 1
        if k < 0:
            continue
        m = _framed_course(text, c, _frame_end(c, ix.sentences[k][1]))
        if m is not None and m.group('frame'):
            spans.append((m.start('frame'), m.end('frame')))
    return tuple(spans)


def _frames_released(text: str, candidates: list, out: list, ix: _Index) -> list:
    """P2, after the decisions: a released paragraph whose first-sentence frame names another family's procedure
    ("After the upper endoscopy, the colonoscope ...") stays released only while that family's own labelled paragraph
    is released too: the frame tells today's sequence only beside today's account of the procedure it names. Repeated
    until nothing changes (each pass can only hold more; at most one pass per candidate)."""
    named = {}
    for n, c in enumerate(candidates):
        k = bisect.bisect_right(ix.sentence_starts, c.body) - 1
        m = _framed_course(text, c, _frame_end(c, ix.sentences[k][1])) if k >= 0 else None
        if m is not None and m.group('frame'):
            frame = m.group('frame')
            named[n] = {f for f, pattern in cues.SERVICE_PATTERNS if pattern.search(frame)} - {c.family}
    for _ in range(len(candidates)):
        released_families = {c.family for c, (_, why) in zip(candidates, out) if not why}
        changed = False
        for n, families in named.items():
            if not out[n][1] and families - released_families:
                out[n] = (out[n][0], "P2: its frame names a procedure whose own paragraph is not released")
                changed = True
        if not changed:
            break
    return out


def _later_occasion(text: str, c: _Candidate, frames: tuple) -> bool:
    """N2: whether a later mention of the family, anywhere after the paragraph, reads as another occasion of it by
    routing's own reading (detect.named_as_another_occasion: "Impression: No colonoscopy was performed today.", "The
    colonoscopy above was done last year."), a later paragraph's frame of today's steps apart. One reading per mention,
    memoised in the frozen analysis."""
    from studio.gi import detect  # local: detect imports this module
    return detect.named_as_another_occasion(text, c.family, c.end, len(text), skip=frames, doubt=True)


def _structure_resumes(text: str, lay: Layout, c: _Candidate, candidate_starts: set) -> bool:
    """N2: whether the report's own structure resumes where the paragraph ends - its next non-blank line opens a layout
    section with a heading ("Impression:", "Findings:"), is another labelled paragraph's label line, is one of the
    report's own fields (the layout's closed list, sections._S2_REPORT_FIELD: "Withdrawal time:", "Extent:", "BBPS:"),
    or there is no further text. A free line after it ("Note: not from this visit.", a comment, a signature) may speak of it, so the
    paragraph is held."""
    m = re.compile(r'\S').search(text, c.end)
    if m is None:
        return True
    line_start = text.rfind('\n', 0, m.start()) + 1
    section = lay.section_at(line_start)
    line_end = text.find('\n', line_start)
    line = text[line_start:len(text) if line_end < 0 else min(line_end, line_start + 200)]
    return line_start in candidate_starts or (section.start == line_start and section.heading is not None) \
        or bool(gi_sections._S2_REPORT_FIELD.match(line))  # the report's own field ("Withdrawal time: 8 minutes.")


def _heading_has_content(text: str, section: Section) -> bool:
    if section.heading is None:
        return False
    line_end = text.find('\n', section.heading.end)
    line_end = len(text) if line_end < 0 else line_end
    return bool(text[section.heading.end:line_end].strip())


# --- The corroborated release (the structure round, 2026-11-08, U18; the module docstring) ------------------------------
# What a corroborating statement - a procedure line's item, an impression or assessment sentence - may not carry: the
# services reader's own tables of a statement that is not a plain one (negation, hedge, cancellation, plan, history,
# incompleteness, a hypothetical, a failure frame) and routing's act failure words (cues.ACT_FAILURE_WORDS, the words both
# readers read as an act's own failure). Closed: they are those readers' tables, reused; any of them doubts the statement,
# which then corroborates nothing (the safe side).
CORROBORATION_READ = 400  # a corroborating sentence is read in its first characters, as _index reads one
# Bounds (u18c cycle 2; the cycle-1 REGRESS lens's cost finding): the corroborated release is a reading of an ordinary
# procedure report, and every bound below only withholds a release, so the installed reading stands (the safe side). A
# document longer than CORROBORATED_DOCUMENT characters, or a paragraph longer than CORROBORATED_PARAGRAPH, is never read
# again (the installed gates' whole-document readers - N2, N3, the tract rule - and routing's reading of a released
# paragraph are then never run on its behalf); a summary is read in its first SUMMARY_READ characters, the procedure
# lines in their first PROCEDURE_LINES_READ. So its work is bounded whatever the text's size.
CORROBORATED_DOCUMENT = 40000
CORROBORATED_PARAGRAPH = 6000
SUMMARY_READ = 8000
PROCEDURE_LINES_READ = 12
# Bounds on the guard's own work (integration, 2026-11-08; u18d's REGRESS lens, cost finding 0). The guard reads every
# sentence and clause that meets a released paragraph with four span readers on each of its two readings, and
# services.passage_readings scans the document's sentences from its start on every call, so the work grows with the
# product of the two: five labelled paragraphs of short sentences inside CORROBORATED_DOCUMENT took 15 s per stage (22x
# the installed reading); the profile puts it in the spans read (5,708 passage readings, 11,416 status readings). Where
# the released paragraphs meet more than GUARD_SPANS sentences and clauses, the guard does not run: every corroborated
# release is withdrawn and the installed reading stands (the safe side, like every bound here). Counted on the installed
# layout. Measured: the largest released case of the design's battery, the walked member c4a, meets 50 (the battery's
# 99th percentile, 22); one paragraph of ordinary sentences at CORROBORATED_PARAGRAPH meets about 250 (the module's own
# long-paragraph pin, 206). The guard's work at the bound stays within 1.6x of the installed reading.
GUARD_SPANS = 300


@functools.lru_cache(maxsize=1)
def _corroboration_doubt() -> tuple:
    from studio.gi import services as gi_services  # local: the services reader's own tables
    failure = re.compile(r'\b(?:' + '|'.join(re.escape(word) for word in cues.ACT_FAILURE_WORDS) + r')\b', FLAGS)
    return (gi_services.NEGATION_WORD, re.compile(gi_services.NEG_CONTRACTION, FLAGS), gi_services.HEDGE_WORDS,
            gi_services.CANCEL_WORDS, gi_services.PLAN_WORDS, gi_services.HISTORY_WORDS, gi_services.INCOMPLETE_WORDS,
            gi_services.HYPOTHETICAL, re.compile(gi_services.FAILURE_FRAME.pattern.rstrip('$'), FLAGS), failure)


def _doubted(text: str, lo: int, hi: int) -> bool:
    """Whether the statement [lo, hi) is not a plain one by the services reader's tables (_corroboration_doubt)."""
    return any(pattern.search(text, lo, hi) for pattern in _corroboration_doubt())


def _act_kinds(text: str, lo: int, hi: int, denials: bool = False, fragments: bool = False) -> frozenset:
    """The act kinds (services.ACTS) named in [lo, hi) (_act_mentions). ``fragments`` (a corroborating statement): a
    fragment participle names every kind the services reader groups under it (services.FRAGMENT_KINDS: "site tattooed"
    restates the tattoo and its injection)."""
    from studio.gi import services as gi_services
    kinds = {kind for kind, _, _ in _act_mentions(text, lo, hi, denials)}
    for word, grouped in (gi_services.FRAGMENT_KINDS.items() if fragments else ()):
        if re.compile(r'\b' + word + r'\b', FLAGS).search(text, lo, hi):
            kinds.update(grouped)
    return frozenset(kinds)


def _act_mentions(text: str, lo: int, hi: int, denials: bool = False) -> list:
    """(kind, start, end) of each act mention (services.ACTS) in [lo, hi), each span claimed by the first kind that
    matches it, as the services reader claims its text ("hot biopsy forceps" is a hot biopsy, not also a biopsy).
    ``denials`` (a paragraph's own acts): a mention that services.NOT_VERB's own "not <participle>" ends on ("it was not
    sampled") is no act stated. Linear: one pass of each pattern, a claimed-character map."""
    from studio.gi import services as gi_services
    claimed = bytearray(max(hi - lo, 0))
    found = []
    for kind, pattern in gi_services.ACTS:
        for m in pattern.finditer(text, lo, hi):
            s, e = m.start() - lo, m.end() - lo
            if claimed.find(1, s, e) >= 0:
                continue
            claimed[s:e] = b'\x01' * (e - s)
            if denials:
                lead = _NOT_BEFORE.search(text, max(lo, m.start() - 12), m.start())
                denial = gi_services.NOT_VERB.match(text, lead.start(), m.end()) if lead is not None else None
                if denial is not None and denial.end() == m.end():
                    continue  # "it was not sampled": denied in its own words
            found.append((kind, m.start(), m.end()))
    return found


_NOT_BEFORE = re.compile(r'\bnot[ \t\n]++\Z', FLAGS)  # the "not" of NOT_VERB's own "not <participle>" before a mention
_ITEM_MARK = re.compile(r'[;,]')


def _listed_acts(text: str, lay: Layout) -> dict:
    """C1: family -> the act kinds the report's procedure lines list for it. A procedure line (_procedure_lines' lines,
    each read in its first PROCEDURE_LINE_READ characters) is read item by item (cut at ';' and ','): an item naming one
    family lists its acts for that family, and so does each item after it that names none ("Colonoscopy with cold snare
    polypectomy, biopsies and tattoo"); an item naming two families lists nothing for either, and an item that is not a
    plain statement (_doubted: "colonoscopy without polypectomy", "planned polypectomy") lists nothing and ends the run.
    Bounded: the first PROCEDURE_LINES_READ lines, each in its first PROCEDURE_LINE_READ characters."""
    listed: dict[str, set] = {}
    lines = 0
    for section in lay.sections:
        if section.kind != 'procedure' or section.heading is None or ':' not in section.heading.text:
            continue
        lines += 1
        if lines > PROCEDURE_LINES_READ:
            break  # a later line lists nothing (the safe side: fewer acts declared, fewer releases)
        line_end = text.find('\n', section.heading.start)
        line_end = len(text) if line_end < 0 else line_end
        lo, hi = section.heading.start, min(line_end, section.heading.start + PROCEDURE_LINE_READ)
        family, pos = None, lo
        for cut in itertools.chain((m.start() for m in _ITEM_MARK.finditer(text, lo, hi)), (hi,)):
            a, b, pos = pos, cut, cut + 1
            named = {f for f, pattern in cues.SERVICE_PATTERNS if pattern.search(text, a, b)}
            if len(named) > 1 or _doubted(text, a, b):
                family = None
                continue
            family = next(iter(named)) if named else family
            if family is not None:
                listed.setdefault(family, set()).update(_act_kinds(text, a, b, fragments=True))
    return listed


def _bound_families(text: str, lo: int, hi: int, families: frozenset, sole: Optional[str]) -> set:
    """The families of ``families`` a summary statement [lo, hi) is about: it names no other family's service or
    instrument, and the sites it names (services.ANATOMY's regions) all lie in the family's reach - or it names none and
    names the family's service or instrument, or the report declares that family alone (``sole``)."""
    named = {f for f, pattern in cues.SERVICE_PATTERNS if pattern.search(text, lo, hi)}
    from studio.gi import services as gi_services
    named |= {_instrument_family(m.group(0)) for m in gi_services.INSTRUMENTS.finditer(text, lo, hi)} - {''}
    regions = _regions_in(text, lo, hi)
    out = set()
    for family in families:
        if named - {family}:
            continue
        if regions:
            if regions <= _family_regions(family):
                out.add(family)
        elif family in named or family == sole:
            out.add(family)
    return out


def _restated_acts(text: str, lay: Layout, families: frozenset, sole: Optional[str]) -> dict:
    """C2: family -> the act kinds the report's summary restates for it as today's: each sentence of an impression or
    assessment section (read in its first CORROBORATION_READ characters) that states no hold signal by N1's own
    narrative reading (_signals) and is a plain statement (_doubted) restates its act kinds for the families it is bound
    to (_bound_families); a sentence bound to none (it names two families' sites) is bound clause by clause. Bounded:
    the summary's first SUMMARY_READ characters of sentences read (a restatement after them restates nothing: the safe
    side)."""
    restated: dict[str, set] = {}
    sentence_starts: Optional[list] = None
    clause_starts: list = []
    read = 0
    for section in lay.sections:
        if section.kind not in ('impression', 'assessment'):
            continue
        if sentence_starts is None:
            sentence_starts, clause_starts = [s for s, _ in lay.sentences], [s for s, _ in lay.clauses]
        k = bisect.bisect_left(sentence_starts, section.start)
        for s, e in lay.sentences[k:]:
            if s >= section.end or read >= SUMMARY_READ:
                break
            e = min(e, section.end, s + CORROBORATION_READ)
            read += e - s
            if _signals(text, s, e, narrative=True) or _doubted(text, s, e):
                continue
            kinds = _act_kinds(text, s, e, fragments=True)
            if not kinds:
                continue
            bound = _bound_families(text, s, e, families, sole)
            if bound:
                for family in bound:
                    restated.setdefault(family, set()).update(kinds)
                continue
            j = bisect.bisect_left(clause_starts, s)
            for cs, ce in lay.clauses[j:]:
                if cs >= e:
                    break
                ce = min(ce, e)
                for family in _bound_families(text, cs, ce, families, sole):
                    restated.setdefault(family, set()).update(_act_kinds(text, cs, ce, fragments=True))
    return restated


def _another_occasion_before(text: str, lay: Layout, c: _Candidate) -> bool:
    """C4: whether a section before the paragraph's own (never a positive one: the report's own declarations) names
    another occasion of its family by routing's own reading (detect.named_as_another_occasion), other than an earlier
    occasion its own clause dates (detect.dated_earlier_occasions_only, N3's dated-history reading)."""
    from studio.gi import detect  # local: detect imports this module
    for section in lay.sections[:c.section]:
        if section.kind in gi_sections.POSITIVE_KINDS or section.end <= section.start:
            continue
        if detect.named_as_another_occasion(text, c.family, section.start, section.end) \
                and not detect.dated_earlier_occasions_only(text, c.family, section.start, section.end):
            return True
    return False


# Today's procedure content a sentence may state (C3): the scope by its name or generically (P2's own generic
# instrument), an act kind, or a site in the family's reach.
_SCOPE_NAMED = re.compile(r'\b(?:' + _GENERIC_INSTRUMENT + r')s?\b', FLAGS)


def _states_procedure(text: str, lo: int, hi: int, family: str) -> bool:
    """Whether the sentence [lo, hi) states today's procedure content: an instrument (services.INSTRUMENTS, or a bare
    "scope"/"endoscope"), an act kind (services.ACTS), or a site in the family's reach (services.ANATOMY's regions)."""
    from studio.gi import services as gi_services
    return bool(gi_services.INSTRUMENTS.search(text, lo, hi) or _SCOPE_NAMED.search(text, lo, hi)
                or _act_kinds(text, lo, hi) or _regions_in(text, lo, hi) & _family_regions(family))


def _paragraph_sentences(c: _Candidate, ix: _Index) -> list:
    """The paragraph's sentences (the layout's), each cut to the paragraph."""
    out = []
    for k in range(max(bisect.bisect_right(ix.sentence_starts, c.start) - 1, 0), len(ix.sentences)):
        s, e = ix.sentences[k]
        if s >= c.end:
            break
        if e > c.start:
            out.append((max(s, c.start), min(e, c.end)))
    return out


def _open_world_at(text: str, start: int, end: int):
    """The positions of N1's two open-world readings in [start, end), as N1 reads the whole paragraph: each place
    preposition whose object no allow-list anchors (_unanchored_places) and each temporal adjunct no step of today's
    anchors (_TEMPORAL_LEAD, _TODAYS_STEP)."""
    yield from _unanchored_places(text, start, end)
    for m in _TEMPORAL_LEAD.finditer(text, start, end):
        if _TODAYS_STEP.match(text, m.end(), end) is None:
            yield m.start()


def _corroborated(text: str, lay: Layout, c: _Candidate, ix: _Index, listed: dict, restated: dict) -> bool:
    """C1-C4 for one paragraph (the module docstring). C1/C2: an act kind it states is listed for its family on a
    procedure line and restated for it by the summary, and the paragraph states it in a sentence that carries no
    open-world reading (the statement the report's two others agree with is itself undoubted). C3: every act kind it
    states is listed or restated; where the paragraph has a future word, each sentence is read on its own words for a
    closed signal (one sentence's future word never exempts another's time words, as the whole paragraph's reading lets
    it; with none, the whole paragraph's closed reading already read every sentence's); and each sentence carrying an
    open-world reading states today's procedure content (_states_procedure) - a sentence that says nothing of the
    procedure ("Everything was done on the cruise ship.") can only frame the whole account, and holds - and is otherwise
    a plain statement (_doubted: the corroboration answers the open-world doubt, never a history, plan, negation, hedge
    or failure word beside it: "..., where the polyp had been removed."). C4: no section before it names an undated other
    occasion of the family. Linear in the paragraph."""
    own_listed, own_restated = listed.get(c.family, set()), restated.get(c.family, set())
    kinds = _act_kinds(text, c.body, c.end, denials=True)
    triple = kinds & own_listed & own_restated
    if not triple:
        return False  # C1/C2: no act the report itself states three times
    if kinds - own_listed - own_restated:
        return False  # C3: an act the report does not itself declare as today's
    sentences = _paragraph_sentences(c, ix)
    if _FUTURE_CLAUSE.search(text, c.start, c.end) is not None \
            and any(_signals(text, s, e, narrative=True, open_world=False) for s, e in sentences):
        return False  # C3: a closed signal read on a sentence's own words
    starts = [s for s, _ in sentences]
    doubtful = {bisect.bisect_right(starts, pos) - 1 for pos in _open_world_at(text, c.start, c.end)}
    undoubted = False
    predicated: dict = {}  # (clause start, end) -> whether it carries an act predicate: each clause searched once
    for k, (s, e) in enumerate(sentences):
        if k in doubtful:
            if not _states_procedure(text, s, e, c.family) or _doubted(text, s, e):
                return False  # C3: an open-world adjunct in a sentence that only frames the account, or doubts more
        elif not undoubted and _plain_act_statement(text, max(s, c.body), e, triple, ix, predicated):
            undoubted = True
    return undoubted and not _another_occasion_before(text, lay, c)  # C1/C2, C4


def _plain_act_statement(text: str, lo: int, hi: int, kinds: frozenset, ix: _Index, predicated: dict) -> bool:
    """C1/C2: whether the sentence [lo, hi) states one of ``kinds`` done, plainly - as the procedure line and the
    summary must: no word of the services reader's doubt tables in it (_doubted: "No polyp was removed ...", "...
    was attempted but failed"), and the act's own clause carries an act predicate (services.ACT_VERB or
    BARE_PARTICIPLE: "was removed", "were taken"), so a mention that only names the act ("the cold snare polypectomy
    scar was clean", "a cold snare was opened, and the polyp was left in place") states none.
    Cost (u18c cycle 2; the cycle-1 REGRESS lens): the predicate is searched once per clause, never once per mention -
    ``predicated`` memoises each clause's answer for the paragraph, so a clause holding many act mentions (a long
    comma-joined list, which the layout keeps as one clause) costs its length once: linear in the paragraph."""
    from studio.gi import services as gi_services
    if _doubted(text, lo, hi):
        return False
    for kind, ms, _ in _act_mentions(text, lo, hi, denials=True):
        if kind not in kinds:
            continue
        k = bisect.bisect_right(ix.clause_starts, ms) - 1
        cs, ce = ix.clauses[k] if k >= 0 else (lo, hi)
        cs, ce = max(cs, lo), min(ce, hi)
        found = predicated.get((cs, ce))
        if found is None:
            found = predicated[(cs, ce)] = bool(gi_services.ACT_VERB.search(text, cs, ce)
                                                or gi_services.BARE_PARTICIPLE.search(text, cs, ce))
        if found:
            return True
    return False


def _held_later(text: str, lay: Layout, c: _Candidate, ix: _Index, stray: dict, frames: tuple,
                candidate_starts: set) -> bool:
    """N2 as installed: a later sentence refers back to the paragraph, its family is named again outside the report's
    summary, a later mention reads as another occasion, or the report's own structure does not resume after it."""
    return _referred_back(c, ix) or _any_between(stray.get(c.family, []), c.end, 1 << 62) \
        or _later_occasion(text, c, frames) or not _structure_resumes(text, lay, c, candidate_starts)


HELD_BY_N1 = 'N1: the paragraph states another time, place, agent or source'
HELD_AFTER_HELD = 'P4: it follows a labelled paragraph that is not released'
TRACT_MISFIT = 'P3: the report narrates a site no labelled or declared family reaches'


def decisions(text: str) -> tuple[tuple[LabelledParagraph, str], ...]:
    """Every labelled paragraph candidate of the text, in order, with '' when it is released or the first condition
    that holds it ('P1' to 'P4', 'N1' to 'N3', with a word of detail). For the tests and the probes; ``released`` reads
    it. The installed conditions decide first; the corroborated release (the module docstring) then reads only the
    paragraphs they hold by N1 or by P4's cascade, and a paragraph it does not release keeps its installed reason; a
    corroborated release stands only where the computed heading twin reads as the document does (_twin_parity).
    Which decisions a text reads is its reading's mode (_mode): a _Reading carries its own, U14's direct-reach twin
    reads the installed ones, every other text the guarded ones; each mode has caches of its own."""
    if not isinstance(text, str) or ':' not in text:
        return ()
    return _decided(text, _mode(text))


def _decided(text: str, mode: str) -> tuple:
    if mode == _CARRIED:
        return text.carried
    if mode == _INSTALLED:
        return _installed_state(text)[0]
    return _guarded_decisions(text)


@functools.lru_cache(maxsize=16)
def _installed_state(text: str) -> tuple:
    """(the installed conditions' decisions, what the corroborated release reads of the text beside them - None when
    there is nothing it could read): the labelled release exactly as installed. A pure function of the text, so every
    reading mode shares it."""
    if not isinstance(text, str) or ':' not in text:
        return (), None
    lay = gi_sections.layout(text)
    candidates = _candidates(text, lay)
    if not candidates:
        return (), None
    head = _head(text)
    if not head.procedure_report:  # P1: every candidate keeps the base reading
        return tuple((LabelledParagraph(c.start, c.end, c.family, c.label), 'P1: not a procedure report')
                     for c in candidates), None
    ix = _index(text, lay)
    declared, declared_doubted = _procedure_lines(text, lay)
    per_family: dict[str, int] = {}
    for c in candidates:
        per_family[c.family] = per_family.get(c.family, 0) + 1
    positive = set(_positive_bodies(text, lay))
    stray = _stray_mentions(text, lay, candidates)
    frames = _frames(text, candidates, ix)
    candidate_starts = {c.start for c in candidates}
    out: list[tuple[LabelledParagraph, str]] = []
    previous: Optional[_Candidate] = None  # the candidate before this one, and whether it was released
    previous_released = False
    first_in_section: dict[int, _Candidate] = {}
    for c in candidates:
        first_in_section.setdefault(c.section, c)
        section = lay.sections[c.section]
        follows = previous is not None and previous.section == c.section and previous.end == c.start
        why = ''
        if not _first_sentence_ok(text, c, ix):
            why = 'P2: the first sentence is not the scope\'s own course'
        elif head.title_families and c.family not in head.title_families:
            why = 'P3: the title names another family'
        elif declared and c.family not in declared:
            why = 'P3: the procedure line names another family'
        elif declared and declared_doubted:
            why = 'P3: the procedure line states another time, place, agent or source'
        elif per_family[c.family] > 1:
            why = 'P3: a second labelled paragraph of the family'
        elif ix.positive_families.get(c.family, set()) - {c.section}:
            why = 'P3: the family has a procedure section of its own'
        elif positive - {c.section} and c.family not in declared:
            why = 'P3: the report has a procedure section of its own that no procedure line declares the family for'
        elif previous is not None and previous.section == c.section and not previous_released:
            why = HELD_AFTER_HELD
        elif section.kind not in gi_sections.POSITIVE_KINDS and not (
                section.kind == 'indication' and (_heading_has_content(text, section) or (follows and previous_released))):
            why = f'P4: it stands in a {section.kind} section' if section.kind != 'indication' \
                else 'P4: an empty indication heading introduces it'
        elif _paragraph_holds(text, c, ix, frames):
            why = HELD_BY_N1
        elif _held_later(text, lay, c, ix, stray, frames, candidate_starts):
            why = 'N2: a later sentence refers back to it'
        elif _announced(text, lay, c, first_in_section[c.section], ix):
            why = 'N3: the containing section announces it'
        out.append((LabelledParagraph(c.start, c.end, c.family, c.label), why))
        previous, previous_released = c, not why
    out = _frames_released(text, candidates, out, ix)
    kept = [c for c, (_, why) in zip(candidates, out) if not why]
    if kept and _tract_misfit(text, lay, kept, declared | head.title_families):
        return tuple((p, why or TRACT_MISFIT) for p, why in out), None
    return tuple(out), (lay, head, ix, candidates, declared, stray, frames, candidate_starts)


@functools.lru_cache(maxsize=16)
def _guarded_decisions(text: str) -> tuple:
    """The decisions a text reads (decisions' guarded mode): the installed ones, and over them the corroborated
    release's candidates (_corroborated_release) where the computed heading twin reads every compared fact as the
    document reads with them (_twin_parity) - otherwise the installed ones, whole."""
    installed, read = _installed_state(text)
    if read is None or len(text) > CORROBORATED_DOCUMENT \
            or not any(why in (HELD_BY_N1, HELD_AFTER_HELD) for _, why in installed):
        return installed
    lay, head, ix, candidates, declared, stray, frames, candidate_starts = read
    listed = _listed_acts(text, lay)
    if not listed:
        return installed  # C1: no procedure line lists an act, so nothing can be corroborated
    candidate = _corroborated_release(text, lay, head, ix, candidates, installed, declared, listed, stray, frames,
                                      candidate_starts)
    if candidate is installed or not _guard_bounded(lay, candidate):
        return installed
    return candidate if _twin_parity(text, candidate) else installed


def _guard_bounded(lay, candidate: tuple) -> bool:
    """Whether the guard's work over ``candidate``'s released paragraphs stays within GUARD_SPANS, counted on the
    installed layout ``lay``."""
    regions = [(p.start, p.end) for p, why in candidate if not why]
    met = sum(1 for spans in (lay.sentences, lay.clauses) for s, e in spans
              if any(rs < e and s < re_ for rs, re_ in regions))
    return met <= GUARD_SPANS


def _p4_passes(text: str, lay: Layout, candidates: list, state: list, n: int) -> bool:
    """P4 for candidate ``n`` against the release ``state`` of the candidate before it, as the installed loop reads it:
    never after a held paragraph of its own section; in a positive section, or in an indication whose heading line
    carries content, or directly after a released paragraph of its own section."""
    c = candidates[n]
    here = candidates[n - 1] if n else None
    before = state[n - 1] if n else ''
    same = here is not None and here.section == c.section
    if same and not before:
        return False
    section = lay.sections[c.section]
    return section.kind in gi_sections.POSITIVE_KINDS or (section.kind == 'indication' and (
        _heading_has_content(text, section) or (same and here.end == c.start and bool(before))))


def _ends_as_its_twin(text: str, lay: Layout, c: _Candidate, released_starts: set) -> bool:
    """C5 (u18c cycle 2): whether the paragraph's procedure section is exactly its heading twin's - the section its
    label opens when written "PROCEDURE: <label>" on a line of its own, which runs to the next layout section or to the
    next label written as a heading. So: no layout section starts inside it, and it ends at the end of the text, at a
    line that opens a layout section with a heading ("IMPRESSION:"), or at the label line of a paragraph that is
    released too. A report field or any other line after it ("Retroflexion: ...", "Withdrawal time: ...", which N2
    accepts as the report's own structure) would lie inside the twin's procedure section and outside the paragraph:
    such a paragraph is not corroborated (the installed reading stands), so what its twin reads with the paragraph and
    what the release reads outside it can never differ. Structure only: the layout's section starts and the released
    set; bisection."""
    if _any_between(lay.section_starts, c.start + 1, c.end):
        return False
    if c.end >= len(text) or c.end in released_starts:
        return True
    section = lay.section_at(c.end)
    return section.start == c.end and section.heading is not None


TWIN_HEADING = 'PROCEDURE: '


def _twin_disagrees(text: str, candidates: list, state: list) -> set:
    """C5, computed (never predicted): the indexes of the corroborated paragraphs whose heading twin's own procedure
    section is not exactly the paragraph. The twin is the text with every released paragraph's inline label "<L>: "
    written "PROCEDURE: <L>" and a newline, every other character unchanged; its section is read by sections.layout
    itself, so a layout rule that reads a line by the section in force (a held line, a phrase line, a service line before
    a procedure heading) is the twin's own. Linear: one twin text, one layout."""
    released = sorted((c for c, how in zip(candidates, state) if how), key=lambda c: c.label.start)
    pieces, shifts, pos, delta = [], [], 0, 0
    for c in released:
        a, colon = c.label.start, c.label.end
        b = colon
        while b < len(text) and text[b] in ' \t':
            b += 1
        heading = TWIN_HEADING + text[a:colon - 1] + '\n'
        pieces += [text[pos:a], heading]
        delta += len(heading) - (b - a)
        shifts.append((a, delta))  # positions after this label move by ``delta`` in the twin
        pos = b
    twin = ''.join(pieces) + text[pos:]
    starts = [a for a, _ in shifts]

    def mapped(at: int) -> int:
        k = bisect.bisect_left(starts, at) - 1  # the labels strictly before ``at``
        return at + (shifts[k][1] if k >= 0 else 0)
    lay = gi_sections.layout(twin)
    out = set()
    for n, (c, how) in enumerate(zip(candidates, state)):
        if how != 'corroborated':
            continue
        start = mapped(c.start)
        section = lay.section_at(start)
        if section.start != start or section.kind != 'procedure' or section.end != mapped(c.end):
            out.add(n)
    return out


def _corroborated_release(text: str, lay: Layout, head: _Head, ix: _Index, candidates: list, installed: tuple,
                          declared: frozenset, listed: dict, stray: dict, frames: tuple, candidate_starts: set) -> tuple:
    """The corroborated release over the installed decisions (the module docstring). A paragraph the installed reading
    holds by N1, or by P4's cascade, is read again: P4 against the paragraphs released so far, N1 with its two
    open-world readings set aside, N2 and N3 as installed; and it is released only when it is corroborated itself
    (_corroborated) - whether N1 held it or P4's cascade did, so a paragraph after one released this way is never
    lifted by that release alone. Then, until nothing changes (each step only withdraws): the frames
    (_frames_released), P4 again against the releases that remain (a paragraph released after one that is withdrawn is
    withdrawn), C5 (_ends_as_its_twin), and once those are stable C5 on the twin's own layout (_twin_disagrees). A
    tract misfit the installed decisions did not have returns the installed
    decisions. Every corroborated release is marked (LabelledParagraph.corroborated) for services._labelled_parts, and
    no installed decision changes. Linear: each paragraph read once more, the summary and the procedure lines once."""
    families = frozenset(c.family for c in candidates)
    titled = declared | head.title_families
    sole = next(iter(titled)) if len(titled) == 1 else None
    restated: Optional[dict] = None
    state = ['installed' if not why else '' for _, why in installed]  # how each candidate is released, if it is
    out = list(installed)
    first_in_section: dict[int, _Candidate] = {}
    for n, c in enumerate(candidates):
        first_in_section.setdefault(c.section, c)
        if installed[n][1] not in (HELD_BY_N1, HELD_AFTER_HELD):
            continue
        if not _p4_passes(text, lay, candidates, state, n):
            continue  # P4 as installed, against the paragraphs released so far
        if c.end - c.start > CORROBORATED_PARAGRAPH or not listed.get(c.family):
            continue  # beyond the bound; or C1: nothing listed for the family
        if _paragraph_holds(text, c, ix, frames, open_world=False):
            continue  # N1 holds by a closed reading
        if restated is None:
            restated = _restated_acts(text, lay, families, sole)
        if not _corroborated(text, lay, c, ix, listed, restated):
            continue  # C1-C4
        if _held_later(text, lay, c, ix, stray, frames, candidate_starts) \
                or _announced(text, lay, c, first_in_section[c.section], ix):
            continue  # N2, N3 as installed (read last: they read the whole document)
        out[n] = (replace(out[n][0], corroborated=True), '')
        state[n] = 'corroborated'
    if 'corroborated' not in state:
        return installed
    for _ in range(len(candidates) + 1):
        changed = False
        for n, (_, why) in enumerate(_frames_released(text, candidates, list(out), ix)):
            if why and state[n] == 'corroborated':
                out[n], state[n], changed = installed[n], '', True
        released_starts = {c.start for c, how in zip(candidates, state) if how}
        for n, c in enumerate(candidates):
            if state[n] == 'corroborated' and not (_p4_passes(text, lay, candidates, state, n)
                                                   and _ends_as_its_twin(text, lay, c, released_starts)):
                out[n], state[n], changed = installed[n], '', True
        if not changed and 'corroborated' in state:
            for n in _twin_disagrees(text, candidates, state):  # C5 computed on the twin itself, once stable
                out[n], state[n], changed = installed[n], '', True
        if not changed:
            break
    if 'corroborated' not in state:
        return installed
    kept = [c for c, (_, why) in zip(candidates, out) if not why]
    if _tract_misfit(text, lay, kept, declared | head.title_families):
        return installed
    return tuple(out)


# --- The computed heading twin (the structure round, u18d: U18's changed approach) --------------------------------------
# The corroborated release (C1-C5 above) only PROPOSES. A corroborated release stands only where the INSTALLED readers,
# run on the document's heading twin, read every compared fact exactly as they read the document with the release; on
# any difference every corroborated release of the document is withdrawn, and it reads as installed. Parity is
# computed, never argued: corroboration's two refuted cycles reasoned that a released paragraph reads as its heading
# twin, and leaked at the readers nobody reasoned about - the services reader binding a site-less act to the label's
# family where the twin's "PROCEDURE: <L>" line binds it to none (a report declaring two families), and routing reading
# a released label against its paragraph's second sentence where the twin's heading reads only the first.
# - The twin (_HeadingTwin): the text with EVERY released paragraph's inline label "<L>: " written "PROCEDURE: <L>" and a
#   newline (TWIN_HEADING), every other character unchanged - the installed ones too, so an installed release's own
#   reader classes (its label binding) are compared as well, and a document whose installed release reads otherwise
#   than its twin keeps its installed reading.
# - Both are READ by the readers themselves, never predicted (_reading_facts): the twin with its installed decisions (no
#   corroboration inside it), the document with the candidate decisions. Each is a _Reading: a text equal only to
#   itself, so no cache keyed by a text shares an entry between the guard's readings and the real one, and it carries
#   its decisions, so nothing is decided again inside the guard (no recursion). A reader that asks for any other text's
#   decisions while the guard reads (a copy of the document) fails it closed (_GuardRead); U14's direct-reach twin is
#   routed by the installed release in every reading (_mode). The guard runs once per text (the decisions are cached):
#   the twin is read at most once per document with a corroborated candidate.
# - What is compared (_reading_facts), every span in CONTENT coordinates - the characters both texts write alike: the
#   label's colon and the blanks after it, and the twin's "PROCEDURE: " and newline, are no content; the label's words
#   are, in both:
#   1. the clinical layout (routing's, the engine's and reconcile's section reads): each section's kind over the text,
#      every sentence and every clause;
#   2. routing (detect.route): the document kind; each family's status, missing facts, facts (name, value, origin,
#      note, evidence) and mentions (span, sentence, section kind, status, cues) - the label's own mention included;
#   3. routing's analysis: the family attributed to each sentence, each family's document-level adjustment, the
#      reading of each reference and of each E/M mention;
#   4. the span readers validation reads a code's evidence with - detect.status_for_span (also with U24's back
#      reading), detect.own_status_for_span and services.passage_readings - on every sentence and every clause of the
#      released paragraphs, and on each label's own words: the spans whose section and sentence the release changes;
#   5. the documented services (services.build with that routing): every service (family, kind, status, completion,
#      extent, intent, date, clinician, setting, role, evidence, completion evidence, cues, uncertainty, routing status,
#      separate E/M, scope, the service it is included in), its lesions and its acts (kind, status, role, sites,
#      technique, detail, evidence, cues, lesion), every conflict, attribution and problem, the sedation reading;
#   6. the services reader's parts (services.parts): each part's family, role, kind, combined, noted and host over the
#      text, and the title spans;
#   7. the decision of every labelled paragraph the document holds (the twin's own decisions at its label).
#   A cue that quotes a released paragraph's own section heading ("section: procedure (Colonoscopy)", the twin's
#   "section: procedure (PROCEDURE)") is compared without the quote (_section_cue): the one word the twin writes
#   otherwise by construction, read by validation only into a reason's wording. Every other word of every cue is
#   compared.
#   Why 1-7 cover what the engine reads for a code: a code is read through routing's family finding (2, 3), the span
#   readers on its evidence (4; a span outside the released paragraphs reads its own characters, clause and section -
#   1 - with the family judgement - 2, 3), the documented services and reconcile's matching on them - acts, sites,
#   families, evidence, scope (5, 6) - and the clinical layout's section at a position and reconcile's held section (1).
# - How a corroborated paragraph comes to read as its twin (structural choices, each checked by the comparison, never
#   assumed): the clinical layout cuts its label's words off as a sentence of their own (_heading_split: routing reads
#   the label against the narrative's first sentence, as the twin reads its heading line); the services reader's parts
#   are the installed ones (installed_released: no labelled report part of its family, as the twin's line opens none, so
#   a site-less act binds as the twin binds it); and the services reader reads the label as it reads the twin's line -
#   a sentence of its own, a procedure-field listing of its service (services._corroborated_labels).
# - Withdrawal: ALL of the document's corroborated releases at once. The twin is read once, for the candidate set as a
#   whole; a smaller set is a different twin, never read, so its parity is never claimed. P4's cascade goes with its
#   anchor.
# - Bounded as the corroborated release is (CORROBORATED_DOCUMENT): two readings of a text of at most that length.
# - The guard reads at the document's own date of service (decisions never read a request's date) and without the
#   revision's page spans: the two readings it compares are read alike.
_CARRIED, _INSTALLED, _GUARDED = 'carried', 'installed', 'guarded'
TWIN_PREFIX = TWIN_HEADING  # "PROCEDURE: " - the twin's heading line is TWIN_PREFIX + the label's words + a newline
# set while the guard reads: the list of the texts a reader asked about that are no _Reading (each fails the guard)
_GUARDING: contextvars.ContextVar = contextvars.ContextVar('structure_twin_guard', default=None)


class _GuardRead(Exception):
    """A reader asked for a plain text's labelled paragraphs while the guard read: the guard cannot tell which release
    that text would read in the real reading, so it fails closed (the document reads as installed)."""


class _Reading(str):
    """A text read by the guard (_twin_parity): the document with its candidate release, or its heading twin. Equal only
    to itself and hashed by identity, so no functools cache keyed by a text - routing's analysis, the layouts, the
    services reader's own - shares an entry between it and any other reading of the same characters; ``carried`` is
    the decisions it reads (decisions returns them: nothing is decided again inside the guard)."""
    __hash__ = object.__hash__

    def __new__(cls, text: str, carried: tuple):
        reading = str.__new__(cls, text)
        reading.carried = carried
        return reading

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other


def _mode(text: str) -> str:
    """Which decisions ``text`` reads: its own (a _Reading), the installed ones (U14's direct-reach twin, routed by the
    installed release in every reading: detect._MOTION_OFF), or the guarded ones. While the guard reads, any other
    text fails the guard (_GuardRead)."""
    if isinstance(text, _Reading):
        return _CARRIED
    from studio.gi import detect  # local: detect imports this module
    if detect._MOTION_OFF.get():
        return _INSTALLED
    guarding = _GUARDING.get()
    if guarding is not None:
        guarding.append(len(text))
        raise _GuardRead(f'a plain text of {len(text)} characters was read while the guard read')
    return _GUARDED


class _HeadingTwin:
    """The heading twin of ``text`` over ``paragraphs`` (released, in order), and the content coordinate of a position in
    either text: the characters the two write differently - the label's colon and the blanks after it, the twin's
    "PROCEDURE: " and its newline - are no content; the label's words are, in both. Linear in the paragraphs; each
    position by bisection."""

    def __init__(self, text: str, paragraphs: list):
        pieces, pos, delta = [], 0, 0
        self.text = text
        self.labels = []  # (a, colon, b, the twin's heading start, the heading line's length with its newline)
        for p in paragraphs:
            a, colon = p.label.start, p.label.end
            b = colon
            while b < len(text) and text[b] in ' \t':
                b += 1
            heading = TWIN_PREFIX + text[a:colon - 1] + '\n'
            pieces += [text[pos:a], heading]
            self.labels.append((a, colon, b, a + delta, len(heading)))
            delta += len(heading) - (b - a)
            pos = b
        self.twin = ''.join(pieces) + text[pos:]
        self.gaps = [colon - 1 for _, colon, _, _, _ in self.labels]  # each label's colon and blanks: [colon - 1, b)
        self.removed = list(itertools.accumulate(b - colon + 1 for _, colon, b, _, _ in self.labels))
        self.twin_starts = [t for _, _, _, t, _ in self.labels]

    def content(self, pos: int) -> int:
        """A position of the document in content coordinates (one in a label's colon and blanks reads as their start)."""
        k = bisect.bisect_right(self.gaps, pos) - 1
        if k < 0:
            return pos
        _, colon, b, _, _ = self.labels[k]
        return colon - 1 - (self.removed[k - 1] if k else 0) if pos < b else pos - self.removed[k]

    def twin_content(self, pos: int) -> int:
        """A position of the twin in content coordinates: its "PROCEDURE: " reads as the label's first word, its newline
        as the label's colon."""
        k = bisect.bisect_right(self.twin_starts, pos) - 1
        if k < 0:
            return self.content(pos)
        a, colon, b, t, length = self.labels[k]
        word = t + len(TWIN_PREFIX)
        if pos < word:
            return self.content(a)
        if pos < t + length - 1:
            return self.content(a + pos - word)
        if pos == t + length - 1:
            return self.content(colon - 1)
        return self.content(b + pos - t - length)

    def twin_position(self, pos: int) -> int:
        """A position of the document outside every released label, in the twin."""
        k = bisect.bisect_right(self.gaps, pos) - 1
        if k < 0:
            return pos
        a, _, b, t, length = self.labels[k]
        return t + length + pos - b

    def sides(self, paragraphs: list) -> tuple:
        """(the document's side, the twin's side) of the comparison's per-reading inputs: the released paragraphs'
        regions (label to end) and the labels' words ("Colonoscopy" of "Colonoscopy: " and of "PROCEDURE: Colonoscopy"),
        and the heading words a section cue quotes for them."""
        doc_regions = [(p.start, p.end) for p in paragraphs]
        twin_regions = [(t, self.twin_position(p.end)) for p, (_, _, _, t, _) in zip(paragraphs, self.labels)]
        doc_words = [(a, colon - 1) for a, colon, _, _, _ in self.labels]
        twin_words = [(t + len(TWIN_PREFIX), t + len(TWIN_PREFIX) + colon - 1 - a) for a, colon, _, t, _ in self.labels]
        headings = {self.text[a:colon - 1].strip() for a, colon, _, _, _ in self.labels}
        return (doc_regions, doc_words, headings), (twin_regions, twin_words, {TWIN_PREFIX.rstrip(': ')})


def _section_cue(cue: str, quoted: tuple) -> str:
    """``cue`` without the quote of a released paragraph's own section heading ("section: procedure (Colonoscopy)" and
    the twin's "section: procedure (PROCEDURE)" read "section: procedure"): the one word the twin writes otherwise by
    construction, read by validation only into a reason's wording. Every other cue, and every other quote, as it is."""
    for heading in quoted:
        cue = cue.replace('section: procedure' + heading, 'section: procedure')
    return cue


def _twin_parity(text: str, candidate: tuple) -> bool:
    """Whether the heading twin of ``text`` over the released paragraphs of ``candidate`` (the installed ones and the
    corroborated ones) reads every compared fact exactly as ``text`` reads with ``candidate`` (the block comment above).
    Fail closed: any error, and any read of a text no _Reading carries, withdraws."""
    paragraphs = sorted((p for p, why in candidate if not why), key=lambda p: p.label.start)
    twin = _HeadingTwin(text, paragraphs)
    try:
        twin_decisions = _installed_state(twin.twin)[0]  # the installed release reads the twin: nothing corroborated
        from studio.gi import context as gi_context  # local: the date reader's own date of service (read only)
        day = gi_context.service_date_of(text)
    except Exception:  # noqa: BLE001 - fail closed
        return False
    refused: list = []
    token = _GUARDING.set(refused)
    try:
        doc_side, twin_side = twin.sides(paragraphs)
        equal = _reading_facts(_Reading(twin.twin, twin_decisions), day, twin.twin_content, *twin_side) \
            == _reading_facts(_Reading(text, candidate), day, twin.content, *doc_side)
    except Exception:  # noqa: BLE001 - fail closed: a reading the guard cannot complete never releases
        return False
    finally:
        _GUARDING.reset(token)
    return equal and not refused


def twin_differences(text: str) -> tuple:
    """For the tests and the probes: the names of the compared facts (_reading_facts) in which the heading twin of
    ``text`` reads otherwise than ``text`` reads with its corroborated release's candidates, before the guard decides;
    () when there is no candidate or none differs. Reads both texts, whatever the guard decided."""
    installed, read = _installed_state(text)
    if read is None or len(text) > CORROBORATED_DOCUMENT:
        return ()
    lay, head, ix, candidates, declared, stray, frames, candidate_starts = read
    listed = _listed_acts(text, lay)
    candidate = _corroborated_release(text, lay, head, ix, candidates, installed, declared, listed, stray, frames,
                                      candidate_starts) if listed else installed
    if candidate is installed:
        return ()
    paragraphs = sorted((p for p, why in candidate if not why), key=lambda p: p.label.start)
    twin = _HeadingTwin(text, paragraphs)
    from studio.gi import context as gi_context
    day = gi_context.service_date_of(text)
    refused: list = []
    token = _GUARDING.set(refused)
    try:
        doc_side, twin_side = twin.sides(paragraphs)
        a = _reading_facts(_Reading(twin.twin, _installed_state(twin.twin)[0]), day, twin.twin_content, *twin_side)
        b = _reading_facts(_Reading(text, candidate), day, twin.content, *doc_side)
    except _GuardRead:
        return ('plain-read',)
    finally:
        _GUARDING.reset(token)
    return tuple(name for name, x, y in zip(_FACT_NAMES, a, b) if x != y) + (('plain-read',) if refused else ())


_FACT_NAMES = ('layout', 'routing', 'analysis', 'span-readings', 'services', 'parts', 'decisions')


def _merged(spans) -> tuple:
    out: list = []
    for s, e in sorted(spans):
        if e <= s:
            continue
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return tuple(out)


def _runs(items, at) -> tuple:
    """[(start, end, value)] in text order -> the maximal runs of each value over content coordinates."""
    out: list = []
    for s, e, value in items:
        cs, ce = at(s), at(e)
        if ce <= cs:
            continue
        if out and out[-1][2] == value and out[-1][1] == cs:
            out[-1] = (out[-1][0], ce, value)
        else:
            out.append((cs, ce, value))
    return tuple(out)


def _reading_facts(reading: '_Reading', day, at, regions: list, label_words: list, headings: set) -> tuple:
    """The compared facts of one reading (the block comment above: 1-7, in _FACT_NAMES' order), every span in content
    coordinates (``at``); ``regions`` are the released paragraphs in this reading (label to end), ``label_words`` their
    labels' words, in order, and ``headings`` the words its section cues quote for them. Read by the readers
    themselves: routing, its span readers, the services reader."""
    from studio.gi import detect
    from studio.gi import services as gi_services

    def span(s, e):
        return at(s), at(e)

    def spans(evidence):
        return _merged(span(x.start, x.end) for x in evidence)

    quoted = tuple(f' ({heading})' for heading in headings)

    def cues_of(found):
        return tuple(_section_cue(c, quoted) for c in found)

    routed = detect.route(reading, day)
    an = detect._analysis(reading, day)[0]
    lay = an.lay
    sentences = [(k, s, e) for k, (s, e) in enumerate(lay.sentences) if at(e) > at(s)]
    clauses = [(s, e) for s, e in lay.clauses if at(e) > at(s)]
    layout = (_runs(((x.start, x.end, x.kind) for x in lay.sections), at), tuple(span(s, e) for _, s, e in sentences),
              tuple(span(s, e) for s, e in clauses))
    routing = (routed.document_kind, tuple(sorted((
        (f.family, f.status, tuple(f.missing),
         tuple(sorted(((x.name, x.value, x.origin, x.note, spans(x.evidence)) for x in f.facts), key=repr)),
         tuple(sorted(((span(m.span.start, m.span.end), span(m.sentence.start, m.sentence.end), m.section, m.status,
                        cues_of(m.cues)) for m in f.mentions), key=repr)))
        for f in routed.findings), key=repr)))

    def reading_of(r):
        return None if r is None else (r.status, cues_of(r.cues), getattr(r, 'doubt', None))
    analysis = (tuple((span(s, e), an.attributed[k] if k < len(an.attributed) else None) for k, s, e in sentences),
                tuple(sorted(((family, None if adj is None else repr(cues_of(adj) if isinstance(adj, tuple) else adj))
                              for family, adj in an.adjustments.items()), key=repr)),
                tuple(sorted(((span(m.start, m.end), m.family, reading_of(r)) for m, r in an.references.items()),
                             key=repr)),
                tuple(sorted(((span(m.start, m.end), reading_of(r)) for m, r in an.em_readings.items()), key=repr)))

    def routed_reading(s, e):
        status, found = detect.status_for_span(reading, s, e, day)
        back, back_found = detect.status_for_span(reading, s, e, day, back=True)
        own, own_found = detect.own_status_for_span(reading, s, e, day)
        return status, cues_of(found), back, cues_of(back_found), own, cues_of(own_found)

    def read(s, e):
        passages = gi_services.passage_readings(reading, s, e, day)
        return (span(s, e), routed_reading(s, e),
                None if passages is None else tuple((r.status, cues_of(r.cues), span(c.start, c.end)) for r, c in passages))
    def inside(s, e):  # a span that meets a released paragraph (a handful of them)
        return any(rs < e and s < re_ for rs, re_ in regions)
    readings = (tuple(read(s, e) for _, s, e in sentences if inside(s, e)),
                tuple(read(s, e) for s, e in clauses if inside(s, e)),
                tuple(read(s, e) for s, e in label_words))
    inventory = gi_services.build(reading, service_date=day, routing=routed)
    by_id = {s.id: s for s in inventory.services}
    lesions_by_id = {}
    for s in inventory.services:
        for lesion in s.lesions:
            lesions_by_id[lesion.id] = (lesion.noun, lesion.size, lesion.morphology, lesion.anatomy, lesion.region,
                                        lesion.specimen, lesion.disposition, spans(lesion.evidence))

    def service_of(service_id):
        found = by_id.get(service_id)
        return (found.family, found.kind) if found is not None else service_id

    documented = []
    for s in inventory.services:
        acts = tuple(sorted(((a.kind, a.status, a.role, tuple(a.anatomy), a.region, a.technique, a.detail,
                              spans(a.evidence), cues_of(a.cues), lesions_by_id.get(a.lesion, a.lesion))
                             for a in s.acts), key=repr))
        documented.append((s.family, s.kind, s.status, s.completion, s.extent, s.intent, s.service_date, s.clinician,
                           s.setting, s.role, spans(s.evidence), spans(s.completion_evidence), cues_of(s.cues),
                           cues_of(s.uncertainty), s.routing_status, s.separate_em, span(s.scope_start, s.scope_end),
                           service_of(s.included_in) if s.included_in else '',
                           tuple(sorted((lesions_by_id[x.id] for x in s.lesions), key=repr)), acts))
    services_read = (tuple(sorted(documented, key=repr)),
                     tuple(sorted(((c.subject, service_of(c.service), lesions_by_id.get(c.lesion, c.lesion),
                                    tuple((x.status, x.role, spans(x.evidence)) for x in c.sides), c.note)
                                   for c in inventory.conflicts), key=repr)),
                     tuple(sorted(((a.role, spans(a.evidence)) for a in inventory.attributions), key=repr)),
                     tuple(inventory.problems), inventory.sedation_by_endoscopist)
    flow = gi_services.reflow(reading)
    token = gi_services._ORIGINAL.set(reading)
    try:
        plist = gi_services.parts(flow, service_date=day)
    finally:
        gi_services._ORIGINAL.reset(token)
    parts = (_runs(((p.start, p.end, (p.family, p.role, p.kind, p.combined, p.noted, p.host)) for p in plist), at),
             tuple(sorted(span(p.title.start, p.title.end) for p in plist if p.title is not None)))
    held = tuple(sorted((at(p.label.start), why) for p, why in decisions(reading) if why))
    return layout, routing, analysis, readings, services_read, parts, held


def released(text: str) -> tuple[LabelledParagraph, ...]:
    """The text's released labelled procedure paragraphs, in order (see the module's docstring for P1-P4, N1-N3)."""
    if not isinstance(text, str) or ':' not in text:
        return ()
    return _released(text, _mode(text))


@functools.lru_cache(maxsize=16)
def _released(text: str, mode: str) -> tuple[LabelledParagraph, ...]:
    return tuple(p for p, why in _decided(text, mode) if not why)


def installed_released(text: str) -> tuple[LabelledParagraph, ...]:
    """The text's paragraphs the INSTALLED conditions release (P1-P4, N1-N3), in order: never a corroborated one, and
    never read through the guard - the services reader's parts read these (services._labelled_parts), so its parts are
    the installed ones whatever the corroborated release releases (u18d). A pure function of the text."""
    if not isinstance(text, str) or ':' not in text:
        return ()
    decided = text.carried if isinstance(text, _Reading) else _installed_state(text)[0]
    return tuple(p for p, why in decided if not why and not p.corroborated)


def overlay(lay: Layout, paragraphs: tuple) -> Layout:
    """``lay`` with each of ``paragraphs`` read as a procedure section of its own (label: the service's name; heading:
    the label as written), cut out of whatever sections it overlaps; the pieces of a section a paragraph stood in keep
    that section's kind, label and heading. The sentences and clauses are ``lay``'s own, but for a corroborated
    paragraph's label (_heading_split). With no paragraphs it is ``lay`` itself. Linear in the sections and the
    paragraphs."""
    if not paragraphs:
        return lay
    cuts = sorted({b for p in paragraphs for b in (p.start, p.end)})
    starts = [p.start for p in paragraphs]
    out: list[Section] = []
    for section in lay.sections:
        lo, hi = bisect.bisect_right(cuts, section.start), bisect.bisect_left(cuts, section.end)
        edges = [section.start] + cuts[lo:hi] + [section.end]
        for a, b in zip(edges, edges[1:]):
            if b <= a:
                continue
            k = bisect.bisect_right(starts, a) - 1
            p = paragraphs[k] if k >= 0 and paragraphs[k].start <= a < paragraphs[k].end else None
            if p is None:
                out.append(section if (a, b) == (section.start, section.end)
                           else Section(section.kind, section.label, section.heading, a, b))
            elif out and out[-1].heading is p.label and out[-1].end == a:
                last = out.pop()  # the paragraph goes on across a section boundary of ``lay``: one section
                out.append(Section('procedure', last.label, p.label, last.start, b))
            else:
                out.append(Section('procedure', gi_sections.normalize_label(p.label.text), p.label, a, b))
    sentences, clauses = lay.sentences, lay.clauses
    corroborated = [p for p in paragraphs if p.corroborated]
    if corroborated:
        sentences, clauses = _heading_split(lay.text, sentences, corroborated), _heading_split(lay.text, clauses,
                                                                                               corroborated)
    return Layout(lay.text, tuple(out), sentences, clauses, tuple(s.start for s in out))


def _heading_split(text: str, spans: tuple, paragraphs: list) -> tuple:
    """``spans`` (a layout's sentences or clauses) with the one opening at each corroborated paragraph's label cut as
    its heading twin cuts it (u18d): the label's words alone ("Colonoscopy"), then the narrative from its first word on
    - the twin writes them "PROCEDURE: Colonoscopy" and a newline, and its layout reads the heading's words as a
    sentence of their own and the narrative's first sentence from its first word. So every reader that reads a
    sentence or a clause - routing's reading of the label against the sentence after its own, the services reader's
    evidence of the service the label names - reads the label as the twin reads its heading line. The blanks after the
    colon lie in no span, as the twin's newline lies in none. A label whose span does not open at it is left
    as it is (the guard then compares what it reads). The label's span keeps its colon, so the released label routing
    reads (detect._released_label_at) lies inside it. Bisection per paragraph."""
    out = list(spans)
    for p in sorted(paragraphs, key=lambda p: -p.label.start):
        k = bisect.bisect_left(out, (p.label.start, -1))
        if k >= len(out) or out[k][0] != p.label.start:
            continue
        s, e = out[k]
        colon, b = p.label.end, p.label.end
        while b < len(text) and text[b] in ' \t':
            b += 1
        if not s < colon - 1 < b < e:
            continue
        out[k:k + 1] = [(s, colon), (b, e)]
    return tuple(out)


def clinical_layout(text: str) -> Layout:
    """sections.layout(text) with the text's released labelled paragraphs read as procedure sections of their own
    (overlay). With nothing released it is sections.layout(text) itself."""
    return _clinical_layout(text, _mode(text) if isinstance(text, str) and ':' in text else _GUARDED)


@functools.lru_cache(maxsize=16)
def _clinical_layout(text: str, mode: str) -> Layout:
    return overlay(gi_sections.layout(text), _released(text, mode) if ':' in text else ())


def reader_layout(text: str, original: str) -> Layout:
    """For a reader of a same-length view of ``original`` (the services reader's reflowed text, a soft line break read
    as a space): its own sections.layout(text) with ``original``'s released paragraphs overlaid, so it reads the same
    section fact as routing, which reads ``original``. With nothing released it is sections.layout(text) itself."""
    if original == text or len(original) != len(text):
        return clinical_layout(text)
    return _reader_layout(text, original, _mode(original) if ':' in original else _GUARDED)


@functools.lru_cache(maxsize=16)
def _reader_layout(text: str, original: str, mode: str) -> Layout:
    return overlay(gi_sections.layout(text), _released(original, mode) if ':' in original else ())
