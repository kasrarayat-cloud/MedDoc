from ops import production_restore_check as r
from ops.test_production_restore_check import FakeDatabase
import tempfile,json,hashlib
from pathlib import Path
with tempfile.TemporaryDirectory() as t:
 p=Path(t);(p/'files').mkdir()
 d=FakeDatabase([],triggers=9)
 result=r.check(d,p,9)
 out={'source_sha256':hashlib.sha256(Path(r.__file__).read_bytes()).hexdigest(),'input_triggers':d.triggers,'result':result,'finding':'Nine invented trigger names pass; expected identity/body is unmeasured.'}
 Path('/opt/meddoc-pro/rebuild/.runtime/v1-astra-recovery-20260927/restore-guards/red.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps(out,indent=2));assert result['passed']
