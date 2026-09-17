#!/usr/bin/env python3
"""Activate the reviewed fresh private preview from shared main, never public ingress."""
import argparse,hashlib,json,os,signal,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/opt/meddoc-pro')
SOURCE=ROOT/'.worktrees/quillmd-fresh/rebuild'
DEST=ROOT/'rebuild'
UNITS=['quillmd-fresh-'+name+'.service' for name in ('doctor','admin','worker')]

def run(args,**kwargs):
    return subprocess.run(args,check=True,**kwargs)
def output(args):
    return subprocess.check_output(args,text=True).strip()
def require(ok,message):
    if not ok:raise RuntimeError(message)
def protected():
    baseline=json.loads((ROOT/'docs/rebuild/activation-baseline.json').read_text())
    rows=json.loads(output(['docker','inspect',*[x['name'].lstrip('/') for x in baseline['containers']]]))
    for want,got in zip(baseline['containers'],rows):
        require(want['id']==got['Id'] and want['image']==got['Image'] and want['running']==got['State']['Running'],'Protected container changed: '+want['name'])
        require(want['mounts']==[{'source':m['Source'],'destination':m['Destination']} for m in got['Mounts']],'Protected mount changed: '+want['name'])
    return len(rows)
def precheck():
    require(Path.cwd()==ROOT and ROOT.resolve()==ROOT,'Run from shared main only.')
    require(output(['git','branch','--show-current'])=='main','Shared tree must stay main.')
    run(['git','diff','--exit-code','HEAD','--','.'])
    require(SOURCE.resolve()==SOURCE and SOURCE.is_dir(),'Unexpected source runtime path.')
    require((SOURCE/'.env').is_file() and (SOURCE/'.runtime').is_dir(),'Fresh source runtime unavailable.')
    require(not (DEST/'.env').exists() and not (DEST/'.runtime').exists(),'Destination runtime already exists; reconcile instead of overwriting.')
    require((SOURCE/'.env').stat().st_mode & 0o777==0o600,'Fresh credentials must be mode0600.')
    protected()
    print('Verified main, fresh runtime ownership, empty destination, and protected container/mount identities.',flush=True)
def stop_preview():
    for name in ('worker','doctor','admin'):
        p=SOURCE/'.runtime'/f'{name}.pid'
        require(p.is_file(),'Missing preview process PID: '+name)
        pid=int(p.read_text())
        proc=Path('/proc')/str(pid)
        require(proc.exists() and proc.stat().st_uid==os.getuid(),'Process ownership mismatch: '+name)
        require((proc/'cwd').resolve()==SOURCE,'Process working directory mismatch: '+name)
        cmd=(proc/'cmdline').read_bytes()
        require((b'manage.py' in cmd and b'worker' in cmd) if name=='worker' else b'gunicorn' in cmd,'Process command mismatch: '+name)
        print('Gracefully stopping verified fresh preview '+name,flush=True)
        os.kill(pid,signal.SIGTERM)
        for attempt in range(150):
            if not proc.exists() or (proc/'stat').read_text().split()[2]=='Z':break
            if attempt%20==0:print('Waiting for '+name+' to finish current work.',flush=True)
            time.sleep(1)
        else:raise RuntimeError('Process still active; no force kill: '+name)

def execute():
    require(Path(os.environ.get('RULED_MUTATION_DECLARATION','')).name=='20260917-quillmd-private-activation.md','Committed activation declaration gate required.')
    precheck()
    sha=output(['git','rev-parse','HEAD'])
    run(['bash','scripts/check-citation.sh',sha])
    # Dependency installation cannot access old data; credentials never enter argv.
    run(['python3','-m','venv',str(DEST/'.venv')])
    run([str(DEST/'.venv/bin/python'),'-m','pip','install','--quiet','-r',str(DEST/'requirements.txt')])
    stop_preview()
    (SOURCE/'.env').rename(DEST/'.env')
    (SOURCE/'.runtime').rename(DEST/'.runtime')
    for name in ('worker','doctor','admin'):(DEST/'.runtime'/f'{name}.pid').unlink(missing_ok=True)
    result={'started_at':datetime.now(timezone.utc).isoformat(),'head':sha,'complete':False,'runtime':str(DEST/'.runtime')}
    result_path=DEST/'.runtime/activation-result.json'
    try:
        run([str(DEST/'.venv/bin/python'),'manage.py','check'],cwd=DEST)
        run([str(DEST/'.venv/bin/python'),'manage.py','collectstatic','--noinput'],cwd=DEST)
        run(['systemd-analyze','verify',*[str(DEST/'deploy'/x) for x in UNITS]])
        # Root helper has no network. Host mount is read-only except the unit directory.
        # The only commands inside the host are these exact three fresh units.
        code='''import os,pathlib,shutil,subprocess\nos.chroot('/host');os.chdir('/')\nunits=['quillmd-fresh-'+n+'.service' for n in ('doctor','admin','worker')]\nfor name in units:\n dst=pathlib.Path('/etc/systemd/system')/name\n if dst.exists():raise RuntimeError('Refuse existing unit: '+name)\n shutil.copyfile(pathlib.Path('/opt/meddoc-pro/rebuild/deploy')/name,dst);dst.chmod(0o644)\ndrop=pathlib.Path('/etc/systemd/system/quillmd-postreboot-proof.service.d/fresh-private.conf')\nif drop.exists():raise RuntimeError('Refuse existing boot ordering drop-in')\ndrop.parent.mkdir(exist_ok=True)\nshutil.copyfile('/opt/meddoc-pro/rebuild/deploy/fresh-private.conf',drop);drop.chmod(0o644)\nsubprocess.run(['systemctl','daemon-reload'],check=True)\nsubprocess.run(['systemctl','enable','--now',*units],check=True)\n'''
        run(['docker','run','--rm','-i','--network','none','--pid=host','--mount','type=bind,src=/,dst=/host,readonly','--mount','type=bind,src=/etc/systemd/system,dst=/host/etc/systemd/system','python:3-slim','python','-'],input=code,text=True)
        # A git checkout can replace the inode while Docker's file bind retains
        # the old one. Load the exact reviewed shared-tree bytes explicitly.
        caddy_config=(ROOT/'Caddyfile').read_bytes()
        require(subprocess.check_output(['git','show','HEAD:Caddyfile'])==caddy_config,'Caddy config differs from reviewed HEAD.')
        for action in ('validate','reload'):
            run(['docker','exec','-i','meddoc-pro-caddy-1','caddy',action,'--config','-','--adapter','caddyfile'],input=caddy_config)
        for _ in range(30):
            try:
                if all(output(['systemctl','is-active',x])=='active' for x in UNITS):
                    for port in ('9130','9131'):run(['curl','--fail','--silent','--output','/dev/null','http://127.0.0.1:'+port+'/login/'])
                    break
            except subprocess.CalledProcessError:pass
            time.sleep(1)
        else:raise RuntimeError('Private listeners failed readiness.')
        run(['bash','scripts/check-cotenants.sh'])
        result.update(protected_containers=protected(),units={x:{'active':output(['systemctl','is-active',x]),'enabled':output(['systemctl','is-enabled',x])} for x in UNITS},complete=True)
    finally:
        result['finished_at']=datetime.now(timezone.utc).isoformat()
        result_path.write_text(json.dumps(result,indent=2)+'\n');result_path.chmod(0o600)
    print('Verified private preview supervised on localhost; public maintenance and preserved marketing verified.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    if p.parse_args().execute:execute()
    else:precheck()
