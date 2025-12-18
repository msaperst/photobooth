# 📁 Photo & Session Storage

## Session Directory Structure

All captured photos and generated photo strips are stored under a single, canonical root directory on the Raspberry Pi:

```
/home/max/photobooth/
└── sessions/
    └── YYYY-MM-DD/
        └── session_<uuid>/
            ├── photos/
            │   ├── photo_1.jpg
            │   ├── photo_2.jpg
            │   └── photo_3.jpg
            └── strip.jpg
```

**Details:**

- A new **session directory** is created when a session starts.
- All photos captured during that session are written to the `photos/` subdirectory.
- The final combined photo strip is saved as `strip.jpg` in the session root.
- Photos and strips are never written to the project root or temporary locations.

This structure ensures:

- Clean separation between sessions
- Predictable paths for post-processing and printing
- Easy browsing and future extensibility (QR codes, downloads, etc.)

---

## 🌐 Accessing Photos via the Web Interface

The Flask app exposes all session artifacts via a read-only web route:

```
/sessions/<path>
```

### Examples

If the Pi is accessible at:

```
http://pi.local:5000
```

You can access:

- A specific strip:
  ```
  http://pi.local:5000/sessions/2025-03-17/session_abc123/strip.jpg
  ```

- An individual photo:
  ```
  http://pi.local:5000/sessions/2025-03-17/session_abc123/photos/photo_1.jpg
  ```

This makes session output:

- easy to verify during development
- accessible from other devices on the Pi’s Wi-Fi network
- ready for future features like QR code sharing

> **Note:** Directory listings at `/sessions/` may or may not be enabled depending on environment and Flask
> configuration. Individual files are always accessible if the path is known.

---

## 🔒 Notes on Security & Scope

- The `/sessions/*` route is intended for **local, trusted networks only** (e.g. the Pi’s hotspot).
- No authentication is currently enforced.
- This is acceptable for MVP and development use.
- Future work may include:
    - session-scoped access
    - QR-based deep links
    - time-limited downloads

---

## 🛠 Configuration Notes

The sessions directory is configured in the Flask app at startup:

```python
app.config["SESSIONS_ROOT"] = Path("/home/max/photobooth/sessions")
```

This path must:

- exist
- be writable by the photobooth process
- remain consistent with the controller’s `image_root` configuration
