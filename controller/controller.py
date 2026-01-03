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
from enum import Enum, auto
from pathlib import Path
from queue import Queue, Empty
from typing import Optional

from controller.camera_base import Camera
from controller.health import HealthStatus, HealthCode, HealthLevel, HealthSource
from controller.session_flow import SessionFlow

CAMERA_NOT_DETECTED = "Camera not detected"


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

    def __init__(self, camera: Camera, image_root: Path, *, strip_logo_path: Path | None = None,
                 event_album_code: str | None = None):
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
        self.sessions_root = image_root / "sessions"
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self._session_storage = None
        self._captured_image_paths = []
        # Event-level configuration (injected by web/app.py from env in deployment).
        default_logo = Path(__file__).resolve().parents[1] / "imaging" / "logo.png"
        self.strip_logo_path = strip_logo_path or default_logo
        self.event_album_code = event_album_code or "Sample Code"

        # Controller loop
        self.state = ControllerState.IDLE
        self.command_queue = Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = False

        # Health
        self._health_lock = threading.Lock()
        self._health_status = HealthStatus.ok()
        self._health_source: Optional[HealthSource] = None

        # Workers (internal)
        self._session_flow = SessionFlow(controller=self)

    # ---------- Lifecycle ----------

    def start(self):
        self._running = True

        if self.camera.health_check():
            self._mark_camera_ok()
        else:
            self._set_camera_error(
                HealthCode.CAMERA_NOT_DETECTED,
                CAMERA_NOT_DETECTED,
                source=HealthSource.CAPTURE,
            )

        self._thread.start()

    # ---------- Deployment / config helpers ----------

    def set_config_error(self, *, message: str, instructions: list[str]) -> None:
        """Mark the controller unhealthy due to deployment configuration issues.

        This is intended to be called once at startup by the web app when required
        deployment configuration is missing/invalid. The service should still start
        so that /healthz can surface actionable errors on a headless Pi.
        """
        with self._health_lock:
            # Do not overwrite an existing error; config errors are "first cause".
            if self._health_status.level == HealthLevel.ERROR:
                return

            self._health_source = HealthSource.CONFIG
            self._health_status = HealthStatus.error(
                code=HealthCode.CONFIG_INVALID,
                message=message,
                instructions=instructions,
                recoverable=True,
            )

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
            storage = self._session_storage
            status = {
                "state": self.state.name,
                "busy": self.state != ControllerState.IDLE,
                "photos_taken": self.photos_taken,
                "total_photos": self.total_photos,
                "countdown_remaining": self.countdown_remaining,
            }
        if storage is not None:
            try:
                strip_path = storage.strip_path
                if strip_path.exists() and strip_path.is_file():
                    rel = strip_path.relative_to(self.sessions_root)
                    status["most_recent_strip_url"] = f"/sessions/{rel.as_posix()}"
            except Exception:
                pass

        return status

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
                self._poll_camera_health_if_idle()
                continue
            except Exception as e:
                # Keep controller loop alive. Tests + logs catch regressions.
                print(f"Controller error: {e}")

    def _handle_command(self, command: Command):
        if command.command_type == CommandType.START_SESSION:
            if self.state == ControllerState.IDLE:
                self._session_flow.start_session(command.payload)


        elif command.command_type == CommandType.TAKE_PHOTO:
            with self._state_lock:
                state = self.state

            if state == ControllerState.READY_FOR_PHOTO:
                self._session_flow.begin_photo_capture()
            else:
                # Ignore only if we are truly busy; do NOT consume early clicks
                if state in (ControllerState.COUNTDOWN, ControllerState.CAPTURING_PHOTO):
                    return
                # If the UI raced the READY transition, retry shortly
                self.command_queue.put(command)

    def _begin_photo_capture(self):
        self._session_flow.begin_photo_capture()

    def _finish_session_worker(self):
        self._session_flow._finish_session_worker()

    def _photo_capture_worker(self):
        self._session_flow._photo_capture_worker()

    # ---------- Internal helpers used by workers ----------

    # Running flag for worker loops
    def _is_running(self) -> bool:
        return self._running

    # State access for workers
    def _get_state(self) -> ControllerState:
        with self._state_lock:
            return self.state

    # Health inspection
    def _is_unhealthy(self) -> bool:
        with self._health_lock:
            return self._health_status.level == HealthLevel.ERROR

    # ---------- Health helpers ----------

    def _poll_camera_health_if_idle(self) -> None:
        if self.state not in (
                ControllerState.IDLE,
                ControllerState.READY_FOR_PHOTO,
        ):            return

        try:
            if self.camera.health_check():
                self._mark_camera_ok()
            else:
                self._set_camera_error(
                    HealthCode.CAMERA_NOT_DETECTED,
                    CAMERA_NOT_DETECTED,
                    source=HealthSource.CAPTURE,
                )
        except Exception:
            self._set_camera_error(
                HealthCode.CAMERA_NOT_DETECTED,
                CAMERA_NOT_DETECTED,
                source=HealthSource.CAPTURE,
            )

    def _get_health_source(self) -> Optional[HealthSource]:
        with self._health_lock:
            return self._health_source

    def _mark_camera_ok(self):
        with self._health_lock:
            # Never clear deployment/config errors from camera polling.
            if self._health_source == HealthSource.CONFIG:
                return

            self._health_source = None
            self._health_status = HealthStatus.ok()

    def _set_camera_error(self, code: HealthCode, message: str, *, source: HealthSource):
        with self._health_lock:
            if self._health_status.level == HealthLevel.ERROR:
                return
            self._health_source = source
            self._health_status = HealthStatus.error(
                code=code,
                message=message,
                instructions=[
                    "Check that the camera is powered on",
                    "Check the USB cable",
                    "Replace the camera battery if needed",
                ],
            )

    def _set_processing_error(self, message: str):
        with self._health_lock:
            if self._health_status.level == HealthLevel.ERROR:
                return
            self._health_source = HealthSource.PROCESSING
            self._health_status = HealthStatus.error(
                code=HealthCode.STRIP_CREATION_FAILED,
                message=message,
                instructions=[
                    "Please restart the photobooth",
                    "Verify strip configuration and logo file",
                    "Contact the operator if the problem persists",
                ],
                recoverable=False,
            )
