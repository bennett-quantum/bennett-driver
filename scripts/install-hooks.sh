#!/usr/bin/env bash
set -euo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS BROWSER
root="$(git -C "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" rev-parse --show-toplevel)"
if hooks="$(git -C "$root" config --path --get core.hooksPath)"; then
  [ -n "$hooks" ] || { echo 'install-hooks: core.hooksPath is empty' >&2; exit 3; }
  case "$hooks" in /*) ;; *) hooks="$root/$hooks" ;; esac
else
  common="$(git -C "$root" rev-parse --path-format=absolute --git-common-dir)"
  hooks="$common/hooks"
fi
mkdir -p "$hooks"
# Keep the effective hook chained to the versioned stub after every update.
# Atomic replacement also avoids exposing a partially written running script.
link="$hooks/.pre-push.$$"
trap 'rm -f "$link"' EXIT
ln -s "$root/scripts/pre-push" "$link"
mv -Tf "$link" "$hooks/pre-push"
echo "installed pre-push hook: $hooks/pre-push -> $root/scripts/pre-push"
