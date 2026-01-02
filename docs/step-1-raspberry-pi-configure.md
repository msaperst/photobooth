> **Automation available**
>
> All steps in this document can be performed automatically using:
> `deployment/scripts/step1_configure_pi.sh`
>
> The script encodes the steps below exactly. Manual execution is still documented for clarity and debugging.

# Step 1: Configure The Raspberry Pi

---

## 1.0 Create a dedicated photobooth user

Run the service as a dedicated non-root user.

```bash
sudo adduser photobooth
```

Add the photobooth user to the groups needed for USB camera access (and later, printing):

```bash
sudo usermod -aG plugdev,video,dialout photobooth
```

Reboot to ensure group membership and udev rules apply cleanly:

```bash
sudo reboot
```

After reboot, confirm:

```bash
groups photobooth
```

---
## 1.1 Update Raspberry Pi and install dependencies

Install the basic dependencies

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y \
  gphoto2 \
  libgphoto2-6t64 \
  libgphoto2-dev \
  libusb-1.0-0 \
  usbutils \
  git
```

Verify versions:

```bash
gphoto2 --version
```

You want libgphoto2 ≥ 2.5.x (Bookworm ships newer).

---

## 1.2 Fix USB Permissions

### 1.2.1 Install / verify gphoto udev rules

Check if rules exist:

```bash
ls /lib/udev/rules.d/ | grep gphoto
```

If you see `60-libgphoto2-6t64.rules`, good

### 1.2.2 Add your user to required groups

```bash
sudo usermod -aG plugdev,video,dialout ${USER}
```

Log out and back in (or reboot):

```bash
sudo reboot
```

After reboot:

```bash
groups
```

You must see:

```bash
plugdev video dialout
```

---

## 1.3 Camera physical setup (important)

Before plugging USB in, set these on the camera itself:

#### Nikon D750 settings checklist

On the camera body:

- Mode dial: M (Manual)
- Image quality: RAW+JPEG (preferred) or JPEG-only

  *note: “RAW-only will break strip creation unless you add RAW conversion.”*
- Wi-Fi: OFF
- Auto power off: Long / Disabled
- USB mode: (Nikon auto-detects, no menu option needed)
- Live View: OFF (intentionally unused by the photobooth)
- Lens: AF-S or manual focus (your choice)

Power ON the camera.

Now plug USB → Pi.

---

## 1.4 Verify USB sees the camera

```bash
lsusb
```

You should see something like:

```bash
Bus 001 Device 006: ID 04b0:0437 Nikon Corp. Nikon DSC D750
```

If not:

- Cable issue
- Power issue
- Camera not on

Stop here if missing.

---

## 1.5 Verify gphoto detection (no sudo)

```bash
gphoto2 --auto-detect
```

Expected:

```bash
Model            Port
---------------------------------------
Nikon DSC D750   usb:001,006
```

If this fails → permissions not correct → go back to 1.2

---

## 1.6 Verify camera communication

```bash
gphoto2 --summary
```

This should now work without sudo.

You should see:

- Battery level
- Image size
- Storage info

If this fails:

- You may have a permissions issue
- Do NOT proceed until this works

*If you get an error about not being able to claim the USB device*,
this is the #1 most common gphoto2 failure on desktop Linux.

Run:

```bash
gsettings set org.gnome.desktop.media-handling automount false
gsettings set org.gnome.desktop.media-handling automount-open false
```

Then log out and back in (or reboot).

This prevents:

- camera mounting
- file manager interception
- gphoto conflicts

Reboot the device and return the summary command. It should now work

If it still doesn't work, try the below commands

```bash
systemctl --user mask gvfs-gphoto2-volume-monitor.service
systemctl --user stop gvfs-gphoto2-volume-monitor.service
```

---

## 1.7 Test capture (critical checkpoint)

Run:

```bash
gphoto2 --capture-image-and-download \
  --filename test_%Y%m%d_%H%M%S_%n.%C
```

note: “Expect `.jpg` and `.nef` if RAW+JPEG enabled.”

Expected behavior:

- Shutter fires
- Image downloads to current directory
- File exists on Pi

Verify:

```bash
ls -lh *.jpg
```

If this works → 🎉 camera integration at OS level is DONE

---

## 1.8 Clean up test files

```bash
rm test_*.jpg
```


---

## 1.9 Configure Raspberry Pi as Wi‑Fi Access Point (AP)

This configures the Pi to broadcast an **open (password‑free)** Wi‑Fi network for guests and the iPad to connect to at events.

Design:
- Wi‑Fi (`wlan0`) runs as an AP only
- Ethernet (`eth0`) remains the management interface (SSH during setup)
- SSID: `Photobooth`
- Security: open (no password)
- Subnet: `192.168.4.0/24`
- Pi IP (gateway): `192.168.4.1`
- Photobooth web UI will be reachable at: `http://192.168.4.1:5000`

Safety:
- **Do not run these steps over Wi‑Fi.** You will disconnect `wlan0` from client mode.
- Ensure you are connected via **Ethernet** (recommended) or have local console access.

### 1.9.1 Verify current network state

```bash
nmcli device status
```

Expected during setup:
- `eth0` is **connected**
- `wlan0` is currently connected to your home Wi‑Fi (client mode) OR disconnected

### 1.9.2 Install required package

```bash
sudo apt update
sudo apt install -y hostapd
```

### 1.9.3 Ensure standalone dnsmasq is NOT installed (critical)

```bash
sudo systemctl stop dnsmasq || true
sudo systemctl disable dnsmasq || true
sudo apt purge -y dnsmasq
```

### 1.9.4 Create the AP connection (NetworkManager)

```bash
sudo nmcli connection add   type wifi   ifname wlan0   con-name photobooth-ap   autoconnect yes   ssid Photobooth
```

### 1.9.5 Configure AP mode + DHCP + static AP IP

```bash
sudo nmcli connection modify photobooth-ap 802-11-wireless.mode ap
sudo nmcli connection modify photobooth-ap 802-11-wireless.band bg
sudo nmcli connection modify photobooth-ap ipv4.method shared
sudo nmcli connection modify photobooth-ap ipv4.addresses 192.168.4.1/24
```

### 1.9.6 Bring the AP up

```bash
sudo nmcli connection up photobooth-ap
```

Verify:

```bash
ip addr show wlan0
```

### 1.9.7 Verify from a client

- Connect to Wi‑Fi network: `Photobooth`
- Open: `http://192.168.4.1:5000`
- Optional SSH:

```bash
ssh photobooth@192.168.4.1
```

### 1.9.8 Reboot persistence test

```bash
sudo reboot
```
