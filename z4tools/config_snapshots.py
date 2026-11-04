#!/usr/bin/env python3
"""z4tools v1.7 configuration snapshots (safe, opt-in file selection)."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys

HOME = Path.home()
STORE = Path(os.environ.get('Z4_SNAPSHOT_DIR', str(HOME / 'z4tools-config-snapshots'))).expanduser()
LAUNCHER = Path(os.environ.get('Z4_LAUNCHER_DIR', str(HOME / 'GPUBrewLauncher'))).expanduser()
ALLOWED = ('.json', '.toml', '.ini', '.yaml', '.yml')
MAX_BYTES = 1024 * 1024
SECRET = re.compile(r'(token|password|secret|api.?key|authorization|cookie|credential|private.?key)', re.I)

def selected_files():
    # Deliberately conservative; user may opt in to additional files later.
    candidates = [
        HOME / 'z4tools' / 'text-values.json',
        HOME / 'z4tools' / 'live-theme.json',
        LAUNCHER / 'settings.json',
        LAUNCHER / 'config.json',
        LAUNCHER / 'launcher-settings.json',
    ]
    return [p for p in candidates if p.is_file() and not p.is_symlink() and p.stat().st_size <= MAX_BYTES]

def sanitize(obj):
    if isinstance(obj, dict):
        return {k: ('[redacted]' if SECRET.search(k) else sanitize(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    return obj

def load_configs():
    output = {}
    for p in selected_files():
        try:
            content = json.loads(p.read_text(encoding='utf-8'))
            output[p.name] = sanitize(content)
        except (ValueError, OSError, UnicodeError) as e:
            print(f'[skip] {p.name}: cannot safely parse json ({type(e).__name__})', file=sys.stderr)
    return output

def snapshot_path(name):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,48}', name):
        raise ValueError('name must contain only letters, numbers, underscores or hyphens (max 48)')
    return STORE / (name + '.json')

def create(name):
    configs = load_configs()
    if not configs:
        print('[info] no supported launcher json configuration files found; nothing saved')
        return 1
    STORE.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = snapshot_path(name)
    data = {'format': 'z4tools-config-snapshot-v1', 'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': configs}
    payload = json.dumps(data, indent=2, sort_keys=True) + '\n'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print('[error] snapshot exists; refusing to overwrite')
        return 1
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(payload)
    print('[saved]', path, f'({len(configs)} config files)')
    return 0

def listing():
    if not STORE.is_dir():
        print('[info] no snapshots yet')
        return
    paths = sorted(STORE.glob('*.json'))
    if not paths:
        print('[info] no snapshots yet')
    for p in paths:
        if p.is_file() and not p.is_symlink():
            print(p.stem, f'({p.stat().st_size} bytes)')

def read(name):
    p = snapshot_path(name)
    if not p.is_file() or p.is_symlink():
        raise ValueError('snapshot not found')
    data = json.loads(p.read_text(encoding='utf-8'))
    if data.get('format') != 'z4tools-config-snapshot-v1' or not isinstance(data.get('files'), dict):
        raise ValueError('invalid snapshot format')
    return data

def inspect(name):
    data = read(name)
    print('snapshot:', name)
    print('created:', data.get('created_utc', 'unknown'))
    for fname, content in data['files'].items():
        digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:12]
        print(' ', fname, 'sha256:', digest)

def compare(a, b):
    aa, bb = read(a)['files'], read(b)['files']
    changed = False
    for key in sorted(set(aa) | set(bb)):
        if key not in aa:
            print('[added]', key); changed = True
        elif key not in bb:
            print('[removed]', key); changed = True
        elif aa[key] != bb[key]:
            print('[changed]', key); changed = True
    if not changed:
        print('[same] no differences in captured configurations')

def main():
    parser = argparse.ArgumentParser(description='z4tools safe configuration snapshots (no restore/delete)')
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('create'); p.add_argument('name')
    sub.add_parser('list')
    p = sub.add_parser('inspect'); p.add_argument('name')
    p = sub.add_parser('compare'); p.add_argument('first'); p.add_argument('second')
    args = parser.parse_args()
    try:
        if args.cmd == 'create': return create(args.name)
        if args.cmd == 'list': listing()
        if args.cmd == 'inspect': inspect(args.name)
        if args.cmd == 'compare': compare(args.first, args.second)
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print('[error]', e, file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
