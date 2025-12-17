# Photobooth Error States & Recovery Behavior

This document describes how the photobooth system behaves when hardware errors
occur, what operators will see, and how to recover safely.

The goal is clarity, predictability, and zero technical intervention.

---

## Overview

The photobooth continuously monitors camera health by observing real usage:

- Live preview frames
- Photo capture success or failure

When an error is detected:

- A full-screen error message is displayed
- All interaction is blocked
- Clear instructions are shown
- The system automatically recovers when possible

---

## Error States

### Camera Not Detected

**Description**  
The camera is powered off, unplugged, or otherwise not responding.

**User-visible message**
> Camera not detected  
> • Check that the camera is powered on  
> • Check the USB cable  
> • Replace the battery if needed

**Behavior**

- Booth interaction is disabled
- Live preview stops
- When the camera reconnects, the booth resumes automatically

---

## Recovery Scenarios

### A. Camera disconnected while idle or ready

**Example**

- Booth is waiting for a session
- Camera battery dies

**System behavior**

- Error overlay appears
- No session state is lost
- When camera is restored, overlay disappears automatically

**Operator action**

- Fix camera (power / cable)
- No restart required

---

### B. Camera disconnected during countdown

**Example**

- Countdown starts
- Camera is turned off before photo is taken

**System behavior**

- Countdown completes
- Photo capture fails
- Session is cancelled
- Error overlay appears with context

**User-visible message**
> Camera disconnected during photo 1 of 3.  
> Session was cancelled.

**Operator action**

- Fix camera
- Start a new session

---

### C. Camera disconnected mid-session (photo 2 of 3)

**Example**

- Photo 1 taken successfully
- Camera disconnects before photo 2

**System behavior**

- Capture fails
- Session is cancelled
- Previously captured photos are preserved
- Error overlay appears with context

**User-visible message**
> Camera disconnected during photo 2 of 3.  
> Session was cancelled.

**Operator action**

- Fix camera
- Start a new session

---

## Design Notes

- Sessions are intentionally **not auto-resumed**
- Partial sessions are cancelled cleanly
- This avoids confusion and unexpected behavior
- Automatic recovery is limited to restoring hardware availability

---

## What to Do If Errors Persist

If the error message does not clear after fixing the camera:

1. Verify the camera is powered on
2. Re-seat the USB cable
3. Replace the camera battery
4. Restart the camera (not the Raspberry Pi)

The system should never require a Raspberry Pi reboot under normal conditions.
