import pytest
from flask import json
from pathlib import Path

from tests.fakes.fake_camera import FakeCamera
from web.app import create_app


@pytest.fixture
def client(tmp_path):
    camera = FakeCamera(tmp_path)
    logo_path = tmp_path / "logo.png"
    # Minimal valid PNG header so PIL can open if needed later
    logo_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    app = create_app(camera=camera, image_root=tmp_path, album_code="TESTALBUM", logo_path=logo_path)
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
