#!/usr/bin/env python3
"""THE SCRATCH LEDGER — a recorder and a recorded reaper. Never called directly.

The granted doors are the two wrappers, and they are the only supported entry points:

    bash scripts/scratch-ledger.sh record --agent <id> [--retain] <dir>/<name>.ledger <file>...
    bash scripts/reap-recorded-scratch.sh [--retained <manifest>]... [--dry-run] <dir>/<name>.ledger [<recorded path>...]

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

THE LEDGER (version 2, after the 2026-09-29 refutation round on df80fa58)
  * A ledger is `<name>.ledger` in a private directory OUTSIDE the sandbox. The first
    record creates `<name>.ledger.key` beside it: 32 random bytes, 0600. Every line the
    recorder appends carries `seq` (its line number) and `mac`, an HMAC-SHA256 under that
    key of every other field. The reaper verifies every line and REFUSES THE WHOLE LEDGER
    if any line is not bound (F3): a ledger written by a tree walk, a line copied from
    another ledger, a line moved or duplicated. What the binding proves is that the line
    was written by something holding this ledger's key — i.e. by the recorder, not by a
    script that walked a tree. It is not a boundary against a same-uid actor who reads
    the key on purpose; nothing an unprivileged same-uid tool does can be.
  * RETAIN IS GLOBAL ACROSS THE LEDGER DIRECTORY (F5): a file recorded --retain in ANY
    `*.ledger` beside this one is kept, matched by path or by (device, inode, sha256) —
    the content hash is part of the key so a reused inode never inherits retain. A
    sibling ledger that cannot be read is CANNOT TELL, and the run refuses to start.
    Ledgers in other directories are not seen: keep one ledger directory per session.

The reaper refuses a recorded entry unless ALL of these hold at the moment of shredding:
  * the recorded path is absolute, in normal form, and under /tmp/claude-<euid>/
    (derived from the effective uid ONLY — no argument or variable can name the root);
  * every component from / down is a real directory, opened with O_NOFOLLOW, and the
    leaf is a regular file, not a link; the sandbox root is yours and not group/other-writable;
  * the same device, inode, size and sha256 as recorded (a sibling or a replacement is never taken);
  * owned by the effective uid, link count 1 (never a shared hard link);
  * not recorded with --retain in any ledger of the directory, by path or by (dev, ino, sha256);
  * not named, aliased (same inode) or contained (listed directory) by any --retained
    manifest, and every manifest line is an exact recognised form that reaches a real
    file or directory — anything else refuses the whole run (F4);
  * not inside a .git directory or a bare repository, not tracked by git, and not under
    a repository git cannot answer for: git exiting anything but 0/1 is CANNOT TELL (F6);
  * not open or mapped by any live process readable to us, and no live process other than
    the caller's own has its working directory in the file's directory or below
    (/proc/*/fd, /proc/*/maps, /proc/*/cwd), scanned immediately before that file. The
    caller's own are its caller chain and the other members of its pipeline (`reap … | tail`):
    processes of the reaper's session joined to its stdio by a pipe made in that session;
  * RE-CHECKED AFTER THOSE SCANS (F7): the open file still has one link and the same size,
    mtime and ctime, and the path walked again from / still reaches it; and the directory
    is writable, so an overwrite is never left behind un-unlinked.
Then it reopens THE VERIFIED INODE for writing through /proc/self/fd (a read-only file of
yours is made owner-writable through that descriptor first, and its mode is restored if the
shred fails), checks the link count on that descriptor one last time, overwrites through it
(`shred - 1<>file`, coreutils' own form), checks shred's exit status, proves the content now
reads as zeros, re-checks that the name still reaches the same inode, and only then unlinks.
Every decision is appended to <ledger>.reap-log, which lives beside the ledger OUTSIDE the
sandbox and is never deleted.

Honest limits, stated so the name does not read wider than the check:
  * processes of OTHER users are invisible to an unprivileged /proc scan;
  * a process can open the file, or link it, in the instant between the last re-check and
    shred's first write (the window is one fstat, not one scan);
  * the recorder cannot prove the caller created a file; it bounds how many undeclared
    records a ledger takes per window (scripts/lib/sweep-guard.sh, shared with
    reap-session-scratch.sh), so that claim is made a few deliberate files at a time
    rather than by a tree walk;
  * the recorder refuses, when it is asked, what the reaper would refuse on git grounds
    (a .git component, a bare repository, a tracked file, a repository git cannot answer
    for) — but a directory can become a repository after a file is recorded, which only
    the reaper sees. NEITHER DOOR REAPS A SCRATCH CLONE'S .git: that capability, which
    reap-session-scratch.sh had before 2026-09-29, is gone (canon 123, round 2);
  * a process that shares a pipe made in the reaper's session and is itself in that
    session is taken as the caller's own for the working-directory check only.
"""
import argparse
import datetime
import errno
import fcntl
import hashlib
import hmac
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
SWEEP_GUARD = os.path.join(HERE, 'sweep-guard.sh')
RECORD_BULK_BOUND = 16
RECORD_DECLARATION = 'SCRATCH_LEDGER_BULK_DECLARATION'
LEDGER_SUFFIX = '.ledger'
LOG_SUFFIX = '.reap-log'
KEY_SUFFIX = '.key'
WINDOW_SUFFIX = '.sweep-window'
LEDGER_VERSION = 2
MAC_DOMAIN = b'scratch-ledger-v2\n'
CHUNK = 1 << 20
AGENT_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:@/+-]{0,127}\Z')
SHA256_RE = re.compile(r'[0-9a-f]{64}\Z')
KEY_RE = re.compile(rb'[0-9a-f]{64}\n\Z')
SHA256SUM_LINE = re.compile(r'([0-9a-f]{64}) ([ *])(.*)\Z', re.S)
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
INT, STR, BOOL, OPT_INT = 'int', 'str', 'bool', 'int-or-null'
FIELDS = {'v': INT, 'kind': STR, 'seq': INT, 'path': STR, 'dev': INT, 'ino': INT, 'size': INT, 'sha256': STR,
          'uid': INT, 'btime': OPT_INT, 'ctime_ns': INT, 'mtime_ns': INT, 'recorded_at': STR, 'agent': STR,
          'retain': BOOL, 'recorder_pid': INT, 'mac': STR}
MANIFEST_FORMS = ('a bare absolute path in normal form, or a sha256sum line: 64 hex digits, then two spaces '
                  'or " *", then an absolute path; plus "#" comment lines and empty lines')
CHANGED_HINT = (' — if you wrote it after recording it, record it again (the latest record for a path is the '
                'one reaped)')
SIBLING_TORN_RETRIES = 20


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


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


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


def read_all(fd):
    chunks, off = [], 0
    while True:
        b = os.pread(fd, CHUNK, off)
        if not b:
            return b''.join(chunks)
        chunks.append(b)
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


def proc_stat(pid):
    """(parent pid, session id) of a live process, read from /proc/<pid>/stat after the last ')' (the command
    name before it may hold spaces and parentheses). Raises OSError/ValueError/IndexError when it cannot be read."""
    with open(f'/proc/{pid}/stat', 'rb') as fh:
        data = fh.read()
    fields = data[data.rindex(b')') + 2:].split()
    return int(fields[1]), int(fields[3])


def ancestors(pid):
    """The caller chain of `pid` (its parent, grandparent, … up to but not including pid 1)."""
    chain, seen = set(), {pid}
    while len(chain) < 256:
        try:
            ppid = proc_stat(pid)[0]
        except (OSError, ValueError, IndexError):
            break
        if ppid <= 1 or ppid in seen:
            break
        chain.add(ppid)
        seen.add(ppid)
        pid = ppid
    return chain


def stdio_pipes(pid):
    """The pipes on a process's stdin, stdout and stderr, as /proc names them ('pipe:[<inode>]')."""
    pipes = set()
    for n in (0, 1, 2):
        try:
            link = os.readlink(f'/proc/{pid}/fd/{n}')
        except OSError:
            continue
        if link.startswith('pipe:['):
            pipes.add(link)
    return pipes


def made_in_session(pipe, holder, session):
    """Whether `pipe` was made inside `session`. Walking up from a process that holds it on stdio, the first
    ancestor that does NOT hold it there is the one that made it (the shell that built the pipeline); that one must
    be in the session. A pipe handed down from outside — a harness's own stdout or stderr passed to every command
    it runs — is held all the way up to a process outside the session, so it is never followed."""
    pid = holder
    for _ in range(256):
        try:
            ppid = proc_stat(pid)[0]
            if ppid <= 0:
                return False
            if pipe not in stdio_pipes(ppid):
                return proc_stat(ppid)[1] == session
        except (OSError, ValueError, IndexError):
            return False
        pid = ppid
    return False


def pipeline_members(self_pid):
    """The other members of the caller's own pipeline: `reap … | tail`, `… 2>&1 | tee log`, `… | grep | tail`,
    `{ reap …; } | tail`, `reap … > >(cat)`, `writer | reap …` (2026-09-29, refutation round 2, R2-2).

    They are the calling shell's CHILDREN, not its ancestors, and they inherited its working directory exactly as
    the reaper did, so an exemption for the caller chain alone refused every file whenever the caller stood in the
    directory and piped the output. What makes them the caller's own is recognised, not their names: a member is in
    the reaper's own SESSION and is joined to the reaper's stdin, stdout or stderr by a pipe that was MADE INSIDE
    that session — directly, or through another member (a pipe on a member's stdio that was made in the session is
    followed in turn). A process in another session is never a member, whatever pipe it holds (`setsid` is how a
    process leaves), and a pipe handed down from outside the session is never followed (`made_in_session`).
    Unreadable /proc entries make a process a non-member: the direction that refuses."""
    try:
        session = proc_stat(self_pid)[1]
        names = os.listdir('/proc')
    except (OSError, ValueError, IndexError):
        return set()
    frontier = {p for p in stdio_pipes(self_pid) if made_in_session(p, self_pid, session)}
    if not frontier:
        return set()
    candidates = {}
    for name in names:
        if not name.isdigit() or int(name) == self_pid:
            continue
        pid = int(name)
        try:
            if proc_stat(pid)[1] != session:
                continue
        except (OSError, ValueError, IndexError):
            continue
        pipes = stdio_pipes(pid)
        if pipes:
            candidates[pid] = pipes
    members, grew = set(), True
    while grew:
        grew = False
        for pid, pipes in candidates.items():
            if pid in members or not pipes & frontier:
                continue
            members.add(pid)
            frontier |= {p for p in pipes - frontier if made_in_session(p, pid, session)}
            grew = True
    return members


def caller_processes(self_pid):
    """The processes whose working directory is the caller's own: its caller chain and its pipeline's members."""
    return frozenset(ancestors(self_pid) | pipeline_members(self_pid))


def process_refusal(dev, ino, parent_dir, self_pid, cwd_exempt=frozenset()):
    """Any readable live process that holds or maps the file refuses it; so does any that works inside the
    file's directory, EXCEPT the caller's own processes (`cwd_exempt`, from `caller_processes`: its caller chain
    and the other members of its pipeline): the shell that asked for the reap standing in the directory, and the
    `tail` it piped the output to, are the owner asking, not another agent working there. The exemption is from
    the working-directory check only; a caller's process that holds or maps the file still refuses it."""
    try:
        pids = [n for n in os.listdir('/proc') if n.isdigit()]
    except OSError as e:
        return f'CANNOT TELL whether a process holds it: /proc is unreadable ({e.strerror})'
    for name in pids:
        pid = int(name)
        if pid == self_pid:
            continue
        base = '/proc/' + name
        if pid not in cwd_exempt:
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


def looks_like_git_dir(d):
    return (os.path.isfile(os.path.join(d, 'HEAD')) and os.path.isdir(os.path.join(d, 'objects'))
            and os.path.isdir(os.path.join(d, 'refs')))


def git_refusal(path, root):
    """Ported from reap-session-scratch.sh and made fail-closed (2026-09-29 refutation, F6).

    Git's own files are never scratch; tracked refuses; git answering anything but 0 (tracked) or 1 (untracked)
    — 128 for an unreadable index or a refused repository — is CANNOT TELL; a repository marker or a git-dir
    shape that git will not answer for is CANNOT TELL."""
    if '.git' in path.split('/'):
        return ("INSIDE A .git DIRECTORY — git's own data (objects, index, refs), never scratch; a local clone "
                'hard-links these to its source')
    directory = os.path.dirname(path)
    git = shutil.which('git')
    if git:
        base = [git, '-c', 'core.fsmonitor=false', '-C', directory]
        answer = subprocess.run(base + ['rev-parse', '--is-inside-git-dir'], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=git_env())
        if answer.returncode == 0:
            if answer.stdout.strip() != b'false':
                return "INSIDE A GIT DIRECTORY — a bare repository's own data, never scratch"
            rc = subprocess.run(base + ['ls-files', '--error-unmatch', '--', path], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=git_env()).returncode
            if rc == 0:
                return 'TRACKED by git — a committed file, not scratch'
            if rc == 1:
                return None
            return (f'CANNOT TELL — git exited {rc} when asked whether this file is tracked (an unreadable index '
                    'or a repository git refuses), so it is refused rather than guessed')
    d = directory
    while d.startswith(root + '/'):
        if os.path.lexists(os.path.join(d, '.git')) or looks_like_git_dir(d):
            return ('CANNOT TELL — a repository marker sits above this path but git will not answer '
                    'for it, so whether it is tracked is unknown')
        d = os.path.dirname(d)
    return None


class RetainedSet:
    """--retained manifests, read STRICTLY (2026-09-29 refutation, F4).

    Exactly two line forms are recognised — a bare absolute path in normal form, or a sha256sum line — plus
    '#' comment lines and empty lines. A line with anything else (trailing blanks, a trailing comment, a size
    column, `ls -l` output, leading whitespace) refuses the whole run, and so does a reference that reaches
    nothing: under the old reading each of those was taken literally, failed to stat, and protected nothing
    while the run exited 0. Active references are resolved: the literal path, its realpath, the inode it
    reaches (so an alias or hard link is covered), and everything under a listed directory."""

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
        lines = raw.decode('utf-8', 'surrogateescape').split('\n')
        if lines and lines[-1] == '':
            lines.pop()
        for n, line in enumerate(lines, 1):
            if line.endswith('\r'):
                line = line[:-1]
            if line == '' or line.startswith('#'):
                continue
            where = f'--retained {manifest}:{n}'
            if line.startswith('\\'):
                # sha256sum ESCAPES an unusual name this way; read literally it names a different path and
                # would silently protect nothing.
                raise StartRefused(f'{where}: an escaped sha256sum line is not decoded here — a manifest that '
                                   'cannot be read protects nothing, so nothing is reaped')
            m = SHA256SUM_LINE.match(line)
            self.add_reference(m.group(3) if m else line, where)

    def add_reference(self, ref, where):
        def refuse(why):
            raise StartRefused(f'{where}: {why}. The recognised forms are {MANIFEST_FORMS}; a line that is not '
                               'read exactly protects nothing, so nothing is reaped')

        if not ref.startswith('/'):
            refuse('no absolute path at the start of the line')
        if ref != ref.strip():
            refuse('leading or trailing whitespace')
        if any(ch in ref for ch in '\t\r\n\v\f\0'):
            refuse('a tab or control character')
        if ' #' in ref:
            refuse('a trailing comment')
        body = ref[:-1] if ref.endswith('/') and ref != '/' else ref
        if body.startswith('//') or os.path.normpath(body) != body:
            refuse('not in normal form (".", "..", "//")')
        try:
            st = os.stat(body)
        except OSError as e:
            refuse(f'{body} reaches nothing ({e.strerror})')
        if body != ref and not stat.S_ISDIR(st.st_mode):
            refuse(f'a trailing "/" on {body}, which is not a directory')
        real = os.path.realpath(body)
        self.paths.update({body, real})
        self.inodes[(st.st_dev, st.st_ino)] = body
        if stat.S_ISDIR(st.st_mode):
            self.dirs.update({body, real})

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
        # ONLY the final directory is created. A ledger path that needs a chain of new directories is what a
        # driver that builds the ledger name from each file (`xargs -I{} … /state/x{}.ledger {}`) produces —
        # one fresh ledger, and so one fresh sweep window, per file.
        try:
            os.mkdir(parent, 0o700)
        except FileNotFoundError:
            raise StartRefused(f'{parent} cannot be created: its parent {os.path.dirname(parent)} does not exist '
                               '(only the ledger directory itself is ever created)')
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


def ledger_path(given, root):
    """The ledger's absolute path: outside the sandbox, not a directory, and named <something>.ledger — the
    suffix is how every ledger of a directory is found for global retain."""
    ap = os.path.abspath(given)
    for p in (ap, os.path.realpath(ap)):
        if inside(p, root):
            raise StartRefused(f'the ledger {given} is inside {root}/: it must live OUTSIDE the scratch sandbox, '
                               'or a sweep of the sandbox can take it (the second 2026-09-29 incident shredded '
                               "the cleanup's own lists and logs)")
    try:
        if stat.S_ISDIR(os.lstat(ap).st_mode):
            raise StartRefused(f'the ledger {given} is a directory — a directory argument is never accepted')
    except OSError:
        pass
    name = os.path.basename(ap)
    if not name.endswith(LEDGER_SUFFIX) or name == LEDGER_SUFFIX:
        raise StartRefused(f'the ledger {given} must be named <name>{LEDGER_SUFFIX}: every ledger in its directory '
                           'is read for retain records, and that suffix is how they are found')
    return ap


def open_dir(parent, pst):
    pfd = os.open(parent, DIR_FLAGS)
    if (os.fstat(pfd).st_dev, os.fstat(pfd).st_ino) != (pst.st_dev, pst.st_ino):
        os.close(pfd)
        raise StartRefused(f'{parent} changed while it was being checked')
    return pfd


def private_file_problem(st, euid):
    if not stat.S_ISREG(st.st_mode):
        return 'is not a regular file'
    if st.st_uid != euid:
        return f'is owned by uid {st.st_uid}, not you ({euid})'
    if st.st_mode & 0o077:
        return f'is mode {oct(stat.S_IMODE(st.st_mode))}; it must be private (0600)'
    if st.st_nlink != 1:
        return f'has link count {st.st_nlink}; a shared ledger, key or log is not private'
    return None


def open_private(path, euid, root, *, create, write, label, keep_dir=False):
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
    pfd = open_dir(parent, pst)
    try:
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
    except BaseException:
        os.close(pfd)
        raise
    problem = private_file_problem(os.fstat(fd), euid)
    if problem:
        os.close(fd)
        os.close(pfd)
        raise StartRefused(f'the {label} {path} {problem}')
    if keep_dir:
        return fd, ap, pfd
    os.close(pfd)
    return fd, ap


def ledger_key(pfd, ledger, euid, ledger_fd, create):
    """The ledger's MAC key, `<ledger>.key` beside it. Created (32 random bytes, 0600) only by the recorder and
    only while the ledger is still empty, under the ledger's own lock. Returns None when it is absent and may
    not be created — which is fine for an empty ledger and refuses one that holds records."""
    name = os.path.basename(ledger) + KEY_SUFFIX
    try:
        kfd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=pfd)
    except FileNotFoundError:
        if not create:
            return None
        if os.fstat(ledger_fd).st_size != 0:
            raise StartRefused(f'the ledger {ledger} holds records but its key {ledger}{KEY_SUFFIX} is missing: its '
                               'lines can no longer be shown to be the recorder\'s, so it is never extended or reaped')
        key = os.urandom(32)
        kfd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=pfd)
        try:
            os.write(kfd, key.hex().encode('ascii') + b'\n')
            os.fsync(kfd)
        finally:
            os.close(kfd)
        return key
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise StartRefused(f'the ledger key {ledger}{KEY_SUFFIX} is a symbolic link')
        raise StartRefused(f'cannot open the ledger key {ledger}{KEY_SUFFIX}: {e.strerror}')
    try:
        problem = private_file_problem(os.fstat(kfd), euid)
        if problem:
            raise StartRefused(f'the ledger key {ledger}{KEY_SUFFIX} {problem}')
        data = os.read(kfd, 256)
    finally:
        os.close(kfd)
    if not KEY_RE.match(data):
        raise StartRefused(f'the ledger key {ledger}{KEY_SUFFIX} is not 64 hex digits and a newline')
    return bytes.fromhex(data[:64].decode('ascii'))


def mac_of(key, record):
    body = json.dumps({k: v for k, v in record.items() if k != 'mac'}, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True).encode('ascii')
    return hmac.new(key, MAC_DOMAIN + body, hashlib.sha256).hexdigest()


def append_line(fd, obj):
    line = (json.dumps(obj, sort_keys=True, ensure_ascii=True) + '\n').encode('ascii')
    if os.write(fd, line) != len(line):
        raise OSError(errno.EIO, 'short write')


def no_duplicate_keys(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f'duplicate key {k!r}')
        out[k] = v
    return out


def field_ok(value, kind):
    if kind == INT:
        return is_int(value)
    if kind == OPT_INT:
        return value is None or is_int(value)
    if kind == STR:
        return isinstance(value, str)
    return isinstance(value, bool)


def read_ledger(fd, key, ledger):
    """Every line must be a version-2 record, in sequence, whose MAC verifies under this ledger's key. One line
    that is not refuses the WHOLE ledger (F3): a line the recorder did not write is not evidence of anything,
    and a ledger holding one is not a ledger any line of which can be trusted to be complete."""
    data = read_all(fd)
    if data and not data.endswith(b'\n'):
        raise StartRefused('the ledger ends mid-line (a torn append); refusing rather than guessing')
    if data and key is None:
        raise StartRefused(f'the ledger {ledger} holds records but has no key ({ledger}{KEY_SUFFIX}): none of its '
                           'lines is bound to the recorder, so nothing is reaped')
    records = []
    for n, raw in enumerate(data.split(b'\n')[:-1], 1):
        try:
            rec = json.loads(raw, object_pairs_hook=no_duplicate_keys)
        except ValueError:
            raise StartRefused(f'ledger line {n} is not JSON; a ledger that cannot be read is not evidence of anything')
        if not isinstance(rec, dict) or set(rec) != set(FIELDS) or not all(
                field_ok(rec[k], kind) for k, kind in FIELDS.items()):
            raise StartRefused(f'ledger line {n} is not a version-{LEDGER_VERSION} record, so it is not bound to the '
                               'recorder (written by hand, by a tree walk, or by an older recorder); nothing is reaped')
        if rec['v'] != LEDGER_VERSION or rec['kind'] != 'record' or not SHA256_RE.match(rec['sha256']) \
                or not SHA256_RE.match(rec['mac']):
            raise StartRefused(f'ledger line {n} is not a version-{LEDGER_VERSION} record, so it is not bound to the '
                               'recorder; nothing is reaped')
        if not hmac.compare_digest(mac_of(key, rec), rec['mac']):
            raise StartRefused(f'ledger line {n} is not bound to the recorder: its MAC does not verify under this '
                               "ledger's key — a line the recorder did not write here (hand-written, or copied from "
                               'another ledger) is not evidence of anything, so nothing is reaped')
        if rec['seq'] != n:
            raise StartRefused(f'ledger line {n} carries sequence {rec["seq"]}: a recorded line was moved, repeated '
                               'or removed, so nothing is reaped')
        rec['line'] = n
        records.append(rec)
    return records, hashlib.sha256(data).hexdigest()


def read_sibling_retains(pfd, parent, own_name, euid):
    """Retain records from every OTHER `*.ledger` in the directory (F5). A retain line is honoured whether or not
    its MAC verifies — a retain can only prevent destruction — but a sibling that cannot be read at all is
    CANNOT TELL: whatever it retains is unknown, so the run refuses to start."""
    by_path, by_id, sources = {}, {}, []
    for name in sorted(os.listdir(pfd)):
        if not name.endswith(LEDGER_SUFFIX) or name == own_name:
            continue
        full = os.path.join(parent, name)

        def refuse(why):
            raise StartRefused(f'the sibling ledger {full} {why} — what it retains cannot be known, so nothing is '
                               'reaped (retain is global across the ledger directory)')

        try:
            lfd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=pfd)
        except OSError as e:
            refuse('is a symbolic link' if e.errno == errno.ELOOP else f'cannot be opened ({e.strerror})')
        try:
            problem = private_file_problem(os.fstat(lfd), euid)
            if problem:
                refuse(problem)
            for _ in range(SIBLING_TORN_RETRIES):
                data = read_all(lfd)
                if not data or data.endswith(b'\n'):
                    break
                time.sleep(0.05)  # another recorder may be mid-append
            else:
                refuse('ends mid-line (a torn append)')
        finally:
            os.close(lfd)
        count = 0
        for n, raw in enumerate(data.split(b'\n')[:-1], 1):
            try:
                rec = json.loads(raw)
            except ValueError:
                refuse(f'line {n} is not JSON')
            if not isinstance(rec, dict) or not isinstance(rec.get('path'), str) \
                    or not isinstance(rec.get('retain'), bool):
                refuse(f'line {n} is not a ledger record')
            if rec['retain']:
                count += 1
                by_path.setdefault(rec['path'], full)
                dev, ino, digest = rec.get('dev'), rec.get('ino'), rec.get('sha256')
                if is_int(dev) and is_int(ino) and isinstance(digest, str) and SHA256_RE.match(digest):
                    by_id.setdefault((dev, ino, digest), full)
        sources.append({'ledger': full, 'sha256': hashlib.sha256(data).hexdigest(), 'retain_records': count})
    return by_path, by_id, sources


def run_sweep_guard(label, count, window):
    """The ONE bound-and-ancestry check, in bash, shared with reap-session-scratch.sh."""
    if not os.access(SWEEP_GUARD, os.R_OK):
        print(f'🔴 {label}: CANNOT TELL — {SWEEP_GUARD} is missing; refusing.', file=sys.stderr)
        return False
    script = '. "$1" && sweep_guard "$2" "$3" "$4" "$5" "$6"'
    return subprocess.run(['bash', '-c', script, 'sweep-guard', SWEEP_GUARD, label, str(count),
                           str(RECORD_BULK_BOUND), RECORD_DECLARATION, window],
                          stdin=subprocess.DEVNULL).returncode == 0


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
    ledger = ledger_path(args.ledger, root)
    # ⚠️ EVERY CHECK THAT REFUSES THE WHOLE CALL RUNS BEFORE THE SWEEP GUARD COUNTS IT (2026-09-29, refutation
    # round 2, R2-5). The guard appends this call's path count to the window as it lets the call through, and it
    # used to run first: a call then refused as a whole — a ledger that is not 0600, a missing key, an unbound line
    # — had already spent its paths, and 16 of them locked the ledger's next record out for five minutes. The lock
    # order is always ledger, then window, for every recorder, so the two locks cannot deadlock.
    fd, ledger, pfd = open_private(ledger, euid, root, create=True, write=True, label='ledger', keep_dir=True)
    refused = 0
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        key = ledger_key(pfd, ledger, euid, fd, create=True)
        rfd = os.open(f'/proc/self/fd/{fd}', os.O_RDONLY | os.O_CLOEXEC)
        try:
            # Every existing line is verified first: a ledger holding an unbound line will never be reaped, and
            # extending it would only hide that until close-out.
            records, _ = read_ledger(rfd, key, ledger)
        finally:
            os.close(rfd)
        # The window lives beside the ledger, in the private directory open_private has just checked. Paths the
        # call names are counted whether or not each one is then recorded: the bound is on what a call ATTEMPTS
        # to claim, and a sweep naming paths that turn out to be refusable is still a sweep.
        if not args.retain and not run_sweep_guard('scratch-ledger record', len(args.files), ledger + WINDOW_SUFFIX):
            return 1
        seq = len(records)
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
                if not args.retain:
                    # ⚠️ THE REAPER'S OWN GIT REFUSALS, APPLIED WHEN THE CLAIM IS MADE (2026-09-29, refutation round
                    # 2, R2-4). The recorder took `.git/HEAD`, `.git/config`, pack files and tracked files that the
                    # reaper refuses on every run, so a whole-ledger close-out could never exit 0 again. The same
                    # function answers both doors. A --retain record is not refused: it can only prevent.
                    reason = git_refusal(path, root)
                    if reason:
                        raise Refused(reason + ' — the reaper refuses it on every run, so it is not recorded')
                digest, size = sha256_fd(leaf_fd)
                after = os.fstat(leaf_fd)
                if size != after.st_size or after.st_mtime_ns != st.st_mtime_ns:
                    raise Refused('CHANGED while it was being hashed; record it once it is complete')
                record = {
                    'v': LEDGER_VERSION, 'kind': 'record', 'seq': seq + 1, 'path': path, 'dev': st.st_dev,
                    'ino': st.st_ino, 'size': size, 'sha256': digest, 'uid': st.st_uid,
                    'btime': birth_time(leaf_fd), 'ctime_ns': st.st_ctime_ns, 'mtime_ns': st.st_mtime_ns,
                    'recorded_at': utc_now(), 'agent': args.agent, 'retain': bool(args.retain),
                    'recorder_pid': os.getpid(),
                }
                record['mac'] = mac_of(key, record)
                append_line(fd, record)
                seq += 1
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
        os.close(pfd)
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
        ledger = ledger_path(args.ledger, self.root)
        self.retained = RetainedSet()
        for manifest in args.retained:
            self.retained.add_manifest(manifest)
        ledger_fd, ledger, pfd = open_private(ledger, self.euid, self.root, create=False, write=False,
                                              label='ledger', keep_dir=True)
        try:
            fcntl.flock(ledger_fd, fcntl.LOCK_EX)
            key = ledger_key(pfd, ledger, self.euid, ledger_fd, create=False)
            records, ledger_sha = read_ledger(ledger_fd, key, ledger)
            self.retain_by_path, self.retain_by_id, sources = read_sibling_retains(
                pfd, os.path.dirname(ledger), os.path.basename(ledger), self.euid)
            self.log_fd, log = open_private(ledger + LOG_SUFFIX, self.euid, self.root, create=True, write=True,
                                            label='reap log')
            latest, order = {}, []
            for rec in records:
                if rec['path'] not in latest:
                    order.append(rec['path'])
                latest[rec['path']] = rec
                if rec['retain']:
                    self.retain_by_path.setdefault(rec['path'], ledger)
                    self.retain_by_id.setdefault((rec['dev'], rec['ino'], rec['sha256']), ledger)
            append_line(self.log_fd, {
                'at': utc_now(), 'run': self.run, 'decision': 'RUN-START', 'ledger': ledger, 'ledger_sha256': ledger_sha,
                'ledger_records': len(records), 'explicit_paths': list(args.paths), 'dry_run': args.dry_run,
                'retained_manifests': self.retained.manifests, 'retain_ledgers': sources,
                'sandbox': self.root + '/', 'euid': self.euid, 'pid': os.getpid(), 'ppid': os.getppid(),
                'parent_comm': comm_of(os.getppid()),
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
            os.close(pfd)
            if self.log_fd is not None:
                os.close(self.log_fd)
        return 1 if self.failed else 0

    def recheck(self, path, leaf_fd, st):
        """F7: after the git and /proc scans, immediately before deciding, the open file and the path must still
        be exactly what was verified. A link added, a rename, a write or a chmod all move ctime."""
        now = os.fstat(leaf_fd)
        if now.st_nlink != 1:
            return (f'SHARED HARD LINK: link count {now.st_nlink} at the moment of overwriting — a name was added '
                    'while it was being checked')
        if (now.st_size, now.st_mtime_ns, now.st_ctime_ns) != (st.st_size, st.st_mtime_ns, st.st_ctime_ns):
            return 'CHANGED while it was being checked (its size, content time or change time moved)'
        try:
            pfd, leaf = open_parent(path, self.root, self.euid)
        except Absent:
            return 'CHANGED while it was being checked: the path no longer exists'
        try:
            lst = os.stat(leaf, dir_fd=pfd, follow_symlinks=False)
        except FileNotFoundError:
            return 'CHANGED while it was being checked: the path no longer exists'
        finally:
            os.close(pfd)
        if stat.S_ISLNK(lst.st_mode) or (lst.st_dev, lst.st_ino) != (st.st_dev, st.st_ino):
            return 'CHANGED while it was being checked: the path now reaches a different file'
        return None

    def reap_one(self, path, rec):
        hold = 'REFUSED' if self.explicit else 'KEPT'
        try:
            check_target_form(path, self.root)
        except Refused as e:
            return self.decide('REFUSED', path, str(e), rec, failure=True)
        source = self.retain_by_path.get(path) or self.retain_by_id.get((rec['dev'], rec['ino'], rec['sha256']))
        if source:
            return self.decide(hold, path, f'RETAIN: recorded with --retain in {source}; retain is never lifted',
                               rec, failure=self.explicit)
        reason = self.retained.refusal(path)
        if reason:
            return self.decide(hold, path, reason, rec, failure=self.explicit)
        parent_fd = leaf_fd = wfd = None
        mode, made_writable = None, False
        try:
            parent_fd, leaf = open_parent(path, self.root, self.euid)
            leaf_fd, st = open_leaf(parent_fd, leaf, path, write=False)
            reason = identity_refusal(rec, st, self.euid)
            if reason:
                raise Refused(reason + (CHANGED_HINT if reason.startswith('CHANGED') else ''))
            reason = self.retained.refusal(path, st)
            if reason:
                return self.decide(hold, path, reason, rec, failure=self.explicit)
            digest, _ = sha256_fd(leaf_fd)
            if digest != rec['sha256']:
                raise Refused(f'CHANGED: content sha256 {digest[:16]} is not the recorded {rec["sha256"][:16]}'
                              + CHANGED_HINT)
            # The caller's own processes are read afresh for each file, immediately before its scan, not once per
            # run: a pipeline member that exited earlier in the run, and whose pid another process now holds, is not
            # exempted. (The gap between that read and the scan is not closed; it is microseconds, not a run.)
            reason = git_refusal(path, self.root) or process_refusal(st.st_dev, st.st_ino, os.path.dirname(path),
                                                                      os.getpid(), caller_processes(os.getpid()))
            if reason:
                raise Refused(reason)
            reason = self.recheck(path, leaf_fd, st)
            if reason:
                raise Refused(reason)
            if not os.access(f'/proc/self/fd/{parent_fd}', os.W_OK | os.X_OK, effective_ids=True):
                raise Refused('its directory is not writable: it could be overwritten but never unlinked, so it is '
                              'not touched')
            mode = stat.S_IMODE(st.st_mode)
            if self.args.dry_run:
                note = None if mode & stat.S_IWUSR else (f'read-only ({oct(mode)}): a real run makes it '
                                                         'owner-writable through the verified descriptor first')
                return self.decide('WOULD-SHRED', path, note, rec)
            append_line(self.log_fd, {'at': utc_now(), 'run': self.run, 'decision': 'SHREDDING', 'path': path,
                                      'mode': oct(mode)})
            if not mode & stat.S_IWUSR:
                try:
                    os.fchmod(leaf_fd, mode | stat.S_IWUSR)
                except OSError as e:
                    return self.decide('REFUSED', path, f'read-only and cannot be made owner-writable '
                                       f'({e.strerror}); nothing was written', rec, failure=True)
                made_writable = True
            try:
                wfd = os.open(f'/proc/self/fd/{leaf_fd}', os.O_RDWR | os.O_NOCTTY | os.O_CLOEXEC)
            except OSError as e:
                return self.decide('REFUSED', path, f'cannot open for overwriting: {e.strerror}; nothing was written',
                                   rec, failure=True)
            wst = os.fstat(wfd)
            if (wst.st_dev, wst.st_ino) != (st.st_dev, st.st_ino) or wst.st_nlink != 1:
                return self.decide('REFUSED', path, f'changed at the moment of overwriting (link count '
                                   f'{wst.st_nlink}); nothing was written', rec, failure=True)
            os.lseek(wfd, 0, os.SEEK_SET)
            proc = subprocess.run([self.shred, '-n', '3', '-z', '-'], stdin=subprocess.DEVNULL, stdout=wfd,
                                  stderr=subprocess.PIPE)
            if proc.returncode != 0:
                err = proc.stderr.decode('utf-8', 'replace').strip()[:300]
                return self.decide('SHRED-FAILED', path, f'shred exited {proc.returncode} ({err}); NOT unlinked, so '
                                   'the failure stays recoverable', rec, failure=True)
            if not reads_as_zeros(wfd):
                return self.decide('SHRED-UNVERIFIED', path, 'shred exited 0 but the content does not read as '
                                   'zeros; NOT unlinked', rec, failure=True)
            made_writable = False  # overwritten and verified: nothing left to put back
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
            if made_writable:
                try:
                    os.fchmod(leaf_fd, mode)  # the overwrite did not complete: leave the mode as it was found
                except OSError:
                    pass
            for f in (wfd, leaf_fd, parent_fd):
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
