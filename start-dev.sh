#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.bonplan"
BACKEND_CONFIG="$BACKEND_DIR/app/core/config.py"
FRONTEND_CONFIG="$FRONTEND_DIR/src/apis/config.ts"
BACKEND_ENV="$ROOT_DIR/.env"
FRONTEND_ENV="$FRONTEND_DIR/.env"

trap 'printf "\n[ERROR] Setup failed on line %s. Fix the issue above and rerun ./start-dev.sh.\n" "$LINENO" >&2' ERR

usage() {
    cat <<'EOF'
BonPlan.ai local development bootstrap

Usage:
  ./start-dev.sh [options]

Options:
  --setup-only       Install Homebrew packages, Python packages, and frontend dependencies without starting servers.
  --start-only       Start Redis and app servers without reinstalling dependencies.
  --yes             Do not pause when env files are missing.
  --help            Show this help message.

Services started:
  API backend       http://localhost:8000
  Agent backend     http://localhost:8001
  Frontend          Vite dev server, usually http://localhost:5173
  Redis             redis://localhost:6379/0
EOF
}

SETUP_ONLY=0
START_ONLY=0
ASSUME_YES=0

for arg in "$@"; do
    case "$arg" in
        --setup-only)
            SETUP_ONLY=1
            ;;
        --start-only)
            START_ONLY=1
            ;;
        --yes)
            ASSUME_YES=1
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            printf "[ERROR] Unknown option: %s\n\n" "$arg" >&2
            usage
            exit 1
            ;;
    esac
done

if [[ "$SETUP_ONLY" -eq 1 && "$START_ONLY" -eq 1 ]]; then
    printf "[ERROR] --setup-only and --start-only cannot be used together.\n" >&2
    exit 1
fi

section() {
    printf "\n==> %s\n" "$1"
}

info() {
    printf "    %s\n" "$1"
}

warn() {
    printf "    [WARN] %s\n" "$1" >&2
}

require_command() {
    local command_name="$1"
    local install_hint="$2"

    if ! command -v "$command_name" >/dev/null 2>&1; then
        printf "[ERROR] Required command not found: %s\n" "$command_name" >&2
        printf "        %s\n" "$install_hint" >&2
        exit 1
    fi
}

shell_quote() {
    printf "%q" "$1"
}

find_python313() {
    if command -v python3.13 >/dev/null 2>&1; then
        command -v python3.13
        return 0
    fi

    local brew_python_prefix
    brew_python_prefix="$(brew --prefix python@3.13 2>/dev/null || true)"
    if [[ -n "$brew_python_prefix" && -x "$brew_python_prefix/bin/python3.13" ]]; then
        printf "%s/bin/python3.13\n" "$brew_python_prefix"
        return 0
    fi

    if [[ -x "/opt/homebrew/bin/python3.13" ]]; then
        printf "/opt/homebrew/bin/python3.13\n"
        return 0
    fi

    if [[ -x "/usr/local/bin/python3.13" ]]; then
        printf "/usr/local/bin/python3.13\n"
        return 0
    fi

    return 1
}

find_redis_cli() {
    if command -v redis-cli >/dev/null 2>&1; then
        command -v redis-cli
        return 0
    fi

    local redis_prefix
    redis_prefix="$(brew --prefix redis 2>/dev/null || true)"
    if [[ -n "$redis_prefix" && -x "$redis_prefix/bin/redis-cli" ]]; then
        printf "%s/bin/redis-cli\n" "$redis_prefix"
        return 0
    fi

    return 1
}

print_env_guidance() {
    section "Environment configuration"
    info "Review these source-of-truth config files before your first run:"
    info "Backend config:  $BACKEND_CONFIG"
    info "Frontend config: $FRONTEND_CONFIG"
    printf "\n"
    info "Create/update these local env files with the variables required by those configs:"
    info "Backend env:  $BACKEND_ENV"
    info "Frontend env: $FRONTEND_ENV"
    printf "\n"
    info "Backend variables include database, Redis, Google, auth, email, and model/API keys."
    info "Frontend variables must use Vite names such as VITE_API_URL and VITE_AGENT_URL."
    info "This script does not generate secrets or overwrite env files."

    local missing_env=0
    if [[ ! -f "$BACKEND_ENV" ]]; then
        warn "Missing backend env file: $BACKEND_ENV"
        missing_env=1
    fi
    if [[ ! -f "$FRONTEND_ENV" ]]; then
        warn "Missing frontend env file: $FRONTEND_ENV"
        missing_env=1
    fi

    if [[ "$missing_env" -eq 1 && "$ASSUME_YES" -eq 0 ]]; then
        printf "\nCreate the missing env file(s), then press Enter to continue. Press Ctrl-C to stop. "
        read -r _
    fi
}

install_brew_bundles() {
    section "Installing Homebrew bundles"
    require_command "brew" "Install Homebrew from https://brew.sh, then rerun ./start-dev.sh."

    local found_brewfile=0
    while IFS= read -r brewfile; do
        found_brewfile=1
        info "brew bundle --file=$brewfile"
        brew bundle --file="$brewfile"
    done < <(
        find "$ROOT_DIR" \
            \( -path "$ROOT_DIR/.git" -o -path "$ROOT_DIR/graphify-out" -o -path "$FRONTEND_DIR/node_modules" -o -path "$VENV_DIR" \) -prune \
            -o -type f \( -iname "Brewfile" -o -iname "brewfile" \) -print | sort
    )

    if [[ "$found_brewfile" -eq 0 ]]; then
        warn "No Brewfile found under $ROOT_DIR."
    fi
}

setup_backend() {
    section "Setting up backend virtual environment"

    local python_bin
    if ! python_bin="$(find_python313)"; then
        printf "[ERROR] Python 3.13 was not found after Homebrew setup.\n" >&2
        printf "        Run: brew install python@3.13\n" >&2
        exit 1
    fi

    info "Using Python: $python_bin"
    "$python_bin" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip

    if [[ -f "$BACKEND_DIR/requirements-test.txt" ]]; then
        info "Installing backend requirements from backend/requirements-test.txt"
        "$VENV_DIR/bin/python" -m pip install -r "$BACKEND_DIR/requirements-test.txt"
    elif [[ -f "$BACKEND_DIR/requirements.txt" ]]; then
        info "Installing backend requirements from backend/requirements.txt"
        "$VENV_DIR/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"
    else
        warn "No backend requirements file found."
    fi
}

setup_frontend() {
    section "Installing frontend dependencies"
    require_command "npm" "Install Node.js 20.x and npm, then rerun ./start-dev.sh."

    if [[ -f "$FRONTEND_DIR/package-lock.json" ]]; then
        info "npm ci"
        (cd "$FRONTEND_DIR" && npm ci)
    else
        info "npm install"
        (cd "$FRONTEND_DIR" && npm install)
    fi
}

start_redis() {
    section "Starting Redis"
    require_command "brew" "Install Homebrew from https://brew.sh, then rerun ./start-dev.sh."

    info "brew services start redis"
    brew services start redis

    local redis_cli
    if redis_cli="$(find_redis_cli)"; then
        local attempt
        for attempt in 1 2 3 4 5 6 7 8 9 10; do
            if "$redis_cli" ping >/dev/null 2>&1; then
                info "Redis is responding on redis://localhost:6379/0"
                return 0
            fi
            sleep 1
        done
        warn "Redis service was started, but redis-cli ping did not return PONG yet."
    else
        warn "redis-cli was not found; skipping Redis health check."
    fi
}

warn_if_port_is_busy() {
    local port="$1"
    local label="$2"

    if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        warn "$label port $port is already in use. The new server may fail to start until that process is stopped."
    fi
}

open_terminal() {
    local title="$1"
    local command_text="$2"

    osascript - "$title" "$command_text" <<'APPLESCRIPT'
on run argv
    set terminalTitle to item 1 of argv
    set commandText to item 2 of argv
    tell application "Terminal"
        activate
        do script "printf '\\033]0;" & terminalTitle & "\\007'; " & commandText
    end tell
end run
APPLESCRIPT
}

start_servers() {
    section "Starting development servers in Terminal"

    if [[ "$(uname -s)" != "Darwin" ]]; then
        printf "[ERROR] This script opens separate terminals through macOS Terminal.app.\n" >&2
        printf "        Run on macOS, or start the commands printed below manually.\n" >&2
        exit 1
    fi

    require_command "osascript" "Install or enable AppleScript support on macOS."

    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        printf "[ERROR] Backend virtual environment is missing: %s\n" "$VENV_DIR" >&2
        printf "        Run ./start-dev.sh without --start-only first.\n" >&2
        exit 1
    fi

    warn_if_port_is_busy "8000" "API backend"
    warn_if_port_is_busy "8001" "Agent backend"
    warn_if_port_is_busy "8002" "MCP backend"
    warn_if_port_is_busy "5173" "Frontend"

    local backend_dir_quoted
    local frontend_dir_quoted
    local venv_activate_quoted
    backend_dir_quoted="$(shell_quote "$BACKEND_DIR")"
    frontend_dir_quoted="$(shell_quote "$FRONTEND_DIR")"
    venv_activate_quoted="$(shell_quote "$VENV_DIR/bin/activate")"

    local api_command
    api_command="cd $backend_dir_quoted && source $venv_activate_quoted && echo '[BonPlan.ai] API backend: http://localhost:8000' && python -m uvicorn app.app:app --host 0.0.0.0 --port 8000 --reload"

    local agent_command
    agent_command="cd $backend_dir_quoted && source $venv_activate_quoted && echo '[BonPlan.ai] Agent backend: http://localhost:8001' && python -m uvicorn app.ai:app --host 0.0.0.0 --port 8001 --reload"

    local mcp_command
    mcp_command="cd $backend_dir_quoted && source $venv_activate_quoted && echo '[BonPlan.ai] MCP backend: http://localhost:8002${MCP_SSE_PATH:-/mcp/sse}' && python -m uvicorn app.mcp:app --host 0.0.0.0 --port 8002 --reload"

    local frontend_command
    frontend_command="cd $frontend_dir_quoted && echo '[BonPlan.ai] Frontend: Vite dev server' && npm run dev"

    open_terminal "BonPlan API Backend" "$api_command"
    open_terminal "BonPlan Agent Backend" "$agent_command"
    open_terminal "BonPlan MCP Backend" "$mcp_command"
    open_terminal "BonPlan Frontend" "$frontend_command"

    printf "\nStarted Terminal windows for:\n"
    printf "  API backend:   http://localhost:8000\n"
    printf "  Agent backend: http://localhost:8001\n"
    printf "  MCP backend:   http://localhost:8002%s\n" "${MCP_SSE_PATH:-/mcp/sse}"
    printf "  Frontend:      usually http://localhost:5173\n"
    printf "  Redis:         redis://localhost:6379/0\n"
    printf "\nLeave those Terminal windows open while developing. Stop each server with Ctrl-C.\n"
}

main() {
    section "BonPlan.ai local development bootstrap"
    info "Project root: $ROOT_DIR"

    if [[ ! -d "$BACKEND_DIR" || ! -d "$FRONTEND_DIR" ]]; then
        printf "[ERROR] Expected backend/ and frontend/ under %s.\n" "$ROOT_DIR" >&2
        exit 1
    fi

    print_env_guidance

    if [[ "$START_ONLY" -eq 0 ]]; then
        install_brew_bundles
        setup_backend
        setup_frontend
    fi

    if [[ "$SETUP_ONLY" -eq 1 ]]; then
        section "Setup complete"
        info "Run ./start-dev.sh --start-only when you are ready to start the local servers."
        exit 0
    fi

    start_redis
    start_servers
}

main "$@"
