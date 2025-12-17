import threading
import time
from typing import Optional, TYPE_CHECKING

from controller.health import HealthCode

if TYPE_CHECKING:  # pragma: no cover
    from controller.controller import PhotoboothController, ControllerState


class LiveViewWorker:
    """
    Owns live view polling + recovery throttling.

    IMPORTANT:
    - Controller remains the single source of truth.
    - This worker does not own state; it reads/writes via controller methods/locks.
    """

    def __init__(self, controller: "PhotoboothController"):
        self._controller = controller
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Debounce + recovery throttling (same behavior as old controller.py)
        self._live_view_failure_since: Optional[float] = None
        self._last_recovery_attempt: float = 0.0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        # Avoid circular import at module import time
        from controller.controller import ControllerState

        while self._running and self._controller._is_running():
            now = time.monotonic()
            state = self._controller._get_state()

            # Only poll preview when it should be visible
            if state not in (ControllerState.IDLE, ControllerState.READY_FOR_PHOTO):
                time.sleep(0.2)
                continue

            # --- Recovery path (fixes camera-off-at-boot -> turn on later) ---
            if self._controller._is_unhealthy() and (
                    now - self._last_recovery_attempt
            ) >= self._controller.RECOVERY_ATTEMPT_INTERVAL:
                self._last_recovery_attempt = now
                try:
                    self._controller.camera.start_live_view()
                    # Don’t immediately trust it, but clear the error so UI unblocks;
                    # first good frame will confirm and keep it OK.
                    self._controller._mark_camera_ok()
                    # Reset debounce since we’re attempting recovery
                    self._live_view_failure_since = None
                except Exception:
                    # Still unhealthy; keep waiting
                    pass

            # --- Frame polling + debounced error (fixes post-capture red flash) ---
            try:
                frame = self._controller.camera.get_live_view_frame()
                self._controller._set_latest_live_view_frame(frame)

                self._live_view_failure_since = None
                self._controller._mark_camera_ok()

            except Exception:
                if self._live_view_failure_since is None:
                    self._live_view_failure_since = now

                # Only surface a generic error if failures persist
                if (now - self._live_view_failure_since) >= self._controller.LIVE_VIEW_ERROR_AFTER:
                    self._controller._set_camera_error(
                        HealthCode.CAMERA_NOT_DETECTED,
                        "Camera not responding",
                    )

            time.sleep(0.5)  # ~2 FPS
