#!/usr/bin/env bash
set -euo pipefail

if command -v git >/dev/null 2>&1; then
    REPO_DIR="$(git rev-parse --show-toplevel)"
fi

log () {
    echo "[$1] $2" >&2
}

# Example: log_info "This is info message"
log_info () {
    log "INFO" "$1"
}

# Example: log_error "This is error message"
log_error () {
    log "ERROR" "$1"
}

# Example: log_warning "This is warning message"
log_warning () {
    log "WARNING" "$1"
}

# Example: log_debug "This is debug message"
log_debug () {
    log "DEBUG" "$1"
}

# Example: check_installed pip "https://pip.pypa.io/en/stable/installation/"
check_installed () {
    local COMMAND="$1"
    local INSTRUCTIONS="$2"
    if ! which "$COMMAND" 1>/dev/null; then
            log_error "Not found command: ${COMMAND}. Please, install ${COMMAND}: ${INSTRUCTIONS}"
            exit 1
    fi
}

# Example: check_variable "VERSION" "-v is required. Usage: $(usage)"
check_variable () {
    local VAR_NAME="$1"
    local ERROR_MESSAGE="$2"
    if [[ -z "${!VAR_NAME+x}" ]]; then
        log_error "$ERROR_MESSAGE"
        exit 1
    fi
}

# Example: assert "$URL" == "$UPSTREAM_URL"
assert () {
    if ! $(test "$@"); then
        log_error "assert ${@}"
        exit 1
    fi
}

# bash replacement for realpath cli (MacOS doesn't have it pre-installed)
# Example: ARCHIVE_PATH="$(real_path "$ARCHIVE_PATH")"
real_path () {
    local P="$( cd "$( dirname "${1/#\~/$HOME}" )" >/dev/null && pwd )"
    if [[ -z "$P" ]]; then
        exit 1
    fi
    echo "${P}/$(basename "$1")"
}

# Execute command silently if success, else print stdout+stderr and exit 1
# Example: exec_silent git checkout main
exec_silent () {
    if ! RESULT=$("$@" 2>&1); then
        log_error "Command failed: \"$@\""
        log_error "$RESULT"
        exit 1
    fi
}

if [ "${DEBUG:-0}" -ne "0" ]; then
        log_debug "Debug is enabled"
        set -xeuo pipefail
fi