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

from controller.camera import Camera
from controller.health import HealthStatus, HealthCode, HealthLevel, HealthSource
from controller.live_view_worker import LiveViewWorker
from controller.session_flow import SessionFlow


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
        self.sessions_root = image_root / "sessions"
        self.sessions_root.mkdir(exist_ok=True)
        self._session_storage = None
        self._captured_image_paths = []
        self.strip_logo_path = Path(__file__).parent.parent / "web/static/logo.png"

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
        self._health_source: Optional[HealthSource] = None

        # Workers (internal)
        self._live_view_worker = LiveViewWorker(controller=self)
        self._session_flow = SessionFlow(controller=self)

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
                source=HealthSource.LIVE_VIEW,
            )

        self._thread.start()

    def stop(self):
        self._running = False
        self._live_view_worker.stop()
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
                # Keep controller loop alive. Tests + logs catch regressions.
                print(f"Controller error: {e}")

    def _handle_command(self, command: Command):
        if command.command_type == CommandType.START_SESSION:
            if self.state == ControllerState.IDLE:
                self._session_flow.start_session(command.payload)

        elif command.command_type == CommandType.TAKE_PHOTO:
            if self.state == ControllerState.READY_FOR_PHOTO:
                self._session_flow.begin_photo_capture()

    def _begin_photo_capture(self):
        self._session_flow.begin_photo_capture()

    def _start_live_view_worker(self):
        if self._live_view_running:
            return

        self._live_view_running = True
        self._live_view_worker.start()

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

    # Live view frame update
    def _set_latest_live_view_frame(self, frame: Optional[bytes]) -> None:
        with self._live_view_lock:
            self._latest_live_view_frame = frame

    # Health inspection
    def _is_unhealthy(self) -> bool:
        with self._health_lock:
            return self._health_status.level == HealthLevel.ERROR

    # ---------- Health helpers ----------

    def _get_health_source(self) -> Optional[HealthSource]:
        with self._health_lock:
            return self._health_source

    def _mark_camera_ok(self):
        with self._health_lock:
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
