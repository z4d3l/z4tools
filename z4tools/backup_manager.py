#!/usr/bin/env python3
"""z4tools v1.7 backup manager: safe, standalone CLI."""
import argparse
import datetime as dt
import os
import pathlib
import tarfile
import tempfile

HOME = pathlib.Path.home()
DEFAULT_BACKUPS = HOME / 'gpubrew-backups'
DEFAULT_LAUNCHER = HOME / 'GPUBrewLauncher'

def archives(folder):
    return sorted(folder.glob('gpubrew-*.tar.gz')) if folder.is_dir() else []

def list_backups(folder):
    items = archives(folder)
    if not items:
        print('no backups found in', folder)
        return
    for p in items:
        print(f'{p.name}  ({p.stat().st_size:,} bytes)')

def check_archive(path, show=False):
    if not path.is_file() or path.suffix != '.gz' or not path.name.endswith('.tar.gz'):
        raise ValueError('expected an existing .tar.gz archive')
    with tarfile.open(path, 'r:gz') as tar:
        members = tar.getmembers()
        if len(members) > 200000:
            raise ValueError('archive contains too many entries')
        for m in members:
            name = pathlib.PurePosixPath(m.name)
            if name.is_absolute() or '..' in name.parts or m.issym() or m.islnk() or m.isdev() or m.isfifo():
                raise ValueError(f'unsafe archive entry: {m.name}')
            if m.isfile():
                f = tar.extractfile(m)
                if f is None:
                    raise ValueError(f'cannot read: {m.name}')
                while f.read(1024 * 1024):
                    pass
            if show:
                print(f'{m.size:>12}  {m.name}')
    print(f'pass: {len(members)} entries verified in {path.name}')

def create_backup(launcher, folder):
    if not launcher.is_dir() or launcher.is_symlink():
        raise ValueError('launcher directory missing or symlinked')
    if not (launcher / 'homebrew-launcher').exists() and not (launcher / 'apps').exists():
        raise ValueError('launcher layout not recognized; refusing backup')
    folder.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target = folder / f'gpubrew-{stamp}.tar.gz'
    fd, temp = tempfile.mkstemp(prefix='.z4tools-backup-', suffix='.tar.gz', dir=folder)
    os.close(fd)
    try:
        with tarfile.open(temp, 'w:gz', dereference=False) as tar:
            tar.add(launcher, arcname=launcher.name, recursive=True)
        check_archive(pathlib.Path(temp))
        os.replace(temp, target)
        print('created:', target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def main():
    parser = argparse.ArgumentParser(description='z4tools v1.7 safe backup manager')
    parser.add_argument('action', choices=['list', 'inspect', 'verify', 'create'])
    parser.add_argument('archive', nargs='?', type=pathlib.Path)
    parser.add_argument('--backup-dir', type=pathlib.Path, default=DEFAULT_BACKUPS)
    parser.add_argument('--launcher', type=pathlib.Path, default=DEFAULT_LAUNCHER)
    args = parser.parse_args()
    try:
        if args.action == 'list':
            list_backups(args.backup_dir)
        elif args.action in ('inspect', 'verify'):
            if args.archive is None:
                parser.error('archive path required')
            check_archive(args.archive, show=args.action == 'inspect')
        else:
            print('launcher:', args.launcher)
            print('destination:', args.backup_dir)
            if input('create a backup? type YES to confirm: ') != 'YES':
                print('cancelled')
                return
            create_backup(args.launcher, args.backup_dir)
    except (OSError, ValueError, tarfile.TarError) as exc:
        parser.exit(1, f'error: {exc}\n')

if __name__ == '__main__':
    main()
