"""Whole-source reattribution/retraction floors for completed elicited reports."""
from django.test import override_settings

from .test_elicited_proof_transport import ElicitedProofTransport
from .test_v3_field_relations import offered
from .test_v3_ordinary_notes import LIVE
from core import generation as g


@override_settings(**dict(LIVE, V3_FIELD_RELATIONS=True, V3_HISTORY_CONTEXT=False))
class ElicitedSourceReference(ElicitedProofTransport):
    # The inherited seven transport controls keep proof isolation pinned.
    def test_explicit_report_bearer_and_report_creation_denial_stay_held(self):
        for tail in ("That statement was about the patient's brother.",
                     'The patient denies making that report.',
                     'The patient denies that statement.',
                     'The patient did not make that report.',
                     'This report belongs to her mother.',
                     'This report may belong to her mother.',
                     'This report is not from the current patient.',
                     'This report describes the patient next year.'):
            with self.subTest(tail=tail):
                self.assert_held(self.quote+'\n'+tail, self.target, self.quote)

    def test_independent_events_and_document_access_do_not_change_the_report(self):
        for tail in ('The patient denies making that appointment.',
                     'The patient did not read that report.',
                     'The patient denies reading that report.',
                     'The patient denies making another report.',
                     'The bottle belongs to her mother.',
                     'The equipment belongs to the doctor.',
                     'The appointment is with the clinician next week.',
                     'This report was prepared by the clinician.',
                     'This report belongs to the current patient.',
                     'That statement was not about her mother.'):
            with self.subTest(tail=tail):
                notes = self.quote+'\n'+tail
                answer = offered(notes,[self.target],{self.target['key']:[self.quote]})[self.target['key']]
                self.assertEqual((answer['status'],answer['text']),('supported',self.quote),answer)
                page=g.as_currently_governed(g.governance_for(notes,[self.target]),notes,{**self.target,**answer})
                self.assertEqual((page['status'],page['text']),('supported',self.quote))
                self.assertEqual(g.governed_decisions(notes,[self.target],{self.target['key']:answer}),[])
