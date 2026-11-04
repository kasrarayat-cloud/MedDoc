"""Core repair and customer interface (2026-11-03): what an older revision would show wrongly of this revision's new
records (ops/install.py UNDO_HAZARDS, SHOWN_HAZARDS; ops/INSTALL.md, Reinstalling an older revision): a member's answer
that stands ('member_answer') and a chosen modifier on a current decision ('modifier'). Both are named until cleared on
this revision's web - the answer withdrawn, the approval undone - and never otherwise.

Also, for the installer's operators phase: `manage grant_operator` records who granted without a passwd lookup
(refutation r2, L6-2)."""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from studio import answers, models, review
from studio.gi import context as gi_context
from studio.management.commands import grant_operator
from studio.types import to_jsonable
from tests.support import factories as f
from tests.support import pipeline_factories as pf
from tests.test_cux_review import SHAPES, assess, decide, persist, retrieval_for
from tests.test_repairs_r1_m import install, run_app_script


# The variables getpass.getuser() reads before its passwd lookup.
LOGIN_VARIABLES = ('LOGNAME', 'USER', 'LNAME', 'USERNAME')


def hazards():
    return run_app_script(install.UNDO_HAZARDS_READ, {})['hazards']


def reassess(s, name, **user_values):
    """A re-assessment of the SAME revision, as a member's context change makes one: a new context, a new assessment."""
    text, codes = SHAPES[name]
    facts = {fact: to_jsonable(value) for fact, value in gi_context.extract_context(text).items()}
    context = pf.context(s.encounter, s.revision, fact_values=facts, user_values=user_values)
    result = assess(text, codes)
    review.persist_assessment(
        encounter=s.encounter, revision=s.revision, context=context, routing_run=pf.routing(s.revision),
        provider_run=pf.provider_run(s.encounter, s.revision), result=result,
        retrieval=retrieval_for(result, [code for code, _ in codes]))
    s.encounter.refresh_from_db()


class UndoHazardTests(TestCase):
    def test_a_chosen_modifier_is_named_until_its_approval_is_undone(self):
        s = persist('pair')
        decide(s, '45380', 'approve', note='Synthetic: no modifier.')
        self.assertEqual(hazards(), {})  # control: an approval with no modifier is not named
        decide(s, '45380', 'revoke')
        decide(s, '45380', 'approve', modifiers=['XS'], note='Synthetic: separate lesion.')
        self.assertEqual(hazards(), {str(s.encounter.pk): ['modifier']})
        self.assertIn('modifier', install.SHOWN_HAZARDS)
        decide(s, '45380', 'revoke')
        self.assertEqual(hazards(), {})

    def test_a_member_answer_is_named_until_it_is_withdrawn(self):
        s = persist('pair')
        assessment = s.encounter.current_assessment
        answer = models.MemberAnswer.objects.create(
            encounter=s.encounter, revision=s.revision, assessment=assessment, fact='base_included',
            family='gi.colonoscopy', code='45378', value='cannot_confirm', answered_by=s.reviewer)
        self.assertEqual(hazards(), {str(s.encounter.pk): ['member_answer']})
        self.assertIn('member_answer', install.SHOWN_HAZARDS)
        answers.revoke_answer(s.encounter, s.reviewer, str(answer.pk))
        self.assertEqual(hazards(), {})

    def test_a_standing_answer_is_named_after_a_reassessment_of_its_revision(self):
        # Refutation r2, L3-4: the answer belongs to its revision (answers.standing_answers) and the overlay applies it
        # to every assessment of that revision; the hazard had read it by the assessment it was given on
        s = persist('selected')
        detail = answers.detail_id('base_included', 'gi.colonoscopy', '45378')
        saved = answers.save_details(s.encounter, s.reviewer,
                                     [{'id': detail, 'fact': 'base_included', 'value': 'cannot_confirm'}])
        self.assertEqual(saved['saved'], 1)
        self.assertEqual(hazards(), {str(s.encounter.pk): ['member_answer']})  # control: on its own assessment
        first = s.encounter.current_assessment_id
        reassess(s, 'selected', setting='asc')
        self.assertNotEqual(s.encounter.current_assessment_id, first)
        answer = models.MemberAnswer.objects.get(encounter=s.encounter)
        self.assertEqual((answer.assessment_id, answer.revision_id), (first, s.revision.pk))
        assessment = s.encounter.current_assessment
        view = review.effective_view(assessment)[assessment.proposals.get(code='45378').key]
        self.assertEqual((view.status, view.reason), ('excluded', 'detail_unavailable'))  # it still stands
        self.assertEqual(hazards(), {str(s.encounter.pk): ['member_answer']})
        answers.revoke_answer(s.encounter, s.reviewer, str(answer.pk))
        self.assertEqual(hazards(), {})  # withdrawn: no longer named


class GrantOperatorWithoutAPasswdEntryTests(TestCase):
    """Refutation r2, L6-2: the operators phase runs `manage grant_operator` in a one-shot as the installer's uid, which
    the image has no passwd entry for, with no login variable set: getpass.getuser() raised KeyError there, for both
    accounts, on every rerun. The installer now passes --by, and the command's own default never looks a login up."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.reason = Path(folder.name) / 'reason.txt'
        self.reason.write_text('Synthetic platform operator for the installer tests.\n', encoding='utf-8')
        environment = {name: value for name, value in os.environ.items() if name not in LOGIN_VARIABLES}
        for patcher in (mock.patch.dict(os.environ, environment, clear=True),
                        mock.patch('getpass.getuser', side_effect=KeyError('getpwuid(): uid not found: 1000')),
                        mock.patch('pwd.getpwuid', side_effect=KeyError('getpwuid(): uid not found: 1000'))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_the_default_is_the_environment_s_login_else_the_uid(self):
        self.assertEqual(grant_operator.by_label(''), f'uid {os.getuid()}')
        self.assertEqual(grant_operator.by_label('   '), f'uid {os.getuid()}')
        with mock.patch.dict(os.environ, {'USER': 'synthetic-login'}):
            self.assertEqual(grant_operator.by_label(''), 'synthetic-login')
        self.assertEqual(grant_operator.by_label(' synthetic admin '), 'synthetic admin')
        self.assertEqual(len(grant_operator.by_label('x' * 300)), 120)

    def test_the_command_records_a_grant_and_a_rerun_succeeds(self):
        user = f.user('ops-agent-synthetic', actor_kind=models.User.AGENT)
        call_command('grant_operator', username=user.username, reason_file=str(self.reason), stdout=io.StringIO())
        grant = models.OperatorGrant.objects.get(user=user)
        self.assertEqual(grant.granted_by, f'uid {os.getuid()}')
        out = io.StringIO()  # the phase's rerun (--reset-passwords): the grant is kept and nothing is written
        call_command('grant_operator', username=user.username, reason_file=str(self.reason),
                     by='ops/install.py --phase operators (claude)', stdout=out)
        self.assertIn('already holds operator access', out.getvalue())
        self.assertEqual(models.OperatorGrant.objects.filter(user=user).count(), 1)
        other = f.user('platform-operator-synthetic')
        call_command('grant_operator', username=other.username, reason_file=str(self.reason),
                     by='ops/install.py --phase operators (claude)', stdout=io.StringIO())
        self.assertEqual(models.OperatorGrant.objects.get(user=other).granted_by,
                         'ops/install.py --phase operators (claude)')
