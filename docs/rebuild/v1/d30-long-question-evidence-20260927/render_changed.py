"""Six changed exports only; original/missing render evidence is hash-proven reusable."""
import json,shutil,subprocess
from pathlib import Path
root=Path(__file__).parent.resolve();src=root/'render-input';dst=root/'render-output'
src.mkdir(exist_ok=False);dst.mkdir(exist_ok=False);src.chmod(0o755);dst.chmod(0o777)
names=[]
for area,folder in [('A23','capture-A23'),('A35','capture-A35-review'),('A44','capture-A44')]:
    for mode in ('ordinary','long'):
        name=area+'-'+mode;names.append(name)
        path=src/(name+'.docx');shutil.copyfile(root/folder/(mode+'.docx'),path);path.chmod(0o644)
cmd=['docker','run','--rm','--pull','never','--network','none','--read-only','--tmpfs','/tmp:rw,nosuid,nodev,size=256m',
     '--user','1001','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--memory','1g','--cpus','1',
     '-v',str(src)+':/in:ro','-v',str(dst)+':/out','--entrypoint','soffice',
     'sha256:4bd4489d15b7326143e5575c789d93f675f77d85dc857900dd28ae1591d55a4b',
     '-env:UserInstallation=file:///tmp/d30-long-profile','--headless','--norestore','--convert-to','pdf','--outdir','/out']
cmd+=['/in/'+name+'.docx' for name in names]
(root/'14-render-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
r=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
(root/'14-render.log').write_text(r.stdout+'\n'+r.stderr)
assert r.returncode==0,r.returncode
assert all((dst/(name+'.pdf')).exists() for name in names)
print('six changed exports rendered; no original/missing rerender')
