# 📁 Photo & Session Storage

## Session Directory Structure

All captured photos and generated artifacts are stored under a single, canonical root directory derived from
`image_root`:

- **No hardcoded absolute paths**
- **Nothing is written to the project root**
- Tests use temporary directories (`tmp_path`)

Live preview images are never stored on disk.

```
<image_root>/
└── sessions/
    └── YYYY-MM-DD/
        └── session_<uuid>/
            ├── photos/
            │   ├── photo_1.jpg
            │   ├── photo_2.jpg
            │   └── photo_3.jpg
            ├── strip.jpg
            └── print.jpg
```

**Details:**

- A new **session directory** is created when a session starts.
- All photos captured during that session are written to the `photos/` subdirectory.
- The combined photo strip is saved as `strip.jpg` in the session root.
- The print composite (when implemented) will be saved alongside the strip (e.g., `print.jpg`).

> **Note:** Directory listings at `/sessions/` may or may not be enabled depending on environment and Flask
> configuration. Individual files are always accessible if the path is known.

---

## 🔒 Notes on Security & Scope

- The `/sessions/*` route is intended for **local, trusted networks only** (e.g. the Pi’s hotspot).
- No authentication is currently enforced.
- This is acceptable for MVP and local event usage, but should be revisited before any internet-facing exposure.
