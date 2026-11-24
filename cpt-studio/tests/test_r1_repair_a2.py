"""Refutation round 2 of release 1, repair builder a2's repairs (sign-in rows, the members list, the key step's lookup, a
read repeated over midnight), each pinned by its finding's own input (refute-r2/findings-round2.json).

phi-3         a member's list read repeated just after midnight UTC was counted on the previous day's record, so the new
              day's reads page said 'No read recorded for this choice'. A repeat is now counted only on a record of its
              own UTC day - the day the reads page files a read under.

Synthetic accounts, practices, titles and rows only."""
from __future__ import annotations

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from studio import models, read_audit
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC
from tests.test_read_audit import member_client

UTC = dt_timezone.utc
LIST = '/api/encounters'
LIST_ROW = 'Document list<br>'  # a member.list row on the reads page (ops_activity_reads.html: the kind, then a break)
NO_READ = 'No read recorded'


def at(moment):
    return mock.patch.object(timezone, 'now', return_value=moment)


# --- phi-3: a list read repeated over midnight is a record of its own day ------------------------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class ListRepeatDayTests(TestCase):
    """The finding's input: one session lists its practice at 23:59:50 UTC and again at 00:00:20, inside
    READ_AUDIT_LIST_REPEAT_SECONDS; an operator then reads the reads page of each day."""

    def setUp(self):
        self.ws = f.workspace('Synthetic practice A2 repeats')
        self.reviewer = f.member(self.ws)
        f.encounter(self.ws, self.reviewer, title='ZZ-A2-TITLE-A synthetic note')
        f.encounter(self.ws, self.reviewer, title='ZZ-A2-TITLE-B synthetic note')
        self.auditor = ops.admin_client(f.user('a2-repeat-auditor'))

    def lists(self):
        return list(models.AccessRecord.objects.filter(view=read_audit.MEMBER_LIST, actor_id=self.reviewer.pk)
                    .order_by('created_at', 'pk'))

    def page(self, query):
        answer = self.auditor.get('/ops/activity/reads' + query)
        self.assertEqual(answer.status_code, 200)
        return answer.content.decode()

    def member_at(self, moment):
        with at(moment):  # signed in a moment before its reads (a session's times are never in the future)
            return member_client(self.reviewer)

    def list_at(self, member, moment):
        with at(moment):
            answer = member.get(LIST)
        self.assertEqual(answer.status_code, 200)
        return answer

    def test_a_list_read_repeated_just_after_midnight_is_a_record_of_the_new_day(self):
        evening = datetime(2026, 11, 20, 23, 59, 40, tzinfo=UTC)
        member = self.member_at(evening)
        self.list_at(member, evening + timedelta(seconds=10))  # 23:59:50 on the 20th
        second = self.list_at(member, evening + timedelta(seconds=40))  # 00:00:20 on the 21st, 30 s later
        self.assertIn(b'ZZ-A2-TITLE-A', second.content)  # the practice's list was served again
        rows = self.lists()
        self.assertEqual([row.created_at for row in rows],
                         [evening + timedelta(seconds=10), evening + timedelta(seconds=40)])
        self.assertFalse(models.AccessRecordRepeat.objects.filter(record_id__in=[row.pk for row in rows]).exists())
        # what an auditor reads: each day's page holds that day's read, by account, by kind and unfiltered
        for query in (f'?day=2026-11-21&account={self.reviewer.pk}', '?day=2026-11-21&kind=member.list',
                      '?day=2026-11-21', f'?day=2026-11-20&account={self.reviewer.pk}'):
            with self.subTest(query=query):
                body = self.page(query)
                self.assertEqual(body.count(LIST_ROW), 1)
                self.assertNotIn(NO_READ, body)
                self.assertNotIn('read again', body)
        self.assertIn('2026-11-21 00:00:20', self.page('?day=2026-11-21'))
        self.assertNotIn('2026-11-21 00:00:20', self.page('?day=2026-11-20'))

    def test_the_day_boundary_is_the_reads_pages_own_to_the_microsecond(self):
        evening = datetime(2026, 11, 20, 23, 59, 30, tzinfo=UTC)
        member = self.member_at(evening - timedelta(seconds=5))
        self.list_at(member, evening)
        self.list_at(member, datetime(2026, 11, 20, 23, 59, 59, 999999, tzinfo=UTC))  # the last moment of the 20th
        (first,) = self.lists()
        repeat = models.AccessRecordRepeat.objects.get(record_id=first.pk)
        self.assertEqual((repeat.repeats, repeat.last_at), (1, datetime(2026, 11, 20, 23, 59, 59, 999999, tzinfo=UTC)))
        midnight = datetime(2026, 11, 21, tzinfo=UTC)
        self.list_at(member, midnight)  # the first moment of the 21st: a record of its own, filed under the 21st
        self.assertEqual([row.created_at for row in self.lists()], [evening, midnight])
        self.assertEqual(models.AccessRecordRepeat.objects.get().repeats, 1)
        self.assertEqual(self.page('?day=2026-11-21').count(LIST_ROW), 1)
        body = self.page('?day=2026-11-20')
        self.assertEqual(body.count(LIST_ROW), 1)
        self.assertIn('read again 1 time by this sign-in, the last at 2026-11-20 23:59:59', body)

    def test_a_repeat_within_one_day_is_still_counted_on_its_record(self):
        noon = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
        member = self.member_at(noon - timedelta(seconds=5))
        for second in (0, 20, 40):
            self.list_at(member, noon + timedelta(seconds=second))
        (first,) = self.lists()
        repeat = models.AccessRecordRepeat.objects.get(record_id=first.pk)
        self.assertEqual((repeat.repeats, repeat.last_at), (2, noon + timedelta(seconds=40)))
        self.assertIn('read again 2 times by this sign-in, the last at 2026-11-21 12:00:40',
                      self.page('?day=2026-11-21'))
