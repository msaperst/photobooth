from pathlib import Path

import pytest
from flask import json

from tests.controller.test_controller import NoOpPrinter
from tests.fakes.fake_camera import FakeCamera
from web.app import create_app


@pytest.fixture
def client(tmp_path):
    camera = FakeCamera(tmp_path)
    logo_path = tmp_path / "logo.png"
    # Minimal valid PNG header so PIL can open if needed later
    logo_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    app = create_app(camera=camera, printer=NoOpPrinter(), image_root=tmp_path, album_code="TESTALBUM", logo_path=logo_path)
    app.config["TESTING"] = True
    return app.test_client()


def test_create_app_requires_env_when_no_overrides(monkeypatch):
    monkeypatch.delenv("PHOTOBOOTH_IMAGE_ROOT", raising=False)
    monkeypatch.delenv("PHOTOBOOTH_ALBUM_CODE", raising=False)
    monkeypatch.delenv("PHOTOBOOTH_LOGO_PATH", raising=False)
    app = create_app(camera=FakeCamera(Path("/tmp")))
    app.config["TESTING"] = True
    client = app.test_client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["level"] == "ERROR"
    assert data["code"] == "CONFIG_INVALID"
    assert "PHOTOBOOTH_IMAGE_ROOT" in "\n".join(data.get("instructions") or [])


def test_operations_are_blocked_when_unhealthy(monkeypatch, tmp_path):
    monkeypatch.delenv("PHOTOBOOTH_IMAGE_ROOT", raising=False)
    monkeypatch.delenv("PHOTOBOOTH_ALBUM_CODE", raising=False)
    monkeypatch.delenv("PHOTOBOOTH_LOGO_PATH", raising=False)
    app = create_app(camera=FakeCamera(tmp_path))
    app.config["TESTING"] = True
    client = app.test_client()

    r = client.post("/start-session", data=json.dumps({"print_count": 1}), content_type="application/json")
    assert r.status_code == 503
    payload = r.get_json()
    assert payload["ok"] is False
    assert payload["error"] == "unhealthy"
    assert payload["health"]["code"] == "CONFIG_INVALID"


def test_status_endpoint(client):
    response = client.get("/status")
    assert response.status_code == 200
    data = response.get_json()
    assert "state" in data
    assert "busy" in data


def test_start_session_ok(client):
    response = client.post(
        "/start-session",
        data=json.dumps({"print_count": 1}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_start_session_rejected_when_busy(client, monkeypatch):
    monkeypatch.setattr(
        client.application.controller,
        "get_status",
        lambda: {"state": "CAPTURING", "busy": True},
    )

    response = client.post("/start-session")
    assert response.status_code == 409


def test_take_photo_ok_when_ready(client, monkeypatch):
    # Pretend controller is ready for photo
    monkeypatch.setattr(
        client.application.controller,
        "get_status",
        lambda: {
            "state": "READY_FOR_PHOTO",
            "busy": True,
            "photos_taken": 0,
            "total_photos": 3,
            "countdown_remaining": 0,
        },
    )

    called = {}

    def fake_enqueue(command):
        called["command"] = command

    monkeypatch.setattr(client.application.controller, "enqueue", fake_enqueue)

    response = client.post("/take-photo")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert "command" in called


def test_index_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.content_type.startswith("text/html")


def test_health_endpoint_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json == {"level": "OK"}


def test_healthz_endpoint_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json == {"level": "OK"}


def test_sessions_route_serves_file(tmp_path, monkeypatch):
    """
    Verify that /sessions/<path> serves files from the sessions directory.
    """

    # Arrange: create fake sessions directory + file
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()

    test_file = sessions_root / "test.txt"
    test_file.write_text("hello photobooth")

    # Patch the SESSIONS_ROOT used by the app
    logo_path = tmp_path / "logo.png"
    logo_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    app = create_app(camera=None, image_root=tmp_path, album_code="TESTALBUM", logo_path=logo_path)
    app.config["SESSIONS_ROOT"] = sessions_root
    client = app.test_client()

    # Act
    response = client.get("/sessions/test.txt")

    # Assert
    assert response.status_code == 200
    assert response.data == b"hello photobooth"


def test_create_app_uses_env_vars_when_overrides_are_none(monkeypatch, tmp_path):
    """Cover the env-var else branches in create_app for root/album/logo."""
    # Arrange env vars + a real logo file.
    env_root = tmp_path / "data"
    env_root.mkdir()
    logo_file = tmp_path / "event_logo.png"
    logo_file.write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setenv("PHOTOBOOTH_IMAGE_ROOT", str(env_root))
    monkeypatch.setenv("PHOTOBOOTH_ALBUM_CODE", "ALBUM123")
    monkeypatch.setenv("PHOTOBOOTH_LOGO_PATH", str(logo_file))

    camera = FakeCamera(tmp_path)

    # Act: do not pass explicit overrides so create_app consumes env.
    app = create_app(camera=camera)
    app.config["TESTING"] = True
    client = app.test_client()

    # Assert: service starts healthy and uses env values.
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"level": "OK"}

    assert app.controller.image_root == env_root
    assert app.controller.event_album_code == "ALBUM123"
    assert app.controller.strip_logo_path == logo_file


def test_create_app_reports_invalid_logo_path(monkeypatch, tmp_path):
    """Cover the logo_path exists/is_file validation branch."""
    env_root = tmp_path / "data"
    env_root.mkdir()
    bad_logo = tmp_path / "does_not_exist.png"

    monkeypatch.setenv("PHOTOBOOTH_IMAGE_ROOT", str(env_root))
    monkeypatch.setenv("PHOTOBOOTH_ALBUM_CODE", "ALBUM123")
    monkeypatch.setenv("PHOTOBOOTH_LOGO_PATH", str(bad_logo))

    app = create_app(camera=FakeCamera(tmp_path))
    app.config["TESTING"] = True
    client = app.test_client()

    resp = client.get("/healthz")
    data = resp.get_json()
    assert data["level"] == "ERROR"
    assert data["code"] == "CONFIG_INVALID"
    instructions = "\n".join(data.get("instructions") or [])
    assert "PHOTOBOOTH_LOGO_PATH is invalid" in instructions
    assert str(bad_logo) in instructions


def test_take_photo_blocked_when_unhealthy(monkeypatch, tmp_path):
    """When controller health is not OK, /take-photo should return 503 with health payload."""
    monkeypatch.delenv("PHOTOBOOTH_IMAGE_ROOT", raising=False)
    monkeypatch.delenv("PHOTOBOOTH_ALBUM_CODE", raising=False)
    monkeypatch.delenv("PHOTOBOOTH_LOGO_PATH", raising=False)

    app = create_app(camera=FakeCamera(tmp_path))
    app.config["TESTING"] = True
    client = app.test_client()

    r = client.post("/take-photo")
    assert r.status_code == 503
    payload = r.get_json()
    assert payload["ok"] is False
    assert payload["error"] == "unhealthy"
    assert payload["health"]["code"] == "CONFIG_INVALID"


def test_status_includes_most_recent_strip_url_when_strip_exists(client, tmp_path):
    # Arrange: create a fake "most recent strip" on disk in the expected sessions dir
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)

    # This mirrors your runtime structure; use any nested path because the controller
    # should compute a /sessions/<relative> URL.
    fake_strip = sessions_root / "2026-01-02" / "session_test" / "strip.jpg"
    fake_strip.parent.mkdir(parents=True, exist_ok=True)
    fake_strip.write_bytes(b"\xff\xd8\xff\xe0" + b"FAKEJPEG")  # minimal JPEG-like bytes

    # Your implementation determines "most recent strip" based on controller storage.
    # If your app uses controller._session_storage.strip_path, ensure that points to fake_strip.
    # If you implemented a different mechanism, adjust this setup accordingly.
    app = client.application
    app.controller._session_storage = type("S", (), {"strip_path": fake_strip})()

    # Act
    r = client.get("/status")
    assert r.status_code == 200
    payload = r.get_json()

    # Assert
    assert "most_recent_strip_url" in payload
    assert payload["most_recent_strip_url"].startswith("/sessions/")
    assert payload["most_recent_strip_url"].endswith("strip.jpg")


def test_download_most_recent_strip_returns_attachment(client, tmp_path):
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    fake_strip = sessions_root / "x" / "strip.jpg"
    fake_strip.parent.mkdir(parents=True, exist_ok=True)
    fake_strip.write_bytes(b"\xff\xd8\xff\xe0" + b"FAKEJPEG")

    app = client.application
    app.controller._session_storage = type("S", (), {"strip_path": fake_strip})()

    r = client.get("/download/most-recent-strip")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("image/jpeg")
    cd = r.headers.get("Content-Disposition", "")
    assert "attachment" in cd
    assert "photo_strip.jpg" in cd
    assert r.data.startswith(b"\xff\xd8")


def test_download_most_recent_strip_404_when_missing(client):
    app = client.application
    app.controller._session_storage = None

    r = client.get("/download/most-recent-strip")
    assert r.status_code == 404
    payload = r.get_json()
    assert payload["ok"] is False
    assert payload["error"] == "no_strip"


def test_qr_most_recent_strip_is_png(client, tmp_path):
    # QR does not require a real strip file; it should always render a QR png.
    r = client.get("/qr/most-recent-strip.png")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("image/png")
    # PNG signature
    assert r.data.startswith(b"\x89PNG\r\n\x1a\n")


def test_download_most_recent_strip_404_when_storage_present_but_file_missing(client, tmp_path):
    # Create a strip path that does NOT exist
    missing = tmp_path / "sessions" / "whatever" / "strip.jpg"
    assert not missing.exists()

    app = client.application
    app.controller._session_storage = type("S", (), {"strip_path": missing})()

    r = client.get("/download/most-recent-strip")
    assert r.status_code == 404
    payload = r.get_json()
    assert payload == {"ok": False, "error": "no_strip"}
