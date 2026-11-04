#!/usr/bin/env python3
"""Read-only status for isolated z4 recovery sandboxes."""
import argparse
import json
import os
from pathlib import Path

MARKER = '.z4-recovery-test-sandbox'
JOURNAL = '.z4-recovery-journal.json'
KNOWN = {'staged', 'moving_original', 'original_preserved', 'completed'}

def inspect(raw):
    if not raw:
        print('[not configured] set Z4_RECOVERY_TEST_SANDBOX to an isolated test directory')
        return 0
    p = Path(raw).expanduser().resolve(strict=True)
    home = Path.home().resolve()
    actual = home / 'GPUBrewLauncher'
    backups = home / 'gpubrew-backups'
    if p == home or p == actual or p == backups or p in actual.parents or p in backups.parents or actual in p.parents or backups in p.parents:
        raise ValueError('protected location blocked')
    marker = p / MARKER
    if not p.is_dir() or not marker.is_file() or marker.is_symlink():
        raise ValueError('test sandbox marker missing or invalid')
    journal = p / JOURNAL
    if journal.is_symlink():
        raise ValueError('symlink journal blocked')
    if not journal.exists():
        print('[clear] no recovery journal in test sandbox')
        return 0
    if not journal.is_file():
        raise ValueError('journal must be a regular file')
    data = json.loads(journal.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('journal must be a json object')
    phase = data.get('phase')
    if not isinstance(phase, str) or phase not in KNOWN:
        raise ValueError('unknown recovery phase; manual inspection required')
    if phase == 'completed':
        print('[completed] restore finished in sandbox; completion journal remains')
        print('[safe] no rollback initiated automatically')
        return 0
    print('[interrupted] recovery journal phase:', phase)
    print('[safe] no automatic file changes; use manual sandbox recovery')
    return 3

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sandbox', default=os.environ.get('Z4_RECOVERY_TEST_SANDBOX', ''))
    args = ap.parse_args()
    try:
        raise SystemExit(inspect(args.sandbox))
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print('[blocked]', type(e).__name__, str(e))
        raise SystemExit(2)
