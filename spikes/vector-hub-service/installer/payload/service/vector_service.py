from __future__ import annotations

import configparser
import socket
import subprocess
import sys
from pathlib import Path

import serial
import servicemanager
import win32event
import win32service
import win32serviceutil

SERVICE_NAME = "GADXVectorHub"
SERVICE_DISPLAY_NAME = "GADX Vector Hub"
SERVICE_DESCRIPTION = "GADX Vector multi-client CAT/PTT/CW hub"
DEFAULT_LOG_MAX_MB = 5
DEFAULT_LOG_BACKUPS = 5

def install_root() -> Path:
    return Path(__file__).resolve().parent.parent

def config_path() -> Path:
    return install_root() / "config" / "vector.ini"

def log_dir() -> Path:
    return install_root() / "logs"

def read_config(path: Path) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if not path.exists(): raise FileNotFoundError(f"Vector configuration not found: {path}")
    loaded = cfg.read(path, encoding="utf-8-sig")
    if not loaded: raise RuntimeError(f"Could not read Vector configuration: {path}")
    return cfg

def resolve_python_executable() -> Path:
    root = install_root()
    candidates = [root / "runtime" / "python.exe", Path(sys.base_prefix) / "python.exe", Path(sys.prefix) / "python.exe", Path(sys.executable).with_name("python.exe")]
    for candidate in candidates:
        if candidate.exists(): return candidate
    raise FileNotFoundError(f"Could not locate python.exe for GADX Vector Hub; sys.executable={sys.executable!r}")

def rotate_log(path: Path, max_bytes: int, backups: int) -> None:
    try:
        if not path.exists() or path.stat().st_size < max_bytes: return
    except OSError: return
    if backups <= 0:
        try:path.unlink(missing_ok=True)
        except OSError:pass
        return
    oldest = Path(f"{path}.{backups}")
    try:oldest.unlink(missing_ok=True)
    except OSError:pass
    for index in range(backups - 1, 0, -1):
        src = Path(f"{path}.{index}"); dst = Path(f"{path}.{index + 1}")
        try:
            if src.exists(): src.replace(dst)
        except OSError:pass
    try:path.replace(Path(f"{path}.1"))
    except OSError:pass

def _rigctld_ptt_off(host: str, port: int) -> None:
    try:
        with socket.create_connection((host, port), timeout=1.0) as sock:
            sock.sendall(b"+\\set_ptt 0\n"); sock.settimeout(1.0); received=b""
            while b"RPRT " not in received:
                chunk=sock.recv(1024)
                if not chunk: break
                received += chunk
    except Exception: pass

def force_safe_state(path: Path) -> None:
    try: cfg=read_config(path)
    except Exception:return
    if "radio_keying" in cfg:
        section=cfg["radio_keying"]; serial_port=section.get("port","").strip(); baud=section.getint("baud",fallback=19200)
        if serial_port:
            try:
                with serial.Serial(serial_port,baud,timeout=0) as port: port.rts=False; port.dtr=False
            except Exception:pass
    if "rig" in cfg:
        section=cfg["rig"]; _rigctld_ptt_off(section.get("host","127.0.0.1"),section.getint("port",fallback=4532))

class GADXVectorHubService(win32serviceutil.ServiceFramework):
    _svc_name_=SERVICE_NAME; _svc_display_name_=SERVICE_DISPLAY_NAME; _svc_description_=SERVICE_DESCRIPTION
    def __init__(self,args):
        super().__init__(args); self.stop_event=win32event.CreateEvent(None,0,0,None); self.process=None; self.root=install_root(); self.config=config_path(); self.logs=log_dir(); self.logs.mkdir(parents=True,exist_ok=True); self.log_handle=None
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING); win32event.SetEvent(self.stop_event)
    def _logging_policy(self):
        try:
            cfg=read_config(self.config); section=cfg["logging"] if "logging" in cfg else None
            if section is None:return DEFAULT_LOG_MAX_MB,DEFAULT_LOG_BACKUPS
            return max(1,section.getint("max_mb",fallback=DEFAULT_LOG_MAX_MB)),max(0,section.getint("backups",fallback=DEFAULT_LOG_BACKUPS))
        except Exception:return DEFAULT_LOG_MAX_MB,DEFAULT_LOG_BACKUPS
    def _start_child(self):
        hub_py=self.root/"app"/"vector_hub.py"
        if not hub_py.exists():raise FileNotFoundError(f"Vector Hub runtime not found: {hub_py}")
        python_exe=resolve_python_executable(); max_mb,backups=self._logging_policy(); log_path=self.logs/"vector-hub.log"; rotate_log(log_path,max_mb*1024*1024,backups)
        cmd=[str(python_exe),str(hub_py),"--config",str(self.config)]
        servicemanager.LogInfoMsg(f"Starting GADX Vector Hub: {' '.join(cmd)}")
        self.log_handle=open(log_path,"a",encoding="utf-8",buffering=1)
        return subprocess.Popen(cmd,cwd=str(self.root/"app"),stdout=self.log_handle,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    def _stop_child(self):
        if self.process is None or self.process.poll() is not None:return
        self.process.terminate()
        try:self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=2)
    def SvcDoRun(self):
        servicemanager.LogInfoMsg("GADX Vector Hub service starting")
        try:
            force_safe_state(self.config); self.process=self._start_child(); wait=win32event.WaitForSingleObject(self.stop_event,1000)
            if wait==win32event.WAIT_OBJECT_0:return
            if self.process.poll() is not None:raise RuntimeError(f"Vector Hub exited during startup with code {self.process.returncode}")
            servicemanager.LogInfoMsg("GADX Vector Hub runtime is running")
            while True:
                wait=win32event.WaitForSingleObject(self.stop_event,500)
                if wait==win32event.WAIT_OBJECT_0:break
                if self.process.poll() is not None:
                    code=self.process.returncode; servicemanager.LogErrorMsg(f"Vector Hub exited unexpectedly with code {code}"); raise RuntimeError(f"Vector Hub exited unexpectedly with code {code}")
        finally:
            try:self._stop_child()
            finally:
                if self.log_handle is not None:
                    try:self.log_handle.close()
                    except OSError:pass
                    self.log_handle=None
                force_safe_state(self.config); servicemanager.LogInfoMsg("GADX Vector Hub service stopped")

if __name__=="__main__":
    win32serviceutil.HandleCommandLine(GADXVectorHubService)
