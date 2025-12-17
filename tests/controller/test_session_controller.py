from datetime import date

from controller.session_storage import SessionStorage


def test_session_storage_creates_expected_paths(tmp_path):
    storage = SessionStorage(
        root=tmp_path,
        session_id="abc123",
        session_date=date(2025, 3, 8),
    )

    storage.prepare()

    assert storage.photos_dir.exists()
    assert storage.photos_dir.is_dir()
    assert storage.strip_path.parent == storage.session_dir


from controller.controller import PhotoboothController, ControllerState, Command, CommandType
from controller.health import HealthLevel
from tests.fakes.fake_camera import FakeCamera
from tests.helpers import wait_for


def test_finish_session_saves_strip(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    saved_paths = []

    class FakeStrip:
        def save(self, path):
            saved_paths.append(path)

    # Patch render_strip to return our fake strip
    monkeypatch.setattr(
        "controller.session_flow.render_strip",
        lambda *args, **kwargs: FakeStrip(),
    )

    controller.start()

    controller.enqueue(
        Command(
            CommandType.START_SESSION,
            payload={"image_count": 1},
        )
    )

    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    controller.enqueue(
        Command(CommandType.TAKE_PHOTO)
    )

    wait_for(lambda: controller.state == ControllerState.IDLE)

    # ---- Assertions ----
    assert len(saved_paths) == 1
    assert saved_paths[0].name == "strip.jpg"

    health = controller.get_health()
    assert health.level == HealthLevel.OK


def test_finish_session_worker_clears_session_and_returns_idle(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    monkeypatch.setattr("time.sleep", lambda _: None)

    controller.session_active = True
    controller.state = ControllerState.PROCESSING

    controller._finish_session_worker()

    assert controller.session_active is False
    assert controller.state == ControllerState.IDLE
