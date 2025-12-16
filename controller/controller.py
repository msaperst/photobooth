"""
Photobooth controller

Single authoritative owner of camera and session state.

Design goals:
- Command loop never blocks on slow I/O
- Camera health is visible to the UI
- System auto-recovers when camera is connected/powered back on
- No red error flashes during normal capture transitions
"""

import threading
import time
from enum import Enum, auto
from pathlib import Path
from queue import Queue, Empty
from typing import Optional

from controller.camera import Camera, CameraError
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
    """
    Single owner of camera + session state.

    Threads:
    - controller thread: consumes commands, updates state (never does slow I/O)
    - live view thread: pulls preview frames (camera I/O)
    - camera monitor thread: only runs when unhealthy + idle; tries to recover
    """

    LIVE_VIEW_FPS_SLEEP = 0.5  # ~2 FPS
    CAMERA_RECOVERY_INTERVAL = 2.0  # seconds (when unhealthy)

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
        self._live_view_lock = threading.Lock()
        self._live_view_running = False

        # Health
        self._health_lock = threading.Lock()
        self._health_status = HealthStatus.ok()
        self._camera_monitor_running = False

    # ---------- Lifecycle ----------

    def start(self):
        self._running = True

        # Always start workers so recovery is possible even if camera is off at boot.
        self._start_live_view_worker()
        self._start_camera_monitor_worker()

        # Best-effort attempt to start live view immediately.
        try:
            self.camera.start_live_view()
            self._set_health_ok()
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

        # Stop live view + capture
        try:
            self.camera.stop_live_view()
        except Exception:
            # If stop_live_view fails, we'll still attempt capture.
            pass

        try:
            self.camera.capture(self.image_root)
            self._set_health_ok()
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
                self.state = ControllerState.IDLE
            return

        with self._state_lock:
            self.photos_taken += 1

        # Restart live view (best effort). If this fails, monitor thread will recover.
        try:
            self.camera.start_live_view()
            self._set_health_ok()
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

    # ---------- Live view worker ----------

    def _start_live_view_worker(self):
        if self._live_view_running:
            return
        self._live_view_running = True
        threading.Thread(target=self._live_view_worker, daemon=True).start()

    def _live_view_worker(self):
        while self._running:
            with self._state_lock:
                state = self.state

            # Only show preview when idle/ready.
            if state not in (ControllerState.IDLE, ControllerState.READY_FOR_PHOTO):
                time.sleep(0.2)
                continue

            try:
                frame = self.camera.get_live_view_frame()
                with self._live_view_lock:
                    self._latest_live_view_frame = frame
                # A successful frame implies camera is alive.
                self._set_health_ok()
            except CameraError:
                # Live view failures can happen transiently; do NOT surface error here.
                pass
            except Exception:
                # Same: do not set health error from live-view polling.
                pass

            time.sleep(self.LIVE_VIEW_FPS_SLEEP)

    # ---------- Camera monitor / recovery worker ----------

    def _start_camera_monitor_worker(self):
        if self._camera_monitor_running:
            return
        self._camera_monitor_running = True
        threading.Thread(target=self._camera_monitor_worker, daemon=True).start()

    def _camera_monitor_worker(self):
        """
        Only tries to recover the camera when:
        - health is ERROR (unhealthy)
        - controller is in a safe state (IDLE/READY_FOR_PHOTO)

        This avoids tying up the command queue and avoids interfering with capture.
        """
        while self._running:
            # Only attempt recovery when unhealthy.
            with self._health_lock:
                unhealthy = self._health_status.level == HealthLevel.ERROR

            with self._state_lock:
                safe_state = self.state in (
                    ControllerState.IDLE,
                    ControllerState.READY_FOR_PHOTO,
                )

            if not unhealthy or not safe_state:
                time.sleep(0.2)
                continue

            # Throttled recovery attempts.
            time.sleep(self.CAMERA_RECOVERY_INTERVAL)

            # Re-check conditions after sleep
            if not self._running:
                break

            with self._health_lock:
                unhealthy = self._health_status.level == HealthLevel.ERROR
            with self._state_lock:
                safe_state = self.state in (
                    ControllerState.IDLE,
                    ControllerState.READY_FOR_PHOTO,
                )
            if not unhealthy or not safe_state:
                continue

            # Attempt to re-acquire camera and restart live view
            try:
                present = self.camera.health_check()
            except Exception:
                present = False

            if not present:
                # Keep the existing error message (don't overwrite)
                continue

            try:
                self.camera.start_live_view()
                self._set_health_ok()
            except Exception:
                # Keep unhealthy; next loop will retry
                continue

    # ---------- Health helpers ----------

    def _set_health_ok(self):
        with self._health_lock:
            self._health_status = HealthStatus.ok()

    def _set_camera_error(self, code: HealthCode, message: str):
        # Preserve the first (most specific) error message.
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
