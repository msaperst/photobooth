import threading

from controller.controller import PhotoboothController, ControllerState
from controller.health import HealthCode, HealthLevel, HealthSource
from tests.fakes.fake_camera import FakeCamera


def test_live_view_worker_start_is_idempotent(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)
    worker = controller._live_view_worker

    thread_created = 0

    class SpyThread:
        def __init__(self, *args, **kwargs):
            nonlocal thread_created
            thread_created += 1

        def start(self):
            pass

    # Patch threading.Thread used inside LiveViewWorker
    monkeypatch.setattr(threading, "Thread", SpyThread)

    # First call should create a thread
    worker.start()
    assert thread_created == 1

    # Second call should early-return and NOT create a thread
    worker.start()
    assert thread_created == 1


def test_live_view_does_not_clear_capture_error(tmp_path, monkeypatch):
    camera = FakeCamera(tmp_path)
    controller = PhotoboothController(camera, tmp_path)
    worker = controller._live_view_worker

    # Ensure worker loop condition passes
    worker._running = True
    with controller._state_lock:
        controller.state = ControllerState.IDLE

    # Simulate a capture-originated error that must NOT be cleared by live view
    controller._set_camera_error(
        HealthCode.CAMERA_NOT_DETECTED,
        "capture failed",
        source=HealthSource.CAPTURE,
    )

    # Make live view succeed once, then stop the worker
    call_count = {"n": 0}

    def one_frame_then_stop():
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Stop the loop after first iteration
            worker._running = False
            return b"frame"
        raise RuntimeError("should not be called")

    monkeypatch.setattr(camera, "get_live_view_frame", one_frame_then_stop)

    # Run synchronously (no threads)
    worker._run()

    # Health must NOT have been cleared
    health = controller.get_health()
    assert health.level == HealthLevel.ERROR
    assert health.code == HealthCode.CAMERA_NOT_DETECTED
    assert "capture failed" in health.message
