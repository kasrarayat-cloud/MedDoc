import os,json,types,subprocess,hashlib,socket
from pathlib import Path
from unittest.mock import patch
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_ENV_MANAGED='1',QUILLMD_SECRET_KEY='synthetic-read-only',QUILLMD_DB_PASSWORD='unused',QUILLMD_DB_PORT='1',QUILLMD_AI_MODE='fixture')
import django;django.setup()
from core import generation as current, v3_syntax
from core.tests import test_v3_ordinary_notes as helper
base_source=subprocess.check_output(['git','show','4caa34431a60e6ce3409ecadbbb6989b50659d7b:rebuild/core/generation.py'])
base=types.ModuleType('core._syntax_refute_base');base.__package__='core';exec(compile(base_source,'base-generation.py','exec'),base.__dict__)
socket.socket=lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('network denied'))
cases=[
('positive','The patient attends an art class every Monday.'),
('advocate','The patient advocate attends an art class every Monday.'),
('coordinator','The patient care coordinator attends an art class every Monday.'),
('caregiver','The patient caregiver attends an art class every Monday.'),
('pluralpatients','The patient and her father attend art classes.'),
('possessive','The patient\'s father attends an art class every Monday.'),
('conditional','The patient attends an art class if symptoms improve.'),
('modal','The patient should attend an art class.'),
('fragment','The patient attending an art class every Monday.'),
('embedded','The patient hopes to attend an art class every Monday.'),
('question','The patient attends an art class every Monday?'),
('negative','The patient never attends an art class.'),
('preservedcoordination','The patient attends an art class and swims every Monday.'),
('foreignconjunction','The patient attends an art class and her father swims every Monday.'),
('passive','The patient attended by a caregiver every Monday.'),
('nounphrase','Patient education improves sleep.'),
]
out={'base_generation_sha256':hashlib.sha256(base_source).hexdigest(),'candidate':{name:hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() for name,module in [('generation',current),('syntax',v3_syntax)]},'cases':[]}
for name,notes in cases:
 label='What activities does the patient attend?';fs=[helper.field('v3_1',label,'long_text')];row={'case':name,'notes':notes}
 for title,module in [('base',base),('candidate',current)]:
  with patch.object(helper,'g',module):
   units=module.source_units(notes,module.v3_generation_fields(fs)[0])[0]
   answer=helper.run(notes,{label:[u['quote'] for u in units]},fields=fs)[label]
   row[title]={'answer':answer,'finalization_governed':module.governed_decisions(notes,fs,{'v3_1':{**answer,'reviewed':True}})}
 parser=v3_syntax._parser()
 row['parse']=[{'text':t.text,'pos':t.pos_,'tag':t.tag_,'dep':t.dep_,'head':t.head.text} for t in parser(notes)]
 out['cases'].append(row)
print(json.dumps(out,indent=2))
