"""Repair round ec5, cluster CONTEXT (studio/gi/context.py): service dates and member-entered context.

Owner decision 2026-10-27 (narrow, install-first), must-fix class 1: a wrong or conflicting service date reaches a
provider request. The date sent is the document's own unambiguous date of service, a member value that agrees with it,
or a member value for a document that states none. A labelled date for another occurrence, a title naming another
document, or a qualifier of another field never supplies the date; a labelled date the reader cannot read or cannot
place, or a qualified first title, is kept as documented text a member value must agree with (else a member conflict,
interpretations 11, 19 and 22). Synthetic text only; no network (the suite's FakeProvider).

Refutation round 2 (tests/test_repairs_7c8_context.py) changed seven tests here (four engine pins, three end to end),
each marked where it stands: a dated title
and a labelled date that differs from it are a conflict - never the title silently, never the label silently - and
another document's title is kept as evidence a member date must agree with.
"""
import json
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from studio import models
from studio.gi import context
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
VISIT_BODY = ('Established patient office visit for chronic constipation.\n'
              'Total time on the date of the encounter was 24 minutes.\n')


def date_fact(text):
    return context.extract_context(text)['service_date']


def merged_date(text, value):
    return context.merge_user_values(context.extract_context(text), {'service_date': value})['service_date']


class DateAssertions:
    def assert_document(self, text, value):
        fact = date_fact(text)
        self.assertEqual((fact.origin, fact.value), ('document', value), [e.text for e in fact.evidence])

    def assert_never(self, text, *dates):
        fact = date_fact(text)
        self.assertFalse(fact.origin == 'document' and fact.value in dates, (fact.origin, fact.value))

    def assert_member_conflict(self, text, value):
        fact = merged_date(text, value)
        self.assertEqual((fact.origin, fact.value), ('conflict', None), fact.note)
        self.assertTrue(context.is_member_conflict(fact), fact.note)

    def assert_member_date(self, text, value):
        fact = merged_date(text, value)
        self.assertEqual((fact.origin, fact.value), ('user', value), fact.note)

    def assert_title_conflict(self, text, own, other):
        """Refutation round 2, rule B: a dated title and a labelled date that differs from it are a conflict - asked,
        both listed - never a silent choice of either; the member settles it by choosing the note's own date."""
        fact = date_fact(text)
        self.assertEqual((fact.origin, set(context.documented_values(fact))), ('conflict', {own, other}),
                         [e.text for e in fact.evidence])
        self.assert_member_date(text, own)
        self.assert_member_conflict(text, '1998-01-01')


class LabelledDateOfAnotherOccurrenceTests(DateAssertions, SimpleTestCase):
    """negtime-8: a labelled date whose label names another occurrence ("Outside procedure date", "Index procedure
    date", a table row about an outside colonoscopy) is never the service date; a label carrying a word this service
    cannot place ("Initial visit date", "Referring visit date") is never taken as the date either - it is asked."""

    TITLED = HEAD + 'Colonoscopy report - 10/14/2026\n'

    def test_the_finding_s_inputs_never_give_the_other_occurrence_s_date(self):
        cases = (
            (self.TITLED + 'Indication: Surveillance. Outside procedure date: 09/03/2026 (cold snare polypectomy of '
                           'two adenomas).\nTechnique: The colonoscope was advanced to the cecum.\nFindings: A 5 mm '
                           'sigmoid polyp was removed with a cold snare.\n', '2026-09-03'),
            (self.TITLED + 'Index procedure date: 04/02/2026 (EMR of a 25 mm lesion).\nFindings: a flat scar.\n',
             '2026-04-02'),
            (self.TITLED + 'Outside colonoscopy | Procedure date | 2021-05-03\n', '2021-05-03'),
            (self.TITLED + 'Outside report | Procedure date | 09/03/2026 | Two adenomas removed\n', '2026-09-03'),
        )
        for text, other in cases:
            with self.subTest(text=text.splitlines()[2][:60]):
                self.assert_never(text, other)
                # Refutation round 2, rule B: the title gives the date only when every labelled date agrees with it -
                # the reader's "another occurrence" may be a misreading (c2:2, c2:5) - so the two are a conflict, which
                # the member settles by choosing the title's date (this pin had the title win silently).
                self.assert_title_conflict(text, '2026-10-14', other)
        widened = HEAD + ('PROCEDURE NOTE: Colonoscopy - 14-Oct-2026\nIndication: surveillance. Outside procedure date: '
                          '03-Sep-2026\n')
        self.assert_never(widened, '2026-09-03')

    def test_a_label_carrying_a_word_this_service_cannot_place_is_asked(self):
        office = HEAD + 'GI office visit - 10/20/2026\n'
        for label, other in (('Initial visit date: 03/11/2025', '2025-03-11'),
                             ('Referring visit date: 09/30/2026.', '2026-09-30')):
            with self.subTest(label=label):
                text = office + label + '\n' + VISIT_BODY
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value), ('conflict', None))
                self.assertEqual(set(context.documented_values(fact)), {'2026-10-20', other})
                self.assert_member_date(text, '2026-10-20')  # the member settles it by choosing a documented value
                self.assert_member_conflict(text, '1998-01-01')
                alone = HEAD + label + '\n' + VISIT_BODY
                fact = date_fact(alone)
                self.assertEqual((fact.origin, fact.value), ('missing', None))
                self.assertIn(label.rstrip('.'), [e.text for e in fact.evidence])
                self.assert_member_conflict(alone, '2026-10-20')

    def test_controls_the_note_s_own_labels_are_read(self):
        # refutation round 2, rule B: beside the title these are a conflict the member settles (the title won silently)
        self.assert_title_conflict(self.TITLED + 'Prior procedure date: 09/03/2026\n', '2026-10-14', '2026-09-03')
        self.assert_title_conflict(self.TITLED + 'Last procedure date: 09/03/2026\n', '2026-10-14', '2026-09-03')
        for text, value in ((HEAD + 'Colonoscopy procedure date: 10/14/2026\n', '2026-10-14'),
                            (HEAD + 'Office visit date: 10/20/2026\n' + VISIT_BODY, '2026-10-20'),
                            (HEAD + "Today's visit date: 10/20/2026\n" + VISIT_BODY, '2026-10-20'),
                            (HEAD + 'Date of service: 2026-10-20\n' + VISIT_BODY, '2026-10-20'),
                            (HEAD + 'Field | Value\nProcedure date | 2026-09-30\n', '2026-09-30')):
            with self.subTest(text=text.splitlines()[1]):
                self.assert_document(text, value)
        for line in ('Previous procedure date: 2019-05-01', 'Next visit date: 2026-12-01', 'Prior DOS: 2025-01-02',
                     'Outside procedure date: 2019-05-01'):
            with self.subTest(line=line):
                self.assertEqual(date_fact(HEAD + line + '\n').origin, 'missing')


class QualifierOfAnotherFieldTests(DateAssertions, SimpleTestCase):
    """negtime-15: a qualifier that belongs to another field or another date on the date-of-service line ("Next
    colonoscopy: 10/2029", "recall due 10/2029", "Last name:", "Visit type: Follow-up") never discards the labelled
    date - which then left a letter or title date to be taken and sent."""

    def test_the_labelled_date_is_read(self):
        cases = (
            ('Procedure date: 10/14/2026    Next colonoscopy: 10/2029\nPROCEDURE NOTE: Colonoscopy\n', '2026-10-14'),
            ('Date of service: 10/14/2026 (recall due 10/2029)\n', '2026-10-14'),
            ('Last name: Synthetic    First name: Alex    DOS: 10/14/2026\n', '2026-10-14'),
            ('Next colonoscopy 10/2029, procedure date: 10/14/2026\n', '2026-10-14'),
        )
        for body, value in cases:
            with self.subTest(body=body.splitlines()[0]):
                self.assert_document(HEAD + body, value)

    def test_a_title_or_letter_date_never_replaces_it(self):
        cases = (
            ('Date: 10/16/2026\nProcedure date: 10/14/2026    Next colonoscopy: 10/2029\nPROCEDURE NOTE: '
             'Colonoscopy\n', '2026-10-14', '2026-10-16'),
            ('Colonoscopy report - 10/16/2026\nProcedure date: 10/14/2026    Next colonoscopy: 10/2029\n',
             '2026-10-14', '2026-10-16'),
            ('GI procedure report - 10/15/2026\nLast name: Synthetic    First name: Alex    DOS: 10/14/2026\n',
             '2026-10-14', '2026-10-15'),
        )
        for body, value, other in cases:
            with self.subTest(body=body.splitlines()[0]):
                self.assert_never(HEAD + body, other)
                if body.startswith('GI procedure report'):
                    # a report naming no service this release codes is never the note's heading (refutation round 2,
                    # c2:7): the labelled date stands
                    self.assert_document(HEAD + body, value)
                else:
                    # Refutation round 2, rule B: the note's own labelled date and its own dated title (or "Date:"
                    # line) that differs are a conflict, never a silent choice: c2:1 had a planned procedure's
                    # labelled date win over the report's title this way, sent, and an act done that day excluded
                    # against it (this pin had the labelled date win silently).
                    self.assert_title_conflict(HEAD + body, value, other)

    def test_a_qualifier_that_may_be_the_date_s_own_holds_it(self):
        # "Visit type: Follow-up" may or may not qualify the visit date: the date is held - never dropped so that the
        # letter's "Date:" is taken, never taken itself; the member settles it by choosing the labelled date.
        letter = HEAD + 'Date: 10/27/2026\nRe: GI office visit\nDate of visit: 10/20/2026    Visit type: Follow-up\n'
        self.assert_never(letter, '2026-10-27')
        fact = date_fact(letter)
        self.assertEqual((fact.origin, set(context.documented_values(fact))), ('conflict', {'2026-10-27', '2026-10-20'}))
        self.assert_member_date(letter, '2026-10-20')
        alone = HEAD + 'Date of visit: 10/20/2026    Visit type: Follow-up\n' + VISIT_BODY
        self.assertEqual((date_fact(alone).origin, [e.text for e in date_fact(alone).evidence]),
                         ('missing', ['Date of visit: 10/20/2026']))
        self.assert_member_date(alone, '2026-10-20')
        self.assert_member_conflict(alone, '1998-01-01')

    def test_controls_a_qualifier_of_the_date_itself_is_never_passed_over(self):
        for line in ('Procedure date: 2026-11-04 (scheduled)', 'Date of service: 10/14/2026, scheduled',
                     'Procedure date: 2026-11-04 - planned', 'Date of service | 10/14/2026 | scheduled'):
            with self.subTest(line=line):
                self.assertEqual(date_fact(HEAD + line + '\n').origin, 'missing')
        # a qualifier across a sentence or a field may be the date's own: never read as the documented date
        titled = HEAD + 'Colonoscopy report - 10/14/2026\n'
        for line in ('Status: scheduled    Procedure date: 11/04/2026', 'Procedure date: 11/04/2026 - Status: scheduled',
                     'Colonoscopy scheduled. Procedure date: 11/04/2026.', 'Procedure date: 11/04/2026. Scheduled.'):
            with self.subTest(line=line):
                self.assert_never(HEAD + line + '\n', '2026-11-04')
                self.assert_never(titled + line + '\n', '2026-11-04', '2026-10-14')  # held beside the title: asked
        self.assert_never(titled + 'Outside colonoscopy    Procedure date    2021-05-03\n', '2021-05-03', '2026-10-14')
        # a plan field's date is a planned date (sections): never the service date, and the report's own title is
        self.assert_never(HEAD + 'Follow-up: Procedure date: 11/04/2026\n', '2026-11-04')
        self.assert_document(titled + 'Follow-up: Procedure date: 11/04/2026\n', '2026-10-14')
        self.assert_document(HEAD + 'Procedure date: 10/14/2026    Endoscopist: Dr. A. Synthetic\n', '2026-10-14')


class TitleOfAnotherDocumentTests(DateAssertions, SimpleTestCase):
    """negtime-14: the first dated title near the top is never another document's own date (a pathology or imaging
    report's) or a letter's date standing beside the encounter it names."""

    PATHOLOGY_FIRST = (HEAD + 'Surgical pathology report: 10/17/2026\nSpecimen A: gastric antrum, biopsy - chronic '
                              'gastritis.\n\nPROCEDURE NOTE: EGD\nTechnique: The upper endoscope was advanced to the '
                              'second portion of the duodenum.\nFindings: Biopsies were taken from the antrum.\n')

    def test_another_document_s_title_gives_no_date(self):
        appended = (HEAD + 'PROCEDURE NOTE: EGD\nFindings: Biopsies were taken from the antrum.\n'
                           'Surgical pathology report: 10/17/2026\nSpecimen A: gastric antrum.\n')
        imaging = HEAD + 'CT abdomen and pelvis report: 10/09/2026\nNo acute findings.\nPROCEDURE NOTE: EGD\n'
        pathology, ct = 'Surgical pathology report: 10/17/2026', 'CT abdomen and pelvis report: 10/09/2026'
        for text, other, title in ((self.PATHOLOGY_FIRST, '2026-10-17', pathology), (appended, '2026-10-17', pathology),
                                   (imaging, '2026-10-09', ct)):
            with self.subTest(text=text.splitlines()[1][:40]):
                fact = date_fact(text)
                # Refutation round 2, rule A (c2:3, c2:7): another document's title is never the date, but it is kept
                # as documented evidence, never dropped with nothing left behind - a visit title misread as another
                # discipline's let a member's 1998-01-01 be sent. A member date must agree with it: the date asked
                # is answered by the date the evidence reads, and any other member date is a conflict (an over-hold
                # for a member who knows the procedure's own date; this pin had no evidence kept).
                self.assertEqual((fact.origin, fact.value, [e.text for e in fact.evidence]), ('missing', None, [title]))
                self.assert_member_date(text, other)
                for member in ('2026-10-14', '1998-01-01'):
                    self.assert_member_conflict(text, member)

    def test_a_letter_date_beside_the_encounter_it_names_is_asked(self):
        letter = HEAD + ('Date: 10/27/2026\nRe: GI consultation of 10/20/2026\nDear Dr. Synthetic,\nThank you for '
                         'referring this patient.\n')
        fact = date_fact(letter)
        self.assertEqual((fact.origin, fact.value), ('conflict', None))
        self.assertEqual(set(context.documented_values(fact)), {'2026-10-27', '2026-10-20'})
        self.assert_member_date(letter, '2026-10-20')
        self.assert_member_conflict(letter, '1998-01-01')

    def test_controls_the_note_s_own_titles(self):
        self.assert_document(HEAD + 'EGD report - 10/14/2026\nTechnique: advanced to the duodenum.\n', '2026-10-14')
        self.assert_document(HEAD + 'Endoscopic ultrasound report: 10/14/2026\nThe echoendoscope was passed.\n',
                             '2026-10-14')
        self.assert_document(HEAD + '\nHepatology clinic note - 9/28/2026\n\nSeen for ascites follow-up.\n',
                             '2026-09-28')
        for text in (HEAD + 'GI consultation note: 2026-10-20\nPathology report: 2026-10-14\n',
                     HEAD + 'Surgical pathology report: 10/17/2026\nEGD report - 10/14/2026\n',
                     HEAD + 'Date: 10/27/2026\nGI consultation of 10/20/2026\nDear Dr. Synthetic,\n'):
            with self.subTest(text=text.splitlines()[1]):
                self.assertEqual(date_fact(text).origin, 'conflict')


class MemberDateAgainstDocumentedTextTests(DateAssertions, SimpleTestCase):
    """context-3: a member date never silently replaces documented date text the reader does not use - a labelled date
    in a form it does not read, a label above its value, a title with its date below it, a qualified first title.
    It is a member conflict unless it agrees with what that text reads."""

    READABLE = ('Date of service: Tuesday, October 20, 2026', 'Date of service:\n10/20/2026',
                'Date of Service\n10/20/2026', 'Colonoscopy Report\n10/20/2026', 'GI follow-up visit - 10/20/2026')
    UNREAD = ('DOS: 10/20/26', 'Date of service: 10-20-2026', 'Date of service: 2026/10/20',
              'Date of service: 20.10.2026')

    def test_a_different_member_date_is_a_conflict(self):
        for header in self.READABLE + self.UNREAD:
            with self.subTest(header=header):
                text = HEAD + header + '\n' + VISIT_BODY
                self.assertEqual(date_fact(text).origin, 'missing')
                self.assertTrue(date_fact(text).evidence)
                self.assert_member_conflict(text, '1998-01-01')

    def test_a_member_date_that_agrees_with_the_text_is_taken(self):
        for header in self.READABLE:
            with self.subTest(header=header):
                self.assert_member_date(HEAD + header + '\n' + VISIT_BODY, '2026-10-20')

    def test_controls(self):
        for text in (HEAD + VISIT_BODY, HEAD + 'Date of service: pending\n' + VISIT_BODY):
            with self.subTest(text=text.splitlines()[1]):
                self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))
                self.assert_member_date(text, '1998-01-01')
        iso = HEAD + 'Date of service: 2026-10-20\n' + VISIT_BODY
        self.assert_member_conflict(iso, '1998-01-01')
        self.assert_member_date(iso, '2026-10-20')
        invalid = HEAD + 'Date of service: 2026-02-30\n' + VISIT_BODY
        self.assertIn('not a valid calendar date', date_fact(invalid).note)
        self.assert_member_conflict(invalid, '2026-02-28')


class EarlierContextFindingsTests(DateAssertions, SimpleTestCase):
    """context-0 and context-1 (repaired before this round by 8d0897ec0): re-checked at this head with their smallest
    inputs; kept as guards."""

    def test_context_0_a_member_date_beside_an_unreadable_second_date_is_a_conflict(self):
        for body in ('Date of service: 2026-10-20\nVisit date: 20/10/2026\n',
                     'Date of service: 2026-10-14\nProcedure date: 2026-10-20\nDOS: 02/30/2026\n',
                     'Date of service: 10/20/2026\nVisit date: 10/32/2026\n'):
            with self.subTest(body=body):
                self.assert_member_conflict(HEAD + body + VISIT_BODY, '1998-01-01')

    def test_context_1_a_member_setting_against_an_unrecognised_documented_code_is_a_conflict(self):
        facts = context.extract_context(HEAD + 'Place of service: 31\nSeen at the skilled nursing facility.\n')
        merged = context.merge_user_values(facts, {'setting': 'office'})['setting']
        self.assertTrue(context.is_member_conflict(merged))


class Provider(FakeProvider):
    """FakeProvider whose response names only the selections the request's own text contains."""

    def send(self, request, *, deadline_s):
        every = self.selections
        self.selections = [(code, quote) for code, quote in every if quote in request.contexts[0]]
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.selections = every


@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class RequestDateTests(TestCase):
    """End to end with the suite's FakeProvider: what the provider request carries as its date of service."""

    SNARE = ('45385', 'was removed with a cold snare')
    VISIT = ('99213', 'Total time on the date of the encounter was 24 minutes.')

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = Provider(selections=[self.VISIT, self.SNARE])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def finished(self, text, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        return response.json()['id']

    def set_context(self, encounter_id, values):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/encounters/{encounter_id}/context', data=json.dumps(values),
                                        content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        drain()

    def dates_sent(self, encounter_id):
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id, sent=True).order_by('created_at')
        return [[c for c in run.contexts[1:]] for run in runs]

    def test_negtime_8_the_outside_procedure_date_is_never_sent(self):
        text = HEAD + ('Colonoscopy report - 10/14/2026\nIndication: Surveillance. Outside procedure date: 09/03/2026 '
                       '(two adenomas removed).\nTechnique: The colonoscope was advanced to the cecum.\nFindings: A 5 mm '
                       'sigmoid polyp was removed with a cold snare.\n')
        encounter_id = self.finished(text)
        # refutation round 2, rule B: the outside date beside the report's title is a conflict: asked, no date sent
        # (this pin sent the title's date while the labelled date was set aside)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': '2026-10-14'})  # the member chooses the report's date
        self.assertEqual(self.dates_sent(encounter_id), [[], ['Date of service: 2026-10-14']])

    def test_negtime_14_a_pathology_title_date_is_never_sent_and_the_member_date_answers(self):
        encounter_id = self.finished(TitleOfAnotherDocumentTests.PATHOLOGY_FIRST)
        self.assertEqual(self.dates_sent(encounter_id), [[]])  # no documented date: the date is asked
        # refutation round 2, rule A: the pathology report's date is kept as evidence, so a member date that differs
        # from it is a member conflict and is never sent (this pin sent it): an over-hold, the date stays asked
        self.set_context(encounter_id, {'service_date': '2026-10-14'})
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertTrue(context.is_member_conflict(encounter.current_context.facts['service_date']))

    def test_negtime_15_the_labelled_date_is_sent_not_the_letter_date(self):
        text = HEAD + ('Date: 10/16/2026\nProcedure date: 10/14/2026    Next colonoscopy: 10/2029\nPROCEDURE NOTE: '
                       'Colonoscopy\nFindings: A 5 mm sigmoid polyp was removed with a cold snare.\n')
        encounter_id = self.finished(text)
        # refutation round 2, rule B: the labelled date and the "Date:" line that differs are a conflict: asked, no
        # date sent, never the letter's (this pin sent the labelled date over the differing "Date:" silently)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': '2026-10-14'})  # the member chooses the labelled date
        self.assertEqual(self.dates_sent(encounter_id), [[], ['Date of service: 2026-10-14']])

    def test_context_3_a_member_date_against_an_unread_documented_date_is_held(self):
        text = OFFICE_NOTE.replace('Date of service: 2026-10-20', 'Date of service: Tuesday, October 20, 2026')
        encounter_id = self.finished(text, service_date='1998-01-01')
        self.assertEqual(self.dates_sent(encounter_id), [])
        held = models.ProviderRun.objects.get(encounter_id=encounter_id)
        self.assertEqual((held.state, held.scope), (models.ProviderRun.NOT_SENT,
                                                    {'held': models.ProviderRun.HELD_MEMBER_DATE_CONFLICT}))
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'needs_clarification')
        self.set_context(encounter_id, {'service_date': '2026-10-20'})  # agreeing with the text releases it
        self.assertEqual(self.dates_sent(encounter_id), [['Date of service: 2026-10-20']])

    def test_context_0_and_1_controls_still_hold(self):
        day_first = OFFICE_NOTE.replace('Date of service: 2026-10-20\n',
                                        'Date of service: 2026-10-20\nVisit date: 20/10/2026\n')
        encounter_id = self.finished(day_first, service_date='1998-01-01')
        self.assertEqual(self.dates_sent(encounter_id), [])
        pos31 = OFFICE_NOTE.replace('Place of service: Office, in-person outpatient visit', 'Place of service: 31')
        encounter_id = self.finished(pos31)
        self.set_context(encounter_id, {'setting': 'office'})
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertTrue(context.is_member_conflict(encounter.current_context.facts['setting']))
        proposal = encounter.current_assessment.proposals.get(code='99213')
        self.assertNotEqual(proposal.status, 'ready')
        self.assertEqual(encounter.state, 'needs_clarification')
