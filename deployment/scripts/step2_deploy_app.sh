
# Ensure repo is writable by the service user
sudo chown -R photobooth:photobooth /opt/photobooth
#!/usr/bin/env bash
set -euo pipefail

# Step 2 deployment: clone/pull + venv + deps + env + systemd.
# Safe to re-run for updates.

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: run as root: sudo $0"
  exit 1
fi

REPO_URL="${REPO_URL:-https://github.com/msaperst/photobooth.git}"
BRANCH="${BRANCH:-main}"

APP_DIR="/opt/photobooth"
VENV_DIR="${APP_DIR}/venv"

ENV_FILE="/etc/photobooth.env"
ENV_EXAMPLE_IN_REPO="${APP_DIR}/deployment/photobooth.env.example"

DATA_DIR="/var/lib/photobooth"
SYSTEMD_UNIT_SRC="${APP_DIR}/deployment/systemd/photobooth.service"
SYSTEMD_UNIT_DST="/etc/systemd/system/photobooth.service"

echo "==> Ensuring /opt exists"
mkdir -p /opt

echo "==> Ensuring data dir exists: ${DATA_DIR}"
mkdir -p "${DATA_DIR}"
chown -R photobooth:photobooth "${DATA_DIR}"
chmod 755 "${DATA_DIR}"

if [[ ! -d "${APP_DIR}/.git" ]]; then
  echo "==> Cloning repo to ${APP_DIR}"
  git clone "${REPO_URL}" "${APP_DIR}"
  chown -R photobooth:photobooth "${APP_DIR}"
else
  echo "==> Repo already present at ${APP_DIR}"
fi

echo "==> Checking out branch: ${BRANCH}"
sudo -u photobooth git -C "${APP_DIR}" fetch --all --prune
sudo -u photobooth git -C "${APP_DIR}" checkout "${BRANCH}"
sudo -u photobooth git -C "${APP_DIR}" pull --ff-only

echo "==> Creating venv at ${VENV_DIR} if missing"
if [[ ! -d "${VENV_DIR}" ]]; then
  sudo -u photobooth python3 -m venv "${VENV_DIR}"
fi

echo "==> Installing python deps"
sudo -u photobooth "${VENV_DIR}/bin/python" -m pip install --upgrade pip
sudo -u photobooth "${VENV_DIR}/bin/python" -m pip install -r "${APP_DIR}/requirements.txt"

echo "==> Verifying gunicorn is available"
sudo -u photobooth "${VENV_DIR}/bin/python" -m gunicorn --version >/dev/null
echo "    gunicorn OK"

echo "==> Installing /etc/photobooth.env if missing"
if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -f "${ENV_EXAMPLE_IN_REPO}" ]]; then
    cp "${ENV_EXAMPLE_IN_REPO}" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    echo "    created ${ENV_FILE} from example (EDIT THIS FILE for your event)"
  else
    echo "ERROR: env example not found at ${ENV_EXAMPLE_IN_REPO}"
    exit 1
  fi
else
  echo "    ${ENV_FILE} already exists (leaving unchanged)"
fi

echo "==> Installing systemd unit"
if [[ ! -f "${SYSTEMD_UNIT_SRC}" ]]; then
  echo "ERROR: systemd unit not found at ${SYSTEMD_UNIT_SRC}"
  exit 1
fi
cp "${SYSTEMD_UNIT_SRC}" "${SYSTEMD_UNIT_DST}"
chmod 644 "${SYSTEMD_UNIT_DST}"

echo "==> Reloading systemd and enabling service"
systemctl daemon-reload
systemctl enable photobooth

echo "==> Restarting service"
systemctl restart photobooth

echo "==> Status:"
systemctl --no-pager --full status photobooth || true

echo "==> Quick health check (may show CONFIG_INVALID until you edit /etc/photobooth.env)"
if command -v curl >/dev/null 2>&1; then
  curl -s http://127.0.0.1:5000/healthz || true
  echo
else
  echo "    curl not installed; install with: sudo apt-get install -y curl"
fi

echo "==> Done."
echo "Next steps:"
echo "  1) Edit ${ENV_FILE} (set PHOTOBOOTH_IMAGE_ROOT, PHOTOBOOTH_ALBUM_CODE, PHOTOBOOTH_LOGO_PATH)"
echo "  2) Copy your event logo to the path you set (e.g. ${DATA_DIR}/logo.png)"
echo "  3) Restart: sudo systemctl restart photobooth"
echo "  4) Check: curl http://127.0.0.1:5000/healthz"
