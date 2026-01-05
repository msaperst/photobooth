from abc import ABC, abstractmethod
from pathlib import Path

VIEW_IS_NOT_SUPPORTED = "Live view is not supported"


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
        """Live view is intentionally not supported by Photobooth.

        Implementations may override this for experimentation, but the core
        system does not rely on live view for booth operation.
        """
        raise NotImplementedError(VIEW_IS_NOT_SUPPORTED)

    def stop_live_view(self) -> None:
        """Stop live view.

        Photobooth does not start live view, so this is normally a no-op.
        """
        raise NotImplementedError(VIEW_IS_NOT_SUPPORTED)

    def get_live_view_frame(self) -> bytes:
        """Return a single live view frame.

        Photobooth does not use live view. This exists only as an optional
        capability for future experimentation.
        """
        raise NotImplementedError(VIEW_IS_NOT_SUPPORTED)

    @abstractmethod
    def capture(self, output_dir: Path) -> Path:
        """Capture a single photo and return the saved file path."""
        pass
