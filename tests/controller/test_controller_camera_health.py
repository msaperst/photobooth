import time

from controller.controller import PhotoboothController
from controller.health import HealthLevel, HealthCode
from tests.fakes.fake_camera import FakeCamera


def test_camera_not_detected_sets_health(tmp_path):
    camera = FakeCamera(tmp_path)
    camera.connected = False

    controller = PhotoboothController(camera, tmp_path, camera_health_interval=0.05)
    controller.start()

    time.sleep(0.3)

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.CAMERA_NOT_DETECTED

    controller.stop()


def test_camera_reconnect_clears_health(tmp_path):
    camera = FakeCamera(tmp_path)
    camera.connected = False

    controller = PhotoboothController(camera, tmp_path, camera_health_interval=0.05)
    controller.start()

    time.sleep(0.3)
    assert controller.get_health().level == HealthLevel.ERROR

    camera.connected = True
    time.sleep(0.4)

    health = controller.get_health()
    assert health.level == HealthLevel.OK

    controller.stop()
