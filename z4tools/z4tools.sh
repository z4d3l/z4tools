#!/usr/bin/env bash
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: # do not import personal settings from an older installation
python3 -c 'import sys;sys.path.insert(0,sys.argv[1]);from settings import get_deployment_dir;print("app deployment folder:",get_deployment_dir())' "$DIR" || echo 'could not read deployment settings'

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  RED=$'\033[38;5;196m'; DIM=$'\033[38;5;245m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
else RED=''; DIM=''; BOLD=''; RESET=''; fi
clear_screen() { if [ -t 1 ]; then printf '\033[2J\033[H'; fi; }
pause_menu() { read -r -p 'press enter to continue...' _z4_pause || true; }
header() {
  clear_screen
  printf '%s%s' "$RED" "$BOLD"
  cat <<'ART'
  ███████╗██╗  ██╗
  ╚══███╔╝██║  ██║
    ███╔╝ ███████║
   ███╔╝  ╚════██║
  ███████╗     ██║
  ╚══════╝     ╚═╝
ART
  printf '%s' "$RESET"
  printf '%s  z4tools v1.7.0%s\n' "$BOLD" "$RESET"
  printf '%s  termux + debian/ubuntu | crimson terminal%s\n\n' "$DIM" "$RESET"
}
run_python() {
  if [ -f "$DIR/$1" ]; then
    local script="$1"; shift
    python3 "$DIR/$script" "$@"
  else
    printf 'missing module: %s\n' "$1"
  fi
}
z4_recovery_status_menu() {
  while true; do
    header
    printf '  sandbox recovery status (test only)\n  [1] view status\n  [2] manually recover interrupted sandbox\n  [0] back\n\n'
    read -r -p 'choose: ' c || return
    case "$c" in
      1) python3 "$DIR/recovery_menu_status.py" ;;
      2)
        if [ -z "${Z4_RECOVERY_TEST_SANDBOX:-}" ]; then
          echo 'set Z4_RECOVERY_TEST_SANDBOX to an isolated marked sandbox first.'
        else
          python3 "$DIR/recovery_menu_status.py"
          result=$?
          if [ "$result" -ne 3 ]; then
            echo 'manual recovery only permitted for a detected interrupted sandbox.'
          else
            read -r -p 'type RECOVER to recover this test sandbox: ' confirm
            if [ "$confirm" = 'RECOVER' ]; then
              python3 "$DIR/integrated_recovery_test.py" recover --sandbox "$Z4_RECOVERY_TEST_SANDBOX"
            else
              echo 'cancelled'
            fi
          fi
        fi
        ;;
      0) return ;;
      *) echo 'invalid option' ;;
    esac
    pause_menu
  done
}

z4_recovery_startup_notice() {
  if [ -n "${Z4_RECOVERY_TEST_SANDBOX:-}" ]; then
    echo '=== sandbox recovery startup check ==='
    python3 "$DIR/recovery_menu_status.py"
    echo '======================================'
  fi
}
z4_recovery_startup_notice

z4_production_restore_preview_menu() {
  python3 "$DIR/production_restore_menu.py"
}

apps_menu() {
  while true; do
    header
    printf '  apps\n  [1] deploy app zips\n  [2] manage installed apps\n  [3] deployment settings\n  [0] back\n\n'
    read -r -p 'choose: ' c || return
    case "$c" in
      1) run_python app-deployer.py ;;
      2) run_python extras.py app_manager ;;
      3) run_python settings.py ;;
      0) return ;;
      *) echo 'invalid option' ;;
    esac
    pause_menu
  done
}
backup_menu() {
  while true; do
    header
    printf '  backups\n  [1] create backup\n  [2] list backups\n  [3] restore backup\n  [4] backup information\n  [5] inspect backup\n  [6] verify backup\n  [7] configuration snapshots\n  [8] compare backups\n  [9] safe recovery preview\n  [10] sandbox recovery status\n  [0] back\n\n'
    read -r -p 'choose: ' c || return
    case "$c" in
      1) python3 "$DIR/backup_manager.py" create ;;
      2) python3 "$DIR/backup_manager.py" list ;;
      3) z4_production_restore_preview_menu ;;
      4) echo 'backups: ~/gpubrew-backups; restores require typing RESTORE.' ;;
      5) read -r -p "archive path (blank cancels): " p; [ -n "$p" ] && python3 "$DIR/backup_manager.py" inspect "$p" ;;
      6) read -r -p "archive path (blank cancels): " p; [ -n "$p" ] && python3 "$DIR/backup_manager.py" verify "$p" ;;
      7) config_snapshot_menu ;;
      8) backup_compare_menu ;;
      9) safe_recovery_menu ;;
      10) z4_recovery_status_menu ;;
      0) return ;;
      *) echo 'invalid option' ;;
    esac
    pause_menu
  done
}



safe_recovery_menu() {
  while true; do
    header
    printf '  safe recovery preview\n  [1] list available backups\n  [2] preview selected backup\n  [0] back\n\n'
    read -r -p 'choose: ' c || return
    case "$c" in
      1)
        find "$HOME/gpubrew-backups" -maxdepth 1 -type f \
          -name 'gpubrew-*.tar.gz' -print 2>/dev/null | sort
        ;;
      2)
        read -r -p 'backup path (blank cancels): ' p
        if [ -n "$p" ]; then
          python3 "$DIR/safe_recovery.py" "$p"
        fi
        ;;
      0) return ;;
      *) echo 'invalid option' ;;
    esac
    pause_menu
  done
}

backup_compare_menu() {
  while true; do
    header
    printf '  backup comparison\n  [1] compare 2 backups\n  [2] custom number of backups\n  [3] compare all backups\n  [0] back\n\n'
    read -r -p 'choose: ' c || return
    case "$c" in
      1)
        python3 "$DIR/backup_compare.py" --mode two
        ;;
      2)
        read -r -p 'how many backups? ' n
        if [[ "$n" =~ ^[0-9]+$ ]] && (( n >= 2 && n <= 100 )); then
          python3 "$DIR/backup_compare.py" --mode custom --count "$n"
        else
          echo 'enter a number between 2 and 100'
        fi
        ;;
      3)
        python3 "$DIR/backup_compare.py" --mode all
        ;;
      0) return ;;
      *) echo 'invalid option' ;;
    esac
    pause_menu
  done
}

config_snapshot_menu() {
  while true; do
    header
    printf '  configuration snapshots\n  [1] create snapshot\n  [2] list snapshots\n  [3] inspect snapshot\n  [4] compare snapshots\n  [0] back\n\n'
    read -r -p 'choose: ' c || return
    case "$c" in
      1)
        read -r -p 'snapshot name: ' n
        [ -n "$n" ] && python3 "$DIR/config_snapshots.py" create "$n"
        ;;
      2)
        python3 "$DIR/config_snapshots.py" list
        ;;
      3)
        read -r -p 'snapshot name: ' n
        [ -n "$n" ] && python3 "$DIR/config_snapshots.py" inspect "$n"
        ;;
      4)
        read -r -p 'first snapshot: ' a
        read -r -p 'second snapshot: ' b
        if [ -n "$a" ] && [ -n "$b" ]; then
          python3 "$DIR/config_snapshots.py" compare "$a" "$b"
        fi
        ;;
      0) return ;;
      *) echo 'invalid option' ;;
    esac
    pause_menu
  done
}

custom_menu() {
  while true; do
    header
    printf '  customization\n  [1] theme maker + advanced editor\n  [2] text editor + hot reload\n  [3] install text hot-reload patch\n  [4] accent hot-load patch setup\n  [5] install / repair watermark\n  [6] configuration editor\n  [0] back\n\n'
    read -r -p 'choose: ' c || return
    case "$c" in
      1) run_python customize.py ;;
      2) run_python text_editor.py ;;
      3) run_python text_hot_reload_patch.py install ;;
      4) run_python accent_setup.py ;;
      5) run_python customize.py watermark ;;
      6) run_python config_editor.py ;;
      0) return ;;
      *) echo 'invalid option' ;;
    esac
    pause_menu
  done
}
diagnostics_menu() {
  while true; do
    header
    printf '  diagnostics\n  [1] advanced compatibility checker\n  [2] dependency manager\n  [3] advanced log viewer\n  [4] logs + startup timer (legacy)\n  [5] launcher builder + diagnostics\n  [6] system health check\n  [7] update checker\n  [8] system dashboard\n  [9] export diagnostics\n  [0] back\n\n'
    read -r -p 'choose: ' c || return
    case "$c" in
      1) run_python compatibility_check.py ;;
      2) run_python dependency_manager.py ;;
      3) run_python log_viewer.py ;;
      4) run_python extras.py logsandtimer ;;
      5) run_python extras.py buildtools ;;
      6) run_python health_check.py ;;
      7) run_python update_checker.py ;;
      8) run_python system_dashboard.py ;;
      9) run_python export_diagnostics.py ;;
      0) return ;;
      *) echo 'invalid option' ;;
    esac
    pause_menu
  done
}
launcher_menu() {
  while true; do
    header
    printf '  launcher tools\n  [1] launcher builder + diagnostics\n  [2] app template generator\n  [0] back\n\n'
    read -r -p 'choose: ' c || return
    case "$c" in
      1) run_python extras.py buildtools ;;
      2) run_python extras.py template ;;
      0) return ;;
      *) echo 'invalid option' ;;
    esac
    pause_menu
  done
}
while true; do
  header
  printf '  [1] customization\n  [2] apps\n  [3] backups + recovery\n  [4] diagnostics + dependencies\n  [5] launcher tools\n  [6] operation preview\n  [7] first-run setup wizard\n  [0] exit\n\n'
  if [ ! -e "$DIR/.z4-first-run.json" ]; then printf '%s\n' '  [setup] option 7 is available for first-time configuration'; fi
  read -r -p 'choose: ' c || exit 0
  case "$c" in
    1) custom_menu ;;
    2) apps_menu ;;
    3) backup_menu ;;
    4) diagnostics_menu ;;
    5) launcher_menu ;;
    6) run_python operation_preview.py ;;
    7) run_python first_run_wizard.py wizard ;;
    0) exit 0 ;;
    *) echo 'invalid option'; pause_menu ;;
  esac
done
