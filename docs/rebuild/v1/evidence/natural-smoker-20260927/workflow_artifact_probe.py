"""Retain the bounded synthetic worker/review/export control; no provider network."""
import hashlib,json
from pathlib import Path
from core.tests import test_natural_smoker as fixture
from core.models import Job,ProviderReceipt,Usage
from core.security import private_path

ART = Path(__file__).resolve().parent

class NaturalSmokerArtifact(fixture.NaturalSmokerWorkflow):
    def test_worker_review_save_finalize_and_original_word_option(self):
        super().test_worker_review_save_finalize_and_original_word_option()
        data = private_path(self.encounter.export_path).read_bytes()
        (ART/'synthetic-original.docx').write_bytes(self.original)
        (ART/'synthetic-finalized.docx').write_bytes(data)
        job=Job.objects.get(encounter=self.encounter)
        usage=Usage.objects.get(job=job)
        proof={'input':fixture.QUOTE,'source_contract':'whole-note exact current-patient statement',
               'worker':'SDK response mocked, network denied; no actual model behavior demonstrated',
               'job_state':job.state,'encounter_state':self.encounter.status,
               'answer':self.encounter.answers[self.key('Smoker')],
               'original_sha256':hashlib.sha256(self.original).hexdigest(),
               'export_sha256':self.encounter.export_sha256,
               'word_option_text':fixture.part_text(data),
               'mock_request_model':job.config['model'],
               'synthetic_receipts':ProviderReceipt.objects.filter(job=job).count(),
               'synthetic_cost':str(usage.actual_cost),'synthetic_charge':str(usage.charged_cost)}
        (ART/'08-workflow-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
