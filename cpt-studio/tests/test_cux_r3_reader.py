"""Reader repair, round 3 (2026-11-04): refutation round 3's lens A findings against the round-2 reader repairs,
repaired so the head reads no document worse than the installed revision and keeps the round-2 repairs' declared
improvements (declared before code in tests/fixtures/gi4/declarations/cux-r3-reader.json).

- A1 (L1c-r3): a same-day note under 'Procedure 2:', 'Subsequent procedure:' or 'Follow-on procedure:' owns its acts,
  as one under 'Separate note:' does; F01's and F03's shapes stay held by the rules that read them.
- A2 (R1c-r3): a labelled lesion's denial naming another site of its own segment keeps the same-lesion conflict beside
  R1c's site reading.
- A3 (R1a-r3): a label or specimen never binds an act told after another examination in a combined narrative.
- A4 (L1e-r3): 'It was removed ...' after a cecal polyp in a sigmoidoscopy note's part is the colonoscopy's.
- A5 (R8b-r3): a postmodified evaluation beside the E/M absence statement holds it, as R8b-2's declared form does.
- A6 (L1d-r3): a header line naming another, separately reported service ends nothing once the running report's own
  instrument is told again.
- A7 (R1b-r3): a label restated without its site, by its size and in its own tract's context, still resolves.
- A8: a residual (routing's layout reads no dash-form indication heading); measured, not changed.

Every document is synthetic. No database, nothing sent.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import battery
from studio.gi import cues, services
from studio.providers import corti
from tests.test_cux_bind import (HEAD, MARA, READY, acts, bundled, conflicts, em_questions, held, inventory, outcomes,
                                 run, service)
from tests.test_cux_hold import row, state

DECLARATION = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'declarations' / 'cux-r3-reader.json')
                         .read_text(encoding='utf-8'))
DECLARED = {(name, code): (before, after) for name, code, before, after in DECLARATION['battery']}
UNMOVED = {tuple(key.split(' | ')): cell for key, cell in DECLARATION['unmoved'].items()}
HELD = 'selected/needs_clarification'
EM = {'setting', 'patient_status', 'em_basis'}

B = battery.B
CECUM = battery.R8_CECUM
CO_SNARE = battery.R8_CO_SNARE
FS_BIOPSY = battery.R8_FS_BIOPSY
SCOPE_60 = 'The flexible sigmoidoscope was advanced to 60 cm in the descending colon.'


class R3RowsTests(SimpleTestCase):
    """Every round-3 battery row ends where the declaration says, with no violation; the A8 residual reads as it is
    recorded (measured, not repaired)."""

    def test_the_rows(self):
        names = DECLARATION['battery_rows_added']
        self.assertEqual(sorted(names), sorted(n for n in battery.CASES if n.startswith('R8 R3 ')))
        for name in names:
            result = row(name)
            for code in result['proposals']:
                with self.subTest(name, code=code):
                    expected = DECLARED[(name, code)][1] if (name, code) in DECLARED else UNMOVED[(name, code)]
                    self.assertEqual(state(result, code), expected)
                    self.assertEqual(result['proposals'][code]['violations'], [])

    def test_the_residual_reads_as_recorded(self):
        recorded = DECLARATION['residuals_measured']['rows']
        self.assertEqual(sorted(recorded), sorted(battery.R3_RESIDUALS))
        m = battery.modules()
        for name, (text, codes) in battery.R3_RESIDUALS.items():
            result = battery.run_row(m, name, text, codes)
            for code, cell in recorded[name].items():
                with self.subTest(name, code=code):
                    self.assertEqual(state(result, code), cell)


# --- A1 (L1c-r3): the restored note labels -------------------------------------------------------------------------

COLON = (B + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
         'Procedure: Colonoscopy\n' + CECUM + '\n')
NOTE_HEADINGS = ('Procedure 2: Flexible sigmoidoscopy (fictional), 2026-10-14',
                 'Subsequent procedure: Flexible sigmoidoscopy (fictional), 2026-10-14',
                 'Follow-on procedure: Flexible sigmoidoscopy (fictional), 2026-10-14')


def colon_then(heading, *lines):
    """R8's H1 shape: a colonoscopy with its snare, then ``heading`` over a flexible sigmoidoscopy and its biopsy."""
    return COLON + CO_SNARE + '\n\n' + heading + '\n' + SCOPE_60 + '\n' + ''.join(line + '\n' for line in lines)


class RestoredNoteLabelTests(SimpleTestCase):
    """A1: a numbered, a 'Subsequent' or a 'Follow-on' heading over a same-day note opens the note's part (R8 D7)."""

    def test_the_note_owns_its_biopsy(self):
        for heading in NOTE_HEADINGS:
            with self.subTest(heading):
                text = colon_then(heading, FS_BIOPSY)
                inv = inventory(text)
                self.assertEqual([a.kind for a in acts(inv, 'gi.colonoscopy')], ['snare'])
                self.assertEqual([a.kind for a in acts(inv, 'gi.flex_sig')], ['biopsy'])
                found = outcomes(run(text, [('45385', CO_SNARE), ('45380', FS_BIOPSY)]))
                self.assertEqual(found['45385'], READY)
                self.assertEqual(found['45380'], held('performed_status'))
                self.assertEqual(outcomes(run(text, [('45385', CO_SNARE), ('45331', FS_BIOPSY)]))['45331'], READY)

    def test_the_lines_are_note_labels(self):
        for line in ('Procedure 2: Colonoscopy', 'Procedure 1 - EGD', 'Subsequent procedure: colonoscopy',
                     'Follow-on procedure: colonoscopy', 'Followon procedure: colonoscopy',
                     'Separate same-day note: Flexible sigmoidoscopy'):
            with self.subTest(line):
                self.assertIsNotNone(services.LABELLED_NOTE.match(line))
        for line in ('Procedure: Colonoscopy', 'Follow-up procedure: colonoscopy', 'Procedures: EGD'):
            with self.subTest(line):
                self.assertIsNone(services.LABELLED_NOTE.match(line))

    def test_controls_f01_and_f03_stay_held(self):
        left = (HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum. A 12 mm sessile polyp was seen '
                'in the sigmoid colon and was left in place because the patient takes clopidogrel.\n')
        quote = [('45385', 'A 12 mm sessile polyp was seen in the sigmoid colon')]
        for tail in ('Recommendations:\nFollow-on procedure: colonoscopy with cold snare polypectomy\n',
                     'Subsequent procedure: colonoscopy with cold snare polypectomy\n',
                     'Follow-on procedure: colonoscopy with cold snare polypectomy\n',
                     'Procedure 2: colonoscopy with cold snare polypectomy\n'):
            with self.subTest(tail):
                self.assertEqual(outcomes(run(left + tail, quote))['45385'], held('performed_status'))
        listed = ('Findings:\nThe gastroscope was advanced to the second part of the duodenum. Biopsies were taken with '
                  'cold forceps. A clip was placed at the biopsy site.\nThe colonoscope was advanced to the cecum. The '
                  'colon was normal.\n')
        codes = [('43239', 'Biopsies were taken with cold forceps.'), ('45380', 'Biopsies were taken with cold forceps.')]
        for head in ('Procedure 1: EGD\nProcedure 2: Colonoscopy\n', 'Procedure 2: Colonoscopy\n',
                     'Procedure 2: Colonoscopy\nProcedure 1: EGD\n'):
            with self.subTest(head):
                text = HEAD + 'Upper endoscopy and colonoscopy report\n' + head + listed
                self.assertEqual(acts(inventory(text), 'gi.colonoscopy', 'biopsy'), [])
                self.assertEqual(outcomes(run(text, codes))['45380'][:2], ('selected', 'needs_clarification'))


# --- A2 (R1c-r3): a labelled denial at another site of its own segment ----------------------------------------------

LABELS = (HEAD + 'Colonoscopy report\nThe colonoscope was advanced to the cecum.\nCOL-1 - ascending colon: a 2 mm polyp was '
          'removed with cold forceps.\nCOL-2 - sigmoid colon: an 8 mm polyp was removed with a cold snare.\n')
SNARE_Q = ('45385', 'an 8 mm polyp was removed with a cold snare.')
FORCEPS_Q = ('45380', 'a 2 mm polyp was removed with cold forceps.')


def lesion(inv, size):
    return next(les for les in service(inv, 'gi.colonoscopy').lesions if les.size == size)


class LabelledDenialAtAnotherSiteTests(SimpleTestCase):
    """A2: where R1c unbinds a label for a site of the clause's own, a denial is read both ways - by its site (F06's
    conflict) and at the labelled lesion (the same-lesion conflict c47d71a34 kept)."""

    def test_the_same_lesion_conflict_is_kept(self):
        for denial, kind, size, code in (
                ('No snare was used on COL-2, just above the rectosigmoid junction.', 'snare', '8 mm', SNARE_Q),
                ('No snare was used on COL-2 in the left colon.', 'snare', '8 mm', SNARE_Q),
                ('No snare was used on COL-2 near the rectosigmoid junction.', 'snare', '8 mm', SNARE_Q),
                ('No forceps were used on COL-1 near the hepatic flexure.', 'biopsy', '2 mm', FORCEPS_Q)):
            with self.subTest(denial):
                text = LABELS + denial + '\n'
                inv = inventory(text)
                at = lesion(inv, size).id
                self.assertEqual([c.lesion for c in conflicts(inv, 'gi.colonoscopy', kind)], [at])
                denied = acts(inv, 'gi.colonoscopy', kind, 'negated')
                self.assertEqual(sorted(a.lesion for a in denied), sorted(['', at]))  # by its site, and at the lesion
                self.assertEqual(len({a.evidence[0].start for a in denied}), 1)  # one statement read both ways
                self.assertEqual(outcomes(run(text, [code]))[code[0]], held(f'conflict:{kind}'))

    def test_controls_f06_s_site_conflict_and_a_label_alone(self):
        text = LABELS + 'No snare was used on COL-1 in the sigmoid colon.\n'
        inv = inventory(text)
        self.assertEqual([c.lesion for c in conflicts(inv, 'gi.colonoscopy', 'snare')], [lesion(inv, '8 mm').id])
        self.assertEqual(outcomes(run(text, [SNARE_Q]))['45385'], held('conflict:snare'))
        for denial in ('No snare was used on COL-1.', 'No snare was used on COL-1 in the ascending colon.'):
            with self.subTest(denial):
                inv = inventory(LABELS + denial + '\n')
                self.assertEqual([a.lesion for a in acts(inv, kind='snare', status='negated')], [lesion(inv, '2 mm').id])
                self.assertEqual(outcomes(run(LABELS + denial + '\n', [SNARE_Q]))['45385'], READY)

    def test_the_second_reading_also_in_another_service_s_part(self):
        # a denial naming the colon label and a colon site inside the upper endoscopy's section: fail closed - the
        # labelled lesion's conflict is kept (its site reading alone would pair with nothing)
        text = (HEAD + 'Colonoscopy and EGD report\nCOLONOSCOPY\nThe colonoscope was advanced to the cecum.\nCOL-2 - sigmoid '
                'colon: an 8 mm polyp was removed with a cold snare.\nUPPER ENDOSCOPY\nThe gastroscope was advanced to '
                'the second part of the duodenum. No snare was used on COL-2 in the descending colon.\n')
        inv = inventory(text)
        self.assertEqual([c.lesion for c in conflicts(inv, 'gi.colonoscopy', 'snare')], [lesion(inv, '8 mm').id])
        self.assertEqual(outcomes(run(text, [SNARE_Q]))['45385'], held('conflict:snare'))

    def test_control_an_act_done_at_another_site_stays_unbound(self):
        text = LABELS + 'One clip was placed on COL-2 in the descending colon.\n'
        clips = acts(inventory(text), 'gi.colonoscopy', 'clip')
        self.assertEqual([(a.lesion, a.anatomy) for a in clips], [('', ('descending colon',))])


# --- A3 (R1a-r3): a binding told after another examination --------------------------------------------------------

GASTRO = 'The gastroscope was advanced to the second part of the duodenum.'
SPECIMEN = 'Biopsies were obtained with cold forceps (specimen 1).'
PASSING = 'Biopsies were then taken with the same cold forceps used to retrieve COL-1.'
ANTRUM = 'Cold forceps biopsies were taken from the gastric antrum.'


class BindingAfterAnotherExaminationTests(SimpleTestCase):
    """A3: in a combined report's narrative, a label or a specimen named in an act's clause after the gastroscope is
    told never makes the upper endoscopy's biopsy the colon lesion's; a labelled denial keeps its lesion."""

    def test_the_gastric_biopsy_is_never_the_colon_lesion_s(self):
        for text, quote in (
                (HEAD + 'EGD and colonoscopy report\nThe colonoscope was advanced to the cecum. A 6 mm polyp in the '
                 'sigmoid colon was removed with a cold snare and sent as specimen 1.\n' + GASTRO + ' The stomach showed '
                 'patchy erythema. ' + SPECIMEN + '\n', SPECIMEN),
                (HEAD + 'Colonoscopy and EGD report\nThe colonoscope was advanced to the cecum. A 6 mm polyp in the '
                 'sigmoid colon was removed with a cold snare and sent as specimen 1.\n' + GASTRO + '\nThe stomach showed '
                 'patchy erythema.\n' + SPECIMEN + '\n', SPECIMEN),
                (HEAD + 'Colonoscopy and EGD report\nThe colonoscope was advanced to the cecum.\nCOL-1 - sigmoid colon: an '
                 '8 mm polyp was removed with a cold snare.\n' + GASTRO + ' The antrum showed patchy erythema. ' + PASSING
                 + '\n', PASSING)):
            with self.subTest(quote, text=text[100:180]):
                inv = inventory(text)
                self.assertEqual(acts(inv, 'gi.colonoscopy', 'biopsy'), [])
                found = outcomes(run(text, [('43239', quote), ('45380', quote)]))
                self.assertEqual(found['45380'][:2], ('selected', 'needs_clarification'))

    def test_controls_a_labelled_clip_and_denial_and_the_colonoscope_told_again(self):
        text = (HEAD + 'EGD and colonoscopy report\n' + GASTRO + ' ' + ANTRUM + '\nThe colonoscope was advanced to the '
                'cecum.\nCOL-1 - sigmoid colon: an 8 mm polyp was removed with a cold snare.\nOne clip was placed at the '
                'COL-1 resection site. No biopsy forceps were used on COL-1.\n')
        inv = inventory(text)
        polyp = next(les for les in service(inv, 'gi.colonoscopy').lesions if les.size == '8 mm')
        self.assertEqual([a.lesion for a in acts(inv, 'gi.colonoscopy', 'clip')], [polyp.id])
        found = outcomes(run(text, [('43239', ANTRUM), SNARE_Q]))
        self.assertEqual((found['43239'], found['45385']), (READY, READY))
        again = (HEAD + 'Colonoscopy and EGD report\nThe colonoscope was advanced to the cecum.\nCOL-1 - sigmoid colon: an '
                 '8 mm polyp was seen.\n' + GASTRO + ' The antrum was normal.\nThe colonoscope was then reinserted.\nCOL-1 '
                 'was removed with a cold snare.\n')
        self.assertEqual(outcomes(run(again, [('45385', 'COL-1 was removed with a cold snare.')]))['45385'], READY)

    def test_control_a_lesion_named_after_the_other_examination_keeps_its_label(self):
        # the gastroscope is told before the colon lesion's own passage: nothing stands between the lesion and its clip
        text = (HEAD + 'EGD and colonoscopy report\n' + GASTRO + ' ' + ANTRUM + '\nCOL-1 - sigmoid colon: an 8 mm polyp '
                'was removed with a cold snare.\nOne clip was placed at the COL-1 resection site.\n')
        inv = inventory(text)
        polyp = next(les for les in service(inv, 'gi.colonoscopy').lesions if les.size == '8 mm')
        self.assertEqual([a.lesion for a in acts(inv, 'gi.colonoscopy', 'clip')], [polyp.id])

    def test_a_labelled_denial_keeps_its_lesion_after_another_examination(self):
        text = (HEAD + 'Colonoscopy and EGD report\nThe colonoscope was advanced to the cecum.\nCOL-2 - sigmoid colon: an '
                '8 mm polyp was removed with a cold snare.\n' + GASTRO + ' ' + ANTRUM + '\nNo biopsy forceps were used on '
                'COL-2.\n')
        inv = inventory(text)
        polyp = next(les for les in service(inv, 'gi.colonoscopy').lesions if les.size == '8 mm')
        self.assertEqual([a.lesion for a in acts(inv, kind='biopsy', status='negated')], [polyp.id])
        self.assertEqual(conflicts(inv), [])
        self.assertEqual(outcomes(run(text, [('43239', ANTRUM)]))['43239'], READY)


# --- A4 (L1e-r3): an anaphoric act after a beyond-reach lesion --------------------------------------------------------

R07 = COLON + '\nSeparate note: Flexible sigmoidoscopy (fictional), 2026-10-14\n' + SCOPE_60 + '\nThe rectum was normal.\n'


class AnaphoraBeyondTheNoteTests(SimpleTestCase):
    """A4: 'It was removed with a cold snare.' after 'A 5 mm polyp was seen in the cecum.' in a sigmoidoscopy note's
    part is the colonoscopy's snare of that polyp, as installed reads it; inside the sigmoidoscope's reach it stays the
    note's."""

    def test_the_cecal_polyp_s_snare_is_the_colonoscopy_s(self):
        for body, quote in (('\nA 5 mm polyp was seen in the cecum. It was removed with a cold snare.\n',
                             'It was removed with a cold snare.'),
                            ('\nA 5 mm cecal polyp was found.\nThe polyp was removed with a cold snare.\n',
                             'The polyp was removed with a cold snare.'),
                            ('A 5 mm polyp was seen in the cecum.\nIt was removed with a cold snare.\n',
                             'It was removed with a cold snare.')):
            with self.subTest(body):
                text = R07 + body
                inv = inventory(text)
                self.assertEqual(acts(inv, 'gi.flex_sig'), [])
                # at the cecal polyp where the lesion reader records it ("A 5 mm cecal polyp" it does not: no lesion)
                cecal = [les.id for les in service(inv, 'gi.colonoscopy').lesions if les.size == '5 mm']
                self.assertEqual([a.lesion for a in acts(inv, 'gi.colonoscopy', 'snare')], cecal or [''])
                found = outcomes(run(text, [('45378', CECUM), ('45385', quote), ('45338', quote)]))
                self.assertEqual(found['45385'], READY)
                self.assertEqual(found['45338'], held('performed_status'))

    def test_the_back_reference_is_the_last_lesion_the_part_names(self):
        # "The polyp" after a rectal polyp and then a cecal one is the cecal polyp (the note's own rectal polyp is not
        # the one it names); after the cecal one and then a rectal one it is the rectal polyp, the note's
        for order, owner in ((('A 3 mm polyp was seen in the rectum.', 'A 5 mm polyp was seen in the cecum.'),
                              'gi.colonoscopy'),
                             (('A 5 mm polyp was seen in the cecum.', 'A 3 mm polyp was seen in the rectum.'), 'gi.flex_sig')):
            with self.subTest(order):
                text = R07 + ''.join(x + '\n' for x in order) + 'The polyp was removed with a cold snare.\n'
                inv = inventory(text)
                self.assertEqual([s.family for s in inv.services for a in s.acts if a.kind == 'snare'], [owner])

    def test_control_a_sigmoid_polyp_s_snare_stays_the_note_s(self):
        text = R07 + 'A 5 mm polyp was seen in the sigmoid colon. It was removed with a cold snare.\n'
        inv = inventory(text)
        self.assertEqual([a.kind for a in acts(inv, 'gi.flex_sig')], ['snare'])
        found = outcomes(run(text, [('45378', CECUM), ('45385', 'It was removed with a cold snare.'),
                                    ('45338', 'It was removed with a cold snare.')]))
        self.assertEqual(found['45338'], READY)
        self.assertEqual(found['45385'], held('performed_status'))


# --- A5 (R8b-r3): a postmodified evaluation beside the absence statement ---------------------------------------------

EM_BODY = battery.R2_EM_BODY
EM_BIOPSY = battery.R2_EM_BIOPSY
MARA_EM = battery.R2_EM_MARA
POSTMODIFIED = ('An evaluation for new-onset jaundice was performed today.',
                'A history and examination for new-onset jaundice were performed today.',
                'A consultation regarding her new-onset jaundice was also provided today.',
                'An assessment of her new-onset jaundice, a separate problem, was documented today.',
                'A focused history and physical for new-onset jaundice was obtained today.',
                'An evaluation of her new-onset jaundice was completed today.',
                'A GI consultation for new-onset jaundice was performed today.',
                'Separately, an evaluation for new-onset jaundice was performed today.')


class PostmodifiedEvaluationTests(SimpleTestCase):
    """A5: R8b-2's declared form ('an evaluation ... performed') with a postmodifier holds the absence statement: the
    E/M questions are asked and 99213 is held, never excluded, in either order."""

    def test_the_cue_reads_each_form(self):
        for sentence in POSTMODIFIED:
            with self.subTest(sentence):
                self.assertIsNotNone(cues.EM_EVALUATION_STATED.search(sentence))

    def test_each_form_holds_the_visit(self):
        for sentence in POSTMODIFIED:
            for text in (EM_BODY + sentence + '\n' + MARA_EM + '\n', EM_BODY + MARA_EM + '\n' + sentence + '\n'):
                with self.subTest(sentence, first=text.index(sentence) < text.index(MARA_EM)):
                    found = outcomes(run(text, [('43239', EM_BIOPSY), ('99213', sentence[:-1])]))
                    self.assertEqual(found['43239'], READY)
                    self.assertEqual(found['99213'][:2], ('selected', 'needs_clarification'))
                    self.assertTrue(EM <= set(found['99213'][2]))
                    self.assertEqual(em_questions(run(text, [('43239', EM_BIOPSY)])), EM)

    def test_controls_no_evaluation_is_read_in_these(self):
        for sentence in ('Cold forceps biopsies for evaluation of eosinophilic esophagitis were obtained from the distal '
                         'esophagus.', 'An assessment of the gastric mucosa was documented today.',
                         'Cold forceps biopsies for an evaluation for eosinophilic esophagitis were obtained from the distal '
                         'esophagus.',
                         'An evaluation for new-onset jaundice will be performed in clinic next week.',
                         'No separate evaluation for new-onset jaundice was performed today.'):
            with self.subTest(sentence):
                text = EM_BODY + sentence + '\n' + MARA_EM + '\n'
                found = outcomes(run(text, [('43239', EM_BIOPSY), ('99213', MARA_EM[:-1])]))
                self.assertEqual(found['99213'][:2], ('excluded', 'excluded'))
                self.assertEqual(em_questions(run(text, [('43239', EM_BIOPSY)])), set())


# --- A6 (L1d-r3): the running report's own instrument after a header line naming another service ---------------------

def colon_header(line, *body):
    return COLON.replace('Procedure: Colonoscopy\n', 'Procedure: Colonoscopy\n' + line + '\n') + ''.join(x + '\n'
                                                                                                         for x in body)


class RunningInstrumentTests(SimpleTestCase):
    """A6: after a note label line naming another service - refused (L1d) or accepted (L1f) - a line telling the
    running report's own examination by its instrument goes on with that report; its acts are its own again."""

    def test_the_colonoscopy_s_own_acts_after_a_header_line(self):
        for label in ('Additional procedure: EGD performed today (separate report)',
                      'Separate note: EGD performed the same day, see that report',
                      'Second procedure: Upper endoscopy performed the same day - reported separately',
                      'Addendum - EGD was also performed today; it is reported separately.',
                      'Separate procedure: EGD, performed the same day',
                      'Second procedure: EGD performed today', 'Separate note: EGD performed today',
                      'Procedure 2: EGD performed today'):
            with self.subTest(label):
                text = colon_header(label, 'A 4 mm sessile polyp was found in the sigmoid colon.',
                                    'It was removed with a cold snare.')
                self.assertEqual(outcomes(run(text, [('45385', 'It was removed with a cold snare.')]))['45385'], READY)
                text = colon_header(label, 'Biopsies were taken with cold forceps.')
                self.assertEqual(outcomes(run(text, [('45380', 'Biopsies were taken with cold forceps.')]))['45380'],
                                 READY)

    def test_an_upper_endoscopy_report_s_own_snare(self):
        text = (B + 'Upper endoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory '
                'surgery center\nProcedure: EGD\nSecond procedure: Colonoscopy performed the same day, see separate note\n'
                'The gastroscope was advanced to the second portion of the duodenum.\nA 6 mm polyp was removed with a hot '
                'snare.\n')
        self.assertEqual(outcomes(run(text, [('43251', 'A 6 mm polyp was removed with a hot snare.')]))['43251'], READY)

    def test_controls_the_note_s_own_instrument_or_a_denied_running_one_keeps_the_note(self):
        for lines in ((SCOPE_60, FS_BIOPSY), ('The colonoscope was not reinserted.', SCOPE_60, FS_BIOPSY),
                      ('The colonoscope and the flexible sigmoidoscope were both available.', SCOPE_60, FS_BIOPSY)):
            with self.subTest(lines):
                text = (COLON + CO_SNARE + '\n\nSeparate note: Flexible sigmoidoscopy (fictional) on 2026-10-14\n'
                        + ''.join(x + '\n' for x in lines))
                self.assertEqual([a.kind for a in acts(inventory(text), 'gi.colonoscopy')], ['snare'])
                found = outcomes(run(text, [('45385', CO_SNARE), ('45380', FS_BIOPSY)]))
                self.assertEqual(found['45380'][:2], ('selected', 'needs_clarification'))


# --- A7 (R1b-r3): a label restated without its site -----------------------------------------------------------------

MARA_LIKE = battery.R3_MARA_LIKE
ROWS = battery.R3_ROWS


class RestatedLabelTests(SimpleTestCase):
    """A7: a label restated without its site, by its size and in its own tract's context (a specimen table), still
    resolves; one restated with another size, or under another examination, resolves to nothing (R1b)."""

    def test_a_specimen_row_restating_a_label_resolves(self):
        for rows, label in ((ROWS.replace('COL-2: sigmoid colon\n8 mm polyp; ', 'COL-2: 8 mm polyp\n'), 'COL-2'),
                            (ROWS.replace('COL-2: sigmoid colon\n8 mm polyp; ', 'COL-2: 8 mm polyp, '), 'COL-2'),
                            (ROWS.replace('COL-2: sigmoid colon\n8 mm polyp; ', 'COL-2: polyp\n'), 'COL-2'),
                            (ROWS.replace('COL-1: ascending colon\n2 mm polyp; ', 'COL-1: 2 mm polyp\n'), 'COL-1')):
            with self.subTest(rows):
                text = MARA_LIKE.format(rows=rows)
                inv = inventory(text)
                self.assertEqual(conflicts(inv), [])
                found = outcomes(run(text, [(c, q) for c, q, _ in battery.R3_MARA_Q]))
                self.assertEqual(found, {'43239': READY, '45380': READY, '45385': READY})

    def test_mara_with_a_specimen_row_restated_without_its_site(self):
        text0 = (MARA / 'rev1.txt').read_text(encoding='utf-8')
        readme = json.loads((MARA / 'README.json').read_text(encoding='utf-8'))
        body = (MARA / 'corti-response.json').read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(), readme['corti_response_sha256'])
        for old, new in (('COL-2: sigmoid colon\n8 mm polyp; cold-snare removal', 'COL-2: 8 mm polyp\ncold-snare removal'),
                         ('COL-1: ascending colon\n2 mm polyp; jumbo cold biopsy forceps removal',
                          'COL-1: 2 mm polyp\njumbo cold biopsy forceps removal')):
            with self.subTest(new):
                self.assertEqual(text0.count(old), 1)
                text = text0.replace(old, new)
                request = corti.build_coding_request('corti', corti.ADAPTER_VERSION, text, date(2026, 11, 3),
                                                     corti.DEFAULT_MAX_REQUEST_BYTES)
                result = run(text, normalized=corti.normalize_coding_response('corti', request, body))
                self.assertEqual(outcomes(result), {'43239': READY, '45380': READY, '45385': READY})
                self.assertEqual(result.services['conflicts'], [])
                self.assertEqual(em_questions(result), set())
                self.assertEqual(bundled(result), [('gi.colonoscopy', 'clip')])

    def test_controls_another_size_or_another_examination_resolves_to_nothing(self):
        colon = (HEAD + 'Colonoscopy and EGD report\nCOLONOSCOPY\nThe colonoscope was advanced to the cecum.\nP1 - sigmoid '
                 'colon: a 4 mm polyp was removed with cold forceps.\n')
        narrative = (HEAD + 'Colonoscopy and EGD report\nThe colonoscope was advanced to the cecum.\nP1 - sigmoid colon: a '
                     '4 mm polyp was removed with cold forceps.\n')
        quote = 'P1 was removed with a hot snare.'
        for text in (colon + 'UPPER ENDOSCOPY\n' + GASTRO + ' \nStomach:\nP1: a 9 mm sessile polyp. ' + quote + '\n',
                     colon + 'UPPER ENDOSCOPY\n' + GASTRO + ' \nStomach:\nP1: a 4 mm sessile polyp. ' + quote + '\n',
                     colon + 'UPPER ENDOSCOPY\nStomach:\nP1: a 4 mm sessile polyp. ' + quote + '\n',  # its heading
                     colon + 'UPPER ENDOSCOPY\nP1: a 4 mm sessile polyp. ' + quote + '\n',  # its part
                     narrative + GASTRO + '\nP1: a sessile polyp. ' + quote + '\n'):  # no size: the last instrument
            with self.subTest(text[150:]):
                self.assertNotIn('P1', services._unique_labels(services._label_definitions(text),
                                                                services._restatement_context(text)))
                self.assertEqual(acts(inventory(text), 'gi.colonoscopy', 'snare'), [])
                self.assertEqual(outcomes(run(text, [('43251', quote), ('45385', quote)]))['45385'][:2],
                                 ('selected', 'needs_clarification'))
        # without a context, a size the restatement does not share still leaves the label unresolved (R1b's own test)
        self.assertNotIn('P1', services._unique_labels(services._label_definitions(
            colon + 'UPPER ENDOSCOPY\nStomach:\nP1: a 9 mm sessile polyp.\n')))
        # and a restatement with the label's size in its own tract's context resolves
        self.assertIn('COL-2', services._unique_labels(services._label_definitions(
            battery.R3_MARA_LIKE.format(rows='COL-2: 8 mm polyp\ncold-snare removal\n'))))


# --- A8: the residual ----------------------------------------------------------------------------------------------

class DashIndicationResidualTests(SimpleTestCase):
    """A8, measured and recorded: the dash-form indication heading is no indication section of routing's layout (H2
    frozen), so it reads as installed (READY); the colon form is held (V05)."""

    def test_the_dash_form_reads_as_installed_and_the_colon_form_is_held(self):
        line = 'Indication - surveillance after a sigmoid polyp was removed with a hot snare'
        today = battery.R8_TODAY_BX
        for heading, expected in ((line, READY), (line.replace(' - ', ': ', 1), held('performed_status'))):
            with self.subTest(heading):
                text = battery._r2v_indication(heading)
                found = outcomes(run(text, [('45380', today), ('45385', heading)]))
                self.assertEqual(found['45380'], READY)
                self.assertEqual(found['45385'], expected)
