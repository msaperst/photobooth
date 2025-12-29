# Photobooth v2

This repository contains **Photobooth v2**, an event‑grade, unattended‑capable photobooth system built around:

* **Raspberry Pi (Raspbian)** as the system controller
* **Nikon D750** tethered via USB (gphoto2)
* **Canon Selphy ES30** (prototype) → **Canon Selphy CP1300/CP1500** (production)
* **iPad** as a fixed touchscreen UI (web‑based, no native app)

The system is designed to be **offline‑capable**, **reproducible from scratch**, and **robust under real event
conditions**.

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
* Live camera preview
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

1. Guests position themselves using physical markers and
   on-screen guidance (Live camera preview is intentionally
   disabled for noise, reliability, and hardware longevity)
2. Guest selects number of prints and taps **Start**
3. UI sends request to Pi API
4. Pi enqueues a session command
5. Controller executes:

    * Countdown
    * Photo capture loop
    * Image processing
    * Printing
6. Status updates are streamed back to the UI
7. System returns to idle

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

The repository is organized to clearly separate **hardware control**, **user interaction**, **runtime data**, and *
*documentation**.  
This separation is intentional and is critical for reliability and maintainability.

```text
photobooth/
├── controller/
│   ├── __init__.py
│   ├── controller.py
│   ├── camera.py
│   ├── printer.py
│   └── image_processing.py
│
├── web/
│   ├── __init__.py
│   ├── app.py
│   ├── templates/
│   └── static/
│
├── sessions/
│   └── .gitkeep
│
├── scripts/
│   ├── setup_os.sh
│   ├── setup_printer.sh
│   └── setup_wifi_ap.sh
│
├── docs/
│   ├── Step-0-Raspberry-Pi-Setup.md
│   └── testing-and-ci.md
│
├── tests/
│   ├── __init__.py
│   ├── controller/
│   │   └── test_controller.py
│   └── web/
│       └── test_api.py
│
├── requirements.txt
├── .gitignore
└── README.md
```

### Directory Responsibilities

`controller/`

Owns **all hardware interaction and session logic.**

- Single authoritative owner of:
    - Camera control (gphoto2)
    - Image processing (ImageMagick)
    - Printing (CUPS)
- Single-threaded
- No Flask or web concerns

`web/`

Owns all user interaction.

- Flask app
- Touchscreen UI
- Status polling
- Never talks to hardware directly

`sessions/`

Runtime storage for per-session artifacts.

- Raw captures
- Processed images
- Never committed to git

`scripts/`

One-time or infrequently-run system scripts.

- OS helpers
- Printer setup
- Wi-Fi access point configuration

`docs/`

Project documentation.

- Step-by-step rebuild docs live here
- Architecture lives in the README

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

### Prototype Printer

* Canon Selphy ES30
* USB via CUPS

### Production Target

* Canon Selphy CP1300 or CP1500
* Faster print times
* Better driver support

Printing is handled synchronously and sequentially to avoid printer overload.

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

Step 0: [step-0-raspberry-pi-setup.md](docs/step-0-raspberry-pi-setup.md)
Step 1: [step-1-raspberry-pi-configure.md](docs/step-1-raspberry-pi-configure.md)
Step 2: [step-2-deploy-and-run-on-raspberry-pi.md](docs/step-2-deploy-and-run-on-raspberry-pi.md)

### Recovery and Errors

See: [recovery-and-errors.md](docs/recovery-and-errors.md)

### Accessing Photos

See: [session-storage-and-access.md](docs/session-storage-and-access.md)