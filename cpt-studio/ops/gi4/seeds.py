"""H3: seeded families of the regression documents (h4-01..h4-06, h2-08, h2-10): each document's decisive lines
substituted by paraphrases of the same meaning, so every variant keeps the source's truth (never re-read from a reader).
Started from the invariant design's seedgen.py (h4-04), with a family of at least 100 variants for every document.

Each slot is (anchor, alternatives); the anchor must occur exactly once in the source (asserted), alternatives[0] is the
source's own wording, and every alternative says the same thing to a careful coder. A family larger than SAMPLE is
sampled with a fixed seed, every alternative of every slot still appearing.
"""
from __future__ import annotations

import itertools
import random
import re

from ops.gi4.gen import cell, date_cells, status_cells

SAMPLE = 216
SLOTS = {
    'h4-01': {
        'label': ('Date seen: 10/26/2026', ['Date seen: 10/26/2026', 'Date of service: 10/26/2026',
                                            'Visit date: 10/26/2026', 'Date of visit: October 26, 2026']),
        'title': ('New Patient Evaluation', ['New Patient Evaluation', 'New Patient Office Visit', 'Initial Visit']),
        'time': ('Total time I spent on her care on the date of this visit: 52 minutes',
                 ['Total time I spent on her care on the date of this visit: 52 minutes',
                  'Total time on the date of the encounter: 52 minutes', 'Time spent on her care today: 52 minutes']),
        'mdm': ('Complexity of decision making: moderate.', ['Complexity of decision making: moderate.',
                                                             'Medical decision making: moderate.', 'MDM: moderate.']),
        'egd': ('Upper endoscopy with duodenal biopsies is booked for 11/23/2026',
                ['Upper endoscopy with duodenal biopsies is booked for 11/23/2026',
                 'Upper endoscopy with duodenal biopsies is scheduled for 11/23/2026']),
    },
    'h4-02': {
        'label': ('Case date: 2026-10-21', ['Case date: 2026-10-21', 'Date of service: 2026-10-21',
                                           'Procedure date: 2026-10-21', 'Date performed: 2026-10-21']),
        'title': ('Gastroscopy and Sigmoidoscopy for Suspected Gut GVHD',
                  ['Gastroscopy and Sigmoidoscopy for Suspected Gut GVHD',
                   'Upper Endoscopy and Flexible Sigmoidoscopy Report', 'Gastroscopy and Sigmoidoscopy']),
        'upper_h': ('Upper Tract Observations', ['Upper Tract Observations', 'Upper Endoscopy Findings',
                                                 'Stomach and Duodenum']),
        'lower_h': ('Lower Tract Observations', ['Lower Tract Observations', 'Flexible Sigmoidoscopy Findings',
                                                 'Rectum and Sigmoid']),
        'limit': ('Limit of insertion |', ['Limit of insertion |', 'Extent of examination |']),
    },
    'h4-03': {
        'label': ('Exam date: 10/06/2026', ['Exam date: 10/06/2026', 'Date of service: 10/06/2026',
                                            'Procedure date: 10/06/2026']),
        'ledger': ('Service date logged for this case: 10/08/2026',
                   ['Service date logged for this case: 10/08/2026', 'Service date: 10/08/2026',
                    'Date of service logged for this case: 10/08/2026']),
        'ledger_h': ('Case Room Ledger', ['Case Room Ledger', 'Case Log', 'Room Ledger']),
        'bands': ('Six bands were placed, starting', ['Six bands were placed, starting',
                                                      'Six bands were applied, starting']),
        'narr_h': ('Banding Narrative', ['Banding Narrative', 'Procedure Narrative', 'Findings and Banding']),
    },
    'h4-04': {  # the invariant design's seedgen.py slots
        'label': ('Date performed: October 19, 2026', ['Date performed: October 19, 2026',
                                                       'Date of service: October 19, 2026',
                                                       'Exam date: October 19, 2026', 'Procedure date: October 19, 2026']),
        'never': ('She has never had a\ncolonoscopy.', ['She has never had a\ncolonoscopy.',
                                                        'She has had no prior\ncolonoscopy.',
                                                        'No colonoscopy has\never been done.',
                                                        'This is her first\ncolonoscopy.']),
        'upper_h': ('Stomach and Duodenum', ['Stomach and Duodenum', 'Upper Endoscopy Findings', 'Upper Tract']),
        'lower_h': ('Large Bowel', ['Large Bowel', 'Colonoscopy Findings', 'Lower Tract']),
        'colon': ('The colonoscope reached the cecum, where its landmarks, the\nappendiceal orifice and ileocecal valve, '
                  'were photographed;',
                  ['The colonoscope reached the cecum, where its landmarks, the\nappendiceal orifice and ileocecal valve, '
                   'were photographed;',
                   'The colonoscope was advanced to the cecum, where its landmarks, the\nappendiceal orifice and '
                   'ileocecal valve, were photographed;',
                   'Cecal intubation was confirmed by photographs of the\nappendiceal orifice and ileocecal valve;',
                   'The instrument was passed to the cecum, where its landmarks, the\nappendiceal orifice and ileocecal '
                   'valve, were photographed;']),
        'upper': ('The gastroscope was introduced by mouth under visual guidance and steered through the stomach and '
                  'pylorus\ninto the second part of the duodenum.',
                  ['The gastroscope was introduced by mouth under visual guidance and steered through the stomach and '
                   'pylorus\ninto the second part of the duodenum.',
                   'The gastroscope was advanced to the second part of the duodenum.',
                   'The endoscope was passed through the stomach and pylorus into the second part of the duodenum.']),
    },
    'h4-05': {
        'label': ('Service date: 2026-10-15', ['Service date: 2026-10-15', 'Date of service: 2026-10-15',
                                              'Procedure date: 2026-10-15']),
        'title': ('Pancreatic Endosonography', ['Pancreatic Endosonography', 'Endoscopic Ultrasound Report',
                                                'EUS of the Pancreas']),
        'prior_h': ('Prior Studies', ['Prior Studies', 'Earlier Imaging and Procedures', 'Previous Studies']),
        'scope_h': ('Scope Passage and Views', ['Scope Passage and Views', 'Procedure', 'Technique']),
        'colon': ('a colonoscopy has been scheduled for 2026-12-03', ['a colonoscopy has been scheduled for 2026-12-03',
                                                                     'a colonoscopy is booked for 2026-12-03']),
    },
    'h4-06': {
        'label': ('Day of procedure: Oct 27, 2026', ['Day of procedure: Oct 27, 2026', 'Date of service: Oct 27, 2026',
                                                     'Procedure date: Oct 27, 2026', 'Date performed: Oct 27, 2026']),
        'reach': ('Reach of the examination: ileocolic anastomosis, with 6 cm of neoterminal ileum viewed through it.',
                  ['Reach of the examination: ileocolic anastomosis, with 6 cm of neoterminal ileum viewed through it.',
                   'Extent of examination: ileocolic anastomosis, with 6 cm of neoterminal ileum viewed through it.',
                   'The colonoscope was advanced through the ileocolic anastomosis into the neoterminal ileum.']),
        'hist_h': ('Prior Surgery and Cancer Care', ['Prior Surgery and Cancer Care', 'Oncologic History', 'History']),
        'obs_h': ('Observations by Segment', ['Observations by Segment', 'Findings', 'Procedure Findings']),
        'ident': ('This is his one-year surveillance colonoscopy.', ['This is his one-year surveillance colonoscopy.',
                                                                    'Today he comes for his one-year surveillance '
                                                                    'colonoscopy.']),
    },
    'h2-08': {
        'label': ('Date of service: 2026-10-05', ['Date of service: 2026-10-05', 'Visit date: 2026-10-05',
                                                 'DOS: 2026-10-05']),
        'charge_h': ('Charge information', ['Charge information', 'Charge Capture', 'Billing information']),
        'title': ('Hepatology follow-up note', ['Hepatology follow-up note', 'Hepatology Clinic Visit',
                                                'Follow-up Visit']),
        'time': ('Physician time on the service date: 44 minutes', ['Physician time on the service date: 44 minutes',
                                                                    'Total time on the date of the encounter: 44 '
                                                                    'minutes']),
        'us': ('Surveillance ultrasound in six months.', ['Surveillance ultrasound in six months.',
                                                         'Repeat ultrasound in six months.']),
    },
    'h2-10': {
        'label': ('Date of service: 2026-10-23', ['Date of service: 2026-10-23', 'Procedure date: 2026-10-23',
                                                 'DOS: 2026-10-23']),
        'stent': ('The existing stent was in position and draining.', ['The existing stent was in position and draining.',
                                                                      'The indwelling stent was in good position and '
                                                                      'draining.']),
        'removal': ('withdrawn through the working channel', ['withdrawn through the working channel',
                                                              'removed through the working channel']),
        'new': ('plastic biliary stent was placed across the stricture', ['plastic biliary stent was placed across the '
                                                                          'stricture', 'plastic biliary stent was '
                                                                                       'deployed across the stricture']),
        'title': ('ERCP Procedure Note', ['ERCP Procedure Note', 'ERCP Report',
                                          'Endoscopic Retrograde Cholangiopancreatography']),
        'imp_h': ('\nImpression\n', ['\nImpression\n', '\nConclusions\n', '\nSummary\n']),
    },
}

# The authors' truth for each family (the manifests' expectations and the walk; h2-10: its own source). 'never': member
# answers that must never be taken (dates the document gives another role, and one it does not state).
TRUTH = {
    'h4-01': dict(date='2026-10-26', conflict=False, allowed=['2026-10-26'],
                  never={'lab': '2026-11-02', 'egd': '2026-11-23', 'return': '2026-12-14', 'outside': '2026-10-14',
                         'F': '1998-01-01'},
                  today={'gi.office_em': 'performed', 'gi.egd': 'not_today', 'gi.colonoscopy': 'not_today',
                         'gi.flex_sig': 'not_today', 'gi.eus': 'not_today', 'gi.ercp': 'not_today'},
                  em=dict(minutes='52', mdm='moderate')),
    'h4-02': dict(date='2026-10-21', conflict=False, allowed=['2026-10-21'], never={'F': '1998-01-01'},
                  today={'gi.egd': 'performed', 'gi.flex_sig': 'performed', 'gi.colonoscopy': 'not_today',
                         'gi.office_em': 'not_today', 'gi.eus': 'not_today', 'gi.ercp': 'not_today'},
                  extent={'gi.egd': ['duoden'], 'gi.flex_sig': ['50', 'descending']}),
    'h4-03': dict(date='2026-10-06', conflict=True, allowed=['2026-10-06', '2026-10-08'],
                  never={'sign': '2026-10-09', 'F': '1998-01-01'},
                  today={'gi.egd': 'performed', 'gi.office_em': 'not_today', 'gi.colonoscopy': 'not_today',
                         'gi.flex_sig': 'not_today', 'gi.eus': 'not_today', 'gi.ercp': 'not_today'},
                  extent={'gi.egd': ['duoden']}),
    'h4-04': dict(date='2026-10-19', conflict=False, allowed=['2026-10-19'], never={'ct': '2026-09-28',
                                                                                  'F': '1998-01-01'},
                  today={'gi.egd': 'performed', 'gi.colonoscopy': 'performed', 'gi.office_em': 'not_today',
                         'gi.flex_sig': 'not_today', 'gi.eus': 'not_today', 'gi.ercp': 'not_today'},
                  extent={'gi.egd': ['duoden'], 'gi.colonoscopy': ['cecum', 'cecal']}, lower_on_upper=True),
    'h4-05': dict(date='2026-10-15', conflict=False, allowed=['2026-10-15'],
                  never={'prior_eus': '2025-04-09', 'mri': '2026-09-22', 'visit': '2026-11-16', 'colon': '2026-12-03',
                         'F': '1998-01-01'},
                  today={'gi.eus': 'performed', 'gi.colonoscopy': 'not_today', 'gi.office_em': 'not_today',
                         'gi.flex_sig': 'not_today', 'gi.ercp': 'not_today'}),
    'h4-06': dict(date='2026-10-27', conflict=False, allowed=['2026-10-27'], never={'surgery': '2025-09-30',
                                                                                  'F': '1998-01-01'},
                  today={'gi.colonoscopy': 'performed', 'gi.office_em': 'not_today', 'gi.egd': 'not_today',
                         'gi.flex_sig': 'not_today', 'gi.eus': 'not_today', 'gi.ercp': 'not_today'},
                  extent={'gi.colonoscopy': ['anastomo', 'ileum', 'ileal']}),
    'h2-08': dict(date='2026-10-05', conflict=True, allowed=['2026-10-05'],
                  never={'charge': '2026-10-06', 'us': '2026-09-28', 'egd': '2025-03-10', 'dob': '1959-06-02',
                         'F': '1998-01-01'},
                  today={'gi.office_em': 'performed', 'gi.egd': 'not_today', 'gi.colonoscopy': 'not_today',
                         'gi.flex_sig': 'not_today', 'gi.eus': 'not_today', 'gi.ercp': 'not_today'},
                  em=dict(minutes='44', mdm='')),
    'h2-10': dict(date='2026-10-23', conflict=False, allowed=['2026-10-23'],
                  never={'prior_ercp': '2026-07-21', 'dob': '1975-05-17', 'F': '1998-01-01'},
                  today={'gi.ercp': 'performed', 'gi.egd': 'not_today', 'gi.office_em': 'not_today'}),
}


_IN_VOCABULARY = re.compile(r'(?:date of (?:service|procedure|visit|encounter)|(?:service|procedure|visit|encounter) '
                            r'date|DOS)\b', re.I)


def _label_class(label: str) -> str:
    """'in' when the label is in the installed own-date vocabulary, else 'out' (the harness's own reading)."""
    return 'in' if _IN_VOCABULARY.match(label) else 'out'


def _variants(doc_id: str, text: str):
    slots = SLOTS[doc_id]
    for key, (anchor, alternatives) in slots.items():
        if text.count(anchor) != 1 or alternatives[0] != anchor:
            raise AssertionError(f'{doc_id} slot {key}: anchor found {text.count(anchor)} times')
    keys = list(slots)
    combos = list(itertools.product(*(range(len(slots[k][1])) for k in keys)))
    if len(combos) > SAMPLE:
        rng = random.Random(f'gi4-seeds-{doc_id}')
        picked = set()
        for k_index, k in enumerate(keys):  # every alternative appears at least once
            for alt in range(len(slots[k][1])):
                picked.add(next(c for c in combos if c[k_index] == alt and c not in picked))
        rest = [c for c in combos if c not in picked]
        rng.shuffle(rest)
        combos = sorted(picked | set(rest[:SAMPLE - len(picked)]))
    for combo in combos:
        t = text
        for key, index in zip(keys, combo):
            t = t.replace(slots[key][0], slots[key][1][index], 1)
        yield dict(zip(keys, combo)), t


def seeded(regression_docs: dict):
    """The seeded families, as gen.py documents (kind 'seeded'), from the regression texts."""
    for doc_id in SLOTS:
        if doc_id not in regression_docs:
            continue
        base = TRUTH[doc_id]
        for n, (axes, text) in enumerate(_variants(doc_id, regression_docs[doc_id]['text'])):
            own_label = _label_class(SLOTS[doc_id]['label'][1][axes['label']])
            answers = {'D': base['date'], **base['never']}
            if base['conflict'] and len(base['allowed']) > 1:
                answers['L'] = base['allowed'][1]
            cells = date_cells(base['date'], base['allowed'], sorted(base['never']), base['conflict'], own_label)
            cells += status_cells(base['today'])
            for family, tokens in (base.get('extent') or {}).items():
                cells.append(cell(f'extent.read[{family}]', 'SHOULD', tokens, 'the source\'s landmark is read'))
                cells.append(cell(f'extent.never-false-incomplete[{family}]', 'MUST', 'not-incomplete',
                                  'no incompleteness is stated'))
            if base.get('lower_on_upper'):
                cells.append(cell('binding.lower-not-on-upper', 'MUST', 'none',
                                  'the rectal polyps belong to the colonoscopy'))
            em = base.get('em') or {}
            if em.get('minutes'):
                cells.append(cell('em.time-read', 'SHOULD', em['minutes'], 'today\'s time is the basis'))
            if em.get('mdm'):
                cells.append(cell('em.mdm-read', 'SHOULD', em['mdm'], 'the decision-making level is read'))
            truth = dict(date=base['date'], conflict=base['conflict'], own_label=own_label, answers=answers,
                         allowed_answers=sorted(base['allowed']), never=sorted(base['never']), today=base['today'],
                         cells=cells, lower_regions=['rectum', 'colon', 'anus'], seed_of=doc_id)
            yield dict(id=f'S-{doc_id}-{n:03d}', kind='seeded', axes={'seed_of': doc_id, **axes}, text=text,
                       truth=truth)
