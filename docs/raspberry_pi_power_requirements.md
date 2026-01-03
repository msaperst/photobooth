# Raspberry Pi Power Requirements (IMPORTANT)

## Summary
The Raspberry Pi **must** be powered by a **stable, Pi-rated power supply**.  
Undervoltage causes USB instability, device resets, and intermittent failures that look like software bugs.

This project **will not behave reliably** if powered from:
- USB ports on power strips or extension cords
- Phone chargers
- Laptop USB ports
- Multi-port “fast charging” bricks

---

## Required Power Supply

**Use one of the following only:**

- **Official Raspberry Pi power supply**
  - 5.1 V
  - 2.5 A (Raspberry Pi 3)
  - Micro-USB connector

OR

- A *single-port* wall adapter rated:
  - **5.1–5.2 V**
  - **≥ 3 A**
  - Short, high-quality micro-USB cable (≤ 1 m)

> The official Raspberry Pi supply is strongly recommended and was used for hardware validation.

---

## Why This Matters

The Photobooth system runs multiple high-load components simultaneously:

- Wi‑Fi access point (NetworkManager AP mode)
- Nikon D750 over USB (RAW + JPEG capture)
- Canon Selphy CP1500 over USB (printing)
- Flask + gunicorn + systemd
- Continuous USB I/O during printing

If the Pi’s 5V rail drops below tolerance, the kernel reports:

```
Undervoltage detected!
```

When this happens:
- USB devices may disconnect or re-enumerate
- Printers may appear and disappear
- Print jobs may fail or hang
- CUPS errors may occur
- Camera capture may become unreliable

These failures are **electrical**, not software bugs.

---

## How to Verify Power Is Healthy

After booting the Pi with all devices connected:

```bash
dmesg -T | grep -i voltage
```

**Expected result:**
- No output

If you see:
```
Undervoltage detected!
```
the power supply is insufficient and must be replaced before proceeding.

---

## Known Bad Configurations (Do Not Use)

The following are known to cause undervoltage and USB instability:

- Power strip or extension cord USB outlets
- “Fast charging” phone chargers
- Multi-port USB charging hubs
- USB‑C → micro‑USB adapters
- Long or thin USB cables
- Shared power supplies for multiple devices

Even if these appear to “work”, they cause intermittent failures under load.

---

## Event Setup Checklist (Power)

Before an event:
- Pi powered from official or Pi‑rated supply
- Printer powered from its own AC adapter
- No undervoltage warnings in `dmesg`
- USB devices enumerate once and remain stable

Power issues must be resolved **before** debugging printer, camera, or CUPS behavior.

---

## Design Note

Power stability is a **hard requirement** for this system.

If the Pi reports undervoltage:
- Printer errors are not considered valid
- Camera errors may be misleading
- Health checks may report cascading failures

Always fix power first.
