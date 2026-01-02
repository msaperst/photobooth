# tests/controller/test_cups_printer.py

import pytest

from controller.cups_printer import CupsPrinter
from controller.printer_base import PrinterError


def test_cups_printer_raises_if_lp_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _p: None)

    printer = CupsPrinter(printer_name="DUMMY")
    with pytest.raises(PrinterError, match="not found in PATH"):
        printer.print_file(tmp_path / "print.jpg")


def test_cups_printer_raises_if_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _p: "/usr/bin/lp")

    printer = CupsPrinter(printer_name="DUMMY")
    with pytest.raises(PrinterError, match="does not exist"):
        printer.print_file(tmp_path / "print.jpg")


def test_cups_printer_submits_expected_commands(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _p: "/usr/bin/lp")

    # Create a dummy file
    f = tmp_path / "print.jpg"
    f.write_bytes(b"fake")

    calls = []

    class FakeProc:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return FakeProc(returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)

    printer = CupsPrinter(printer_name="SELPHY", lp_path="lp")
    printer.print_file(f, copies=3, job_name="Photobooth Print")

    assert len(calls) == 3
    # Assert printer name appears and file path is last arg
    for cmd in calls:
        assert cmd[0] == "lp"
        assert "-d" in cmd and "SELPHY" in cmd
        assert str(f) == cmd[-1]


def test_cups_printer_raises_on_lp_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _p: "/usr/bin/lp")

    f = tmp_path / "print.jpg"
    f.write_bytes(b"fake")

    class FakeProc:
        def __init__(self):
            self.returncode = 1
            self.stdout = ""
            self.stderr = "boom"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())

    printer = CupsPrinter(printer_name="SELPHY")
    with pytest.raises(PrinterError, match="lp failed"):
        printer.print_file(f)


def test_cups_printer_raises_if_copies_less_than_one(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _p: "/usr/bin/lp")

    f = tmp_path / "print.jpg"
    f.write_bytes(b"fake")

    printer = CupsPrinter(printer_name="SELPHY")
    with pytest.raises(PrinterError, match=r"copies must be >= 1"):
        printer.print_file(f, copies=0)


def test_cups_printer_raises_if_path_is_not_a_file(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _p: "/usr/bin/lp")

    d = tmp_path / "not_a_file"
    d.mkdir()

    printer = CupsPrinter(printer_name="SELPHY")
    with pytest.raises(PrinterError, match=r"Print path is not a file"):
        printer.print_file(d)


def test_cups_printer_preflight_raises_if_lp_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _p: None)

    printer = CupsPrinter(printer_name="DUMMY")
    with pytest.raises(PrinterError, match="not found in PATH"):
        printer.preflight()


def test_cups_printer_preflight_ok_when_lp_present(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _p: "/usr/bin/lp")

    printer = CupsPrinter(printer_name="DUMMY")
    printer.preflight()  # should not raise
