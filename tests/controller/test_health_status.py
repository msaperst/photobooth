from controller.health import HealthStatus, HealthLevel, HealthCode


def test_ok_health_status():
    hs = HealthStatus.ok()
    assert hs.level == HealthLevel.OK
    assert hs.to_dict() == {"level": "OK"}


def test_error_health_status():
    hs = HealthStatus.error(
        code=HealthCode.CAMERA_NOT_DETECTED,
        message="Camera not detected",
        instructions=["Turn camera on"],
    )

    data = hs.to_dict()
    assert data["level"] == "ERROR"
    assert data["code"] == "CAMERA_NOT_DETECTED"
    assert "Turn camera on" in data["instructions"]
