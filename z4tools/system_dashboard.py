#!/usr/bin/env python3
"""Read-only z4tools v1.6 system dashboard."""
import argparse
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
LAUNCHER = Path(os.environ.get('Z4TOOLS_LAUNCHER_DIR', str(HOME / 'GPUBrewLauncher'))).expanduser()

def command_version(name, args=('--version',)):
    exe = shutil.which(name)
    if not exe:
        return {'available': False, 'detail': 'not found'}
    try:
        result = subprocess.run([exe, *args], capture_output=True, text=True, timeout=4)
        line = (result.stdout or result.stderr).strip().splitlines()
        return {'available': result.returncode == 0, 'detail': line[0][:150] if line else 'installed'}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'available': False, 'detail': str(exc)}

def collect():
    try:
        disk = shutil.disk_usage(HOME)
        storage = {'total_gib': round(disk.total / 1024**3, 2), 'free_gib': round(disk.free / 1024**3, 2), 'used_percent': round(100 * disk.used / disk.total, 1)}
    except OSError as exc:
        storage = {'error': str(exc)}
    runtime = LAUNCHER / 'homebrew-launcher'
    tools = {'python': {'available': True, 'detail': platform.python_version()}, 'node': command_version('node'), 'git': command_version('git'), 'bash': command_version('bash'), 'glslangValidator': command_version('glslangValidator', ('--version',)), 'spirv-val': command_version('spirv-val', ('--version',))}
    return {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'environment': 'termux' if os.environ.get('PREFIX', '').startswith('/data/data/com.termux/') else platform.system().lower(), 'platform': platform.platform(), 'architecture': platform.machine(), 'storage': storage, 'launcher': {'path': str(LAUNCHER), 'directory_exists': LAUNCHER.is_dir(), 'runtime_exists': runtime.is_dir(), 'javascript_exists': (runtime / 'index.js').is_file()}, 'dependencies': tools, 'note': 'read-only snapshot; does not verify launcher runtime or graphics rendering'}

def show(data):
    print('=== z4tools v1.6 | system dashboard ===')
    print('environment:', data['environment'], '| architecture:', data['architecture'])
    s = data['storage']
    if 'error' in s:
        print('storage: unavailable -', s['error'])
    else:
        print(f"storage: {s['free_gib']:.2f} gib free / {s['total_gib']:.2f} gib total ({s['used_percent']:.1f}% used)")
    l = data['launcher']
    print('launcher:', l['path'])
    print('launcher directory:', 'found' if l['directory_exists'] else 'missing')
    print('runtime directory:', 'found' if l['runtime_exists'] else 'missing')
    print('launcher index.js:', 'found' if l['javascript_exists'] else 'not found (layout may differ)')
    print('\ndependencies:')
    for name, result in data['dependencies'].items():
        print(f"  [{'ok' if result['available'] else '--'}] {name}: {result['detail']}")
    print('\n' + data['note'])

def main():
    parser = argparse.ArgumentParser(description='Read-only system dashboard')
    parser.add_argument('--json', metavar='PATH', help='write a json snapshot to this path')
    parser.add_argument('--no-pause', action='store_true')
    args = parser.parse_args()
    data = collect()
    show(data)
    if args.json:
        dest = Path(args.json).expanduser()
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
            print('json report:', dest)
        except OSError as exc:
            print('json export failed:', exc)
            return 1
    if not args.no_pause and os.isatty(0):
        try:
            input('\npress enter to return...')
        except EOFError:
            pass
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
