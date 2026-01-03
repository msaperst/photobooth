#!/usr/bin/env bash
set -u

# Fail fast inside the script, but systemd will ignore failures (see ExecStartPre=-...).
set -e

cd /opt/photobooth

# Never prompt (important for boot)
export GIT_TERMINAL_PROMPT=0

# If this isn't a git repo, do nothing.
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# If there are local modifications, do NOT stomp them. Just skip updating.
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "photobooth: repo has local changes; skipping auto-update"
  exit 0
fi

# If there is no upstream configured, skip.
UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)"
if [[ -z "${UPSTREAM}" ]]; then
  echo "photobooth: no upstream configured for current branch; skipping auto-update"
  exit 0
fi

# Fetch + fast-forward only. No merges, no prompts.
# Keep it quick so boot isn't delayed if Ethernet is absent.
timeout 10s git fetch --prune || exit 0
timeout 10s git merge --ff-only "${UPSTREAM}" || exit 0

echo "photobooth: auto-update complete ($(git rev-parse --short HEAD))"
