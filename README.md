# z4tools

**an unofficial terminal toolkit for customizing and managing [gpubrewlauncher](https://github.com/NiftyNova/GPUBrewLauncher).**

z4tools is a menu-driven toolkit for launcher themes, app deployment, backups, maintenance, and development workflows. **v1.5.3 rc1** provides downloadable packages for android termux and debian/ubuntu.

> **prerelease:** the debian launcher menu, custom hex accent hot reload, text hot reload, and backup/restore workflows have been tested with an existing modified launcher. fresh installation on an unpatched launcher and independent termux package testing remain unverified. back up your launcher before applying patches.

## download

**[download v1.5.3 rc1](https://github.com/z4d3l/z4tools/releases/tag/v1.5.3-rc1)**

release assets:
- `z4tools-v1.5.3-termux-rc1.zip` — android termux
- `z4tools-v1.5.3-debian-ubuntu-rc1.zip` — debian/ubuntu
- `SHA256SUMS.txt` — integrity checksums

both zip files currently contain the **same portable source**, packaged separately for convenience. they are not independently optimized platform builds.

## features

| tool | what it does |
| --- | --- |
| theme maker + advanced editor | customize launcher theme colors and related assets |
| live themes / accent switching | change supported accents, including custom `#RRGGBB` colors, while a compatible launcher is running |
| theme restoration | save supported accent choices for later sessions |
| app deployer + manager | deploy app archives and manage installed apps |
| backups | create, list, and safely restore backups to a **new directory** without overwriting an existing launcher |
| launcher utilities | run build, maintenance, and diagnostic workflows |
| logs + startup timer | inspect launcher diagnostics and timing |
| app template generator | create starter files for gpubrew apps |
| watermark utilities | manage supported watermark changes |
| text editor + hot reload | edit launcher text and request supported live updates |
| accent patch manager | inspect and install supported accent patches |
| compatibility checker | report missing or incompatible files and dependencies |

some features require patches to gpubrewlauncher. live reload is not guaranteed on every upstream revision, and a successful compatibility check does not guarantee functionality.

## requirements

- android termux **or** a debian/ubuntu environment
- bash, python 3.10+, node.js 22+, and git
- `glslangValidator` and `spirv-val` for relevant launcher/build workflows
- an existing compatible [gpubrewlauncher](https://github.com/NiftyNova/GPUBrewLauncher) installation
- storage permissions as needed for shared downloads on android

## installation

1. install and configure gpubrewlauncher first.
2. download the matching zip from [releases](https://github.com/z4d3l/z4tools/releases/tag/v1.5.3-rc1).
3. extract the archive, keeping `z4tools/` and `z4-accent-live/` next to each other.
4. open a terminal in the extracted release directory and run:

```bash
bash z4tools/z4tools.sh
```

if your launcher is not at `~/GPUBrewLauncher`, specify its location first:

```bash
export Z4TOOLS_LAUNCHER_DIR="/path/to/GPUBrewLauncher"
bash z4tools/z4tools.sh
```

**do not assume this installs all required patches onto a clean, unmodified launcher.** some patch installers have not yet been verified as self-contained. avoid applying patches while the launcher is running.

for additional notes, see [installation documentation](docs/INSTALL.md).

## verify downloads

in the directory containing both zip files and `SHA256SUMS.txt`:

```bash
sha256sum -c SHA256SUMS.txt
```

if you downloaded only one zip, compare its `sha256sum` output against the matching entry in `SHA256SUMS.txt`.

## repository layout

```text
z4tools/
├── README.md
├── docs/
│   └── INSTALL.md
├── z4tools/
│   ├── z4tools.sh
│   ├── platform_runtime.py
│   ├── live_themes.py
│   ├── backup.sh
│   ├── compatibility_check.py
│   └── ...other toolkit modules
└── z4-accent-live/
    ├── z4_accent.py
    └── launcher.frag
```

## compatibility and limitations

- **debian/ubuntu:** tested against an existing customized launcher in a debian environment; fresh-host installation not yet verified.
- **android termux:** supported target, but the rc1 zip has not been independently validated as a fresh installation.
- **other linux distributions, wsl, and macos:** not verified end-to-end.
- **native windows terminal:** not a tested target.
- **backup restore:** extracts to a new, nonexistent destination directory; it does not replace your active installation or automatically switch to the restored copy.
- upstream launcher changes may break patches or hot reload.

## privacy and security

this repository is intended to contain source code, not personal runtime data. keep settings, logs, credentials, temporary files, and backup snapshots on your device. review `git status` before committing.

never publish github tokens, passwords, private keys, personal configuration, or launcher backups. revoke any credentials accidentally exposed.

## version and credits

**v1.5.3 rc1 — prerelease**

this community-made toolkit is independent of and not endorsed by the gpubrewlauncher developers.

**upstream:** [niftynova/gpubrewlauncher](https://github.com/NiftyNova/GPUBrewLauncher)

**license:** not yet selected. until a license is added, no open-source license grant is implied.
