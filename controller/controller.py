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
        self._live_view_started = False

    def start(self):
        self._running = True
        # Start live view immediately if camera is available
        if self.camera.health_check():
            try:
                self.camera.start_live_view()
                self._live_view_started = True
            except Exception as e:
                print(f"Live view start failed: {repr(e)}")
        self._thread.start()

    def stop(self):
        self._running = False

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
        """
        Return a JPEG frame if we're in a state where preview is allowed.
        Return None if not allowed or frame unavailable.
        """
        with self._state_lock:
            allowed = self.state in (ControllerState.READY_FOR_PHOTO, ControllerState.IDLE)
            if not allowed:
                return None

        # Start on-demand (outside lock to avoid blocking controller state)
        if not self._live_view_started:
            try:
                self.camera.start_live_view()
                self._live_view_started = True
            except Exception as e:
                print(f"Live view start failed: {repr(e)}")
                return None

        try:
            return self.camera.get_live_view_frame()
        except Exception as e:
            # Do not spam logs too hard; but keep a breadcrumb
            print(f"Live view frame error: {repr(e)}")
            return None

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
                self.countdown_remaining -= 1
            time.sleep(1)

        with self._state_lock:
            self.state = ControllerState.CAPTURING_PHOTO

        # Stop live view during capture to avoid camera conflicts
        if self._live_view_started:
            try:
                self.camera.stop_live_view()
            except Exception as e:
                print(f"Live view stop failed: {repr(e)}")
            self._live_view_started = False

        try:
            self.camera.capture(self.image_root)
        except Exception as e:
            with self._state_lock:
                print(f"Camera capture failed: {repr(e)}")
                self.state = ControllerState.IDLE
            return

        # Restart live view after capture
        try:
            self.camera.start_live_view()
            self._live_view_started = True
        except Exception as e:
            print(f"Live view restart failed: {repr(e)}")
            self._live_view_started = False

        with self._state_lock:
            self.photos_taken += 1
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
