from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class SessionStorage:
    root: Path
    session_id: str
    session_date: date

    @property
    def session_dir(self) -> Path:
        return (
                self.root
                / self.session_date.isoformat()
                / f"session_{self.session_id}"
        )

    @property
    def photos_dir(self) -> Path:
        return self.session_dir / "photos"

    @property
    def strip_path(self) -> Path:
        return self.session_dir / "strip.jpg"

    def prepare(self) -> None:
        self.photos_dir.mkdir(parents=True, exist_ok=False)
