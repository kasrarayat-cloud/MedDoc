from unittest.mock import patch
from django.test import override_settings
from core.tests.test_mapping_assistance import MappingAssistance
from core import generation,mapping_assistance as mapping,jobs
from core.models import Reservation,ProviderReceipt
class ConstructorProbe(MappingAssistance):
 @override_settings(AI_MODE='live',QUILLMD_MAPPING_ASSISTANCE_LIVE=True)
 def test_definite_constructor_failure_releases_without_unknown_outcome(self):
  self.config=generation.configuration();self.compiled=mapping.compile_request(self.version,self.config)
  job=self.enqueue()
  with patch('anthropic.Anthropic',side_effect=ValueError('synthetic missing configuration')) as constructor:
   jobs.run_one()
  job.refresh_from_db()
  print('constructor calls',constructor.call_count,'state',job.state,'held',Reservation.objects.filter(job=job,state='held').exists(),'receipt',ProviderReceipt.objects.filter(job=job).exists())
  self.assertEqual(job.state,'failed')
  self.assertFalse(Reservation.objects.filter(job=job,state='held').exists())
