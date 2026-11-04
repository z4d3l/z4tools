#!/usr/bin/env python3
"""z4tools isolated recovery test engine. Refuses real launcher targets."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import uuid

MAX_FILES = 20000
MAX_BYTES = 4 * 1024**3
MAX_SINGLE = 1024**3


def validate(archive):
    if archive.is_symlink() or not archive.is_file() or not archive.name.endswith(('.tar.gz', '.tgz')):
        raise ValueError('expected a regular .tar.gz archive')
    seen = set()
    total = 0
    count = 0
    has_launcher = False
    with tarfile.open(archive, 'r:gz') as tf:
        for m in tf:
            parts = m.name.rstrip('/').split('/')
            if (not m.name or m.name.startswith('/') or '\\' in m.name or '\x00' in m.name
                    or any(p in ('', '.', '..') for p in parts) or parts[0] != 'GPUBrewLauncher'):
                raise ValueError('unsafe archive path')
            name = '/'.join(parts)
            if name in seen:
                raise ValueError('duplicate archive entry')
            seen.add(name)
            if not (m.isfile() or m.isdir()):
                raise ValueError('links and special archive entries are forbidden')
            if m.isfile():
                count += 1
                total += m.size
                if m.size < 0 or m.size > MAX_SINGLE or total > MAX_BYTES:
                    raise ValueError('archive size limit exceeded')
                if name.startswith('GPUBrewLauncher/homebrew-launcher/'):
                    has_launcher = True
            if len(seen) > MAX_FILES:
                raise ValueError('archive entry limit exceeded')
    if not has_launcher:
        raise ValueError('missing launcher contents')
    return count, total


def restore_test(archive, target, fail_after_swap=False):
    target = target.expanduser().resolve(strict=False)
    real = (Path.home() / 'GPUBrewLauncher').resolve(strict=False)
    if target == real or target == Path.home().resolve() or real in target.parents or target in real.parents:
        raise ValueError('refusing real launcher or overlapping directory')
    if target.name != 'GPUBrewLauncher':
        raise ValueError('test target must be named GPUBrewLauncher')
    if target.is_symlink() or not target.is_dir() or not (target / 'homebrew-launcher').is_dir():
        raise ValueError('test launcher directory missing')
    # Restrict all test operations to a fresh temporary directory, never user-controlled existing trees.
    parent = target.parent
    if not (parent / '.z4-recovery-test-sandbox').is_file():
        raise ValueError('test sandbox marker missing')
    count, total = validate(archive)
    print(f'[validated] {count} files, {total} bytes', flush=True)
    stage = Path(tempfile.mkdtemp(prefix='.z4-stage-', dir=parent))
    rollback = parent / ('.z4-rollback-' + uuid.uuid4().hex)
    moved = False
    try:
        with tarfile.open(archive, 'r:gz') as tf:
            for m in tf:
                parts = m.name.rstrip('/').split('/')
                if (not m.name or m.name.startswith('/') or '\\' in m.name or '\x00' in m.name
                        or any(p in ('', '.', '..') for p in parts) or parts[0] != 'GPUBrewLauncher'
                        or not (m.isfile() or m.isdir())):
                    raise ValueError('unsafe archive entry during extraction')
                dest = stage.joinpath(*parts)
                if m.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    src = tf.extractfile(m)
                    if src is None:
                        raise ValueError('unreadable archive file')
                    with src, dest.open('xb') as out:
                        copied = shutil.copyfileobj(src, out, length=1024*1024)
                    if dest.stat().st_size != m.size:
                        raise ValueError('file size mismatch')
        staged = stage / 'GPUBrewLauncher'
        if not (staged / 'homebrew-launcher').is_dir():
            raise ValueError('staged launcher missing')
        print('[staged] extraction completed', flush=True)
        target.rename(rollback)
        moved = True
        if fail_after_swap:
            raise RuntimeError('simulated failure after original moved')
        staged.rename(target)
        print('[restored] test launcher replaced', flush=True)
        print('[rollback preserved]', rollback, flush=True)
        return rollback
    except BaseException:
        if moved and not target.exists() and rollback.exists():
            rollback.rename(target)
            print('[rollback] original test launcher restored', flush=True)
        raise
    finally:
        shutil.rmtree(stage)


def main():
    p = argparse.ArgumentParser(description='isolated staged recovery test only; real launcher blocked')
    p.add_argument('archive', type=Path)
    p.add_argument('--test-target', required=True, type=Path)
    p.add_argument('--simulate-failure', action='store_true')
    args = p.parse_args()
    try:
        restore_test(args.archive, args.test_target, args.simulate_failure)
    except (ValueError, OSError, RuntimeError, tarfile.TarError) as e:
        print('[blocked/error]', str(e), file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())
