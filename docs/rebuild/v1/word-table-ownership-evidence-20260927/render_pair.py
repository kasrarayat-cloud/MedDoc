"""Only four affected synthetic exports, no corpus or provider operation."""
import json,shutil,subprocess
from pathlib import Path
r=Path(__file__).parent.resolve();src=r/'render-input';dst=r/'render-output'
src.mkdir(exist_ok=False);dst.mkdir(exist_ok=False);src.chmod(0o755);dst.chmod(0o777);names=[]
for id in ('D30','D31'):
 for mode in ('ordinary','long'):
  name=id+'-'+mode;names.append(name);p=src/(name+'.docx')
  shutil.copyfile(r/(id+'-workflow-after')/(mode+'.docx'),p);p.chmod(0o644)
cmd=['docker','run','--rm','--pull','never','--network','none','--read-only','--tmpfs','/tmp:rw,nosuid,nodev,size=256m','--user','1001','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--memory','1g','--cpus','1','-v',str(src)+':/in:ro','-v',str(dst)+':/out','--entrypoint','soffice','sha256:4bd4489d15b7326143e5575c789d93f675f77d85dc857900dd28ae1591d55a4b','-env:UserInstallation=file:///tmp/word-pair-profile','--headless','--norestore','--convert-to','pdf','--outdir','/out']+['/in/'+n+'.docx' for n in names]
(r/'12-render-command.json').write_text(json.dumps(cmd,indent=2))
p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
(r/'12-render.log').write_text(p.stdout+'\n'+p.stderr)
assert p.returncode==0 and all((dst/(n+'.pdf')).exists() for n in names)
print('four affected exports rendered')
