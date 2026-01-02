# controller/cups_printer.py

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Sequence, Optional

from controller.printer_base import Printer, PrinterError


class CupsPrinter(Printer):
    """
    CUPS-backed printer using the `lp` command.

    Design constraints (intentional):
    - Fire-and-forget submission only (no job tracking yet).
    - Prints an existing file (print.jpg). No image processing.
    - Minimal options; printer/queue configuration happens in CUPS.
    """

    def __init__(
            self,
            printer_name: str,
            lp_path: str = "lp",
            extra_args: Optional[Sequence[str]] = None,
    ) -> None:
        self._printer_name = printer_name
        self._lp_path = lp_path
        self._extra_args = list(extra_args or [])

    def _validate(self) -> None:
        if shutil.which(self._lp_path) is None:
            raise PrinterError(f"CUPS not available: '{self._lp_path}' not found in PATH")

    def print_file(self, file_path: Path, *, copies: int = 1, job_name: str | None = None) -> None:
        self._validate()

        if copies < 1:
            raise PrinterError(f"copies must be >= 1 (got {copies})")

        if not file_path.exists():
            raise PrinterError(f"Print file does not exist: {file_path}")
        if not file_path.is_file():
            raise PrinterError(f"Print path is not a file: {file_path}")

        # Submit as N independent jobs. This matches "start print job, let next guests start"
        # better than relying on printer-side copy semantics.
        for i in range(copies):
            title = job_name or file_path.name
            if copies > 1:
                title = f"{title} ({i + 1}/{copies})"

            cmd = [
                self._lp_path,
                "-d", self._printer_name,
                "-t", title,
                *self._extra_args,
                str(file_path),
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                out = (proc.stdout or "") + (proc.stderr or "")
                raise PrinterError(f"lp failed (rc={proc.returncode}): {out.strip()}")
