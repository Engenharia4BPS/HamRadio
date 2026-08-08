from __future__ import annotations

import configparser
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import serial
import win32event
import win32service
import win32serviceutil
import servicemanager


SERVICE_NAME = "GADXVectorBridge"
SERVICE_DISPLAY_NAME = "GADX Vector Bridge"
SERVICE_DESCRIPTION = "GADX Vector TS-2000 CAT/PTT/CW bridge"


def program_data_dir() -> Path:
    base = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    return base / "GADXVector"


def read_bridge_config(path: Path) -> configparser.SectionProxy | None:
    cfg = configparser.ConfigParser()
    if not path.exists():
        return None
    cfg.read(path, encoding="utf-8")
    return cfg["bridge"] if "bridge" in cfg else None


def force_safe_state(config_path: Path) -> None:
    """Best-effort safety shutdown independent from the child process."""
    section = read_bridge_config(config_path)
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
        self.root = program_data_dir()
        self.config_path = self.root / "bridge.ini"
        self.log_dir = self.root / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def _start_child(self) -> subprocess.Popen:
        app_dir = Path(__file__).resolve().parent.parent
        bridge_py = app_dir / "rigctld_bridge.py"
        log_path = self.log_dir / "bridge-service.log"
        log_handle = open(log_path, "a", encoding="utf-8", buffering=1)
        cmd = [sys.executable, str(bridge_py), "--config", str(self.config_path)]
        servicemanager.LogInfoMsg(f"Starting GADX Vector bridge: {' '.join(cmd)}")
        return subprocess.Popen(
            cmd,
            cwd=str(app_dir),
            stdout=log_handle,
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
            force_safe_state(self.config_path)
            servicemanager.LogInfoMsg("GADX Vector Bridge service stopped")


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(GADXVectorBridgeService)
