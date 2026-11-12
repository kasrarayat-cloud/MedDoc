"""H3: the generated corpus, with PROVISIONAL truth tables written by construction (never read back from any reader).

Started from the invariant design's generator (procedure reports, office notes, two-service reports) and widened with
the round-4 plan's document kinds: notes written around a procedure (pre-procedure call, booking, consent, instructions,
an education handout), records reviews and correspondence with copied reports (the heading near or far, the family named
or not, the copy signed on another day), telephone, video and no-show visits, a time dated by an addendum, a
procedure-day H&P, two-service reports with past negations, head-less reports, and four layouts (lines, DOCX with blank
lines dropped, OCR with a blank line between lines, PDF hard wrap at 100 characters).

Every document is {id, kind, axes, text, truth}. ``truth`` holds the encounter's own date, the member answers to try,
which answers may be taken, the dates that must never be sent, each family's status today, the E/M reading, and
``cells``: one per property, each MUST (safety), SHOULD (a reading asked for) or MAY (careful coders could differ: never
judged). truth.review() is the second, independent pass that marks disputed cells MAY. No qualified GI coder has
reviewed any of it: every cell is a provisional author expectation.
"""
from __future__ import annotations

import datetime as dt
import itertools
import random

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'
SEED = 20261101
FAMILIES = ('gi.egd', 'gi.colonoscopy', 'gi.flex_sig', 'gi.eus', 'gi.ercp', 'gi.office_em')

FAM = {
    'gi.colonoscopy': dict(name='Colonoscopy', lower='colonoscopy', instr='colonoscope', landmark='the cecum',
                           extent_tokens=('cec',), title_words=('Colonoscopy',), site='ascending colon'),
    'gi.egd': dict(name='Upper Endoscopy', lower='upper endoscopy', instr='gastroscope',
                   landmark='the second part of the duodenum', extent_tokens=('duoden',),
                   title_words=('Upper Endoscopy', 'EGD'), site='gastric antrum'),
    'gi.flex_sig': dict(name='Flexible Sigmoidoscopy', lower='flexible sigmoidoscopy', instr='flexible sigmoidoscope',
                        landmark='the descending colon', extent_tokens=('descending',),
                        title_words=('Flexible Sigmoidoscopy',), site='sigmoid colon'),
}
# own-date labels: 'in' is the installed vocabulary; 'out' are labels a careful coder reads as the date of service
OWN_LABELS = {'in': ('Date of service', 'Procedure date'),
              'out': ('Date performed', 'Exam date', 'Case date', 'Day of procedure', 'Date seen')}


def fmt(d: dt.date, style: str) -> str:
    if style == 'iso':
        return d.isoformat()
    if style == 'us':
        return f'{d.month:02d}/{d.day:02d}/{d.year}'
    return d.strftime('%B ') + str(d.day) + d.strftime(', %Y')


def render(blocks: list, style: str) -> str:
    """Blocks of lines (each block a heading and its lines) in one of four layouts."""
    lines = [line for block in blocks for line in block]
    if style == 'lines':  # a text file: a blank line between blocks
        return '\n\n'.join('\n'.join(block) for block in blocks) + '\n'
    if style == 'docx':  # the DOCX renderer drops blank lines
        return '\n'.join(lines) + '\n'
    if style == 'ocr':  # a scanned PDF read by OCR: a blank line between lines
        return '\n\n'.join(lines) + '\n'
    out = []  # 'wrap': a PDF's hard wrap at 100 characters
    for line in lines:
        while len(line) > 100:
            cut = line.rfind(' ', 0, 100)
            cut = cut if cut > 40 else 100
            out.append(line[:cut])
            line = line[cut + 1:]
        out.append(line)
    return '\n'.join(out) + '\n'


def dates(rng: random.Random) -> dict:
    d = dt.date(2026, 10, 1) + dt.timedelta(days=rng.randrange(0, 28))
    return dict(D=d, P=d.replace(year=d.year - rng.choice((1, 2, 5))), N=d + dt.timedelta(days=rng.randrange(20, 70)),
                L=d + dt.timedelta(days=2), S=d - dt.timedelta(days=rng.randrange(3, 9)), DOB=dt.date(1959, 6, 2))


def answers_of(ds: dict, *keys) -> dict:
    out = {k: ds[k].isoformat() for k in keys if k in ds}
    out['F'] = '1998-01-01'
    return out


def cell(name: str, level: str, expect, why: str) -> dict:
    return {'cell': name, 'level': level, 'expect': expect, 'why': why}


def date_cells(own: str | None, allowed: list, never: list, conflict: bool, own_label: str) -> list:
    """The date properties every document carries."""
    cells = [cell('date.send', 'MUST', {'allowed': sorted(set(allowed))},
                  'a request carries no date or one the document gives as this encounter\'s own')]
    if conflict:
        cells.append(cell('date.no-send-before-answer', 'MUST', 'asked',
                          'two documented dates of service for one encounter: asked, never silently chosen'))
    for key in never:
        cells.append(cell(f'date.answer-held[{key}]', 'MUST', 'not-taken',
                          'never another occurrence\'s date, a date of birth, or a date the document does not state'))
    if own and not conflict:
        cells.append(cell('date.answer-own-taken', 'SHOULD', 'taken-or-sent', 'the document\'s own date is accepted'))
        if own_label in ('in', 'out'):
            cells.append(cell(f'date.own-read[{own_label}]', 'SHOULD', 'sent',
                              'the own date is read from its label without a question'))
    return cells


def status_cells(today: dict) -> list:
    out = []
    for family, status in sorted(today.items()):
        if status == 'performed':
            out.append(cell(f'status.not-denied[{family}]', 'MUST', 'not-not-today',
                            'a service performed today is never read negated, historical, planned or cancelled'))
            out.append(cell(f'status.performed[{family}]', 'SHOULD', 'performed', 'read as performed today'))
        elif status == 'not_today':
            out.append(cell(f'status.not-performed[{family}]', 'MUST', 'not-positive',
                            'a service not done today never reads performed or incomplete'))
    return out


# --- procedure reports (the invariant design's generator, widened) ----------------------------------------------------

def procedure_doc(i, family, label_cls, history, body_heading, insertion, ledger, head, rng):
    f = FAM[family]
    ds = dates(rng)
    style = rng.choice(('iso', 'us', 'long'))
    lay = rng.choice(('lines', 'docx', 'ocr', 'wrap'))
    she, She = rng.choice((('she', 'She'), ('he', 'He')))
    top = [BANNER, rng.choice((f'{rng.choice(f["title_words"])} Report', f'{f["name"]}', f'Surveillance {f["name"]}',
                               f'{f["name"]} for Suspected Colitis')),
           'Hensley Narrows Surgery Center (fictional)', 'Facility category: ambulatory surgical center, POS 24']
    label = ''
    if label_cls != 'none':
        label = rng.choice(OWN_LABELS[label_cls])
        top.append(f'{label}: {fmt(ds["D"], style)}')
    has_dob = rng.random() < 0.5
    top.append('Patient: Petronella Szymanski-Abara (fictional), 64 years'
               + (f'; Date of birth: {fmt(ds["DOB"], "iso")}' if has_dob else ''))
    if head == 'head':
        top += ['Gastroenterologist: Lazare Sobczak-Muir, DO (fictional)',
                'Sedation: propofol by Wynona Tarkington-Ezeh, CRNA (fictional)']
    blocks = [top]
    past_acts = ()
    indication = 'Six kilograms of unintended weight loss over five months.'
    if history == 'never':
        indication += f' {She} has never had a {f["lower"]}. The examination was done to look for a cause.'
    elif history == 'prior_known':
        blocks.append(['Prior Procedures', f'{f["name"]} on {fmt(ds["P"], style)}: a 6 mm polyp was removed by cold snare.'])
        past_acts = ('snare',)
    elif history == 'prior_runaway':  # a history heading whose section runs on under an unknown body heading
        blocks.append(['Prior Studies', f'Earlier {f["lower"]} (this service): {fmt(ds["P"], style)} - two small '
                                        f'polyps, removed by cold snare.'])
        past_acts = ('snare',)
    elif history == 'outside_undated':
        blocks.append(['Earlier Care', f'A {f["lower"]} at another center some years ago was reported as normal.'])
    blocks.append([rng.choice(('Indication', 'Why It Was Done')), indication])
    heading = (rng.choice(('Procedure', 'Findings', 'Description of the procedure')) if body_heading == 'known'
               else rng.choice(('Observations by Segment', 'Scope Passage and Views', 'Large Bowel Narrative')))
    body, reached = [], True
    if insertion == 'aux':
        body.append(f'The {f["instr"]} was advanced to {f["landmark"]}.')
    elif insertion == 'active':
        body.append(f'The {f["instr"]} reached {f["landmark"]}, where the landmarks were photographed.')
    elif insertion == 'label':
        body.append(f'Extent of examination: {f["landmark"][4:]}.')
    elif insertion == 'label_unknown':
        body.append(f'Reach of the examination: {f["landmark"][4:]}.')
    else:
        reached = False
        body.append('The mucosa was inspected carefully.')
    today_acts = ()
    if rng.random() < 0.5:
        body.append(f'Cold forceps biopsies were taken from the {f["site"]}.')
        today_acts = ('biopsy',)
    else:
        body.append(f'The {f["site"]} looked normal and no tissue was taken.')
    blocks.append([heading, ' '.join(body)])
    blocks.append([rng.choice(('Impression', 'At a Glance')),
                   '1. ' + ('Biopsies taken; results to follow.' if today_acts else 'Normal examination.')])
    plan_booked = rng.random() < 0.5
    blocks.append([rng.choice(('Plan', 'Next Steps')), (f'Repeat {f["lower"]} booked for {fmt(ds["N"], style)}.'
                                                       if plan_booked else f'Repeat {f["lower"]} in three years.')])
    conflict = ledger in ('differ', 'charge_differ')
    if ledger in ('same', 'differ'):
        blocks.append(['Case Room Ledger', 'Case reference: EVL-K-7731 (synthetic)',
                       f'Service date logged for this case: {fmt(ds["D"] if ledger == "same" else ds["L"], style)}'])
    elif ledger == 'charge_differ':
        blocks.append(['Charge information', f'Date of service: {fmt(ds["L"], style)}'])
    blocks.append([f'Report authenticated: Lazare Sobczak-Muir, DO (fictional), {fmt(ds["D"], style)} 11:52'])
    allowed = [ds['D'].isoformat()] + ([ds['L'].isoformat()] if ledger == 'differ' else [])
    answers = answers_of(ds, 'D', 'L', 'P', 'N') | ({'DOB': ds['DOB'].isoformat()} if has_dob else {})
    never = ['P', 'N', 'F'] + (['DOB'] if has_dob else []) + (['L'] if ledger in ('same', 'none', 'charge_differ')
                                                                else [])
    today = {family: 'performed'} | {x: 'not_today' for x in FAM if x != family} | {'gi.office_em': 'not_today'}
    cells = date_cells(ds['D'].isoformat(), allowed, never, conflict, label_cls) + status_cells(today)
    if reached:
        cells.append(cell(f'extent.read[{family}]', 'SHOULD', list(f['extent_tokens']), 'the landmark reached is read'))
    cells.append(cell(f'extent.never-false-incomplete[{family}]', 'MUST', 'not-incomplete',
                      'never "incomplete" without a stated incompleteness'))
    for act in past_acts:
        if act not in today_acts:
            cells.append(cell(f'act.not-another-occurrence[{family}.{act}]', 'MUST', 'not-performed',
                              'another occurrence\'s act is never today\'s'))
    for act in today_acts:
        cells.append(cell(f'act.today-read[{family}.{act}]', 'SHOULD', 'performed', 'today\'s act is read'))
    truth = dict(date=ds['D'].isoformat(), conflict=conflict, own_label=label_cls, answers=answers,
                 allowed_answers=sorted(set(allowed)), never=never, today=today, cells=cells)
    axes = dict(family=family, label=label_cls, history=history, body_heading=body_heading, insertion=insertion,
                ledger=ledger, head=head, layout=lay, date_style=style)
    return dict(id=f'P{i:05d}', kind='procedure', axes=axes, text=render(blocks, lay), truth=truth)


# --- office notes, and the visits that are not an office visit -------------------------------------------------------

EM_TIME = {
    'today_supported': ('Total time spent on the date of the encounter: {m} minutes.', True),
    'today_h208': ('Physician time on the service date: {m} minutes, covering review of the ultrasound and laboratory '
                   'results, the examination and documentation.', True),
    'today_h401': ('Total time I spent on her care on the date of this visit: {m} minutes, covering her history, the '
                   'examination, counseling, the orders, and documentation.', True),
    'last_visit': ('Total time at her last visit was 40 minutes.', False),
    'next_month': ('Total time 30 minutes at the follow-up visit next month.', False),
    'none': ('', False),
}
EM_MDM = {'mdm_supported': 'Medical decision making: moderate.', 'mdm_h401': 'Complexity of decision making: moderate.',
          'shared': 'Shared decision making about colonoscopy; she accepts the high risk of bleeding.', 'none': ''}
EM_HEADER = {'office_note': ('Office visit note', 'Established patient'),
             'new_eval': ('New Patient Evaluation', 'Relationship to practice: new patient'),
             'h208': ('Hepatology follow-up note', 'Established patient')}
# visit modes: an office visit, or one that is not (truth 'not_office': no office E/M; 'MAY': coders differ)
VISIT_MODES = ('office', 'telephone', 'video', 'no_show', 'addendum_time', 'procedure_day_hp')


def em_doc(i, header, time_cls, mdm_cls, charge, mode, rng):
    ds = dates(rng)
    style = rng.choice(('iso', 'us', 'long'))
    lay = rng.choice(('lines', 'docx', 'wrap'))
    minutes = rng.choice((44, 52, 34))
    title, status_line = EM_HEADER[header]
    if mode == 'telephone':
        title = 'Telephone encounter'
    elif mode == 'video':
        title = 'Video visit note'
    elif mode == 'procedure_day_hp':
        title = 'Pre-procedure History and Physical'
    top = [BANNER, 'Osprey Point Liver and Digestive Clinic (fictional)', title,
           f'Date of service: {fmt(ds["D"], style)}', 'Place of service: office (POS 11)', status_line,
           'Attending physician: Marguerite Szabo-Reyes, MD (fictional)']
    subj = 'Follow-up of reflux and iron deficiency.'
    if mode == 'telephone':
        subj = 'The patient was not seen in the office; we spoke by telephone about her reflux.'
    elif mode == 'video':
        subj = 'Seen by two-way video from her home; she consented to the video visit.'
    elif mode == 'no_show':
        subj = 'Patient did not arrive for the visit; no-show. A letter will be sent.'
    elif mode == 'procedure_day_hp':
        subj = 'Seen in the endoscopy unit immediately before today\'s colonoscopy; history reviewed and unchanged.'
    subj += f' Colonoscopy on {fmt(ds["P"], style)} showed diverticulosis only.'
    blocks = [top, ['Subjective', subj]]
    if mode in ('office', 'video', 'addendum_time', 'procedure_day_hp'):
        blocks.append(['Objective', 'Blood pressure 112/70; abdomen soft and non-tender.'])
    plan = ['Assessment and plan', 'Iron deficiency without a cause yet.',
            f'Upper endoscopy with duodenal biopsies is booked for {fmt(ds["N"], style)}.',
            'Blood work is ordered but was not drawn in the office today.', 'Surveillance ultrasound in six months.']
    t, today_time = EM_TIME[time_cls]
    if t and mode != 'addendum_time':
        plan.append(t.format(m=minutes))
    if EM_MDM[mdm_cls]:
        plan.append(EM_MDM[mdm_cls])
    blocks.append(plan)
    if mode == 'addendum_time':
        blocks.append([f'Addendum {fmt(ds["L"], style)}', (t or EM_TIME['today_h208'][0]).format(m=minutes)
                       + ' Reviewing the outside pathology.'])
    if charge == 'charge_differ':
        blocks.append(['Charge information', f'Date of service: {fmt(ds["L"], style)}'])
    elif charge == 'charge_same':
        blocks.append(['Charge information', f'Date of service: {fmt(ds["D"], style)}'])
    blocks.append([f'Electronically signed: Marguerite Szabo-Reyes, MD (fictional), {fmt(ds["D"], style)} 09:12'])
    em_status = {'office': 'performed', 'telephone': 'not_office', 'no_show': 'not_office', 'video': 'MAY',
                 'addendum_time': 'performed', 'procedure_day_hp': 'MAY'}[mode]
    today = {'gi.egd': 'not_today', 'gi.colonoscopy': 'MAY' if mode == 'procedure_day_hp' else 'not_today'}
    if em_status == 'performed':
        today['gi.office_em'] = 'performed'
    elif em_status == 'not_office':
        today['gi.office_em'] = 'not_today'
    cells = date_cells(ds['D'].isoformat(), [ds['D'].isoformat()], ['P', 'N', 'F'] + (['L'] if charge != 'none' else []),
                       charge == 'charge_differ', 'in') + status_cells(today)
    stated = str(minutes) if today_time and t else ''
    if time_cls in ('last_visit', 'next_month'):
        cells.append(cell('em.time-not-another-occurrence', 'MUST', '40' if time_cls == 'last_visit' else '30',
                          'no E/M basis from another occurrence\'s time'))
    if em_status == 'not_office':
        cells.append(cell('em.not-office-basis', 'MUST', 'no-basis', 'a telephone-only or missed visit is no office E/M'))
    elif em_status == 'performed':
        if stated and mode == 'office':
            cells.append(cell('em.time-read', 'SHOULD', stated, 'today\'s time is the basis'))
        if mode == 'addendum_time':
            cells.append(cell('em.time-read', 'MAY', stated, 'a time stated under an addendum dated another day'))
        if mdm_cls in ('mdm_supported', 'mdm_h401'):
            cells.append(cell('em.mdm-read', 'SHOULD', 'moderate', 'the decision-making level is read'))
    if mdm_cls == 'shared':
        cells.append(cell('em.no-level-from-shared-decision', 'MUST', 'no-mdm-level',
                          '"shared decision making" never gives a level'))
    truth = dict(date=ds['D'].isoformat(), conflict=charge == 'charge_differ', own_label='in',
                 answers=answers_of(ds, 'D', 'L', 'P', 'N'), allowed_answers=[ds['D'].isoformat()],
                 never=['P', 'N', 'F'] + (['L'] if charge != 'none' else []), today=today,
                 em=dict(status=em_status, minutes=stated, mdm='moderate' if mdm_cls in ('mdm_supported', 'mdm_h401')
                         else ''), cells=cells)
    axes = dict(header=header, time=time_cls, mdm=mdm_cls, charge=charge, mode=mode, layout=lay, date_style=style)
    return dict(id=f'E{i:05d}', kind='em', axes=axes, text=render(blocks, lay), truth=truth)


# --- two-service reports with past negations --------------------------------------------------------------------------

def bidirectional_doc(i, headings, colon_phrase, never, rectal_left, head, rng):
    ds = dates(rng)
    style = rng.choice(('iso', 'us', 'long'))
    lay = rng.choice(('lines', 'docx', 'wrap'))
    upper_h, lower_h = (('Upper Endoscopy Findings', 'Colonoscopy Findings') if headings == 'known'
                        else ('Stomach and Duodenum', 'Large Bowel'))
    top = [BANNER, 'Gastroscopy Then Colonoscopy in One Sitting', 'Hensley Narrows Surgery Center (fictional)',
           'Facility category: ambulatory surgical center, POS 24', f'Date of service: {fmt(ds["D"], style)}']
    if head == 'head':
        top += ['Gastroenterologist: Lazare Sobczak-Muir, DO (fictional)', 'Sedation: propofol by a CRNA (fictional)']
    lower = {'aux': 'The colonoscope was advanced to the cecum.',
             'active': 'The colonoscope reached the cecum, where its landmarks were photographed.'}[colon_phrase]
    if rectal_left:
        lower += (' In the rectum, 4 and 6 cm from the anal verge, there were two 3 mm pale polyps, left in place: no '
                  'polypectomy was performed in the colon.')
    blocks = [top, ['Indication', 'Unintended weight loss.' + (' She has never had a colonoscopy.' if never else '')],
              [upper_h, 'The gastroscope was advanced to the second part of the duodenum. In the gastric antrum sat a '
                        '14 mm pedunculated polyp; a hot snare was closed around the stalk and the polyp was removed and '
                        'retrieved.'],
              [lower_h, lower], ['Plan', 'Next colonoscopy in ten years.'],
              [f'Report authenticated: Lazare Sobczak-Muir, DO (fictional), {fmt(ds["D"], style)} 11:52']]
    today = {'gi.egd': 'performed', 'gi.colonoscopy': 'performed', 'gi.flex_sig': 'not_today',
             'gi.office_em': 'not_today'}
    cells = date_cells(ds['D'].isoformat(), [ds['D'].isoformat()], ['F'], False, 'in') + status_cells(today)
    cells += [cell('extent.read[gi.egd]', 'SHOULD', ['duoden'], 'the landmark reached is read'),
              cell('extent.read[gi.colonoscopy]', 'SHOULD', ['cec'], 'the landmark reached is read'),
              cell('extent.never-false-incomplete[gi.egd]', 'MUST', 'not-incomplete', 'no stated incompleteness'),
              cell('extent.never-false-incomplete[gi.colonoscopy]', 'MUST', 'not-incomplete', 'no stated incompleteness'),
              cell('binding.lower-not-on-upper', 'MUST', 'none', 'a lower-tract act or lesion never binds to the EGD'),
              cell('act.no-phantom[gi.colonoscopy.snare]', 'MUST', 'not-performed', 'no snare was used in the colon')]
    truth = dict(date=ds['D'].isoformat(), conflict=False, own_label='in', answers=answers_of(ds, 'D'),
                 allowed_answers=[ds['D'].isoformat()], never=['F'], today=today, cells=cells,
                 lower_regions=['rectum', 'colon', 'anus'])
    axes = dict(headings=headings, colon_phrase=colon_phrase, never=never, rectal_left=rectal_left, head=head,
                layout=lay)
    return dict(id=f'B{i:05d}', kind='bidirectional', axes=axes, text=render(blocks, lay), truth=truth)


# --- notes written around a procedure: never the procedure's report ---------------------------------------------------

AROUND = {
    'call': ('Pre-procedure telephone call', 'Patient reached by phone; bowel preparation and arrival time reviewed.'),
    'booking': ('Endoscopy booking', '{fam} booked for the morning list; arrival 07:00.'),
    'consent': ('Procedure consent', 'Risks, benefits and alternatives of the {low} were discussed and the consent form '
                                     'was signed.'),
    'instructions': ('Colonoscopy preparation instructions', 'Clear liquids the day before; split-dose preparation as '
                                                             'printed.'),
    'education': ('Patient Education Handout', 'During the test the {instr} is passed gently; in most patients it '
                                               'reaches the {land} within minutes.'),
}
AROUND_LABELS = ('Day of procedure', 'Case date', 'Procedure date', 'Scheduled for')


def around_doc(i, kind, family, label, signed, lay, rng):
    f = FAM[family]
    ds = dates(rng)  # C: the note's own day (D); P: the planned procedure day (N)
    style = rng.choice(('iso', 'us', 'long'))
    title, body = AROUND[kind]
    body = body.format(fam=f['name'], low=f['lower'], instr=f['instr'], land=f['landmark'][4:])
    top = [BANNER, 'Hensley Narrows Endoscopy (fictional)', title, f'{label}: {fmt(ds["N"], style)}']
    blocks = [top, [body]]
    sign_day = ds['N'] if signed == 'on_procedure_day' else ds['D']
    blocks.append([f'Signed: Synthetic Nurse, RN (fictional), {fmt(sign_day, style)} 09:10'])
    today = {x: 'not_today' for x in FAM} | {'gi.office_em': 'not_today'}
    never = ['N', 'P', 'F']
    # the note's own day is never stated as a date of service here: no answer is required to be taken
    cells = date_cells(None, [ds['D'].isoformat()], never, False, 'none') + status_cells(today)
    truth = dict(date=ds['D'].isoformat(), conflict=False, own_label='none', answers=answers_of(ds, 'D', 'N', 'P'),
                 allowed_answers=[ds['D'].isoformat()], never=never, today=today, cells=cells)
    axes = dict(around=kind, family=family, label=label, signed=signed, layout=lay)
    return dict(id=f'A{i:05d}', kind='around', axes=axes, text=render(blocks, lay), truth=truth)


# --- records reviews and correspondence carrying a copied report ------------------------------------------------------

FILL = tuple(f'Line {n} of the outside summary lists medications and allergies in detail.' for n in range(8))


def records_doc(i, kind, family, named, reach, signed_other, lay, rng):
    f = FAM[family]
    ds = dates(rng)
    style = rng.choice(('iso', 'us', 'long'))
    title, heading = {'review': ('GI Records Review', 'Summary of outside records'),
                      'letter': ('Clinic Correspondence', 'Attached Document')}[kind]
    top = [BANNER, title, f'Date of service: {fmt(ds["D"], style)}']
    copied = [heading, 'The patient brought copies from Mercy GI.']
    if reach == 'far':
        copied += list(FILL)
    narration = (f'{f["name"]} at Mercy GI. ' if named else '') + (
        f'The {f["instr"]} reached {f["landmark"]}. A 10 mm polyp was removed with a hot snare.')
    copied.append(narration)
    if signed_other:
        copied.append(f'Signed {fmt(ds["P"], style)}.')
    blocks = [top, copied, ['Assessment', 'Adenoma history.'], ['Plan', f'Surveillance {f["lower"]} in three years.']]
    today = {x: 'not_today' for x in FAM}
    cells = date_cells(ds['D'].isoformat(), [ds['D'].isoformat()], ['P', 'F'], False, 'in') + status_cells(today)
    cells.append(cell(f'act.not-another-occurrence[{family}.snare]', 'MUST', 'not-performed',
                      'a copied report\'s act is never today\'s'))
    truth = dict(date=ds['D'].isoformat(), conflict=False, own_label='in', answers=answers_of(ds, 'D', 'P'),
                 allowed_answers=[ds['D'].isoformat()], never=['P', 'F'], today=today, cells=cells)
    axes = dict(records=kind, family=family, named=named, reach=reach, signed_other=signed_other, layout=lay)
    return dict(id=f'R{i:05d}', kind='records', axes=axes, text=render(blocks, lay), truth=truth)


def generate():
    """Every generated document, in a fixed order with fixed seeds."""
    rng = random.Random(SEED)
    n = 0
    for fam, lab, hist, bh, ins, led, head in itertools.product(
            FAM, ('in', 'out', 'none'), ('none', 'never', 'prior_known', 'prior_runaway', 'outside_undated'),
            ('known', 'unknown'), ('aux', 'active', 'label', 'label_unknown', 'absent'),
            ('none', 'same', 'differ', 'charge_differ'), ('head', 'headless')):
        if head == 'headless' and (hist, ins) not in (('none', 'active'), ('never', 'active'), ('prior_runaway', 'aux'),
                                                      ('outside_undated', 'active')):
            continue  # head-less reports on the shapes the instrument's reach would read
        yield procedure_doc(n, fam, lab, hist, bh, ins, led, head, random.Random(rng.random()))
        n += 1
    for hdr, tm, mdm, ch, mode in itertools.product(EM_HEADER, EM_TIME, EM_MDM, ('none', 'charge_same', 'charge_differ'),
                                                    VISIT_MODES):
        yield em_doc(n, hdr, tm, mdm, ch, mode, random.Random(rng.random()))
        n += 1
    for hd, cp, nv, rl, head, rep in itertools.product(('known', 'unknown'), ('aux', 'active'), (False, True),
                                                       (False, True), ('head', 'headless'), range(3)):
        yield bidirectional_doc(n, hd, cp, nv, rl, head, random.Random(rng.random()))
        n += 1
    for kind, fam, label, signed, lay in itertools.product(AROUND, FAM, AROUND_LABELS, ('on_call_day', 'on_procedure_day'),
                                                           ('lines', 'docx', 'ocr', 'wrap')):
        yield around_doc(n, kind, fam, label, signed, lay, random.Random(rng.random()))
        n += 1
    for kind, fam, named, reach, signed_other, lay in itertools.product(('review', 'letter'), FAM, (False, True),
                                                                        ('near', 'far'), (False, True),
                                                                        ('lines', 'docx', 'ocr', 'wrap')):
        yield records_doc(n, kind, fam, named, reach, signed_other, lay, random.Random(rng.random()))
        n += 1
