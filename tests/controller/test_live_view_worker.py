import threading

from controller.controller import PhotoboothController
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
