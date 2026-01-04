# Photobooth v2

This repository contains **Photobooth v2**, an event‑grade, unattended‑capable photobooth system built around:

* **Raspberry Pi (Raspbian)** as the system controller
* **Nikon D750** tethered via USB (gphoto2)
* **Canon Selphy ES30** (prototype) → **Canon Selphy CP1300/CP1500** (production)
* **iPad** as a fixed touchscreen UI (web‑based, no native app)

The system is designed to be **offline‑capable**, **reproducible from scratch**, and **robust under real event
conditions**.

> An important note about
> [powering the Raspberry Pi](docs/raspberry_pi_power_requirements.md)

---

## Design Goals

* No operator required for normal operation
* Single, authoritative hardware controller (no race conditions)
* Offline operation (no internet required)
* Guests receive clear feedback (countdown, progress, and error states)
* Easy reprints and recovery when something goes wrong
* Fully documented so the system can be rebuilt under pressure

---

## High‑Level Architecture

### Core Principle

> **Only one process ever touches hardware.**
> UI and networking layers request actions but never directly control the camera or printer.

### Component Roles

**iPad (UI only)**

* Touchscreen controls
* Countdown display
* Print count selection
* Connects via local Wi‑Fi to the Raspberry Pi

**Raspberry Pi (Brain)**

* Hosts Wi‑Fi access point
* Hosts web UI and API
* Owns camera and printer
* Runs a single‑threaded controller with a command queue
* Executes OS‑level commands (gphoto2, ImageMagick, CUPS)

**Camera (Nikon D750)**

* USB tethered
* Fixed zoom and focus (manual)
* Controlled exclusively via gphoto2

**Printer (Canon Selphy)**

* USB via CUPS
* Controlled exclusively via CUPS

---

## System Flow Overview

1. Guests position themselves using physical markers and on-screen guidance.
   (Live camera preview is intentionally disabled for noise, reliability, and hardware longevity.)

2. Guest selects the number of strips to print (2/4/6/8) and taps **Start**.

3. UI sends `POST /start-session` with:
    - `print_count` (number of print sheets; 2 strips per sheet)

4. The controller transitions to an active session and becomes ready for the first photo.

5. Photo capture is guest-driven using the same on-screen button:
    - Each tap triggers `POST /take-photo`
    - The controller runs a countdown, captures a photo, and returns to READY_FOR_PHOTO
    - This repeats until all photos are captured

6. After the final photo, the controller processes the session:
    - Generates `strip.jpg` (600x1596, printer-agnostic)
    - Generates `print.jpg` (1200x1800 @300 DPI; two strips side-by-side; print-only text under each)

7. Printing (CUPS) is started asynchronously so the UI is not blocked.
   The system returns to IDLE so the next guests can begin while the printer finishes.
   Any printer errors are surfaced through `/health`.

> **_NOTE:_** Three photos are always taken for the strip. The first
> time the take photo button is clicked, the `/start-session` endpoint is
> called, followed immediately by the `/take-photo` endpoint

---

## Session State Machine

The controller operates as a strict state machine:

* `IDLE`
* `READY_FOR_PHOTO`
* `COUNTDOWN`
* `CAPTURING_PHOTO`
* `PROCESSING`
* `PRINTING`
* `IDLE`

State is exposed read‑only to the UI via `/status`.

---

## Directory Structure

Key directories and their purpose:

- `controller/` — single source of truth for system state (sessions, health, command queue) and all hardware access.
- `imaging/` — deterministic image processing functions (strip creation, print composition).
- `web/` — Flask API + web UI assets (the iPad touchscreen client).
- `tests/` — pytest unit tests (controller rules, imaging, and API behavior). Tests use `tmp_path`; CI must stay green.
- `docs/` — project documentation and operational notes.

Runtime session data is written under `<image_root>/sessions/...` (see `docs/session-storage-and-access.md`).

---

## Event Configuration (Album Code + Logo)

Two event-level values are configured directly in the controller for now (intentionally simple for MVP):

1) Album code (printed under each strip on the print sheet)

- File: `controller/controller.py`
- Field: `PhotoboothController.event_album_code`
- Example (current):
  `self.event_album_code = "MaxMitzvah2026"`

2) Logo used in strip + print rendering

- File: `controller/controller.py`
- Field: `PhotoboothController.strip_logo_path`
- Default location (current):
  `imaging/logo.png`

To update the logo, replace the file at `imaging/logo.png` (or change `strip_logo_path` to point elsewhere).
The logo is required for strip creation.

---

## Camera Configuration

### Physical Setup

* Fixed focal length (zoom ring taped)
* Manual focus
* Floor markers for guest positioning
* Aperture: f/8 – f/11
* Large depth of field for reliability

### Control

* Camera is controlled exclusively via gphoto2
* Live view is intentionally disabled
* Camera is accessed only for:
    - Health checks
    - Image capture

Disabling live view reduces shutter chatter, USB contention, and camera wear,
and significantly improves reliability during long events.

---

## Why No Live View?

Although live camera preview is common in photobooth systems, **Photobooth v2 intentionally does not use live view** by
default.

This decision is based on real-world event reliability, not technical limitations.

### Reasons

**1. Mechanical Noise & Guest Experience**  
On cameras like the Nikon D750, USB live view causes continual mirror/shutter activity.
This is distracting, noisy, and undesirable in quiet or formal event environments.

**2. Reliability Under Load**  
Live view significantly increases:

- USB traffic
- Camera state churn
- gphoto2 contention

Disabling live view dramatically reduces:

- dropped connections
- intermittent “device busy” errors
- long-running instability during multi-hour events

**3. Health Monitoring Should Be Intent-Driven**  
Camera health is more reliably detected through:

- explicit health checks when idle
- real capture attempts
- failure of actual work, not background streaming

This avoids false positives and unnecessary hardware stress.

**4. Future-Proofing**  
Not all cameras support stable USB live view.
By designing the system to function without it:

- camera models can be swapped more easily
- HDMI-based preview or external monitors remain viable options
- the controller remains hardware-agnostic

### What Guests See Instead

- Physical positioning markers
- Clear countdown UI
- Explicit progress and error states

In practice, this results in:

- quieter operation
- fewer failures
- faster recovery
- better unattended reliability

Live view may be reintroduced **only if a future camera supports it cleanly and silently**.

---

## Printing

* Canon Selphy CP1500
* Faster print times
* Better driver support

Printing is handled synchronously and sequentially to avoid
printer overload. Session processing produces `strip.jpg`
and `print.jpg` (print-ready 1200×1800 @300 DPI).

Strip/print sizing and responsibilities are defined in `docs/strip-vs-print-contract.md`.

Photobooth v2 uses **driverless IPP Everywhere printing over Wi‑Fi**.

### Why USB printing is unsupported

USB printing on the Canon SELPHY CP1500 is intentionally not supported:

- USB printer class drivers (`usblp`, `ipp-usb`) conflict on modern Linux
- IPP‑over‑USB is unstable in AP‑mode deployments
- Canon officially supports AirPrint / IPP Everywhere on this model
- Wi‑Fi printing recovers cleanly after Pi or printer reboots

For reliability and maintainability, all production printing uses Wi‑Fi IPP Everywhere.
---

## Networking

* Raspberry Pi acts as Wi‑Fi Access Point
* No internet required
* iPad connects directly to Pi
* UI accessed via browser (Safari)

Example access:

```
http://192.168.4.1
```

---

## Web API (Internal)

The API is intentionally minimal.

### Start Session

```http
POST /start-session
```

Payload:

```json
{
  "print_count": 2
}
```

### Status

```http
GET /status
```

Returns:

```json
{
  "state": "COUNTDOWN",
  "countdown": 3
}
```

---

## Safety & Concurrency Guarantees

* Single controller thread
* In‑memory command queue
* No parallel hardware access
* UI reloads are safe
* iPad disconnect does not stop an active session

---

## Attendant Role (Optional)

The system is designed to run unattended. When present, an attendant:

* Helps position guests
* Keeps groups moving
* Handles edge cases

The attendant does **not** operate the camera.

---

## Rebuild Philosophy

This repository is intended to allow a full rebuild from scratch:

* OS installation
* Camera setup
* Printer setup
* Wi‑Fi configuration
* Application install

All critical steps must be scripted or documented.

---

## Notes

This project favors **reliability over cleverness**.
If something can fail at an event, it eventually will — design accordingly.

---

## Implementation

Implementation steps are intentionally documented in separate files to keep this README concise and readable.

### Development

TBD

### Testing & CI

See: [testing-and-ci.md](docs/testing-and-ci.md)

### Setup

The Raspberry Pi setup and deployment process is documented in three steps:

- **[Step 0](docs/step-0-raspberry-pi-setup.md)**: Base OS installation and initial access
- **[Step 1](docs/step-1-raspberry-pi-configure.md)**: System configuration (users, camera, networking, access point)
- **[Step 2](docs/step-2-deploy-and-run-on-raspberry-pi.md)**: Application deployment and runtime setup

Steps 1 and 2 can be performed manually using the documentation below, or by using the provided scripts:

- Step 1 script: `deployment/scripts/step1_provision_pi.sh`
- Step 2 script: `deployment/scripts/step2_deploy_app.sh`

To run the scripts:

```bash
sudo ./deployment/scripts/step1_provision_pi.sh
sudo ./deployment/scripts/step2_deploy_app.sh
```

### Recovery and Errors

See: [recovery-and-errors.md](docs/recovery-and-errors.md)

### Accessing Photos

See: [session-storage-and-access.md](docs/session-storage-and-access.md)