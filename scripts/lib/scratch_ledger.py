#!/usr/bin/env python3
"""THE SCRATCH LEDGER — a recorder and a recorded reaper. Never called directly.

The granted doors are the two wrappers, and they are the only supported entry points:

    bash scripts/scratch-ledger.sh record --agent <id> [--retain] <ledger> <file>...
    bash scripts/reap-recorded-scratch.sh [--retained <manifest>]... [--dry-run] <ledger> [<recorded path>...]

WHY IT EXISTS — two incidents on 2026-09-29, one session, same tool, same shape
(evidence: rebuild/.runtime/v1-closeout-20260929/incident-evidence/ on the VPS):

  1. A subagent closing out ran `find <whole session scratchpad> -type f | xargs
     bash scripts/reap-session-scratch.sh` and shredded 30 files OTHER agents had
     written — their evidence, harnesses and messages.
  2. The lead later swept the same scratchpad with `find ... | xargs -0 -n 200` in
     three passes and shredded 6,537 files, including the cleanup's own lists and logs.

`reap-session-scratch.sh` did exactly what it promises: it refuses outside-sandbox
paths, symlink escapes and git-tracked files. None of those is OWNERSHIP. Everything
under /tmp/claude-<uid>/ is the same uid, so "inside the sandbox" answered "may I
destroy this?" for every agent at once. The only fact that distinguishes my scratch
from yours is that I made it — and the only moment that fact is knowable is the
moment of creation. So the recorder writes it down THEN, and the reaper destroys
nothing that was not written down, and nothing that has changed since.

The reaper refuses a recorded entry unless ALL of these hold at the moment of shredding:
  * the recorded path is absolute, in normal form, and under /tmp/claude-<euid>/
    (derived from the effective uid ONLY — no argument or variable can name the root);
  * every component from / down is a real directory, opened with O_NOFOLLOW, and the
    leaf is a regular file, not a link; the sandbox root is yours and not group/other-writable;
  * the same device, inode, size and sha256 as recorded (a sibling or a replacement is never taken);
  * owned by the effective uid, link count 1 (never a shared hard link);
  * not recorded with --retain, under that path or that inode — retain is never lifted;
  * not named, aliased (same inode) or contained (listed directory) by any --retained manifest;
  * not tracked by git, and not under a repository marker git will not answer for
    (the reap-session-scratch.sh refusal, ported so this door is never the weaker one);
  * not open, mapped, or the working directory's container for any live process readable to
    us (/proc/*/fd, /proc/*/maps, /proc/*/cwd), scanned immediately before that file is shredded.
Then it overwrites THROUGH THE VERIFIED FILE DESCRIPTOR (`shred - 1<>file`, coreutils' own
form), checks shred's exit status, proves the content now reads as zeros, re-checks that the
name still reaches the same inode, and only then unlinks. Every decision is appended to
<ledger>.reap-log, which lives beside the ledger OUTSIDE the sandbox and is never deleted.

Honest limits, stated so the name does not read wider than the check:
  * processes of OTHER users are invisible to an unprivileged /proc scan;
  * a process can open the file between the scan and the overwrite (the window is one file's scan);
  * the recorder cannot prove the caller created a file; it refuses sweeps (a bound and a
    find/xargs ancestry check, shared with reap-session-scratch.sh) so that claim is made
    one deliberate call at a time rather than by a tree walk.
"""
import argparse
import datetime
import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
SWEEP_GUARD = os.path.join(HERE, 'sweep-guard.sh')
RECORD_BULK_BOUND = 16
RECORD_DECLARATION = 'SCRATCH_LEDGER_BULK_DECLARATION'
LOG_SUFFIX = '.reap-log'
LEDGER_VERSION = 1
CHUNK = 1 << 20
AGENT_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:@/+-]{0,127}\Z')
SHA256_RE = re.compile(r'[0-9a-f]{64}\Z')
SHA256SUM_LINE = re.compile(r'[0-9a-f]{64} [ *](.+)\Z')
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FIELDS = (('v', int), ('kind', str), ('path', str), ('dev', int), ('ino', int), ('size', int),
          ('sha256', str), ('uid', int), ('agent', str), ('retain', bool), ('recorded_at', str))


class StartRefused(Exception):
    """The tool refuses to run at all (exit 2)."""


class Refused(Exception):
    """One target is refused; the run continues with the next."""


class Absent(Exception):
    """The path does not exist (any component)."""


def sandbox_root():
    # ⚠️ DERIVED FROM THE EFFECTIVE UID AND NOTHING ELSE. A parameter or environment
    # variable that names the root is a way to widen it, so there is none.
    return f'/tmp/claude-{os.geteuid()}'


def inside(path, root):
    return path == root or path.startswith(root + '/')


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def check_target_form(path, root):
    """A target is an absolute path in normal form strictly under the sandbox root."""
    if not isinstance(path, str) or not path or '\0' in path:
        raise Refused('not a usable path')
    if not path.startswith('/'):
        raise Refused('not an absolute path')
    if path.startswith('//') or os.path.normpath(path) != path:
        raise Refused('not in normal form (".", "..", "//" or a trailing "/")')
    if not path.startswith(root + '/'):
        raise Refused(f'OUTSIDE THE SANDBOX: not under {root}/')


def open_parent(path, root, euid):
    """Open every directory of `path` from / down, never following a link.

    Returns (parent_fd, leaf). A symlink ANYWHERE on the way refuses; a missing component is Absent.
    """
    names = path.split('/')[1:]
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    walked = ''
    try:
        for name in names[:-1]:
            walked += '/' + name
            try:
                st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                raise Absent(walked)
            except OSError as e:
                raise Refused(f'cannot inspect {walked}: {e.strerror}')
            if stat.S_ISLNK(st.st_mode):
                raise Refused(f'SYMLINK COMPONENT: {walked} is a symbolic link')
            if not stat.S_ISDIR(st.st_mode):
                raise Refused(f'{walked} is not a directory')
            if walked == root:
                if st.st_uid != euid:
                    raise Refused(f'the sandbox root {root} is owned by uid {st.st_uid}, not you ({euid})')
                if st.st_mode & 0o022:
                    raise Refused(f'the sandbox root {root} is group- or other-writable')
            try:
                nfd = os.open(name, DIR_FLAGS, dir_fd=fd)
            except OSError as e:
                if e.errno == errno.ELOOP:
                    raise Refused(f'SYMLINK COMPONENT: {walked} is a symbolic link')
                if e.errno == errno.ENOENT:
                    raise Absent(walked)
                raise Refused(f'cannot open directory {walked}: {e.strerror}')
            nst = os.fstat(nfd)
            if (nst.st_dev, nst.st_ino) != (st.st_dev, st.st_ino):
                os.close(nfd)
                raise Refused(f'{walked} changed while it was being checked')
            os.close(fd)
            fd = nfd
        return fd, names[-1]
    except BaseException:
        os.close(fd)
        raise


def open_leaf(parent_fd, leaf, path, write):
    """lstat then open the leaf with O_NOFOLLOW; the opened object must be the one lstat saw."""
    try:
        lst = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        raise Absent(path)
    except OSError as e:
        raise Refused(f'cannot inspect: {e.strerror}')
    if stat.S_ISLNK(lst.st_mode):
        raise Refused('SYMLINK: the path is a symbolic link')
    if stat.S_ISDIR(lst.st_mode):
        raise Refused('DIRECTORY: directories are never walked or reaped')
    if not stat.S_ISREG(lst.st_mode):
        raise Refused('not a regular file')
    flags = (os.O_RDWR if write else os.O_RDONLY) | os.O_NOFOLLOW | os.O_NOCTTY | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        fd = os.open(leaf, flags, dir_fd=parent_fd)
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise Refused('SYMLINK: the path is a symbolic link')
        if e.errno == errno.ENOENT:
            raise Absent(path)
        raise Refused(f'cannot open{" for overwriting" if write else ""}: {e.strerror}')
    st = os.fstat(fd)
    if (st.st_dev, st.st_ino) != (lst.st_dev, lst.st_ino) or not stat.S_ISREG(st.st_mode):
        os.close(fd)
        raise Refused('changed while it was being checked')
    fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) & ~os.O_NONBLOCK)
    return fd, st


def identity_refusal(record, st, euid):
    """The pure identity comparison, kept pure so every arm is provable without privilege."""
    if not stat.S_ISREG(st.st_mode):
        return 'not a regular file'
    if st.st_uid != euid:
        return f'NOT YOURS: owned by uid {st.st_uid}; you are uid {euid}'
    if (st.st_dev, st.st_ino) != (record['dev'], record['ino']):
        return (f'REPLACED: device/inode {st.st_dev}/{st.st_ino} is not the recorded '
                f'{record["dev"]}/{record["ino"]} — a different file now has this name')
    if st.st_nlink != 1:
        return f'SHARED HARD LINK: link count {st.st_nlink} — another name reaches the same data'
    if st.st_size != record['size']:
        return f'CHANGED: size {st.st_size} is not the recorded {record["size"]}'
    return None


def sha256_fd(fd):
    h, off = hashlib.sha256(), 0
    while True:
        b = os.pread(fd, CHUNK, off)
        if not b:
            return h.hexdigest(), off
        h.update(b)
        off += len(b)


def reads_as_zeros(fd):
    off = 0
    while True:
        b = os.pread(fd, CHUNK, off)
        if not b:
            return True
        if b.strip(b'\0'):
            return False
        off += len(b)


def comm_of(pid):
    try:
        with open(f'/proc/{pid}/comm', 'rb') as fh:
            return fh.read().decode('utf-8', 'replace').strip()
    except OSError:
        return '?'


def process_refusal(dev, ino, parent_dir, self_pid):
    """Any readable live process that holds, maps, or works inside the file's directory refuses it."""
    try:
        pids = [n for n in os.listdir('/proc') if n.isdigit()]
    except OSError as e:
        return f'CANNOT TELL whether a process holds it: /proc is unreadable ({e.strerror})'
    for name in pids:
        pid = int(name)
        if pid == self_pid:
            continue
        base = '/proc/' + name
        try:
            cwd = os.readlink(base + '/cwd')
        except OSError:
            cwd = None
        if cwd is not None:
            if cwd.endswith(' (deleted)'):
                cwd = cwd[:-len(' (deleted)')]
            if cwd == parent_dir or cwd.startswith(parent_dir + '/'):
                return f'IN USE: live process {pid} ({comm_of(pid)}) has its working directory at {cwd}'
        try:
            fds = os.listdir(base + '/fd')
        except OSError:
            fds = ()
        for fdn in fds:
            try:
                st = os.stat(f'{base}/fd/{fdn}')
            except OSError:
                continue
            if st.st_ino == ino and st.st_dev == dev:
                return f'OPEN: live process {pid} ({comm_of(pid)}) holds it as fd {fdn}'
        try:
            with open(base + '/maps', 'rb') as fh:
                maps = fh.read()
        except OSError:
            maps = b''
        for line in maps.splitlines():
            parts = line.split(None, 5)
            if len(parts) < 5 or parts[4] == b'0':
                continue
            try:
                major, minor = parts[3].split(b':')
                if int(parts[4]) == ino and os.makedev(int(major, 16), int(minor, 16)) == dev:
                    return f'MAPPED: live process {pid} ({comm_of(pid)}) has it memory-mapped'
            except ValueError:
                continue
    return None


def git_env():
    # A caller's GIT_DIR / GIT_WORK_TREE would make `git -C <dir>` answer about another repository.
    return {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


def git_refusal(path, root):
    """Ported from reap-session-scratch.sh: tracked refuses; a marker git will not answer for refuses."""
    directory = os.path.dirname(path)
    git = shutil.which('git')
    quiet = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=git_env())
    if git and subprocess.run([git, '-C', directory, 'rev-parse', '--git-dir'], **quiet).returncode == 0:
        if subprocess.run([git, '-C', directory, 'ls-files', '--error-unmatch', '--', path], **quiet).returncode == 0:
            return 'TRACKED by git — a committed file, not scratch'
        return None
    d = directory
    while d.startswith(root + '/'):
        if os.path.lexists(os.path.join(d, '.git')):
            return ('CANNOT TELL — a repository marker sits above this path but git will not answer '
                    'for it, so whether it is tracked is unknown')
        d = os.path.dirname(d)
    return None


class RetainedSet:
    """--retained manifests, with active references resolved: the literal path, its realpath, the
    inode it reaches (so an alias or hard link is covered), and everything under a listed directory."""

    def __init__(self):
        self.paths, self.dirs, self.inodes, self.manifests = set(), set(), {}, []

    def add_manifest(self, manifest):
        try:
            with open(manifest, 'rb') as fh:
                raw = fh.read()
        except OSError as e:
            raise StartRefused(f'--retained {manifest}: {e.strerror} — a manifest that cannot be read protects '
                               'nothing, so nothing is reaped')
        self.manifests.append({'path': os.path.abspath(manifest), 'sha256': hashlib.sha256(raw).hexdigest()})
        for n, line in enumerate(raw.decode('utf-8', 'surrogateescape').split('\n'), 1):
            line = line.rstrip('\r')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            if line.startswith('\\'):
                # sha256sum ESCAPES an unusual name this way; read literally it names a different path and
                # would silently protect nothing.
                raise StartRefused(f'--retained {manifest}:{n}: an escaped sha256sum line is not decoded here — a '
                                   'manifest that cannot be read protects nothing, so nothing is reaped')
            m = SHA256SUM_LINE.match(line)
            if m:
                ref = m.group(1)
            elif line.startswith('/'):
                ref = line
            else:
                i = line.find(' /')
                if i < 0:
                    raise StartRefused(f'--retained {manifest}:{n}: no absolute path on this line — a manifest '
                                       'that cannot be read protects nothing, so nothing is reaped')
                ref = line[i + 1:]
            if not ref.startswith('/'):
                raise StartRefused(f'--retained {manifest}:{n}: the reference is not an absolute path')
            self.add_reference(ref)

    def add_reference(self, ref):
        literal = os.path.normpath(ref)
        self.paths.add(literal)
        real = os.path.realpath(ref)
        self.paths.add(real)
        try:
            st = os.stat(ref)
        except OSError:
            return
        self.inodes[(st.st_dev, st.st_ino)] = ref
        if stat.S_ISDIR(st.st_mode):
            self.dirs.update({literal, real})

    def refusal(self, path, st=None):
        if path in self.paths:
            return 'RETAINED: listed in a --retained manifest'
        for d in self.dirs:
            if path.startswith(d.rstrip('/') + '/'):
                return f'RETAINED: under {d}, a directory listed in a --retained manifest'
        if st is not None and (st.st_dev, st.st_ino) in self.inodes:
            return f'RETAINED: the same file as {self.inodes[(st.st_dev, st.st_ino)]}, listed in a --retained manifest'
        return None


def check_private_dir(parent, euid, create):
    try:
        st = os.lstat(parent)
    except FileNotFoundError:
        if not create:
            raise StartRefused(f'{parent} does not exist')
        os.makedirs(parent, mode=0o700)
        st = os.lstat(parent)
    if stat.S_ISLNK(st.st_mode):
        raise StartRefused(f'{parent} is a symbolic link; the ledger directory must be a real private directory')
    if not stat.S_ISDIR(st.st_mode):
        raise StartRefused(f'{parent} is not a directory')
    if st.st_uid != euid:
        raise StartRefused(f'{parent} is owned by uid {st.st_uid}, not you ({euid})')
    if st.st_mode & 0o077:
        raise StartRefused(f'{parent} is mode {oct(stat.S_IMODE(st.st_mode))}; the ledger directory must be private (0700)')
    return st


def open_private(path, euid, root, *, create, write, label):
    """Open a ledger or a log: outside the sandbox, in a private directory, 0600, ours, one link, no symlink."""
    ap = os.path.abspath(path)
    for p in (ap, os.path.realpath(ap)):
        if inside(p, root):
            raise StartRefused(f'the {label} {path} is inside {root}/: it must live OUTSIDE the scratch sandbox, '
                               'or a sweep of the sandbox can take it (the second 2026-09-29 incident shredded '
                               "the cleanup's own lists and logs)")
    try:
        lst = os.lstat(ap)
    except OSError:
        lst = None
    if lst is not None and stat.S_ISDIR(lst.st_mode):
        raise StartRefused(f'the {label} {path} is a directory — a directory argument is never accepted')
    parent, name = os.path.split(ap)
    pst = check_private_dir(parent, euid, create)
    pfd = os.open(parent, DIR_FLAGS)
    try:
        if (os.fstat(pfd).st_dev, os.fstat(pfd).st_ino) != (pst.st_dev, pst.st_ino):
            raise StartRefused(f'{parent} changed while it was being checked')
        flags = os.O_NOFOLLOW | os.O_CLOEXEC | ((os.O_WRONLY | os.O_APPEND) if write else os.O_RDONLY)
        if create:
            flags |= os.O_CREAT
        try:
            fd = os.open(name, flags, 0o600, dir_fd=pfd)
        except FileNotFoundError:
            raise StartRefused(f'the {label} {path} does not exist')
        except OSError as e:
            if e.errno == errno.ELOOP:
                raise StartRefused(f'the {label} {path} is a symbolic link')
            raise StartRefused(f'cannot open the {label} {path}: {e.strerror}')
    finally:
        os.close(pfd)
    st = os.fstat(fd)
    problem = None
    if not stat.S_ISREG(st.st_mode):
        problem = 'is not a regular file'
    elif st.st_uid != euid:
        problem = f'is owned by uid {st.st_uid}, not you ({euid})'
    elif st.st_mode & 0o077:
        problem = f'is mode {oct(stat.S_IMODE(st.st_mode))}; it must be private (0600)'
    elif st.st_nlink != 1:
        problem = f'has link count {st.st_nlink}; a shared ledger or log is not private'
    if problem:
        os.close(fd)
        raise StartRefused(f'the {label} {path} {problem}')
    return fd, ap


def append_line(fd, obj):
    line = (json.dumps(obj, sort_keys=True, ensure_ascii=True) + '\n').encode('ascii')
    if os.write(fd, line) != len(line):
        raise OSError(errno.EIO, 'short write')


def read_ledger(fd):
    chunks, off = [], 0
    while True:
        b = os.pread(fd, CHUNK, off)
        if not b:
            break
        chunks.append(b)
        off += len(b)
    data = b''.join(chunks)
    if data and not data.endswith(b'\n'):
        raise StartRefused('the ledger ends mid-line (a torn append); refusing rather than guessing')
    records = []
    for n, raw in enumerate(data.split(b'\n')[:-1], 1):
        try:
            rec = json.loads(raw)
        except ValueError:
            raise StartRefused(f'ledger line {n} is not JSON; a ledger that cannot be read is not evidence of anything')
        if not isinstance(rec, dict):
            raise StartRefused(f'ledger line {n} is not a record')
        for key, kind in FIELDS:
            value = rec.get(key)
            if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
                raise StartRefused(f'ledger line {n}: field {key!r} is missing or not {kind.__name__}')
        if rec['v'] != LEDGER_VERSION or rec['kind'] != 'record' or not SHA256_RE.match(rec['sha256']):
            raise StartRefused(f'ledger line {n} is not a version-{LEDGER_VERSION} record')
        rec['line'] = n
        records.append(rec)
    return records, hashlib.sha256(data).hexdigest()


def run_sweep_guard(label, count):
    """The ONE bound-and-ancestry check, in bash, shared with reap-session-scratch.sh."""
    if not os.access(SWEEP_GUARD, os.R_OK):
        print(f'🔴 {label}: CANNOT TELL — {SWEEP_GUARD} is missing; refusing.', file=sys.stderr)
        return False
    script = '. "$1" && sweep_guard "$2" "$3" "$4" "$5"'
    return subprocess.run(['bash', '-c', script, 'sweep-guard', SWEEP_GUARD, label, str(count),
                           str(RECORD_BULK_BOUND), RECORD_DECLARATION], stdin=subprocess.DEVNULL).returncode == 0


def birth_time(fd):
    # statx birth time of the OPENED file; 0 or unparseable means the filesystem does not keep it.
    try:
        out = subprocess.run(['stat', '-L', '-c', '%W', f'/dev/fd/{fd}'], pass_fds=(fd,), capture_output=True,
                             text=True, check=True).stdout.strip()
        value = int(out)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None
    return value or None


def cmd_record(args):
    os.umask(0o077)
    euid = os.geteuid()
    if euid == 0:
        raise StartRefused('running as root — "owned by the current uid" would then mean everything')
    if not AGENT_RE.match(args.agent):
        raise StartRefused(f'--agent {args.agent!r}: an agent id is 1-128 of [A-Za-z0-9._:@/+-]')
    root = sandbox_root()
    if not args.retain and not run_sweep_guard('scratch-ledger record', len(args.files)):
        return 1
    fd, ledger = open_private(args.ledger, euid, root, create=True, write=True, label='ledger')
    refused = 0
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        for given in args.files:
            path = os.path.abspath(given)
            parent_fd = leaf_fd = None
            try:
                check_target_form(path, root)
                if os.path.realpath(path) != path:
                    raise Refused('SYMLINK COMPONENT: the path does not resolve to itself')
                parent_fd, leaf = open_parent(path, root, euid)
                leaf_fd, st = open_leaf(parent_fd, leaf, path, write=False)
                if st.st_uid != euid:
                    raise Refused(f'NOT YOURS: owned by uid {st.st_uid}; you are uid {euid}')
                if st.st_nlink != 1:
                    raise Refused(f'SHARED HARD LINK: link count {st.st_nlink}')
                digest, size = sha256_fd(leaf_fd)
                after = os.fstat(leaf_fd)
                if size != after.st_size or after.st_mtime_ns != st.st_mtime_ns:
                    raise Refused('CHANGED while it was being hashed; record it once it is complete')
                append_line(fd, {
                    'v': LEDGER_VERSION, 'kind': 'record', 'path': path, 'dev': st.st_dev, 'ino': st.st_ino,
                    'size': size, 'sha256': digest, 'uid': st.st_uid, 'btime': birth_time(leaf_fd),
                    'ctime_ns': st.st_ctime_ns, 'mtime_ns': st.st_mtime_ns, 'recorded_at': utc_now(),
                    'agent': args.agent, 'retain': bool(args.retain), 'recorder_pid': os.getpid(),
                })
                print(f'   recorded{" (RETAIN)" if args.retain else ""}: {path} sha256 {digest[:16]}')
            except Absent:
                refused += 1
                print(f'🔴 REFUSED (does not exist): {given}')
            except Refused as e:
                refused += 1
                print(f'🔴 REFUSED ({e}): {given}')
            finally:
                for f in (leaf_fd, parent_fd):
                    if f is not None:
                        os.close(f)
    finally:
        os.close(fd)
    return 1 if refused else 0


class Reaper:
    def __init__(self, args):
        self.args = args
        self.euid = os.geteuid()
        self.root = sandbox_root()
        self.explicit = bool(args.paths)
        self.counts = {}
        self.failed = 0
        self.log_fd = None
        self.run = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]

    def decide(self, decision, path, reason=None, record=None, failure=False):
        self.counts[decision] = self.counts.get(decision, 0) + 1
        self.failed += failure
        entry = {'at': utc_now(), 'run': self.run, 'decision': decision, 'path': path}
        if reason:
            entry['reason'] = reason
        if record is not None:
            entry.update(agent=record['agent'], ledger_line=record['line'],
                         recorded={'dev': record['dev'], 'ino': record['ino'], 'sha256': record['sha256']})
        append_line(self.log_fd, entry)
        text = {'SHREDDED': 'shredded', 'ABSENT': 'absent (already gone)', 'WOULD-SHRED': 'would shred',
                'KEPT': f'kept ({reason})'}.get(decision)
        if text and not failure:
            print(f'   {text}: {path}')
        else:
            print(f'🔴 {decision} ({reason}): {path}')

    def main(self):
        args = self.args
        if self.euid == 0:
            raise StartRefused('running as root — "owned by the current uid" would then mean everything')
        shred = shutil.which('shred')
        if not shred:
            raise StartRefused('no shred on PATH — a reap that cannot shred must not fall back to unlinking')
        self.shred = shred
        self.retained = RetainedSet()
        for manifest in args.retained:
            self.retained.add_manifest(manifest)
        ledger_fd, ledger = open_private(args.ledger, self.euid, self.root, create=False, write=False, label='ledger')
        try:
            fcntl.flock(ledger_fd, fcntl.LOCK_EX)
            records, ledger_sha = read_ledger(ledger_fd)
            self.log_fd, log = open_private(ledger + LOG_SUFFIX, self.euid, self.root, create=True, write=True,
                                            label='reap log')
            latest, order, self.retain_paths, self.retain_inodes = {}, [], set(), set()
            for rec in records:
                if rec['path'] not in latest:
                    order.append(rec['path'])
                latest[rec['path']] = rec
                if rec['retain']:
                    self.retain_paths.add(rec['path'])
                    self.retain_inodes.add((rec['dev'], rec['ino']))
            append_line(self.log_fd, {
                'at': utc_now(), 'run': self.run, 'decision': 'RUN-START', 'ledger': ledger, 'ledger_sha256': ledger_sha,
                'ledger_records': len(records), 'explicit_paths': list(args.paths), 'dry_run': args.dry_run,
                'retained_manifests': self.retained.manifests, 'sandbox': self.root + '/', 'euid': self.euid,
                'pid': os.getpid(), 'ppid': os.getppid(), 'parent_comm': comm_of(os.getppid()),
            })
            selected = []
            if self.explicit:
                seen = set()
                for given in args.paths:
                    path = os.path.abspath(given)
                    try:
                        is_dir = stat.S_ISDIR(os.lstat(path).st_mode)
                    except OSError:
                        is_dir = False
                    if is_dir or given.endswith('/'):
                        self.decide('REFUSED', path, 'DIRECTORY ARGUMENT: directories are never walked; name the '
                                    'recorded files', failure=True)
                    elif path not in latest:
                        self.decide('REFUSED', path, 'NOT IN THE LEDGER: only files this ledger recorded are ever '
                                    'reaped', failure=True)
                    elif path not in seen:
                        seen.add(path)
                        selected.append(path)
            else:
                selected = order
            for path in selected:
                self.reap_one(path, latest[path])
            append_line(self.log_fd, {'at': utc_now(), 'run': self.run, 'decision': 'RUN-END',
                                      'counts': self.counts, 'failed': self.failed})
            summary = ', '.join(f'{v} {k}' for k, v in sorted(self.counts.items())) or 'nothing selected'
            print(f'reap-recorded-scratch: {summary}; log {log}')
        finally:
            os.close(ledger_fd)
            if self.log_fd is not None:
                os.close(self.log_fd)
        return 1 if self.failed else 0

    def reap_one(self, path, rec):
        hold = 'REFUSED' if self.explicit else 'KEPT'
        try:
            check_target_form(path, self.root)
        except Refused as e:
            return self.decide('REFUSED', path, str(e), rec, failure=True)
        if path in self.retain_paths or (rec['dev'], rec['ino']) in self.retain_inodes:
            return self.decide(hold, path, 'RETAIN: recorded with --retain as evidence; retain is never lifted',
                               rec, failure=self.explicit)
        reason = self.retained.refusal(path)
        if reason:
            return self.decide(hold, path, reason, rec, failure=self.explicit)
        parent_fd = leaf_fd = None
        try:
            parent_fd, leaf = open_parent(path, self.root, self.euid)
            leaf_fd, st = open_leaf(parent_fd, leaf, path, write=True)
            reason = identity_refusal(rec, st, self.euid)
            if reason:
                raise Refused(reason)
            reason = self.retained.refusal(path, st)
            if reason:
                return self.decide(hold, path, reason, rec, failure=self.explicit)
            digest, _ = sha256_fd(leaf_fd)
            if digest != rec['sha256']:
                raise Refused(f'CHANGED: content sha256 {digest[:16]} is not the recorded {rec["sha256"][:16]}')
            reason = git_refusal(path, self.root) or process_refusal(st.st_dev, st.st_ino, os.path.dirname(path),
                                                                      os.getpid())
            if reason:
                raise Refused(reason)
            if self.args.dry_run:
                return self.decide('WOULD-SHRED', path, None, rec)
            append_line(self.log_fd, {'at': utc_now(), 'run': self.run, 'decision': 'SHREDDING', 'path': path})
            os.lseek(leaf_fd, 0, os.SEEK_SET)
            proc = subprocess.run([self.shred, '-n', '3', '-z', '-'], stdin=subprocess.DEVNULL, stdout=leaf_fd,
                                  stderr=subprocess.PIPE)
            if proc.returncode != 0:
                err = proc.stderr.decode('utf-8', 'replace').strip()[:300]
                return self.decide('SHRED-FAILED', path, f'shred exited {proc.returncode} ({err}); NOT unlinked, so '
                                   'the failure stays recoverable', rec, failure=True)
            if not reads_as_zeros(leaf_fd):
                return self.decide('SHRED-UNVERIFIED', path, 'shred exited 0 but the content does not read as '
                                   'zeros; NOT unlinked', rec, failure=True)
            try:
                after = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                return self.decide('SHREDDED', path, 'overwritten; the name was already gone', rec)
            if (after.st_dev, after.st_ino) != (st.st_dev, st.st_ino):
                return self.decide('NOT-UNLINKED', path, 'overwritten, but the name now reaches a different file, '
                                   'which was left alone', rec, failure=True)
            try:
                os.unlink(leaf, dir_fd=parent_fd)
            except OSError as e:
                return self.decide('UNLINK-FAILED', path, f'overwritten but not unlinked: {e.strerror}', rec,
                                   failure=True)
            return self.decide('SHREDDED', path, None, rec)
        except Absent as e:
            return self.decide('ABSENT', path, f'{e} does not exist', rec)
        except Refused as e:
            return self.decide('REFUSED', path, str(e), rec, failure=True)
        finally:
            for f in (leaf_fd, parent_fd):
                if f is not None:
                    os.close(f)


def parser_for(prog):
    return argparse.ArgumentParser(prog=prog, allow_abbrev=False)


def main(argv):
    if not argv or argv[0] not in ('record', 'reap'):
        print('usage: scratch_ledger.py record|reap ... (use scripts/scratch-ledger.sh or '
              'scripts/reap-recorded-scratch.sh)', file=sys.stderr)
        return 2
    command, rest = argv[0], argv[1:]
    if command == 'record':
        p = parser_for('scratch-ledger.sh record')
        p.add_argument('--agent', required=True, help='who is recording (your agent id)')
        p.add_argument('--retain', action='store_true', help='evidence: never reaped')
        p.add_argument('ledger')
        p.add_argument('files', nargs='+')
    else:
        p = parser_for('reap-recorded-scratch.sh')
        p.add_argument('--retained', action='append', default=[], metavar='MANIFEST')
        p.add_argument('--dry-run', action='store_true')
        p.add_argument('ledger')
        p.add_argument('paths', nargs='*')
    args = p.parse_args(rest)
    label = 'scratch-ledger' if command == 'record' else 'reap-recorded-scratch'
    try:
        return cmd_record(args) if command == 'record' else Reaper(args).main()
    except StartRefused as e:
        print(f'🔴 {label}: REFUSED TO START — {e}', file=sys.stderr)
        return 2
    except OSError as e:
        print(f'🔴 {label}: STOPPED — {e}; no further decision was taken', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
