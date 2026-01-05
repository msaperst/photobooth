# controller/cups_printer.py

from __future__ import annotations

import re
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

    def _get_device_uri(self) -> str:
        proc = subprocess.run(
            ["lpstat", "-v", self._printer_name],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise PrinterError(proc.stderr.strip())

        # Expected: device for PRINTER: ipp://host:631/ipp/print
        match = re.search(r":\s*(ipp[s]?://\S+)", proc.stdout)
        if not match:
            raise PrinterError("Could not determine printer device URI")

        return match.group(1)

    def preflight(self) -> None:
        # Cheap fast check: confirm lp exists.
        # We intentionally do NOT query printer state here (could block / be flaky).
        self._validate()

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

    def health_check(self) -> dict:
        """
        Actively probe printer via IPP.
        """
        try:
            uri = self._get_device_uri()
            proc = subprocess.run(
                [
                    "ipptool",
                    "-tv",
                    uri,
                    "get-printer-attributes.test",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except Exception:
            return {
                "reachable": False,
                "state": None,
                "reasons": [],
            }

        if proc.returncode != 0:
            return {
                "reachable": False,
                "state": None,
                "reasons": [],
            }

        state = None
        reasons: list[str] = []

        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("printer-state "):
                # example: printer-state (enum) = idle
                state = line.split("=")[-1].strip()
            elif line.startswith("printer-state-reasons "):
                # example:  printer-state-reasons (keyword) = media-empty,marker-supply-empty
                raw = line.split("=")[-1].strip()
                if raw != "none":
                    reasons = [r.strip() for r in raw.split(",")]

        return {
            "reachable": True,
            "state": state,
            "reasons": reasons,
        }
