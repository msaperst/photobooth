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
    COUNTDOWN = auto()
    CAPTURING = auto()
    PROCESSING = auto()
    PRINTING = auto()


class CommandType(Enum):
    START_SESSION = auto()


class Command:
    def __init__(self, command_type, payload=None):
        self.command_type = command_type
        self.payload = payload or {}


class PhotoboothController:
    def __init__(self, camera: Camera):
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
            "busy": self.state != ControllerState.IDLE
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
            if self.state != ControllerState.IDLE:
                return

            self._run_session(command.payload)

    def _run_session(self, payload):
        self.state = ControllerState.COUNTDOWN
        time.sleep(1)

        self.state = ControllerState.CAPTURING
        image_count = payload.get("image_count", 3)
        self.camera.capture_images(image_count)

        self.state = ControllerState.PROCESSING
        time.sleep(1)

        self.state = ControllerState.PRINTING
        time.sleep(1)

        self.state = ControllerState.IDLE
