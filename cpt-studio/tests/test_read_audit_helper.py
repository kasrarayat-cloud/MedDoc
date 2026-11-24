"""studio.read_audit, the helper (release 1; RELEASE-1-SPEC 3.3 and 3.7; C1): one AccessRecord per read, written with
the right ids, refused when it cannot be written (fail closed), a poll's repeat recognised, and views marked for the
route-coverage test. The views that call it are Lane 3's (tests/test_read_audit.py). Synthetic data only."""
from __future__ import annotations

import functools
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from importlib import import_module
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from studio import models, read_audit, request_meta
from tests.support import coding as f

REQUEST_ID = 'feedfacefeedfacefeedfacefeedface'


class ReadAuditCase(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.other_ws = f.workspace('Another synthetic practice')
        self.reviewer = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.reviewer)
        self.ref = uuid.uuid4()

    def request_for(self, user, *, host='cpt.quillmd.com', ref='default'):
        request = RequestFactory().get('/api/encounters', HTTP_HOST=host, REMOTE_ADDR='198.51.100.23',
                                       HTTP_X_REQUEST_ID=REQUEST_ID)
        request.user = user
        request.session = import_module(settings.SESSION_ENGINE).SessionStore()
        ref = self.ref if ref == 'default' else ref
        if ref is not None:
            request.session[request_meta.SESSION_SIGN_IN_REF] = str(ref)
        return request


class RecordTests(ReadAuditCase):
    def test_one_read_writes_one_row_with_the_ids_and_reads_back_the_same(self):
        as_of = timezone.now()
        row = read_audit.record(self.request_for(self.reviewer), view=read_audit.MEMBER_LIST, workspace_id=self.ws.pk,
                                encounter_ids=[self.enc.pk], count=1, as_of=as_of,
                                filters={'state': 'ready', 'workspace': self.ws.pk, 'before': as_of, 'ids': [1, 2]})
        self.assertEqual(models.AccessRecord.objects.count(), 1)
        stored = models.AccessRecord.objects.get()
        self.assertEqual(stored.pk, row.pk)
        self.assertEqual(
            (stored.host, stored.view, stored.actor_id, stored.actor_kind, stored.actor_role, stored.workspace_id,
             stored.encounter_ids, stored.count, stored.as_of, stored.outcome, stored.reason, stored.export_id),
            ('cpt', 'member.list', self.reviewer.pk, 'human', 'reviewer', self.ws.pk, [str(self.enc.pk)], 1, as_of,
             'served', '', None))
        self.assertEqual(stored.filters, {'state': 'ready', 'workspace': str(self.ws.pk), 'before': as_of.isoformat(),
                                          'ids': [1, 2]})
        self.assertEqual((stored.client, stored.sign_in_ref, stored.request_id), ('198.51.100.23', self.ref, REQUEST_ID))

    def test_an_operator_s_console_read_on_the_admin_host(self):
        operator = f.user('synthetic-operator')
        export = uuid.uuid4()
        row = read_audit.record(self.request_for(operator, host='admin.quillmd.com', ref=None),
                                view=read_audit.OPS_CONTENT_OPEN, encounter_ids=[self.enc.pk], export_id=str(export),
                                reason='support request: ticket 4471')
        self.assertEqual((row.host, row.actor_role, row.workspace_id, row.export_id, row.sign_in_ref, row.reason),
                         ('admin', 'operator', None, export, None, 'support request: ticket 4471'))

    def test_a_refused_read_of_another_practice_s_document_is_recorded_as_refused(self):
        stranger = f.member(self.other_ws)
        row = read_audit.record(self.request_for(stranger), view=read_audit.MEMBER_DETAIL, encounter_ids=[self.enc.pk],
                                outcome=read_audit.REFUSED)
        self.assertEqual((row.outcome, row.actor_role, row.workspace_id), ('refused', '', None))
        role = read_audit.record(self.request_for(stranger), view=read_audit.MEMBER_DETAIL, workspace_id=self.ws.pk,
                                 encounter_ids=[self.enc.pk], outcome=read_audit.REFUSED).actor_role
        self.assertEqual(role, '')  # no membership in the practice read

    def test_an_agent_and_a_viewer_are_recorded_as_what_they_are(self):
        agent = models.User.objects.create_user(username='synthetic-agent', password='synthetic-pass-123!',
                                                actor_kind=models.User.AGENT)
        models.Membership.objects.create(user=agent, workspace=self.ws, role=models.Membership.VIEWER)
        row = read_audit.record(self.request_for(agent), view=read_audit.MEMBER_DOWNLOAD, workspace_id=self.ws.pk,
                                encounter_ids=[self.enc.pk], filters={'format': 'original'})
        self.assertEqual((row.actor_kind, row.actor_role, row.filters), ('agent', 'viewer', {'format': 'original'}))


class FailClosedTests(ReadAuditCase):
    """A read whose row cannot be written raises NotRecorded, writes nothing, and leaves the caller's transaction usable,
    so the view can answer its 503 without serving anything."""

    def refuse_every_insert(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE FUNCTION studio_test_refuse_access() RETURNS trigger LANGUAGE plpgsql AS '
                           "$$ BEGIN RAISE EXCEPTION 'synthetic refusal of the read record'; END $$")
            cursor.execute('CREATE TRIGGER studio_test_refuse_access BEFORE INSERT ON studio_accessrecord '
                           'FOR EACH ROW EXECUTE FUNCTION studio_test_refuse_access()')

    def test_a_database_that_refuses_the_row_refuses_the_read(self):
        self.refuse_every_insert()
        with transaction.atomic():  # as a view inside a transaction would be
            with self.assertRaises(read_audit.NotRecorded) as refused:
                read_audit.record(self.request_for(self.reviewer), view=read_audit.MEMBER_DETAIL,
                                  workspace_id=self.ws.pk, encounter_ids=[self.enc.pk])
            self.assertEqual(str(refused.exception), read_audit.NOT_RECORDED)
            self.assertIsInstance(refused.exception.__cause__, DatabaseError)
            self.assertEqual(models.AccessRecord.objects.count(), 0)  # and the transaction is still usable
        self.assertEqual(read_audit.NOT_RECORDED, 'This could not be recorded, so nothing was shown.')

    def test_any_failure_of_the_write_refuses_the_read(self):
        for failure in (DatabaseError('synthetic: the connection was lost'), RuntimeError('synthetic')):
            with self.subTest(failure=type(failure).__name__):
                with mock.patch.object(models.AccessRecord.objects, 'create', side_effect=failure):
                    with self.assertRaises(read_audit.NotRecorded) as refused:
                        read_audit.record(self.request_for(self.reviewer), view=read_audit.MEMBER_INLINE,
                                          workspace_id=self.ws.pk, encounter_ids=[self.enc.pk])
                self.assertIs(refused.exception.__cause__, failure)
        self.assertEqual(models.AccessRecord.objects.count(), 0)

    def test_a_session_that_cannot_be_read_refuses_the_read(self):
        request = self.request_for(self.reviewer)
        with mock.patch.object(request_meta, 'sign_in_ref', side_effect=DatabaseError('synthetic: session store down')):
            with self.assertRaises(read_audit.NotRecorded):
                read_audit.record(request, view=read_audit.MEMBER_DETAIL, workspace_id=self.ws.pk,
                                  encounter_ids=[self.enc.pk])
        self.assertEqual(models.AccessRecord.objects.count(), 0)

    def test_arguments_outside_the_contract_write_nothing(self):
        request = self.request_for(self.reviewer)
        cases = {
            'an unknown kind': dict(view='member.peek'),
            'an outcome': dict(view=read_audit.MEMBER_LIST, outcome='maybe'),
            'ids as one string': dict(view=read_audit.MEMBER_DETAIL, encounter_ids=str(self.enc.pk)),
            'an id that is no UUID': dict(view=read_audit.MEMBER_DETAIL, encounter_ids=['Synthetic note']),
            'a workspace that is no UUID': dict(view=read_audit.MEMBER_LIST, workspace_id='Synthetic practice'),
            'a negative count': dict(view=read_audit.MEMBER_LIST, count=-1),
            'a count that is a flag': dict(view=read_audit.MEMBER_LIST, count=True),
            'typed text in a filter': dict(view=read_audit.MEMBER_LIST, filters={'search': 'x' * 101}),
            'a filter name that is no word': dict(view=read_audit.MEMBER_LIST, filters={'Patient Name': 'x'}),
            'a nested filter': dict(view=read_audit.MEMBER_LIST, filters={'where': {'title': 'Synthetic note'}}),
            'a time that is a string': dict(view=read_audit.MEMBER_LIST, as_of='2026-11-24'),
            'a reason that is not text': dict(view=read_audit.OPS_CONTENT_OPEN, reason=None),
        }
        for label, arguments in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                read_audit.record(request, **arguments)
        anonymous = self.request_for(self.reviewer)
        anonymous.user = AnonymousUser()
        with self.assertRaises(ValueError):
            read_audit.record(anonymous, view=read_audit.MEMBER_LIST)
        self.assertEqual(models.AccessRecord.objects.count(), 0)


class PollTests(ReadAuditCase):
    def detail(self, request, *, outcome=read_audit.SERVED, view=read_audit.MEMBER_DETAIL, enc=None):
        return read_audit.record(request, view=view, workspace_id=self.ws.pk, encounter_ids=[(enc or self.enc).pk],
                                 outcome=outcome)

    def test_a_served_detail_of_this_sign_in_is_seen_for_a_minute(self):
        request = self.request_for(self.reviewer)
        self.assertFalse(read_audit.detail_seen_recently(request, self.enc.pk))
        self.detail(request)
        self.assertTrue(read_audit.detail_seen_recently(request, self.enc.pk))
        self.assertTrue(read_audit.detail_seen_recently(request, str(self.enc.pk)))
        later = timezone.now() + timedelta(seconds=settings.READ_AUDIT_DETAIL_DEDUPE_SECONDS + 1)
        with mock.patch.object(timezone, 'now', return_value=later):
            self.assertFalse(read_audit.detail_seen_recently(request, self.enc.pk))

    def test_only_this_sign_in_s_served_detail_of_this_document_counts(self):
        request = self.request_for(self.reviewer)
        other_document = f.encounter(self.ws, self.reviewer, title='Another synthetic note')
        self.detail(request, outcome=read_audit.REFUSED)
        self.detail(request, view=read_audit.MEMBER_INLINE)
        self.detail(request, enc=other_document)
        self.detail(self.request_for(self.reviewer, ref=uuid.uuid4()))  # another sign-in of the same account
        self.detail(self.request_for(f.member(self.ws)))  # another account
        self.assertFalse(read_audit.detail_seen_recently(request, self.enc.pk))
        self.assertTrue(read_audit.detail_seen_recently(request, other_document.pk))
        anonymous = self.request_for(self.reviewer)
        anonymous.user = AnonymousUser()
        self.assertFalse(read_audit.detail_seen_recently(anonymous, other_document.pk))


class MarkTests(TestCase):
    def test_phi_read_marks_a_view_of_a_known_kind_and_outer_wrappers_carry_it(self):
        @read_audit.phi_read(read_audit.MEMBER_DOWNLOAD)
        def view(request):
            return 'answer'

        @functools.wraps(view)
        def wrapped(request):
            return view(request)
        self.assertEqual((read_audit.read_kind(view), read_audit.read_kind(wrapped)), ('member.download',) * 2)
        self.assertEqual(view(None), 'answer')  # it marks only
        self.assertIsNone(read_audit.read_kind(lambda request: None))
        with self.assertRaises(ValueError):
            read_audit.phi_read('member.peek')

    def test_the_kinds_are_the_specification_s(self):
        self.assertEqual(set(read_audit.VIEW_KINDS), {
            'member.list', 'member.detail', 'member.inline', 'member.download', 'member.report_download',
            'member.bundle_download', 'ops.list', 'ops.workspace', 'ops.spending', 'ops.activity', 'ops.detail',
            'ops.content_open', 'ops.original', 'ops.reads'})
        self.assertTrue(all(len(kind) <= models.AccessRecord._meta.get_field('view').max_length
                            for kind in read_audit.VIEW_KINDS))
