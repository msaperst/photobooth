#!/usr/bin/env bash
set -euo pipefail


ARCH="$(uname -m || true)"
if [[ "${ARCH}" != "aarch64" ]]; then
  echo "WARN: Detected architecture: ${ARCH}. For SELPHY printing, use Raspberry Pi OS 64-bit (aarch64)."
fi
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
  cups \
  cups-client \
  printer-driver-gutenprint \
  curl \
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


echo "==> Configuring Wi-Fi Access Point (AP) via NetworkManager"
echo "    SSID: Photobooth (open / no password)"
echo "    AP IP: 192.168.4.1/24"

# Safety: switching wlan0 into AP mode will drop any existing Wi-Fi client connection.
# Require Ethernet (eth0) connectivity unless explicitly overridden.
if ! ip link show eth0 >/dev/null 2>&1; then
  echo "WARNING: eth0 not present. Ensure you have local console access before proceeding."
else
  if ! ip link show eth0 | grep -q "state UP"; then
    if [[ "${PHOTOBOOTH_ALLOW_NO_ETHERNET:-}" != "1" ]]; then
      echo "ERROR: eth0 is not UP. Connect Ethernet before enabling AP to avoid lockout."
      echo "       If you are on local console and accept the risk, re-run with: PHOTOBOOTH_ALLOW_NO_ETHERNET=1"
      exit 1
    fi
  fi
fi

# hostapd is used internally by NetworkManager for AP mode on Raspberry Pi OS / Raspbian.
apt-get install -y hostapd

# IMPORTANT: Do NOT run standalone dnsmasq when using NetworkManager 'ipv4.method shared'.
# If the dnsmasq package is installed, it can conflict and prevent clients from receiving an IP address.
if dpkg -s dnsmasq >/dev/null 2>&1; then
  echo "==> Removing standalone dnsmasq (conflicts with NetworkManager shared-mode DHCP)"
  systemctl stop dnsmasq >/dev/null 2>&1 || true
  systemctl disable dnsmasq >/dev/null 2>&1 || true
  apt-get purge -y dnsmasq
  echo "==> Restarting NetworkManager after dnsmasq removal"
  systemctl restart NetworkManager
fi

# Ensure nmcli is available (NetworkManager).
if ! command -v nmcli >/dev/null 2>&1; then
  echo "ERROR: nmcli (NetworkManager) not found. AP setup requires NetworkManager."
  exit 1
fi

# Recreate the AP connection deterministically (nmcli behavior varies by distro/version).

echo "==> Setting up SELPHY CP1500 printer queue (if connected)"
systemctl enable cups
systemctl restart cups

PRINTER_URI="$(lpinfo -v 2>/dev/null | awk '/usb:\/\/Canon\/SELPHY/ {print $2; exit}')"
if [[ -n "${PRINTER_URI}" ]]; then
  echo "    Found SELPHY URI: ${PRINTER_URI}"
  MODEL="$(lpinfo -m | awk 'BEGIN{IGNORECASE=1} /selphy/ && /cp1500/ {print $1; exit}')"
  if [[ -z "${MODEL}" ]]; then
    MODEL="$(lpinfo -m | awk 'BEGIN{IGNORECASE=1} /selphy/ && /cp1300/ {print $1; exit}')"
  fi
  if [[ -z "${MODEL}" ]]; then
    MODEL="$(lpinfo -m | awk 'BEGIN{IGNORECASE=1} /selphy/ && /cp1200/ {print $1; exit}')"
  fi

  if [[ -z "${MODEL}" ]]; then
    echo "    WARN: Could not find SELPHY Gutenprint model (lpinfo -m | grep -i selphy)."
  else
    echo "    Using model: ${MODEL}"
    lpadmin -x SELPHY_CP1500 >/dev/null 2>&1 || true
    lpadmin -p SELPHY_CP1500 -E -v "${PRINTER_URI}" -m "${MODEL}"
    cupsenable SELPHY_CP1500
    cupsaccept SELPHY_CP1500
    lpstat -t || true
  fi
else
  echo "    NOTE: SELPHY not detected. Plug it in and re-run step1_provision_pi.sh to create the queue."
fi


if nmcli -t -f NAME connection show | grep -qx "photobooth-ap"; then
  echo "==> Removing existing NetworkManager connection: photobooth-ap"
  nmcli connection delete photobooth-ap
fi

echo "==> Creating NetworkManager AP connection: photobooth-ap"
nmcli connection add type wifi ifname wlan0 con-name photobooth-ap autoconnect yes ssid Photobooth

echo "==> Configuring AP mode + shared IPv4"
nmcli connection modify photobooth-ap 802-11-wireless.mode ap
nmcli connection modify photobooth-ap 802-11-wireless.band bg
nmcli connection modify photobooth-ap ipv4.method shared
nmcli connection modify photobooth-ap ipv4.addresses 192.168.4.1/24

echo "==> Bringing up AP"
nmcli connection up photobooth-ap

echo "==> AP configured. Verify:"
echo "    - SSID visible: Photobooth"
echo "    - Pi AP IP: 192.168.4.1"
echo "    - Web UI: http://192.168.4.1:5000"
echo "    - SSH: ssh photobooth@192.168.4.1"
echo "==> Done."
echo "Next steps:"
echo "  1) Reboot: say 'sudo reboot' (USB group changes require re-login)"
echo "  2) Follow camera verification steps (lsusb, gphoto2 --auto-detect, gphoto2 --summary)"
