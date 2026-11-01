# z4tools v1.5.3 — installation

z4tools is a development-stage customization toolkit for [gpubrewlauncher](https://github.com/NiftyNova/GPUBrewLauncher).

## requirements

- android termux (primary tested environment)
- bash, python 3 and node.js as required by the installed launcher
- an existing compatible gpubrewlauncher checkout at `~/GPUBrewLauncher`
- a backup of your current launcher and toolkit before applying patches

## launch

```bash
bash ~/z4tools/z4tools.sh
```

## source status

the source upload is in progress. this repository is not yet a complete installable release. the runtime accent controller and shader must match the patched launcher version; copying toolkit scripts alone does not enable live accents.

## compatibility

other linux distributions and wsl have not been verified end-to-end. patch detection does not guarantee visual/runtime success.
