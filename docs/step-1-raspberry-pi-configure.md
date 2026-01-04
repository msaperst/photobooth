# Step 1: Configure The Raspberry Pi

> **Automation available**
>
> All steps in this document can be performed automatically using:
> `deployment/scripts/step1_provision_pi.sh`
>
> The script encodes the steps below exactly. Manual execution is still documented for clarity and debugging.

Prerequisite:

- Clone the repo first (Step 0) so the scripts exist locally under `/opt/photobooth/deployment/scripts/`.

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
sudo apt install -y   gphoto2   libgphoto2-6t64   libgphoto2-dev   libusb-1.0-0   usbutils   git
```

Verify versions:

```bash
gphoto2 --version
```

You want libgphoto2 ≥ 2.5.x (Bookworm ships newer).

---

## 1.2 Camera Setup (Nikon D750)

### 1.2.1 Fix USB permissions

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

### 1.2.2 Physical camera configuration

Before plugging USB in, set these on the camera itself:

- Mode dial: M (Manual)
- Image quality: RAW+JPEG (preferred) or JPEG-only

  *note: “RAW-only will break strip creation unless you add RAW conversion.”*
- Wi-Fi: OFF
- Auto power off: Long / Disabled
- Live View: OFF (intentionally unused by the photobooth)
- Lens: AF-S or manual focus (your choice)

Power on camera and connect USB.

### 1.2.3 Verify USB detection

```bash
lsusb
```

Expected:

```bash
Bus 001 Device 006: ID 04b0:0437 Nikon Corp. Nikon DSC D750
```

If not:

- Cable issue
- Power issue
- Camera not on
-

### 1.2.4 Verify gphoto access

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

If USB claim errors occur:

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

### 1.2.5 Test capture

Run:

```bash
gphoto2 --capture-image-and-download   --filename test_%Y%m%d_%H%M%S_%n.%C
```

note: “Expect `.jpg` and `.nef` if RAW+JPEG enabled.”

Expected behavior:

- Shutter fires
- Image downloads to current directory
- File exists on Pi

Verify:

```bash
ls test_*.*
```

If this works → 🎉 camera integration at OS level is DONE

```bash
rm test_*.*
```

---

## 1.3 Wi‑Fi Access Point (AP)

This configures the Pi to broadcast an **open (password‑free)** Wi‑Fi network for guests and the iPad to connect to at
events.

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

### 1.3.1 Verify current network state

```bash
nmcli device status
```

Expected during setup:

- `eth0` is **connected**
- `wlan0` is currently connected to your home Wi‑Fi (client mode) OR disconnected

### 1.3.2 Install required package

```bash
sudo apt update
sudo apt install -y hostapd
```

### 1.3.3 Ensure standalone dnsmasq is NOT installed (critical)

```bash
sudo systemctl stop dnsmasq || true
sudo systemctl disable dnsmasq || true
sudo apt purge -y dnsmasq
```

### 1.3.4 Create the AP connection (NetworkManager)

```bash
sudo nmcli connection add   type wifi   ifname wlan0   con-name photobooth-ap   autoconnect yes   ssid Photobooth
```

### 1.3.5 Configure AP mode + DHCP + static AP IP

```bash
sudo nmcli connection modify photobooth-ap 802-11-wireless.mode ap
sudo nmcli connection modify photobooth-ap 802-11-wireless.band bg
sudo nmcli connection modify photobooth-ap ipv4.method shared
sudo nmcli connection modify photobooth-ap ipv4.addresses 192.168.4.1/24
```

### 1.3.6 Bring the AP up

```bash
sudo nmcli connection up photobooth-ap
```

Verify:

```bash
ip addr show wlan0
```

### 1.3.7 Verify from a client

- Connect to Wi‑Fi network: `Photobooth`
- Open: `http://192.168.4.1:5000`
- Optional SSH:

```bash
ssh photobooth@192.168.4.1
```

### 1.3.8 Reboot persistence test

```bash
sudo reboot
```

Ensure you can still connect

## 1.10 Printer Setup (Canon SELPHY CP1500)

The photobooth uses **driverless IPP Everywhere printing over Wi-Fi**.

The SELPHY **does not connect over USB**.  
Instead, the printer joins the Raspberry Pi’s Wi-Fi Access Point and is discovered automatically by CUPS via mDNS.

This approach is:

- Reliable
- Reboot-safe
- Driverless
- Supported by Canon firmware
- Fully compatible with the Pi running as an AP

---

### 1.10.1 Prepare the printer (on the device)

On the Canon SELPHY CP1500 touchscreen:

1. Power on the printer
2. Open **Settings**
3. Go to **Wi‑Fi Settings**
4. Select **Connection Settings**
5. Choose **Other**
6. Select **Via Wireless Router**
7. From the network list, select:
   Photobooth
8. Confirm connection

When complete, the printer will show as connected to the Photobooth network.

Recommended printer settings:

- Disable Power Save / Auto Power Off
- Leave paper size and color defaults unchanged (controlled by CUPS)

---

### 1.10.2 Verify network visibility on the Pi

```bash
ip neigh | grep 192.168.4.
```

Expected:

- Printer IP visible on wlan0 (e.g. 192.168.4.205)

Verify mDNS advertisement:

```bash
avahi-browse -avtr | grep -i selphy
```

Expected services:

- Internet Printer
- Secure Internet Printer
- Web Site
- _canon-cpp-disc._udp

---

### 1.10.3 Add the printer to CUPS (driverless)

Confirm discovery:

```bash
sudo lpinfo -v | grep ipp
```

Expected entry:
dnssd://Canon%20SELPHY%20CP1500._ipp._tcp.local/

Add printer:

```bash
sudo lpadmin \
  -p Canon_SELPHY_CP1500 \
  -E \
  -v "dnssd://Canon%20SELPHY%20CP1500._ipp._tcp.local/" \
  -m everywhere
```

Enable and accept jobs:

```bash
sudo cupsenable Canon_SELPHY_CP1500
sudo cupsaccept Canon_SELPHY_CP1500
```

Set defaults:

```bash
sudo lpoptions -p Canon_SELPHY_CP1500 \
  -o media=jpn_hagaki_100x148mm \
  -o print-color-mode=color \
  -o sides=one-sided
```

---

### 1.10.4 Verify printer state

```bash
lpstat -p
```

Expected:
printer Canon_SELPHY_CP1500 is idle. enabled

---

### 1.10.5 Non-destructive queue test

```bash
lp -d Canon_SELPHY_CP1500 /etc/hosts
sudo cancel -a Canon_SELPHY_CP1500
```

Verifies:

- Job submission
- Queue handling
- Cancellation
- Printer communication

---

### 1.10.6 Real print test

```bash
lp -d Canon_SELPHY_CP1500 \
  -o media=jpn_hagaki_100x148mm \
  -o fit-to-page \
  /path/to/print.jpg
```

Printing is now production-ready.