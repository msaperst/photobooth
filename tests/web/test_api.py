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
