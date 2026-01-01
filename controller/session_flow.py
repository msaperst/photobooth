import threading
import time
import uuid
from datetime import date
from typing import TYPE_CHECKING

from controller.health import HealthCode, HealthSource
from controller.session_storage import SessionStorage
from imaging.strip_errors import StripCreationError
from imaging.strip_layout import StripLayout
from imaging.strip_renderer import render_strip

if TYPE_CHECKING:  # pragma: no cover
    from controller.controller import PhotoboothController, ControllerState


class SessionFlow:
    """
    Owns session lifecycle logic (start session, countdown, capture, finish).

    IMPORTANT:
    - Controller remains the single source of truth for state/health.
    - This module keeps behavior identical to the pre-refactor controller.py.
    """

    def __init__(self, controller: "PhotoboothController"):
        self._controller = controller

    # ---------- Command handlers ----------

    def start_session(self, payload: dict) -> None:
        with self._controller._state_lock:
            self._controller.session_active = True
            self._controller.photos_taken = 0
            self._controller.total_photos = payload.get("image_count", 3)
            from controller.controller import ControllerState  # local import
            self._controller._captured_image_paths = []
            self._controller._session_storage = SessionStorage(
                root=self._controller.sessions_root,
                session_id=str(uuid.uuid4()),
                session_date=date.today(),
            )
            self._controller._session_storage.prepare()
            self._controller.state = ControllerState.READY_FOR_PHOTO

    def begin_photo_capture(self) -> None:
        from controller.controller import ControllerState  # local import

        with self._controller._state_lock:
            if self._controller.state != ControllerState.READY_FOR_PHOTO:
                return
            self._controller.state = ControllerState.COUNTDOWN
            self._controller.countdown_remaining = self._controller.countdown_seconds

        threading.Thread(target=self._photo_capture_worker, daemon=True).start()

    # ---------- Workers ----------

    def _photo_capture_worker(self) -> None:
        from controller.controller import ControllerState  # local import

        # Countdown
        while True:
            with self._controller._state_lock:
                if self._controller.countdown_remaining <= 0:
                    break
            time.sleep(1)
            with self._controller._state_lock:
                self._controller.countdown_remaining -= 1

        with self._controller._state_lock:
            self._controller.state = ControllerState.CAPTURING_PHOTO

        try:
            path = self._controller.camera.capture(
                self._controller._session_storage.photos_dir
            )
            self._controller._captured_image_paths.append(path)
            self._controller._mark_camera_ok()

        except Exception:
            failed_photo_number = self._controller.photos_taken + 1
            self._controller._set_camera_error(
                HealthCode.CAMERA_NOT_DETECTED,
                (
                    f"Camera disconnected during photo "
                    f"{failed_photo_number} of {self._controller.total_photos}. "
                    f"Session was cancelled. Please start again."
                ),
                source=HealthSource.CAPTURE,
            )
            with self._controller._state_lock:
                self._controller.session_active = False
                # reset numbering to avoid “photo 2 of 3” confusion
                self._controller.photos_taken = 0
                self._controller.state = ControllerState.IDLE
            return

        with self._controller._state_lock:
            self._controller.photos_taken += 1
            if self._controller.photos_taken < self._controller.total_photos:
                self._controller.state = ControllerState.READY_FOR_PHOTO
                return

        self._finish_session()

    def _finish_session(self) -> None:
        threading.Thread(target=self._finish_session_worker, daemon=True).start()

    def _finish_session_worker(self) -> None:
        from controller.controller import ControllerState  # local import

        with self._controller._state_lock:
            self._controller.state = ControllerState.PROCESSING
        try:
            strip = render_strip(
                image_paths=self._controller._captured_image_paths,
                layout=StripLayout(
                    photo_size=(576, 384),
                    padding=12,
                    background_color=(255, 255, 255),
                    logo_path=self._controller.strip_logo_path,
                    logo_size=(576, 384),
                ),
            )

            storage = self._controller._session_storage
            strip.save(storage.strip_path)

        except StripCreationError as e:
            self._controller._set_processing_error(str(e))
            with self._controller._state_lock:
                self._controller.session_active = False
                self._controller.state = ControllerState.IDLE
            return

        with self._controller._state_lock:
            self._controller.state = ControllerState.PRINTING
        time.sleep(1)

        with self._controller._state_lock:
            self._controller.session_active = False
            self._controller.state = ControllerState.IDLE
