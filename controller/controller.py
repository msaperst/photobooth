"""
Photobooth controller

Single authoritative owner of camera and session state.

Goals:
- Command loop never blocks on slow camera I/O
- Live view worker always runs (enables recovery when camera is off at boot)
- Camera-off-at-boot -> turning camera on later recovers automatically
- No "red flash" after capture (debounced live-view failures)
- Specific capture-failure error messages are not overwritten by generic ones
"""

import threading
import time
from enum import Enum, auto
from pathlib import Path
from queue import Queue, Empty
from typing import Optional

from controller.camera import Camera
from controller.health import HealthStatus, HealthCode, HealthLevel


class ControllerState(Enum):
    IDLE = auto()
    READY_FOR_PHOTO = auto()
    COUNTDOWN = auto()
    CAPTURING_PHOTO = auto()
    PROCESSING = auto()
    PRINTING = auto()


class CommandType(Enum):
    START_SESSION = auto()
    TAKE_PHOTO = auto()


class Command:
    def __init__(self, command_type, payload=None):
        self.command_type = command_type
        self.payload = payload or {}


class PhotoboothController:
    # How long live view must be failing (while idle/ready) before surfacing an error
    LIVE_VIEW_ERROR_AFTER = 2.5  # seconds

    # How often to attempt recovery when unhealthy (camera off/unplugged)
    RECOVERY_ATTEMPT_INTERVAL = 2.0  # seconds

    def __init__(self, camera: Camera, image_root: Path):
        self._state_lock = threading.Lock()

        # Session state
        self.total_photos = 3
        self.photos_taken = 0
        self.session_active = False

        self.countdown_seconds = 3
        self.countdown_remaining = 0

        # Camera + storage
        self.camera = camera
        self.image_root = image_root

        # Controller loop
        self.state = ControllerState.IDLE
        self.command_queue = Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = False

        # Live view
        self._latest_live_view_frame: Optional[bytes] = None
        self._live_view_lock = threading.Lock()
        self._live_view_running = False

        # Health
        self._health_lock = threading.Lock()
        self._health_status = HealthStatus.ok()

        # Live view failure debounce + recovery throttling
        self._live_view_failure_since: Optional[float] = None
        self._last_recovery_attempt: float = 0.0

    # ---------- Lifecycle ----------

    def start(self):
        self._running = True

        # Always start worker so recovery is possible even if camera is OFF at boot.
        self._start_live_view_worker()

        # Best-effort initial live view start. Failure is ok; worker will recover later.
        try:
            self.camera.start_live_view()
            self._mark_camera_ok()
        except Exception:
            self._set_camera_error(
                HealthCode.CAMERA_NOT_DETECTED,
                "Camera not detected",
            )

        self._thread.start()

    def stop(self):
        self._running = False
        try:
            self.camera.stop_live_view()
        except Exception:
            pass

    # ---------- Public API ----------

    def enqueue(self, command: Command):
        self.command_queue.put(command)

    def get_status(self):
        with self._state_lock:
            return {
                "state": self.state.name,
                "busy": self.state != ControllerState.IDLE,
                "photos_taken": self.photos_taken,
                "total_photos": self.total_photos,
                "countdown_remaining": self.countdown_remaining,
            }

    def get_live_view_frame(self) -> Optional[bytes]:
        with self._live_view_lock:
            return self._latest_live_view_frame

    def get_health(self) -> HealthStatus:
        with self._health_lock:
            return self._health_status

    # ---------- Controller loop ----------

    def _run(self):
        while self._running:
            try:
                command = self.command_queue.get(timeout=0.1)
                self._handle_command(command)
            except Empty:
                continue
            except Exception as e:
                print(f"Controller error: {e}")

    def _handle_command(self, command: Command):
        if command.command_type == CommandType.START_SESSION:
            if self.state == ControllerState.IDLE:
                self._start_session(command.payload)

        elif command.command_type == CommandType.TAKE_PHOTO:
            if self.state == ControllerState.READY_FOR_PHOTO:
                self._begin_photo_capture()

    # ---------- Session flow ----------

    def _start_session(self, payload):
        with self._state_lock:
            self.session_active = True
            self.photos_taken = 0
            self.total_photos = payload.get("image_count", 3)
            self.state = ControllerState.READY_FOR_PHOTO

    def _begin_photo_capture(self):
        with self._state_lock:
            if self.state != ControllerState.READY_FOR_PHOTO:
                return
            self.state = ControllerState.COUNTDOWN
            self.countdown_remaining = self.countdown_seconds

        threading.Thread(target=self._photo_capture_worker, daemon=True).start()

    def _photo_capture_worker(self):
        # Countdown
        while True:
            with self._state_lock:
                if self.countdown_remaining <= 0:
                    break
            time.sleep(1)
            with self._state_lock:
                self.countdown_remaining -= 1

        with self._state_lock:
            self.state = ControllerState.CAPTURING_PHOTO

        try:
            # Stop preview, capture
            try:
                self.camera.stop_live_view()
            except Exception:
                pass

            self.camera.capture(self.image_root)
            self._mark_camera_ok()

        except Exception:
            failed_photo_number = self.photos_taken + 1
            self._set_camera_error(
                HealthCode.CAMERA_NOT_DETECTED,
                (
                    f"Camera disconnected during photo "
                    f"{failed_photo_number} of {self.total_photos}. "
                    f"Session was cancelled. Please start again."
                ),
            )
            with self._state_lock:
                self.session_active = False
                self.photos_taken = 0  # reset numbering to avoid “photo 2 of 3” confusion
                self.state = ControllerState.IDLE
            return

        with self._state_lock:
            self.photos_taken += 1

        # Restart preview (best effort). If it fails, worker will attempt recovery.
        try:
            self.camera.start_live_view()
            self._mark_camera_ok()
        except Exception:
            self._set_camera_error(
                HealthCode.CAMERA_NOT_DETECTED,
                "Camera reconnected, but live preview could not be restarted",
            )

        with self._state_lock:
            if self.photos_taken < self.total_photos:
                self.state = ControllerState.READY_FOR_PHOTO
                return

        self._finish_session()

    def _finish_session(self):
        threading.Thread(target=self._finish_session_worker, daemon=True).start()

    def _finish_session_worker(self):
        with self._state_lock:
            self.state = ControllerState.PROCESSING
        time.sleep(1)

        with self._state_lock:
            self.state = ControllerState.PRINTING
        time.sleep(1)

        with self._state_lock:
            self.session_active = False
            self.state = ControllerState.IDLE

    # ---------- Live view + recovery ----------

    def _start_live_view_worker(self):
        if self._live_view_running:
            return
        self._live_view_running = True
        threading.Thread(target=self._live_view_worker, daemon=True).start()

    def _live_view_worker(self):
        while self._running:
            now = time.monotonic()

            with self._state_lock:
                state = self.state

            # Only poll preview when it should be visible
            if state not in (ControllerState.IDLE, ControllerState.READY_FOR_PHOTO):
                time.sleep(0.2)
                continue

            # --- Recovery path (fixes camera-off-at-boot -> turn on later) ---
            with self._health_lock:
                unhealthy = self._health_status.level == HealthLevel.ERROR

            if unhealthy and (now - self._last_recovery_attempt) >= self.RECOVERY_ATTEMPT_INTERVAL:
                self._last_recovery_attempt = now
                try:
                    self.camera.start_live_view()
                    # Don’t immediately trust it, but clear the error so UI unblocks;
                    # first good frame will confirm and keep it OK.
                    self._mark_camera_ok()
                    # Reset debounce since we’re attempting recovery
                    self._live_view_failure_since = None
                except Exception:
                    # Still unhealthy; keep waiting
                    pass

            # --- Frame polling + debounced error (fixes post-capture red flash) ---
            try:
                frame = self.camera.get_live_view_frame()
                with self._live_view_lock:
                    self._latest_live_view_frame = frame

                self._live_view_failure_since = None
                self._mark_camera_ok()

            except Exception:
                if self._live_view_failure_since is None:
                    self._live_view_failure_since = now

                # Only surface a generic error if failures persist
                if (now - self._live_view_failure_since) >= self.LIVE_VIEW_ERROR_AFTER:
                    self._set_camera_error(
                        HealthCode.CAMERA_NOT_DETECTED,
                        "Camera not responding",
                    )

            time.sleep(0.5)  # ~2 FPS

    # ---------- Health helpers ----------

    def _mark_camera_ok(self):
        with self._health_lock:
            self._health_status = HealthStatus.ok()

    def _set_camera_error(self, code: HealthCode, message: str):
        # Preserve the first (most specific) error; don’t overwrite with generic ones.
        with self._health_lock:
            if self._health_status.level == HealthLevel.ERROR:
                return
            self._health_status = HealthStatus.error(
                code=code,
                message=message,
                instructions=[
                    "Check that the camera is powered on",
                    "Check the USB cable",
                    "Replace the camera battery if needed",
                ],
            )
