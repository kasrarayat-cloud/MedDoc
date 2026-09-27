import django,json
django.setup()
from core.tests.test_v3_ordinary_notes import field,run
from core.generation import plain_printed_side_option
rows=[]
for value in ['(R) knee','Lt. knee','(R) knee, sorry, Lt. knee','Lt. knee. Patient declined.','(R) knee (prior study)','Lt. knee?','Lt. knee...','(R) knee rather left']:
    fs=[field('reason','Indication'),field('site','Injection site','choice',['(R) knee','Lt. knee'])]
    notes='Indication: pain\nInjection site: '+value
    answers=run(notes,{'Indication':['Indication: pain'],'Injection site':['Injection site: '+value]},fields=fs)
    expected='supported' if value in ['(R) knee','Lt. knee'] else 'conflict'
    assert answers['Injection site']['status']==expected,(value,answers)
    assert answers['Indication']['status']==expected,(value,answers)
    rows.append({'value':value,'expected':expected,'actual':{k:{a:v[a] for a in ['status','text']} for k,v in answers.items()}})
for options in [['Lt. knee','Lt. knee.'],['(R) knee','(R) knee']]:
    assert not plain_printed_side_option(field('site','Site','choice',options),options[0]),options
print(json.dumps({'result':'PASS','cases':rows,'duplicate_option_controls':2},indent=2))
