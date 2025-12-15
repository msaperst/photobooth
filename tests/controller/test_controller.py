from controller.controller import (
    PhotoboothController,
    Command,
    CommandType,
    ControllerState,
)
from tests.fakes.fake_camera import FakeCamera
from tests.helpers import wait_for


def test_manual_photo_progression(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)
    controller.start()

    controller.enqueue(
        Command(
            CommandType.START_SESSION,
            payload={"image_count": 3},
        )
    )

    for expected_count in range(1, 4):
        # Wait until controller is ready for the next photo
        wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

        controller.enqueue(Command(CommandType.TAKE_PHOTO))

        # Wait until that photo is captured
        wait_for(lambda: len(list(tmp_path.glob("*.jpg"))) == expected_count)

    # Final assertion (belt-and-suspenders)
    images = list(tmp_path.glob("*.jpg"))
    assert len(images) == 3


def test_controller_starts_idle(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)
    assert controller.state == ControllerState.IDLE


def test_start_session_enters_ready_for_photo(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)
    controller.start()

    controller.enqueue(Command(CommandType.START_SESSION))

    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)


def test_busy_flag_after_start_session(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)
    controller.start()

    controller.enqueue(Command(CommandType.START_SESSION))

    wait_for(lambda: controller.get_status()["busy"] is True)
