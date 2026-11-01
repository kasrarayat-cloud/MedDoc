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
           '    return bool(_pa_unread_heading(text, reading.start))\n',  # Wave 1 repair cycle 1: the real unread heading
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
           'studio/validation/engine.py', '    if line == _PA_FAR:\n',  # Wave 1 repair cycle 1: moved into _pa_reach
           '    if False:\n', 'unit:tests.test_gi4_pa'),
    # --- package PA, Wave 1 repair cycle 1 (pa.json amendment_20261101_r2; refutations F6, CTS-3, CTS-4): only a REAL
    # unread heading makes the section's reading one cause, and the act path's one-cause hold says why ---
    Mutant('pa-real-first-line', "a real unread heading is never the section's first line under its heading",
           'studio/validation/engine.py',
           '    if start == first or _pa_name_line(line) or _pa_procedure_name_line(line):\n',
           '    if _pa_name_line(line) or _pa_procedure_name_line(line):\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-real-procedure-name', 'a bare procedure name is an entry of a history, never a heading',
           'studio/validation/engine.py',
           '    if start == first or _pa_name_line(line) or _pa_procedure_name_line(line):\n',
           '    if start == first or _pa_name_line(line):\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-procedure-only-words', 'a bare procedure name says nothing but connectors, acts and qualifiers',
           'studio/validation/engine.py',
           "    return named and all(w.lower() in _PA_PROCEDURE_WORDS for w in gi_sections._HEADING_WORD.findall(''.join("
           "rest)))\n",
           '    return named\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-procedure-named', 'a bare procedure name names a service the documented-service reader names',
           'studio/validation/engine.py',
           "    return named and all(w.lower() in _PA_PROCEDURE_WORDS for w in gi_sections._HEADING_WORD.findall(''.join("
           "rest)))\n",
           "    return all(w.lower() in _PA_PROCEDURE_WORDS for w in gi_sections._HEADING_WORD.findall(''.join(rest)))\n",
           'unit:tests.test_gi4_pa'),
    Mutant('pa-real-bounded-above', 'a real heading is bounded above: never a list entry under another or a sentence it '
           'continues', 'studio/validation/engine.py',
           '    if not _pa_bounded_above(text[above:start - 1].strip()):\n        return False\n',
           '    if False:\n        return False\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-real-bounded-field', 'a field line bounds a heading above it', 'studio/validation/engine.py',
           "    return not line or line[-1] in '.!?' or gi_sections._TITLE_FIELD.search(line) is not None\n",
           "    return not line or line[-1] in '.!?'\n", 'unit:tests.test_gi4_pa'),
    Mutant('pa-real-content', 'a real heading is followed by content, never by another short entry',
           'studio/validation/engine.py', '    return not after or _pa_content(after)\n', '    return True\n',
           'unit:tests.test_gi4_pa'),
    Mutant('pa-real-content-sentence', 'a sentence is content a heading heads', 'studio/validation/engine.py',
           "    return len(line) > 60 or line[-1] in '.!?' or gi_sections._TITLE_FIELD.search(line) is not None \\\n",
           '    return len(line) > 60 or gi_sections._TITLE_FIELD.search(line) is not None \\\n',
           'unit:tests.test_gi4_pa'),
    Mutant('pa-name-page', "a page's running number is never a heading", 'studio/validation/engine.py',
           '    return _PA_PAGE_LINE.fullmatch(bare) is not None or _PA_CREDENTIAL.search(bare) is not None \\\n',
           '    return _PA_CREDENTIAL.search(bare) is not None \\\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-name-credential', "a provider's name with a credential is never a heading", 'studio/validation/engine.py',
           '    return _PA_PAGE_LINE.fullmatch(bare) is not None or _PA_CREDENTIAL.search(bare) is not None \\\n',
           '    return _PA_PAGE_LINE.fullmatch(bare) is not None \\\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-name-title', "a provider's name after a title is never a heading", 'studio/validation/engine.py',
           '        or _PA_TITLE_PREFIX.match(bare) is not None or _PA_FACILITY.search(bare) is not None\n',
           '        or _PA_FACILITY.search(bare) is not None\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-name-facility', "a facility's name is never a heading", 'studio/validation/engine.py',
           '        or _PA_TITLE_PREFIX.match(bare) is not None or _PA_FACILITY.search(bare) is not None\n',
           '        or _PA_TITLE_PREFIX.match(bare) is not None\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-name-aside', 'an aside in brackets at the end of a name line is read past', 'studio/validation/engine.py',
           "    bare = _PA_TRAILING_ASIDE.sub('', line).strip()\n", '    bare = line\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-occurrence-governs', 'the nearest heading-like line naming another occurrence dates the passage: the '
           'agreement stands', 'studio/validation/engine.py',
           "            if gi_sections.ANOTHER_OCCURRENCE_HEAD.search(line):\n                return ''  # the passage",
           "            if False:\n                return ''  # the passage", 'unit:tests.test_gi4_pa'),
    Mutant('pa-one-cause-hold-words', "the act path's one-cause hold says why, not the act_missing words",
           'studio/validation/engine.py',
           '            found = _pa_one_cause_hold(found, outcome, code, text, day, pages)\n', '            pass\n',
           'unit:tests.test_gi4_pa'),
    Mutant('pa-one-cause-hold-acts-here', "a hold a documented act of the code's kind decides keeps its words",
           'studio/validation/engine.py',
           '            or _acts_in_passage(code, decisive, found.service):\n        return found\n',
           '            or False:\n        return found\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-one-cause-hold-only', 'only the one-cause disagreement takes the one-cause words',
           'studio/validation/engine.py', '    if not why.startswith(_PA_ONE_CAUSE):\n        return found\n',
           '    if False:\n        return found\n', 'unit:tests.test_gi4_pa'),
    Mutant('pa-unread-far-lines', 'past HEADING_REACH_LINES lines read, the real-heading rule still fails closed',
           'studio/validation/engine.py', '        end = start - 1\n    return _PA_FAR\n',
           "        end = start - 1\n    return ''\n", 'unit:tests.test_gi4_pa'),
    Mutant('pa-unread-far-chars', 'a line begun before the characters read fails closed', 'studio/validation/engine.py',
           '            return _PA_FAR  # a line begun before the characters read: fail-closed\n',
           "            return ''  # mutant: a line begun before the characters read\n", 'unit:tests.test_gi4_pa'),
    Mutant('pa-unread-far-floor', 'past HEADING_REACH_CHARS characters read, the real-heading rule still fails closed',
           'studio/validation/engine.py', "            return _PA_FAR if floor > lo else ''\n", "            return ''\n",
           'unit:tests.test_gi4_pa'),
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
    Mutant('pd-plain-apart', 'the installed candidates are read apart from the wide ones', _PD_CONTEXT,
           '    return plain + tuple(c for c in joint if c.wide)\n', '    return joint\n', _PD_UNIT),
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
    # --- the Wave 1 repair (PD, cycle 1; DS-1 to DS-4, CTS-5): one killing mutant per guard of rule (c)'s narrowing,
    # rule (a)'s scope and quotes, and the quoted span (pd.json amendment_20261101) ---
    Mutant('pd-rule-a-asks-around', 'rule (a) never asks under a title of a note written around a procedure (PS rule)', _PD_CONTEXT,
           '        differing = [c for c in wide if c.value != fact.value and c.asks]\n',
           '        differing = [c for c in wide if c.value != fact.value]\n', _PD_UNIT),
    Mutant('pd-around-broadened', 'rule (c) narrows nothing in a note around a procedure: the broadened detection, not the PS title rule alone', _PD_CONTEXT,
           '    if _pd_around_procedure(text) or _PD_COPIED.search(text) or _PD_ADDENDUM.search(text, head_end):\n',
           '    if around_procedure_title(text) or _PD_COPIED.search(text) or _PD_ADDENDUM.search(text, head_end):\n', _PD_UNIT),
    Mutant('pd-around-kind-field', 'the broadened detection reads a kind field ("Note type: Telephone")', _PD_CONTEXT,
           "                if kind is not None:\n                    if _PD_AROUND_WORDS.search(kind.group('value')):\n",
           "                if False:\n                    if _PD_AROUND_WORDS.search(kind.group('value')):\n", _PD_UNIT),
    Mutant('pd-around-cells', "the broadened detection reads a flattened line's cells as titles", _PD_CONTEXT,
           '            for cell in _FIELD_BREAK.split(text[start:line_end]):\n',
           '            for cell in (text[start:line_end],):\n', _PD_UNIT),
    Mutant('pd-around-head-lines', "the broadened detection reads the head's first TITLE_LINES lines, not six", _PD_CONTEXT,
           '    end, start = head_lines_end(text, TITLE_LINES), 0\n',
           '    end, start = head_lines_end(text, 6), 0\n', _PD_UNIT),
    Mutant('pd-around-title-chars', 'the broadened detection reads titles up to _PD_TITLE_CHARS characters, not 80', _PD_CONTEXT,
           "                elif len(cell) <= _PD_TITLE_CHARS and cell[-1] not in '.!?;,' and re.search(r':[ \\t]*\\S', cell) is None \\\n",
           "                elif len(cell) <= 80 and cell[-1] not in '.!?;,' and re.search(r':[ \\t]*\\S', cell) is None \\\n", _PD_UNIT),
    Mutant('pd-own-not-cosign', "a co-signature or a transcription line is never the author's own sign-off", _PD_CONTEXT,
           '        if _PD_NOT_CLOSING.search(text, start, line_end) or _PD_NOT_OWN.search(text, start, line_end):\n',
           '        if _PD_NOT_CLOSING.search(text, start, line_end):\n', _PD_UNIT),
    Mutant('pd-not-closing-words', 'a consent, order, request, booking or call line is never a sign-off', _PD_CONTEXT,
           '        if _PD_NOT_CLOSING.search(text, start, line_end) or _PD_NOT_OWN.search(text, start, line_end):\n',
           '        if _PD_NOT_OWN.search(text, start, line_end):\n', _PD_UNIT),
    Mutant('pd-signoff-names-performer', "every sign-off verb counts only when the line names the performer the head names", _PD_CONTEXT,
           "            continue  # signed or attested by anyone the head does not name as the note's performer or author\n",
           '            pass  # mutant: any signer signs\n', _PD_UNIT),
    Mutant('pd-performer-whole-name', "the head performer's surname ends the signer's name", _PD_CONTEXT,
           "                continue  # the signer's name goes on past this surname: another person's\n",
           '                pass  # mutant: any word may follow the surname\n', _PD_UNIT),
    Mutant('pd-performer-first-name', "the name words before the surname agree with the head's first name", _PD_CONTEXT,
           '            if not first or _pd_first_name_agrees(line[max(0, m.start() - _PD_NAME_BACK):m.start()], first):\n',
           '            if True:\n', _PD_UNIT),
    Mutant('pd-signoff-short-line', 'a sign-off line is at most _PD_QUOTE_CHARS characters', _PD_CONTEXT,
           '        if start < region or not stated or line_end - start > _PD_QUOTE_CHARS:\n',
           '        if start < region or not stated:\n', _PD_UNIT),
    Mutant('pd-attest-sole-line', "a line that only attests signs only as the closing region's sole closing-role line", _PD_CONTEXT,
           '    if attests and not verbs and signers > 1:\n', '    if False:\n', _PD_UNIT),
    Mutant('pd-dictated-only', 'a dictation line alone is no sign-off', _PD_CONTEXT,
           '            continue  # a dictation line alone\n',
           '            pass  # mutant: a dictation line alone signs\n', _PD_UNIT),
    Mutant('pd-closing-days-agree', 'every closing-role day after the head agrees with the sign-off day', _PD_CONTEXT,
           '    return next(iter(own)) if len(own) == 1 and days == own else None\n',
           '    return next(iter(own)) if len(own) == 1 else None\n', _PD_UNIT),
    Mutant('pd-region-not-head', "the closing region never reaches into the head (a short document's head is no closing)", _PD_CONTEXT,
           '    region = max(_pd_closing_start(text), head_end)\n    own, days, line_end, performers = set(), set(), -1, None\n'
           '    signers, verbs, attests = 0, False, False  # the closing region\'s closing-role lines; how the own sign-off signs\n'
           '    for m in _CLOSING_ROLE.finditer(text, head_end):\n',
           '    region = _pd_closing_start(text)\n    own, days, line_end, performers = set(), set(), -1, None\n'
           '    signers, verbs, attests = 0, False, False  # the closing region\'s closing-role lines; how the own sign-off signs\n'
           '    for m in _CLOSING_ROLE.finditer(text, region):\n', _PD_UNIT),
    Mutant('pd-closing-last-lines', "the author's sign-off is read only among the last 8 non-empty lines", _PD_CONTEXT,
           '    region = max(_pd_closing_start(text), head_end)\n',
           '    region = head_end\n', _PD_UNIT),
    Mutant('pd-no-addendum', 'no narrowing with an addendum line after the head', _PD_CONTEXT,
           '    if _pd_around_procedure(text) or _PD_COPIED.search(text) or _PD_ADDENDUM.search(text, head_end):\n',
           '    if _pd_around_procedure(text) or _PD_COPIED.search(text):\n', _PD_UNIT),
    Mutant('pd-no-call-phrase', 'no narrowing where the document states a call, a phone contact or a message', _PD_CONTEXT,
           '    if _PD_CALL_PHRASE.search(text):\n', '    if False:\n', _PD_UNIT),
    Mutant('pd-no-copied-text', 'no narrowing with a line announcing copied, pasted or attached text', _PD_CONTEXT,
           '    if _pd_around_procedure(text) or _PD_COPIED.search(text) or _PD_ADDENDUM.search(text, head_end):\n',
           '    if _pd_around_procedure(text) or _PD_ADDENDUM.search(text, head_end):\n', _PD_UNIT),
    Mutant('pd-signoff-not-under-occurrence', "the sign-off is not under a heading naming another occurrence's record", _PD_CONTEXT,
           "        if under_another_occurrence(text, start):\n            return None  # a copied block's signature\n",
           "        if False:\n            return None  # a copied block's signature\n", _PD_UNIT),
    Mutant('pd-every-candidate-narrows', 'every wide or worded candidate narrows: exactly one value, never several', _PD_CONTEXT,
           '    if all(c.narrows for c in wide) and len(wide) == sum(1 for c in found if c.wide):\n',
           '    if any(c.narrows for c in wide) and len(wide) == sum(1 for c in found if c.wide):\n', _PD_UNIT),
    Mutant('pd-no-wide-in-doubt', 'no wide label is in doubt (birth, part, order) or read elsewhere beside the narrowed ones', _PD_CONTEXT,
           '    if all(c.narrows for c in wide) and len(wide) == sum(1 for c in found if c.wide):\n',
           '    if all(c.narrows for c in wide):\n', _PD_UNIT),
    Mutant('pd-procedure-label-head', "a label naming a procedure's occurrence narrows only in a procedure's own report", _PD_CONTEXT,
           '                              and (not procedural or report_head)))\n', '                              ))\n', _PD_UNIT),
    Mutant('pd-label-alone', "a narrowing label's date stands alone in its field", _PD_CONTEXT,
           '                              narrows=alone and signoff == value.isoformat()\n',
           '                              narrows=signoff == value.isoformat()\n', _PD_UNIT),
    Mutant('pd-clean-line-dates', "a narrowing label's line states no other date-shaped text", _PD_CONTEXT,
           '    return _PD_OTHER_DATE.search(text, ls, start) is None and _PD_OTHER_DATE.search(text, end, le) is None\n',
           '    return True\n', _PD_UNIT),
    Mutant('pd-clean-line-length', "a narrowing label's line is short and names no addendum", _PD_CONTEXT,
           "    if le - ls > _PD_QUOTE_CHARS or re.search(r'\\baddend', text[ls:le], re.I):\n        return False\n",
           '    if False:\n        return False\n', _PD_UNIT),
    Mutant('pd-quoted-limits-nothing', 'a quoted line limits no member answer (every date taken, as installed)', _PD_CONTEXT,
           '                and documented.evidence and _limits_answers(documented):  # Wave 1 repair (PD): a quoted line limits none\n',
           '                and documented.evidence:\n', _PD_UNIT),
    Mutant('pd-rule-a-whole-line', "rule (a)'s note quotes each differing label's whole line (CTS-5)", _PD_CONTEXT,
           "            wide=', '.join(list(dict.fromkeys(c.quote for c in differing))[:3]),\n",
           "            wide=', '.join('\\u201c' + ' '.join(c.span.text.split()) + '\\u201d' for c in differing[:3]),\n", _PD_UNIT),
    Mutant('pd-quote-only-whole-line', "rule (c)'s quoted evidence is the label's whole line", _PD_CONTEXT,
           "    lines = list({c.line_at: c.line for c in reversed(wide)}.values())  # each line once (its first label's span)\n",
           "    lines = list({c.line_at: c.span for c in reversed(wide)}.values())  # each line once (its first label's span)\n", _PD_UNIT),
    Mutant('pd-wide-never-own', "a narrowed wide label is never the note's own date (never sent)", _PD_CONTEXT,
           "        return Fact('service_date', None, 'missing', _sorted_spans(lines), WIDE_DATE_NOTE)\n",
           "        return Fact('service_date', wide[0].value, 'document', _sorted_spans(lines), WIDE_DATE_NOTE)\n", _PD_UNIT),
    # --- the integration of Wave 1 repair cycle 1: the STRONG-HEAD HOLD (pd.json amendment_20261101_integration), one
    # killing mutant per guard of the hold: the hold itself, the strong head (never PS's weak one), the one-date field,
    # no note around a procedure (rule (c)'s broadened detection, a call or a message stated), and its notes ---
    Mutant('pd-head-hold', "a member's answer of another day than a procedure report's own head gives is held", _PD_CONTEXT,
           "    if isinstance(documented, _HeadHeldFact) and answer is not None and answer.origin == 'user' \\\n",
           "    if False and isinstance(documented, _HeadHeldFact) and answer is not None and answer.origin == 'user' \\\n",
           _PD_UNIT),
    Mutant('pd-head-strong', "only the strong head holds (detect.todays_procedure_report, never PS's procedure_report_head)",
           _PD_CONTEXT, '    if not detect.todays_procedure_report(text):\n        return None\n    if _pd_around_procedure(text):\n',
           '    if not (procedure_report_head(text) and detect._gi4_head(text).own_dates):\n        return None\n'
           '    if _pd_around_procedure(text):\n', _PD_UNIT),
    Mutant('pd-head-one-date', "the head's own-date field gives exactly one date", _PD_CONTEXT,
           '            if _PD_OTHER_DATE.search(text, m.end(), brk.start() if brk else line_end) is not None:\n',
           '            if False:\n', _PD_UNIT),
    Mutant('pd-head-around', 'no hold in a note written around a procedure (the broadened detection)', _PD_CONTEXT,
           '    if _pd_around_procedure(text):\n        return None  # a booking, a call, a consent',
           '    if False:\n        return None  # a booking, a call, a consent', _PD_UNIT),
    Mutant('pd-head-call', 'no hold where the document states a call, a phone contact or a message', _PD_CONTEXT,
           '    if _PD_CALL_PHRASE.search(text) is not None:\n        return None  # a call or a message written as an event',
           '    if False:\n        return None  # a call or a message written as an event', _PD_UNIT),
    Mutant('pd-head-note', "the hold's fact says which answers are held (never 'a member's date is taken')", _PD_CONTEXT,
           '            note = HEAD_DATE_NOTE.format(day=day, head=quote, also=also)\n',
           '            pass  # mutant: the note as made\n', _PD_UNIT),
    Mutant('pd-head-charge-note', "rule (a)'s question says the date it keeps is held too", _PD_CONTEXT,
           '            note = fact.note + _HEAD_CHARGE_NOTE.format(day=day, own=own)\n',
           '            note = fact.note\n', _PD_UNIT),
)
# --- package PV1: E/M reading fixes and the C4 holds (detectors tests.test_gi4_pv1 and, for repair cycle 1's guards,
# tests.test_gi4_pv1_cycle1; moved here from tests/test_gi4_pv1_mutants.py, which now checks this slice). Repair cycle 1
# (2026-11-01) re-anchored the guards whose code it rewrote, removed pv1-c2-opens-sentence and pv1-quote-window (their
# guards are gone: a refused label is no mention, so it is never quoted) and added one mutant per guard it adds ---
_PV1_DETECT, _PV1_CUES, _PV1_CHECKS = 'studio/gi/detect.py', 'studio/gi/cues.py', 'studio/validation/checks.py'
_PV1_UNIT = 'unit:tests.test_gi4_pv1'
_PV1_CYCLE1 = 'unit:tests.test_gi4_pv1_cycle1'
_PV1_HOLD = "        return Reading('uncertain', (f\"{EM_NOT_IN_PERSON}: '{words}'\",), 'cue', doubt=True)"
_PV1_TIME_ONLY = "    if m.kind != 'em-time':\n        return None\n    return cues.EM_TIME_ACTIVITIES"
_PV1_DATES = '    for d in an.dates_in(cs, ce):  # GI round 4 (C1): a date in an activity list still governs (see the docstring)\n'
_PV1_SKIP = '        if activities is not None and cue.start >= activities and _pv1_activity_work(cue):'
_PV1_PLAN_NOUN = '    return noun is not None and noun.match(cue.text) is not None'
_PV1_OTHER_STATEMENTS = "    if m.kind in ('em-time', 'em-mdm'):\n        other = _pv1_other_time(an, m)"
_PV1_CONTACT_PLAN = "    if any(c.status == 'planned' for c in an.cues_in(cs, ce)) or _PV1_PREFERS.search(text, cs, ce):"
_PV1_REVIEWED = ('    return _PV1_ACTIVITY_NOUN.search(text, cut, pos) is not None and _PV1_LIST_TIME.search(text, cut, item_end) '
                 'is None')
_PV1_SCAN = "        for s, e in spans:\n            if an.lay.section_at(s).kind == 'history':"
_PV1_EXAM_TEST = ('        if not _PV1_NO_EXAM.match(rest) and _PV1_EXAM_CONTENT.search(rest) and not '
                  '_PV1_REPORTED.search(rest):')
_PV1_ITEM_BOUND = ('    for count, (x, y) in enumerate(spans[i:i + _PV1_ITEM_MATCHES + 1]):\n        if y > end:\n            break\n'
                   '        if count < _PV1_ITEM_MATCHES and work is not None')
# C4's session-2 synonyms in cues.NOT_IN_PERSON, from their comment to their last alternative (exact source text)
_PV1_SYNONYMS = r'''                   # session 2: "The patient was not seen.", a visit-type field naming the telephone ("Visit type:
                   # Telephone", "Type of encounter: phone"), "missed her appointment", "left without being seen"
                   r'|\b(?:patient|pt|she|he)\s+(?:was|is)\s+not\s+seen\b|\b(?:(?:visit|encounter|appointment|contact|'
                   r'consult(?:ation)?)\s+(?:type|mode|modality|method)|(?:type|mode|modality|method)\s+of\s+(?:visit|'
                   r'encounter|appointment|contact|consult(?:ation)?))[ \t]*[:\-][ \t]*(?:tele)?phone\b'
                   r"|\bmissed\s+(?:her|his|their|the|this|today'?s)\s+(?:scheduled\s+)?(?:appointment|visit)\b"
                   r'|\bleft\s+without\s+being\s+seen\b|\bLWBS\b'
'''
# ... and repair cycle 1's (EMR-8): "on phone", "over phone", "(telephone)", ", telephone." ...
_PV1_PHONE_SYNONYMS = (r'''                   r'|\b(?:by|via|over(?:\s+the)?|on(?:\s+the)?)\s+(?:tele)?phone\b|\((?:by\s+|via\s+)?(?:tele)?phone\)'
                   r'|,[ \t]*(?:tele)?phone(?=[ \t]*(?:[.;]|$))'  # "Total time: 12 minutes, telephone."
''', r'''                   r'|\b(?:by|via|over\s+the|on\s+the)\s+(?:tele)?phone\b'
''')
# ... and the field "Encounter: Telephone" and the attendance synonyms, the pattern's last alternatives
_PV1_ATTENDANCE_SYNONYMS = r'''                   r'|\bleft\s+without\s+being\s+seen\b|\bLWBS\b'
                   # repair cycle 1 (EMR-8): the field "Encounter: Telephone"; a patient who did not show or come in, who
                   # did not keep or who cancelled the appointment - the patient as subject, at the clause's end or
                   # before "for the visit" ("The CT did not show a mass." is no missed visit)
                   r'|^[ \t]*(?:encounter|visit|appointment)[ \t]*:[ \t]*(?:tele)?phone\b'
                   r"|\b(?:patient|pt|she|he|they)\s+(?:did\s+not|didn't|failed\s+to)\s+(?:show|come\s+in)(?:\s+(?:up|"
                   r"today))?(?=[ \t]*(?:[.;,!]|$|for\s+(?:the|her|his|their|this|today'?s)\s+(?:scheduled\s+)?"
                   r'(?:visit|appointment)))'
                   r"|\b(?:did\s+not|didn't|failed\s+to)\s+keep\s+(?:her|his|their|the|this|today'?s)\s+(?:scheduled\s+)?"
                   r'appointment\b'
                   r"|\b(?:patient|pt|she|he|they)\s+cancell?ed\s+(?:her|his|their|the|this|today'?s)\s+(?:scheduled\s+)?"
                   r'(?:appointment|visit)\b', FLAGS | re.M)'''


def _pv1(name, guard, old, new, detector=_PV1_CYCLE1, path=_PV1_DETECT):
    return Mutant(name, guard, path, old, new, detector)


PV1_MUTANTS = (
    # --- Wave 1's guards (re-anchored where repair cycle 1 rewrote their code) ---
    _pv1('pv1-c4-hold', 'C4: a performed E/M reading is held when the note may document no in-person visit',
         '    if words is not None:\n' + _PV1_HOLD, '    if False:\n' + _PV1_HOLD, _PV1_UNIT),
    _pv1('pv1-c4-head', "C4: the head's title lines are read whatever section they fall in (a \"Telephone note\" title "
         'too, which the statement scan reads as a data item)',
         '            for title in cues.NOT_IN_PERSON_TITLE.finditer(text, 0, head):', '            for title in ():'),
    _pv1('pv1-c4-own-sentence', "C4: the E/M statement's own sentence is read in a history section too, and holds the "
         'whole document', '                if cues.TODAY.search(text, cs, ce) is None and not _pv1_em_in(an, '
         '*an.lay.sentence_for(s, e)):', '                if cues.TODAY.search(text, cs, ce) is None:'),
    _pv1('pv1-another-time', "C4-time: installed's _another_time holds a performed E/M time statement",
         '    held = _pv1_another_time(an, m, work)', '    held = None', _PV1_UNIT),
    _pv1('pv1-c2-another-time', 'C4-time and EMR-9: a decision-making statement takes the other-time holds (installed\'s '
         'MDM reading and a read label)', _PV1_OTHER_STATEMENTS,
         _PV1_OTHER_STATEMENTS.replace("m.kind in ('em-time', 'em-mdm')", "m.kind == 'em-time'")),
    _pv1('pv1-c1-after-only', 'C1: a cue before the activity word still re-times the time statement', _PV1_SKIP,
         '        if activities is not None and _pv1_activity_work(cue):', _PV1_UNIT),
    _pv1('pv1-c1-plan-work', 'C1: after the activity word only a planned cue is skipped (a cancellation or a history '
         'still re-times the statement)', _PV1_SKIP, '        if activities is not None and cue.start >= activities:',
         _PV1_UNIT),
    _pv1('pv1-c1-planned-time', 'C1: a planned time after the activity word still re-times the statement (only a noun of '
         "the visit's planning work is skipped)", _PV1_PLAN_NOUN, '    return True', _PV1_UNIT),
    _pv1('pv1-c1-dates-count', 'C1: a date in an activity list still re-times the time statement', _PV1_DATES,
         _PV1_DATES + '        if activities is not None and d.start >= activities:\n            continue\n', _PV1_UNIT),
    _pv1('pv1-c1-time-only', "C1: only a time statement has an activity list (a visit statement's cues count)",
         _PV1_TIME_ONLY, _PV1_TIME_ONLY.replace("if m.kind != 'em-time':", "if m.kind not in ('em-time', 'em-visit'):"),
         _PV1_UNIT),
    _pv1('pv1-c2-shared', '"shared decision making" never gives an MDM level (a label and its separator)',
         r"               r'|\b(?:complexity|level)\s+of\s+decision[- ]making[ \t]*[:\-][ \t]*)'",
         r"               r'|\b(?:\w+\s+)?(?:of\s+)?decision[- ]making\b[^.;\n]{0,60}?)'", _PV1_UNIT, _PV1_CUES),
    _pv1('pv1-v3-ultrasound', "V3: an ultrasound named in an E/M code's negative passage holds the E/M",
         'labs?|ultrasounds?|sonograms?|', 'labs?|sonograms?|', _PV1_UNIT, _PV1_CHECKS),
    _pv1('pv1-c4-synonyms', 'C4 (session 2): "the patient was not seen", a visit-type field naming the telephone, '
         '"missed her appointment" and "left without being seen" hold every E/M reading', _PV1_SYNONYMS, '', _PV1_UNIT,
         _PV1_CUES),
    _pv1('pv1-other-visit', 'C4-time: another visit named by a preposition, with or without a determiner, holds a time '
         'statement', '    other = _pv1_other_visit(an, s, max(e, m.end), label, work)', '    other = None', _PV1_UNIT),
    _pv1('pv1-other-visit-window', 'H7 (session 2): the other-visit quote is cut from a bounded window of its match',
         "        return ' '.join(an.text[x:min(y, x + _PV1_QUOTE_WINDOW)].split())[:_PV1_QUOTE]",
         "        return ' '.join(an.text[x:y].split())[:_PV1_QUOTE]", _PV1_UNIT),
    # --- repair cycle 1: C2, kept only with positive evidence of today's office visit, otherwise not read ---
    _pv1('pv1-c2-drop', 'C2: a label refused its release is no mention at all (installed\'s reading)',
         '    an.em = _pv1_read_labels(an)', '    an.em = an.em'),
    _pv1('pv1-c2-office-visit', "C2: the label is read only where the note documents today's in-person office visit",
         '    why = _pv1_office_visit(an)', '    why = None'),
    _pv1('pv1-c2-kept-c4', 'C2: where C4 holds the document, the visit\'s own label is kept and held with the rest',
         '                 or (held and _pv1_statement_refused(an, m) is None))', '                 or False)'),
    _pv1('pv1-c2-kept-own', 'C2: under C4 only the visit\'s own label is kept (another note\'s is not read)',
         '                 or (held and _pv1_statement_refused(an, m) is None))', '                 or held)'),
    _pv1('pv1-c2-opens-line', 'C2 and C1: the statement must open its own line',
         '    line_start = _pv1_line_start(text, m.start)', "    line_start = text.rfind('\\n', 0, m.start) + 1"),
    _pv1('pv1-c2-history-section', 'C2 and C1: a statement in a history or indication section is not the visit\'s own',
         "    if an.lay.section_at(m.start).kind in ('history', 'indication'):", '    if False:'),
    _pv1('pv1-c2-governing', 'C2 and C1: the heading-like line governing the statement names no other occurrence',
         '    if governing is not None and _pv1_names_another_occurrence(an, *governing):', '    if False:'),
    _pv1('pv1-c2-section-heading', 'C2 and C1: no heading-like line further up the statement\'s section names another '
         'occurrence (a pasted prior note)', '    above = _pv1_section_heading_above(an, m.start, line_start)',
         '    above = None'),
    _pv1('pv1-c2-line-rest', "C2 and C1: the rest of the statement's line names no other visit, time or date",
         '    words = _pv1_names_another_occurrence(an, m.end, line_end, rest=True)', '    words = None'),
    _pv1('pv1-visit-exam', 'visit evidence: an exam or vital signs with content', '    if not _pv1_exam_with_content(text):',
         '    if False:'),
    _pv1('pv1-visit-setting', "visit evidence: the document's own office setting",
         "    if setting.origin != 'document' or setting.value != 'office':", '    if False:'),
    _pv1('pv1-visit-not-a-visit', 'visit evidence: no telephone, portal, message, e-consult, no-show or cancelled word',
         '    words = _pv1_first_signal(an, _PV1_NOT_A_VISIT, everywhere=False)', '    words = None'),
    _pv1('pv1-visit-procedure-day', 'visit evidence: no procedure-day word (H&P, ASA, airway, today\'s colonoscopy)',
         '    words = _pv1_first_signal(an, _PV1_PROCEDURE_DAY, everywhere=True)', '    words = None'),
    _pv1('pv1-visit-around-title', 'visit evidence: no title of a note written around a procedure',
         '    if gi_sections.around_procedure_title(text):', '    if False:'),
    _pv1('pv1-visit-reported', 'visit evidence: reported values or another visit\'s exam are no exam', _PV1_EXAM_TEST,
         '        if not _PV1_NO_EXAM.match(rest) and _PV1_EXAM_CONTENT.search(rest):'),
    _pv1('pv1-c1-office-visit', "C1: the plan-work skip applies only with the visit's evidence and its own statement",
         '    if _pv1_office_visit(an) is not None or _pv1_statement_refused(an, m) is not None:', '    if False:'),
    _pv1('pv1-c1-nouns', "C1: only a noun of the visit's planning work is skipped ('scheduled' is not)",
         "_PV1_PLAN_WORK = {'ordered': re.compile(r'orders?\\Z', re.A | re.I),",
         "_PV1_PLAN_WORK = {'scheduled': re.compile(r'.*'), 'ordered': re.compile(r'orders?\\Z', re.A | re.I),"),
    # --- repair cycle 1: C4 holds only on a statement of today's encounter type ---
    _pv1('pv1-c4-today-mode', "C4: only a statement of today's encounter type holds the document",
         '            if _pv1_todays_mode(an, s, e):', '            if True:'),
    _pv1('pv1-c4-third-party', 'C4: a contact naming only another party holds nothing',
         '    if not party and _PV1_THIRD_PARTY.search(text, cs, ce):', '    if False:'),
    _pv1('pv1-c4-other-time', "C4: a statement naming another time holds nothing", '    if _pv1_clause_other_time(an, cs, ce):',
         '    if False:'),
    _pv1('pv1-c4-in-person', "C4: a sentence stating today's in-person visit holds nothing",
         '    if _pv1_in_person_today(an, ss, se):', '    if False:'),
    _pv1('pv1-c4-in-person-today', 'C4: an in-person visit told of another time clears nothing',
         '        if not _pv1_clause_other_time(an, cs, ce):\n            return True', '        if True:\n            return True'),
    _pv1('pv1-c4-contact-detail', 'C4: a contact detail (a telephone field, a preference, a letterhead number) holds nothing',
         '    if _pv1_contact_detail(text, start, end, party or _PV1_TODAY_SUBJECT.search(text, cs, ce) is not None):',
         '    if False:'),
    _pv1('pv1-c4-planned', 'C4: a planned contact holds nothing', _PV1_CONTACT_PLAN,
         '    if _PV1_PREFERS.search(text, cs, ce):'),
    _pv1('pv1-c4-prefers', "C4: a patient's preference holds nothing", _PV1_CONTACT_PLAN,
         "    if any(c.status == 'planned' for c in an.cues_in(cs, ce)):"),
    _pv1('pv1-c4-plan-read', 'C4 (EMR-8): a plan-section statement of today\'s encounter type is read', _PV1_SCAN,
         "        for s, e in spans:\n            if an.lay.section_at(s).kind == 'plan':\n                continue\n"
         "            if an.lay.section_at(s).kind == 'history':"),
    _pv1('pv1-c4-other-occasion', 'C4: a contact under a heading naming another occasion (a dated addendum) holds nothing',
         '    if _pv1_under_another_occasion(an, start):', '    if False:'),
    _pv1('pv1-c4-synonyms-phone', 'C4 (EMR-8): "on phone", "over phone", "(telephone)" and ", telephone." are read',
         *_PV1_PHONE_SYNONYMS, path=_PV1_CUES),
    _pv1('pv1-c4-synonyms-attendance', 'C4 (EMR-8): "Encounter: Telephone", "did not show / come in / keep", "cancelled '
         'the appointment" are read', _PV1_ATTENDANCE_SYNONYMS,
         r'''                   r'|\bleft\s+without\s+being\s+seen\b|\bLWBS\b', FLAGS | re.M)''', path=_PV1_CUES),
    # --- repair cycle 1: CTS-2, a hold never calls a stated basis undocumented, and quotes its line ---
    _pv1('pv1-cts2-basis', 'CTS-2: where C4 holds the document, the statements it held are its documented basis',
         '        done = [m for m in an.em if _pv1_held_by_c4(an, readings[m])]', '        done = []'),
    _pv1('pv1-line-quote', 'CTS-2: the C4 cue quotes at most _PV1_LINE_QUOTE characters of its line',
         '    if len(line) <= _PV1_LINE_QUOTE and not cut_left and not cut_right:', '    if True:'),
    # --- repair cycle 1: C4-time (EMR-7) and the EMR-9 holds ---
    _pv1('pv1-c4time-reviewed', "EMR-7: an activity-list item that is today's work on an earlier event names no other "
         'occasion', _PV1_REVIEWED, '    return False'),
    _pv1('pv1-c4time-item-duration', 'EMR-7: an item stating a duration is read whatever leads it', _PV1_REVIEWED,
         '    return _PV1_ACTIVITY_NOUN.search(text, cut, pos) is not None'),
    _pv1('pv1-emr9-unprepped', 'EMR-9: another visit named without a preposition holds a time statement',
         '        other = _pv1_unprepped(an, s, m.end, work, max(e, m.end))', '        other = None'),
    _pv1('pv1-emr9-paren', 'EMR-9: a parenthesis right after the minutes is read for another visit',
         "        spans.append((*paren.span('inside'), False))", '        pass'),
    _pv1('pv1-emr9-mdm-other-visit', "EMR-9: installed's MDM reading takes the prepositional other-visit hold",
         '        other = _pv1_other_visit(an, min(cs, m.start), m.end, False)', '        other = None'),
    _pv1('pv1-emr9-shared', "EMR-9: an MDM level read after 'shared' is held",
         "    if m.kind == 'em-mdm' and _PV1_SHARED_LEAD.search(an.text, max(0, m.start - 16), m.start):", '    if False:'),
    _pv1('pv1-cost-item-bound', 'H7: at most _PV1_ITEM_MATCHES reviewed prepositional matches are passed over, then held',
         _PV1_ITEM_BOUND, '    for count, (x, y) in enumerate(spans[i:]):\n        if y > end:\n            break\n'
         '        if work is not None'),
    _pv1('pv1-cost-unprepped-bound', 'H7: at most _PV1_ITEM_MATCHES unprepositioned matches are looked at, then held',
         '            if count >= _PV1_ITEM_MATCHES:\n                return words\n', ''),
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
    # (detect.todays_procedure_report, detect.in_todays_narrative), read by PE's routing-only reach and PI's S1 (PI's E1 too
    # until its drop in Wave 1 repair cycle 2) ---
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
    # --- amendment_20261101_cycle1_d ---
    Mutant('pe-head-not-today', 'a head mention routing reads as not done today (planned, historical, cancelled, negated) '
           'names no family', _PE_DETECT,
           '                if m.family in families and _generic_reading(an, m.start, m.end).status not in NOT_TODAY:',
           '                if m.family in families:', _PE_UNIT),
)
# --- package PI: the inventory (detector tests.test_gi4_pi; moved here from tests/test_gi4_pi_mutants.py, which now
# checks this slice; its (name, guard, path, old, new, detector) tuples are Mutant records here) ---
_PI_UNIT = 'unit:tests.test_gi4_pi'
# GI round 4 Wave 1 repair cycle 2 (pi.json amendment_20261101_cycle2): E1 and A1 were DROPPED with their code, and their
# 16 mutants retired with it (pi-e1-section, pi-e1-occurrence, pi-e1-extent-word, pi-e1-occurrence-word,
# pi-e1-routing-positive; pi-carry-part, pi-carry-part-kind, pi-carry-performed, pi-carry-region, pi-carry-reach,
# pi-carry-paragraph, pi-carry-field, pi-carry-two-named, pi-carry-lesion, pi-carry-lesion-paragraph,
# pi-carry-lesion-heading). Kept: S1's and W1's 8, unchanged but for the three descriptions that named E1. New: one
# killing mutant per part of S1's binding rule (pi-reach-binding*).
PI_MUTANTS = (
    Mutant('pi-reach-head', 'the reach needs a STRONG procedure report head (Wave 1 repair: '
           'detect.todays_procedure_report replaces sections.procedure_report_head; E1, which read it too, was dropped '
           'in cycle 2)', 'studio/gi/services.py',
           '    return detect.todays_procedure_report(text) and not _sections.around_procedure_title(text)',
           '    return not _sections.around_procedure_title(text)', _PI_UNIT),
    Mutant('pi-reach-around-title', 'the reach is never read in a note written around a procedure (as E1 was not, '
           'until its drop in cycle 2)', 'studio/gi/services.py',
           '    return detect.todays_procedure_report(text) and not _sections.around_procedure_title(text)',
           '    return detect.todays_procedure_report(text)', _PI_UNIT),
    Mutant('pi-reach-occurrence', "the reach is read only inside today's procedure narrative (Wave 1 repair: the shared "
           'copy guards, which read under_another_occurrence now)', 'studio/gi/services.py',
           '    if not detect.in_todays_narrative(original, pos, service_date, (ss, se)):\n        return False',
           '    if False:\n        return False', _PI_UNIT),
    Mutant('pi-reach-date', 'the reach is never read in a clause carrying a date', 'studio/gi/services.py',
           '                    if own_report[0] and not _dates_in(dates, cs, ce) \\',
           '                    if own_report[0] \\', _PI_UNIT),
    Mutant('pi-office-visit', 'the reach is never read in an office visit note (routing reads the visit done; E1, which '
           'read it too, was dropped in cycle 2)', 'studio/gi/services.py',
           "    if visit is not None and visit.status in POSITIVE:\n        return False",
           '    if False:\n        return False', _PI_UNIT),
    Mutant('pi-w1-another-stent', 'W1: dropped only beside another stent performed (hold-only)', 'studio/gi/services.py',
           "            if any(a.kind == 'stent' and a.status == 'performed' and a.id not in phantom for a in d.acts):",
           '            if True:', _PI_UNIT),
    # --- GI round 4 Wave 1 repair, cycle 1 ---
    Mutant('pi-reach-family', 'S1 reads a reach only for a family the head NAMES (amendment_20261101_cycle1_b: positive '
           "evidence, replacing cycle 1's hold-only 'the head excludes')", 'studio/gi/services.py',
           '    if family not in _pi_head_families(original, routing):\n        return False',
           '    if False:\n        return False', _PI_UNIT),
    # --- amendment_20261101_cycle1_d ---
    Mutant('pi-head-not-today', "S1: a head name routing reads as not done today names no family", 'studio/gi/services.py',
           '                     if not any(a < m.end() and m.start() < b for a, b in elsewhere))',
           '                     if True)', _PI_UNIT),
    # --- amendment_20261101_cycle2: S1 never decides the binding of an act or lesion A1 used to carry ---
    Mutant('pi-reach-binding', 'where more than one family is read performed, a family S1 alone reads performed takes no '
           "part in pass 3's one-performed-family fallback (those shapes bind as installed binds them)",
           'studio/gi/services.py',
           '        binding_families = [f for f in performed_families if f not in reach_only] \\\n',
           '        binding_families = performed_families \\\n', _PI_UNIT),
    Mutant('pi-reach-binding-own', "only there: where S1's family is the only family read performed, it still takes an "
           'act or lesion nothing else gives a family, as before cycle 2', 'studio/gi/services.py',
           "            if len([f for f in performed_families if f != 'gi.office_em']) > 1 else performed_families\n",
           '            if True else performed_families\n', _PI_UNIT),
    Mutant('pi-reach-binding-installed', 'an installed performed reading of the family (after its reach) puts it back '
           'into the fallback', 'studio/gi/services.py',
           '                    reach_only.discard(family)  # an installed reading states it performed too\n',
           '                    pass  # mutant: an installed reading never puts the family back\n', _PI_UNIT),
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
    # --- PO, Wave 1 repair cycle 1 (po.json amendment_20261101_r2; refutation F4): P1, PO-1's positive evidence ---
    Mutant('po1-positive-evidence', "PO-1 P1: positive evidence of today's performance beyond routing's silence",
           _PO_ENGINE,
           '        if not _po_done_in_body(u, inventory, text):  # P1: silence is no evidence that anything was done '
           'today\n            return False\n',
           '        pass  # mutant: P1 removed\n', _PO_UNIT),
    Mutant('po1-own-act', "PO-1 P1: for an act item, only that act", _PO_ENGINE,
           '        if u.act and a.kind != u.act:\n            continue\n', '        pass  # mutant: any act\n',
           _PO_UNIT),
    Mutant('po1-act-performed', 'PO-1 P1: the act is read performed', _PO_ENGINE,
           "        if a.status != 'performed':\n            continue\n", '        pass  # mutant: any status\n',
           _PO_UNIT),
    Mutant('po1-act-predicate', 'PO-1 P1: by an act predicate of its own, never a title, a procedure line, a box or a '
           'field', _PO_ENGINE,
           '        if not any(c.startswith(_PO_ACT_PREDICATE) for c in a.cues):\n            continue\n',
           '        pass  # mutant: any cue\n', _PO_UNIT),
    Mutant('po1-act-occurrence', "PO-1 P1: a passage under no line naming another occurrence's record", _PO_ENGINE,
           '        if any(0 <= ev.start < ev.end <= len(text) and not gi_sections.under_another_occurrence(text, '
           'ev.start)\n',
           '        if any(0 <= ev.start < ev.end <= len(text)\n', _PO_UNIT),
    Mutant('po1-act-in-text', 'PO-1 P1: a passage outside the text is no evidence', _PO_ENGINE,
           '        if any(0 <= ev.start < ev.end <= len(text) and not gi_sections.under_another_occurrence(text, '
           'ev.start)\n',
           '        if any(not gi_sections.under_another_occurrence(text, ev.start)\n', _PO_UNIT),
    Mutant('po1-no-service', "PO-1 P1: no inventory, or no service of the item, is no evidence", _PO_ENGINE,
           '    if service is None:\n        return False\n    for a in service.acts:\n',
           '    if service is None:\n        return True\n    for a in service.acts:\n', _PO_UNIT),
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
