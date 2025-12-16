import json

import pytest

from web.app import app, controller


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


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
        controller,
        "get_status",
        lambda: {"state": "CAPTURING", "busy": True},
    )

    response = client.post("/start-session")
    assert response.status_code == 409


def test_take_photo_ok_when_ready(client, monkeypatch):
    # Pretend controller is ready for photo
    monkeypatch.setattr(
        controller,
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

    monkeypatch.setattr(controller, "enqueue", fake_enqueue)

    response = client.post("/take-photo")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert "command" in called


def test_take_photo_rejected_when_not_ready(client, monkeypatch):
    monkeypatch.setattr(
        controller,
        "get_status",
        lambda: {
            "state": "COUNTDOWN",
            "busy": True,
            "photos_taken": 1,
            "total_photos": 3,
            "countdown_remaining": 2,
        },
    )

    response = client.post("/take-photo")
    assert response.status_code == 409


def test_live_view_returns_204_when_no_frame(client, monkeypatch):
    # None -> 204
    monkeypatch.setattr(controller, "get_live_view_frame", lambda: None)

    resp = client.get("/live-view")
    assert resp.status_code == 204
    assert resp.data == b""


def test_live_view_returns_204_when_empty_bytes(client, monkeypatch):
    # b"" -> 204 (since `if not frame:`)
    monkeypatch.setattr(controller, "get_live_view_frame", lambda: b"")

    resp = client.get("/live-view")
    assert resp.status_code == 204
    assert resp.data == b""


def test_live_view_returns_jpeg_when_frame_exists(client, monkeypatch):
    fake_frame = b"\xff\xd8\xff\xe0" + b"fakejpegdata" + b"\xff\xd9"
    monkeypatch.setattr(controller, "get_live_view_frame", lambda: fake_frame)

    resp = client.get("/live-view")
    assert resp.status_code == 200
    assert resp.mimetype == "image/jpeg"
    assert resp.data == fake_frame


def test_index_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.content_type.startswith("text/html")


def test_health_endpoint_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json == {"level": "OK"}
