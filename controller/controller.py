"""
Photobooth controller

Single authoritative owner of camera, printer, and session state.
"""

import threading
import time
from enum import Enum, auto
from pathlib import Path
from queue import Queue, Empty

from controller.camera import Camera


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
    def __init__(self, camera: Camera, image_root: Path):
        self._state_lock = threading.Lock()
        self.total_photos = 3
        self.photos_taken = 0
        self.session_active = False

        self.countdown_seconds = 3
        self.countdown_remaining = 0

        self.camera = camera
        self.image_root = image_root
        self.state = ControllerState.IDLE
        self.command_queue = Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = False

        self._latest_live_view_frame: bytes | None = None
        self._live_view_lock = threading.Lock()
        self._live_view_running = False

    def start(self):
        self._running = True
        if self.camera.health_check():
            self.camera.start_live_view()
            self._start_live_view_worker()
        self._thread.start()

    def stop(self):
        self._running = False
        try:
            self.camera.stop_live_view()
        except Exception:
            pass

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

    def get_live_view_frame(self) -> bytes | None:
        with self._live_view_lock:
            return self._latest_live_view_frame

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
            # with self._state_lock:
            if self.state == ControllerState.IDLE:
                self._start_session(command.payload)

        elif command.command_type == CommandType.TAKE_PHOTO:
            # with self._state_lock:
            if self.state == ControllerState.READY_FOR_PHOTO:
                self._begin_photo_capture()

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
        while True:
            with self._state_lock:
                if self.countdown_remaining <= 0:
                    break
            time.sleep(1)
            with self._state_lock:
                self.countdown_remaining -= 1

        with self._state_lock:
            self.state = ControllerState.CAPTURING_PHOTO
            self.camera.stop_live_view()

        try:
            self.camera.capture(self.image_root)
        except Exception as e:
            with self._state_lock:
                print(f"Camera capture failed: {repr(e)}")
                self.state = ControllerState.IDLE
            return

        with self._state_lock:
            self.photos_taken += 1
            self.camera.start_live_view()
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

    def _start_live_view_worker(self):
        if self._live_view_running:
            return

        self._live_view_running = True

        threading.Thread(
            target=self._live_view_worker,
            daemon=True,
        ).start()

    def _live_view_worker(self):
        while self._running:
            with self._state_lock:
                if self.state not in (
                        ControllerState.IDLE,
                        ControllerState.READY_FOR_PHOTO,
                ):
                    time.sleep(0.2)
                    continue

            try:
                frame = self.camera.get_live_view_frame()
                with self._live_view_lock:
                    self._latest_live_view_frame = frame
            except Exception:
                pass

            # 🔑 CRITICAL: throttle
            time.sleep(0.5)  # ~2 FPS, realistic for Nikon
