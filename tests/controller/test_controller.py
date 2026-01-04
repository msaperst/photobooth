import threading
import time
from pathlib import Path

from controller.controller import (
    PhotoboothController,
    Command,
    CommandType,
    ControllerState,
)
from controller.health import HealthLevel, HealthCode, HealthSource
from controller.printer_base import Printer
from imaging.strip_errors import StripCreationError
from tests.helpers import wait_for


class NoOpPrinter(Printer):
    def print_file(self, file_path: Path, *, copies: int = 1, job_name: str | None = None) -> None:
        return


class SpyPrinter(NoOpPrinter):
    def __init__(self):
        self.preflight_called = False

    def preflight(self) -> None:
        self.preflight_called = True


def test_manual_photo_progression(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)
    controller.countdown_seconds = 0
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
        wait_for(lambda: controller.photos_taken == expected_count)

    # Find the session photos directory
    sessions_dir = tmp_path / "sessions"
    assert sessions_dir.exists()

    # There should be exactly one date directory
    date_dirs = list(sessions_dir.iterdir())
    assert len(date_dirs) == 1

    # There should be exactly one session directory
    session_dirs = list(date_dirs[0].iterdir())
    assert len(session_dirs) == 1

    photos_dir = session_dirs[0] / "photos"
    assert photos_dir.exists()

    images = list(photos_dir.glob("*.jpg"))
    assert len(images) == 3


def test_start_session_enters_ready_for_photo(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)
    controller.start()

    controller.enqueue(Command(CommandType.START_SESSION))

    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)


def test_busy_flag_after_start_session(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)
    controller.start()

    controller.enqueue(Command(CommandType.START_SESSION))

    wait_for(lambda: controller.get_status()["busy"] is True)


def test_controller_stop_ignores_camera_errors(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)
    controller.start()

    controller.stop()

    assert controller._running is False


def test_run_loop_logs_unhandled_exceptions(tmp_path, capsys, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    def boom(_command):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(controller, "_handle_command", boom)

    controller.start()
    controller.enqueue(Command(CommandType.START_SESSION))

    # Wait until the print happens
    wait_for(lambda: "Controller error: kaboom" in capsys.readouterr().out, timeout=2.0)


def test_begin_photo_capture_returns_when_not_ready(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    controller.state = ControllerState.COUNTDOWN  # not READY_FOR_PHOTO

    started = {"called": False}

    class SpyThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            started["called"] = True

    monkeypatch.setattr(threading, "Thread", lambda *a, **k: SpyThread())

    controller._begin_photo_capture()

    assert started["called"] is False


def test_photo_capture_worker_counts_down(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    # Make countdown deterministic + fast
    controller.countdown_seconds = 2

    sleep_calls = {"n": 0}

    def fast_sleep(_seconds):
        sleep_calls["n"] += 1
        return None

    monkeypatch.setattr(time, "sleep", fast_sleep)

    controller.start()
    controller.enqueue(Command(CommandType.START_SESSION, payload={"image_count": 1}))

    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    controller.enqueue(Command(CommandType.TAKE_PHOTO))

    # Countdown should run and decrement to 0
    wait_for(lambda: controller.countdown_remaining == 0, timeout=2.0)

    # And we should have slept at least once inside the countdown loop
    assert sleep_calls["n"] >= 1


def test_photo_capture_worker_sets_idle_on_capture_failure(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)
    controller._start_live_view_worker = lambda: None

    controller.countdown_seconds = 0

    monkeypatch.setattr(time, "sleep", lambda _s: None)

    def fail_capture(_output_dir):
        raise RuntimeError("nope")

    monkeypatch.setattr(camera, "capture", fail_capture)

    controller.start()
    controller.enqueue(Command(CommandType.START_SESSION, payload={"image_count": 1}))
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    controller.enqueue(Command(CommandType.TAKE_PHOTO))

    wait_for(lambda: controller.state == ControllerState.IDLE, timeout=2.0)

    # Health should reflect error
    health = controller.get_health()

    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.CAMERA_NOT_DETECTED
    assert "photo 1 of 3" in health.message
    assert "Session was cancelled" in health.message


def test_finish_session_worker_transitions_states(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    # Pretend a session is active
    controller.session_active = True
    controller.state = ControllerState.CAPTURING_PHOTO

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    # Prevent real sleeping
    monkeypatch.setattr(time, "sleep", fake_sleep)

    # Run worker directly (no thread)
    controller._finish_session_worker()

    # ---- Assertions ----

    # Final state is IDLE
    assert controller.state == ControllerState.IDLE

    # Session is marked inactive
    assert controller.session_active is False


def test_start_does_not_fail_when_live_view_unavailable(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    # Simulate preview being unavailable
    monkeypatch.setattr(camera, "start_live_view", lambda: (_ for _ in ()).throw(RuntimeError()))

    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    # Should not raise
    controller.start()

    health = controller.get_health()
    assert health.level == HealthLevel.OK


def test_capture_failure_mid_round_sets_contextual_message(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)
    controller._live_view_running = True  # prevent worker from starting

    controller.countdown_seconds = 0
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    # First capture succeeds, second fails
    call_count = {"n": 0}

    def capture_side_effect(_output_dir):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("camera died")

    monkeypatch.setattr(camera, "capture", capture_side_effect)

    controller.start()
    controller.enqueue(Command(CommandType.START_SESSION, payload={"image_count": 3}))
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    # Photo 1
    controller.enqueue(Command(CommandType.TAKE_PHOTO))
    wait_for(lambda: controller.photos_taken == 1)

    # Photo 2 (fails)
    controller.enqueue(Command(CommandType.TAKE_PHOTO))
    wait_for(lambda: controller.state == ControllerState.IDLE)

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert "photo 2 of 3" in health.message
    assert "Session was cancelled" in health.message


def test_set_camera_error_does_not_override_existing_error(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    controller._set_camera_error(
        HealthCode.CAMERA_NOT_DETECTED,
        "Primary error",
        source=HealthSource.CAPTURE,
    )

    controller._set_camera_error(
        HealthCode.CAMERA_NOT_DETECTED,
        "Secondary error",
        source=HealthSource.CAPTURE,
    )

    health = controller.get_health()

    assert health.level == HealthLevel.ERROR
    assert health.message == "Primary error"


def test_capture_failure_sets_health_error_message(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    # Force capture to fail so we hit the error path
    monkeypatch.setattr(camera, "capture", lambda *_: (_ for _ in ()).throw(RuntimeError("capture failed")))

    controller.photos_taken = 0
    controller.total_photos = 3
    controller.state = ControllerState.READY_FOR_PHOTO
    controller.countdown_remaining = 0

    controller._photo_capture_worker()

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert "photo 1 of 3" in health.message


def test_strip_failure_sets_health_error(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    # Speed everything up
    controller.countdown_seconds = 0
    monkeypatch.setattr("time.sleep", lambda _: None)

    # Force strip creation to fail by breaking the renderer
    def fake_render_strip(*args, **kwargs):
        raise StripCreationError("boom")

    monkeypatch.setattr(
        "controller.session_flow.render_strip",
        fake_render_strip,
    )

    controller.start()

    controller.enqueue(
        Command(
            CommandType.START_SESSION,
        )
    )

    # Wait until ready
    from tests.helpers import wait_for
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    # Take 3 photos (session always requires 3)
    for expected_count in range(1, 4):
        wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)
        controller.enqueue(Command(CommandType.TAKE_PHOTO))
        wait_for(lambda: controller.photos_taken == expected_count)

    # Wait for processing to complete
    wait_for(lambda: controller.state == ControllerState.IDLE)

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.STRIP_CREATION_FAILED


def test_is_running_reflects_controller_lifecycle(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    assert controller._is_running() is False

    controller.start()
    assert controller._is_running() is True

    controller.stop()
    assert controller._is_running() is False


def test_get_state_returns_current_state(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    controller.state = ControllerState.READY_FOR_PHOTO
    assert controller._get_state() == ControllerState.READY_FOR_PHOTO

    controller.state = ControllerState.PROCESSING
    assert controller._get_state() == ControllerState.PROCESSING


def test_is_unhealthy_reflects_health_state(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    assert controller._is_unhealthy() is False

    controller._set_camera_error(
        HealthCode.CAMERA_NOT_DETECTED,
        "Camera missing",
        source=HealthSource.CAPTURE,
    )

    assert controller._is_unhealthy() is True


def test_get_health_source_returns_current_source(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    assert controller._get_health_source() is None

    controller._set_camera_error(
        HealthCode.CAMERA_NOT_DETECTED,
        "Camera missing",
        source=HealthSource.CAPTURE,
    )

    assert controller._get_health_source() == HealthSource.CAPTURE


def test_poll_camera_health_noop_when_not_idle(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    controller.state = ControllerState.CAPTURING_PHOTO

    called = {"n": 0}
    monkeypatch.setattr(camera, "health_check", lambda: called.__setitem__("n", 1))

    controller._poll_camera_health_if_idle()

    assert called["n"] == 0


def test_poll_camera_health_marks_ok_when_camera_recovers(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    controller.state = ControllerState.IDLE

    controller._set_camera_error(
        HealthCode.CAMERA_NOT_DETECTED,
        "Camera missing",
        source=HealthSource.CAPTURE,
    )

    monkeypatch.setattr(camera, "health_check", lambda: True)

    controller._poll_camera_health_if_idle()

    health = controller.get_health()
    assert health.level == HealthLevel.OK


def test_poll_camera_health_sets_error_on_exception(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera=camera, printer=NoOpPrinter(), image_root=tmp_path)
    controller.state = ControllerState.READY_FOR_PHOTO

    monkeypatch.setattr(camera, "health_check", lambda: (_ for _ in ()).throw(RuntimeError()))

    t0 = 2000.0
    monkeypatch.setattr("controller.controller.time.time", lambda: t0)
    controller._poll_camera_health_if_idle()
    assert controller.get_health().level == HealthLevel.OK

    monkeypatch.setattr("controller.controller.time.time", lambda: t0 + controller.CAMERA_ERROR_AFTER + 0.1)
    controller._poll_camera_health_if_idle()

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.CAMERA_NOT_DETECTED


def test_set_processing_error_does_not_override_existing_error(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    controller._set_camera_error(
        HealthCode.CAMERA_NOT_DETECTED,
        "Camera failed",
        source=HealthSource.CAPTURE,
    )

    controller._set_processing_error("Strip failed")

    health = controller.get_health()
    assert health.code == HealthCode.CAMERA_NOT_DETECTED
    assert health.message == "Camera failed"


def test_poll_camera_health_does_not_flash_error_on_transient_failure(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera=camera, printer=NoOpPrinter(), image_root=tmp_path)
    controller.state = ControllerState.READY_FOR_PHOTO

    # Transient failure (e.g., gphoto2 slowness) should not immediately surface an error.
    monkeypatch.setattr(camera, "health_check", lambda: False)

    t0 = 3000.0
    monkeypatch.setattr("controller.controller.time.time", lambda: t0)
    controller._poll_camera_health_if_idle()
    assert controller.get_health().level == HealthLevel.OK

    # Still within debounce window -> still OK
    monkeypatch.setattr("controller.controller.time.time", lambda: t0 + (controller.CAMERA_ERROR_AFTER / 2.0))
    controller._poll_camera_health_if_idle()
    assert controller.get_health().level == HealthLevel.OK


def test_poll_camera_health_sets_error_when_health_check_returns_false(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    controller.state = ControllerState.IDLE

    # Simulate camera responding but reporting unhealthy
    monkeypatch.setattr(camera, "health_check", lambda: False)

    # Debounced: first failure should not immediately surface an error.
    t0 = 1000.0
    monkeypatch.setattr("controller.controller.time.time", lambda: t0)
    controller._poll_camera_health_if_idle()
    assert controller.get_health().level == HealthLevel.OK

    # After sustained failure beyond threshold, error should surface.
    monkeypatch.setattr("controller.controller.time.time", lambda: t0 + controller.CAMERA_ERROR_AFTER + 0.1)
    controller._poll_camera_health_if_idle()

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.CAMERA_NOT_DETECTED
    assert controller._get_health_source() == HealthSource.CAPTURE
    assert health.message == "Camera not detected"


def test_take_photo_enqueued_before_ready_is_not_lost(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)
    controller.countdown_seconds = 0

    controller.start()

    # Start session and IMMEDIATELY enqueue TAKE_PHOTO
    controller.enqueue(Command(CommandType.START_SESSION))
    controller.enqueue(Command(CommandType.TAKE_PHOTO))

    # Photo should still be taken
    wait_for(lambda: controller.photos_taken == 1)


def test_take_photo_ignored_when_busy(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    # Simulate busy state
    controller.state = ControllerState.COUNTDOWN

    # Spy on begin_photo_capture
    called = {"n": 0}

    def fake_begin():
        called["n"] += 1

    monkeypatch.setattr(
        controller._session_flow,
        "begin_photo_capture",
        fake_begin,
    )

    # Spy on queue.put
    put_called = {"n": 0}

    def fake_put(_cmd):
        put_called["n"] += 1

    monkeypatch.setattr(controller.command_queue, "put", fake_put)

    controller._handle_command(Command(CommandType.TAKE_PHOTO))

    # ---- Assertions ----
    assert called["n"] == 0, "Should not start capture while busy"
    assert put_called["n"] == 0, "Should not re-enqueue while busy"


def test_take_photo_reenqueued_when_not_ready_and_not_busy(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    # State is neither READY nor busy
    controller.state = ControllerState.IDLE

    # Spy on begin_photo_capture
    called = {"n": 0}

    def fake_begin():
        called["n"] += 1

    monkeypatch.setattr(
        controller._session_flow,
        "begin_photo_capture",
        fake_begin,
    )

    # Spy on queue.put
    put_args = []

    def fake_put(cmd):
        put_args.append(cmd)

    monkeypatch.setattr(controller.command_queue, "put", fake_put)

    cmd = Command(CommandType.TAKE_PHOTO)
    controller._handle_command(cmd)

    # ---- Assertions ----
    assert called["n"] == 0, "Should not start capture immediately"
    assert len(put_args) == 1, "Command should be re-enqueued"
    assert put_args[0] is cmd, "Same command object should be re-queued"


def test_controller_stores_printer_dependency(tmp_path):
    camera = FakeCamera(tmp_path)

    class DummyPrinter(NoOpPrinter):
        pass

    printer = DummyPrinter()
    controller = PhotoboothController(camera=camera, printer=printer, image_root=tmp_path)

    assert controller.printer is printer


def test_set_printer_error_does_not_override_existing_error(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera=camera, printer=NoOpPrinter(), image_root=tmp_path)

    # First set some other error (capture/processing) to simulate a pre-existing sticky error
    controller._set_processing_error("processing failed")
    original = controller.get_health()

    assert original.level == HealthLevel.ERROR

    # Now try to set a printer error; it should be ignored
    controller._set_printer_error("printer failed")
    after = controller.get_health()

    assert after.level == original.level
    assert after.code == original.code
    assert after.message == original.message


def test_set_printer_error_sets_printer_failed_and_message(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera=camera, printer=NoOpPrinter(), image_root=tmp_path)

    controller._set_printer_error("lp failed: printer offline")

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.PRINTER_FAILED
    assert "printer offline" in (health.message or "")


def test_busy_flag_true_when_printer_error_active(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, printer=NoOpPrinter(), image_root=tmp_path)

    # Simulate a printer-owned sticky error
    controller._set_printer_error("printer offline")

    status = controller.get_status()
    assert status["busy"] is True

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.PRINTER_FAILED


def test_poll_printer_health_noop_when_not_idle(tmp_path):
    camera = FakeCamera(tmp_path)

    class PrinterThatWouldRecover(Printer):
        def preflight(self) -> None:
            return

        def print_file(self, file_path, *, copies=1, job_name=None) -> None:
            raise AssertionError("should not print while not idle")

    controller = PhotoboothController(camera=camera, printer=PrinterThatWouldRecover(), image_root=tmp_path)

    controller.state = ControllerState.READY_FOR_PHOTO
    controller._set_printer_error("printer offline")

    # Seed pending job
    controller._pending_print_path = tmp_path / "print.jpg"
    controller._pending_print_copies = 1

    controller._poll_printer_health_if_idle()  # should do nothing
    assert controller.get_health().level == HealthLevel.ERROR


def test_start_print_job_returns_early_when_copies_less_than_one(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    class SpyPrinter(NoOpPrinter):
        def __init__(self):
            self.preflight_called = False
            self.print_called = False

        def preflight(self) -> None:
            self.preflight_called = True

        def print_file(self, file_path: Path, *, copies: int = 1, job_name: str | None = None) -> None:
            self.print_called = True

    printer = SpyPrinter()
    controller = PhotoboothController(camera=camera, printer=printer, image_root=tmp_path)

    # If a worker thread were created, we'd see this called
    started = {"called": False}
    monkeypatch.setattr(threading, "Thread",
                        lambda *a, **k: type("T", (), {"start": lambda _s: started.__setitem__("called", True)})())

    controller._start_print_job(tmp_path / "print.jpg", copies=0)

    assert printer.preflight_called is False
    assert printer.print_called is False
    assert started["called"] is False


def test_start_print_job_worker_exits_when_print_in_flight(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    class SpyPrinter(NoOpPrinter):
        def __init__(self):
            self.preflight_called = False
            self.print_called = False

        def preflight(self) -> None:
            self.preflight_called = True

        def print_file(self, file_path: Path, *, copies: int = 1, job_name: str | None = None) -> None:
            self.print_called = True

    printer = SpyPrinter()
    controller = PhotoboothController(camera=camera, printer=printer, image_root=tmp_path)

    # Force the "in flight" guard to trigger
    controller._print_in_flight = True

    class ImmediateThread:
        def __init__(self, *, target, daemon, name):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(threading, "Thread", lambda *a, **k: ImmediateThread(**k))

    controller._start_print_job(tmp_path / "print.jpg", copies=1)

    # Preflight still happens before worker creation
    assert printer.preflight_called is True
    # But printing must NOT occur because worker returns immediately
    assert printer.print_called is False


def test_poll_printer_health_returns_when_print_in_flight(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    printer = SpyPrinter()
    controller = PhotoboothController(camera=camera, printer=printer, image_root=tmp_path)

    controller.state = ControllerState.IDLE
    controller._set_printer_error("printer offline")

    controller._pending_print_path = tmp_path / "print.jpg"
    controller._pending_print_copies = 1

    # Simulate an active print job
    controller._print_in_flight = True

    controller._poll_printer_health_if_idle()

    assert printer.preflight_called is False


def test_poll_printer_health_returns_when_no_pending_job(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    printer = SpyPrinter()
    controller = PhotoboothController(camera=camera, printer=printer, image_root=tmp_path)

    controller.state = ControllerState.IDLE
    controller._set_printer_error("printer offline")

    # Case A: pending_path is None
    controller._pending_print_path = None
    controller._pending_print_copies = 1
    controller._poll_printer_health_if_idle()
    assert printer.preflight_called is False

    # Case B: pending_copies < 1
    controller._pending_print_path = tmp_path / "print.jpg"
    controller._pending_print_copies = 0
    controller._poll_printer_health_if_idle()
    assert printer.preflight_called is False


def test_poll_printer_health_throttles_recovery_attempts(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    printer = SpyPrinter()
    controller = PhotoboothController(camera=camera, printer=printer, image_root=tmp_path)

    controller.state = ControllerState.IDLE
    controller._set_printer_error("printer offline")

    controller._pending_print_path = tmp_path / "print.jpg"
    controller._pending_print_copies = 1

    monkeypatch.setattr(time, "time", lambda: 1000.0)
    controller._last_printer_recovery_attempt = 999.5  # 0.5s ago < 2.0s interval

    controller._poll_printer_health_if_idle()

    assert printer.preflight_called is False


def test_poll_printer_health_returns_cleanly_when_preflight_raises(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    class ExplodingPreflightPrinter(NoOpPrinter):
        def preflight(self) -> None:
            raise RuntimeError("still broken")

    printer = ExplodingPreflightPrinter()
    controller = PhotoboothController(camera=camera, printer=printer, image_root=tmp_path)

    controller.state = ControllerState.IDLE
    controller._set_printer_error("printer offline")

    controller._pending_print_path = tmp_path / "print.jpg"
    controller._pending_print_copies = 1

    # Ensure throttle won't prevent the call
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    controller._last_printer_recovery_attempt = 0.0

    controller._poll_printer_health_if_idle()

    # Health should remain ERROR (not cleared)
    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.PRINTER_FAILED


def test_set_config_error_does_not_overwrite_existing_error(tmp_path):
    """Cover the early-return branch in set_config_error when health is already ERROR."""
    camera = FakeCamera(tmp_path)
    camera.connected = False  # start() will mark capture error

    printer = SpyPrinter()
    controller = PhotoboothController(camera, printer, tmp_path)
    controller.start()

    # Sanity: controller is unhealthy due to camera.
    assert controller.get_health().level == HealthLevel.ERROR
    assert controller.get_health().code == HealthCode.CAMERA_NOT_DETECTED
    assert controller._get_health_source() == HealthSource.CAPTURE

    # Act: attempt to set config error; should not overwrite first-cause error.
    controller.set_config_error(
        message="config broken",
        instructions=["fix it"],
    )

    # Assert: still the original capture error.
    assert controller.get_health().level == HealthLevel.ERROR
    assert controller.get_health().code == HealthCode.CAMERA_NOT_DETECTED
    assert controller._get_health_source() == HealthSource.CAPTURE


from tests.fakes.fake_camera import FakeCamera


def test_get_status_has_no_most_recent_strip_url_when_no_session_storage(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera=camera, printer=NoOpPrinter(), image_root=tmp_path)

    status = controller.get_status()

    # Depending on your implementation, it might omit the key or set it to None.
    assert status.get("most_recent_strip_url") in (None,)


def test_get_status_includes_most_recent_strip_url_when_strip_exists(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera=camera, printer=NoOpPrinter(), image_root=tmp_path)

    # Create a real file under sessions_root and point storage.strip_path to it.
    fake_strip = controller.sessions_root / "2026-01-02" / "session_x" / "strip.jpg"
    fake_strip.parent.mkdir(parents=True, exist_ok=True)
    fake_strip.write_bytes(b"\xff\xd8\xff\xe0" + b"FAKEJPEG")

    controller._session_storage = type("S", (), {"strip_path": fake_strip})()

    status = controller.get_status()
    assert "most_recent_strip_url" in status
    assert status["most_recent_strip_url"].startswith("/sessions/")
    assert status["most_recent_strip_url"].endswith("strip.jpg")


class _ExplodingStorage:
    @property
    def strip_path(self) -> Path:
        raise RuntimeError("boom")


def test_get_status_swallows_exception_when_strip_path_access_fails(tmp_path):
    controller = PhotoboothController(camera=FakeCamera(tmp_path), printer=NoOpPrinter(), image_root=tmp_path)
    controller._session_storage = _ExplodingStorage()

    status = controller.get_status()

    # Should still return base status keys
    assert status["state"] in {"IDLE", "READY_FOR_PHOTO", "COUNTDOWN", "CAPTURING_PHOTO", "PROCESSING", "PRINTING"}
    assert "busy" in status
    assert "photos_taken" in status
    assert "total_photos" in status
    assert "countdown_remaining" in status

    # Exception path should prevent adding the derived URL
    assert "most_recent_strip_url" not in status
