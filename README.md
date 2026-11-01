# z4tools v1.5.3

**an unofficial terminal toolkit for customizing and managing [gpubrewlauncher](https://github.com/NiftyNova/GPUBrewLauncher).**

z4tools provides a menu-driven collection of utilities for themes, app deployment, backups, launcher maintenance, and development workflows. it is primarily developed for **android termux** and an existing gpubrewlauncher installation.

> **development release:** source files are published, but a fresh installation from this repository has not been verified end-to-end. back up your launcher before changing files or applying patches.

## features

| tool | what it does |
| --- | --- |
| theme maker + advanced editor | customize launcher theme colors and related assets |
| live themes / accent switching | apply supported accent changes while the compatible launcher runtime is active |
| theme restoration | store supported theme choices for later launcher sessions |
| app deployer + manager | deploy app archives, manage installed apps, and perform related maintenance |
| backups | create, list, and restore launcher backups with confirmation prompts |
| launcher utilities | run build, maintenance, and diagnostic workflows |
| logs + startup timer | inspect launcher diagnostics and timing information |
| app template generator | create starter files for gpubrew apps |
| watermark utilities | manage supported watermark changes |
| text editor + hot reload | edit launcher text and apply supported live updates |
| accent patch manager | inspect and install supported accent hot-load patches |
| compatibility checker | report missing or incompatible files and dependencies without modifying them |

some features require modifications to the upstream launcher and a compatible shader/runtime version. **live reload is not guaranteed on every gpubrewlauncher revision.**

## requirements

- android with **termux** (primary development environment)
- **bash** and **python 3**
- **node.js** and other dependencies required by your gpubrewlauncher installation
- a compatible checkout of [gpubrewlauncher](https://github.com/NiftyNova/GPUBrewLauncher), normally at `~/GPUBrewLauncher`
- storage access when deploying apps from shared downloads

## getting started

this repository currently provides the source tree, not a tested one-command installer.

1. install and configure gpubrewlauncher first.
2. obtain the z4tools source and place the toolkit directory at `~/z4tools`.
3. install the dependencies required by the features you plan to use.
4. launch the menu:

```bash
bash ~/z4tools/z4tools.sh
```

if your installation uses a different folder, run `z4tools.sh` from that folder instead. **do not overwrite an existing working installation without a backup.**

for additional notes, see [docs/install.md](docs/INSTALL.md).

## repository layout

```text
z4tools/
├── README.md
├── .gitignore
├── docs/
│   └── INSTALL.md
├── z4tools/
│   ├── z4tools.sh
│   ├── theme-maker.py
│   ├── customize.py
│   ├── live_themes.py
│   ├── app-deployer.py
│   ├── backup.sh
│   ├── text_editor.py
│   ├── compatibility_check.py
│   └── ...other toolkit modules
└── z4-accent-live/
    ├── z4_accent.py
    └── launcher.frag
```

## compatibility and limitations

- **android termux:** primary development target.
- **other linux distributions / wsl / macos:** not verified end-to-end.
- **windows native terminal:** not supported as a tested environment.
- theme patches and hot reload may stop working when the upstream launcher changes.
- the compatibility checker reports findings; it cannot guarantee that a patch will function correctly.
- a local backup should be made before restoring backups, rebuilding, or applying patches.

## privacy and security

the repository is intended to contain **source code, not personal runtime data**. local settings, logs, credentials, temporary files, and backup snapshots should stay on your device. the [`.gitignore`](.gitignore) excludes common local files, but **review `git status` before committing**: ignore rules cannot catch every sensitive file.

never publish github tokens, passwords, private keys, personal configuration, or full launcher backups. if credentials were committed, revoke them even after removing the files.

## version

**v1.5.3 — development snapshot**

this is a community-made toolkit, independent of and not endorsed by the gpubrewlauncher developers.

**upstream project:** [niftynova/gpubrewlauncher](https://github.com/NiftyNova/GPUBrewLauncher)

**license:** not yet selected. until a license is added, no open-source license grant is implied.
