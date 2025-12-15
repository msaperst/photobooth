"""
Photobooth controller

Single authoritative owner of camera, printer, and session state.
"""

import threading
import time
from enum import Enum, auto
from queue import Queue

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
    def __init__(self, camera: Camera):
        self.total_photos = 3
        self.photos_taken = 0
        self.session_active = False

        self.countdown_seconds = 3
        self.countdown_remaining = 0

        self.camera = camera
        self.state = ControllerState.IDLE
        self.command_queue = Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = False

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False

    def enqueue(self, command: Command):
        self.command_queue.put(command)

    def get_status(self):
        return {
            "state": self.state.name,
            "busy": self.state != ControllerState.IDLE,
            "photos_taken": self.photos_taken,
            "total_photos": self.total_photos,
            "countdown_remaining": self.countdown_remaining,
        }

    def _run(self):
        while self._running:
            try:
                command = self.command_queue.get(timeout=0.1)
                self._handle_command(command)
            except Exception:
                pass

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
        self.state = ControllerState.COUNTDOWN
        self.countdown_remaining = self.countdown_seconds

        while self.countdown_remaining > 0:
            time.sleep(1)
            self.countdown_remaining -= 1

        self.state = ControllerState.CAPTURING_PHOTO
        self.camera.capture_images(1)
        self.photos_taken += 1

        if self.photos_taken < self.total_photos:
            self.state = ControllerState.READY_FOR_PHOTO
        else:
            self._finish_session()

    def _finish_session(self):
        self.state = ControllerState.PROCESSING
        time.sleep(1)

        self.state = ControllerState.PRINTING
        time.sleep(1)

        self.session_active = False
        self.state = ControllerState.IDLE
