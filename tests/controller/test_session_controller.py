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
    assert storage.print_path.parent == storage.session_dir


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

    class FakeSheet:
        def save(self, path, **kwargs):
            saved_paths.append(path)

    monkeypatch.setattr(
        "controller.session_flow.render_strip",
        lambda *args, **kwargs: FakeStrip(),
    )

    monkeypatch.setattr(
        "controller.session_flow.render_print_sheet",
        lambda *args, **kwargs: FakeSheet(),
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

    assert [p.name for p in saved_paths] == ["strip.jpg", "print.jpg"]

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


def test_finish_session_recovers_from_unexpected_processing_exception(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    class ExplodingStrip:
        def save(self, path):
            raise RuntimeError("disk full")

    # Make render_strip succeed but saving fail with a non-StripCreationError
    monkeypatch.setattr(
        "controller.session_flow.render_strip",
        lambda *args, **kwargs: ExplodingStrip(),
    )

    # Start controller loop
    controller.start()

    # Start a 1-photo session
    controller.enqueue(
        Command(CommandType.START_SESSION, payload={"image_count": 1})
    )
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    # Take the single photo (triggers finish worker)
    controller.enqueue(Command(CommandType.TAKE_PHOTO))

    # Controller must recover to IDLE (not stranded in PROCESSING)
    wait_for(lambda: controller.state == ControllerState.IDLE)

    # Session should be cleared and health should show error
    assert controller.session_active is False

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.message is not None
    assert "disk full" in health.message


def test_start_session_stores_print_count(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    controller.start()

    controller.enqueue(
        Command(CommandType.START_SESSION, payload={"image_count": 3, "print_count": 4})
    )

    wait_for(lambda: controller.session_active is True)

    assert controller.print_count == 4
    status = controller.get_status()
    assert status["print_count"] == 4


def test_start_session_clamps_print_count(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    controller.start()

    controller.enqueue(
        Command(CommandType.START_SESSION, payload={"image_count": 3, "print_count": 999})
    )
    wait_for(lambda: controller.session_active is True)

    assert controller.print_count == 4


def test_start_session_invalid_print_count_defaults_to_one(tmp_path, monkeypatch):
    """
    Branch coverage:
    - int(raw_print_count) raises ValueError/TypeError
    - print_count defaults to 1
    """
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    controller.start()

    # ValueError path: int("not-an-int") -> ValueError
    controller.enqueue(
        Command(CommandType.START_SESSION, payload={"image_count": 3, "print_count": "not-an-int"})
    )
    wait_for(lambda: controller.session_active is True)

    assert controller.print_count == 1
    assert controller.get_status()["print_count"] == 1


def test_start_session_print_count_below_one_is_clamped_to_one(tmp_path, monkeypatch):
    """
    Branch coverage:
    - print_count < 1 triggers clamp to 1
    """
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    controller.start()

    controller.enqueue(
        Command(CommandType.START_SESSION, payload={"image_count": 3, "print_count": 0})
    )
    wait_for(lambda: controller.session_active is True)

    assert controller.print_count == 1
    assert controller.get_status()["print_count"] == 1
