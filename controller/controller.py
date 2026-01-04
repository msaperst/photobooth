"""
Photobooth controller

Single authoritative owner of system state and the only component allowed to touch hardware
(camera and, later, printer).

Core responsibilities:
- Own the session state machine and expose read-only status to the web UI
- Serialize user actions via a command queue processed by a single controller loop
- Delegate long-running operations (capture countdown, camera I/O, image processing, printing)
  to internal worker threads that report results back to the controller via explicit state updates
- Surface failures via the Health model (sticky errors with explicit ownership)

Notes about workers:
- The controller loop remains responsive while capture/processing/printing run in worker threads.
- Workers must update state under the controller's locks and must set Health errors explicitly on failure.
- UI should never block on hardware operations; it polls /status and /health.

Configuration (event-level):
- strip_logo_path: Path to the logo used in strip/print rendering
- event_album_code: Operator-provided album code rendered under each printed strip
  Both are currently configured on PhotoboothController.__init__ for easy one-place editing.
"""

import threading
import time
from enum import Enum, auto
from pathlib import Path
from queue import Queue, Empty
from typing import Optional

from controller.camera_base import Camera
from controller.health import HealthStatus, HealthCode, HealthLevel, HealthSource
from controller.printer_base import Printer
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
    # How long camera connectivity must be failing (while idle/ready) before surfacing an error
    CAMERA_ERROR_AFTER = 2.5  # seconds

    # How often to poll camera connectivity when idle/ready (avoid blocking the controller loop)
    CAMERA_POLL_INTERVAL = 1.0  # seconds

    # How long printer connectivity must be failing (while idle/ready) before surfacing an error
    PRINTER_ERROR_AFTER = 6.0  # seconds

    # How often to poll printer connectivity when idle/ready (avoid blocking the controller loop)
    PRINTER_POLL_INTERVAL = 2.0  # seconds

    # How long the printer must be healthy for before clearing the error
    PRINTER_CLEAR_AFTER = 10.0  # seconds

    # How often to attempt recovery when unhealthy (camera/printer off/unplugged)
    RECOVERY_ATTEMPT_INTERVAL = 2.0  # seconds

    # How many photos are taken to build out the strip.
    TOTAL_PHOTOS_PER_SESSION = 3

    # Hints to the user about possible printer errors
    PRINTER_REASON_HINTS = {
        "media-empty": "Paper tray may be empty",
        "media-needed": "Paper tray may need attention",
        "marker-supply-empty": "Ink cartridge may be empty",
        "marker-supply-low": "Ink cartridge may be low",
        "paused": "Printer is paused or waiting for input",
        "offline": "Printer may be powered off or disconnected",
        "door-open": "Printer cover or tray may be open",
    }

    def __init__(self, camera: Camera, printer: Printer, image_root: Path, *, strip_logo_path: Path | None = None,
                 event_album_code: str | None = None):
        self._state_lock = threading.Lock()

        # Session state
        self.total_photos = self.TOTAL_PHOTOS_PER_SESSION
        self.photos_taken = 0
        self.print_count = 1
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

        # Printer
        self.printer = printer
        self._last_printer_recovery_attempt = 0.0
        self._printer_poll_fail_since: float | None = None
        self._printer_poll_ok_since: float | None = None
        self._print_lock = threading.Lock()
        self._print_in_flight = False
        self._pending_prints: list[tuple[Path, int]] = []

        # Controller loop
        self.state = ControllerState.IDLE
        self.command_queue = Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = False

        # Health
        self._health_lock = threading.Lock()
        self._health_status = HealthStatus.ok()

        # Camera/printer poll debounce (prevents transient gphoto2/ipp slowness from flashing errors)
        self._camera_poll_last_attempt = 0.0
        self._camera_poll_fail_since: float | None = None
        self._printer_poll_last_attempt = 0.0
        self._printer_poll_fail_since: float | None = None
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

    # ---------- Public API ----------

    def enqueue(self, command: Command):
        self.command_queue.put(command)

    def get_status(self):
        with self._state_lock:
            storage = self._session_storage
            state = self.state
            photos_taken = self.photos_taken
            total_photos = self.total_photos
            print_count = self.print_count
            countdown_remaining = self.countdown_remaining

        with self._health_lock:
            printer_blocked = self._health_source == HealthSource.PRINTER

        status = {
            "state": state.name,
            "busy": state != ControllerState.IDLE or printer_blocked,
            "photos_taken": photos_taken,
            "total_photos": total_photos,
            "print_count": print_count,
            "countdown_remaining": countdown_remaining,
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
                self._poll_printer_health_if_idle()
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

    # will print stuff
    def _start_print_job(self, print_path: Path, *, copies: int) -> None:
        if copies < 1:
            return

        with self._print_lock:
            self._pending_prints.append((print_path, copies))
            if self._print_in_flight:
                return
            self._print_in_flight = True

        def _print_worker():
            try:
                while True:
                    with self._print_lock:
                        if not self._pending_prints:
                            return
                        path, count = self._pending_prints[0]

                    self.printer.preflight()
                    self.printer.print_file(path, copies=count, job_name="Photobooth Print")

                    with self._print_lock:
                        self._pending_prints.pop(0)

            except Exception as e:
                self._set_printer_error(str(e), reasons=[])
            finally:
                with self._print_lock:
                    self._print_in_flight = False

        threading.Thread(target=_print_worker, daemon=True).start()

    def _kick_print_worker_if_needed(self) -> None:
        """
        If there are pending prints and no print worker in flight, start a worker
        to drain the queue. This does not enqueue a new job.
        """
        with self._print_lock:
            if self._print_in_flight:
                return
            if not self._pending_prints:
                return
            self._print_in_flight = True

        def _print_worker():
            try:
                while True:
                    with self._print_lock:
                        if not self._pending_prints:
                            return
                        path, count = self._pending_prints[0]

                    self.printer.preflight()
                    self.printer.print_file(path, copies=count, job_name="Photobooth Print")

                    with self._print_lock:
                        self._pending_prints.pop(0)

            except Exception as e:
                self._set_printer_error(str(e), reasons=[])
            finally:
                with self._print_lock:
                    self._print_in_flight = False

        threading.Thread(target=_print_worker, daemon=True).start()

    # ---------- Health helpers ----------

    def _poll_camera_health_if_idle(self) -> None:
        # Only poll camera health when we are "idle enough" that we won't interfere with capture.
        # READY_FOR_PHOTO is included so we can surface a disconnect before the operator presses
        # the button, but we debounce to avoid transient gphoto2 slowness flashing errors.
        if self.state not in (
                ControllerState.IDLE,
                ControllerState.READY_FOR_PHOTO,
        ):
            return

        now = time.time()
        if now - self._camera_poll_last_attempt < self.CAMERA_POLL_INTERVAL:
            return
        self._camera_poll_last_attempt = now

        try:
            ok = bool(self.camera.health_check())
        except Exception:
            ok = False

        if ok:
            self._camera_poll_fail_since = None
            self._mark_camera_ok()
            return

        # Failure: only surface after sustained failure window.
        if self._camera_poll_fail_since is None:
            self._camera_poll_fail_since = now
            return

        if now - self._camera_poll_fail_since < self.CAMERA_ERROR_AFTER:
            return

        self._set_camera_error(
            HealthCode.CAMERA_NOT_DETECTED,
            CAMERA_NOT_DETECTED,
            source=HealthSource.CAPTURE,
        )

    def _poll_printer_health_if_idle(self) -> None:
        # Only poll printer health while fully idle (avoid interference with capture/processing).
        if self.state != ControllerState.IDLE:
            return

        now = time.time()
        if now - self._printer_poll_last_attempt < self.PRINTER_POLL_INTERVAL:
            return
        self._printer_poll_last_attempt = now

        # Health check is optional (printers may not implement it yet).
        try:
            health = self.printer.health_check()
        except Exception:
            health = None

        if not health:
            return

        reachable = bool(health.get("reachable"))
        reasons = list(health.get("reasons") or [])

        # --- Unreachable (debounced) ---
        if not reachable:
            # Any failure resets the "healthy since" window.
            self._printer_poll_ok_since = None

            # Start or continue failure window.
            if self._printer_poll_fail_since is None:
                self._printer_poll_fail_since = now
                return

            # Still within debounce window -> do nothing (prevents transient flaps).
            if now - self._printer_poll_fail_since < self.PRINTER_ERROR_AFTER:
                return

            # Sustained failure -> surface sticky printer error.
            self._set_printer_error("Printer is not reachable", reasons=[])
            return

        # --- Reachable ---
        # Reaching the printer resets failure window.
        self._printer_poll_fail_since = None

        # If printer reports explicit reasons, surface them as hints.
        if reasons:
            self._printer_poll_ok_since = None
            self._set_printer_error("Printer reported a problem", reasons=reasons)
            return

        # Healthy (reachable + no reasons)
        if self._printer_poll_ok_since is None:
            self._printer_poll_ok_since = now

        # Clear PRINTER error only after sustained healthy window (prevents red flash).
        with self._health_lock:
            if self._health_source != HealthSource.PRINTER:
                return

            if now - self._printer_poll_ok_since < self.PRINTER_CLEAR_AFTER:
                return

            self._health_source = None
            self._health_status = HealthStatus.ok()

        # If we just recovered and there are pending prints, resume draining.
        self._kick_print_worker_if_needed()

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

        # Camera poll debounce (prevents transient gphoto2 slowness from flashing errors)
        self._camera_poll_last_attempt = 0.0
        self._camera_poll_fail_since: float | None = None

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

    def _set_printer_error(self, message: str, *, reasons: list[str]):
        with self._health_lock:
            if self._health_status.level == HealthLevel.ERROR:
                return

            instructions = [
                "Check that the printer is powered on",
                "Confirm the printer is connected to the Photobooth Wi-Fi",
                "Verify the CUPS queue is online",
                "Check paper/ink and clear any jams",
            ]

            if reasons:
                instructions.append("Reported by printer:")
                for r in reasons:
                    hint = self.PRINTER_REASON_HINTS.get(r, f"Printer reported: {r}")
                    instructions.append(f"- {hint}")

            self._health_source = HealthSource.PRINTER
            self._health_status = HealthStatus.error(
                code=HealthCode.PRINTER_FAILED,
                message=message,
                instructions=instructions,
                recoverable=True,
            )
