#!/usr/bin/env bash
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -e "$DIR/settings.json" ] && [ -f "$HOME/z4tools/settings.json" ] && [ "$DIR" != "$HOME/z4tools" ]; then cp "$HOME/z4tools/settings.json" "$DIR/settings.json"; fi
python3 -c 'import sys;sys.path.insert(0,sys.argv[1]);from settings import ensure_deployment_dir;print("app deployment folder:",ensure_deployment_dir())' "$DIR" || echo 'could not create deployment folder'
while true; do
printf '\033[2J\033[H'
cat <<'ART'
  ███████╗██╗  ██╗
  ╚══███╔╝██║  ██║
    ███╔╝ ███████║
   ███╔╝  ╚════██║
  ███████╗     ██║
  ╚══════╝     ╚═╝
           Z4TOOLS v1.5.3
  ----------------------------
  [1] theme maker + advanced editor
  [2] app deployer + manager
  [3] backups + restore points
  [4] launcher builder + diagnostics
  [5] logs + startup timer
  [6] app template generator
  [7] install / repair watermark
  [8] text editor + hot-reload launcher
  [9] install text hot-reload patch
  [10] accent colors hot-load patch setup
  [11] compatibility checker
  [0] exit
  ----------------------------
ART
read -r -p 'choose: ' c || exit 0
case "$c" in
1) python3 "$DIR/customize.py" ;;
2)
 while true; do
 printf '\033[2J\033[H'
 echo 'app tools: [1] deploy zips [2] manage apps [3] settings (deployment directory) [0] back'
 read -r -p 'choose: ' a || break
 case "$a" in
 1) python3 "$DIR/app-deployer.py" ;;
 2) python3 "$DIR/extras.py" app_manager ;;
 3) python3 "$DIR/settings.py" ;;
 0) break ;;
 esac
 read -r -p 'press enter to continue...' _z4_subpause || true
 done ;;
3)
 while true; do
 printf '\033[2J\033[H'
 echo 'backups: [1] create [2] list [3] restore [4] settings [0] back'
 read -r -p 'choose: ' a || break
 case "$a" in
 1) read -r -p 'create backup? [y/N] ' y; [ "$y" = y ] && bash "$DIR/backup.sh" backup ;;
 2) bash "$DIR/backup.sh" list ;;
 3) bash "$DIR/backup.sh" list; read -r -p 'backup path (blank cancels): ' p; [ -n "$p" ] && bash "$DIR/backup.sh" restore "$p" ;;
 4) echo 'settings: backups are saved to ~/gpubrew-backups. restores require typing RESTORE.' ;;
 0) break ;;
 esac
 read -r -p 'press enter to continue...' _z4_subpause || true
 done ;;
4) python3 "$DIR/extras.py" buildtools ;;
5) python3 "$DIR/extras.py" logsandtimer ;;
6) python3 "$DIR/extras.py" template ;;
7) python3 "$DIR/customize.py" watermark ;;
8) python3 "$DIR/text_editor.py" ;;
9) python3 "$DIR/text_hot_reload_patch.py" install ;;
10) python3 "$DIR/accent_setup.py" ;;
11) python3 "$DIR/compatibility_check.py" ;;
0) exit 0 ;;
*) echo 'invalid option' ;;
esac
read -r -p 'press enter to return to menu...' _z4_pause || true
# z4tools-clean-menu-v152
done
