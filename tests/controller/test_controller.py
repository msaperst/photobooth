import time

from controller.controller import (
    PhotoboothController,
    Command,
    CommandType,
    ControllerState,
)
from tests.fakes.fake_camera import FakeCamera


def test_controller_calls_camera_capture(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera)
    controller.start()

    controller.enqueue(
        Command(
            CommandType.START_SESSION,
            payload={"image_count": 3},
        )
    )

    # Wait up to 5 seconds for images to appear
    deadline = time.time() + 5
    images = []

    while time.time() < deadline:
        images = list(tmp_path.glob("*.jpg"))
        if len(images) == 3:
            break
        time.sleep(0.05)

    assert len(images) == 3


def test_controller_starts_idle(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera)
    assert controller.state == ControllerState.IDLE


def test_start_session_transitions_states(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera)
    controller.start()

    controller.enqueue(Command(CommandType.START_SESSION))

    time.sleep(0.2)
    assert controller.state != ControllerState.IDLE

    time.sleep(5)
    assert controller.state == ControllerState.IDLE


def test_busy_flag(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera)
    controller.start()

    controller.enqueue(Command(CommandType.START_SESSION))

    time.sleep(0.2)
    status = controller.get_status()
    assert status["busy"] is True

    time.sleep(5)
    status = controller.get_status()
    assert status["busy"] is False
