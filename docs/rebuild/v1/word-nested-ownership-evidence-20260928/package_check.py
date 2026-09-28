from pathlib import Path
from zipfile import ZipFile
import json,hashlib
R=Path(__file__).parent
out={}
with ZipFile(R/'D03-http-after/original.docx') as source:
 for stage in ('missing','ordinary'):
  path=R/'D03-http-after'/f'{stage}.docx'
  with ZipFile(path) as export:
   assert source.namelist()==export.namelist()
   changed=[part for part in source.namelist() if source.read(part)!=export.read(part)]
   assert set(changed)<= {'word/document.xml'}
   out[stage]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'package_parts':len(source.namelist()),'changed_parts':changed,'all_other_parts_byte_identical':True}
p=R/'17-package-identity.json';assert not p.exists();p.write_text(json.dumps(out,indent=2));print(json.dumps(out))
