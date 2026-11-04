#!/usr/bin/env python3
"""Test-only recovery lock and journal discovery. Never restores files."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys

MARKER = '.z4-recovery-test-sandbox'
LOCK = '.z4-recovery.lock'
JOURNAL = '.z4-recovery-journal.json'


def sandbox(path):
    p = Path(path).expanduser().resolve(strict=True)
    home = Path.home().resolve()
    real = home / 'GPUBrewLauncher'
    if p == home or p == real or p in real.parents or real in p.parents:
        raise ValueError('protected path')
    if not p.is_dir() or not (p / MARKER).is_file() or (p / MARKER).is_symlink():
        raise ValueError('missing test sandbox marker')
    if (p / LOCK).is_symlink() or (p / JOURNAL).is_symlink():
        raise ValueError('symlink lock/journal forbidden')
    return p


def acquire(p):
    fd = os.open(p / LOCK, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise RuntimeError('another recovery holds the lock')
    return fd


def scan(p):
    j = p / JOURNAL
    if not j.exists():
        print('[clear] no unfinished journal found')
        return 0
    if not j.is_file():
        print('[blocked] journal is not a regular file')
        return 2
    try:
        obj = json.loads(j.read_text())
        if not isinstance(obj, dict):
            raise ValueError('journal not object')
        state = obj.get('state', obj.get('stage', 'unknown'))
        if not isinstance(state, str):
            raise ValueError('invalid state')
    except (OSError, ValueError) as exc:
        print('[blocked] unreadable journal:', type(exc).__name__)
        return 2
    print('[detected] recovery journal stage:', state)
    print('[safe] no automatic restoration attempted')
    return 3


def main():
    ap = argparse.ArgumentParser(description='isolated recovery guard test; never restores')
    ap.add_argument('command', choices=('check', 'hold'))
    ap.add_argument('--sandbox', required=True)
    ap.add_argument('--seconds', type=float, default=2.0)
    args = ap.parse_args()
    try:
        p = sandbox(args.sandbox)
        fd = acquire(p)
        try:
            if args.command == 'check':
                return scan(p)
            if not 0 <= args.seconds <= 15:
                raise ValueError('seconds must be 0..15')
            import time
            print('[locked] exclusive recovery lock acquired', flush=True)
            time.sleep(args.seconds)
            print('[released] lock released', flush=True)
            return 0
        finally:
            os.close(fd)
    except (ValueError, RuntimeError, OSError) as exc:
        print('[blocked]', str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
