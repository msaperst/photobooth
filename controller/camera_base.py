from abc import ABC, abstractmethod
from pathlib import Path


class CameraError(Exception):
    pass


class Camera(ABC):
    """
    Abstract camera interface.

    All camera implementations (real or fake) must implement this contract.
    """

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the camera is connected and usable."""
        pass

    # optional capabilities
    def start_live_view(self) -> None:
        raise NotImplementedError

    def stop_live_view(self) -> None:
        raise NotImplementedError

    def get_live_view_frame(self) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def capture(self, output_dir: Path) -> Path:
        """Capture a single photo and return the saved file path."""
        pass
