#!/usr/bin/env python3
"""z4tools v1.6-dev: read-only launcher log browser (standard library only)."""
import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024
LEVELS = ('all', 'error', 'warn', 'info', 'debug')
PATTERNS = {
    'error': re.compile(r'\b(error|fatal|exception|traceback|failed|critical)\b', re.I),
    'warn': re.compile(r'\b(warn|warning)\b', re.I),
    'info': re.compile(r'\b(info|notice)\b', re.I),
    'debug': re.compile(r'\b(debug|trace)\b', re.I),
}
REDACT = [
    (re.compile(r'(?i)\b(authorization\s*:\s*bearer\s+)\S+'), r'\1[redacted]'),
    (re.compile(r'(?i)\b((?:token|password|secret|api[_-]?key)\s*[=:]\s*)\S+'), r'\1[redacted]'),
]


def root_path():
    return Path(os.environ.get('Z4TOOLS_LAUNCHER_DIR', '~/GPUBrewLauncher')).expanduser()


def discover(root):
    # Bounded search in known directories; never recursively scan user home.
    dirs = [root, root / 'homebrew-launcher', root / 'logs', root / 'homebrew-launcher' / 'logs', Path.home() / 'z4tools' / 'logs']
    found = set()
    for folder in dirs:
        if not folder.is_dir():
            continue
        try:
            for path in folder.iterdir():
                if path.is_file() and (path.suffix.lower() in ('.log', '.out') or path.name in ('nohup.out', 'launcher.log')):
                    found.add(path.resolve())
        except OSError:
            pass
    return sorted(found, key=lambda p: str(p))


def read_lines(path):
    # Tail bounded bytes, so huge logs won't exhaust phone memory.
    with path.open('rb') as fh:
        fh.seek(0, 2)
        size = fh.tell()
        start = max(0, size - MAX_BYTES)
        fh.seek(start)
        data = fh.read(MAX_BYTES)
    if start:
        data = data.split(b'\n', 1)[-1]  # discard partial first line
    return data.decode('utf-8', errors='replace').splitlines(), size > MAX_BYTES


def filtered(lines, level, query):
    result = []
    for line in lines:
        if level != 'all' and not PATTERNS[level].search(line):
            continue
        if query and query.casefold() not in line.casefold():
            continue
        result.append(line)
    return result


def redact(text):
    for pattern, replacement in REDACT:
        text = pattern.sub(replacement, text)
    return text


def display(path, level, query, limit, export=None):
    try:
        lines, truncated = read_lines(path)
    except (OSError, ValueError) as exc:
        print(f'[error] cannot read log: {exc}')
        return False
    matches = filtered(lines, level, query)
    selected = matches[-limit:]
    print(f'\nfile: {path}\nmatched: {len(matches)} | displaying: {len(selected)}' + (' | last 5 mib scanned' if truncated else ''))
    if not export:
        for line in selected:
            print(redact(line))
        if not selected:
            print('(no matching entries)')
    else:
        target = Path(export).expanduser()
        if target.resolve() == path.resolve():
            print('[error] export destination cannot overwrite source log')
            return False
        if target.exists():
            print('[error] export already exists; choose a new filename')
            return False
        try:
            # Exclusive creation prevents accidental overwrites.
            with target.open('x', encoding='utf-8') as fh:
                fh.write(f'z4tools log export | {datetime.now().isoformat(timespec="seconds")}\n')
                fh.write(f'source: {path.name} | filter: {level} | search: {query!r}\n\n')
                fh.write('\n'.join(redact(line) for line in selected) + '\n')
        except OSError as exc:
            print(f'[error] export failed: {exc}')
            return False
        print(f'[ok] exported {len(selected)} lines to {target}')
        print('note: review exports before sharing; automatic redaction is not exhaustive.')
    return True


def interactive(root):
    while True:
        files = discover(root)
        print('\n=== z4tools v1.6 | advanced log viewer ===')
        for i, path in enumerate(files, 1):
            print(f'[{i}] {path}')
        print('[p] enter a custom log path  [0] back')
        try:
            choice = input('choose: ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == '0':
            return
        if choice.lower() == 'p':
            path = Path(input('log path: ').strip()).expanduser()
        elif choice.isdigit() and 1 <= int(choice) <= len(files):
            path = files[int(choice) - 1]
        else:
            print('invalid selection')
            continue
        if not path.is_file():
            print('[error] file not found')
            continue
        level = input('severity [all/error/warn/info/debug] (all): ').strip().lower() or 'all'
        if level not in LEVELS:
            print('invalid severity')
            continue
        query = input('search text (blank for all): ').strip()
        action = input('show or export? [s/e] (s): ').strip().lower() or 's'
        if action == 'e':
            dest = input('new export filename: ').strip()
            if dest:
                display(path, level, query, 1000, dest)
        else:
            display(path, level, query, 100)
        input('\npress enter to continue...')


def main():
    parser = argparse.ArgumentParser(description='z4tools read-only log viewer')
    parser.add_argument('--file', help='log file path')
    parser.add_argument('--level', choices=LEVELS, default='all')
    parser.add_argument('--search', default='')
    parser.add_argument('--lines', type=int, default=100)
    parser.add_argument('--export', help='new export filename; never overwrites')
    parser.add_argument('--list', action='store_true', help='list detected logs')
    args = parser.parse_args()
    if args.lines < 1 or args.lines > 10000:
        parser.error('--lines must be between 1 and 10000')
    root = root_path()
    if args.list:
        files = discover(root)
        print('\n'.join(map(str, files)) if files else 'no logs automatically detected; use --file')
    elif args.file:
        path = Path(args.file).expanduser()
        if not path.is_file() or not display(path, args.level, args.search, args.lines, args.export):
            sys.exit(1)
    elif sys.stdin.isatty():
        interactive(root)
    else:
        parser.error('provide --file or --list in noninteractive mode')


if __name__ == '__main__':
    main()
