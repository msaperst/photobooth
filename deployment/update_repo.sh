#!/usr/bin/env bash
set -u

# Fail inside the script, but systemd will ignore failures (ExecStartPre=-...).
set -e

cd /opt/photobooth

# Never prompt at boot.
export GIT_TERMINAL_PROMPT=0
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1

# If this isn't a git repo, do nothing.
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# If there are local modifications, do NOT stomp them. Just skip updating.
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "photobooth: repo has local changes; skipping auto-update"
  exit 0
fi

OLD_HEAD_FULL="$(git rev-parse HEAD 2>/dev/null || true)"
OLD_HEAD_SHORT="$(git rev-parse --short HEAD 2>/dev/null || true)"

# Require an upstream tracking branch; otherwise skip.
UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)"
if [[ -z "${UPSTREAM}" ]]; then
  echo "photobooth: no upstream configured for current branch; skipping auto-update"
  exit 0
fi

# Fetch (bounded) so boot doesn't hang if Ethernet isn't present.
timeout 10s git fetch --prune || exit 0

# Resolve the target commit we would fast-forward to.
TARGET_HEAD_FULL="$(git rev-parse --verify "${UPSTREAM}" 2>/dev/null || true)"
if [[ -z "${TARGET_HEAD_FULL}" ]]; then
  exit 0
fi

# Already up to date.
if [[ "${OLD_HEAD_FULL}" == "${TARGET_HEAD_FULL}" ]]; then
  echo "photobooth: already up to date (${OLD_HEAD_SHORT})"
  exit 0
fi

# Determine if requirements.txt would change between current HEAD and target HEAD
REQ_CHANGED=0
# If requirements exists in the target, compare blob hashes.
if git cat-file -e "${TARGET_HEAD_FULL}:requirements.txt" 2>/dev/null; then
  OLD_REQ_BLOB="$(git rev-parse HEAD:requirements.txt 2>/dev/null || true)"
  NEW_REQ_BLOB="$(git rev-parse "${TARGET_HEAD_FULL}:requirements.txt" 2>/dev/null || true)"
  if [[ "${OLD_REQ_BLOB}" != "${NEW_REQ_BLOB}" ]]; then
    REQ_CHANGED=1
  fi
else
  # If requirements doesn't exist at target but exists now, that's also a change.
  if git cat-file -e "HEAD:requirements.txt" 2>/dev/null; then
    REQ_CHANGED=1
  fi
fi

# Fast-forward to upstream (bounded)
timeout 10s git merge --ff-only "${UPSTREAM}" || exit 0

NEW_HEAD_SHORT="$(git rev-parse --short HEAD 2>/dev/null || true)"
echo "photobooth: updated ${OLD_HEAD_SHORT} -> ${NEW_HEAD_SHORT}"

# If requirements changed, attempt to install. If pip fails, revert repo to OLD_HEAD.
if [[ "${REQ_CHANGED}" -eq 1 ]]; then
  echo "photobooth: requirements changed; attempting pip install"

  if [[ -x /opt/photobooth/venv/bin/python ]]; then
    if ! timeout 60s /opt/photobooth/venv/bin/python -m pip install -r requirements.txt; then
      echo "photobooth: pip install failed; keeping old code (${OLD_HEAD_SHORT})"
      # Revert code to the previous known-good revision
      git reset --hard "${OLD_HEAD_FULL}" || true
      exit 0
    fi
    echo "photobooth: pip install complete"
  else
    echo "photobooth: venv python not found; keeping old code (${OLD_HEAD_SHORT})"
    git reset --hard "${OLD_HEAD_FULL}" || true
    exit 0
  fi
fi

exit 0
