# Photobooth – Technical Troubleshooting Guide

This guide is for **technical support** when non‑technical fixes fail.

---

## 1. First Steps (Always Try These)

1. Power cycle printer
2. Wait 30 seconds
3. Refresh iPad browser
4. Confirm camera and printer are powered on

---

## 2. Connect to the Photobooth System

### Wi‑Fi

- SSID: **Photobooth**
- No password

### SSH

```bash
ssh pi@192.168.4.1
```

---

## 3. Check System Status

```bash
curl http://localhost:5000/health
curl http://localhost:5000/status
```

- Health ERROR will indicate owner (camera / printer)
- Status shows busy state and session info

---

## 4. Printer Troubleshooting

### Check Printer Queue

```bash
lpstat -p
lpstat -v
```

### Restart Printing System

```bash
sudo systemctl restart cups
```

### Check Printer Reachability

```bash
ipptool -tv ipp://<printer-host>/ipp/print get-printer-attributes.test
```

### Avahi / mDNS Printer Discovery Troubleshooting

The photobooth uses **IPP Everywhere over Wi-Fi** with **Avahi (mDNS)** for printer discovery.

This section covers diagnosing printer discovery issues when the printer does not appear in CUPS.

---

#### Verify Avahi Is Running

```bash
systemctl status avahi-daemon
```

If not running or unhealthy:

```bash
sudo systemctl restart avahi-daemon
```

---

#### Browse for IPP Services

List discovered IPP printers:

```bash
avahi-browse -rt _ipp._tcp
```

List all discovered services (verbose):

```bash
avahi-browse -rav
```

##### Expected Behavior

- Canon printer appears as an `_ipp._tcp` service
- Service resolves to an IP on the Photobooth subnet (e.g. `192.168.4.x`)

---

#### If the Printer Does Not Appear

1. Confirm the printer is connected to the **Photobooth Wi‑Fi network**
2. Power cycle the printer
3. Restart Avahi:

```bash
sudo systemctl restart avahi-daemon
```

4. Restart CUPS if needed:

```bash
sudo systemctl restart cups
```

---

#### Notes

- Printer discovery relies on mDNS; it will not work across subnets
- USB printing is not supported
- Do not install `ipp-usb`, Gutenprint drivers, or vendor PPDs

---

## 5. Camera Troubleshooting

### Detect Camera

```bash
gphoto2 --auto-detect
```

If missing:

- Power cycle camera
- Replug USB

---

## 6. Restart Photobooth Service

```bash
sudo systemctl restart photobooth
```

---

## 7. Recovery Rules (Important)

- Camera fixes clear camera errors only
- Printer fixes clear printer errors only
- Errors are sticky until the owning component recovers
- Pending prints are queued and resume automatically

---

## 8. Known Gotchas

- Printer paper must be **glossy side UP**
- Two strips = one print (expected behavior)
- Do not change Wi‑Fi during operation

---

If issues persist after these steps, escalate.

---

## Health Code Reference

The `PhotoboothController` is the single source of truth for system health.
Each error has a clear owner. **Only the component that raised the error may clear it.**

| Health Code             | Owner            | Recoverable | Meaning                                                      |
|-------------------------|------------------|-------------|--------------------------------------------------------------|
| `CONFIG_INVALID`        | Configuration    | No          | Required runtime configuration is missing or invalid         |
| `CAMERA_NOT_DETECTED`   | Camera           | Yes         | Camera is not detected by `gphoto2`                          |
| `CAMERA_DISCONNECTED`   | Camera           | Yes         | Camera was previously available but disconnected mid-session |
| `STRIP_CREATION_FAILED` | Image Processing | No          | Photos captured, but strip or print asset generation failed  |
| `UNKNOWN_ERROR`         | Controller       | No          | An unexpected exception occurred                             |

---

### CONFIG_INVALID

**Owner:** Configuration  
**Recoverable:** No

#### Common Causes

- `/etc/photobooth.env` missing
- `PHOTOBOOTH_IMAGE_ROOT` not set or not writable
- `PHOTOBOOTH_ALBUM_CODE` missing
- `PHOTOBOOTH_LOGO_PATH` missing or file does not exist

#### Resolution

1. Fix `/etc/photobooth.env`
2. Verify all required variables are present and correct
3. Restart the service:

```bash
sudo systemctl restart photobooth
```

---

### CAMERA_NOT_DETECTED

**Owner:** Camera  
**Recoverable:** Yes

#### Common Causes

- Camera powered off
- USB cable disconnected
- Dead battery

#### Resolution

- Power on camera
- Reseat USB cable
- Replace or recharge battery

The error clears automatically once the camera is detected.

---

### CAMERA_DISCONNECTED

**Owner:** Camera  
**Recoverable:** Yes

#### Common Causes

- Loose USB cable
- Camera powered off
- Battery failure

#### Resolution

- Reconnect camera
- Power cycle camera if needed

The error clears automatically once the camera reconnects.

---

### STRIP_CREATION_FAILED

**Owner:** Image Processing  
**Recoverable:** No

#### Meaning

JPEG images were captured successfully, but strip or print asset generation failed.

#### Common Causes

- Invalid or missing logo file
- Unexpected image processing error
- Filesystem write failure

#### Resolution

1. Restart the photobooth service:

```bash
sudo systemctl restart photobooth
```

2. If the error repeats:
    - Verify the logo file exists and is readable
    - Verify `PHOTOBOOTH_IMAGE_ROOT` is writable
    - Review logs:

```bash
journalctl -u photobooth
```

---

### UNKNOWN_ERROR

**Owner:** Controller  
**Recoverable:** No

#### Resolution

- Restart the photobooth service
- Inspect logs for details