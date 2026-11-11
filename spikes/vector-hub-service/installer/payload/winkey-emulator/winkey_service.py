"""Windows service host for the isolated GADX WinKey emulator.

The service deliberately owns only the dedicated virtual WinKey COM endpoint.
It never opens a physical keying port and does not modify vector.ini.
"""

from __future__ import annotations

import configparser
import subprocess
import sys
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil


SERVICE_NAME = "GADXWinKeyEmulator"
SERVICE_DISPLAY_NAME = "GADX WinKey Emulator"
SERVICE_DESCRIPTION = "GADX isolated N1MM WinKey-to-rigctld emulator"


def emulator_root() -> Path:
    return Path(__file__).resolve().parent


def install_root() -> Path:
    return emulator_root().parent


def config_path() -> Path:
    return emulator_root() / "winkey.ini"


def resolve_python_executable() -> Path:
    candidates = [
        install_root() / "runtime" / "python.exe",
        Path(sys.base_prefix) / "python.exe",
        Path(sys.prefix) / "python.exe",
        Path(sys.executable).with_name("python.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not locate the GADX private Python runtime")


def log_policy() -> tuple[int, int]:
    """Read optional bounded logging settings without importing the emulator."""
    defaults = (5, 5)
    try:
        parser = configparser.ConfigParser()
        if not parser.read(config_path(), encoding="utf-8-sig"):
            return defaults
        section = parser["logging"] if "logging" in parser else None
        if section is None:
            return defaults
        return (
            max(1, section.getint("max_mb", fallback=defaults[0])),
            max(0, section.getint("backups", fallback=defaults[1])),
        )
    except Exception:
        return defaults


def rotate_log(path: Path, max_bytes: int, backups: int) -> None:
    try:
        if not path.exists() or path.stat().st_size < max_bytes:
            return
    except OSError:
        return
    if backups <= 0:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return
    for index in range(backups, 0, -1):
        target = Path(f"{path}.{index}")
        source = path if index == 1 else Path(f"{path}.{index - 1}")
        try:
            if target.exists():
                target.unlink()
            if source.exists():
                source.replace(target)
        except OSError:
            pass


class GADXWinKeyEmulatorService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process: subprocess.Popen | None = None
        self.log_handle = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def _start_child(self) -> subprocess.Popen:
        emulator = emulator_root() / "winkey_emulator.py"
        config = config_path()
        if not emulator.exists() or not config.exists():
            raise FileNotFoundError("WinKey emulator program or winkey.ini is missing")

        logs = install_root() / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        max_mb, backups = log_policy()
        log_path = logs / "winkey-emulator.log"
        rotate_log(log_path, max_mb * 1024 * 1024, backups)
        self.log_handle = open(log_path, "a", encoding="utf-8", buffering=1)

        command = [str(resolve_python_executable()), str(emulator), "--config", str(config)]
        servicemanager.LogInfoMsg(f"Starting GADX WinKey Emulator: {' '.join(command)}")
        return subprocess.Popen(
            command,
            cwd=str(emulator_root()),
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _stop_child(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("GADX WinKey Emulator service starting")
        try:
            self.process = self._start_child()
            if win32event.WaitForSingleObject(self.stop_event, 1000) == win32event.WAIT_OBJECT_0:
                return
            if self.process.poll() is not None:
                raise RuntimeError(f"WinKey emulator exited during startup with {self.process.returncode}")

            while win32event.WaitForSingleObject(self.stop_event, 500) != win32event.WAIT_OBJECT_0:
                if self.process.poll() is not None:
                    raise RuntimeError(f"WinKey emulator exited unexpectedly with {self.process.returncode}")
        finally:
            self._stop_child()
            if self.log_handle is not None:
                self.log_handle.close()
                self.log_handle = None
            servicemanager.LogInfoMsg("GADX WinKey Emulator service stopped")


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(GADXWinKeyEmulatorService)
