#!/usr/bin/env python3
"""Isolated combined recovery test. NEVER targets real GPUBrewLauncher."""
import argparse
import fcntl
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import uuid

from staged_recovery import validate
from recovery_journal import write_journal

JOURNAL = '.z4-recovery-journal.json'

def sandbox(value):
    root = Path(value).expanduser().absolute()
    tmp = Path(tempfile.gettempdir()).resolve()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('sandbox missing or symlink')
    root = root.resolve()
    if root.parent != tmp or not root.name.startswith('z4-combined-'):
        raise ValueError('sandbox must be a fresh z4-combined-* directory directly in temp')
    if not (root / '.z4-recovery-test-sandbox').is_file():
        raise ValueError('sandbox marker missing')
    for name in (JOURNAL, 'GPUBrewLauncher', '.z4-combined-rollback', '.z4-combined-stage', '.z4-combined-quarantine'):
        if (root / name).is_symlink():
            raise ValueError('symlink blocked: ' + name)
    return root

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.digest()

def locations(root):
    return (root / 'GPUBrewLauncher', root / '.z4-combined-rollback', root / '.z4-combined-stage', root / '.z4-combined-quarantine')

def start(root, archive, crash):
    target, rollback, stage, quarantine = locations(root)
    if any(p.exists() for p in (root / JOURNAL, rollback, stage, quarantine)):
        raise ValueError('pending operation; recover before starting')
    if not (target / 'homebrew-launcher').is_dir():
        raise ValueError('test launcher missing')
    archive = archive.expanduser().absolute()
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('archive missing or symlink')
    initial = sha(archive)
    count, total = validate(archive)
    print(f'[validated] {count} files, {total} bytes', flush=True)
    stage.mkdir()
    with tarfile.open(archive, 'r:gz') as tf:
        for member in tf:
            parts = member.name.rstrip('/').split('/')
            if (not member.name or member.name.startswith('/') or '\\' in member.name
                or any(p in ('', '.', '..') for p in parts)
                or parts[0] != 'GPUBrewLauncher'
                or not (member.isfile() or member.isdir())):
                raise ValueError('unsafe archive member')
            dest = stage.joinpath(*parts)
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                source = tf.extractfile(member)
                if source is None:
                    raise ValueError('unreadable member')
                with source, dest.open('xb') as out:
                    shutil.copyfileobj(source, out, 1024*1024)
                if dest.stat().st_size != member.size:
                    raise ValueError('size mismatch')
    if sha(archive) != initial:
        raise ValueError('archive changed during staging')
    if not (stage / 'GPUBrewLauncher' / 'homebrew-launcher').is_dir():
        raise ValueError('staged launcher missing')
    print('[staged] archive unchanged; files extracted', flush=True)
    write_journal(root, 'staged', rollback.name)
    if crash == 'staged':
        os._exit(44)
    write_journal(root, 'moving_original', rollback.name)
    target.rename(rollback)
    if crash == 'moved':
        os._exit(44)
    write_journal(root, 'original_preserved', rollback.name)
    (stage / 'GPUBrewLauncher').rename(target)
    if crash == 'replaced':
        os._exit(44)
    write_journal(root, 'completed', rollback.name)
    print('[completed] isolated restore; rollback retained', flush=True)

def recover(root):
    target, rollback, stage, quarantine = locations(root)
    journal = root / JOURNAL
    if not journal.is_file() or journal.is_symlink():
        raise ValueError('journal missing or invalid')
    data = json.loads(journal.read_text())
    if data.get('version') != 1 or data.get('backup') != rollback.name:
        raise ValueError('unexpected journal data')
    phase = data.get('phase')
    if phase not in ('staged', 'moving_original', 'original_preserved', 'completed'):
        raise ValueError('invalid journal phase')
    if phase == 'completed':
        if not target.is_dir() or not rollback.is_dir():
            raise ValueError('completed state inconsistent')
        print('[safe] completed; rollback retained', flush=True)
        return
    if rollback.is_dir():
        if target.exists():
            if phase != 'original_preserved' or quarantine.exists():
                raise ValueError('ambiguous replacement; manual inspection required')
            target.rename(quarantine)
            print('[quarantined] incomplete replacement', flush=True)
        rollback.rename(target)
        print('[recovered] original restored', flush=True)
    elif not target.is_dir():
        raise ValueError('original missing; manual inspection required')
    else:
        print('[safe] original already present', flush=True)
    journal.unlink()
    print('[safe] journal cleared; staging retained', flush=True)

@contextmanager
def recovery_lock(root):
    lock = root / '.z4-recovery.lock'
    if lock.is_symlink():
        raise ValueError('symlinked recovery lock blocked')
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('another recovery operation is running')
        yield
    finally:
        os.close(fd)


def startup_check(root):
    journal = root / JOURNAL
    if journal.is_symlink():
        raise ValueError('symlinked journal blocked')
    if not journal.exists():
        print('[clear] no pending recovery journal', flush=True)
        return
    try:
        data = json.loads(journal.read_text())
    except (ValueError, UnicodeError):
        raise ValueError('corrupt journal; manual inspection required')
    if data.get('version') != 1 or data.get('backup') != '.z4-combined-rollback' or data.get('phase') not in ('staged', 'moving_original', 'original_preserved', 'completed'):
        raise ValueError('invalid journal; manual inspection required')
    print('[pending] recovery phase:', data['phase'], flush=True)
    print('[safe] run recover explicitly; no automatic changes', flush=True)

def main():
    p = argparse.ArgumentParser(description='combined recovery test; temp sandboxes only')
    p.add_argument('action', choices=('start','recover','check'))
    p.add_argument('--sandbox', required=True)
    p.add_argument('--archive', type=Path)
    p.add_argument('--crash', choices=('staged','moved','replaced'))
    p.add_argument('--confirm', default='')
    a = p.parse_args()
    try:
        root = sandbox(a.sandbox)
        with recovery_lock(root):
            if a.action == 'check':
                startup_check(root)
            elif a.action == 'start':
                startup_check(root)
                if (root / JOURNAL).exists():
                    raise ValueError('unfinished journal; recovery required')
                if a.confirm != 'RESTORE':
                    raise ValueError('confirmation required: --confirm RESTORE')
                if a.archive is None:
                    raise ValueError('--archive required')
                start(root, a.archive, a.crash)
            else:
                startup_check(root)
                recover(root)
    except (ValueError, OSError, RuntimeError, tarfile.TarError, json.JSONDecodeError) as e:
        print('[blocked]', str(e), file=sys.stderr, flush=True)
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())
