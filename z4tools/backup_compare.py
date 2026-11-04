#!/usr/bin/env python3
"""Read-only multi-backup ZIP and tar.gz comparator for z4tools."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tarfile
import sys
import zipfile

DEFAULT_DIR = Path.home() / 'gpubrew-backups'
MAX_ARCHIVES = 100
MAX_MEMBERS = 100000
MAX_MEMBER_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024


def archives(folder):
    if not folder.is_dir():
        return []
    return sorted((p for p in folder.iterdir() if p.is_file() and not p.is_symlink() and (p.name.lower().endswith('.tar.gz') or p.suffix.lower() == '.zip')), key=lambda p: p.name)


def safe_name(name):
    if not name or name.startswith('/') or '\\' in name or '\x00' in name:
        return False
    parts = name.split('/')
    return not any(part in ('', '.', '..') for part in parts if part != parts[-1] or not name.endswith('/')) and not name.startswith('//')


def digest_zip(path):
    result = {}
    total = 0
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError('too many archive entries')
        seen = set()
        for info in infos:
            name = info.filename
            if not safe_name(name):
                raise ValueError('unsafe entry name')
            mode = (info.external_attr >> 16) & 0xffff
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFDIR, stat.S_IFREG)):
                raise ValueError('links and special entries are unsupported')
            normalized = name.rstrip('/')
            if normalized in seen:
                raise ValueError('duplicate entry name')
            seen.add(normalized)
            if info.is_dir():
                continue
            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError('entry exceeds size limit')
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError('archive exceeds uncompressed size limit')
            h = hashlib.sha256()
            read = 0
            with z.open(info) as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    read += len(chunk)
                    if read > MAX_MEMBER_BYTES:
                        raise ValueError('entry exceeded size limit while reading')
                    h.update(chunk)
            result[name] = h.hexdigest()
    return result


def digest_tar(path):
    """Stream regular files, reject links/special entries and ambiguous paths."""
    result = {}
    seen = set()
    total = 0
    members = 0
    with tarfile.open(path, mode='r:gz') as tf:
        for entry in tf:
            members += 1
            if members > MAX_MEMBERS:
                raise ValueError('too many archive entries')
            name = entry.name
            # POSIX tar often has a harmless leading './' for GNU tar-created
            # archives; normalize it without ever accepting traversal.
            while name.startswith('./'):
                name = name[2:]
            if not name or not safe_name(name):
                raise ValueError('unsafe entry name')
            normalized = name.rstrip('/')
            if normalized in seen:
                raise ValueError('duplicate entry name')
            seen.add(normalized)
            if entry.isdir():
                continue
            if not entry.isfile():
                raise ValueError('links and special entries are unsupported')
            if entry.size < 0 or entry.size > MAX_MEMBER_BYTES:
                raise ValueError('entry exceeds size limit')
            total += entry.size
            if total > MAX_TOTAL_BYTES:
                raise ValueError('archive exceeds uncompressed size limit')
            stream = tf.extractfile(entry)
            if stream is None:
                raise ValueError('could not read tar entry')
            h = hashlib.sha256()
            size = 0
            with stream:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_MEMBER_BYTES or size > entry.size:
                        raise ValueError('entry exceeded declared size')
                    h.update(chunk)
            if size != entry.size:
                raise ValueError('truncated tar entry')
            result[name] = h.hexdigest()
    return result


def digest_archive(path):
    if path.name.lower().endswith('.tar.gz'):
        return digest_tar(path)
    if path.suffix.lower() == '.zip':
        return digest_zip(path)
    raise ValueError('unsupported archive type (expected .zip or .tar.gz)')


def compare(a, b):
    ak, bk = set(a), set(b)
    return {'added': sorted(bk - ak), 'removed': sorted(ak - bk), 'modified': sorted(k for k in ak & bk if a[k] != b[k])}


def choose(paths, mode, count):
    if len(paths) < 2:
        raise ValueError('at least two .zip or .tar.gz backups are required')
    print('\navailable backups (.zip and .tar.gz):')
    for i, p in enumerate(paths, 1):
        print(f'  [{i}] {p.name}')
    if mode == 'all':
        selected = paths
    else:
        n = 2 if mode == 'two' else count
        if n is None or n < 2 or n > len(paths):
            raise ValueError(f'choose between 2 and {len(paths)} backups')
        raw = input(f'enter {n} backup numbers, comma-separated: ').strip()
        try:
            ids = [int(x.strip()) for x in raw.split(',')]
        except ValueError:
            raise ValueError('invalid selection')
        if len(ids) != n or len(set(ids)) != n or any(i < 1 or i > len(paths) for i in ids):
            raise ValueError('selection must have distinct valid backup numbers')
        selected = [paths[i - 1] for i in ids]
    if len(selected) > MAX_ARCHIVES:
        raise ValueError(f'maximum {MAX_ARCHIVES} archives per comparison')
    return selected


def run(folder, mode, count, report):
    paths = archives(folder)
    selected = choose(paths, mode, count)
    print('\nreading backups (read-only)...')
    snapshots = []
    for p in selected:
        try:
            files = digest_archive(p)
        except (OSError, ValueError, zipfile.BadZipFile, tarfile.TarError, RuntimeError, EOFError, UnicodeError) as e:
            raise ValueError(f'{p.name}: {e}')
        snapshots.append(files)
        print(f'  {p.name}: {len(files)} files')
    comparisons = []
    for i in range(1, len(selected)):
        delta = compare(snapshots[i-1], snapshots[i])
        item = {'from': selected[i-1].name, 'to': selected[i].name, **delta}
        comparisons.append(item)
        print(f'\n{item["from"]} -> {item["to"]}')
        print(f'  added: {len(delta["added"])} | removed: {len(delta["removed"])} | modified: {len(delta["modified"])}')
        for kind in ('added', 'removed', 'modified'):
            for name in delta[kind][:15]:
                print(f'    {kind}: {name}')
            if len(delta[kind]) > 15:
                print(f'    ... {len(delta[kind])-15} more {kind}')
    if len(selected) > 2:
        common = set.intersection(*(set(x) for x in snapshots))
        union = set.union(*(set(x) for x in snapshots))
        variable = sorted(name for name in union if len({snap.get(name) for snap in snapshots}) > 1)
        print(f'\nacross all selected: {len(common)} paths present in every backup; {len(variable)} paths vary')
    if report:
        target = Path(report).expanduser()
        if target.is_symlink():
            raise ValueError('report path cannot be a symlink')
        data = {'format': 'z4tools-backup-comparison-v1', 'backups': [p.name for p in selected], 'comparisons': comparisons}
        with target.open('x', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            f.write('\n')
        print(f'\nreport saved: {target}')
    return 0


def main():
    parser = argparse.ArgumentParser(description='read-only comparison of ZIP and tar.gz backup contents')
    parser.add_argument('--directory', default=str(DEFAULT_DIR), help='backup directory')
    parser.add_argument('--mode', choices=('two', 'custom', 'all'), default='two')
    parser.add_argument('--count', type=int, help='number for custom mode')
    parser.add_argument('--report', help='optional new JSON report path (never overwrites)')
    args = parser.parse_args()
    try:
        return run(Path(args.directory).expanduser(), args.mode, args.count, args.report)
    except (ValueError, OSError, EOFError, KeyboardInterrupt) as e:
        print(f'\n[error] {e}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
