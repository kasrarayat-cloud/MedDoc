from pathlib import Path
import hashlib,json,os,subprocess
R=Path(__file__).parent
before=json.loads((R/'D03-http-red/uploaded-map.json').read_text());after=json.loads((R/'D03-http-after/uploaded-map.json').read_text())
def identity(f):return json.dumps(f['locator'],sort_keys=True)
def comparable(f):return {k:v for k,v in f.items() if k!='key'}
old={identity(f):comparable(f) for f in before};new={identity(f):comparable(f) for f in after}
result={'before_fields':len(before),'after_fields':len(after),'added':[v for k,v in new.items() if k not in old],
 'removed':[v for k,v in old.items() if k not in new], 'changed_existing':[{'before':v,'after':new[k]} for k,v in old.items() if k in new and v!=new[k]],
 'generated':{mode:json.loads((R/f'D03-http-after/{mode}.json').read_text())['generated_answer'] for mode in ('missing','ordinary','long')}}
(R/'06-original-map-delta.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
output=R/'render-output';output.mkdir();output.chmod(0o777)
cmd=['docker','run','--rm','--pull','never','--network','none','--read-only','--tmpfs','/tmp:rw,nosuid,nodev,size=256m','--user','1001','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--memory','1g','--cpus','1','-v',str(R/'D03-http-after')+':/in:ro','-v',str(output)+':/out','--entrypoint','soffice','sha256:4bd4489d15b7326143e5575c789d93f675f77d85dc857900dd28ae1591d55a4b','-env:UserInstallation=file:///tmp/writein-profile','--headless','--norestore','--convert-to','pdf','--outdir','/out','/in/ordinary.docx','/in/long.docx']
(R/'07-render-command.json').write_text(json.dumps(cmd,indent=2))
with (R/'07-render.log').open('x') as f: result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=90)
assert result.returncode==0
