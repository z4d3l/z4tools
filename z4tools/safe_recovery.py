#!/usr/bin/env python3
"""Read-only ZIP / tar.gz recovery preview. Never extracts or restores."""
import argparse
import json
from pathlib import Path
import stat
import sys
import tarfile
import zipfile

MAX_ENTRIES = 20000
MAX_TOTAL = 4 * 1024**3
MAX_FILE = 1024**3
CHUNK = 1024 * 1024


def inspect(path):
    r = {'archive': str(path), 'status': 'blocked', 'issues': [], 'files': 0,
         'uncompressed_bytes': 0, 'entries_preview': []}
    if not path.is_file() or path.is_symlink():
        r['issues'].append('archive missing or symlink')
        return r
    is_tar = path.name.endswith(('.tar.gz', '.tgz'))
    is_zip = path.name.endswith('.zip')
    if not (is_tar or is_zip):
        r['issues'].append('unsupported archive extension')
        return r
    r['format'] = 'tar.gz' if is_tar else 'zip'
    seen = set()
    root_seen = False

    def check(name, size, kind):
        nonlocal root_seen
        parts = name.rstrip('/').split('/')
        if (not name or name.startswith('/') or '\\' in name or '\x00' in name
                or ':' in parts[0] or any(x in ('', '.', '..') for x in parts)):
            r['issues'].append('unsafe path: ' + repr(name[:120]))
            return False
        normalized = '/'.join(parts)
        if normalized in seen:
            r['issues'].append('duplicate entry: ' + normalized[:120])
        seen.add(normalized)
        if is_tar and parts[0] != 'GPUBrewLauncher':
            r['issues'].append('unexpected backup root: ' + normalized[:120])
        if is_tar and len(parts) > 1 and parts[0] == 'GPUBrewLauncher':
            root_seen = True
        if kind not in ('file', 'dir'):
            r['issues'].append('unsupported entry type: ' + normalized[:120])
        if size < 0 or size > MAX_FILE:
            r['issues'].append('oversized entry: ' + normalized[:120])
        r['uncompressed_bytes'] += size
        if r['uncompressed_bytes'] > MAX_TOTAL:
            r['issues'].append('total size exceeds 4 gib limit')
        if kind == 'file':
            r['files'] += 1
            if len(r['entries_preview']) < 25:
                r['entries_preview'].append({'path': normalized, 'bytes': size})
        if len(seen) > MAX_ENTRIES:
            r['issues'].append('too many entries')
        return True

    try:
        if is_tar:
            # streaming mode reads compressed contents and verifies gzip data without extraction.
            with tarfile.open(path, 'r|gz') as archive:
                for member in archive:
                    kind = 'file' if member.isfile() else 'dir' if member.isdir() else 'other'
                    check(member.name, member.size, kind)
                    if len(seen) > MAX_ENTRIES or r['uncompressed_bytes'] > MAX_TOTAL:
                        break
                    if kind == 'file' and member.size <= MAX_FILE:
                        stream = archive.extractfile(member)
                        if stream is None:
                            r['issues'].append('unreadable entry: ' + member.name[:120])
                        else:
                            with stream:
                                while stream.read(CHUNK):
                                    pass
            if not root_seen:
                r['issues'].append('missing GPUBrewLauncher contents')
        else:
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                for member in infos:
                    mode = member.external_attr >> 16
                    kind = 'dir' if member.is_dir() else 'file'
                    if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                        kind = 'other'
                    check(member.filename, member.file_size, kind)
                    if member.flag_bits & 1:
                        r['issues'].append('encrypted entry: ' + member.filename[:120])
                    if len(seen) > MAX_ENTRIES or r['uncompressed_bytes'] > MAX_TOTAL:
                        break
                if not r['issues']:
                    bad = archive.testzip()
                    if bad:
                        r['issues'].append('crc failure: ' + bad[:120])
    except (OSError, EOFError, ValueError, RuntimeError, tarfile.TarError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        r['issues'].append('archive inspection failed: ' + type(exc).__name__)
    if not r['issues']:
        r['status'] = 'preview_only'
    return r


def main():
    parser = argparse.ArgumentParser(description='read-only recovery preview; never restores')
    parser.add_argument('archive', help='ZIP or tar.gz backup path')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    r = inspect(Path(args.archive).expanduser())
    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print('=== z4tools safe recovery preview ===')
        print('archive:', r['archive'])
        print('format:', r.get('format', 'unknown'))
        print('status:', r['status'])
        print('files:', r['files'])
        print('uncompressed bytes:', r['uncompressed_bytes'])
        for item in r['entries_preview']:
            print(' ', item['path'], f"({item['bytes']} bytes)")
        for issue in r['issues'][:20]:
            print('[blocked]', issue)
        print('[safe] no files extracted or modified')
    return 0 if r['status'] == 'preview_only' else 2


if __name__ == '__main__':
    sys.exit(main())
