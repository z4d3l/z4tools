#!/usr/bin/env python3
"""z4tools v1.7 first-run wizard; no launcher or backup mutation."""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from datetime import datetime, timezone

MARKER = '.z4-first-run.json'
TEST_MARKER = '.z4-first-run-test-sandbox'
DEPLOY_KEY = 'app_deployment_directory'

class WizardError(Exception):
    pass

def assert_safe_base(base, testing=False):
    base = Path(base).absolute()
    if not base.is_dir() or base.is_symlink():
        raise WizardError('invalid or symlinked wizard directory')
    if testing:
        home = Path.home().resolve()
        forbidden = (home, home / 'GPUBrewLauncher', home / 'gpubrew-backups', home / 'z4tools', home / 'z4tools-v1.7-dev')
        resolved = base.resolve()
        if any(resolved == p or p in resolved.parents or resolved in p.parents for p in forbidden):
            raise WizardError('test sandbox overlaps protected path')
        marker = base / TEST_MARKER
        if marker.is_symlink() or not marker.is_file():
            raise WizardError('missing test sandbox marker')
    else:
        if base.name != 'z4tools' or not (base / 'z4tools.sh').is_file():
            raise WizardError('wizard requires a z4tools installation folder')
    path = base / MARKER
    if path.is_symlink():
        raise WizardError('wizard marker cannot be a symlink')
    return base

def status(base):
    marker = base / MARKER
    if marker.is_symlink():
        raise WizardError('symlinked wizard marker blocked')
    if not marker.exists():
        print('[pending] first-run setup not completed')
        return False
    st = marker.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_size > 16384:
        raise WizardError('invalid wizard marker; manual inspection required')
    try:
        data = json.loads(marker.read_text())
    except (OSError, ValueError, UnicodeDecodeError):
        raise WizardError('unreadable setup marker; manual inspection required')
    if not isinstance(data, dict) or data.get('version') != 1 or data.get('complete') is not True:
        raise WizardError('invalid setup marker; manual inspection required')
    print('[complete] first-run setup already completed')
    return True

def mark_completed(base):
    marker = base / MARKER
    payload = (json.dumps({'version':1, 'complete':True, 'completed_at':datetime.now(timezone.utc).isoformat()}, indent=2) + '\n').encode()
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
    finally:
        pass
    dirfd = os.open(base, os.O_RDONLY)
    try:
        os.fsync(dirfd)
    finally:
        os.close(dirfd)

def get_editor():
    import config_editor
    return config_editor

def current_settings(base):
    editor = get_editor()
    data, _, _ = editor.load(base / 'settings.json')
    return data

def check_environment():
    print('\n=== environment ===')
    print('[ok] python:', sys.version.split()[0])
    for cmd in ('tar', 'git', 'unzip'):
        print(('[ok]' if shutil.which(cmd) else '[notice]'), cmd, 'available' if shutil.which(cmd) else 'not found')
    print('[info] none of these checks installs or downloads anything')

def wizard(base, input_fn=input):
    if status(base):
        print('[info] use feature #5 to edit settings later')
        return
    editor = get_editor()
    data = current_settings(base)
    from settings import DEFAULT_DEPLOYMENT
    default = str(DEFAULT_DEPLOYMENT)
    configured = data.get(DEPLOY_KEY, default)
    print('\n=== z4tools v1.7 first-run setup ===')
    print('configuration:', base / 'settings.json')
    print('existing deployment directory:', configured)
    print('your real launcher and backups will not be modified')
    check_environment()
    choice = input_fn('\n[1] keep current/default directory  [2] choose a directory  [0] cancel: ').strip()
    if choice == '0':
        print('[cancelled] no changes');return
    if choice not in ('1', '2'):
        print('[cancelled] unrecognized choice');return
    newdir = None
    if choice == '2':
        raw = input_fn('new deployment directory (absolute or ~/...): ').strip()
        if not raw:
            print('[cancelled] no changes');return
        newdir = editor.validate_deployment(raw)
    print('\n=== setup preview ===')
    print('configuration:', base / 'settings.json')
    print('deployment directory:', newdir if newdir else configured)
    print('settings write:', 'yes; rollback history will be retained' if newdir and newdir != data.get(DEPLOY_KEY) else 'no')
    print('setup marker:', base / MARKER)
    print('launcher changes: none')
    print('backup archive changes: none')
    if input_fn('type SETUP to finish (anything else cancels): ').strip() != 'SETUP':
        print('[cancelled] no changes');return
    if newdir is not None and newdir != data.get(DEPLOY_KEY):
        # Reuses feature #5 for locking, optimistic concurrency, validation, and rollback history.
        editor.commit(base, DEPLOY_KEY, newdir, confirm=True)
    mark_completed(base)
    print('[complete] setup finished')
    print('[safe] live launcher and archives untouched')

def main():
    p = argparse.ArgumentParser(description='z4tools v1.7 first-run wizard')
    p.add_argument('command', choices=('wizard', 'status'), nargs='?', default='wizard')
    p.add_argument('--test-base', help='isolated marked test directory only')
    args = p.parse_args()
    if args.test_base:
        base = assert_safe_base(args.test_base, True)
    else:
        base = assert_safe_base(Path(__file__).resolve().parent)
    if args.command == 'status':status(base)
    else:wizard(base)

if __name__ == '__main__':
    try: main()
    except (WizardError, OSError, ValueError, EOFError, KeyboardInterrupt) as exc:
        print('[blocked]', str(exc), file=sys.stderr);sys.exit(2)
