from datetime import date

from controller.controller import PhotoboothController, ControllerState, Command, CommandType
from controller.health import HealthLevel, HealthCode
from controller.session_storage import SessionStorage
from tests.controller.test_controller import NoOpPrinter
from tests.fakes.fake_camera import FakeCamera
from tests.helpers import wait_for


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


def test_finish_session_saves_strip(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

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
        )
    )

    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    for expected_count in range(1, 4):
        wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)
        controller.enqueue(Command(CommandType.TAKE_PHOTO))
        wait_for(lambda: controller.photos_taken == expected_count)

    wait_for(lambda: controller.state == ControllerState.IDLE)

    assert [p.name for p in saved_paths] == ["strip.jpg", "print.jpg"]

    health = controller.get_health()
    assert health.level == HealthLevel.OK


def test_finish_session_worker_clears_session_and_returns_idle(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    monkeypatch.setattr("time.sleep", lambda _: None)

    controller.session_active = True
    controller.state = ControllerState.PROCESSING

    controller._finish_session_worker()

    assert controller.session_active is False
    assert controller.state == ControllerState.IDLE


def test_finish_session_recovers_from_unexpected_processing_exception(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

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
        Command(CommandType.START_SESSION)
    )
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    for expected_count in range(1, 4):
        wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)
        controller.enqueue(Command(CommandType.TAKE_PHOTO))
        wait_for(lambda: controller.photos_taken == expected_count)

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
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

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
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

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
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

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
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    controller.start()

    controller.enqueue(
        Command(CommandType.START_SESSION, payload={"image_count": 3, "print_count": 0})
    )
    wait_for(lambda: controller.session_active is True)

    assert controller.print_count == 1
    assert controller.get_status()["print_count"] == 1


def test_start_session_ignores_image_count_payload(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)
    controller.start()

    controller.enqueue(
        Command(CommandType.START_SESSION, payload={"image_count": 99, "print_count": 1})
    )

    wait_for(lambda: controller.session_active is True)
    assert controller.total_photos == controller.TOTAL_PHOTOS_PER_SESSION
    assert controller.total_photos == 3


def test_finish_session_print_preflight_failure_sets_printer_health(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    class PreflightFailPrinter:
        def __init__(self):
            self.print_called = False

        def preflight(self) -> None:
            raise RuntimeError("lp missing")

        def print_file(self, file_path, *, copies=1, job_name=None) -> None:
            self.print_called = True

    printer = PreflightFailPrinter()
    controller = PhotoboothController(camera=camera, printer=printer, image_root=tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    # Make rendering fast / deterministic (optional). If your existing tests already do this,
    # you can reuse those monkeypatches.
    class FakeStrip:
        def save(self, path): pass

    class FakeSheet:
        def save(self, path, **kwargs): pass

    monkeypatch.setattr("controller.session_flow.render_strip", lambda *a, **k: FakeStrip())
    monkeypatch.setattr("controller.session_flow.render_print_sheet", lambda *a, **k: FakeSheet())

    controller.start()
    controller.enqueue(Command(CommandType.START_SESSION, payload={"print_count": 2}))
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    for expected in range(1, 4):
        controller.enqueue(Command(CommandType.TAKE_PHOTO))
        wait_for(lambda: controller.photos_taken == expected)

    wait_for(lambda: controller.state == ControllerState.IDLE)

    assert printer.print_called is False

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.PRINTER_FAILED
    assert "lp missing" in (health.message or "")


def test_finish_session_print_failure_sets_printer_health(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    class FailingPrinter:
        def preflight(self) -> None:
            return

        def print_file(self, file_path, *, copies=1, job_name=None) -> None:
            raise RuntimeError("printer offline")

    controller = PhotoboothController(camera=camera, printer=FailingPrinter(), image_root=tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    class FakeStrip:
        def save(self, path): pass

    class FakeSheet:
        def save(self, path, **kwargs): pass

    monkeypatch.setattr("controller.session_flow.render_strip", lambda *a, **k: FakeStrip())
    monkeypatch.setattr("controller.session_flow.render_print_sheet", lambda *a, **k: FakeSheet())

    controller.start()
    controller.enqueue(Command(CommandType.START_SESSION, payload={"print_count": 1}))
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    for expected in range(1, 4):
        controller.enqueue(Command(CommandType.TAKE_PHOTO))
        wait_for(lambda: controller.photos_taken == expected)

    wait_for(lambda: controller.state == ControllerState.IDLE)

    # Since printing happens in a daemon thread, give the health update a moment.
    wait_for(lambda: controller.get_health().level == HealthLevel.ERROR)

    health = controller.get_health()
    assert health.code == HealthCode.PRINTER_FAILED
    assert "printer offline" in (health.message or "")


def test_finish_session_starts_print_job_with_correct_copies(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    calls = []

    class RecordingPrinter:
        def preflight(self) -> None:
            return

        def print_file(self, file_path, *, copies=1, job_name=None) -> None:
            calls.append((file_path, copies, job_name))

    controller = PhotoboothController(camera=camera, printer=RecordingPrinter(), image_root=tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    class FakeStrip:
        def save(self, path): pass

    class FakeSheet:
        def save(self, path, **kwargs): pass

    monkeypatch.setattr("controller.session_flow.render_strip", lambda *a, **k: FakeStrip())
    monkeypatch.setattr("controller.session_flow.render_print_sheet", lambda *a, **k: FakeSheet())

    controller.start()
    controller.enqueue(Command(CommandType.START_SESSION, payload={"print_count": 3}))
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    for expected in range(1, 4):
        controller.enqueue(Command(CommandType.TAKE_PHOTO))
        wait_for(lambda: controller.photos_taken == expected)

    wait_for(lambda: controller.state == ControllerState.IDLE)

    # Wait until print thread runs
    wait_for(lambda: len(calls) == 1)

    file_path, copies, job_name = calls[0]
    assert file_path.name == "print.jpg"
    assert copies == 3
    assert job_name == "Photobooth Print"


def test_printer_recovery_clears_health_and_retries_pending_print(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    class FlakyPrinter:
        def __init__(self):
            self.preflight_ok = False
            self.print_calls = 0

        def preflight(self) -> None:
            if not self.preflight_ok:
                raise RuntimeError("lp missing")

        def print_file(self, file_path, *, copies=1, job_name=None) -> None:
            self.print_calls += 1

    printer = FlakyPrinter()
    controller = PhotoboothController(camera=camera, printer=printer, image_root=tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    # Make rendering fast
    class FakeStrip:
        def save(self, path): pass

    class FakeSheet:
        def save(self, path, **kwargs): pass

    monkeypatch.setattr("controller.session_flow.render_strip", lambda *a, **k: FakeStrip())
    monkeypatch.setattr("controller.session_flow.render_print_sheet", lambda *a, **k: FakeSheet())

    controller.start()
    controller.enqueue(Command(CommandType.START_SESSION, payload={"print_count": 2}))
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    for expected in range(1, 4):
        controller.enqueue(Command(CommandType.TAKE_PHOTO))
        wait_for(lambda: controller.photos_taken == expected)

    wait_for(lambda: controller.state == ControllerState.IDLE)

    # Preflight failed: printer error set, no print calls yet, booth blocked
    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.PRINTER_FAILED
    assert printer.print_calls == 0
    assert controller.get_status()["busy"] is True

    # "Fix" printer and force recovery attempt timing
    printer.preflight_ok = True
    controller._last_printer_recovery_attempt = 0.0

    # Trigger recovery directly (deterministic, no waiting on run loop timing)
    controller._poll_printer_health_if_idle()

    # Should clear health and retry printing (async thread)
    wait_for(lambda: controller.get_health().level == HealthLevel.OK)
    wait_for(lambda: printer.print_calls == 1)
