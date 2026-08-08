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

# Hamlib mode token -> TS-2000 MD code/name used by the emulator.
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
    """Small rigctld client using Hamlib's Extended Response Protocol.

    Canonical protocol reference: rigctld(1). Commands are prefixed with '+'
    so every reply ends with an explicit 'RPRT n' record, which makes framing
    robust for scripts.
    """

    def __init__(self, host: str, port: int, timeout: float = 2.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
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

    def _ensure_connected(self) -> None:
        if self.sock is None or self.file is None:
            self.connect()

    def command(self, long_command: str, *args: object) -> Dict[str, str]:
        self._ensure_connected()
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
            self.close()
            raise

        values: Dict[str, str] = {}
        for line in records:
            if ": " in line:
                key, value = line.split(": ", 1)
                values[key.strip()] = value.strip()
        return values

    def get_snapshot(self) -> RigSnapshot:
        freq_values = self.command("get_freq")
        mode_values = self.command("get_mode")

        if "Frequency" not in freq_values:
            raise RuntimeError(f"rigctld get_freq returned no Frequency: {freq_values}")
        if "Mode" not in mode_values:
            raise RuntimeError(f"rigctld get_mode returned no Mode: {mode_values}")

        frequency_hz = int(float(freq_values["Frequency"]))
        mode = mode_values["Mode"].upper()
        passband_hz = int(float(mode_values.get("Passband", "0")))
        return RigSnapshot(frequency_hz, mode, passband_hz)

    def set_frequency(self, frequency_hz: int) -> None:
        self.command("set_freq", frequency_hz)

    def set_mode(self, mode: str, passband_hz: int = 0) -> None:
        self.command("set_mode", mode, passband_hz)

    def set_ptt(self, enabled: bool) -> None:
        # Hamlib rigctld set_ptt uses 0=RX and 1=TX.
        self.command("set_ptt", 1 if enabled else 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GADX Vector SPIKE: unified TS-2000 CAT + serial keying bridge to rigctld"
    )
    parser.add_argument("--port", required=True, help="TS-2000 serial side, e.g. COM18")
    parser.add_argument("--baud", type=int, default=19200)
    parser.add_argument("--keying-port", help="Optional serial-keying monitor side, e.g. COM32")
    parser.add_argument("--keying-baud", type=int, default=19200)
    parser.add_argument("--rig-host", default="127.0.0.1")
    parser.add_argument("--rig-port", type=int, default=4532)
    parser.add_argument("--poll-ms", type=int, default=250, help="rigctld polling interval (default: 250 ms)")
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="EXPERIMENTAL: allow CAT FA/MD changes to change the physical radio through rigctld",
    )
    parser.add_argument(
        "--allow-ptt",
        action="store_true",
        help="EXPERIMENTAL/DANGEROUS: allow CAT TX/RX and keying DTR to key the physical radio through rigctld",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def apply_snapshot(radio: TS2000Emulator, snapshot: RigSnapshot) -> None:
    radio.state.frequency_a_hz = snapshot.frequency_hz

    mapped_name = HAMLIB_TO_TS2000.get(snapshot.mode)
    if mapped_name is None:
        LOG.warning("Hamlib mode %s has no TS-2000 mapping; retaining current mode", snapshot.mode)
        return

    radio.state.mode_code = MODE_NAMES[mapped_name]


def keying_worker(
    port_name: str,
    baud: int,
    events: "queue.SimpleQueue[KeyingEvent]",
    stop_event: threading.Event,
) -> None:
    """Capture N1MM serial keying without letting CAT polling hide short dits.

    With the com0com mapping used by this SPIKE:
      remote DTR (N1MM COM31) -> local DSR/DCD (Vector COM32) = PTT
      remote RTS (N1MM COM31) -> local CTS     (Vector COM32) = CW key

    The worker only observes modem-control lines and posts transitions to the
    main bridge. It never talks to rigctld directly.
    """
    try:
        with serial.Serial(
            port=port_name,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0,
            write_timeout=None,
        ) as key_port:
            last_ptt = bool(key_port.dsr or key_port.cd)
            last_cw = bool(key_port.cts)
            events.put(KeyingEvent("PTT", last_ptt, time.monotonic()))
            events.put(KeyingEvent("CW", last_cw, time.monotonic()))
            LOG.info(
                "Keying interface ready on %s: DTR->DSR/DCD=PTT, RTS->CTS=CW",
                port_name,
            )

            while not stop_event.is_set():
                now = time.monotonic()
                ptt = bool(key_port.dsr or key_port.cd)
                cw = bool(key_port.cts)

                if ptt != last_ptt:
                    last_ptt = ptt
                    events.put(KeyingEvent("PTT", ptt, now))

                if cw != last_cw:
                    last_cw = cw
                    events.put(KeyingEvent("CW", cw, now))

                # 1 ms sampling is comfortably below the ~46 ms dits observed
                # from N1MM in the SPIKE while avoiding a busy-spin core.
                time.sleep(0.001)
    except serial.SerialException as exc:
        LOG.error("Keying port error on %s: %s", port_name, exc)
        events.put(KeyingEvent("ERROR", False, time.monotonic()))


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.poll_ms < 50:
        LOG.error("--poll-ms must be at least 50 ms")
        return 2

    if args.allow_ptt and not args.allow_write:
        LOG.error("--allow-ptt requires --allow-write")
        return 2

    radio = TS2000Emulator()
    rig = RigctldClient(args.rig_host, args.rig_port)

    physical_ptt_asserted = False
    cat_ptt_requested = False
    keying_ptt_requested = False
    cw_asserted_at: Optional[float] = None

    keying_events: "queue.SimpleQueue[KeyingEvent]" = queue.SimpleQueue()
    keying_stop = threading.Event()
    keying_thread: Optional[threading.Thread] = None

    LOG.info("GADX Vector unified bridge starting")
    LOG.info("CAT facade: %s @ %d 8N1", args.port, args.baud)
    LOG.info("Physical radio backend: rigctld %s:%d", args.rig_host, args.rig_port)
    LOG.info("CAT writes: %s", "ENABLED (experimental)" if args.allow_write else "DISABLED / READ-ONLY")
    LOG.info("Physical PTT: %s", "ENABLED (experimental)" if args.allow_ptt else "DISABLED")
    LOG.info("Serial keying: %s", args.keying_port or "DISABLED")

    def update_physical_ptt() -> None:
        nonlocal physical_ptt_asserted
        desired = bool(cat_ptt_requested or keying_ptt_requested)
        if desired == physical_ptt_asserted:
            return

        if not args.allow_ptt:
            LOG.warning(
                "Blocked physical PTT %s because --allow-ptt is not enabled",
                "ON" if desired else "OFF",
            )
            return

        LOG.warning(
            "BRIDGE -> PHYSICAL RADIO PTT %s (CAT=%s KEYING=%s)",
            "ON" if desired else "OFF",
            "ON" if cat_ptt_requested else "OFF",
            "ON" if keying_ptt_requested else "OFF",
        )
        rig.set_ptt(desired)
        physical_ptt_asserted = desired

    try:
        rig.connect()
        initial = rig.get_snapshot()
        apply_snapshot(radio, initial)
        LOG.info(
            "Initial physical radio: %d Hz %s passband=%d Hz",
            initial.frequency_hz,
            initial.mode,
            initial.passband_hz,
        )

        if args.keying_port:
            keying_thread = threading.Thread(
                target=keying_worker,
                args=(args.keying_port, args.keying_baud, keying_events, keying_stop),
                name="vector-keying-monitor",
                daemon=True,
            )
            keying_thread.start()

        with serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.01,
            write_timeout=None,
        ) as cat_port:
            LOG.info("Bridge ready — open N1MM on the paired CAT/keying COM ports")
            next_poll = 0.0
            last_snapshot = initial

            while True:
                # Drain high-resolution serial-keying events first.
                while True:
                    try:
                        event = keying_events.get_nowait()
                    except queue.Empty:
                        break

                    if event.kind == "ERROR":
                        raise serial.SerialException("keying monitor stopped after a serial error")

                    if event.kind == "PTT":
                        keying_ptt_requested = event.enabled
                        LOG.info("KEYING PTT %s (remote DTR)", "ON" if event.enabled else "OFF")
                        update_physical_ptt()
                        continue

                    if event.kind == "CW":
                        if event.enabled:
                            cw_asserted_at = event.timestamp
                            LOG.info("CW ON  (remote RTS)")
                        else:
                            if cw_asserted_at is not None:
                                pulse_ms = (event.timestamp - cw_asserted_at) * 1000.0
                                LOG.info("CW OFF (pulse %.1f ms)", pulse_ms)
                            else:
                                LOG.info("CW OFF")
                            cw_asserted_at = None
                        continue

                now = time.monotonic()
                if now >= next_poll:
                    try:
                        snapshot = rig.get_snapshot()
                        if snapshot != last_snapshot:
                            LOG.info(
                                "Physical radio changed: %d Hz %s passband=%d Hz",
                                snapshot.frequency_hz,
                                snapshot.mode,
                                snapshot.passband_hz,
                            )
                        apply_snapshot(radio, snapshot)
                        last_snapshot = snapshot
                    except (OSError, ConnectionError, RuntimeError, ValueError) as exc:
                        LOG.error("rigctld poll failed: %s", exc)
                        time.sleep(0.5)
                        try:
                            rig.connect()
                            # Re-assert requested PTT state after reconnect only
                            # through the same guarded path.
                            physical_ptt_asserted = False
                            update_physical_ptt()
                        except OSError as reconnect_exc:
                            LOG.error("rigctld reconnect failed: %s", reconnect_exc)
                    next_poll = now + (args.poll_ms / 1000.0)

                data = cat_port.read(4096)
                if not data:
                    continue

                text = data.decode("ascii", errors="replace")
                LOG.debug("CAT RX raw: %r", text)

                before_freq = radio.state.frequency_a_hz
                before_mode = radio.state.mode_code
                before_ptt = radio.state.ptt

                responses = radio.feed(text)

                requested_freq = radio.state.frequency_a_hz
                requested_mode = radio.state.mode_code
                requested_ptt = radio.state.ptt

                if not args.allow_write:
                    apply_snapshot(radio, last_snapshot)
                    radio.state.ptt = False
                    cat_ptt_requested = False
                else:
                    if requested_freq != before_freq:
                        LOG.warning("CAT -> PHYSICAL RADIO set frequency: %d Hz", requested_freq)
                        rig.set_frequency(requested_freq)
                        last_snapshot = rig.get_snapshot()
                        apply_snapshot(radio, last_snapshot)

                    if requested_mode != before_mode:
                        ts_mode_name = next(
                            (name for name, code in MODE_NAMES.items() if code == requested_mode), None
                        )
                        reverse = {
                            "LSB": "LSB",
                            "USB": "USB",
                            "CW": "CW",
                            "CW-R": "CWR",
                            "FM": "FM",
                            "AM": "AM",
                            "FSK": "RTTY",
                            "FSK-R": "RTTYR",
                        }
                        hamlib_mode = reverse.get(ts_mode_name or "")
                        if hamlib_mode:
                            LOG.warning("CAT -> PHYSICAL RADIO set mode: %s", hamlib_mode)
                            rig.set_mode(hamlib_mode, 0)
                            last_snapshot = rig.get_snapshot()
                            apply_snapshot(radio, last_snapshot)
                        else:
                            LOG.warning("Cannot map TS-2000 mode code %s to Hamlib", requested_mode)

                    if requested_ptt != before_ptt:
                        cat_ptt_requested = requested_ptt
                        LOG.info("CAT PTT %s", "ON" if requested_ptt else "OFF")
                        update_physical_ptt()

                for response in responses:
                    LOG.debug("CAT TX: %s", response)
                    cat_port.write(response.encode("ascii"))

                while radio.unsupported_commands:
                    unknown = radio.unsupported_commands.pop(0)
                    LOG.warning("UNSUPPORTED CAT command: %s;", unknown)

    except KeyboardInterrupt:
        LOG.info("Stopped by user")
        return 0
    except (serial.SerialException, OSError, ConnectionError, RuntimeError, ValueError) as exc:
        LOG.error("Bridge error: %s", exc)
        return 2
    finally:
        keying_stop.set()
        if keying_thread is not None:
            keying_thread.join(timeout=1.0)

        # Fail-safe: if this process ever asserted physical PTT, make a best-effort
        # attempt to force RX before closing the rigctld connection.
        if args.allow_ptt and physical_ptt_asserted:
            try:
                LOG.warning("Fail-safe shutdown: forcing physical PTT OFF")
                rig.set_ptt(False)
            except (OSError, ConnectionError, RuntimeError, ValueError) as exc:
                LOG.error("Fail-safe PTT OFF failed: %s", exc)
        rig.close()


if __name__ == "__main__":
    sys.exit(main())
