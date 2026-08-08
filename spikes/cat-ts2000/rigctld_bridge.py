from __future__ import annotations

import argparse
import logging
import queue
import socket
import sys
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import serial

from ts2000 import MODE_NAMES, TS2000Emulator


LOG = logging.getLogger("gadx.vector.rigctld-bridge")

HAMLIB_TO_TS2000 = {
    "LSB": "LSB", "USB": "USB", "CW": "CW", "CWR": "CW-R",
    "FM": "FM", "WFM": "FM", "AM": "AM", "RTTY": "FSK",
    "RTTYR": "FSK-R", "PKTLSB": "LSB", "PKTUSB": "USB", "PKTFM": "FM",
}


@dataclass
class RigSnapshot:
    frequency_hz: int
    mode: str
    passband_hz: int


@dataclass(frozen=True)
class KeyingEvent:
    kind: str
    enabled: bool
    timestamp: float


class RigctldClient:
    def __init__(self, host: str, port: int, timeout: float = 2.0) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.sock: Optional[socket.socket] = None
        self.file = None

    def connect(self) -> None:
        self.close()
        LOG.info("Connecting to rigctld at %s:%d", self.host, self.port)
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        self.file = self.sock.makefile("rwb", buffering=0)
        LOG.info("Connected to rigctld")

    def close(self) -> None:
        if self.file is not None:
            try: self.file.close()
            except OSError: pass
            self.file = None
        if self.sock is not None:
            try: self.sock.close()
            except OSError: pass
            self.sock = None

    def command(self, long_command: str, *args: object) -> Dict[str, str]:
        if self.sock is None or self.file is None:
            self.connect()
        assert self.file is not None
        payload = "+\\" + long_command
        if args: payload += " " + " ".join(str(arg) for arg in args)
        payload += "\n"
        LOG.debug("RIGCTL TX: %s", payload.rstrip())
        try:
            self.file.write(payload.encode("ascii"))
            records: List[str] = []
            while True:
                raw = self.file.readline()
                if not raw: raise ConnectionError("rigctld closed the connection")
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                LOG.debug("RIGCTL RX: %s", line)
                records.append(line)
                if line.startswith("RPRT "):
                    code = int(line.split(maxsplit=1)[1])
                    if code != 0: raise RuntimeError(f"rigctld {long_command} failed with RPRT {code}")
                    break
        except (OSError, ConnectionError):
            self.close(); raise
        values: Dict[str, str] = {}
        for line in records:
            if ": " in line:
                key, value = line.split(": ", 1); values[key.strip()] = value.strip()
        return values

    def get_snapshot(self) -> RigSnapshot:
        f, m = self.command("get_freq"), self.command("get_mode")
        return RigSnapshot(int(float(f["Frequency"])), m["Mode"].upper(), int(float(m.get("Passband", "0"))))

    def set_frequency(self, hz: int) -> None: self.command("set_freq", hz)
    def set_mode(self, mode: str, passband_hz: int = 0) -> None: self.command("set_mode", mode, passband_hz)
    def set_ptt(self, enabled: bool) -> None: self.command("set_ptt", 1 if enabled else 0)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GADX Vector SPIKE: TS-2000 CAT + real-time serial keying bridge")
    p.add_argument("--port", required=True, help="TS-2000 CAT side, e.g. COM18")
    p.add_argument("--baud", type=int, default=19200)
    p.add_argument("--keying-port", help="N1MM keying receive side, e.g. COM32")
    p.add_argument("--keying-baud", type=int, default=19200)
    p.add_argument("--radio-keying-port", help="Physical radio keying port, e.g. IC-7760 USB(B) COM22")
    p.add_argument("--radio-keying-baud", type=int, default=9600)
    p.add_argument("--allow-cw", action="store_true", help="DANGEROUS: mirror CW key DOWN/UP to physical radio RTS")
    p.add_argument("--rig-host", default="127.0.0.1")
    p.add_argument("--rig-port", type=int, default=4532)
    p.add_argument("--poll-ms", type=int, default=250)
    p.add_argument("--allow-write", action="store_true")
    p.add_argument("--allow-ptt", action="store_true")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def apply_snapshot(radio: TS2000Emulator, s: RigSnapshot) -> None:
    radio.state.frequency_a_hz = s.frequency_hz
    mapped = HAMLIB_TO_TS2000.get(s.mode)
    if mapped is not None: radio.state.mode_code = MODE_NAMES[mapped]


def keying_worker(port_name: str, baud: int, events: "queue.SimpleQueue[KeyingEvent]", stop: threading.Event) -> None:
    try:
        with serial.Serial(port_name, baud, timeout=0, write_timeout=None) as p:
            last_ptt, last_cw = bool(p.dsr or p.cd), bool(p.cts)
            events.put(KeyingEvent("PTT", last_ptt, time.monotonic()))
            events.put(KeyingEvent("CW", last_cw, time.monotonic()))
            LOG.info("N1MM keying input ready on %s: DTR->DSR/DCD=PTT, RTS->CTS=CW", port_name)
            while not stop.is_set():
                now = time.monotonic(); ptt, cw = bool(p.dsr or p.cd), bool(p.cts)
                if ptt != last_ptt:
                    last_ptt = ptt; events.put(KeyingEvent("PTT", ptt, now))
                if cw != last_cw:
                    last_cw = cw; events.put(KeyingEvent("CW", cw, now))
                time.sleep(0.001)
    except serial.SerialException as exc:
        LOG.error("Keying input error on %s: %s", port_name, exc)
        events.put(KeyingEvent("ERROR", False, time.monotonic()))


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")
    if args.allow_ptt and not args.allow_write:
        LOG.error("--allow-ptt requires --allow-write"); return 2
    if args.allow_cw and (not args.keying_port or not args.radio_keying_port):
        LOG.error("--allow-cw requires --keying-port and --radio-keying-port"); return 2

    radio, rig = TS2000Emulator(), RigctldClient(args.rig_host, args.rig_port)
    physical_ptt_asserted = cat_ptt_requested = keying_ptt_requested = False
    cw_asserted_at: Optional[float] = None
    events: "queue.SimpleQueue[KeyingEvent]" = queue.SimpleQueue()
    stop = threading.Event(); thread: Optional[threading.Thread] = None
    radio_key_port: Optional[serial.Serial] = None

    def update_ptt() -> None:
        nonlocal physical_ptt_asserted
        desired = bool(cat_ptt_requested or keying_ptt_requested)
        if desired == physical_ptt_asserted: return
        if not args.allow_ptt:
            LOG.warning("Blocked physical PTT %s", "ON" if desired else "OFF"); return
        LOG.warning("BRIDGE -> PHYSICAL RADIO PTT %s", "ON" if desired else "OFF")
        rig.set_ptt(desired); physical_ptt_asserted = desired

    try:
        rig.connect(); initial = rig.get_snapshot(); apply_snapshot(radio, initial); last_snapshot = initial
        LOG.info("Initial physical radio: %d Hz %s", initial.frequency_hz, initial.mode)

        if args.radio_keying_port:
            radio_key_port = serial.Serial(args.radio_keying_port, args.radio_keying_baud, timeout=0, write_timeout=None)
            # Fail-safe idle state before enabling any forwarding.
            radio_key_port.rts = False
            radio_key_port.dtr = False
            LOG.info("Physical keying output ready on %s @ %d; RTS=CW", args.radio_keying_port, args.radio_keying_baud)

        if args.keying_port:
            thread = threading.Thread(target=keying_worker, args=(args.keying_port, args.keying_baud, events, stop), daemon=True)
            thread.start()

        with serial.Serial(args.port, args.baud, timeout=0.01, write_timeout=None) as cat:
            LOG.info("Bridge ready")
            next_poll = 0.0
            while True:
                while True:
                    try: event = events.get_nowait()
                    except queue.Empty: break
                    if event.kind == "ERROR": raise serial.SerialException("keying input failed")
                    if event.kind == "PTT":
                        keying_ptt_requested = event.enabled
                        LOG.info("KEYING PTT %s", "ON" if event.enabled else "OFF")
                        update_ptt(); continue
                    if event.kind == "CW":
                        if event.enabled:
                            cw_asserted_at = event.timestamp; LOG.info("CW ON (remote RTS)")
                        else:
                            pulse = (event.timestamp - cw_asserted_at) * 1000 if cw_asserted_at is not None else 0
                            LOG.info("CW OFF (pulse %.1f ms)", pulse); cw_asserted_at = None
                        if args.allow_cw and radio_key_port is not None:
                            radio_key_port.rts = event.enabled
                            LOG.debug("KEYING MIRROR: COM input CW=%d -> %s RTS=%d", int(event.enabled), args.radio_keying_port, int(event.enabled))

                now = time.monotonic()
                if now >= next_poll:
                    try:
                        s = rig.get_snapshot(); apply_snapshot(radio, s); last_snapshot = s
                    except Exception as exc:
                        LOG.error("rigctld poll failed: %s", exc)
                    next_poll = now + args.poll_ms / 1000.0

                data = cat.read(4096)
                if not data: continue
                text = data.decode("ascii", errors="replace"); LOG.debug("CAT RX raw: %r", text)
                bf, bm, bp = radio.state.frequency_a_hz, radio.state.mode_code, radio.state.ptt
                responses = radio.feed(text)
                rf, rm, rp = radio.state.frequency_a_hz, radio.state.mode_code, radio.state.ptt
                if not args.allow_write:
                    apply_snapshot(radio, last_snapshot); radio.state.ptt = False; cat_ptt_requested = False
                else:
                    if rf != bf:
                        LOG.warning("CAT -> PHYSICAL RADIO set frequency: %d Hz", rf); rig.set_frequency(rf)
                    if rm != bm:
                        name = next((n for n, c in MODE_NAMES.items() if c == rm), None)
                        reverse = {"LSB":"LSB","USB":"USB","CW":"CW","CW-R":"CWR","FM":"FM","AM":"AM","FSK":"RTTY","FSK-R":"RTTYR"}
                        if name in reverse:
                            LOG.warning("CAT -> PHYSICAL RADIO set mode: %s", reverse[name]); rig.set_mode(reverse[name], 0)
                    if rp != bp:
                        cat_ptt_requested = rp; update_ptt()
                for response in responses:
                    LOG.debug("CAT TX: %s", response); cat.write(response.encode("ascii"))
    except KeyboardInterrupt:
        LOG.info("Stopped by user"); return 0
    except Exception as exc:
        LOG.error("Bridge error: %s", exc); return 2
    finally:
        stop.set()
        if thread is not None: thread.join(timeout=1.0)
        # CW fail-safe is independent from CAT/PTT fail-safe.
        if radio_key_port is not None:
            try:
                LOG.warning("Fail-safe shutdown: forcing CW KEY UP (RTS OFF)")
                radio_key_port.rts = False; radio_key_port.dtr = False
            except serial.SerialException as exc:
                LOG.error("Fail-safe CW OFF failed: %s", exc)
            try: radio_key_port.close()
            except serial.SerialException: pass
        if args.allow_ptt and physical_ptt_asserted:
            try:
                LOG.warning("Fail-safe shutdown: forcing physical PTT OFF"); rig.set_ptt(False)
            except Exception as exc: LOG.error("Fail-safe PTT OFF failed: %s", exc)
        rig.close()


if __name__ == "__main__":
    sys.exit(main())
