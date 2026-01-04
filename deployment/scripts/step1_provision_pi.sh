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
  libgphoto2-dev \
  libusb-1.0-0 \
  usbutils \
  cups \
  cups-client \
  cups-filters \
  avahi-daemon \
  avahi-utils \
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

echo ""
echo "==> Camera quick verification"
echo "    Plug in the Nikon D750 via USB and power it on."
echo "    (If you see 'could not claim the device', see the NOTE above.)"
read -r -p "Press Enter to run camera detection (or Ctrl+C to abort)..." _

set +e
sudo -u photobooth -H gphoto2 --auto-detect
AUTO_DETECT_RC=$?
sudo -u photobooth -H gphoto2 --summary
SUMMARY_RC=$?
set -e

if [[ $AUTO_DETECT_RC -ne 0 || $SUMMARY_RC -ne 0 ]]; then
  echo "WARNING: Camera verification did not succeed (auto-detect rc=$AUTO_DETECT_RC, summary rc=$SUMMARY_RC)."
  echo "         If you are on a desktop environment, the gvfs steps above usually fix 'could not claim the device'."
  echo "         Otherwise, confirm the camera is in the correct USB mode and try a different USB port/cable."
else
  echo "    Camera verification OK."
fi


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
# If you have made manual tweaks in production and don't want this script to overwrite them,
# re-run with: PHOTOBOOTH_PRESERVE_AP=1
if nmcli -t -f NAME connection show | grep -qx "photobooth-ap"; then
  if [[ "${PHOTOBOOTH_PRESERVE_AP:-}" == "1" ]]; then
    echo "==> Preserving existing NetworkManager connection: photobooth-ap (PHOTOBOOTH_PRESERVE_AP=1)"
  else
    echo "==> Removing existing NetworkManager connection: photobooth-ap"
    nmcli connection delete photobooth-ap
  fi
fi

if ! nmcli -t -f NAME connection show | grep -qx "photobooth-ap"; then
  echo "==> Creating NetworkManager AP connection: photobooth-ap"
  nmcli connection add type wifi ifname wlan0 con-name photobooth-ap autoconnect yes ssid Photobooth
else
  echo "==> Using existing NetworkManager AP connection: photobooth-ap"
fi

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
echo "    - SSH: ssh photobooth@192.168.4.1"


echo
echo "==> Enabling CUPS + mDNS (for SELPHY Wi-Fi / AirPrint discovery)..."
systemctl enable --now cups avahi-daemon

# cups-browsed can auto-create queues and implicit classes, which gets confusing.
# We manage the SELPHY queue explicitly.
if systemctl list-unit-files | awk '{print $1}' | grep -qx 'cups-browsed.service'; then
  systemctl stop cups-browsed || true
  systemctl disable cups-browsed || true
fi

if [[ "${PHOTOBOOTH_SKIP_PRINTER:-}" != "1" ]]; then
  echo
  echo "==> Printer setup (Canon SELPHY CP1500 over Wi-Fi / AirPrint)"
  echo "    This step requires you to connect the SELPHY to the Photobooth AP."
  echo
  echo "    On the printer:"
  echo "      Wi‑Fi settings -> Connection Settings -> Other -> Via wireless router"
  echo "      Select SSID: Photobooth"
  echo
  read -r -p "Press ENTER once the printer shows as connected... " _

  echo "==> Waiting for SELPHY to appear via DNS-SD..."
  for _ in {1..30}; do
    if lpinfo -v 2>/dev/null | grep -q 'dnssd://Canon%20SELPHY%20CP1500\._ipp\._tcp\.local/'; then
      break
    fi
    sleep 2
  done

  if ! lpinfo -v 2>/dev/null | grep -q 'dnssd://Canon%20SELPHY%20CP1500\._ipp\._tcp\.local/'; then
    echo "WARNING: SELPHY not discovered via DNS-SD (yet)."
    echo "  - Confirm the printer is connected to the Photobooth SSID"
    echo "  - Power cycle the printer"
    echo "  - Run: avahi-browse -avtr | grep -i selphy"
    echo
    if [[ "${PHOTOBOOTH_REQUIRE_PRINTER:-}" == "1" ]]; then
      echo "ERROR: PHOTOBOOTH_REQUIRE_PRINTER=1 set; failing provisioning because printer is required."
      exit 1
    fi
    echo "==> Skipping printer queue creation for now (re-run later once the printer is discoverable)."
    echo "    Tip: re-run with PHOTOBOOTH_REQUIRE_PRINTER=1 once you expect it to be online."
    echo "==> Done."
    exit 0
  fi

  if lpstat -p Canon_SELPHY_CP1500 >/dev/null 2>&1; then
    echo "==> CUPS queue already exists: Canon_SELPHY_CP1500"
  else
    echo "==> Creating CUPS queue: Canon_SELPHY_CP1500"
    lpadmin \
      -p Canon_SELPHY_CP1500 \
      -E \
      -v "dnssd://Canon%20SELPHY%20CP1500._ipp._tcp.local/" \
      -m everywhere
  fi
  cupsenable Canon_SELPHY_CP1500
  cupsaccept Canon_SELPHY_CP1500

  echo "==> Setting defaults (Postcard, color, one-sided)"
  lpoptions -p Canon_SELPHY_CP1500 \
    -o media=jpn_hagaki_100x148mm \
    -o print-color-mode=color \
    -o sides=one-sided

  echo "==> Quick queue sanity check (submits a HELD job then cancels; should NOT print)"
  # Capture the job id so we only cancel what we just submitted.
  JOB_ID=$(lp -d Canon_SELPHY_CP1500 -o job-hold-until=indefinite /etc/hosts 2>/dev/null | awk '{print $4}' | tr -d '()')
  lpstat -o || true
  if [[ -n "${JOB_ID:-}" ]]; then
    cancel "${JOB_ID}" || true
  else
    # Fallback (should be rare): cancel everything on this queue.
    cancel -a Canon_SELPHY_CP1500 || true
  fi
  echo "==> Printer queue configured."
fi

echo "==> Done."
echo "Next steps:"
echo "  1) Reboot: say 'sudo reboot' (USB group changes require re-login)"
echo "  2) If you skipped camera verification, run: gphoto2 --auto-detect && gphoto2 --summary"