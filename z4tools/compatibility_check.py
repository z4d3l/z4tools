#!/usr/bin/env python3
"""z4tools v1.6 advanced, read-only compatibility diagnostics.

Does not execute launcher code, compile shaders, or alter launcher files.
"""
import argparse
import ast
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
Z4 = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('Z4TOOLS_LAUNCHER_DIR', str(HOME / 'GPUBrewLauncher'))).expanduser()
RUNTIME = ROOT / 'homebrew-launcher'
CHECKS = []


def add(name, status, detail, fix=None, category='general'):
    CHECKS.append({'name': name, 'status': status, 'detail': str(detail),
                   'suggestion': fix, 'category': category})


def run(args, timeout=8, cwd=None):
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout, cwd=cwd, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return exc


def command_check(name, minimum=None, required=True):
    executable = shutil.which(name)
    if not executable:
        add(name, 'warning' if required else 'unverified', 'not found on path',
            'install this dependency for features that require it', 'dependencies')
        return
    if minimum is None:
        add(name, 'pass', executable, category='dependencies')
        return
    result = run([executable, '--version'])
    if isinstance(result, Exception) or result.returncode != 0:
        add(name, 'unverified', 'version command failed', category='dependencies')
        return
    output = (result.stdout or result.stderr).strip().splitlines()
    version = output[0] if output else ''
    match = re.search(r'v?(\d+)(?:\.\d+)*', version)
    if not match:
        add(name, 'unverified', f'could not parse version: {version[:100]}', category='dependencies')
    elif int(match.group(1)) < minimum:
        add(name, 'warning', f'{version}; requires major version {minimum}+',
            'update this dependency', 'dependencies')
    else:
        add(name, 'pass', version, category='dependencies')


def file_check(name, path, required=True):
    if not path.is_file():
        add(name, 'failed' if required else 'unverified', f'missing: {path}',
            'check the launcher installation and expected file layout', 'files')
        return False
    try:
        with path.open('rb') as stream:
            stream.read(1)
    except OSError as exc:
        add(name, 'failed', f'not readable: {exc}', 'check file permissions', 'files')
        return False
    add(name, 'pass', 'present and readable', category='files')
    return True


def directory_check(name, path, required=True):
    if path.is_dir():
        add(name, 'pass', str(path), category='files')
        return True
    add(name, 'failed' if required else 'unverified', f'missing directory: {path}',
        'verify your installation location', 'files')
    return False


def syntax_check(path, language, name):
    if not path.is_file():
        add(name, 'unverified', 'source file missing', category='syntax')
        return
    if language == 'python':
        try:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            add(name, 'pass', 'valid python syntax', category='syntax')
        except (SyntaxError, UnicodeError, OSError) as exc:
            add(name, 'failed', str(exc)[:200], 'inspect source file', 'syntax')
    else:
        node = shutil.which('node')
        if not node:
            add(name, 'unverified', 'node unavailable', category='syntax')
            return
        result = run([node, '--check', str(path)], timeout=15)
        if isinstance(result, Exception):
            add(name, 'unverified', str(result)[:150], category='syntax')
        elif result.returncode == 0:
            add(name, 'pass', 'valid javascript syntax', category='syntax')
        else:
            lines = (result.stderr or result.stdout).strip().splitlines()
            add(name, 'failed', (lines[-1] if lines else 'syntax error')[:200],
                'inspect javascript syntax', 'syntax')


def marker_check(name, path, markers):
    if not path.is_file():
        add(name, 'unverified', 'file missing', category='patches')
        return
    try:
        contents = path.read_text(encoding='utf-8', errors='replace')
        found = any(marker in contents for marker in markers)
    except OSError:
        add(name, 'unverified', 'could not read file', category='patches')
        return
    add(name, 'pass' if found else 'unverified',
        'marker found (functionality not proven)' if found else 'marker not found',
        category='patches')


def git_check():
    if not ROOT.is_dir() or not shutil.which('git'):
        add('launcher git status', 'unverified', 'launcher directory or git missing', category='git')
        return
    result = run(['git', '-C', str(ROOT), 'status', '--porcelain=v1', '--untracked-files=normal'], timeout=20)
    if isinstance(result, Exception) or result.returncode != 0:
        add('launcher git status', 'unverified', 'not a usable git working tree', category='git')
        return
    entries = result.stdout.splitlines()
    tracked = sum(not line.startswith('??') for line in entries)
    untracked = sum(line.startswith('??') for line in entries)
    detail = f'{tracked} tracked changes, {untracked} untracked entries' if entries else 'clean working tree'
    add('launcher git status', 'pass', detail + ' (informational)', category='git')


def saved_theme_check():
    path = Z4 / 'live-theme.json'
    if not path.is_file():
        add('saved accent', 'unverified', 'no saved accent configuration', category='configuration')
        return
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        value = obj.get('hex') if isinstance(obj, dict) else None
        if isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            add('saved accent', 'pass', 'valid hex accent', category='configuration')
        else:
            add('saved accent', 'warning', 'invalid accent color',
                'save a valid #rrggbb accent', 'configuration')
    except (OSError, ValueError) as exc:
        add('saved accent', 'warning', str(exc)[:160], category='configuration')


def environment_check():
    is_termux = 'com.termux' in str(HOME) or bool(os.environ.get('TERMUX_VERSION'))
    system = platform.system().lower()
    if is_termux:
        add('platform', 'pass', 'android termux detected', category='environment')
    elif system == 'linux':
        os_release = Path('/etc/os-release')
        info = ''
        if os_release.is_file():
            try:
                info = os_release.read_text(errors='replace')
            except OSError:
                pass
        supported = any(s in info.lower() for s in ('debian', 'ubuntu'))
        add('platform', 'pass' if supported else 'unverified',
            'debian/ubuntu-family linux' if supported else 'linux (distribution unverified)',
            category='environment')
    else:
        add('platform', 'unverified', f'{platform.system()} not tested', category='environment')
    add('python', 'pass' if sys.version_info >= (3, 10) else 'warning',
        sys.version.split()[0], 'python 3.10+ required' if sys.version_info < (3, 10) else None,
        'dependencies')


def perform_checks():
    environment_check()
    command_check('node', minimum=22)
    command_check('git')
    command_check('glslangValidator')
    command_check('spirv-val')
    directory_check('launcher root', ROOT)
    directory_check('launcher runtime folder', RUNTIME)
    directory_check('launcher shader folder', RUNTIME / 'shaders')
    file_check('launcher runtime', RUNTIME / 'launcher-loop.cjs')
    file_check('z4tools main menu', Z4 / 'z4tools.sh')
    file_check('accent patch manager', Z4 / 'accent_setup.py', required=False)
    file_check('live accent controller', Z4.parent / 'z4-accent-live' / 'z4_accent.py', required=False)
    file_check('live theme switcher', Z4 / 'live_themes.py', required=False)
    file_check('launcher shader source', RUNTIME / 'shaders' / 'launcher.frag', required=False)
    file_check('launcher compiled shader', RUNTIME / 'shaders' / 'launcher.frag.spv', required=False)
    syntax_check(RUNTIME / 'launcher-loop.cjs', 'javascript', 'launcher javascript syntax')
    syntax_check(RUNTIME / 'catalog-assets.py', 'python', 'launcher python syntax')
    syntax_check(RUNTIME / 'launcher-text.py', 'python', 'launcher text python syntax')
    marker_check('live runtime marker', RUNTIME / 'launcher-loop.cjs',
                 ['z4-accent-live', 'z4tools-v1.5'])
    marker_check('startup theme restore marker', RUNTIME / 'launcher-loop.cjs',
                 ['z4tools-v1.5.05-auto-restore'])
    marker_check('clean menu patch marker', Z4 / 'z4tools.sh',
                 ['z4tools-clean-menu-v152'])
    saved_theme_check()
    git_check()


def main():
    parser = argparse.ArgumentParser(description='read-only z4tools compatibility checker')
    parser.add_argument('--json', metavar='PATH', help='save json report outside launcher')
    parser.add_argument('--no-pause', action='store_true', help='skip enter prompt')
    args = parser.parse_args()
    perform_checks()
    print('=== z4tools | advanced compatibility checker v1.6-dev ===')
    print('read-only launcher inspection; no automatic repairs\n')
    symbols = {'pass': '[ok]', 'warning': '[!!]', 'failed': '[xx]', 'unverified': '[??]'}
    for entry in CHECKS:
        print(f"{symbols[entry['status']]} {entry['name']} — {entry['detail']}")
        if entry['status'] in ('warning', 'failed') and entry['suggestion']:
            print('     suggestion:', entry['suggestion'])
    counts = {status: sum(e['status'] == status for e in CHECKS) for status in symbols}
    print('\nsummary:', ', '.join(f'{counts[k]} {k}' for k in symbols))
    print('note: syntax, file and marker checks do not prove runtime functionality.')
    if args.json:
        dest = Path(args.json).expanduser().resolve()
        # Never write diagnostics into the launcher directory.
        if dest == ROOT.resolve() or ROOT.resolve() in dest.parents:
            parser.error('json report destination must be outside launcher directory')
        payload = {'schema_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
                   'summary': counts, 'checks': CHECKS}
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
            print('json report saved:', dest)
        except OSError as exc:
            print('could not save json report:', exc, file=sys.stderr)
            return 2
    if not args.no_pause and sys.stdin.isatty():
        try:
            input('\npress enter to return to z4tools...')
        except (EOFError, KeyboardInterrupt):
            pass
    return 1 if counts['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
