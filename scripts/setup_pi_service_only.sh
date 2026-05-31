#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/durian-dashboard}"
SERVICE_NAME="${SERVICE_NAME:-durian-dashboard}"
PI_USER="${PI_USER:-pi}"
ASSUME_YES=0

PI_HOME=""
SERVICE_SRC=""
SERVICE_DST=""

log() {
  echo "[setup-service-only] $*"
}

die() {
  echo "[setup-service-only][error] $*" >&2
  exit 1
}

refresh_paths() {
  PI_HOME="${PI_HOME:-/home/$PI_USER}"
  SERVICE_SRC="$APP_DIR/systemd/$SERVICE_NAME.service"
  SERVICE_DST="/etc/systemd/system/$SERVICE_NAME.service"
}

show_help() {
  cat <<EOF
Usage: sudo bash scripts/setup_pi_service_only.sh [options]

Options:
  --yes, -y            Run non-interactive with current/default values
  --help, -h           Show this help text

Environment overrides:
  APP_DIR, SERVICE_NAME, PI_USER, PI_HOME
EOF
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --yes|-y)
        ASSUME_YES=1
        ;;
      --help|-h)
        show_help
        exit 0
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
    shift
  done
}

is_tty() {
  [ -t 0 ] && [ -t 1 ]
}

prompt_with_default() {
  local label="$1"
  local current="$2"
  local answer
  read -r -p "$label [$current]: " answer
  if [ -n "$answer" ]; then
    echo "$answer"
  else
    echo "$current"
  fi
}

prompt_yes_no() {
  local label="$1"
  local default="$2"
  local answer
  read -r -p "$label [$default]: " answer
  answer="${answer:-$default}"
  case "$answer" in
    y|Y|yes|YES)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[&|]/\\&/g'
}

collect_inputs() {
  if [ "$ASSUME_YES" -eq 1 ] || ! is_tty; then
    return
  fi

  echo
  echo "=== Durian Dashboard Service-Only Setup (Interactive) ==="
  echo "Press Enter to use default values shown in [brackets]."
  echo

  APP_DIR="$(prompt_with_default "Project directory" "$APP_DIR")"
  PI_USER="$(prompt_with_default "Linux user (service owner)" "$PI_USER")"
  PI_HOME="$(prompt_with_default "Home directory for that user" "/home/$PI_USER")"
  SERVICE_NAME="$(prompt_with_default "Systemd service name" "$SERVICE_NAME")"

  refresh_paths

  echo
  echo "Selected values:"
  echo "- APP_DIR=$APP_DIR"
  echo "- PI_USER=$PI_USER"
  echo "- PI_HOME=$PI_HOME"
  echo "- SERVICE_NAME=$SERVICE_NAME"

  if ! prompt_yes_no "Continue setup" "y"; then
    die "Cancelled by user"
  fi
}

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    die "Run this script as root: sudo bash scripts/setup_pi_service_only.sh"
  fi
}

require_paths() {
  [ -d "$APP_DIR" ] || die "APP_DIR not found: $APP_DIR"
  [ -f "$APP_DIR/requirements.txt" ] || die "Missing requirements file: $APP_DIR/requirements.txt"
  [ -f "$SERVICE_SRC" ] || die "Missing service file: $SERVICE_SRC"
  id "$PI_USER" >/dev/null 2>&1 || die "User not found: $PI_USER"
}

install_packages() {
  log "Installing OS packages (service-only)"
  apt-get update
  apt-get install -y python3-venv python3-pip curl
}

setup_python_env() {
  log "Creating and updating Python virtual environment"
  if [ ! -d "$APP_DIR/.venv" ]; then
    python3 -m venv "$APP_DIR/.venv"
  fi

  "$APP_DIR/.venv/bin/pip" install --upgrade pip
  "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
}

setup_systemd_service() {
  log "Configuring systemd service"
  local app_dir_escaped
  local user_escaped
  local exec_start_escaped
  local db_path_escaped

  app_dir_escaped="$(escape_sed_replacement "$APP_DIR")"
  user_escaped="$(escape_sed_replacement "$PI_USER")"
  exec_start_escaped="$(escape_sed_replacement "$APP_DIR/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 1")"
  db_path_escaped="$(escape_sed_replacement "$APP_DIR/data/durian_dashboard.db")"

  sed \
    -e "s|^User=.*|User=$user_escaped|" \
    -e "s|^Group=.*|Group=$user_escaped|" \
    -e "s|^WorkingDirectory=.*|WorkingDirectory=$app_dir_escaped|" \
    -e "s|^Environment=DB_PATH=.*|Environment=DB_PATH=$db_path_escaped|" \
    -e "s|^ExecStart=.*|ExecStart=$exec_start_escaped|" \
    "$SERVICE_SRC" > "$SERVICE_DST"

  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
}

print_summary() {
  log "Completed"
  echo
  echo "Next steps:"
  echo "1) Verify service: sudo systemctl status $SERVICE_NAME --no-pager"
  echo "2) Verify web port: sudo ss -tulpn | grep 8080"
  echo "3) Test from another device: http://<SERVER_IP>:8080"
  echo
  echo "This script does NOT configure browser autostart or desktop kiosk mode."
}

main() {
  parse_args "$@"
  require_root
  refresh_paths
  collect_inputs
  require_paths
  install_packages
  setup_python_env
  setup_systemd_service
  print_summary
}

main "$@"
