#!/usr/bin/env bash
set -euo pipefail

# Step 1 provisioning: OS deps + user/group setup.
# Safe to re-run.

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: run as root: sudo $0"
  exit 1
fi

echo "==> Updating apt and installing base dependencies"
apt-get update
apt-get upgrade -y

# Keep this intentionally minimal and explicit.
apt-get install -y \
  git \
  gphoto2 \
  libgphoto2-6t64 \
  libusb-1.0-0 \
  usbutils \
  python3-venv \
  python3-pip

echo "==> Ensuring photobooth user exists"
if id -u photobooth >/dev/null 2>&1; then
  echo "    photobooth user already exists"
else
  useradd --create-home --shell /bin/bash photobooth
  echo "    created user: photobooth"
fi

echo "==> Adding photobooth user to required groups (plugdev, video, dialout, lp, lpadmin if present)"
for grp in plugdev video dialout lp lpadmin; do
  if getent group "${grp}" >/dev/null 2>&1; then
    usermod -aG "${grp}" photobooth
  fi
done

echo "==> Verifying gphoto udev rules exist (informational)"
if ls /lib/udev/rules.d/ | grep -q "libgphoto2"; then
  echo "    gphoto udev rules present"
else
  echo "WARNING: gphoto udev rules not found in /lib/udev/rules.d/. Camera permissions may fail."
fi

# NOTE: The gvfs/gsettings steps from your docs are only relevant on desktop environments.
# We do NOT assume GNOME is installed on the Pi (headless typical), so we only print guidance.
echo "==> NOTE: If you're on a desktop environment and gphoto can't claim the device:"
echo "    gsettings set org.gnome.desktop.media-handling automount false"
echo "    gsettings set org.gnome.desktop.media-handling automount-open false"
echo "    systemctl --user mask gvfs-gphoto2-volume-monitor.service"
echo "    systemctl --user stop gvfs-gphoto2-volume-monitor.service"

echo "==> Done."
echo "Next steps:"
echo "  1) Reboot: say 'sudo reboot' (USB group changes require re-login)"
echo "  2) Follow camera verification steps (lsusb, gphoto2 --auto-detect, gphoto2 --summary)"
