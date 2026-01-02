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

# TODO

- configure system to be wifi hotspot