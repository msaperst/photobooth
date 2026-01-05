# Photobooth – Operator Runbook (Non‑Technical)

This guide is for **event operators**. No technical knowledge is required.

---

## 1. Event Setup (5 Minutes)

### Power On

1. Plug in and power on:
    - Printer
    - Camera
        - Plug Camera into Raspberry Pi
    - Raspberry Pi (photobooth box)
2. Wait ~1 minute

### Connect iPad

1. Wi‑Fi: **Photobooth** (no password)
2. Open browser
3. Go to: `http://192.168.4.1:5000`
4. Photobooth screen should appear

---

## 2. Printer Setup

1. Open printer tray
2. Load paper **glossy side UP**
3. Insert paper cartridge fully
4. Close tray firmly

If paper is loaded incorrectly, printing will fail.

---

## 3. Normal Operation

- Green / normal screen = everything is working
- Operator:
    1. Select number of prints
    2. Take photos
    3. Prints come out automatically

No action needed between guests.

---

## 4. Red Screen of Death (RSoD)

The screen turns **RED** only when action is required.

### 🔴 Photobooth Not Reachable

**Meaning:** Raspberry Pi (photobooth box) is off or Wi-Fi is down

**Fix:**

1. Make sure Raspberry Pi (photobooth box) is plugged in
2. Ensure red light is on
3. The green light should be blinking
4. Unplug then replug in the Raspberry Pi power cord

---

### 🔴 Printer Not Reachable

**Meaning:** Printer is off or disconnected

**Fix:**

1. Make sure printer is powered ON
2. Ensure printer is connected to **Photobooth** Wi-Fi
3. Wait 30 seconds
4. Printing will resume automatically

---

### 🔴 Printer Needs Attention

**Meaning:** Paper, ink, or tray issue

**Fix:**

The LCD on the printer should tell you what the problem is. If not check:

- Paper present (glossy side UP)
- Ink cartridge installed
- Tray fully inserted

Printing should resume automatically

---

### 🔴 Camera Error

**Meaning:** Camera power or cable issue

**Fix:**

1. Make sure camera is ON
2. Check camera USB cable
3. Wait ~10 seconds
4. Booth recovers automatically

---

### 🔴 Strip Creation Error

**Meaning:** Photos were successfully taken, but the system
failed while generating the photo strip or print image

**Fix:**

1. Tap the screen to acknowledge the error.
2. Restart the photobooth application.
3. Relaunch the UI on the iPad.
4. Resume operation.

If it happens again:

- Stop using the booth.
- Notify the technical operator.
- Do not continue running sessions until resolved.

Important notes:

- This is not caused by the camera.
- Photos from the failed session are still saved on disk.

---

## 5. Important Rules

- Fix **one issue at a time**
- Do **not** plug printer into Raspberry Pi (printer is Wi‑Fi)
- Do **not** change Wi‑Fi on iPad
- Do **not** reload paper matte‑side up

---

## 6. If Things Seem Stuck

1. Refresh browser on iPad
2. If still red:
    - Power cycle printer
    - Wait 30 seconds
3. If still stuck, contact technical support

---

If the screen is green, the booth is safe to use.

