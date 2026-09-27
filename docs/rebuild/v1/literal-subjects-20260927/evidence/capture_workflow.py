"""Retain the already-passing synthetic workflow outputs; no provider/network."""
import hashlib, json
from pathlib import Path
from django.conf import settings
from django.test.utils import get_runner
from core.security import private_path
from core.tests.test_v3_literal_subjects import LiteralSubjectsWorkflow
HERE = Path(__file__).resolve().parent
original_walk = LiteralSubjectsWorkflow.walk

def capture(self, *args, **kwargs):
    original_walk(self, *args, **kwargs)
    original = private_path(self.template.original_path).read_bytes()
    exported = private_path(self.encounter.export_path).read_bytes()
    for name, data in (("synthetic-original.docx", original), ("synthetic-finalized.docx", exported)):
        (HERE / name).write_bytes(data)
    report = {"scope": "synthetic mocked-provider workflow; no actual model evidence",
              "original_sha256": hashlib.sha256(original).hexdigest(),
              "export_sha256": hashlib.sha256(exported).hexdigest(),
              "recorded_export_sha256": self.encounter.export_sha256,
              "notes": self.encounter.notes, "fields": self.version.fields,
              "answers": self.encounter.answers, "status": self.encounter.status}
    (HERE / "07-workflow-artifacts.json").write_text(json.dumps(report, indent=2) + "\n")
LiteralSubjectsWorkflow.walk = capture
runner = get_runner(settings)(verbosity=2, interactive=False)
failures = runner.run_tests(["core.tests.test_v3_literal_subjects.LiteralSubjectsWorkflow.test_worker_review_save_finalize_exports_complete_negative_declaration_and_head"])
if failures: raise SystemExit(1)
