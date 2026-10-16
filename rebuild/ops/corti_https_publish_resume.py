"""Complete only the prepared synthetic ingress after its preserved safe rollback."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request
from ops import managed_helper

OUT = Path('/home/claude/quillmd-corti-test/https-install-20261016')
INSTALLED = '40f78febd847b79efce3c13912d2edccc51eee16'
INGRESS = Path('/etc/nginx/sites-available/quillmd')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity():
    names = ['quillmd-fresh-doctor', 'quillmd-fresh-admin', 'quillmd-fresh-worker']
    return {n: subprocess.check_output(['systemctl', 'show', n, '-p', 'MainPID', '-p', 'ActiveState',
        '-p', 'ExecMainStartTimestamp'], timeout=10).decode() for n in names}


def replace(expected, replacement):
    code = '''import os,hashlib,base64,pathlib
p=pathlib.Path('/target/quillmd');i=p.lstat()
assert i.st_uid==i.st_gid==0 and i.st_mode&0o777==0o644 and not p.is_symlink() and i.st_nlink==1
assert hashlib.sha256(p.read_bytes()).hexdigest()==EXPECTED
q=p.with_name('.quillmd-corti-resume');raw=base64.b64decode(REPLACEMENT)
f=os.open(q,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
try:
 os.fchmod(f,0o644);assert os.write(f,raw)==len(raw);os.fsync(f)
 assert p.lstat()==i and hashlib.sha256(p.read_bytes()).hexdigest()==EXPECTED
 os.replace(q,p);d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
finally:
 os.close(f)
 if q.exists():q.unlink()
print('exact_ingress_replaced')
'''.replace('EXPECTED', repr(digest(expected))).replace('REPLACEMENT', repr(base64.b64encode(replacement).decode()))
    managed_helper.run_helper(['docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none', '--network', 'none',
        '--mount', 'type=bind,src=/etc/nginx/sites-available,dst=/target', managed_helper.IMAGE, 'python', '-B', '-'],
        input=code.encode(), timeout=30, failure_directory=OUT)


def check_and_reload(label):
    for args, name in [(['sudo', '-n', '/usr/sbin/nginx', '-t'], 'syntax'),
                       (['sudo', '-n', '/usr/bin/systemctl', 'reload', 'nginx'], 'reload')]:
        result = subprocess.run(args, capture_output=True, timeout=30)
        target = OUT / (label + '-' + name + '.log')
        with target.open('xb') as handle:
            os.chmod(target, 0o600)
            handle.write(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError('Host nginx ' + name + ' failed; protected output retained.')


def main():
    os.umask(0o077)
    assert os.environ.get('RULED_MUTATION_DECLARATION') and os.environ.get('RULED_MUTATION_DECL_COMMIT')
    assert not (OUT / 'installation.json').exists()
    original = (OUT / 'nginx-before.conf').read_bytes()
    candidate = (OUT / 'nginx-after.conf').read_bytes()
    assert digest(original) == 'a6b45d31a328559d8b37de6281683ec60201c880191fef758347827edc5f73eb'
    assert INGRESS.read_bytes() == original
    start = candidate.index(b'    # Isolated authenticated retained-response replay; no provider credentials.\n')
    end = candidate.index(b'    location / {', start)
    assert candidate[:start] + candidate[end:] == original
    assert b'proxy_pass http://127.0.0.1:9146/;' in candidate[start:end]
    headers = {'Host': 'app.quillmd.com', 'X-Forwarded-Proto': 'https', 'X-QuillMD-Account': '1',
               'X-QuillMD-Corti-Prefix': '/synthetic/corti'}
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:9146/health/', headers=headers), timeout=5) as response:
        health = json.load(response)
    assert health == {'status': 'ok', 'data_mode': 'synthetic-only', 'surface': 'doctor', 'release': INSTALLED}
    before = identity()
    (OUT / 'resume-baseline.json').write_text(json.dumps({'native_units': before,
        'nginx_sha256': digest(original), 'health': health}, indent=2))
    replace(original, candidate)
    try:
        check_and_reload('published')
        with urllib.request.urlopen('https://app.quillmd.com/synthetic/corti/health/', timeout=10) as response:
            assert json.load(response) == health
    except BaseException:
        replace(candidate, original)
        check_and_reload('rollback')
        raise
    after = identity()
    assert after == before
    result = {'revision': INSTALLED, 'operations_commit': os.environ['RULED_MUTATION_DECL_COMMIT'],
        'url': 'https://app.quillmd.com/synthetic/corti/', 'mode': 'synthetic_retained_response_replay',
        'health': health, 'native_units_before': before, 'native_units_after': after,
        'native_services_unchanged': True, 'nginx_before_sha256': digest(original),
        'nginx_after_sha256': digest(candidate), 'source_archive_sha256': digest((OUT / 'source.tar').read_bytes()),
        'provider_calls': 0, 'builds': 0, 'production_source_or_database_modified': False,
        'preserved_installation_failure': 'First invocation lacked module path and performed no action. '
            'Second installed candidate units; read-only helper nginx validation failed and restored original ingress. '
            'This exact resume publishes only the prepared prefix using host nginx validation/reload.'}
    with (OUT / 'installation.json').open('x') as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps({'installed_revision': INSTALLED, 'url': result['url'], 'receipt': str(OUT / 'installation.json')}))


if __name__ == '__main__':
    main()
