#!/usr/bin/env python3
"""Run ONE command of the private QA candidate environment with a FRESH environment (env -i semantics).

    python3 -B qa_launch.py [--surface doctor|admin] [--profile ci|v1] [--wm-replay] [--print] -- COMMAND [ARGS...]

COPY (demo/env-789c0372, 2026-10-01) of demo/qa_launch.py: SRC = demo/env-789c0372/src/rebuild (git archive 789c0372),
RELEASE 789c0372, DB quillmd_qa_int_sol_789c0372 (the presenter's demo environment); state/home/secret-key/word-runtime.json in this directory.

* cwd is <this dir>/src/rebuild: an exact `git archive` of the candidate commit (see demo-env-commands.txt step 2),
  so collectstatic, seed_private and the browser harness write into this private copy, never into a git worktree.
* The environment is built from nothing: no inherited QUILLMD_*, provider key, proxy or dotenv value can leak in.
  The QA database password and the Django secret key are read from 0600 files into the child's environment only;
  they never appear in argv (argv is world-readable in /proc/<pid>/cmdline) and are never printed.
* Profiles:
    ci  -- the CI job 'Private browser and accessibility' semantics (.github/workflows/test.yml:161-170): fixture AI,
           HTTPS off, explicit Sonnet 5.5 and automatic physical-coverage Word selection. Use it for seeding and for CI-equivalent harness runs.
    v1  -- ci plus the candidate's "deployed-equivalent" generation profile, still in FIXTURE mode:
           claude-sonnet-5-5 request profile, QUILLMD_WORD_ENGINE=auto, field relations on, roles/mapping assistance off, no layout socket
           (rebuild/ops/sonnet5_stages.py:117-119, 574-576). No provider request is possible: AI_MODE stays fixture.
* --wm-replay adds QUILLMD_WM_NARRATIVE=1 and QUILLMD_AI_REPLAY_DIR=<this dir>/replay (fixture mode only;
  core/generation.py:3619-3657). It needs the Word runtime (word-runtime.json) because the narrative contract applies
  only to the qualified WM IOV form.
* Optional <this dir>/word-runtime.json: {"runtime": ABS, "manifest": ABS, "manifest_sha256": HEX, "qualification": bool}
  -> QUILLMD_WORD_RUNTIME / _MANIFEST / _MANIFEST_SHA256 / QUILLMD_WORD_QUALIFICATION (documents/sdk_service.py:104-110).
"""
import argparse
import json
import os
import re
import secrets
import shutil
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/demo-789c0372/src/rebuild')
STATE = HERE / 'state'
HOME = HERE / 'home'
REPLAY = HERE / 'replay'
SECRET_FILE = HERE / 'secret-key'
WORD_FILE = HERE / 'word-runtime.json'
PASSWORD_FILE = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password')
RELEASE = '789c0372127d89b1750a2f790c561e68c19f1654'
DB = {'QUILLMD_DB_HOST': '127.0.0.1', 'QUILLMD_DB_PORT': '55731', 'QUILLMD_DB_USER': 'quillmd_qa',
      'QUILLMD_DB_NAME': 'quillmd_qa_int_sol_789c0372'}
PORTS = {'doctor': 9160, 'admin': 9161}
SECRET_NAMES = ('QUILLMD_DB_PASSWORD', 'QUILLMD_SECRET_KEY')


def refuse(message):
    raise SystemExit('qa_launch REFUSED: ' + message)


def private_dir(path):
    if not path.exists():
        path.mkdir(mode=0o700, parents=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid():
        refuse(f'{path} must be an owner-only 0700 directory')


def secret_key(create):
    if not SECRET_FILE.exists():
        if not create:
            return None
        fd = os.open(SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(secrets.token_urlsafe(48))
    info=SECRET_FILE.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        refuse('secret-key must be mode 0600')
    return SECRET_FILE.read_text().strip()


def build(args, create):
    name = DB['QUILLMD_DB_NAME']
    if not name.startswith('quillmd_qa_') or name == 'quillmd_qa_sonnet5' or len(name) >= 40:
        refuse('the QA database name must be a new quillmd_qa_* name, never quillmd_qa_sonnet5')
    if not SRC.is_dir():
        refuse(f'{SRC} is missing: run step 2 (git archive) first')
    if os.path.lexists(SRC / '.env'):
        refuse('src/rebuild/.env exists: quillmd/settings.py:10-11 would load it')
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(HOME), 'LANG': 'C.UTF-8', 'TZ': 'UTC',
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1', 'TMPDIR': str(STATE / 'tmp'),
           **DB,
           'QUILLMD_STATE_DIR': str(STATE), 'QUILLMD_RELEASE_SHA': RELEASE,
           'QUILLMD_DATA_MODE': 'synthetic', 'QUILLMD_REGISTRATION': 'open', 'QUILLMD_STRIPE_MODE': 'test',
           'QUILLMD_EMAIL_MODE': 'file', 'QUILLMD_HTTPS': '0', 'QUILLMD_TRUST_PROXY': '0',
           'QUILLMD_PREVIEW_AUTH_ENABLED': '0', 'QUILLMD_ENV_MANAGED': '0', 'QUILLMD_ROLE_SUGGESTIONS': '0', 'QUILLMD_WORD_AUTO_PREFER_V3': '1',
           'QUILLMD_ADMIN_SITE': '1' if args.surface == 'admin' else '0',
           'QUILLMD_APP_BASE_URL': f"http://127.0.0.1:{PORTS['doctor']}",
           'QUILLMD_AI_MODE': 'fixture'}
    if args.profile == 'v1':
        env.update({'QUILLMD_AI_PROVIDER': 'anthropic', 'QUILLMD_AI_MODEL': 'claude-sonnet-5-5',
                    'QUILLMD_AI_THINKING': 'between_tools', 'QUILLMD_AI_EFFORT': 'medium',
                    'QUILLMD_AI_INPUT_RATE': '2', 'QUILLMD_AI_OUTPUT_RATE': '10', 'QUILLMD_AI_CACHED_RATE': '0.20',
                    'QUILLMD_WORD_ENGINE': 'auto', 'QUILLMD_WM_NARRATIVE': '0', 'QUILLMD_V3_HISTORY_CONTEXT': '0',
                    'QUILLMD_V3_GENERATION_BATCHES': '0', 'QUILLMD_V3_FIELD_RELATIONS': '1',
                    'QUILLMD_MAPPING_ASSISTANCE': '0', 'QUILLMD_MAPPING_ASSISTANCE_LIVE': '0'})
    if args.wm_replay:
        if not WORD_FILE.exists():
            refuse('--wm-replay needs word-runtime.json (the narrative contract is WM IOV only)')
        env.update({'QUILLMD_WM_NARRATIVE': '1', 'QUILLMD_AI_REPLAY_DIR': str(REPLAY)})
    if WORD_FILE.exists():
        word = json.loads(WORD_FILE.read_text())
        if not (Path(word['runtime']).is_absolute() and Path(word['manifest']).is_absolute()
                and re.fullmatch('[0-9a-f]{64}', word['manifest_sha256'])):
            refuse('word-runtime.json is malformed')
        env.update({'QUILLMD_WORD_RUNTIME': word['runtime'], 'QUILLMD_WORD_MANIFEST': word['manifest'],
                    'QUILLMD_WORD_MANIFEST_SHA256': word['manifest_sha256'],
                    'QUILLMD_WORD_QUALIFICATION': '1' if word.get('qualification') else '0'})
    if create:
        for path in (STATE, STATE / 'tmp', HOME) + ((REPLAY,) if args.wm_replay else ()):
            private_dir(path)
    if PASSWORD_FILE.exists():
        sys.path.insert(0,str(SRC / 'ops'))
        from provider_campaign import load_credential
        for parent in (PASSWORD_FILE.parent,PASSWORD_FILE.parent.parent):
            assert not parent.is_symlink() and stat.S_IMODE(parent.stat().st_mode)==0o700
        env['QUILLMD_DB_PASSWORD'] = load_credential(PASSWORD_FILE)
    key = secret_key(create)
    if key:
        env['QUILLMD_SECRET_KEY'] = key
    if create and not all(env.get(k) for k in SECRET_NAMES):
        refuse('the QA database password file or the secret key is unavailable')
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--surface', choices=('doctor', 'admin'), default='doctor')
    parser.add_argument('--profile', choices=('ci', 'v1'), default='ci')
    parser.add_argument('--wm-replay', action='store_true')
    parser.add_argument('--print', action='store_true', help='print the environment (secrets redacted) and exit')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    env = build(args, create=not args.print)
    if args.print:
        shown = {k: ('<present, redacted>' if k in SECRET_NAMES and v else v) for k, v in sorted(env.items())}
        print(json.dumps({'cwd': str(SRC), 'command': command, 'environment': shown,
                          'missing_secrets': [k for k in SECRET_NAMES if not env.get(k)]}, indent=1))
        return
    if not command:
        refuse('no command given')
    executable = command[0] if os.path.isabs(command[0]) else shutil.which(command[0], path=env['PATH'])
    if not executable:
        refuse(f'{command[0]} is not on {env["PATH"]}')
    os.chdir(SRC)
    os.execve(executable, [executable] + command[1:], env)


if __name__ == '__main__':
    main()
