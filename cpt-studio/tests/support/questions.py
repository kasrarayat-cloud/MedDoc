"""Answers in the question-id shape (D370, D372) and the synthetic case that led to it: one round of an operative note
asked 2 distinct questions and showed them 5 times - was a biopsy taken (it decides between two codes), and which date
of service is right. The wording here is a synthetic paraphrase of the stored round's codes and questions, never a
document's words; the document the customer fixture quotes (ops/dev_preview_server.cjs, SYNTHETIC_DOCUMENTS) is
invented too. Nothing reaches the network."""
from __future__ import annotations

from tests.support import coding as f
from tests.support import rounds as r


def coded(code, status='ready', *, ids=(), reason='The note documents it.', **kwargs):
    """A reader code line in the question-id shape: no question text of its own, the ids of the questions it depends
    on in question_ids."""
    item = {key: value for key, value in f.code(code, status, reason=reason, **kwargs).items() if key != 'question'}
    return {**item, 'question_ids': list(ids)}


def reviewed(line, code, verdict='agree', *, ids=(), status='ready', reason='Supported as listed.'):
    """A checker review of reader line ``line`` in the question-id shape."""
    item = {key: value for key, value in r.review(line, code, verdict, status=status, reason=reason).items()
            if key != 'question'}
    return {**item, 'question_ids': list(ids)}


def added(code, status='ready', *, ids=(), reason='The note documents it.'):
    """A missed code of the checker in the question-id shape."""
    item = {key: value for key, value in r.missed(code, status, reason=reason).items() if key != 'question'}
    return {**item, 'question_ids': list(ids)}


def asked(ident, text, affects=()):
    """A top-level question with its id."""
    return {'id': ident, 'question': text, 'affects': list(affects)}


# --- the case ---------------------------------------------------------------------------------------------------------
# L1 45380 needs an answer (the checker agrees); L2 45378, the no-biopsy alternative (the checker disagrees: it is not a
# service of its own); L3 99152 not supported (both agree).

BIOPSY = ('Was a biopsy taken during the colonoscopy? The procedure title names one, but the description of the '
          'procedure does not.')
DATE = 'Which date of service is right: 2026-11-13, entered at upload, or 2026-11-12, written in the note?'
# how today's shape restated them: the reader again on each of its two alternative lines, the checker in its own list
BIOPSY_ON_L1 = ('Was a biopsy taken, for example cold forceps samples from any part of the colon? The title says so '
                'and the description does not.')
BIOPSY_ON_L2 = 'Did the endoscopist take any tissue sample during this colonoscopy?'
DATE_BY_CHECKER = 'Is the date of service 2026-11-13, as entered at upload, or 2026-11-12, as the note says?'

REASONS = {
    'L1': ('The procedure title names a biopsy, but the description does not record one. A colonoscopy with a biopsy '
           'is coded 45380 only when a biopsy was taken.'),
    'L2': 'If no biopsy was taken, the procedure is a diagnostic colonoscopy, coded 45378 instead of 45380.',
    'L3': ('Moderate sedation by the endoscopist is coded only with a recorded intraservice time of at least 10 '
           'minutes, and no time is recorded.'),
}
CHECKS = {
    'L1': 'A biopsy is named in the title only, so the answer decides between 45380 and 45378.',
    'L2': 'This is the alternative to line L1, not a separate service: only one of the two can be reported.',
    'L3': 'No sedation time is documented.',
}
PROBLEM = 'The date of service written in the note differs from the date entered at upload.'
SERVICE_DATE, INSURANCE = '2026-11-13', 'commercial'  # entered at upload
# the passages each line's section cites, as the synthetic document writes them (a text file: no pages)
QUOTES = {
    'L1': ['Procedure: colonoscopy with biopsy (fictional)',
           'The colonoscope was advanced to the cecum and the mucosa was examined on withdrawal.'],
    'L2': ['The colonoscope was advanced to the cecum and the mucosa was examined on withdrawal.',
           'The mucosa appeared normal throughout, and the scope was withdrawn.'],
    'L3': ['Moderate sedation was given by the endoscopist; no start or stop time is recorded.'],
}

# The new shape, as the instructions now ask: each question once, with an id, and the lines naming it.
READER = f.reader_result(
    [coded('45380', 'needs_answer', ids=['Q1', 'Q2'], reason=REASONS['L1']),
     coded('45378', 'needs_answer', ids=['Q1', 'Q2'], reason=REASONS['L2']),
     coded('99152', 'not_supported', reason=REASONS['L3'])],
    questions=[asked('Q1', BIOPSY, ['L1', 'L2']), asked('Q2', DATE, ['L1', 'L2'])], problems=[PROBLEM])
CHECKER = f.checker_result(
    [reviewed('L1', '45380', ids=['Q1', 'Q2'], status='needs_answer', reason=CHECKS['L1']),
     reviewed('L2', '45378', 'disagree', ids=['Q1'], status='needs_answer', reason=CHECKS['L2']),
     reviewed('L3', '99152', status='not_supported', reason=CHECKS['L3'])])

# Today's shape, as the round was stored: 2 questions written 5 times.
TODAYS_READER = f.reader_result(
    [f.code('45380', 'needs_answer', question=BIOPSY_ON_L1, reason=REASONS['L1']),
     f.code('45378', 'needs_answer', question=BIOPSY_ON_L2, reason=REASONS['L2']),
     f.code('99152', 'not_supported', reason=REASONS['L3'])],
    questions=[{'question': BIOPSY, 'affects': ['L1', 'L2']}, {'question': DATE, 'affects': ['L1', 'L2']}],
    problems=[PROBLEM])
TODAYS_CHECKER = f.checker_result(
    [r.review('L1', '45380', status='needs_answer', reason=CHECKS['L1']),
     r.review('L2', '45378', 'disagree', status='needs_answer', reason=CHECKS['L2']),
     r.review('L3', '99152', status='not_supported', reason=CHECKS['L3'])],
    questions=[{'question': DATE_BY_CHECKER, 'affects': ['L1', 'L2']}])


def case_messages(reader=READER, checker=CHECKER):
    """The two answers as messages: the reader's sections cite QUOTES under each line's marker (character locations,
    as a text document's citations are), the checker's sections cite nothing; then each final JSON."""
    reader_blocks = [f.text_block('I read the whole note.\n')]
    for number, item in enumerate(reader['codes'], start=1):
        reader_blocks.append(f.text_block(f"\nLINE L{number} {item['code']}\n"))
        reader_blocks.append(f.text_block('Cited.', [f.char_cite(quote, 10 * index)
                                                     for index, quote in enumerate(QUOTES[f'L{number}'])]))
    reader_blocks += [f.text_block('\nEND\n'), f.text_block(f.fenced(reader))]
    checker_blocks = [f.text_block('I read the whole note first.\n')]
    for item in checker['reviews']:
        checker_blocks += [f.text_block(f"\nREVIEW {item['line']} {item['code']}\n"), f.text_block('Checked.')]
    checker_blocks += [f.text_block('\nEND\n'), f.text_block(f.fenced(checker))]
    return f.message(reader_blocks), f.message(checker_blocks)
