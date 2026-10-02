"""Money wording: one status vocabulary for the doctor (core.doctor_status), a list of requests holding funds on the
billing page, and the right answer to a re-posted request while its earlier job is still pending.

Offline and synthetic: fixture generation, rows made directly. Wording only: amounts, settlement and the ledger are read,
never changed, and the tests check that no money row moves.
"""
import re
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core import doctor_status as ds
from core.jobs import CANCELLED_ERROR, LATE_RECEIPT, NOT_ADOPTED, PLATFORM_FAILURE
from core.models import Job, LedgerEntry, Reservation, Usage, Wallet
from . import test_workflow
from .test_workflow import TEST_SETTINGS

INTERNAL = re.compile(r'reconciliation|staged|validating|not_adopted|platform_failure|not_processed|administrator:|'
                      r'Resolved by|Worker stopped|automatic retry|Late provider evidence', re.I)
ADMIN_NOTES = ['Resolved by administrator: settled provider cost absorbed by QuillMD.',
               'Resolved by administrator: no provider cost evidenced.', LATE_RECEIPT,
               'Worker stopped with an unknown provider outcome. Automatic retry is disabled.',
               'Late provider evidence requires financial reconciliation; this attempt cannot run again.',
               'Batch request outcome requires reconciliation; it will not be sent again.']


class Mapping(TestCase):
    def job(self, state, error=''):
        return Job(state=state, error=error, kind='generation')

    def test_every_state_reads_in_the_doctor_s_words_without_internal_words_or_administrator_notes(self):
        cases = [('queued', ''), ('running', ''), ('staged', ''), ('validating', ''), ('succeeded', ''), ('cancelled', CANCELLED_ERROR),
                 ('failed', NOT_ADOPTED + 'Source or permission changed; output was not adopted.'),
                 ('failed', PLATFORM_FAILURE + 'The provider returned an error.'), ('failed', 'Access was revoked before processing.')]
        cases += [('reconciliation', note) for note in ADMIN_NOTES] + [('failed', note) for note in ADMIN_NOTES]
        for state, error in cases:
            with self.subTest(state=state, error=error[:40]):
                status = ds.doctor_status(self.job(state, error))
                self.assertIn(status.key, ds.LABELS)
                self.assertIsNone(INTERNAL.search(status.label + ' ' + status.explanation), status)
                self.assertNotEqual(status.key, 'unknown')
                # Refutation F5: `charged` is what the ledger shows (core.tests.test_doctor_status_ledger), not a reading of
                # the state; these unsaved jobs have no ledger entries, so none is charged.
                self.assertFalse(status.charged)

    def test_pending_held_and_ended_states_say_what_happens_to_the_money(self):
        self.assertEqual(ds.doctor_status(self.job('queued')).label, 'Waiting to start')
        self.assertTrue(ds.doctor_status(self.job('running')).pending)
        held = ds.doctor_status(self.job('reconciliation', LATE_RECEIPT))
        self.assertEqual((held.label, held.pending), ('On hold for review', True))
        self.assertIn('within the maximum you approved', held.explanation)
        self.assertIn('No charge is recorded', ds.doctor_status(self.job('failed', NOT_ADOPTED + 'Changed.')).explanation)
        self.assertIn('not charged to you', ds.doctor_status(self.job('failed', PLATFORM_FAILURE + 'Error.')).explanation)
        self.assertEqual(ds.doctor_status(self.job('cancelled', CANCELLED_ERROR)).explanation,
                         'Cancelled before any provider request; nothing was charged.')
        self.assertEqual(ds.doctor_status(self.job('mystery')).key, 'unknown')


@override_settings(**TEST_SETTINGS)
class Pages(TestCase):
    workflow = test_workflow.DocumentWorkflow
    setUp, make_docx, upload = workflow.setUp, workflow.make_docx, workflow.upload
    create_encounter = workflow.create_encounter
    NOTES = 'Symptoms: No chest pain.\nExamination: Normal gait.'

    def money(self):
        return (list(Reservation.objects.order_by('pk').values()), list(LedgerEntry.objects.order_by('pk').values()),
                list(Wallet.objects.order_by('pk').values('pk', 'balance', 'reserved')), Usage.objects.count())

    def test_a_stale_re_post_while_the_first_request_is_queued_says_so_not_answer_draft(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.NOTES)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/generate/').status_code, 302)
        job = Job.objects.get(encounter=encounter); self.assertEqual(job.state, 'queued')
        before = self.money()
        response = self.client.post(f'/encounters/{encounter.pk}/generate/', follow=True)
        text = response.content.decode()
        self.assertNotIn('already have an answer draft', text)  # ac43e379: it said so while the request was queued
        self.assertIn('was already made and is waiting to start. No new request was made and nothing more was charged.', text)
        self.assertEqual(Job.objects.filter(encounter=encounter).count(), 1); self.assertEqual(self.money(), before)
        # Once it has completed, the earlier answer is right.
        Job.objects.filter(pk=job.pk).update(state='succeeded')
        response = self.client.post(f'/encounters/{encounter.pk}/generate/', follow=True)
        self.assertContains(response, 'These source notes already have an answer draft from an earlier request.')
        # A charged completion keeps the page's own next step, not a generic status sentence.
        self.assertContains(response, 'The answer draft is ready below.')

    def test_the_document_page_shows_the_doctor_status_never_the_state_word_or_administrator_note(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.NOTES)
        Job.objects.create(encounter=encounter, user=self.user, request_key='held:1', state='reconciliation',
                           error='Worker stopped with an unknown provider outcome. Automatic retry is disabled.')
        page = self.client.get(f'/encounters/{encounter.pk}/').content.decode()
        self.assertIn('data-request-status="held">On hold for review</span>', page)
        self.assertNotIn('Automatic retry is disabled', page)  # ac43e379: the administrator's note, verbatim
        self.assertNotIn('>reconciliation<', page); self.assertNotIn('· reconciliation', page)  # list and latest-job notice
        self.assertIn('data-latest-job role="status"><strong>Generation · <span data-request-status="held">On hold for review</span>', page)
        self.assertIn('<dt>Status</dt><dd>Draft</dd>', page)
        self.assertIn('<span class="badge draft">Draft</span>', page)  # the heading badge, not the raw word

    def test_the_billing_page_lists_requests_holding_funds_with_their_status(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.NOTES)
        wallet = Wallet.objects.get(user=self.user, kind='promo')
        job = Job.objects.create(encounter=encounter, user=self.user, request_key='held:2', state='reconciliation', error=LATE_RECEIPT)
        Reservation.objects.create(job=job, wallet=wallet, amount=Decimal('0.25'), state='held')
        settled = Job.objects.create(encounter=encounter, user=self.user, request_key='done:2', state='succeeded')
        Reservation.objects.create(job=settled, wallet=wallet, amount=Decimal('0.50'), state='settled')
        before = self.money()
        page = self.client.get('/billing/')
        self.assertEqual(page.status_code, 200)
        rows = page.context['held_requests']
        self.assertEqual([(row['job'].pk, row['amount'], row['status'].key) for row in rows], [(job.pk, Decimal('0.25'), 'held')])
        text = page.content.decode()
        self.assertIn('Requests holding funds', text); self.assertIn('data-held-request', text)
        self.assertIn('On hold for review', text); self.assertNotIn('an administrator must reconcile it', text)
        self.assertEqual(self.money(), before)  # read-only
        detail = self.client.get(f'/billing/jobs/{job.pk}/').content.decode()
        self.assertIn('data-request-status="held">On hold for review</span>', detail)


@override_settings(**TEST_SETTINGS)
class HeldListScope(TestCase):
    """Refutation F11 (dc33e094): the list of requests holding funds was every held reservation on the viewer's wallets, and a
    clinician whose request held funds on the organization's wallet saw nothing. Refutation M1 (4cfa4301): the repair scoped
    the list to departments the viewer owns while the wallet strip and the charge page use organization ownership, so the
    owner of another department of the PAYING organization saw that wallet's funds reserved, "No request is holding funds",
    and still opened the charge page. ONE scope now (core.views.owned_organizations): the viewer's own requests, and those
    an organization the viewer owns pays for (the Organization owner role, held in any of its departments) — what the
    wallet strip shows and what the charge page opens."""
    workflow = test_workflow.DocumentWorkflow
    setUp, make_docx, upload, create_encounter = workflow.setUp, workflow.make_docx, workflow.upload, workflow.create_encounter

    def held(self, client):
        return sorted((str(row['job'].pk), row['amount'], row['label']) for row in client.get('/billing/').context['held_requests'])

    def member(self, name, department, role, active=True):
        from django.test import Client
        from core.models import Membership, User
        user = User.objects.create_user(username=name, email=name + '@synthetic.invalid', verified_at=timezone.now())
        Membership.objects.create(user=user, department=department, role=role, active=active)
        client = Client(); client.force_login(user)
        return user, client

    def test_one_scope_for_the_wallet_strip_the_held_list_and_the_charge_page(self):
        from core.models import Department, Organization
        template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, 'Symptoms: no chest pain.\nExamination: Normal gait.')
        org = f'organization:{self.organization.pk}'
        org_wallet = Wallet.objects.create(organization=self.organization, kind='paid', balance=Decimal('5'), reserved=Decimal('0.8'))
        mine = Job.objects.create(encounter=encounter, user=self.user, request_key='m1:mine', state='queued', payer=org)
        Reservation.objects.create(job=mine, wallet=org_wallet, amount=Decimal('0.40'), state='held')
        # FG-9: a form-mapping request the organization pays for, named in the doctor's words.
        mapping = Job.objects.create(mapping_version=version, user=self.user, kind='mapping', request_key='m1:mapping',
                                     state='queued', payer=org, config={'source_sha256': template.sha256,
                                     'department_id': str(template.department_id), 'mapping_version_id': str(version.pk)})
        Reservation.objects.create(job=mapping, wallet=org_wallet, amount=Decimal('0.40'), state='held')
        colleague, colleague_client = self.member('m1-colleague', self.department, 'clinician')
        from core.billing import welcome_credit
        welcome_credit(colleague)
        personal = Job.objects.create(encounter=encounter, user=colleague, request_key='m1:personal', state='queued',
                                      payer=f'user:{colleague.pk}')
        Reservation.objects.create(job=personal, wallet=Wallet.objects.get(user=colleague, kind='promo'),
                                   amount=Decimal('0.40'), state='held')
        paid_by_org = sorted([(str(mine.pk), Decimal('0.40'), 'Generation'), (str(mapping.pk), Decimal('0.40'), 'Form mapping')])
        other_department = Department.objects.create(organization=self.organization, name='Other department, same org')
        outsider = Department.objects.create(organization=Organization.objects.create(name='Synthetic outsider'), name='X')
        # viewer: (client, the requests listed, whether the viewer owns the paying organization)
        viewers = {
            'requester': (self.client, paid_by_org, False),                                # dc33e094: []
            'owner of the requesting department': (self.member('m1-owner', self.department, 'owner')[1], paid_by_org, True),
            'owner of another department of the paying organization':                      # 4cfa4301: [] beside $0.80 reserved
                (self.member('m1-other-owner', other_department, 'owner')[1], paid_by_org, True),
            'colleague, personally paid': (colleague_client, [(str(personal.pk), Decimal('0.40'), 'Generation')], False),
            'former owner (membership inactive)':                                          # FG-3
                (self.member('m1-former-owner', self.department, 'owner', active=False)[1], [], False),
            'owner in another organization': (self.member('m1-outsider', outsider, 'owner')[1], [], False),
        }
        for viewer, (client, expected, owner) in viewers.items():
            with self.subTest(viewer=viewer):
                page = client.get('/billing/')
                self.assertEqual(self.held(client), expected)
                # The organization's wallet is on the strip exactly for its owners, and beside it the requests holding its
                # funds are listed: never its funds reserved beside "No request is holding funds" (M1).
                self.assertEqual(org_wallet.pk in [wallet.pk for wallet in page.context['wallets']], owner)
                text = page.content.decode()
                self.assertEqual('No request is holding funds' in text, not expected)
                for row in page.context['held_requests']:                                 # FG-10: every row links, and opens
                    self.assertIn(f'/billing/jobs/{row["job"].pk}/', text)
                    self.assertEqual(client.get(f'/billing/jobs/{row["job"].pk}/').status_code, 200)
                    if row['job'].user_id != page.context['user'].pk:
                        self.assertIn(row['job'].user.email, text)                        # the requester is named
                        self.assertNotRegex(row['status'].explanation, r'(?i)\byou(r)?\b')  # R3B-2: not "you approved"
                    else:
                        self.assertIn('you approved', row['status'].explanation)          # the requester's own words
                for job in (mine, mapping, personal):                                     # the charge page agrees
                    opens = client.get(f'/billing/jobs/{job.pk}/').status_code == 200
                    self.assertEqual(opens, str(job.pk) in [row[0] for row in expected], (viewer, job.request_key))


from core.tests.test_generation_batch import BatchFixture, SETTINGS as BATCH_SETTINGS  # noqa: E402


@override_settings(**BATCH_SETTINGS)
class HeldListOneRowPerRequest(BatchFixture, TestCase):
    def test_a_complete_form_request_is_one_row_named_for_the_doctor(self):
        batch = self.admit()
        rows = self.client.get('/billing/').context['held_requests']
        parts = list(Reservation.objects.filter(job__generation_part__batch=batch, state='held').values_list('amount', flat=True))
        self.assertGreater(len(parts), 1)
        self.assertEqual([(row['label'], row['amount'], row['status'].key) for row in rows],
                         [('Generation', sum(parts), 'waiting')])  # dc33e094: one row per part, 'Generation_Part'
        page = self.client.get('/billing/').content.decode()
        self.assertNotIn('Generation_Part', page); self.assertNotIn('generation_part', page)

    def test_M2_the_rows_link_explains_the_whole_request_in_the_doctors_words(self):
        """4cfa4301: the one row of a complete form linked to part 1's charge page, which said "Total reserved for this
        request" with part 1's amount alone and was titled 'Generation_Part'."""
        import html
        from core.templatetags.console import usd
        batch = self.admit()
        rows = self.client.get('/billing/').context['held_requests']
        total = sum(Reservation.objects.filter(job__generation_part__batch=batch, state='held').values_list('amount', flat=True))
        self.assertEqual(rows[0]['amount'], total)
        page = html.unescape(self.client.get(f'/billing/jobs/{rows[0]["job"].pk}/').content.decode())
        self.assertNotIn('Generation_Part', page); self.assertNotIn('Generation_part', page)
        self.assertIn(f'Total reserved for the whole request: {usd(total)}', page)
        self.assertIn('part 1 of 2', page)

    def test_M4_the_row_cap_never_splits_a_complete_form_request(self):
        """4cfa4301 cut the reservations at 500 before grouping them, so 499 newer holds left the batch row with one part's
        amount. The cap is on rows: the batch row carries its whole amount, or is not shown."""
        batch = self.admit()
        total = sum(Reservation.objects.filter(job__generation_part__batch=batch, state='held').values_list('amount', flat=True))
        promo = Wallet.objects.get(user=self.user, kind='promo')
        def newer(count, start):
            jobs = Job.objects.bulk_create([Job(encounter=self.encounter, user=self.user, kind='transcription', state='queued',
                                                request_key=f'm4:{start + i}', payer=f'user:{self.user.pk}')
                                            for i in range(count)])
            Reservation.objects.bulk_create([Reservation(job=job, wallet=promo, amount=Decimal('0.001'), state='held')
                                             for job in jobs])
        newer(499, 0)
        rows = self.client.get('/billing/').context['held_requests']
        self.assertEqual(len(rows), 500)
        self.assertEqual([row['amount'] for row in rows if row['job'].kind == 'generation_part'], [total])  # 4cfa4301: one part
        newer(1, 499)
        rows = self.client.get('/billing/').context['held_requests']
        self.assertEqual(len(rows), 500)
        self.assertEqual([row for row in rows if row['job'].kind == 'generation_part'], [])  # older than the newest 500: absent

    def test_R3F11_each_parts_charge_page_names_its_own_part(self):
        import html
        batch = self.admit()
        for part in batch.parts.order_by('ordinal'):
            with self.subTest(ordinal=part.ordinal):
                page = html.unescape(self.client.get(f'/billing/jobs/{part.job_id}/').content.decode())
                self.assertIn(f'this page explains part {part.ordinal} of 2', page)


class OthersRequestsAreNotAddressedToTheViewer(TestCase):
    """Refutation R3B-2 of 75d11c09: the held list shows an owner of the paying organization the requests colleagues made,
    each with the requester's own sentence: 'the maximum charge you approved is held'. That owner approved nothing. A row
    of another person's request is told in the third person (doctor_status.for_others)."""
    def test_no_sentence_for_another_persons_request_says_you(self):
        from core.models import GenerationBatch  # noqa: F401  (the batch states are covered by the same sentences)
        cases = [('queued', ''), ('running', ''), ('reconciliation', ''), ('succeeded', ''), ('cancelled', CANCELLED_ERROR),
                 ('failed', PLATFORM_FAILURE + 'Provider supplied no usable transcript.'),
                 ('failed', NOT_ADOPTED + 'Source changed while this job ran; output was not adopted. Its recorded usage stays billed.'),
                 ('failed', 'Access was revoked before processing.'), ('unknown-state', '')]
        for state, error in cases:
            for charge in (0, Decimal('0.15')):
                with self.subTest(state=state, charge=charge), \
                        patch('core.doctor_status.net_charge', return_value=charge):
                    mine = ds.doctor_status(Job(state=state, error=error, kind='generation'))
                    theirs = ds.for_others(mine)
                    self.assertNotRegex(theirs.explanation, r'(?i)\byou(r)?\b')
                    # R4B-2: 'Billing shows it' is true only of the requester's Billing.
                    self.assertNotRegex(theirs.explanation, r"(?<!requester's )\bBilling\b")
                    self.assertNotEqual(theirs.explanation, theirs.label + '.')   # rewritten, never the bare fallback
                    self.assertEqual((theirs.key, theirs.label, theirs.charged), (mine.key, mine.label, mine.charged))
        waiting = ds.doctor_status(Job(state='queued', kind='generation'))
        self.assertIn('the maximum charge you approved', waiting.explanation)          # the requester's own words stay
        for unknown in ('A sentence no rewrite knows, addressed to you.', 'Your request is queued.',   # R4F-13: any case,
                        'You approved its maximum.', 'It waits for your approval.',                    # 'you' and 'your',
                        'Its charge is under Billing.'):                                            # and a bare Billing
            with self.subTest(unknown=unknown):
                self.assertEqual(ds.for_others(waiting._replace(explanation=unknown)).explanation, waiting.label + '.')


@override_settings(**TEST_SETTINGS)
class ColleaguesReadAnotherPersonsRequestInTheThirdPerson(TestCase):
    """Refutation R4B-1 of b3d8111d: the encounter page lists every request on the document to every member of its
    department, and each carried its requester's sentence ('the maximum charge you approved is held'), with no requester
    named. Another person's request reads in the third person there too (doctor_status.for_others)."""
    workflow = test_workflow.DocumentWorkflow
    setUp, make_docx, upload, create_encounter = workflow.setUp, workflow.make_docx, workflow.upload, workflow.create_encounter

    def test_the_encounter_page_tells_a_colleague_the_request_in_the_third_person(self):
        from django.test import Client
        from core.billing import reserve
        from core.models import Membership, User
        _t, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, 'Symptoms: no chest pain.\nExamination: Normal gait.')
        job = Job.objects.create(encounter=encounter, user=self.user, request_key='r4b1:job', state='queued', kind='generation')
        reserve(job, charge_limit=Decimal('0.40'))
        colleague = User.objects.create_user(username='r4b1-colleague', email='r4b1-colleague@synthetic.invalid',
                                             verified_at=timezone.now())
        Membership.objects.create(user=colleague, department=self.department, role='clinician')
        other = Client(); other.force_login(colleague)
        for state in ('queued', 'reconciliation'):
            Job.objects.filter(pk=job.pk).update(state=state)
            with self.subTest(state=state):
                theirs = other.get(f'/encounters/{encounter.pk}/').content.decode()
                mine = self.client.get(f'/encounters/{encounter.pk}/').content.decode()
                self.assertNotIn('you approved', theirs)                       # b3d8111d: the requester's sentence
                self.assertIn('the approved maximum', theirs)
                self.assertIn('you approved', mine)
