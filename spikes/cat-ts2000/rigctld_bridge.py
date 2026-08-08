from __future__ import annotations

import argparse
import logging
import socket
import sys
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


class RigctldClient:
    """Small rigctld client using Hamlib's Extended Response Protocol.

    Canonical protocol reference: rigctld(1).  Commands are prefixed with '+'
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GADX Vector SPIKE: bridge a real rigctld radio to the TS-2000 CAT facade"
    )
    parser.add_argument("--port", required=True, help="TS-2000 serial side, e.g. COM18")
    parser.add_argument("--baud", type=int, default=19200)
    parser.add_argument("--rig-host", default="127.0.0.1")
    parser.add_argument("--rig-port", type=int, default=4532)
    parser.add_argument("--poll-ms", type=int, default=250, help="rigctld polling interval (default: 250 ms)")
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="EXPERIMENTAL: allow N1MM FA/MD changes to change the physical radio through rigctld",
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


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.poll_ms < 50:
        LOG.error("--poll-ms must be at least 50 ms")
        return 2

    radio = TS2000Emulator()
    rig = RigctldClient(args.rig_host, args.rig_port)

    LOG.info("GADX Vector rigctld bridge starting")
    LOG.info("CAT facade: %s @ %d 8N1", args.port, args.baud)
    LOG.info("Physical radio backend: rigctld %s:%d", args.rig_host, args.rig_port)
    LOG.info("Mode: %s", "READ/WRITE (experimental)" if args.allow_write else "READ-ONLY (safe first test)")

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

        with serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.05,
            write_timeout=None,
        ) as cat_port:
            LOG.info("Bridge ready — open N1MM on the paired CAT COM port")
            next_poll = 0.0
            last_snapshot = initial

            while True:
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
                responses = radio.feed(text)
                requested_freq = radio.state.frequency_a_hz
                requested_mode = radio.state.mode_code

                # In safe read-only mode, N1MM may send set commands but they are
                # intentionally not propagated to hardware.  Restore the most
                # recently observed physical state immediately.
                if not args.allow_write:
                    apply_snapshot(radio, last_snapshot)
                else:
                    if requested_freq != before_freq:
                        LOG.warning("N1MM -> PHYSICAL RADIO set frequency: %d Hz", requested_freq)
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
                            LOG.warning("N1MM -> PHYSICAL RADIO set mode: %s", hamlib_mode)
                            rig.set_mode(hamlib_mode, 0)
                            last_snapshot = rig.get_snapshot()
                            apply_snapshot(radio, last_snapshot)
                        else:
                            LOG.warning("Cannot map TS-2000 mode code %s to Hamlib", requested_mode)

                for response in responses:
                    # Responses are regenerated from the current physical state
                    # on the next logger poll.  Query responses in this batch are
                    # already based on the state present when feed() processed it.
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
        rig.close()


if __name__ == "__main__":
    sys.exit(main())
