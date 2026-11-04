#!/usr/bin/env python3
"""z4tools recovery candidate. Production mutations require explicit opt-in.

Never deletes backups, preserved launchers, or staged content. Run when launcher is stopped.
"""
import argparse
import ctypes
import errno
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import uuid

MAX_ENTRIES = 20000
MAX_BYTES = 4 * 1024**3
MAX_SINGLE = 1024**3
PHASES = {'staged', 'moving_original', 'original_preserved', 'completed'}


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def safe_path(path):
    if path.is_symlink():
        raise ValueError('symlinked recovery path: ' + str(path))
    return path


def root_path(value, production):
    home = Path.home().resolve()
    if production:
        if value is not None:
            raise ValueError('production root is fixed; omit --sandbox')
        root = home
    else:
        if value is None:
            raise ValueError('--sandbox required for testing')
        root = Path(value).expanduser().absolute()
        if root.is_symlink() or not root.is_dir():
            raise ValueError('invalid sandbox')
        root = root.resolve()
        if root == home or home in root.parents or root in home.parents:
            raise ValueError('sandbox overlaps home')
        if not (root / '.z4-recovery-test-sandbox').is_file() or (root / '.z4-recovery-test-sandbox').is_symlink():
            raise ValueError('sandbox marker missing')
    return root


def state_paths(root):
    state = root / '.z4tools-recovery-state'
    return state, root / 'GPUBrewLauncher', state / 'journal.json', state / 'recovery.lock'


def init_state(root):
    state, target, journal, lock = state_paths(root)
    safe_path(state)
    if state.exists() and not state.is_dir():
        raise ValueError('recovery state is not a directory')
    if not state.exists():
        state.mkdir(mode=0o700)
        fsync_dir(root)
    safe_path(journal)
    safe_path(lock)
    safe_path(target)
    return state, target, journal, lock


@contextmanager
def locked(root):
    state, target, journal, lock = init_state(root)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('another recovery operation is running')
        yield state, target, journal
    finally:
        os.close(fd)


def rename_noreplace(source, destination):
    """Atomic no-overwrite rename; fail closed if unsupported."""
    source, destination = Path(source), Path(destination)
    safe_path(source)
    safe_path(destination)
    libc = ctypes.CDLL(None, use_errno=True)
    fn = getattr(libc, 'renameat2', None)
    if fn is None:
        raise ValueError('atomic no-replace rename unavailable; refusing mutation')
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    result = fn(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    if result != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), str(destination))


def validate_recovery_layout(state, target, phase, stage, rollback, quarantine):
    """Reject uncertain states rather than guessing which tree is original."""
    for path in (stage, rollback, quarantine, target):
        safe_path(path)
    if quarantine.exists():
        raise ValueError('quarantine already exists; manual inspection required')
    if phase == 'staged':
        if rollback.exists() or not target.is_dir():
            raise ValueError('staged journal conflicts with filesystem; manual inspection required')
    elif phase == 'moving_original':
        if rollback.is_dir() and target.exists():
            raise ValueError('ambiguous original and rollback both exist; manual inspection required')
        if not rollback.is_dir() and not target.is_dir():
            raise ValueError('original and rollback missing; manual inspection required')
    elif phase == 'original_preserved':
        if not rollback.is_dir():
            raise ValueError('preserved original missing; manual inspection required')


def journal_read(journal):
    safe_path(journal)
    if not journal.exists():
        return None
    if not journal.is_file() or journal.stat().st_size > 16384:
        raise ValueError('invalid journal; manual inspection required')
    try:
        data = json.loads(journal.read_text())
    except (ValueError, UnicodeError, OSError) as exc:
        raise ValueError('corrupt journal; manual inspection required') from exc
    if not isinstance(data, dict) or data.get('version') != 2 or data.get('phase') not in PHASES:
        raise ValueError('invalid journal format')
    ident = data.get('id')
    if not isinstance(ident, str) or len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident):
        raise ValueError('invalid journal id')
    return data


def journal_write(journal, ident, phase):
    payload = {'version': 2, 'id': ident, 'phase': phase}
    temp = journal.parent / ('.journal-' + uuid.uuid4().hex)
    try:
        with temp.open('x') as f:
            json.dump(payload, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, journal)
        fsync_dir(journal.parent)
    finally:
        temp.unlink(missing_ok=True)


def archive_open(path):
    path = Path(path).expanduser().absolute()
    if path.is_symlink() or not path.is_file() or not path.name.endswith(('.tar.gz', '.tgz')):
        raise ValueError('expected regular .tar.gz backup')
    return path


def members_validated(tf):
    seen = set()
    files = 0
    total = 0
    launcher = False
    for m in tf:
        parts = m.name.rstrip('/').split('/')
        if (not m.name or m.name.startswith('/') or '\\' in m.name or '\x00' in m.name
                or any(p in ('', '.', '..') for p in parts) or parts[0] != 'GPUBrewLauncher'
                or not (m.isfile() or m.isdir())):
            raise ValueError('unsafe archive member')
        normalized = '/'.join(parts)
        if normalized in seen:
            raise ValueError('duplicate archive member')
        seen.add(normalized)
        if len(seen) > MAX_ENTRIES:
            raise ValueError('too many archive entries')
        if m.isfile():
            files += 1
            if m.size < 0 or m.size > MAX_SINGLE:
                raise ValueError('archive member too large')
            total += m.size
            if total > MAX_BYTES:
                raise ValueError('archive too large')
            if normalized.startswith('GPUBrewLauncher/homebrew-launcher/'):
                launcher = True
        yield m, parts
    if not launcher:
        raise ValueError('archive missing launcher contents')


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_archive(path):
    path = archive_open(path)
    # Streaming pass verifies gzip contents before extraction.
    with tarfile.open(path, 'r|gz') as tf:
        for m, _ in members_validated(tf):
            if m.isfile():
                stream = tf.extractfile(m)
                if stream is None:
                    raise ValueError('unreadable archive member')
                with stream:
                    while stream.read(1024 * 1024):
                        pass
    return path


def names(state, ident):
    return state / ('stage-' + ident), state / ('rollback-' + ident), state / ('quarantine-' + ident)


def status(state, target, journal):
    data = journal_read(journal)
    if data is None:
        print('[clear] no recovery journal')
        return
    stage, rollback, quarantine = names(state, data['id'])
    for path in (stage, rollback, quarantine, target):
        safe_path(path)
    print('[status]', data['phase'])
    print('[rollback]', 'present' if rollback.is_dir() else 'absent')
    print('[launcher]', 'present' if target.is_dir() else 'absent')
    if data['phase'] == 'completed':
        print('[completed] original preserved; no recovery required')
    else:
        print('[interrupted] manual recover requires --confirm RECOVER')


def start(state, target, journal, archive):
    if journal_read(journal) is not None:
        raise ValueError('existing journal; inspect before starting')
    if not target.is_dir() or not (target / 'homebrew-launcher').is_dir():
        raise ValueError('existing launcher missing')
    if not os.access(state, os.W_OK):
        raise ValueError('recovery state not writable')
    ident = uuid.uuid4().hex
    stage, rollback, quarantine = names(state, ident)
    for p in (stage, rollback, quarantine):
        if p.exists() or p.is_symlink():
            raise ValueError('recovery destination already exists')
    archive = validate_archive(archive)
    original_hash = sha256(archive)
    print('[verified] archive integrity and paths')
    stage.mkdir(mode=0o700)
    try:
        with tarfile.open(archive, 'r:gz') as tf:
            for m, parts in members_validated(tf):
                dest = stage.joinpath(*parts)
                if m.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    stream = tf.extractfile(m)
                    if stream is None:
                        raise ValueError('unreadable archive member')
                    with stream, dest.open('xb') as out:
                        shutil.copyfileobj(stream, out, 1024 * 1024)
                        out.flush()
                        os.fsync(out.fileno())
                    if dest.stat().st_size != m.size:
                        raise ValueError('extraction size mismatch')
        if sha256(archive) != original_hash:
            raise ValueError('archive changed while extracting')
        staged_launcher = stage / 'GPUBrewLauncher'
        if not (staged_launcher / 'homebrew-launcher').is_dir():
            raise ValueError('staged launcher missing')
        # Same-filesystem atomic renames; journal intent is synced before each move.
        if target.stat().st_dev != state.stat().st_dev:
            raise ValueError('rollback must be on same filesystem')
        fsync_dir(stage)
        journal_write(journal, ident, 'staged')
        journal_write(journal, ident, 'moving_original')
        rename_noreplace(target, rollback)
        fsync_dir(state)
        fsync_dir(target.parent)
        journal_write(journal, ident, 'original_preserved')
        rename_noreplace(staged_launcher, target)
        fsync_dir(stage)
        fsync_dir(target.parent)
        journal_write(journal, ident, 'completed')
        print('[completed] launcher restored; original retained at:', rollback)
        print('[retained] journal and staging preserved for audit')
    except Exception:
        print('[blocked] operation failed; inspect journal and use manual recover if needed', file=sys.stderr)
        raise


def recover(state, target, journal):
    data = journal_read(journal)
    if data is None:
        raise ValueError('no recovery journal')
    phase = data['phase']
    stage, rollback, quarantine = names(state, data['id'])
    for p in (stage, rollback, quarantine, target):
        safe_path(p)
    if phase == 'completed':
        print('[completed] no rollback performed; preserved original:', rollback)
        return
    validate_recovery_layout(state, target, phase, stage, rollback, quarantine)
    resolved = state / ('resolved-' + data['id'] + '.json')
    if resolved.exists() or resolved.is_symlink():
        raise ValueError('resolved journal already exists; manual inspection required')
    if rollback.is_dir():
        if target.exists():
            if phase != 'original_preserved' or quarantine.exists() or quarantine.is_symlink():
                raise ValueError('ambiguous state; manual inspection required')
            rename_noreplace(target, quarantine)
            fsync_dir(target.parent)
            fsync_dir(state)
            print('[quarantined] incomplete replacement:', quarantine)
        rename_noreplace(rollback, target)
        fsync_dir(state)
        fsync_dir(target.parent)
        print('[recovered] original launcher restored')
    elif target.is_dir():
        print('[safe] original launcher already present')
    else:
        raise ValueError('original launcher missing; manual inspection required')
    # Preserve the journal as an audit record instead of deleting it; mark resolved.
    rename_noreplace(journal, resolved)
    fsync_dir(state)
    print('[retained] recovery journal archived:', resolved)


def main():
    p = argparse.ArgumentParser(description='z4tools guarded recovery candidate')
    p.add_argument('action', choices=('status', 'dry-run', 'restore', 'recover'))
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--sandbox', type=Path)
    mode.add_argument('--production', action='store_true')
    p.add_argument('--archive', type=Path)
    p.add_argument('--confirm', default='')
    p.add_argument('--enable-production', action='store_true')
    args = p.parse_args()
    try:
        root = root_path(args.sandbox, args.production)
        if args.production and args.action in ('restore', 'recover') and not args.enable_production:
            raise ValueError('production changes disabled; explicit --enable-production required')
        if args.action == 'restore' and args.confirm != 'RESTORE':
            raise ValueError('restore requires --confirm RESTORE')
        if args.action == 'recover' and args.confirm != 'RECOVER':
            raise ValueError('recovery requires --confirm RECOVER')
        if args.action in ('restore', 'dry-run') and args.archive is None:
            raise ValueError('--archive required')
        if args.action == 'dry-run':
            validate_archive(args.archive)
            print('[pass] archive integrity and paths verified')
            print('[dry-run] no launcher files replaced')
            return 0
        with locked(root) as (state, target, journal):
            if args.action == 'status':
                status(state, target, journal)
            elif args.action == 'restore':
                start(state, target, journal, args.archive)
            else:
                recover(state, target, journal)
    except (ValueError, OSError, RuntimeError, tarfile.TarError, EOFError) as exc:
        print('[blocked]', str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
