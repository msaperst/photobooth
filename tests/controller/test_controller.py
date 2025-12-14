import time

from controller.controller import (
    PhotoboothController,
    Command,
    CommandType,
    ControllerState,
)


def test_controller_starts_idle():
    controller = PhotoboothController()
    assert controller.state == ControllerState.IDLE


def test_start_session_transitions_states():
    controller = PhotoboothController()
    controller.start()

    controller.enqueue(Command(CommandType.START_SESSION))

    time.sleep(0.2)
    assert controller.state != ControllerState.IDLE

    time.sleep(5)
    assert controller.state == ControllerState.IDLE


def test_busy_flag():
    controller = PhotoboothController()
    controller.start()

    controller.enqueue(Command(CommandType.START_SESSION))

    time.sleep(0.2)
    status = controller.get_status()
    assert status["busy"] is True

    time.sleep(5)
    status = controller.get_status()
    assert status["busy"] is False
