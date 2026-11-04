z4tools v1.7.0
================

z4tools is a terminal toolkit for GPUBrewLauncher with a crimson menu.

supported/tested environments
-----------------------------
- termux on android: the seven v1.7 features were tested in development.
- debian 13 (trixie) under termux proot-distro: all seven v1.7 features passed functional tests on a disposable installation.
- native debian/ubuntu has not been fully tested; filesystem and dependency behavior may differ.

installation
------------
1. extract this zip into a directory you own, preserving the z4tools/ folder.
2. run: bash z4tools/z4tools.sh
3. use the first-run setup wizard (main menu option 7) to check settings.
4. confirm required external build/deployment tools are available for the functions you plan to use.

new in v1.7.0
-------------
1. advanced backup manager
2. configuration snapshots
3. backup comparison for .zip and .tar.gz archives (read-only)
4. guarded backup recovery with archive verification, rollback retention, locking and manual interruption handling
5. configuration editor with private history
6. read-only operation previews
7. first-run setup wizard

safety
------
- backup recovery can replace the entire ~/GPUBrewLauncher directory if explicitly authorized.
- do not select production restore for routine testing. verify the archive, launcher path and backup location before confirming.
- close GPUBrewLauncher before any real restore. keep separate verified backups.
- real production restoration has not been exercised in the reported regression tests; disposable restores have been tested.
- previews do not execute operations, and some previews are estimates rather than complete integrity checks.
- no personal settings, launcher data or backup archives are included in this distribution.

comparison usage
----------------
python3 z4tools/backup_compare.py --help
--mode two | --mode custom --count N | --mode all

repository: https://github.com/z4d3l/z4tools
