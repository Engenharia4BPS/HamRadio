from __future__ import annotations

import configparser
import socket
import subprocess
import sys
from pathlib import Path

import serial
import win32event
import win32service
import win32serviceutil
import servicemanager


SERVICE_NAME = "GADXVectorBridge"
SERVICE_DISPLAY_NAME = "GADX Vector Bridge"
SERVICE_DESCRIPTION = "GADX Vector TS-2000 CAT/PTT/CW bridge"
DEFAULT_ROOT = Path(r"C:\Ham\GADX-Vector")
DEFAULT_LOG_MAX_MB = 5
DEFAULT_LOG_BACKUPS = 5


def install_root() -> Path:
    # The service lives under <root>\service. Deriving the root from __file__
    # keeps the installation relocatable if the user changes C:\Ham\GADX-Vector.
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return install_root() / "config" / "bridge.ini"


def log_dir() -> Path:
    return install_root() / "logs"


def read_bridge_config(path: Path) -> configparser.SectionProxy | None:
    cfg = configparser.ConfigParser()
    if not path.exists():
        return None
    cfg.read(path, encoding="utf-8-sig")
    return cfg["bridge"] if "bridge" in cfg else None


def resolve_python_executable() -> Path:
    """Return the private Vector python.exe used for child applications."""
    root = install_root()
    candidates = [
        root / "runtime" / "python.exe",
        Path(sys.base_prefix) / "python.exe",
        Path(sys.prefix) / "python.exe",
        Path(sys.executable).with_name("python.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate python.exe for GADX Vector child process; "
        f"sys.executable={sys.executable!r}"
    )


def rotate_log(path: Path, max_bytes: int, backups: int) -> None:
    """Rotate log before opening it, bounding disk use without extra deps."""
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

    oldest = Path(f"{path}.{backups}")
    try:
        oldest.unlink(missing_ok=True)
    except OSError:
        pass

    for index in range(backups - 1, 0, -1):
        src = Path(f"{path}.{index}")
        dst = Path(f"{path}.{index + 1}")
        try:
            if src.exists():
                src.replace(dst)
        except OSError:
            pass

    try:
        path.replace(Path(f"{path}.1"))
    except OSError:
        pass


def force_safe_state(path: Path) -> None:
    """Best-effort safety shutdown independent from the child process."""
    section = read_bridge_config(path)
    if section is None:
        return

    radio_keying_port = section.get("radio_keying_port", "").strip()
    radio_keying_baud = section.getint("radio_keying_baud", fallback=9600)
    if radio_keying_port:
        try:
            with serial.Serial(radio_keying_port, radio_keying_baud, timeout=0) as port:
                port.rts = False
                port.dtr = False
        except Exception:
            pass

    host = section.get("rig_host", "127.0.0.1")
    port = section.getint("rig_port", fallback=4532)
    try:
        with socket.create_connection((host, port), timeout=1.0) as sock:
            sock.sendall(b"+\\set_ptt 0\n")
            sock.settimeout(1.0)
            while True:
                data = sock.recv(1024)
                if not data or b"RPRT " in data:
                    break
    except Exception:
        pass


class GADXVectorBridgeService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process: subprocess.Popen | None = None
        self.root = install_root()
        self.config_path = config_path()
        self.log_dir = log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_handle = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def _start_child(self) -> subprocess.Popen:
        bridge_py = self.root / "app" / "rigctld_bridge.py"
        log_path = self.log_dir / "bridge-service.log"
        python_exe = resolve_python_executable()

        section = read_bridge_config(self.config_path)
        max_mb = section.getint("log_max_mb", fallback=DEFAULT_LOG_MAX_MB) if section else DEFAULT_LOG_MAX_MB
        backups = section.getint("log_backups", fallback=DEFAULT_LOG_BACKUPS) if section else DEFAULT_LOG_BACKUPS
        rotate_log(log_path, max(1, max_mb) * 1024 * 1024, max(0, backups))

        cmd = [str(python_exe), str(bridge_py), "--config", str(self.config_path)]
        servicemanager.LogInfoMsg(f"Starting GADX Vector bridge: {' '.join(cmd)}")
        self.log_handle = open(log_path, "a", encoding="utf-8", buffering=1)
        return subprocess.Popen(
            cmd,
            cwd=str(self.root / "app"),
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("GADX Vector Bridge service starting")
        try:
            force_safe_state(self.config_path)
            self.process = self._start_child()

            while True:
                wait = win32event.WaitForSingleObject(self.stop_event, 500)
                if wait == win32event.WAIT_OBJECT_0:
                    break
                if self.process.poll() is not None:
                    code = self.process.returncode
                    servicemanager.LogErrorMsg(f"Vector bridge exited unexpectedly with code {code}")
                    raise RuntimeError(f"bridge exited with code {code}")
        finally:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            if self.log_handle is not None:
                try:
                    self.log_handle.close()
                except OSError:
                    pass
            force_safe_state(self.config_path)
            servicemanager.LogInfoMsg("GADX Vector Bridge service stopped")


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(GADXVectorBridgeService)
