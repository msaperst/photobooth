# Step 0: Raspberry Pi Base Setup

This document describes how to provision a **fresh Raspberry Pi** with Raspberry Pi OS, configure Wi‑Fi, and enable remote access.

These steps apply whether:

* You are setting up a brand new Pi
* You are re-imaging an existing Pi
* You are recovering from a broken system before an event

---

## 0.1 Install Raspberry Pi OS

1. Download **Raspberry Pi Imager**:
   [https://www.raspberrypi.com/software/](https://www.raspberrypi.com/software/)

2. Insert an SD card (16GB+ recommended)

3. In Raspberry Pi Imager:

   * Choose **Raspberry Pi OS (32-bit)**
   * Choose the SD card

4. **Before writing**, open *Advanced Settings* (⚙️):

   * Set hostname (e.g. `photobooth`)
   * Enable SSH
   * Set username/password
   * Configure Wi‑Fi:

     * SSID
     * Password
     * Country

5. Write the image and eject the SD card

---

## 0.2 First Boot

1. Insert SD card into Raspberry Pi
2. Power on
3. Wait ~1–2 minutes for boot and Wi‑Fi connection
4. SSH into the Pi:

```bash
ssh <username>@photobooth.local
```

(or use the IP assigned by your router)

---

## 0.3 Update System

```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```

---

## 0.4 Enable Required Interfaces

```bash
sudo raspi-config
```

Ensure:

* SSH: Enabled
* WLAN Country: Set correctly

Reboot if prompted.

---

## 0.5 Wi‑Fi Configuration (Important)

### Automatic Wi‑Fi (Preferred)

Wi‑Fi credentials configured in Raspberry Pi Imager will auto‑connect on boot.

### Manually Updating Wi‑Fi (Existing System)

If the Pi is already set up but tries to connect to an **old SSID**:

```bash
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
```

Update or add:

```text
network={
    ssid="NEW_WIFI_SSID"
    psk="NEW_WIFI_PASSWORD"
}
```

Apply changes:

```bash
sudo wpa_cli -i wlan0 reconfigure
```

Or reboot:

```bash
sudo reboot
```

This allows Wi‑Fi changes without moving the Pi near the router.

---

## 0.6 Verify Connectivity

```bash
ip a show wlan0
ping -c 3 google.com
```

(Internet is not required long‑term, but useful during setup.)

---

## Notes

* Raspberry Pi OS is used for maximum compatibility with:

  * gphoto2
  * USB camera access
  * CUPS printing
* Containerization is intentionally avoided at this stage
* Later steps will configure the Pi as a **Wi‑Fi access point** for offline events
