from datetime import date

from controller.session_storage import SessionStorage


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
