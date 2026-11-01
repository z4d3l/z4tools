#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PROJECT="$HOME/GPUBrewLauncher"
STORE="$HOME/gpubrew-backups"
mkdir -p "$STORE"

usage() {
  printf 'usage: bash gpubrew-backup.sh backup | list | restore <backup-file.tar.gz>\n'
}

case "${1:-}" in
  backup)
    [ -d "$PROJECT/homebrew-launcher" ] || { echo 'gpubrew project not found'; exit 1; }
    stamp="$(date +%Y%m%d-%H%M%S)"
    target="$STORE/gpubrew-$stamp.tar.gz"
    tmp="$target.partial"
    trap 'rm -f "$tmp"' EXIT
    echo 'backing up the complete gpubrew project (including crimson theme and compiled shaders)...'
    tar -czf "$tmp" -C "$HOME" --exclude='GPUBrewLauncher/.git' --exclude='GPUBrewLauncher/node_modules' GPUBrewLauncher
    tar -tzf "$tmp" >/dev/null
    mv "$tmp" "$target"
    trap - EXIT
    echo "backup saved: $target"
    du -h "$target"
    ;;
  list)
    echo "backups in $STORE:"
    find "$STORE" -maxdepth 1 -type f -name 'gpubrew-*.tar.gz' -print | sort
    ;;
  restore)
    file="${2:-}"
    [ -f "$file" ] || { echo 'provide the full path to an existing backup'; usage; exit 1; }
    tar -tzf "$file" >/dev/null || { echo 'invalid archive'; exit 1; }
    if tar -tzf "$file" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
      echo 'unsafe archive paths; refusing restore'; exit 1
    fi
    tar -tzf "$file" | grep -q '^GPUBrewLauncher/homebrew-launcher/' || { echo 'not a gpubrew project backup'; exit 1; }
    echo 'stop gpubrew/start.sh before restoring!'
    printf 'type RESTORE to replace the current project: '
    read -r confirmation
    [ "$confirmation" = RESTORE ] || { echo 'cancelled'; exit 0; }
    stamp="$(date +%Y%m%d-%H%M%S)"
    previous="$HOME/GPUBrewLauncher-before-restore-$stamp"
    if [ -e "$PROJECT" ]; then mv "$PROJECT" "$previous"; fi
    if tar -xzf "$file" -C "$HOME"; then
      echo 'restore complete.'
      echo "previous project kept at: $previous"
    else
      echo 'restore failed; attempting to recover previous project'
      rm -rf "$PROJECT"
      if [ -d "$previous" ]; then mv "$previous" "$PROJECT"; fi
      exit 1
    fi
    ;;
  *) usage; exit 1 ;;
esac
