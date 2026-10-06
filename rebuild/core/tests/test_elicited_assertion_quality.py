"""Unknown pointed assertion predicates retain dependencies without a bad-word list."""
from django.test import override_settings

from .test_elicited_passive_reference import ElicitedPassiveReference
from .test_v3_field_relations import offered
from .test_v3_ordinary_notes import LIVE
from core import generation as g


@override_settings(**dict(LIVE, V3_FIELD_RELATIONS=True, V3_HISTORY_CONTEXT=False))
class ElicitedAssertionQuality(ElicitedPassiveReference):
    def test_pointed_assertion_quality_is_not_independent_or_unconditionally_true(self):
        for tail in ('That report was false.',
                     'That statement was incorrect.',
                     'That statement was not clear.',
                     'That statement seems incorrect.',
                     'That statement was uncertain.',
                     'That statement was not accurate.',
                     'That statement may be true.',
                     'That statement was partly true.',
                     'That statement was true yesterday.',
                     'Was that statement true?'):
            with self.subTest(tail=tail):
                self.assert_held(self.quote+'\n'+tail, self.target, self.quote)

    def test_literal_truth_atoms_and_distinct_argument_quality_keep_original_speech(self):
        for tail in ('That statement was true.',
                     'That statement is true.',
                     'That statement was accurate.',
                     'That statement is accurate.',
                     'That statement was not false.',
                     'Another statement was incorrect.',
                     'That appointment was incorrect.',
                     'That appointment was not clear.'):
            with self.subTest(tail=tail):
                notes = self.quote+'\n'+tail
                answer = offered(notes,[self.target],{self.target['key']:[self.quote]})[self.target['key']]
                self.assertEqual((answer['status'],answer['text']),('supported',self.quote),answer)
                page=g.as_currently_governed(g.governance_for(notes,[self.target]),notes,{**self.target,**answer})
                self.assertEqual((page['status'],page['text']),('supported',self.quote))
                self.assertEqual(g.governed_decisions(notes,[self.target],{self.target['key']:answer}),[])
