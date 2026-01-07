# Photobooth – Operator Runbook (Non‑Technical)

This guide is for **event operators**. No technical knowledge is required.

> When in doubt, wait 10–30 seconds after fixing something — most issues clear automatically.
---

## 1. Event Setup (5 Minutes)

### Power On

1. Plug in and power on:
    - **Raspberry Pi (using Pi rated power supply)**
    - **Printer**
    - **Camera**
        - Plug the camera into the Raspberry Pi using only **USB cable (USB A → Mini-B)**
        - One end goes into the **bottom front port on the left side of the camera**
        - The other end goes into **any USB port on the Raspberry Pi**

2. Wait ~1 minute for everything to boot

**Notes:**

- Only **one USB cable** should connect the camera to the Pi
- Do **not** connect the printer via USB

### Connect iPad

1. Wi‑Fi: **Photobooth** (no password)
2. Open browser (Safari or Chrome)
3. Go to: `http://192.168.4.1:5000`
4. Photobooth screen should appear

If the page does not load, refresh once and wait ~10 seconds.

---

## 2. Printer Setup

### Paper (start with a full paper tray)

1. Open printer tray
2. Load paper **glossy side UP**
3. Insert paper cartridge fully
4. Close tray firmly

If paper is loaded incorrectly, printing will fail.

### Ink Reload (when prompted by printer)

1. Open the ink compartment on the printer
2. Remove the empty ink cartridge
3. Insert the new cartridge until it clicks
4. Close the compartment
5. Wait for the printer to finish initializing

Follow on‑screen instructions on the printer if shown.

### Wi‑Fi Check (important)

The printer **must** be connected to the **Photobooth** Wi‑Fi network.

On the printer screen, verify the Wi-Fi icon (ᯤ) is shown next to the SSID **Photobooth**.

If it is not, reconnect the printer to **Photobooth**:

1. Open **Settings**
2. Go to **Wi‑Fi Settings**
3. Select **Connection Settings**
4. Choose **Other**
5. Select **Via Wireless Router**
6. From the network list, select:
   Photobooth
7. Confirm connection (see above)
8. Wait ~30 seconds after reconnecting

---

## 3. Normal Operation

- Green / normal screen = everything is working
- Operator flow:
    1. Select number of prints
    2. Take photos
    3. Prints come out automatically

No action is needed between guests.
> _Note_: Printing may start a few seconds after the last photo.

> ⚠️ **Important – Printer Handling**
>
> The printer uses a multi-pass printing process (it will pull the photo in and out several times).
> 
> **Do NOT let guests touch or pull the print until the printer is completely finished and releases it on its own.**
> 
> Pulling the print early will ruin the photo and may damage the printer.

### Finished Prints

Each print comes out as **one sheet containing two strips**.

- The operator should **cut the print in half** using a paper cutter or scissors.
- Do this **only after the printer is completely finished** and releases the print.
  
---

## 4. Red Screen of Death (RSoD)

The screen turns **RED** only when action is required.

### 🔴 Photobooth Not Reachable

**Meaning:** Raspberry Pi is off or Wi‑Fi is down

**Fix:**

1. Make sure Raspberry Pi is plugged in
2. Ensure red power light is on
3. The green activity light should be blinking
4. Restart the photobooth application (see #5 below)
5. Error should clear within ~60 seconds

### 🔴 Printer Not Reachable

**Meaning:** Printer is off or disconnected from Wi‑Fi

**Fix:**

1. Make sure printer is powered ON
2. Confirm printer is connected to **Photobooth** Wi‑Fi (see instructions above)
3. Wait 30 seconds
4. Error should clear within ~10–30 seconds

Printing will resume automatically once reconnected.

### 🔴 Printer Needs Attention

**Meaning:** Paper, ink, or tray issue

**Fix:**

The printer screen will usually show the problem. Common things to check:

- Paper present (glossy side UP)
- Ink cartridge installed correctly
- Tray fully inserted

Once fixed, error should clear within ~10–30 seconds and printing should resume automatically.

### 🔴 Camera Error

**Meaning:** Camera power or cable issue

**Fix:**

1. Make sure camera is ON
2. Check the USB cable between camera and Raspberry Pi
3. Reseat the cable on both ends
4. Wait ~10 seconds
5. Error should clear within ~10–30 seconds

The booth will recover automatically.

### 🔴 Strip Creation Error

**Meaning:** Photos were successfully taken, but the system failed while generating the photo strip or print image

**Fix:**

1. Read and follow the error message on screen (no button press is required)
2. Restart the photobooth application (see #5 below)
3. Relaunch the UI on the iPad
4. Resume operation

If it happens again:

- Stop using the booth
- Notify the technical operator
- Do not continue running sessions

Important notes:

- This is **not** caused by the camera
- Photos from the failed session are still saved

---

## 5. How to Restart the Photobooth Application

1. Power cycle the **Raspberry Pi**:
    - Unplug the Raspberry Pi power cable
    - Wait 10 seconds
    - Plug it back in
2. Wait ~1 minute for startup to complete

This automatically restarts the photobooth application. This is a safe
operation, and will **not** delete photos or break the system.

---

## 6. How to Relaunch the UI on the iPad

1. Close the browser tab
2. Reopen the browser
3. Go to: `http://192.168.4.1:5000`
4. Confirm the photobooth screen loads

If needed, you may also refresh the page.

---

## 7. Important Rules

- Fix **one issue at a time**
- Do **not** plug printer into Raspberry Pi (printer is Wi‑Fi)
- Do **not** change Wi‑Fi on iPad
- Do **not** load paper matte‑side up
- Do **not** allow guests to touch or pull prints while the printer is printing

---

## 8. If Things Seem Stuck

1. Refresh browser on iPad
2. If still red:
    - Power cycle printer
    - Power cycle camera
    - Wait 30 seconds
3. If still stuck
    - Power cycle Raspberry Pi
4. If issues still persist, do not continue restarting devices
   repeatedly - stop and contact technical support

---

If the screen is green, the booth is safe to use.
