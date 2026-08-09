from __future__ import annotations

import argparse
import configparser
import logging
import queue
import socket
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import serial

from ts2000 import MODE_NAMES, TS2000Emulator


LOG = logging.getLogger("gadx.vector.multi-bridge")

HAMLIB_TO_TS2000 = {
    "LSB": "LSB",
    "USB": "USB",
    "CW": "CW",
    "CWR": "CW-R",
    "FM": "FM",
    "WFM": "FM",
    "AM": "AM",
    "RTTY": "FSK",
    "RTTYR": "FSK-R",
    "PKTLSB": "LSB",
    "PKTUSB": "USB",
    "PKTFM": "FM",
}

SERIAL_LINES = {"DTR", "RTS", "NONE"}
KEYING_POLL_SECONDS = 0.0005


@dataclass
class RigSnapshot:
    frequency_hz: int
    mode: str
    passband_hz: int


@dataclass
class KeyingClientConfig:
    name: str
    port: str
    ptt_input: str
    cw_input: str


@dataclass
class BridgeConfig:
    cat_ports: List[str]
    cat_baud: int
    keying_clients: List[KeyingClientConfig]
    radio_keying_port: Optional[str]
    radio_keying_baud: int
    radio_ptt_line: str
    radio_cw_line: str
    rig_host: str
    rig_port: int
    rig_poll_ms: int
    allow_write: bool
    allow_ptt: bool
    allow_cw: bool
    log_level: str


class RigctldClient:
    """Thread-safe rigctld client shared by all CAT workers."""

    def __init__(self, host: str, port: int, timeout: float = 2.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.file = None
        self.lock = threading.RLock()

    def connect(self) -> None:
        with self.lock:
            self._connect_locked()

    def _connect_locked(self) -> None:
        self._close_locked()
        LOG.info("Connecting to rigctld at %s:%d", self.host, self.port)
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        self.file = self.sock.makefile("rwb", buffering=0)
        LOG.info("Connected to rigctld")

    def close(self) -> None:
        with self.lock:
            self._close_locked()

    def _close_locked(self) -> None:
        if self.file is not None:
            try:
                self.file.close()
            except OSError:
                pass
            self.file = None
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def command(self, long_command: str, *args: object) -> Dict[str, str]:
        with self.lock:
            if self.sock is None or self.file is None:
                self._connect_locked()
            assert self.file is not None
            payload = "+\\" + long_command
            if args:
                payload += " " + " ".join(str(arg) for arg in args)
            payload += "\n"
            LOG.debug("RIGCTL TX: %s", payload.rstrip())
            try:
                self.file.write(payload.encode("ascii"))
                records: List[str] = []
                while True:
                    raw = self.file.readline()
                    if not raw:
                        raise ConnectionError("rigctld closed the connection")
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    LOG.debug("RIGCTL RX: %s", line)
                    records.append(line)
                    if line.startswith("RPRT "):
                        code = int(line.split(maxsplit=1)[1])
                        if code != 0:
                            raise RuntimeError(f"rigctld {long_command} failed with RPRT {code}")
                        break
            except (OSError, ConnectionError):
                self._close_locked()
                raise
            values: Dict[str, str] = {}
            for line in records:
                if ": " in line:
                    key, value = line.split(": ", 1)
                    values[key.strip()] = value.strip()
            return values

    def get_snapshot(self) -> RigSnapshot:
        f = self.command("get_freq")
        m = self.command("get_mode")
        return RigSnapshot(
            int(float(f["Frequency"])),
            m["Mode"].upper(),
            int(float(m.get("Passband", "0"))),
        )

    def set_frequency(self, hz: int) -> None:
        self.command("set_freq", hz)

    def set_mode(self, mode: str, passband_hz: int = 0) -> None:
        self.command("set_mode", mode, passband_hz)

    def set_ptt(self, enabled: bool) -> None:
        self.command("set_ptt", 1 if enabled else 0)


class SharedRigState:
    def __init__(self, snapshot: RigSnapshot) -> None:
        self.lock = threading.RLock()
        self.snapshot = snapshot

    def get(self) -> RigSnapshot:
        with self.lock:
            return RigSnapshot(
                self.snapshot.frequency_hz,
                self.snapshot.mode,
                self.snapshot.passband_hz,
            )

    def set(self, snapshot: RigSnapshot) -> None:
        with self.lock:
            self.snapshot = snapshot


class LogicalState:
    """OR state used for PTT and CW sources."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.sources: Dict[str, bool] = {}

    def set(self, source: str, enabled: bool) -> Tuple[bool, bool, int]:
        with self.lock:
            old = any(self.sources.values())
            self.sources[source] = bool(enabled)
            new = any(self.sources.values())
            active = sum(1 for value in self.sources.values() if value)
            return old, new, active


def parse_port_list(value: str) -> List[str]:
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def parse_keying_client(name: str, value: str) -> KeyingClientConfig:
    parts = [x.strip().upper() for x in value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"{name} must be PORT,PTT_INPUT,CW_INPUT; got {value!r}")
    port, ptt_input, cw_input = parts
    if ptt_input not in SERIAL_LINES or cw_input not in SERIAL_LINES:
        raise ValueError(f"{name}: inputs must be DTR, RTS or NONE")
    if ptt_input != "NONE" and cw_input != "NONE" and ptt_input == cw_input:
        raise ValueError(f"{name}: PTT and CW cannot use the same input line")
    return KeyingClientConfig(name=name, port=port, ptt_input=ptt_input, cw_input=cw_input)


def load_config(path: str) -> BridgeConfig:
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding="utf-8-sig")
    for required in ("cat", "radio_keying", "rig"):
        if required not in cfg:
            raise ValueError(f"INI must contain [{required}]")

    cat = cfg["cat"]
    cat_ports = parse_port_list(cat.get("ports", ""))
    if not cat_ports:
        raise ValueError("[cat] ports must contain at least one COM port")

    keying_clients: List[KeyingClientConfig] = []
    if "keying" in cfg:
        for key, value in cfg["keying"].items():
            if key.lower().startswith("client"):
                keying_clients.append(parse_keying_client(key, value))

    rk = cfg["radio_keying"]
    radio_ptt_line = rk.get("ptt_line", fallback="NONE").strip().upper()
    radio_cw_line = rk.get("cw_line", fallback="NONE").strip().upper()
    if radio_ptt_line not in SERIAL_LINES or radio_cw_line not in SERIAL_LINES:
        raise ValueError("[radio_keying] lines must be DTR, RTS or NONE")
    if radio_ptt_line != "NONE" and radio_cw_line != "NONE" and radio_ptt_line == radio_cw_line:
        raise ValueError("[radio_keying] PTT and CW cannot use the same line")

    bridge = cfg["bridge"] if "bridge" in cfg else None
    return BridgeConfig(
        cat_ports=cat_ports,
        cat_baud=cat.getint("baud", fallback=19200),
        keying_clients=keying_clients,
        radio_keying_port=rk.get("port", fallback="").strip().upper() or None,
        radio_keying_baud=rk.getint("baud", fallback=19200),
        radio_ptt_line=radio_ptt_line,
        radio_cw_line=radio_cw_line,
        rig_host=cfg["rig"].get("host", fallback="127.0.0.1"),
        rig_port=cfg["rig"].getint("port", fallback=4532),
        rig_poll_ms=cfg["rig"].getint("poll_ms", fallback=250),
        allow_write=bridge.getboolean("allow_write", fallback=True) if bridge else True,
        allow_ptt=bridge.getboolean("allow_ptt", fallback=True) if bridge else True,
        allow_cw=bridge.getboolean("allow_cw", fallback=True) if bridge else True,
        log_level=bridge.get("log_level", fallback="INFO").upper() if bridge else "INFO",
    )


def set_serial_line(port: serial.Serial, line: str, enabled: bool) -> None:
    if line == "DTR":
        port.dtr = enabled
    elif line == "RTS":
        port.rts = enabled
    elif line != "NONE":
        raise ValueError(f"Unsupported serial control line: {line}")


def read_input_line(port: serial.Serial, line: str) -> bool:
    # com0com cross-wiring: remote DTR -> local DSR/DCD; remote RTS -> local CTS.
    if line == "DTR":
        return bool(port.dsr or port.cd)
    if line == "RTS":
        return bool(port.cts)
    if line == "NONE":
        return False
    raise ValueError(f"Unsupported input control line: {line}")


def apply_snapshot(radio: TS2000Emulator, snapshot: RigSnapshot) -> None:
    radio.state.frequency_a_hz = snapshot.frequency_hz
    mapped = HAMLIB_TO_TS2000.get(snapshot.mode)
    if mapped is not None:
        radio.state.mode_code = MODE_NAMES[mapped]


def keying_worker(
    client: KeyingClientConfig,
    output_port: Optional[serial.Serial],
    output_lock: threading.RLock,
    radio_ptt_line: str,
    radio_cw_line: str,
    allow_ptt: bool,
    allow_cw: bool,
    ptt_state: LogicalState,
    cw_state: LogicalState,
    stop: threading.Event,
    error_queue: "queue.SimpleQueue[str]",
) -> None:
    key_in: Optional[serial.Serial] = None
    try:
        key_in = serial.Serial(client.port, 19200, timeout=0, write_timeout=None)
        last_ptt = read_input_line(key_in, client.ptt_input)
        last_cw = read_input_line(key_in, client.cw_input)
        ptt_state.set(f"KEY:{client.name}", last_ptt)
        cw_state.set(f"KEY:{client.name}", last_cw)
        LOG.info("Keying %s ready: %s PTT=%s CW=%s", client.name, client.port, client.ptt_input, client.cw_input)

        while not stop.is_set():
            now_ptt = read_input_line(key_in, client.ptt_input)
            now_cw = read_input_line(key_in, client.cw_input)

            if now_ptt != last_ptt:
                last_ptt = now_ptt
                old, new, _ = ptt_state.set(f"KEY:{client.name}", now_ptt)
                if allow_ptt and old != new and radio_ptt_line != "NONE" and output_port is not None:
                    with output_lock:
                        set_serial_line(output_port, radio_ptt_line, new)

            if now_cw != last_cw:
                last_cw = now_cw
                t0 = time.perf_counter_ns()
                old, new, active = cw_state.set(f"KEY:{client.name}", now_cw)
                if active > 1 and now_cw:
                    LOG.warning("CW collision: %d keying clients active", active)
                if allow_cw and old != new and radio_cw_line != "NONE" and output_port is not None:
                    with output_lock:
                        set_serial_line(output_port, radio_cw_line, new)
                if LOG.isEnabledFor(logging.DEBUG):
                    latency_us = (time.perf_counter_ns() - t0) / 1000.0
                    LOG.debug("%s CW %s -> combined=%s in %.1fus", client.name, "ON" if now_cw else "OFF", "ON" if new else "OFF", latency_us)

            time.sleep(KEYING_POLL_SECONDS)
    except Exception as exc:
        error_queue.put(f"keying client {client.name}: {exc}")
    finally:
        ptt_state.set(f"KEY:{client.name}", False)
        cw_state.set(f"KEY:{client.name}", False)
        if key_in is not None:
            try:
                key_in.close()
            except Exception:
                pass


def cat_worker(
    port_name: str,
    baud: int,
    rig: RigctldClient,
    shared_state: SharedRigState,
    allow_write: bool,
    stop: threading.Event,
    error_queue: "queue.SimpleQueue[str]",
) -> None:
    radio = TS2000Emulator()
    try:
        with serial.Serial(port_name, baud, timeout=0.01, write_timeout=None) as cat:
            LOG.info("CAT client ready: %s @ %d", port_name, baud)
            while not stop.is_set():
                apply_snapshot(radio, shared_state.get())
                data = cat.read(4096)
                if not data:
                    continue
                text = data.decode("ascii", errors="replace")
                LOG.debug("CAT %s RX: %r", port_name, text)
                before_f, before_m = radio.state.frequency_a_hz, radio.state.mode_code
                responses = radio.feed(text)
                after_f, after_m = radio.state.frequency_a_hz, radio.state.mode_code

                if allow_write:
                    if after_f != before_f:
                        rig.set_frequency(after_f)
                    if after_m != before_m:
                        name = next((n for n, c in MODE_NAMES.items() if c == after_m), None)
                        reverse = {
                            "LSB": "LSB", "USB": "USB", "CW": "CW", "CW-R": "CWR",
                            "FM": "FM", "AM": "AM", "FSK": "RTTY", "FSK-R": "RTTYR",
                        }
                        if name in reverse:
                            rig.set_mode(reverse[name], 0)
                else:
                    apply_snapshot(radio, shared_state.get())
                    radio.state.ptt = False

                for response in responses:
                    cat.write(response.encode("ascii"))
    except Exception as exc:
        error_queue.put(f"CAT {port_name}: {exc}")


def rig_poll_worker(
    rig: RigctldClient,
    shared_state: SharedRigState,
    poll_ms: int,
    stop: threading.Event,
) -> None:
    while not stop.is_set():
        try:
            shared_state.set(rig.get_snapshot())
        except Exception as exc:
            LOG.error("rigctld poll failed: %s", exc)
        time.sleep(max(10, poll_ms) / 1000.0)


def main() -> int:
    parser = argparse.ArgumentParser(description="GADX Vector multi-client CAT/keying bridge")
    parser.add_argument("--config", default="bridge_multi.ini")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    LOG.info("Configuration file: %s", args.config)
    LOG.info("CAT ports: %s @ %d", ",".join(config.cat_ports), config.cat_baud)
    LOG.info("Keying clients: %s", ", ".join(f"{c.name}:{c.port}" for c in config.keying_clients) or "none")
    LOG.info("Physical keying: %s @ %d PTT=%s CW=%s", config.radio_keying_port or "disabled", config.radio_keying_baud, config.radio_ptt_line, config.radio_cw_line)

    rig = RigctldClient(config.rig_host, config.rig_port)
    try:
        rig.connect()
        initial = rig.get_snapshot()
    except Exception as exc:
        LOG.error("Cannot initialize rigctld: %s", exc)
        return 2

    shared_state = SharedRigState(initial)
    ptt_state = LogicalState()
    cw_state = LogicalState()
    stop = threading.Event()
    errors: "queue.SimpleQueue[str]" = queue.SimpleQueue()
    output_lock = threading.RLock()
    output_port: Optional[serial.Serial] = None

    if config.radio_ptt_line != "NONE" or config.radio_cw_line != "NONE":
        if not config.radio_keying_port:
            LOG.error("Physical keying lines configured but [radio_keying] port is empty")
            return 2
        try:
            output_port = serial.Serial(config.radio_keying_port, config.radio_keying_baud, timeout=0, write_timeout=None)
            output_port.rts = False
            output_port.dtr = False
        except Exception as exc:
            LOG.error("Cannot open physical keying port %s: %s", config.radio_keying_port, exc)
            return 2

    threads: List[threading.Thread] = []
    poll_thread = threading.Thread(target=rig_poll_worker, args=(rig, shared_state, config.rig_poll_ms, stop), name="RigPoll", daemon=True)
    poll_thread.start()
    threads.append(poll_thread)

    for client in config.keying_clients:
        t = threading.Thread(
            target=keying_worker,
            args=(client, output_port, output_lock, config.radio_ptt_line, config.radio_cw_line, config.allow_ptt, config.allow_cw, ptt_state, cw_state, stop, errors),
            name=f"Key-{client.name}",
            daemon=True,
        )
        t.start()
        threads.append(t)

    for cat_port in config.cat_ports:
        t = threading.Thread(
            target=cat_worker,
            args=(cat_port, config.cat_baud, rig, shared_state, config.allow_write, stop, errors),
            name=f"CAT-{cat_port}",
            daemon=True,
        )
        t.start()
        threads.append(t)

    LOG.info("Bridge ready")
    return_code = 0
    try:
        while True:
            try:
                error = errors.get_nowait()
            except queue.Empty:
                error = None
            if error:
                raise RuntimeError(error)
            time.sleep(0.25)
    except KeyboardInterrupt:
        LOG.info("Stopped by user")
    except Exception as exc:
        LOG.error("Bridge error: %s", exc)
        return_code = 2
    finally:
        stop.set()
        for t in threads:
            t.join(timeout=2.0)
        if output_port is not None:
            try:
                output_port.rts = False
                output_port.dtr = False
            except Exception:
                pass
            try:
                output_port.close()
            except Exception:
                pass
        try:
            if config.allow_ptt:
                rig.set_ptt(False)
        except Exception:
            pass
        rig.close()
    return return_code


if __name__ == "__main__":
    sys.exit(main())
