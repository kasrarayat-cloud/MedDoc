"""Synthetic upper-envelope sizing; no document contents, network or tokenizer guesses."""
import json,hashlib
from pathlib import Path
root=Path(__file__).parent
# Conservative integer widths: all 1200 source slots, 200 fields, 100 replacements,
# 400 printed-option spans. Repeated spans here measure wire size, not clinical validity.
body={'f':{'k':list(range(100)),'r':list(range(100,200)),'n':[],'u':[]},
      's':{'c':list(range(1200)),'n':[],'u':[]},'x':[], 'e':False}
for field in range(100,200):
    body['x'].append([field,1199,4,99999,399699,399999,-1]+[99999,399799,399999]*4)
text=json.dumps(body,separators=(',',':'))
p=root/'compact-ceiling-response.json';p.write_text(text)
req={'model':'claude-sonnet-5','messages':[{'role':'user','content':text}]}
request=json.dumps(req,sort_keys=True,separators=(',',':'))
(root/'compact-count-request.json').write_text(request)
report={'response_bytes':len(text.encode()),'response_sha256':hashlib.sha256(text.encode()).hexdigest(),
        'count_request_sha256':hashlib.sha256(request.encode()).hexdigest(),
        'fields':200,'slots':1200,'changes':100,'option_spans':400,
        'note':'No token estimate. Wide integers conservatively exceed realizable catalog/offset widths under the full request byte cap.'}
(root/'compact-sizing.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
