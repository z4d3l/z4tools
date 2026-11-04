#!/usr/bin/env python3
"""Isolated crash journal prototype. Never operates outside marked test sandboxes."""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid

MARKER = '.z4-recovery-test-sandbox'
JOURNAL = '.z4-recovery-journal.json'


def sandbox(path):
    root = Path(path).expanduser().absolute()
    real = (Path.home() / 'GPUBrewLauncher').resolve()
    if root.is_symlink() or not root.is_dir() or not (root / MARKER).is_file():
        raise ValueError('unmarked or invalid sandbox')
    root = root.resolve()
    if root == Path.home().resolve() or root == real or root in real.parents or real in root.parents:
        raise ValueError('sandbox overlaps real launcher')
    if (root / JOURNAL).is_symlink():
        raise ValueError('journal symlink blocked')
    return root


def write_journal(root, phase, backup):
    data = {'version': 1, 'phase': phase, 'backup': backup}
    tmp = root / ('.z4-journal-temp-' + uuid.uuid4().hex)
    try:
        with tmp.open('x') as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, root / JOURNAL)
        fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        tmp.unlink(missing_ok=True)


def paths(root):
    return root / 'GPUBrewLauncher', root / '.z4-rollback-journal-test', root / '.z4-staged-journal-test'


def start(root, crash):
    target, rollback, staged = paths(root)
    if (root / JOURNAL).exists() or rollback.exists() or staged.exists():
        raise ValueError('pending recovery or leftover test files; run recover')
    if not (target / 'homebrew-launcher' / 'state.txt').is_file():
        raise ValueError('test launcher missing')
    (staged / 'homebrew-launcher').mkdir(parents=True)
    (staged / 'homebrew-launcher' / 'state.txt').write_text('restored')
    write_journal(root, 'staged', rollback.name)
    if crash == 'staged':
        os._exit(44)
    # Journal intent BEFORE moving original, so recovery handles either side of rename.
    write_journal(root, 'moving_original', rollback.name)
    target.rename(rollback)
    if crash == 'moved':
        os._exit(44)
    write_journal(root, 'original_preserved', rollback.name)
    staged.rename(target)
    if crash == 'replaced':
        os._exit(44)
    write_journal(root, 'completed', rollback.name)
    print('[pass] test swap completed; original preserved', flush=True)


def recover(root):
    target, rollback, staged = paths(root)
    journal = root / JOURNAL
    if not journal.is_file():
        raise ValueError('no journal found; no automatic changes')
    data = json.loads(journal.read_text())
    if data.get('version') != 1 or data.get('backup') != rollback.name or data.get('phase') not in ('staged','moving_original','original_preserved','completed'):
        raise ValueError('invalid journal')
    phase = data['phase']
    if phase == 'completed':
        if not target.is_dir() or not rollback.is_dir():
            raise ValueError('completed state inconsistent; manual inspection needed')
        print('[safe] completed restore detected; preserved rollback retained')
        return
    if target.is_symlink() or rollback.is_symlink() or staged.is_symlink():
        raise ValueError('symlink detected; manual inspection needed')
    if rollback.is_dir():
        if target.exists():
            if phase != 'original_preserved' or not target.is_dir():
                raise ValueError('both launcher and rollback exist; manual inspection needed')
            quarantine = root / '.z4-incomplete-replacement'
            if quarantine.exists() or quarantine.is_symlink():
                raise ValueError('quarantine already exists; manual inspection needed')
            target.rename(quarantine)
            print('[preserved] incomplete replacement quarantined')
        rollback.rename(target)
        print('[recovered] original test launcher restored')
    elif not target.is_dir():
        raise ValueError('original launcher missing; manual inspection needed')
    else:
        print('[safe] original test launcher already in place')
    # Never remove staged directory automatically; keep it for inspection.
    journal.unlink()
    print('[safe] journal cleared; staged test files retained if present')


def main():
    p = argparse.ArgumentParser(description='journal crash simulation in marked sandbox only')
    p.add_argument('action', choices=['start','recover'])
    p.add_argument('--sandbox', required=True)
    p.add_argument('--crash', choices=['staged','moved','replaced'])
    a = p.parse_args()
    try:
        root = sandbox(a.sandbox)
        if a.action == 'start':
            start(root, a.crash)
        else:
            recover(root)
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print('[blocked]', e, file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
