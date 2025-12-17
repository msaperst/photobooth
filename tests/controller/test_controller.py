import threading
import time

from controller.camera import CameraError
from controller.controller import (
    PhotoboothController,
    Command,
    CommandType,
    ControllerState,
)
from controller.health import HealthLevel, HealthCode
from imaging.strip_errors import StripCreationError
from tests.fakes.fake_camera import FakeCamera
from tests.helpers import wait_for


def test_manual_photo_progression(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)
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

    # Final assertion (belt-and-suspenders)
    images = list(tmp_path.glob("*.jpg"))
    assert len(images) == 3


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


def test_controller_stop_calls_camera_stop_live_view(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    controller.start()
    assert controller._running is True
    assert camera.live_view_active is True

    controller.stop()

    assert controller._running is False
    assert camera.live_view_active is False


def test_controller_stop_ignores_camera_errors(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)
    controller.start()

    def boom():
        raise RuntimeError("camera exploded")

    monkeypatch.setattr(camera, "stop_live_view", boom)

    # Should NOT raise
    controller.stop()

    assert controller._running is False


def test_get_live_view_frame_returns_latest_frame(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    fake_frame = b"\xff\xd8\xff"
    with controller._live_view_lock:
        controller._latest_live_view_frame = fake_frame

    frame = controller.get_live_view_frame()

    assert frame == fake_frame


def test_run_loop_logs_unhandled_exceptions(tmp_path, capsys, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    def boom(_command):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(controller, "_handle_command", boom)

    controller.start()
    controller.enqueue(Command(CommandType.START_SESSION))

    # Wait until the print happens
    wait_for(lambda: "Controller error: kaboom" in capsys.readouterr().out, timeout=2.0)


def test_begin_photo_capture_returns_when_not_ready(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

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
    controller = PhotoboothController(camera, tmp_path)

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
    controller = PhotoboothController(camera, tmp_path)
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
    assert "photo 1 of 1" in health.message
    assert "Session was cancelled" in health.message


def test_start_live_view_worker_returns_if_already_running(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    # Pretend live view worker is already running
    controller._live_view_running = True

    thread_created = False

    def fake_thread(*args, **kwargs):
        nonlocal thread_created
        thread_created = True
        raise AssertionError("Thread should not be created")

    # Patch threading.Thread so we can detect misuse
    monkeypatch.setattr("controller.controller.threading.Thread", fake_thread)

    # Call the method under test
    controller._start_live_view_worker()

    # Assert no thread was started
    assert thread_created is False


def test_finish_session_worker_transitions_states(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

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


def test_start_sets_health_error_when_start_live_view_fails(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)

    def boom():
        raise RuntimeError("camera not connected")

    monkeypatch.setattr(camera, "start_live_view", boom)

    controller = PhotoboothController(camera, tmp_path)

    # Should not raise
    controller.start()

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.CAMERA_NOT_DETECTED


def test_capture_sets_health_error_when_restart_live_view_fails(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    controller.countdown_seconds = 0
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    def fail_start_live_view():
        raise RuntimeError("live view failed")

    monkeypatch.setattr(camera, "start_live_view", fail_start_live_view)

    controller.start()
    controller.enqueue(Command(CommandType.START_SESSION, payload={"image_count": 1}))
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    controller.enqueue(Command(CommandType.TAKE_PHOTO))

    # Capture still succeeds, but health should reflect error
    wait_for(lambda: controller.get_health().level == HealthLevel.ERROR)


def test_live_view_camera_error_sets_health(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    def fail_live_view():
        raise CameraError("device busy")

    monkeypatch.setattr(camera, "get_live_view_frame", fail_live_view)

    controller.start()

    # Live view worker runs in background
    wait_for(lambda: controller.get_health().level == HealthLevel.ERROR)


def test_capture_failure_mid_round_sets_contextual_message(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)
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


def test_capture_success_but_live_view_restart_fails_sets_health_message(
        tmp_path, monkeypatch
):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    # Make everything fast and deterministic
    controller.countdown_seconds = 0
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    # Capture succeeds (use FakeCamera default behavior)
    # Force live view restart to fail
    def fail_start_live_view():
        raise RuntimeError("live view restart failed")

    monkeypatch.setattr(camera, "start_live_view", fail_start_live_view)

    controller.start()
    controller.enqueue(
        Command(CommandType.START_SESSION, payload={"image_count": 1})
    )

    # Wait until ready
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    # Take the photo
    controller.enqueue(Command(CommandType.TAKE_PHOTO))

    # Photo should still be counted
    wait_for(lambda: controller.photos_taken == 1)

    # Health should reflect restart failure
    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.CAMERA_NOT_DETECTED
    assert (
            "live preview could not be restarted" in health.message
    )

    # Session should still complete and return to IDLE
    wait_for(lambda: controller.state == ControllerState.IDLE)


def test_set_camera_error_does_not_override_existing_error(tmp_path):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    controller._set_camera_error(
        HealthCode.CAMERA_NOT_DETECTED,
        "Primary error"
    )

    controller._set_camera_error(
        HealthCode.CAMERA_NOT_DETECTED,
        "Secondary error"
    )

    health = controller.get_health()

    assert health.level == HealthLevel.ERROR
    assert health.message == "Primary error"


def test_stop_live_view_exception_does_not_abort_capture(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)

    # Force stop_live_view to fail
    monkeypatch.setattr(camera, "stop_live_view", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

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
    controller = PhotoboothController(camera, tmp_path)

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
            payload={"image_count": 1},
        )
    )

    # Wait until ready
    from tests.helpers import wait_for
    wait_for(lambda: controller.state == ControllerState.READY_FOR_PHOTO)

    controller.enqueue(
        Command(CommandType.TAKE_PHOTO)
    )

    # Wait for processing to complete
    wait_for(lambda: controller.state == ControllerState.IDLE)

    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.STRIP_CREATION_FAILED
