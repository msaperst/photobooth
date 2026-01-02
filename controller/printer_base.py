# controller/printer_base.py

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class PrinterError(RuntimeError):
    """Raised when the printer cannot accept or process a print request."""


class Printer(ABC):
    """
    Abstract printer interface.

    The controller owns printing behavior and error handling. Concrete implementations
    talk to real hardware/spoolers (CUPS, USB printer SDK, etc).
    """

    @abstractmethod
    def print_file(self, file_path: Path, *, copies: int = 1, job_name: str | None = None) -> None:
        """
        Submit `file_path` to the printer.

        - `copies` is the number of identical print jobs desired.
        - Implementations should raise PrinterError on failure.
        """
        raise NotImplementedError
