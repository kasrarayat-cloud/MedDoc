"""H6: the mutant battery. One killing mutant per guard, applied to a COPY of a sealed export (never to a worktree and
never to a file anyone is editing), with the sha256 printed after the mutation is applied and again after it is
restored, and the restore compared with the original bytes.

A mutant names the guard it removes, one exact anchor (it must occur exactly once, or nothing is applied and the
mutant counts as NOT RUN, never as killed), its replacement, and its detector:
  unit:LABEL    the Django test LABEL (SimpleTestCase only: no database) fails on the mutant
  state:LABEL   the Django test LABEL fails on the mutant, on the throwaway test database (127.0.0.1:55461 only)
  replay        the H1 replay differs from the unmutated tree's
  freeze        the H2 freeze gate fails (base: the unmutated tree, head: the mutant)
  battery       the H4 battery shows a movement no declaration names
Every detector first runs on the unmutated copy and must pass there: a detector that fails without the mutation proves
nothing (a failing baseline turns every mutant into a false kill).

The registry holds stage A's mutants and every round-4 package's: PS and PA (written here by their packages), and PD,
PV1, PE, PI and PO (merged here by the Wave 1 integration from the registries each package kept outside this file).
No registry check lives in a detector module: a mutant removes its own anchor, so an anchor check there would kill
every mutant whatever the behaviour tests saw. tests/test_gi4_mutants.py checks every anchor against the tree.

  python -m ops.gi4.mutants --base REF|DIR [--only NAME ...] [--scratch DIR]
"""
from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ops.gi4 import boot


@dataclass(frozen=True)
class Mutant:
    name: str
    guard: str
    path: str  # relative to the cpt-studio directory
    old: str
    new: str
    detector: str


MUTANTS = (
    # --- package PS: the shared helpers (killed by their own unit tests) ---
    Mutant('ps-head-lines-blank', 'head_lines_end skips whitespace-only lines', 'studio/gi/sections.py',
           '        if _NON_BLANK.search(text, start, end):\n            count, found = count + 1, end',
           '        if True:\n            count, found = count + 1, end',
           'unit:tests.test_gi4_sections'),
    Mutant('ps-procedure-head-reach', 'procedure_report_head reads the head only', 'studio/gi/sections.py',
           '    return end > 0 and PROCEDURE_HEAD.search(text, 0, end) is not None',
           '    return PROCEDURE_HEAD.search(text) is not None', 'unit:tests.test_gi4_sections'),
    Mutant('ps-around-title-field', 'around_procedure_title: a field is no title', 'studio/gi/sections.py',
           '                    and not _TITLE_FIELD.search(line) and AROUND_PROCEDURE_WORDS.search(line):',
           '                    and AROUND_PROCEDURE_WORDS.search(line):', 'unit:tests.test_gi4_sections'),
    Mutant('ps-around-title-sentence', 'around_procedure_title: a sentence is no title', 'studio/gi/sections.py',
           "            if line and len(line) <= AROUND_PROCEDURE_TITLE_CHARS and line[-1] not in '.!?;,' \\",
           '            if line and len(line) <= AROUND_PROCEDURE_TITLE_CHARS \\', 'unit:tests.test_gi4_sections'),
    Mutant('ps-under-occurrence-head', 'under_another_occurrence reads the heading-like line above',
           'studio/gi/sections.py',
           '            return bool(ANOTHER_OCCURRENCE_HEAD.search(line))\n        end = start - 1\n    return False\n\n\n'
           'HEADING_REACH_LINES',
           '            return False\n        end = start - 1\n    return False\n\n\nHEADING_REACH_LINES',
           'unit:tests.test_gi4_sections'),
    Mutant('ps-beyond-reach-fail-closed', 'beyond_heading_reach fails closed past its reach', 'studio/gi/sections.py',
           '    if pos - lo > HEADING_REACH_CHARS:\n        return True',
           '    if pos - lo > HEADING_REACH_CHARS:\n        return False', 'unit:tests.test_gi4_sections'),
    Mutant('ps-beyond-reach-heading-like', 'beyond_heading_reach finds an unread heading-like line',
           'studio/gi/sections.py',
           "                and all(w[:1].isupper() for w in _HEADING_WORD.findall(line) if len(w) >= 4):\n"
           "            return True",
           "                and all(w[:1].isupper() for w in _HEADING_WORD.findall(line) if len(w) >= 4):\n"
           "            return False", 'unit:tests.test_gi4_sections'),
    # --- package PA: the agreement gate's one-cause rule (studio/validation/engine.py) ---
    Mutant('pa-second-reading-one-cause', "_second_reading: both readings only by a section beyond its heading's reach "
           'are no agreement', 'studio/validation/engine.py',
           '                if one_cause:\n                    # GI round 4 (PA): both readers take the time from one section',
           '                if False:\n                    # GI round 4 (PA): both readers take the time from one section',
           'battery'),
    Mutant('pa-not-same-one-cause', '_not_the_same_not_done: a service and a passage read only by one section are no '
           'agreement', 'studio/validation/engine.py',
           '        if _section_only_service_reading(found.service.cues) and _section_only_routing_reading(decisive, text):\n',
           '        if False:\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-service-side-not-same', "_not_the_same_not_done: the service's own reading must be its section's too",
           'studio/validation/engine.py',
           '        if _section_only_service_reading(found.service.cues) and _section_only_routing_reading(decisive, text):\n',
           '        if _section_only_routing_reading(decisive, text):\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-service-side-second', "_second_reading: the documented-service reading must be its section's too",
           'studio/validation/engine.py', '            if _section_only_service_reading(reading.cues):\n',
           '            if True:\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-routing-reach', "the one-cause rule needs the section to reach the passage beyond its heading's reach",
           'studio/validation/engine.py',
           '    return gi_sections.beyond_heading_reach(text, gi_sections.layout(text), reading.start)\n',
           '    return True\n', 'battery'),
    Mutant('pa-routing-own-time', "a routing time or status cue of its own is routing's own reading",
           'studio/validation/engine.py', '            or any(_pa_own_time(cue) for cue in reading.cues):\n',
           '            or False:\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-routing-section-cue', "routing's reading must be its section's (a section cue)", 'studio/validation/engine.py',
           '    if not any(cue.startswith(checks.SECTION_CUE_PREFIX) for cue in reading.cues) \\\n', '    if False \\\n',
           'unit:tests.test_gi4_pa'),
    Mutant('pa-routing-position', 'a reading of the whole family (no passage) is never one-cause',
           'studio/validation/engine.py', '    if reading.start is None:  # a reading of the whole family',
           '    if False:  # a reading of the whole family', 'unit:tests.test_gi4_pa'),
    Mutant('pa-service-own-time', "a documented-service time or status cue of its own is that reader's own reading",
           'studio/validation/engine.py',
           '        and all(cue in _SECTION_ONLY_SERVICES for cue in cues if _pa_own_time(cue))\n', '        and True\n',
           'unit:tests.test_gi4_pa'),
    Mutant('pa-service-section-cue', "a documented-service reading is its section's only with its section's own cue",
           'studio/validation/engine.py', '    return any(cue in _SECTION_ONLY_SERVICES for cue in cues) \\\n',
           '    return True \\\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-own-time-planned', 'a plan word a reader states itself is its own reading (every not-done status)',
           'studio/validation/engine.py',
           "    return cue.startswith(('historical:', 'planned:', 'negated:', 'cancelled:'))\n",
           "    return cue.startswith(('historical:', 'negated:', 'cancelled:'))\n", 'unit:tests.test_gi4_pa'),
    Mutant('pa-same-way-words', 'a one-cause hold says the two readings read it the same way, never otherwise',
           'studio/validation/engine.py',
           "            how = 'reads it the same way' if _pa_same_not_done(found, old) else 'reads it otherwise'\n",
           "            how = 'reads it otherwise'\n", 'unit:tests.test_gi4_pa'),
    Mutant('pa-reach-far-words', 'a heading beyond the reach read is said so, never as an unread heading line',
           'studio/validation/engine.py', '    if lo >= 0 and (pos - lo > gi_sections.HEADING_REACH_CHARS\n',
           '    if False and (pos - lo > gi_sections.HEADING_REACH_CHARS\n', 'unit:tests.test_gi4_pa'),
    # --- H1's three planted controls (the replay must differ on each) ---
    Mutant('ctl-date-charge-answer', "the charge-block question takes only the installed reading's date",
           'studio/gi/context.py', "if value == own else", "if True else", 'replay'),
    Mutant('ctl-routing-elsewhere-order', "routing's order of another encounter's statuses", 'studio/gi/detect.py',
           "ELSEWHERE_ORDER = ('negated', 'historical', 'planned')",
           "ELSEWHERE_ORDER = ('planned', 'historical', 'negated')", 'replay'),
    Mutant('ctl-request-date-line', "the request's date line", 'studio/providers/corti.py',
           "(text, f'Date of service: {service_date.isoformat()}')",
           "(text, f'Service date: {service_date.isoformat()}')", 'replay'),
    # --- H2's gates ---
    Mutant('freeze-member-differs-is-conflict', 'a member date differing from the documented one is a conflict',
           'studio/gi/context.py', '                and str(documented.value) != value:',
           '                and str(documented.value) != value and False:', 'freeze'),
    Mutant('freeze-cue-pattern', 'a cue pattern sections.py reads (cues.PROCEDURE_TITLE)', 'studio/gi/cues.py',
           r"(?:procedure\s+)?(?:report|note)$')", r"(?:procedure\s+)?(?:report|note|summary)$')", 'freeze'),
    Mutant('freeze-heading-length', "the layout's heading length limit", 'studio/gi/sections.py',
           '    if not raw.strip() or len(raw) > 60:\n        return None\n    label = normalize_label(raw)',
           '    if not raw.strip() or len(raw) > 24:\n        return None\n    label = normalize_label(raw)', 'freeze'),
    Mutant('freeze-mention-count', "the analyze stage's mention count", 'studio/gi/detect.py',
           '    return len(_service_mentions(text))\n', '    return len(_service_mentions(text)) // 2\n', 'freeze'),
    # --- H4's code-level guard: the agreement an exclusion needs (both directions) ---
    Mutant('battery-agreement-never', "the second reader's agreement can exclude", 'studio/validation/engine.py',
           '    return not _second_reading(outcome, text, day, pages)\n', '    return False\n', 'battery'),
    Mutant('battery-exclusion-needs-agreement', 'an exclusion needs the second reader to agree', 'studio/validation/engine.py',
           '    return not _second_reading(outcome, text, day, pages)\n', '    return True\n', 'battery'),
    # --- H5's state guards (the throwaway test database) ---
    Mutant('state-reuse-retained', 'an identical retained request is reused, never sent again', 'studio/jobs.py',
           "    ).order_by('created_at').first()\n    if prior is not None:\n        run = models.ProviderRun.objects.create(",
           "    ).order_by('created_at').first()\n    if False:\n        run = models.ProviderRun.objects.create(",
           'state:tests.test_gi4_state'),
    Mutant('state-upgrade-predict-never-sends', "an upgrade's own predict never sends", 'studio/jobs.py',
           '    if job.idempotency_key == _upgrade_predict_key(context):\n        # Refutation r1',
           '    if False:\n        # Refutation r1', 'state:tests.test_gi4_state'),
)

# === the Wave 1 packages' registries, merged here by the Wave 1 integration. Each package kept its mutants beside its
# detector, outside this file it did not own (PV1, PE, PI and PO in tests/test_gi4_<package>_mutants.py, PD in a scratch
# driver); every anchor, replacement, guard and detector below is the package's own, byte for byte, and each package's
# tests/test_gi4_<package>_mutants.py now checks its slice of this registry. ===
# --- package PD: date step 1 (studio/gi/context.py; detector tests.test_gi4_pd). PD ran these from its scratch driver
# (they were registered nowhere in the tree); the integration registers them here, byte for byte ---
_PD_CONTEXT = 'studio/gi/context.py'
_PD_UNIT = 'unit:tests.test_gi4_pd'
PD_MUTANTS = (
    Mutant('pd-around-title', 'no wide or worded label is read under a title of a note written around a procedure', _PD_CONTEXT,
           '    if not worded and WIDE_SERVICE_DATE.search(text, 0, head_end) is None or around_procedure_title(text):\n',
           '    if not worded and WIDE_SERVICE_DATE.search(text, 0, head_end) is None:\n', _PD_UNIT),
    Mutant('pd-closing-last-lines', 'corroboration only from the last 8 non-empty lines', _PD_CONTEXT,
           '    for m in _CLOSING_ROLE.finditer(text, _pd_closing_start(text)):\n',
           '    for m in _CLOSING_ROLE.finditer(text, 0):\n', _PD_UNIT),
    Mutant('pd-not-closing-words', 'never from a consent, order, request, booking or call line', _PD_CONTEXT,
           '        if _PD_NOT_CLOSING.search(text, start, line_end):\n            continue\n',
           '        if False:\n            continue\n', _PD_UNIT),
    Mutant('pd-plain-apart', 'the installed candidates are read apart from the wide ones', _PD_CONTEXT,
           '    return plain + tuple(c for c in joint if c.wide)\n', '    return joint\n', _PD_UNIT),
    Mutant('pd-corroboration', 'one uncorroborated wide value restricts no answer (the installed fact stands)', _PD_CONTEXT,
           "    if full.origin == 'missing' and not any(c.corroborated for c in wide):\n", '    if False:\n', _PD_UNIT),
    Mutant('pd-own-reading-filter', "a wide label the installed label reading places elsewhere is dropped", _PD_CONTEXT,
           "        if _READING[kind] != 'own':\n            continue  # another occurrence's, or one it cannot place: "
           "dropped, as the installed reading drops the label\n", '        if False:\n            continue\n', _PD_UNIT),
    Mutant('pd-worded-occurrence-words', "a worded field with another occurrence's words before its colon is dropped", _PD_CONTEXT,
           "        if _READING[kind] != 'own' or _OCCURRENCE_WORDS.search(text, m.end('label'), ds):\n",
           "        if _READING[kind] != 'own':\n", _PD_UNIT),
    Mutant('pd-head-reach', 'wide labels are read in the head only', _PD_CONTEXT,
           '    return min(head_lines_end(text, TITLE_LINES), first)\n', '    return len(text)\n', _PD_UNIT),
    Mutant('pd-rule-a-readers-read-x', "a wide label's question is read as the narrow release's (every reader reads X)", _PD_CONTEXT,
           "    if get('origin') != 'conflict' or not note.startswith((_CHARGE_NOTE_HEAD, _WIDE_NOTE_HEAD)) \\\n",
           "    if get('origin') != 'conflict' or not note.startswith(_CHARGE_NOTE_HEAD) \\\n", _PD_UNIT),
    Mutant('pd-rule-a-only-x', "rule (a) takes only the date the installed reading sends", _PD_CONTEXT,
           "            value=fact.value, own='\\u201c'", "            value=differing[0].value, own='\\u201c'", _PD_UNIT),
    Mutant('pd-wide-never-own', 'a wide label is never the note\'s own date (never sent)', _PD_CONTEXT,
           '                              alone=_alone_in_field(text, m.end(), rows.line(m.start())[1]), installed=False,\n',
           '                              alone=_alone_in_field(text, m.end(), rows.line(m.start())[1]), installed=True,\n', _PD_UNIT),
)
# --- package PV1: E/M reading fixes and the C4 holds (detector tests.test_gi4_pv1; moved here from
# tests/test_gi4_pv1_mutants.py, which now checks this slice) ---
_PV1_DETECT, _PV1_CUES, _PV1_CHECKS = 'studio/gi/detect.py', 'studio/gi/cues.py', 'studio/validation/checks.py'
_PV1_UNIT = 'unit:tests.test_gi4_pv1'
_PV1_HOLD = "        return Reading('uncertain', (f\"{EM_NOT_IN_PERSON}: '{words}'\",), 'cue', doubt=True)"
_PV1_TIME_HOLD = "    if m.kind == 'em-time' or _pv1_decision_label(an, m):"
_PV1_TIME_ONLY = "    if m.kind != 'em-time':\n        return None\n    listed = cues.EM_TIME_ACTIVITIES"
_PV1_DATES = '    for d in an.dates_in(cs, ce):  # GI round 4 (C1): a date in an activity list still governs (see the docstring)\n'
_PV1_SKIP = '        if activities is not None and cue.start >= activities and _pv1_activity_work(cue):'
# C4's session-2 synonyms in cues.NOT_IN_PERSON, from the line before them to the pattern's end (exact source text)
_PV1_NO_SHOW = (' ' * 19 + r'''r"|\bno[- ]?show(?:s|ed)?\b|\b(?:did\s+not|didn't|failed\s+to)'''
                r'''\s+(?:arrive|attend|show\s+up)\b"''')
_PV1_SYNONYMS = _PV1_NO_SHOW + r'''
                   # session 2: "The patient was not seen.", a visit-type field naming the telephone ("Visit type:
                   # Telephone", "Type of encounter: phone"), "missed her appointment", "left without being seen"
                   r'|\b(?:patient|pt|she|he)\s+(?:was|is)\s+not\s+seen\b|\b(?:(?:visit|encounter|appointment|contact|'
                   r'consult(?:ation)?)\s+(?:type|mode|modality|method)|(?:type|mode|modality|method)\s+of\s+(?:visit|'
                   r'encounter|appointment|contact|consult(?:ation)?))[ \t]*[:\-][ \t]*(?:tele)?phone\b'
                   r"|\bmissed\s+(?:her|his|their|the|this|today'?s)\s+(?:scheduled\s+)?(?:appointment|visit)\b"
                   r'|\bleft\s+without\s+being\s+seen\b|\bLWBS\b')'''

PV1_MUTANTS = (
    Mutant('pv1-c4-hold', 'C4: a performed E/M reading is held when the note may document no in-person visit',
           _PV1_DETECT, '    if words is not None:\n' + _PV1_HOLD, '    if False:\n' + _PV1_HOLD, _PV1_UNIT),
    Mutant('pv1-c4-head', "C4: the head's title lines are read whatever section they fall in", _PV1_DETECT,
           '            title = cues.NOT_IN_PERSON_TITLE.search(text, 0, gi_sections.head_lines_end(text, '
           '_PV1_HEAD_LINES))', '            title = None', _PV1_UNIT),
    Mutant('pv1-c4-own-sentence', "C4: the E/M statement's own sentence is read whatever its section", _PV1_DETECT,
           '    if i < len(spans) and spans[i][1] <= e:', '    if False:', _PV1_UNIT),
    Mutant('pv1-another-time', "C4: installed's _another_time holds a performed E/M time statement", _PV1_DETECT,
           _PV1_TIME_HOLD, '    if _pv1_decision_label(an, m):', _PV1_UNIT),
    Mutant('pv1-c2-another-time', "C2: the new decision-making label takes the time statement's hold", _PV1_DETECT,
           _PV1_TIME_HOLD, "    if m.kind == 'em-time':", _PV1_UNIT),
    Mutant('pv1-c1-after-only', 'C1: a cue before the activity word still re-times the time statement', _PV1_DETECT,
           _PV1_SKIP, '        if activities is not None and _pv1_activity_work(cue):', _PV1_UNIT),
    Mutant('pv1-c1-plan-work', 'C1 (session 2): after the activity word only a planned cue is skipped (a '
           'cancellation or a history still re-times the statement)', _PV1_DETECT, _PV1_SKIP,
           '        if activities is not None and cue.start >= activities:', _PV1_UNIT),
    Mutant('pv1-c1-planned-time', 'C1 (session 2): a planned time after the activity word still re-times the '
           'statement (only the plan words of the visit\'s work are skipped)', _PV1_DETECT,
           "    return cue.name in _PV1_PLAN_WORK_CUES or (cue.name == 'next' and "
           "_PV1_NEXT_STEPS.match(cue.text) is not None)", '    return True', _PV1_UNIT),
    Mutant('pv1-c1-dates-count', "C1: a date in an activity list still re-times the time statement", _PV1_DETECT,
           _PV1_DATES, _PV1_DATES + '        if activities is not None and d.start >= activities:\n            continue\n',
           _PV1_UNIT),
    Mutant('pv1-c1-time-only', "C1: only a time statement has an activity list (a visit statement's cues count)",
           _PV1_DETECT, _PV1_TIME_ONLY, _PV1_TIME_ONLY.replace("if m.kind != 'em-time':",
                                                               "if m.kind not in ('em-time', 'em-visit'):"), _PV1_UNIT),
    Mutant('pv1-c2-shared', '"shared decision making" never gives an MDM level (a label and its separator)', _PV1_CUES,
           r"               r'|\b(?:complexity|level)\s+of\s+decision[- ]making[ \t]*[:\-][ \t]*)'",
           r"               r'|\b(?:\w+\s+)?(?:of\s+)?decision[- ]making\b[^.;\n]{0,60}?)'", _PV1_UNIT),
    Mutant('pv1-v3-ultrasound', "V3: an ultrasound named in an E/M code's negative passage holds the E/M", _PV1_CHECKS,
           'labs?|ultrasounds?|sonograms?|', 'labs?|sonograms?|', _PV1_UNIT),
    Mutant('pv1-c4-synonyms', 'C4 (session 2): "the patient was not seen", a visit-type field naming the '
           'telephone, "missed her appointment" and "left without being seen" hold every E/M reading', _PV1_CUES,
           _PV1_SYNONYMS, _PV1_NO_SHOW + ')', _PV1_UNIT),
    Mutant('pv1-c2-opens-sentence', "C2 (session 2): the new label reads a level only when it opens its "
           'sentence', _PV1_DETECT, '        if label and not _pv1_opens_its_sentence(an.text, m.start, s):',
           '        if False:', _PV1_UNIT),
    Mutant('pv1-other-visit', 'C2 and C4-time (session 2): another visit named by a preposition, with or '
           'without a determiner, holds a time statement or the new label', _PV1_DETECT,
           '        other = _pv1_other_visit(an, s, max(e, m.end), label)', '        other = None', _PV1_UNIT),
    Mutant('pv1-quote-window', "H7 (session 2): the label-inside quote is cut from a bounded window, never from "
           "the sentence's start", _PV1_DETECT,
           "            said = ' '.join(an.text[max(s, m.start - _PV1_QUOTE_WINDOW):m.end].split())[-_PV1_QUOTE:]",
           "            said = ' '.join(an.text[s:m.end].split())[-_PV1_QUOTE:]", _PV1_UNIT),
    Mutant('pv1-other-visit-window', 'H7 (session 2): the other-visit quote is cut from a bounded window of its '
           'match', _PV1_DETECT,
           "        return ' '.join(an.text[x:min(y, x + _PV1_QUOTE_WINDOW)].split())[:_PV1_QUOTE]",
           "        return ' '.join(an.text[x:y].split())[:_PV1_QUOTE]", _PV1_UNIT),
)
# --- package PE: routing extent vocabulary (detector tests.test_gi4_pe; moved here from tests/test_gi4_pe_mutants.py,
# which now checks this slice) ---
_PE_DETECT = 'studio/gi/detect.py'
_PE_UNIT = 'unit:tests.test_gi4_pe'
PE_MUTANTS = (
    Mutant('pe-vocabulary', "routing's own reach verbs are read (the release)", _PE_DETECT,
           '    found = cues.REACHED_BEFORE_ROUTING.search(pre)\n', '    found = cues.REACHED_BEFORE.search(pre)\n', _PE_UNIT),
    Mutant('pe-endpoint', "a routing-only verb reads only the family's endpoint or beyond", _PE_DETECT,
           "    if depth < _S2_expected_depth(an, table):\n        return False  # short of the family's endpoint",
           "    if False:\n        return False  # short of the family's endpoint", _PE_UNIT),
    Mutant('pe-doubt-governs', 'a negation, modal, infinitive, hedge or present tense governing the verb', _PE_DETECT,
           '    if re.search(r"(?:\\b(?:not|never|cannot|unable[ \\t\\n]+to|',
           '    if False and re.search(r"(?:\\b(?:not|never|cannot|unable[ \\t\\n]+to|', _PE_UNIT),
    Mutant('pe-doubt-falling-short', 'a falling-short adverb before the verb', _PE_DETECT,
           '        return True  # it fell short', '        return False  # it fell short', _PE_UNIT),
    Mutant('pe-doubt-plan', 'a wish, plan, attempt or condition before the verb', _PE_DETECT,
           '        return True  # a wish, a plan, an attempt or a condition',
           '        return False  # a wish, a plan, an attempt or a condition', _PE_UNIT),
    Mutant('pe-doubt-span', 'a negation, hedge or attempt between the verb and the landmark', _PE_DETECT,
           '        return True  # denied or doubted between the verb and the landmark',
           '        return False  # denied or doubted between the verb and the landmark', _PE_UNIT),
    Mutant('pe-doubt-post', 'another time or a condition after the landmark', _PE_DETECT,
           "    return re.search(r'\\b(?:later|tomorrow|upcoming|future|",
           "    return False and re.search(r'\\b(?:later|tomorrow|upcoming|future|", _PE_UNIT),
    Mutant('pe-endoscope', 'the endoscope moved, never an accessory', _PE_DETECT,
           '    if not _pe_endoscope_moved(before, span):\n        return False', '    if False:\n        return False', _PE_UNIT),
    Mutant('pe-around-procedure', 'no routing-only reach in a note written around a procedure', _PE_DETECT,
           '    if _pe_around_procedure(an):\n        return False', '    if False:\n        return False', _PE_UNIT),
    Mutant('pe-another-occurrence', "no routing-only reach outside today's procedure narrative (Wave 1 repair: the shared "
           'copy guards, which read under_another_occurrence now)', _PE_DETECT,
           '    return in_todays_narrative(an.text, verb, an.service_date, (at - len(pre), at + len(post)))',
           '    return True', _PE_UNIT),
    # --- GI round 4 Wave 1 repair, cycle 1: the shared copy guards of today's procedure report and narrative
    # (detect.todays_procedure_report, detect.in_todays_narrative), read by PE's routing-only reach and PI's S1 and E1 ---
    Mutant('pe-today-head-date', "the strong head: an own-date field", _PE_DETECT,
           '    if not head.own_dates:  # an own-date field\n        return False',
           '    if False:  # an own-date field\n        return False', _PE_UNIT),
    Mutant('pe-today-head-one-date', 'the strong head: its own-date fields name one day only', _PE_DETECT,
           '    if len(set(head.own_dates)) > 1:  # one own date only (a second one names another day: whose report is it?)\n'
           '        return False',
           '    if False:  # one own date only (a second one names another day: whose report is it?)\n        return False',
           _PE_UNIT),
    Mutant('pe-today-head-proceduralist', 'the strong head: a proceduralist field (never "Attending:")', _PE_DETECT,
           '    if not head.proceduralist:  # a proceduralist field\n        return False',
           '    if False:  # a proceduralist field\n        return False', _PE_UNIT),
    Mutant('pe-today-head-sedation', 'the strong head: a sedation field, never the word in another field', _PE_DETECT,
           '    if not head.sedation:  # a sedation field\n        return False',
           '    if False:  # a sedation field\n        return False', _PE_UNIT),
    Mutant('pe-today-sedation-denial', 'a sedation field whose value is a denial ("none") is no sedation field', _PE_DETECT,
           "                        and not _GI4_NO_SEDATION.match(text, field_m.start('value'), line_end):",
           '                        and True:', _PE_UNIT),
    Mutant('pe-today-head-title', 'no head title names a later review, a result or another record', _PE_DETECT,
           '    return not any(_GI4_TITLE_HOLD.search(text, s, e) for s, e in head.titles)', '    return True', _PE_UNIT),
    Mutant('pe-today-foreign-heading', 'a heading naming an attachment or a copy opens a foreign block', _PE_DETECT,
           '                if _GI4_ATTACHED.search(line) and start < foreign:  # a foreign block: an attachment or a copy',
           '                if False:  # a foreign block: an attachment or a copy', _PE_UNIT),
    Mutant('pe-today-foreign-dated', 'a heading dated another day opens a foreign block', _PE_DETECT,
           '                if dated and start < foreign:  # a foreign block: a heading dated another day',
           '                if False:  # a foreign block: a heading dated another day', _PE_UNIT),
    Mutant('pe-today-foreign-signoff', 'a sign-off line opens a foreign block', _PE_DETECT,
           "                if start < foreign:  # a foreign block: today's report, or another, signed off above the passage",
           "                if False:  # a foreign block: today's report, or another, signed off above the passage",
           _PE_UNIT),
    Mutant('pe-today-foreign-copy', 'a statement that a copy follows opens a foreign block', _PE_DETECT,
           '    if copy is not None and copy.start() < foreign:  # a foreign block: a statement that a copy follows',
           '    if False:  # a foreign block: a statement that a copy follows', _PE_UNIT),
    Mutant('pe-today-governing-words', 'the governing heading names no other record or occasion and no education',
           _PE_DETECT,
           '        if words:  # the governing heading names another record or occasion, or education\n            return False',
           '        if False:  # the governing heading names another record or occasion, or education\n            return False',
           _PE_UNIT),
    Mutant('pe-today-governing-facility', "the governing heading below the head's fields names no facility", _PE_DETECT,
           "        if facility:  # a facility's heading below the head's own fields\n            return False",
           "        if False:  # a facility's heading below the head's own fields\n            return False", _PE_UNIT),
    Mutant('pe-today-governing-kind', 'the governing heading is no history, plan or indication heading', _PE_DETECT,
           '        if kind:  # a history, plan or indication heading\n            return False',
           '        if False:  # a history, plan or indication heading\n            return False', _PE_UNIT),
    Mutant('pe-today-governing-reach', 'the governing heading lies within 200 lines and 20,000 characters (no release '
           'beyond)', _PE_DETECT,
           '        return False  # its heading lies beyond reach: no release',
           '        pass  # its heading lies beyond reach: no release', _PE_UNIT),
    Mutant('pe-today-block-date', "the passage's block carries no date other than today's", _PE_DETECT,
           "        if _gi4_other_day(d, today):  # another day's date in the passage's block\n            return False",
           "        if False:  # another day's date in the passage's block\n            return False", _PE_UNIT),
    Mutant('pe-today-block-signoff', "the passage's block carries no sign-off line", _PE_DETECT,
           "    if k < len(marks.signoffs) and marks.signoffs[k] < hi:  # a sign-off line in the passage's block\n"
           '        return False',
           "    if False:  # a sign-off line in the passage's block\n        return False", _PE_UNIT),
    Mutant('pe-today-general', "the passage's sentence states no unit statistics or generalisation", _PE_DETECT,
           '        return False  # unit statistics or a generalisation',
           '        pass  # unit statistics or a generalisation', _PE_UNIT),
    Mutant('pe-today-occurrence', 'the passage is not under another occurrence (sections.under_another_occurrence)',
           _PE_DETECT, '    if gi_sections.under_another_occurrence(text, pos):\n        return False',
           '    if False:\n        return False', _PE_UNIT),
    Mutant('pe-today-beyond-reach', 'the passage is not beyond heading reach (sections.beyond_heading_reach)', _PE_DETECT,
           '    return not marks.beyond[line_start]', '    return True', _PE_UNIT),
    # --- amendment_20261101_cycle1_b: the head must NAME the family (one head, read by PE here and PI's S1) ---
    Mutant('pe-head-family', "a routing-only reach counts only for a family the document's head names (routing's own "
           'names in its title lines and procedure fields)', _PE_DETECT,
           '    if not _pe_head_names(an, table):\n        return False',
           '    if False:\n        return False', _PE_UNIT),
    Mutant('pe-head-span-body', "the head's procedure fields never reach past the body's first heading", _PE_DETECT,
           "                break  # the body's first heading: nothing after it is the head's",
           "                pass  # the body's first heading: nothing after it is the head's", _PE_UNIT),
)
# --- package PI: the inventory (detector tests.test_gi4_pi; moved here from tests/test_gi4_pi_mutants.py, which now
# checks this slice; its (name, guard, path, old, new, detector) tuples are Mutant records here) ---
_PI_UNIT = 'unit:tests.test_gi4_pi'
PI_MUTANTS = (
    Mutant('pi-reach-head', 'the reach and E1 need a STRONG procedure report head (Wave 1 repair: '
           'detect.todays_procedure_report replaces sections.procedure_report_head)', 'studio/gi/services.py',
           '    return detect.todays_procedure_report(text) and not _sections.around_procedure_title(text)',
           '    return not _sections.around_procedure_title(text)', _PI_UNIT),
    Mutant('pi-reach-around-title', 'the reach and E1 are never read in a note written around a procedure',
           'studio/gi/services.py',
           '    return detect.todays_procedure_report(text) and not _sections.around_procedure_title(text)',
           '    return detect.todays_procedure_report(text)', _PI_UNIT),
    Mutant('pi-reach-occurrence', "the reach is read only inside today's procedure narrative (Wave 1 repair: the shared "
           'copy guards, which read under_another_occurrence now)', 'studio/gi/services.py',
           '    if not detect.in_todays_narrative(original, pos, service_date, (ss, se)):\n        return False',
           '    if False:\n        return False', _PI_UNIT),
    Mutant('pi-reach-date', 'the reach is never read in a clause carrying a date', 'studio/gi/services.py',
           '                    if own_report[0] and not _dates_in(dates, cs, ce) \\',
           '                    if own_report[0] \\', _PI_UNIT),
    Mutant('pi-carry-part', 'a paragraph carries its service within its own part only', 'studio/gi/services.py',
           "    if part_start != part.start or part.kind in ('history', 'plan', 'indication'):",
           "    if part.kind in ('history', 'plan', 'indication'):", _PI_UNIT),
    Mutant('pi-carry-part-kind', 'never into a history, plan or indication part', 'studio/gi/services.py',
           "    if part_start != part.start or part.kind in ('history', 'plan', 'indication'):",
           '    if part_start != part.start:', _PI_UNIT),
    Mutant('pi-carry-performed', 'the carried family is one documented performed', 'studio/gi/services.py',
           '    if len(done) < 2 or family not in done:', '    if len(done) < 2:', _PI_UNIT),
    Mutant('pi-carry-region', 'every site the statement names is one the carried family reaches', 'studio/gi/services.py',
           '    if named and not named <= FAMILY_REGIONS.get(family, frozenset()):', '    if False:', _PI_UNIT),
    Mutant('pi-carry-reach', 'within CARRY_REACH characters', 'studio/gi/services.py',
           'CARRY_REACH = 1500  # A1:', 'CARRY_REACH = 10 ** 9  # A1:', _PI_UNIT),
    Mutant('pi-carry-paragraph', 'no blank line between', 'studio/gi/services.py',
           '    if pos - end > CARRY_REACH or (pos > end and PARAGRAPH_BREAK.search(text, end, pos)):',
           '    if pos - end > CARRY_REACH:', _PI_UNIT),
    Mutant('pi-carry-field', 'never a field or check-box row', 'studio/gi/services.py',
           '                                      field_row=_field_or_box_line(text, ms, me), lesion_carry=lesion_carry)',
           '                                      field_row=False, lesion_carry=lesion_carry)', _PI_UNIT),
    Mutant('pi-carry-two-named', 'a sentence naming two families clears the carry', 'studio/gi/services.py',
           '            elif carrying and named_here:\n                carry = None',
           '            elif False:\n                carry = None', _PI_UNIT),
    Mutant('pi-e1-section', 'E1: never from a history or plan section of the layout', 'studio/gi/services.py',
           "        if _sections.layout(t).section_at(pos).kind in ('history', 'plan'):\n            return True",
           '        if False:\n            return True', _PI_UNIT),
    Mutant('pi-e1-occurrence', "E1: only inside today's procedure narrative (Wave 1 repair: the shared copy guards, which "
           'read under_another_occurrence now)', 'studio/gi/services.py',
           '        if text and not _pi_todays_statement(text, span):', '        if False:', _PI_UNIT),
    Mutant('pi-e1-extent-word', 'E1: never from a statement carrying an extent word', 'studio/gi/services.py',
           '        if EXTENT_WORD.search(span.text) or (text and _pi_not_today_place(text, span.start)):',
           '        if text and _pi_not_today_place(text, span.start):', _PI_UNIT),
    Mutant('pi-e1-occurrence-word', 'E1: never a landmark an earlier-occurrence word leads in its statement',
           'studio/gi/services.py',
           '            if any(not _sections.ANOTHER_OCCURRENCE_HEAD.search(span.text, 0, m.start())\n'
           '                   for m in pattern.finditer(span.text)):',
           '            if any(True for m in pattern.finditer(span.text)):', _PI_UNIT),
    Mutant('pi-office-visit', 'the reach and E1 are never read in an office visit note (routing reads the visit done)',
           'studio/gi/services.py',
           "    if visit is not None and visit.status in POSITIVE:\n        return False",
           '    if False:\n        return False', _PI_UNIT),
    Mutant('pi-e1-routing-positive', "E1: never where routing reads the family done today", 'studio/validation/checks.py',
           '                    and (finding is None or finding.status not in POSITIVE):', '                    and True:', _PI_UNIT),
    Mutant('pi-w1-another-stent', 'W1: dropped only beside another stent performed (hold-only)', 'studio/gi/services.py',
           "            if any(a.kind == 'stent' and a.status == 'performed' and a.id not in phantom for a in d.acts):",
           '            if True:', _PI_UNIT),
    # --- GI round 4 Wave 1 repair, cycle 1 ---
    Mutant('pi-reach-family', 'S1 reads a reach only for a family the head NAMES (amendment_20261101_cycle1_b: positive '
           "evidence, replacing cycle 1's hold-only 'the head excludes')", 'studio/gi/services.py',
           '    if family not in _pi_head_families(original):\n        return False',
           '    if False:\n        return False', _PI_UNIT),
    Mutant('pi-carry-lesion', "A1: a carry the paragraph's lesion carry stands against holds (a misbinding never binds)",
           'studio/gi/services.py',
           "        return ''  # GI round 4 Wave 1 repair (F5): the lesion carry is another family's - hold, never bind",
           "        pass  # GI round 4 Wave 1 repair (F5): the lesion carry is another family's - hold, never bind",
           _PI_UNIT),
    Mutant('pi-carry-lesion-paragraph', 'A1: the lesion carry stands only within its paragraph (no blank line between)',
           'studio/gi/services.py', '        return False  # a blank line: the paragraph, and its lesion carry, ended',
           '        pass  # a blank line: the paragraph, and its lesion carry, ended', _PI_UNIT),
    # --- amendment_20261101_cycle1_c ---
    Mutant('pi-carry-lesion-heading', 'A1: the lesion carry lapses at a line written as a heading between it and the act',
           'studio/gi/services.py', '    return not _pi_heading_between(text, end, pos)', '    return True', _PI_UNIT),
)
# --- package PO: second-review offers, the amendment A1-A5 included (detector tests.test_gi4_po; moved here from
# tests/test_gi4_po_mutants.py, which now checks this slice) ---
_PO_ENGINE = 'studio/validation/engine.py'
_PO_UNIT = 'unit:tests.test_gi4_po'
PO_MUTANTS = (
    Mutant('po-document-head', "PO: the document's head carries a procedure report's own fields (PS guard)",
           _PO_ENGINE, '    return (gi_sections.procedure_report_head(text)\n', '    return (True\n', _PO_UNIT),
    Mutant('po-document-sedation', 'PO A1: a head field labelled sedation or anaesthesia', _PO_ENGINE,
           '            and _po_sedation_field(text)\n', '            and True\n', _PO_UNIT),
    Mutant('po-sedation-label', 'PO A1: the label, not a word anywhere in a head line, names sedation', _PO_ENGINE,
           '    return end > 0 and _PO_SEDATION_FIELD.search(text, 0, end) is not None',
           '    return end > 0 and gi_sections.PROCEDURE_HEAD.search(text, 0, end) is not None', _PO_UNIT),
    Mutant('po-document-around', 'PO: no head line is the title of a note written around a procedure', _PO_ENGINE,
           '            and not gi_sections.around_procedure_title(text)\n', '            and True\n', _PO_UNIT),
    Mutant('po-document-not-done', 'PO A5: no unnamed statement that a procedure was called off or not done',
           _PO_ENGINE, '            and not _po_procedure_not_done(text))', '            and True)', _PO_UNIT),
    Mutant('po-not-done-other', 'PO A5: "no other procedures were performed" says nothing was not done',
           _PO_ENGINE, r'    r"\bno\s+(?!(?:other|further|additional|more|separate|extra|second)\b)(?:[\w-]+\s+){1,2}?"',
           r'    r"\bno\s+(?:[\w-]+\s+){1,2}?"', _PO_UNIT),
    Mutant('po-family-on-title', 'PO A2: routing names the family on a title line of the head', _PO_ENGINE,
           '    if not named:  # A2', '    if not mentions:  # A2', _PO_UNIT),
    Mutant('po-title-before-fields', "PO A2: a title stands before the head's first field line", _PO_ENGINE,
           "                break  # the head's first field line: the title stands before it",
           "                pass  # mutant: the head's fields are read through", _PO_UNIT),
    Mutant('po-unreadable-passage', 'PO: a passage outside the text never reads as saying nothing', _PO_ENGINE,
           '            return False\n        readings.append(', '            continue\n        readings.append(',
           _PO_UNIT),
    Mutant('po1-family-silent', 'PO-1: every mention of the family is silent', _PO_ENGINE,
           '    if all(_po_silent(m.status, m.cues) for m in mentions):  # PO-1', '    if True:  # PO-1', _PO_UNIT),
    Mutant('po1-evidence-says-nothing', "PO-1: no passage of the item reads as not today or doubted", _PO_ENGINE,
           '        return all(_po_says_nothing(status, cues) for _, status, cues in readings)',
           '        return True', _PO_UNIT),
    Mutant('po2-family-contradicts', 'PO-2: no mention of the family contradicts', _PO_ENGINE,
           '        return False\n    if not any(_po_on_title(titles, pos)',
           '        continue\n    if not any(_po_on_title(titles, pos)', _PO_UNIT),
    Mutant('po2-evidence-on-title', "PO A3: a passage of the item on a title line says nothing", _PO_ENGINE,
           '    if not any(_po_on_title(titles, pos) and _po_says_nothing(status, cues)\n'
           '               for pos, status, cues in readings):  # A3',
           '    if False:  # A3', _PO_UNIT),
    Mutant('po2-at-least-one', "PO-2: at least one passage of the item is a runaway section's", _PO_ENGINE,
           '    return any(runaway) and all(', '    return all(', _PO_UNIT),
    Mutant('po-says-nothing-worded', 'PO: a worded doubt says something', _PO_ENGINE,
           '    return status == \'uncertain\' and bool(cues) and all(\n'
           '        c.startswith((checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX, checks.SILENT_CUE_PREFIX))\n'
           '        or c == UNESTABLISHED for c in cues)',
           "    return status == 'uncertain'", _PO_UNIT),
    Mutant('po2-another-occasion-clean', "PO-2: another occasion's mention carries no doubt or denial", _PO_ENGINE,
           '    return any(c.startswith(_PO_OWN_TIME) for c in cues) and all(\n'
           '        c.startswith(_PO_OWN_TIME + (checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX)) for c in '
           'cues)',
           '    return any(c.startswith(_PO_OWN_TIME) for c in cues)', _PO_UNIT),
    Mutant('po-runaway-section-only', 'PO-2: the not-today reading takes its time only from its section', _PO_ENGINE,
           '            or not all(c.startswith((checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX)) for c in '
           'cues) \\\n            or not any(c.startswith(checks.SECTION_CUE_PREFIX) for c in cues):',
           '            or False:', _PO_UNIT),
    Mutant('po-runaway-within-reach', "PO-2: the section's heading lies within the helper's reach", _PO_ENGINE,
           "    if lo < 0 or lo >= pos or pos - lo > gi_sections.HEADING_REACH_CHARS \\\n"
           "            or text.count('\\n', lo, pos) > gi_sections.HEADING_REACH_LINES:",
           '    if lo < 0 or lo >= pos:', _PO_UNIT),
    Mutant('po-runaway-unread-heading', 'PO-2: an unread heading-like line stands between heading and passage',
           _PO_ENGINE, '    return (gi_sections.beyond_heading_reach(text, lay, pos)\n', '    return (True\n', _PO_UNIT),
    Mutant('po-runaway-occurrence', 'PO-2: the nearest short line above names no other occurrence', _PO_ENGINE,
           '            and not gi_sections.under_another_occurrence(text, pos)\n', '            and True\n', _PO_UNIT),
    Mutant('po-runaway-occurrence-between', 'PO A4: no unread heading-like line within the reach names another '
           'occurrence', _PO_ENGINE, '            and not _po_unread_line_names_another_occurrence(text, lo, pos))',
           '            and True)', _PO_UNIT),
)
MUTANTS += PD_MUTANTS + PV1_MUTANTS + PE_MUTANTS + PI_MUTANTS + PO_MUTANTS
# Every round-4 package's mutants by name prefix (the census in tests/test_gi4_mutants.py holds each exactly once);
# the rest are stage A's own (H1's controls, H2's gates, H4's agreement guard, H5's state guards).
PACKAGE_PREFIXES = {'PS': ('ps-',), 'PA': ('pa-',), 'PD': ('pd-',), 'PV1': ('pv1-',), 'PE': ('pe-',), 'PI': ('pi-',),
                    'PO': ('po-', 'po1-', 'po2-')}
STAGE_A_PREFIXES = ('ctl-', 'freeze-', 'battery-', 'state-')
REPLAY_CONTROLS = ('ctl-date-charge-answer', 'ctl-routing-elsewhere-order', 'ctl-request-date-line')
BY_NAME = {m.name: m for m in MUTANTS}


@contextlib.contextmanager
def applied(tree, name: str, scratch: Path):
    """A copy of ``tree`` (the cpt-studio directory of a sealed export) with mutant ``name`` applied; yields the copy's
    path. Prints the sha256 after applying and after restoring; the copy is removed afterwards."""
    mutant = BY_NAME[name]
    source = Path(tree)
    copy_root = scratch / f'mutant-{name}-{os.getpid()}'
    if copy_root.exists():
        boot.unseal(copy_root)
        shutil.rmtree(copy_root)
    shutil.copytree(source, copy_root / 'cpt-studio', symlinks=True)
    boot.unseal(copy_root)
    target = copy_root / 'cpt-studio' / mutant.path
    original = target.read_bytes()
    before = boot.sha256_file(target)
    text = original.decode('utf-8')
    count = text.count(mutant.old)
    if count != 1:
        shutil.rmtree(copy_root)
        raise RuntimeError(f'[{name}] anchor found {count} times (expected exactly 1): NOT RUN')
    mutated = text.replace(mutant.old, mutant.new, 1)
    marker = mutant.new
    target.write_text(mutated, encoding='utf-8')
    applied_ok = marker in target.read_text(encoding='utf-8')
    print(f'[{name}] mutation applied: {applied_ok}; sha256 {before[:16]} -> {boot.sha256_file(target)[:16]} '
          f'({mutant.path})', flush=True)
    if not applied_ok:
        shutil.rmtree(copy_root)
        raise RuntimeError(f'[{name}] the mutation did not apply: NOT RUN')
    try:
        yield copy_root / 'cpt-studio'
    finally:
        target.write_bytes(original)
        after = boot.sha256_file(target)
        print(f'[{name}] restored: {after == before} (sha256 {after[:16]})', flush=True)
        shutil.rmtree(copy_root)
        if after != before:
            raise RuntimeError(f'[{name}] the restore does not match the original bytes')


def _django_env(state: bool, scratch: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP')}
    env.update(boot.OFFLINE_ENV)
    env.update({'PYTHONDONTWRITEBYTECODE': '1', 'CPT_STUDIO_STATE_DIR': str(scratch)})
    if state:  # the throwaway test database: never the live port
        env.update({'CPT_STUDIO_DB_PORT': '55461', 'CPT_STUDIO_TEST_DB_SUFFIX': 'gi4mut'})
    else:  # no database at all: a closed port, so any query fails loudly
        env.update({'CPT_STUDIO_DB_PORT': '9', 'CPT_STUDIO_TEST_DB_SUFFIX': 'gi4none'})
    assert env['CPT_STUDIO_DB_PORT'] != boot.LIVE_DB_PORT
    return env


def detect(mutant: Mutant, tree: Path, base: Path, scratch: Path) -> tuple[bool, str]:
    """(failed, tail of the output) for the mutant's detector on ``tree`` (``base``: the unmutated tree)."""
    kind, _, label = mutant.detector.partition(':')
    if kind in ('unit', 'state'):
        cmd = [sys.executable, '-B', 'manage.py', 'test', label, '--noinput']
        done = subprocess.run(cmd, cwd=tree, env=_django_env(kind == 'state', scratch), capture_output=True,
                              text=True, timeout=3600)
    else:
        args = {'replay': ['--fixtures'], 'freeze': ['--quick'], 'battery': []}[kind]
        cmd = [sys.executable, '-B', '-m', f'ops.gi4.{kind}', '--base', str(base), '--head', str(tree), *args,
               '--scratch', str(scratch)]
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP')}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        done = subprocess.run(cmd, cwd=boot.HARNESS_TREE, env=env, capture_output=True, text=True, timeout=3600)
    tail = (done.stdout + done.stderr).strip().splitlines()[-12:]
    return done.returncode != 0, '\n'.join(tail)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m ops.gi4.mutants')
    parser.add_argument('--base', required=True, help='git ref or cpt-studio directory to mutate copies of')
    parser.add_argument('--only', nargs='*', default=())
    parser.add_argument('--scratch')
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args(argv)
    if args.list:
        for m in MUTANTS:
            print(f'{m.name:36s} {m.detector:34s} {m.guard}')
        return 0
    scratch = boot.scratch_dir(args.scratch)
    base = Path(args.base).resolve() if Path(args.base).is_dir() else boot.export_ref(args.base, scratch)
    chosen = [m for m in MUTANTS if not args.only or m.name in args.only]
    baselines, results = {}, []
    for mutant in chosen:
        t0 = time.time()
        if mutant.detector not in baselines:
            failed, tail = detect(mutant, base, base, scratch)
            baselines[mutant.detector] = not failed
            print(f'baseline {mutant.detector}: {"passes" if not failed else "FAILS (its mutants prove nothing)"}')
            if failed:
                print(tail)
        if not baselines[mutant.detector]:
            results.append((mutant.name, 'NOT RUN (failing baseline)'))
            continue
        try:
            with applied(base, mutant.name, scratch) as tree:
                failed, tail = detect(mutant, tree, base, scratch)
        except RuntimeError as exc:
            results.append((mutant.name, f'NOT RUN: {exc}'))
            continue
        verdict = 'KILLED' if failed else 'SURVIVED'
        results.append((mutant.name, verdict))
        print(f'[{mutant.name}] {verdict} by {mutant.detector} in {time.time() - t0:.0f}s')
        if not failed:
            print(tail)
    print('\n== mutant battery')
    for name, verdict in results:
        print(f'  {name:36s} {verdict}')
    killed = sum(v == 'KILLED' for _, v in results)
    print(f'  {killed} of {len(results)} killed')
    return 0 if killed == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
