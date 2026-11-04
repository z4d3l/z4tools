# z4tools v1.7.0 — release notes

this release adds seven major capabilities to z4tools and expands test coverage to debian 13 under proot-distro.

### highlights
- backups: management, snapshots, `.zip`/`.tar.gz` comparisons and guarded restoration
- settings: configuration editing and first-run wizard
- transparency: read-only operation previews
- portability: improved defaults for termux and linux installation directories

### installation
unzip `z4tools-v1.7.0.zip`, then run `bash z4tools/z4tools.sh` from the parent directory (or `bash z4tools.sh` from inside the extracted folder).

### recovery warning
production restore is a destructive operation requiring multiple deliberate confirmations. it can replace the entire existing `~/GPUBrewLauncher` tree. the prior launcher is designed to be retained in a rollback directory, but no crash-recovery scheme is guaranteed for every filesystem fault. close the launcher and keep independent verified backups before restoring. live restoration is not included in the reported test coverage.

### compatibility
- tested: termux on android; debian 13 trixie in termux proot-distro
- not fully validated: native debian and ubuntu; other linux distributions
- some launcher build/deployment features depend on external tools and environment setup

### integrity
verify the downloaded zip against the sha-256 checksum distributed alongside this release.
