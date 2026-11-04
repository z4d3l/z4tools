#!/usr/bin/env python3
"""Explicitly authorized production restore UI for z4tools v1.7.

This program NEVER edits launcher files itself. Only the separately installed
production_recovery.py performs restoration, after verification and confirmation.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tarfile

PHASES = {'staged', 'moving_original', 'original_preserved', 'completed'}


def recovery_status(home, output=print):
    state = home / '.z4tools-recovery-state'
    journal = state / 'journal.json'
    if state.is_symlink() or (state.exists() and not state.is_dir()):
        output('[blocked] invalid recovery state; manual inspection needed')
        return 'blocked'
    if journal.is_symlink():
        output('[blocked] symlinked journal')
        return 'blocked'
    if not journal.exists():
        output('[clear] no production recovery journal')
        return 'clear'
    try:
        if not journal.is_file() or journal.stat().st_size > 16384:
            raise ValueError('bad journal file')
        data = json.loads(journal.read_text())
        ident = data.get('id') if isinstance(data, dict) else None
        if (not isinstance(data, dict) or data.get('version') != 2
            or data.get('phase') not in PHASES or not isinstance(ident, str)
            or len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident)):
            raise ValueError('invalid format')
    except (ValueError, OSError, UnicodeError):
        output('[blocked] corrupt journal; manual inspection needed')
        return 'blocked'
    phase = data['phase']
    output('[journal] phase: ' + phase)
    if phase == 'completed':
        output('[completed] previous rollback retained; new restores blocked pending manual review')
    else:
        output('[interrupted] do not start another restore; inspect and recover manually')
    return phase


def verified_backup_paths(home):
    backup_dir = home / 'gpubrew-backups'
    if backup_dir.is_symlink() or not backup_dir.is_dir():
        return []
    candidates = sorted(backup_dir.glob('gpubrew-*.tar.gz'))
    return [p for p in candidates if p.is_file() and not p.is_symlink() and p.parent == backup_dir]


def run_engine(engine, args, runner=subprocess.run):
    return runner([sys.executable, str(engine), *args], check=False)


def preflight(home, engine, backup, runner=subprocess.run, output=print):
    launcher = home / 'GPUBrewLauncher'
    state = home / '.z4tools-recovery-state'
    if not engine.is_file() or engine.is_symlink():
        output('[blocked] hardened recovery engine missing or invalid')
        return False
    if (not launcher.is_dir() or launcher.is_symlink()
        or not (launcher / 'homebrew-launcher').is_dir()
        or (launcher / 'homebrew-launcher').is_symlink()):
        output('[blocked] live launcher structure invalid')
        return False
    if recovery_status(home, output) != 'clear':
        output('[blocked] resolve or review existing journal before any new restore')
        return False
    if backup not in verified_backup_paths(home):
        output('[blocked] selected archive is not a regular backup in the backup directory')
        return False
    try:
        backup_bytes = backup.stat().st_size
        with tarfile.open(backup, 'r:gz') as tar:
            estimated = sum(m.size for m in tar if m.isfile())
        # Conservative, approximate budget: staged extraction + 512MiB reserve.
        available = shutil.disk_usage(home).free
        required = estimated + 512 * 1024 * 1024
        if available < required:
            output(f'[blocked] insufficient free space: {available} available, {required} required')
            return False
    except (OSError, tarfile.TarError, EOFError, ValueError) as exc:
        output(f'[blocked] backup preflight failed: {exc}')
        return False
    output('[backup] ' + str(backup))
    output('[launcher to replace] ' + str(launcher))
    output('[rollback root] ' + str(state))
    output('[archive bytes] ' + str(backup_bytes))
    output('[estimated extracted bytes] ' + str(estimated))
    output('[free bytes] ' + str(available))
    output('[dry-run] validating archive contents...')
    result = run_engine(engine, ['dry-run', '--production', '--archive', str(backup)], runner)
    if result.returncode != 0:
        output('[blocked] recovery engine rejected archive')
        return False
    output('[pass] backup verified; no launcher files changed')
    return True


def choose_backup(home, input_fn=input, output=print):
    choices = verified_backup_paths(home)
    if not choices:
        output('[blocked] no valid backup archives found')
        return None
    for idx, path in enumerate(choices, 1):
        output(f'  [{idx}] {path.name}')
    try:
        raw = input_fn('backup number (blank cancels): ').strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not raw.isdecimal() or int(raw) not in range(1, len(choices) + 1):
        output('[cancelled] no archive selected')
        return None
    return choices[int(raw) - 1]


def restore(home, engine, input_fn=input, runner=subprocess.run, output=print):
    backup = choose_backup(home, input_fn, output)
    if backup is None:
        return
    output('\n=== production restore: preflight ===')
    if not preflight(home, engine, backup, runner, output):
        return
    output('\n[warning] this REPLACES ~/GPUBrewLauncher with the selected backup.')
    output('[warning] close the running launcher first. existing changes may be lost.')
    output('[warning] original launcher should be retained in the rollback directory.')
    try:
        first = input_fn('type the EXACT backup filename to continue: ').strip()
        if first != backup.name:
            output('[cancelled] filename did not match')
            return
        second = input_fn('type RESTORE to confirm replacement: ').strip()
        if second != 'RESTORE':
            output('[cancelled] confirmation did not match')
            return
        third = input_fn('type ENABLE PRODUCTION RESTORE to authorize disk changes: ').strip()
        if third != 'ENABLE PRODUCTION RESTORE':
            output('[cancelled] production authorization did not match')
            return
    except (EOFError, KeyboardInterrupt):
        output('[cancelled] no changes requested')
        return
    # Revalidate after prompts in case another recovery completed during interaction.
    if not preflight(home, engine, backup, runner, output):
        output('[blocked] preflight changed before restoration')
        return
    output('[authorized] invoking hardened recovery engine...')
    result = run_engine(engine, [
        'restore', '--production', '--archive', str(backup),
        '--confirm', 'RESTORE', '--enable-production'
    ], runner)
    if result.returncode:
        output('[blocked] restore failed or interrupted; inspect recovery status before retrying')
    else:
        output('[completed] recovery engine finished; inspect launcher and retained rollback')


def main():
    home = Path.home()
    engine = Path(__file__).resolve().parent / 'production_recovery.py'
    while True:
        print('\n  production recovery (guarded)')
        print('  [1] list backups')
        print('  [2] dry-run selected backup')
        print('  [3] recovery journal status')
        print('  [4] restore launcher (requires 3 confirmations)')
        print('  [0] back')
        try:
            choice = input('choose: ').strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if choice == '0':
            return 0
        if choice == '1':
            for path in verified_backup_paths(home):
                print(' ', path)
        elif choice == '2':
            b = choose_backup(home)
            if b:
                preflight(home, engine, b)
        elif choice == '3':
            recovery_status(home)
        elif choice == '4':
            restore(home, engine)
        else:
            print('invalid option')

if __name__ == '__main__':
    raise SystemExit(main())
