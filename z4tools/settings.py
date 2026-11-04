#!/usr/bin/env python3
"""Shared z4tools settings, stored beside the scripts."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / 'settings.json'
# Termux uses Android shared storage; Linux defaults to a user-owned folder.
import os
IS_TERMUX = 'com.termux' in str(Path(__import__('sys').executable).resolve())
DEFAULT_DEPLOYMENT = (Path.home() / 'storage' / 'downloads' / 'app_deployment'
                      if IS_TERMUX else Path.home() / 'Downloads' / 'app_deployment')


def get_deployment_dir():
    try:
        data = json.loads(CONFIG.read_text(encoding='utf-8'))
        raw = data.get('app_deployment_directory')
        if isinstance(raw, str) and raw.strip():
            return Path(raw).expanduser().resolve()
    except (OSError, ValueError, TypeError):
        pass
    return DEFAULT_DEPLOYMENT


def ensure_deployment_dir():
    folder = get_deployment_dir()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def settings_menu():
    while True:
        current = get_deployment_dir()
        print('\n=== z4tools settings ===')
        print('app deployment directory:', current)
        print('1) change app deployment directory')
        print('2) reset to default')
        print('0) back')
        choice = input('choose: ').strip()
        if choice == '0':
            return
        if choice == '1':
            raw = input('new folder path (blank to cancel): ').strip()
            if not raw:
                continue
            target = Path(raw).expanduser()
            if not target.is_absolute():
                print('please enter an absolute path, such as ~/storage/downloads/my_apps')
                continue
            if input('confirm changing deployment directory? [y/N]: ').strip().lower()!='y':
                print('cancelled');continue
            try:
                target = target.resolve()
                target.mkdir(parents=True, exist_ok=True)
                CONFIG.write_text(json.dumps({'app_deployment_directory': str(target)}, indent=2) + '\n', encoding='utf-8')
                print('saved! app deployer will use:', target)
            except OSError as exc:
                print('could not create or save folder:', exc)
        elif choice == '2':
            if input('confirm resetting deployment directory? [y/N]: ').strip().lower()!='y':
                print('cancelled');continue
            try:
                DEFAULT_DEPLOYMENT.mkdir(parents=True, exist_ok=True)
                CONFIG.write_text('{}\n', encoding='utf-8')
                print('reset to:', DEFAULT_DEPLOYMENT)
            except OSError as exc:
                print('could not reset:', exc)
        else:
            print('invalid option')


if __name__ == '__main__':
    try:
        settings_menu()
    except (KeyboardInterrupt, EOFError):
        print('\nreturning to menu')
