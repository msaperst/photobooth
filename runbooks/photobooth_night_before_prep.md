# Photobooth – Night Before Prep Checklist

This checklist is for **the day or night before an event**. It is designed to prevent the most common event-day
failures.

---

## 1. Software & Configuration Updates

Do these **before leaving home**.

- Create album for event with **album code**
- Update **album code** for the event (in `/etc/photobooth.env`)
- Update **event logo / strip logo** (in `/etc/photobooth.env`)
    - Confirm logo renders correctly on a test strip
- Restart photobooth service
    - Confirm UI loads at `http://192.168.4.1:5000`
- Run a **full test session**
    - Take photos
    - Confirm strip generation
    - Confirm QR code on iPad downloads strip
    - Confirm printing works end-to-end
    - Confirm QR code on print goes to new album

---

## 2. Charge Everything

Charge to 100% where possible.

- iPad
- Camera batteries (at least 2)
- External battery packs (if using any)

---

## 3. Printer Prep

- Verify printer powers on
- Load **fresh paper + ink cartridge**
    - Paper must be **glossy side UP**
- Pack **extra paper/ink cartridges**
- Test a print from the photobooth

---

## 4. Camera Prep

- Camera powers on
- Camera captures correctly
- Camera date/time correct
- Camera storage card installed
- Camera settings are correct
    - Mode dial: M (Manual)
    - Image quality: RAW+JPEG (preferred) or JPEG-only
    - Wi-Fi: OFF
    - Auto power off: Long / Disabled
    - USB mode: (Nikon auto-detects, no menu option needed)
    - Live View: OFF (intentionally unused by the photobooth)
    - Lens: AF-S or manual focus (your choice)
- Pack:
    - Extra camera batteries
    - Battery charger

---

## 5. Pack Hardware (Do Not Skip)

### Required

- Raspberry Pi (photobooth box)
- Power cable for Pi
- Printer
- Printer power cable
- Camera
- Camera USB cable
- Camera batteries + charger
- iPad
- iPad charger

### Strongly Recommended

- Extension cord
- Power strip
- Gaffer tape
- Small screwdriver
- Lens cloth
- Backup USB cable for camera

---

## 6. Final Sanity Check

- All devices power on
- You know where everything is packed
- Paper is packed **separately** and protected
- This checklist is printed or saved offline

---

If this checklist is completed, event-day setup should be smooth.

