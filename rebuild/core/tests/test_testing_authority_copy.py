from decimal import Decimal
from types import SimpleNamespace
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class SponsoredRequestCopyTests(SimpleTestCase):
    def render_input(self, sponsored):
        return render_to_string('encounter_input.html', {
            'encounter': SimpleNamespace(pk='00000000-0000-0000-0000-000000000001',
                                        revision=1, notes='Subjective: synthetic facts', answers={}),
            'standing_testing': sponsored, 'generation_max_charge': Decimal('0.45'),
            'generation_provider_estimate': Decimal('0.30'),
            'voice_max_charge': Decimal('0.30'), 'voice_fits': '5 minutes',
            'prior_generations': 1, 'prior_transcriptions': 1,
        })

    def test_sponsored_live_requests_disclose_cost_without_wallet_or_funding_approval(self):
        html = self.render_input(True)
        self.assertIn('Sponsored synthetic testing · $0 account charge', html)
        self.assertIn('Estimated provider cost: $0.30', html)
        self.assertIn('provider charges require separate evidence', html)
        self.assertNotIn('Reserve up to', html)
        self.assertNotIn('longer recording needs separate approval', html)
        self.assertNotIn('remains charged', html)
        self.assertNotIn('No live AI service is called', html)
        for control in ['data-voice-stop', 'transcript', 'data-generate-form']:
            self.assertIn(control, html)

    def test_ordinary_paid_request_keeps_existing_charge_disclosure(self):
        html = self.render_input(False)
        self.assertIn('Reserve up to $0.45', html)
        self.assertIn('longer recording needs separate approval', html)
        self.assertIn('provider usage × 1.5', html)
        self.assertNotIn('Sponsored synthetic testing', html)
