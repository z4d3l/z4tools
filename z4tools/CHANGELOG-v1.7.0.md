# z4tools v1.7.0 — changelog

## added
- advanced backup manager: create, list, inspect and verify archives
- configuration snapshots with sensitive-value redaction and comparison
- backup comparison for both `.zip` and `.tar.gz`, including content-hash differences
- guarded recovery workflow with integrity checks, explicit multi-step confirmation, exclusive locking, retained rollback directories, and interruption journals
- configuration editor with change previews, typed values, history copies, and protected-path checks
- read-only operation previews for apps, configuration, backups and launcher recovery
- first-run setup wizard with dependency checks, preview and completion marker

## improved
- debian/termux platform defaults for deployment directories
- portable configuration editor and setup wizard paths
- crimson menu integration for all seven features
- prevention of automatically importing an older installation's settings

## verification
- termux development and real-backup disposable recovery tests passed
- debian 13 proot functional regression tests passed for all seven features
- packaged debian 13 proot tests passed using an isolated installation
- release package checked for path traversal, duplicate entries, symlinks, manifest consistency, and private configuration files

## limits
- native debian/ubuntu remain incompletely tested
- real production launcher restoration was not exercised during the tests
- proot-distro uses android's kernel and does not guarantee native linux behavior
