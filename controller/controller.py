"""
Photobooth controller

Single authoritative owner of camera, printer, and session state.
"""

import threading
import time
from enum import Enum, auto
from pathlib import Path
from queue import Queue, Empty
from typing import Optional

from controller.camera import Camera
from controller.health import HealthStatus, HealthCode


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
    """
    Core controller loop.

    Design guarantees:
    - Never blocks on slow I/O in the command loop
    - Camera health is inferred from real interactions
    - Live view failures do not crash the controller
    """

    LIVE_VIEW_OK_WINDOW = 2.0  # seconds

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

        # Controller state
        self.state = ControllerState.IDLE
        self.command_queue = Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = False

        # Live view
        self._latest_live_view_frame: Optional[bytes] = None
        self._last_live_view_ok: Optional[float] = None
        self._live_view_lock = threading.Lock()
        self._live_view_running = False

        # Health
        self._health_status = HealthStatus.ok()
        self._last_camera_error: Optional[Exception] = None

    # ---------- Lifecycle ----------

    def start(self):
        self._running = True

        # Start live view if possible, but do not fail hard
        try:
            self.camera.start_live_view()
            self._start_live_view_worker()
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

        threading.Thread(
            target=self._photo_capture_worker,
            daemon=True,
        ).start()

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
            self.camera.stop_live_view()
            self.camera.capture(self.image_root)
            self._mark_camera_ok()

        except Exception:
            failed_photo_number = self.photos_taken + 1

            self._set_camera_error(
                HealthCode.CAMERA_NOT_DETECTED,
                (
                    f"Camera disconnected during photo "
                    f"{failed_photo_number} of {self.total_photos}. "
                    f"Session was cancelled."
                ),
            )

            with self._state_lock:
                self.session_active = False
                # Optional: reset numbering if desired
                # self.photos_taken = 0
                self.state = ControllerState.IDLE

            return

        with self._state_lock:
            self.photos_taken += 1

        try:
            self.camera.start_live_view()
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
        threading.Thread(
            target=self._finish_session_worker,
            daemon=True,
        ).start()

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

    # ---------- Live view ----------

    def _start_live_view_worker(self):
        if self._live_view_running:
            return

        self._live_view_running = True

        threading.Thread(
            target=self._live_view_worker,
            daemon=True,
        ).start()

    def _live_view_worker(self):
        retry_interval = 2.0
        last_retry = 0.0

        while self._running:
            now = time.monotonic()

            with self._state_lock:
                state = self.state
                health_level = self._health_status.level

            # ---- HARD STOP during capture ----
            # Do NOT attempt live view or health inference while capturing
            if state in (
                    ControllerState.COUNTDOWN,
                    ControllerState.CAPTURING_PHOTO,
            ):
                time.sleep(0.2)
                continue

            # ---- Recovery retry when unhealthy ----
            if (
                    health_level != HealthStatus.Level.OK
                    and state in (ControllerState.IDLE, ControllerState.READY_FOR_PHOTO)
                    and now - last_retry > retry_interval
            ):
                last_retry = now
                try:
                    self.camera.start_live_view()
                    self._mark_camera_ok()
                except Exception:
                    pass  # still unhealthy

            # ---- Normal live view polling ----
            try:
                frame = self.camera.get_live_view_frame()
                with self._live_view_lock:
                    self._latest_live_view_frame = frame
                self._mark_camera_ok()

            except Exception:
                # Only unexpected failures get surfaced
                self._set_camera_error(
                    HealthCode.CAMERA_NOT_DETECTED,
                    "Camera not responding",
                )

            time.sleep(0.5)

    # ---------- Health inference ----------

    def _mark_camera_ok(self):
        self._last_camera_error = None
        self._health_status = HealthStatus.ok()
        self._last_live_view_ok = time.monotonic()

    def _set_camera_error(self, code: HealthCode, message: str):
        if self._health_status.level == HealthStatus.Level.ERROR:
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
        self._last_camera_error = True
