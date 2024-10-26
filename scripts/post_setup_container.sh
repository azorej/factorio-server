#!/bin/bash

# DO NOT USE STANDADARD PREAMBULE: it will break MacOS devcontainers

set -euo pipefail

if [ -z ${1+x} ] ; then
    echo "Absent argument: {HOST_USER}"
    exit 1
fi
HOST_USER="$1"

if [ -z ${2+x} ] ; then
    echo "Absent argument: {WORKSPACE_PATH}"
    exit 1
fi
WORKSPACE_PATH="$2"

sudo chown -R "$HOST_USER":"$HOST_USER" "/home/${HOST_USER}/.cache"
# Don't try to change owner for git directories
ls -A "$WORKSPACE_PATH" | egrep -vx '.git(hub)?' | xargs -I{} sudo chown -R "$HOST_USER" "${WORKSPACE_PATH}/{}"

git config --global --add safe.directory "$WORKSPACE_PATH"
cd "$WORKSPACE_PATH"
pre-commit install

uname -a