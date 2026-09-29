import sys,json
txt=sys.stdin.read()
for block in txt.split('\n=== ')[1:]:
    name,body=block.split('\n',1)
    end=body.rfind('}')
    try:d=json.loads(body[:end+1])
    except Exception as e:print('RAW',name,body[:1500]);continue
    print(name,'\n  engine=',[(f[0],f[1],f[2]) for f in d['engine_fields']],'\n  held=',d['held'],'anchored=',d['anchored'],'\n  adopted=',[(a['label'],a['kind'],a['options'],a['locator']['slot'],a['locator']['target'],a['answerable'],a['write_protected']) for a in d['adopted']],'\n  rejected=',d['rejected'],'\n  unresolved=',d['unresolved'],'\n  fill=',d.get('fill'))
tail=[l for l in txt.splitlines() if l.startswith(('OK','FAILED','Ran','ERROR','FAIL:','Traceback')) or 'Error' in l]
print('\n'.join(tail[-15:]))
