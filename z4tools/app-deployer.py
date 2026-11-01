#!/usr/bin/env python3
"""Deploy app ZIPs from Android Downloads/app_deployment into GPUBrewLauncher/apps."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from settings import ensure_deployment_dir

HERE = Path(__file__).resolve().parent
ROOT = Path.home() / 'GPUBrewLauncher'
APPS = ROOT / 'apps'

BACKUPS = ROOT / 'app_deployment_backups'  # Same filesystem as apps/ for atomic renames

MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_FILES = 1000


def prompt(question: str) -> bool:
    return input(question + ' [y/N]: ').strip().lower() in ('y', 'yes')


def validate_zip(z: zipfile.ZipFile) -> None:
    infos = z.infolist()
    if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
        raise ValueError('zip exceeds safety limits (100 mb / 1000 entries)')
    for item in infos:
        name = item.filename.replace('\\', '/')
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or not p.parts or ':' in p.parts[0]:
            raise ValueError('unsafe zip path: ' + item.filename)
        # Reject symlinks (ZIP unix file mode).
        if ((item.external_attr >> 16) & 0o170000) == 0o120000:
            raise ValueError('symlinks are not allowed: ' + item.filename)


def locate_apps(extracted: Path) -> list[Path]:
    # Common formats: apps/name/, name/, or wrapper/apps/name/.
    found = []
    for manifest in extracted.rglob('app.json'):
        folder = manifest.parent
        if not (folder / 'build.cjs').is_file():
            continue
        if len(folder.relative_to(extracted).parts) > 4:
            continue
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError):
            continue
        if not isinstance(data, dict):
            continue
        if folder.name in ('.', '..') or folder.name.startswith('.'):
            continue
        found.append(folder)
    # Do not install nested app projects twice.
    return [f for f in found if not any(other != f and other in f.parents for other in found)]


def install_one(source: Path) -> None:
    name = source.name
    dest = APPS / name
    BACKUPS.mkdir(parents=True, exist_ok=True)
    backup = BACKUPS / name
    if backup.exists():
        n = 2
        while (BACKUPS / f'{name}-{n}').exists():
            n += 1
        backup = BACKUPS / f'{name}-{n}'
    staging = APPS / ('.deploy-' + name)
    if staging.exists():
        raise RuntimeError('staging folder already exists: ' + str(staging))
    if dest.exists():
        if not prompt(f'  {name} already exists. overwrite installed app with this version?'):
            print('  skipped:', name)
            return False
    shutil.copytree(source, staging)  # Copies from extracted download into Termux storage
    had_previous = dest.exists()
    if had_previous:
        if not dest.is_dir() or dest.is_symlink():
            shutil.rmtree(staging)
            raise RuntimeError('existing destination is not a normal directory: ' + str(dest))
        try:
            dest.rename(backup)
        except Exception:
            shutil.rmtree(staging)
            raise
    try:
        staging.rename(dest)
    except Exception:
        if had_previous and backup.exists():
            backup.rename(dest)
        if staging.exists():
            shutil.rmtree(staging)
        raise
    print(f'  installed: apps/{name}' + (' (replaced previous version)' if had_previous else ''))
    if prompt(f'  build {name} now?'):
        try:
            result = subprocess.run(['node', str(dest / 'build.cjs')], cwd=ROOT, check=False)
        except FileNotFoundError:
            print('  node not found. install node.js and build later.')
            result = None
        if result is None or result.returncode != 0:
            print('  build failed. source is still installed.')
            if had_previous and prompt('  restore previous app version?'):
                shutil.rmtree(dest)
                backup.rename(dest)
                print('  previous version restored.')
                return True
        else:
            print('  build successful! refresh gpubrewlauncher.')
    else:
        print(f'  skipped build. later: node apps/{name}/build.cjs')
    if had_previous:
        print('  previous version backed up at:', backup)
    return True


def main() -> int:
    if not (ROOT / 'sdk').is_dir():
        print('error: GPUBrewLauncher not found at', ROOT, '(expected sdk/ and apps/).')
        return 1
    APPS.mkdir(exist_ok=True)
    try:
        downloads = ensure_deployment_dir()
    except OSError as exc:
        print('cannot create deployment directory:', exc)
        return 1
    done = downloads / 'deployed_zips'
    print('deployment directory:', downloads)
    zips = sorted(downloads.glob('*.zip'))
    if not zips:
        print('no zip files found. place app zips in:', downloads)
        return 0
    if not prompt(f"deploy {len(zips)} zip archive(s) into gpubrew?"):
        print("cancelled");return 0
    from extras import point
    if not point():return 1
    done.mkdir(exist_ok=True)
    for archive in zips:
        print('\n===', archive.name, '===')
        try:
            with tempfile.TemporaryDirectory(prefix='gpubrew-deploy-') as temp:
                temp_path = Path(temp)
                with zipfile.ZipFile(archive) as z:
                    validate_zip(z)
                    z.extractall(temp_path)
                apps = locate_apps(temp_path)
                if not apps:
                    print('  no app folder containing app.json + build.cjs found. zip left untouched.')
                    continue
                print('  detected:', ', '.join(a.name for a in apps))
                installed_all = True
                for source in apps:
                    if install_one(source) is False:
                        installed_all = False
                if not installed_all:
                    print('  zip kept in downloads because at least one app was skipped.')
                    continue
            target = done / archive.name
            if target.exists():
                print('  zip already exists in deployed_zips; leaving original in downloads.')
            else:
                shutil.move(str(archive), str(target))
                print('  zip moved to deployed_zips/')
        except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
            print('  ERROR:', exc)
            print('  zip kept for retry.')
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print('\ninterrupted.')
        sys.exit(130)
