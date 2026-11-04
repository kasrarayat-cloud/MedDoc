"""Core repair and customer interface (2026-11-03): what an older revision would show wrongly of this revision's new
records (ops/install.py UNDO_HAZARDS, SHOWN_HAZARDS; ops/INSTALL.md, Reinstalling an older revision): a member's answer
that stands ('member_answer') and a chosen modifier on a current decision ('modifier'). Both are named until cleared on
this revision's web - the answer withdrawn, the approval undone - and never otherwise."""
from __future__ import annotations

from django.test import TestCase

from studio import answers, models
from tests.test_cux_review import decide, persist
from tests.test_repairs_r1_m import install, run_app_script


def hazards():
    return run_app_script(install.UNDO_HAZARDS_READ, {})['hazards']


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
