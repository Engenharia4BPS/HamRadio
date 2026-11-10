"""Isolated WinKey-to-rigctld prototype for GADX Vector.

This program intentionally does not import or start ``vector_hub.py``.  It opens
only its own virtual COM port and speaks directly to a configured rigctld endpoint.
That keeps the validated CAT/PTT/physical-CW paths of GADX Vector untouched.
"""

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
from typing import Callable, List, Optional, Protocol, Sequence, Tuple

try:
    import serial
except ImportError:  # --check should still explain the missing runtime clearly.
    serial = None


LOG = logging.getLogger("gadx.winkey")

# K1EL WinKey host-mode command bytes.  The prototype implements the narrow
# subset N1MM needs to initialise a keyer, set WPM, send buffered ASCII and
# abort it.  Every known command still has its correct parameter length so it
# never accidentally turns a command parameter into CW text.
ADMIN = 0x00
SET_SPEED = 0x02
SET_PAUSE = 0x06
GET_SPEED_POT = 0x07
BACKSPACE = 0x08
CLEAR_BUFFER = 0x0A
KEY_IMMEDIATE = 0x0B
LOAD_DEFAULTS = 0x0F
REQUEST_STATUS = 0x15
BUFFER_POINTER = 0x16
PTT_CONTROL = 0x18
TIMED_KEY_DOWN = 0x19
WAIT = 0x1A
MERGE_LETTERS = 0x1B
BUFFERED_SPEED = 0x1C
CANCEL_BUFFERED_SPEED = 0x1E

STATUS_TAG = 0xC0
STATUS_BUSY = 0x04
SPEED_POT_TAG = 0x80

# International Morse patterns used only to model WinKey completion/echo
# timing.  The actual CW waveform remains the radio's own responsibility.
MORSE_PATTERNS = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".",
    "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---",
    "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---",
    "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-",
    "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--",
    "Z": "--..", "0": "-----", "1": ".----", "2": "..---", "3": "...--",
    "4": "....-", "5": ".....", "6": "-....", "7": "--...", "8": "---..",
    "9": "----.", "/": "-..-.", "?": "..--..", ".": ".-.-.-",
    ",": "--..--", "=": "-...-", "+": ".-.-.", "-": "-....-",
    "@": ".--.-.", "(": "-.--.", ")": "-.--.-",
}


def _morse_character_units(character: str) -> int:
    pattern = MORSE_PATTERNS.get(character.upper())
    if pattern is None:
        # Unknown printable characters use a conservative average rather than
        # falsely signalling completion too early.
        return 10
    return sum(3 if element == "-" else 1 for element in pattern) + len(pattern) - 1


def morse_timing(text: str, wpm: int) -> Tuple[float, List[Tuple[str, float]]]:
    """Return total duration and individual serial-echo completion offsets.

    A standard PARIS word is 50 dit units, so one dit is 1.2/WPM seconds.
    WinKey echoes a serial character once that character has been sent, not
    when the host merely placed it in the buffer.
    """
    dit_seconds = 1.2 / max(wpm, 1)
    elapsed_units = 0
    echoes: List[Tuple[str, float]] = []
    words = [word for word in text.split() if word]
    for word_index, word in enumerate(words):
        for character_index, character in enumerate(word):
            elapsed_units += _morse_character_units(character)
            echoes.append((character, elapsed_units * dit_seconds))
            if character_index < len(word) - 1:
                elapsed_units += 3
        if word_index < len(words) - 1:
            elapsed_units += 7
    return max(0.05, elapsed_units * dit_seconds), echoes


@dataclass(frozen=True)
class Settings:
    serial_port: str
    serial_baud: int
    text_gap_seconds: float
    max_message_chars: int
    firmware_revision: int
    initial_wpm: int
    min_wpm: int
    max_wpm: int
    rig_host: str
    rig_port: int
    rig_timeout_seconds: float
    allow_transmit: bool
    log_text: bool
    protocol_trace: bool


def _bounded_int(section: configparser.SectionProxy, name: str, minimum: int, maximum: int) -> int:
    value = section.getint(name)
    if not minimum <= value <= maximum:
        raise ValueError(f"[{section.name}] {name} must be between {minimum} and {maximum}")
    return value


def load_settings(path: Path) -> Settings:
    parser = configparser.ConfigParser()
    if not parser.read(path, encoding="utf-8-sig"):
        raise ValueError(f"cannot read configuration: {path}")
    for section in ("winkey", "rigctld", "safety", "logging"):
        if section not in parser:
            raise ValueError(f"INI must contain [{section}]")

    wk = parser["winkey"]
    rig = parser["rigctld"]
    safety = parser["safety"]
    logging_settings = parser["logging"]
    port = wk.get("port", "").strip().upper()
    if not port:
        raise ValueError("[winkey] port must not be empty")

    gap_ms = _bounded_int(wk, "text_gap_ms", 1, 1000)
    max_chars = _bounded_int(wk, "max_message_chars", 1, 2048)
    min_wpm = _bounded_int(wk, "min_wpm", 5, 99)
    max_wpm = _bounded_int(wk, "max_wpm", min_wpm, 99)
    initial_wpm = _bounded_int(wk, "initial_wpm", min_wpm, max_wpm)
    revision = _bounded_int(wk, "firmware_revision", 1, 255)
    timeout_ms = _bounded_int(rig, "timeout_ms", 100, 30000)
    rig_host = rig.get("host", "").strip()
    if not rig_host:
        raise ValueError("[rigctld] host must not be empty")

    return Settings(
        serial_port=port,
        serial_baud=_bounded_int(wk, "baud", 1200, 115200),
        text_gap_seconds=gap_ms / 1000.0,
        max_message_chars=max_chars,
        firmware_revision=revision,
        initial_wpm=initial_wpm,
        min_wpm=min_wpm,
        max_wpm=max_wpm,
        rig_host=rig_host,
        rig_port=_bounded_int(rig, "port", 1, 65535),
        rig_timeout_seconds=timeout_ms / 1000.0,
        allow_transmit=safety.getboolean("allow_transmit", False),
        log_text=logging_settings.getboolean("log_text", True),
        protocol_trace=logging_settings.getboolean("protocol_trace", False),
    )


class RigctldTransport:
    """One request per TCP connection, with no automatic TX retry.

    Retrying a failed ``b`` request could duplicate an over-the-air message, so
    the caller gets one attempt and a clear error in the local log instead.
    """

    def __init__(self, host: str, port: int, timeout_seconds: float):
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds

    def command(self, command: str) -> None:
        payload = (command.rstrip("\r\n") + "\n").encode("ascii", errors="strict")
        with socket.create_connection((self.host, self.port), timeout=self.timeout_seconds) as connection:
            connection.settimeout(self.timeout_seconds)
            connection.sendall(payload)
            response = bytearray()
            while True:
                block = connection.recv(4096)
                if not block:
                    break
                response.extend(block)
                if b"RPRT " in response:
                    break

        if not response:
            raise RuntimeError("rigctld closed the request without an RPRT reply")
        lines = response.decode("utf-8", errors="replace").replace("\r", "").split("\n")
        report = next((line for line in lines if line.startswith("RPRT ")), None)
        if report is None:
            raise RuntimeError(f"unexpected rigctld reply: {response!r}")
        try:
            code = int(report.split(maxsplit=1)[1])
        except (IndexError, ValueError) as error:
            raise RuntimeError(f"malformed rigctld reply: {report!r}") from error
        if code:
            raise RuntimeError(f"rigctld rejected {command!r} with RPRT {code}")


class MorseBridge(Protocol):
    def set_speed(self, wpm: int) -> None: ...
    def submit_text(self, text: str, wpm: int) -> None: ...
    def submit_wait(self, seconds: int) -> None: ...
    def abort(self, reason: str) -> None: ...
    def is_busy(self) -> bool: ...
    def close(self) -> None: ...


class RigctldMorseBridge:
    """Ordered queue converting WinKey intent into rigctld commands."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.transport = RigctldTransport(settings.rig_host, settings.rig_port, settings.rig_timeout_seconds)
        self._commands: "queue.Queue[Optional[Tuple[int, str, object]]]" = queue.Queue()
        self._generation_lock = threading.Lock()
        self._generation = 0
        self._wire_lock = threading.Lock()
        self._busy_until = 0.0
        self._busy_lock = threading.Lock()
        self._activity_lock = threading.Lock()
        self._remote_activity = False
        self._worker = threading.Thread(target=self._work, daemon=True, name="RigctldMorse")
        self._worker.start()

    def _current_generation(self) -> int:
        with self._generation_lock:
            return self._generation

    def set_speed(self, wpm: int) -> None:
        self._commands.put((self._current_generation(), "speed", wpm))

    def submit_text(self, text: str, wpm: int) -> None:
        if text:
            self._commands.put((self._current_generation(), "text", (text, wpm)))

    def submit_wait(self, seconds: int) -> None:
        if seconds:
            self._commands.put((self._current_generation(), "wait", seconds))

    def abort(self, reason: str) -> None:
        with self._generation_lock:
            self._generation += 1
        now = time.monotonic()
        with self._busy_lock:
            # N1MM emits CLEAR BUFFER before every function-key message and
            # when it closes the WinKey port.  A stop request is meaningful
            # only while the most recent `b` is still expected to be keyed.
            # Some rigctld/backend combinations do not treat a late
            # stop_morse as a harmless no-op, so never send one after the
            # locally tracked CW interval has elapsed.
            remote_message_active = now < self._busy_until
            self._busy_until = 0.0
        LOG.info("CW abort requested: %s", reason)
        if not self.settings.allow_transmit:
            LOG.info("TX disabled: would send rigctld stop_morse (0xbb)")
            return
        try:
            with self._wire_lock:
                # Do not send a stop command merely because the emulator could
                # not open its COM port, N1MM cleared an empty buffer, or a
                # previous message has already completed. A stop is relevant
                # only after this process has sent an active `b` request.
                with self._activity_lock:
                    if not self._remote_activity or not remote_message_active:
                        self._remote_activity = False
                        LOG.info("CW abort skipped: no active remote message")
                        return
                    self._remote_activity = False
                self.transport.command("0xbb")
        except Exception as error:
            LOG.error("rigctld stop_morse failed: %s", error)

    def is_busy(self) -> bool:
        with self._busy_lock:
            return time.monotonic() < self._busy_until

    def _mark_busy(self, text: str, wpm: int) -> None:
        # A conservative PARIS-word estimate lets N1MM's status poll see BUSY
        # while the remote radio is expected to be sending.  rigctld has no
        # portable query for the internal keyer queue, so this is intentionally
        # only an estimate.
        duration, _ = morse_timing(text, wpm)
        with self._busy_lock:
            self._busy_until = max(self._busy_until, time.monotonic()) + duration

    def _work(self) -> None:
        while True:
            item = self._commands.get()
            if item is None:
                return
            generation, kind, payload = item
            if generation != self._current_generation():
                continue
            try:
                if kind == "speed":
                    self._send_speed(int(payload), generation)
                elif kind == "text":
                    text, wpm = payload  # type: ignore[misc]
                    self._send_text(str(text), int(wpm), generation)
                elif kind == "wait":
                    self._wait(int(payload), generation)
            except Exception as error:
                LOG.error("rigctld %s action failed: %s", kind, error)

    def _wait(self, seconds: int, generation: int) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if generation != self._current_generation():
                return
            time.sleep(min(0.1, deadline - time.monotonic()))

    def _send_speed(self, wpm: int, generation: int) -> None:
        LOG.info("CW speed -> %d WPM", wpm)
        if not self.settings.allow_transmit:
            LOG.info("TX disabled: would send rigctld L KEYSPD %d", wpm)
            return
        with self._wire_lock:
            if generation != self._current_generation():
                return
            LOG.info("rigctld TX -> L KEYSPD %d", wpm)
            self.transport.command(f"L KEYSPD {wpm}")

    def _send_text(self, text: str, wpm: int, generation: int) -> None:
        if self.settings.log_text:
            LOG.info("CW text -> %r", text)
        else:
            LOG.info("CW text queued (%d characters)", len(text))
        if not self.settings.allow_transmit:
            self._mark_busy(text, wpm)
            LOG.info("TX disabled: would send rigctld b <text>")
            return
        with self._wire_lock:
            if generation != self._current_generation():
                return
            self._mark_busy(text, wpm)
            # Once bytes are headed to rigctld, a later Clear/ESC/close must
            # issue 0xbb even if the TCP reply itself is lost.
            with self._activity_lock:
                self._remote_activity = True
            LOG.info("rigctld TX -> b %r", text)
            self.transport.command(f"b {text}")

    def close(self) -> None:
        self.abort("emulator shutdown")
        self._commands.put(None)
        self._worker.join(timeout=2.0)


class WinKeyProtocol:
    """Streaming parser for the WinKey host protocol used by N1MM."""

    # Commands with fixed parameter count.  The individual actions below are
    # deliberately narrow; unsupported keyer features are parsed and logged,
    # never translated into physical keying.
    PARAMETER_COUNTS = {
        0x01: 1, 0x02: 1, 0x03: 1, 0x04: 2, 0x05: 3, 0x06: 1,
        0x09: 1, 0x0B: 1, 0x0C: 1, 0x0D: 1, 0x0E: 1, 0x0F: 15,
        0x10: 1, 0x11: 1, 0x12: 1, 0x14: 1, 0x17: 1, 0x18: 1,
        0x19: 1, 0x1A: 1, 0x1B: 2, 0x1C: 1, 0x1D: 1,
    }

    def __init__(self, settings: Settings, bridge: MorseBridge, write_response: Callable[[bytes], None]):
        self.settings = settings
        self.bridge = bridge
        self.write_response = write_response
        self._opened = False
        self._paused = False
        self._mode = 0
        self._serial_echo_enabled = False
        self._speed = settings.initial_wpm
        self._text = bytearray()
        self._last_text_at: Optional[float] = None
        self._pending: Optional[Tuple[str, int, List[int]]] = None
        self._response_lock = threading.Lock()
        self._activity_generation = 0
        self._host_busy_until = 0.0

    @property
    def opened(self) -> bool:
        return self._opened

    def feed(self, byte: int) -> None:
        if self.settings.protocol_trace:
            printable = repr(chr(byte)) if 0x20 <= byte <= 0x7E else ""
            pending = self._pending[0] if self._pending else "none"
            buffered = self._text.decode("ascii", errors="replace")
            LOG.info(
                "WK RX 0x%02X %s pending=%s text=%r",
                byte,
                printable,
                pending,
                buffered,
            )
        if self._pending is not None:
            self._consume_pending(byte)
            return
        if byte == ADMIN:
            self._flush_text()
            self._pending = ("admin", 1, [])
            return
        if not self._opened:
            LOG.debug("Ignoring byte 0x%02X while host mode is closed", byte)
            return
        if 0x20 <= byte <= 0x7E:
            self._append_text(byte)
            return
        if byte == 0x07:
            self._respond(bytes([SPEED_POT_TAG]))
            return
        if byte == 0x08:
            if self._text:
                if self.settings.protocol_trace:
                    LOG.info("WK backspace removed %r", chr(self._text[-1]))
                self._text.pop()
            return
        if byte == CLEAR_BUFFER:
            self._text.clear()
            self._last_text_at = None
            self._cancel_host_activity()
            self.bridge.abort("WinKey clear buffer")
            return
        if byte == REQUEST_STATUS:
            self._respond(bytes([self._status_byte()]))
            return
        if byte == 0x13 or byte == CANCEL_BUFFERED_SPEED or byte == 0x1F:
            return
        if byte == BUFFER_POINTER:
            self._flush_text()
            self._pending = ("pointer", 1, [])
            return
        count = self.PARAMETER_COUNTS.get(byte)
        if count is not None:
            self._flush_text()
            self._pending = (f"command:{byte}", count, [])
            return
        LOG.warning("Unsupported WinKey command byte 0x%02X ignored", byte)

    def flush_if_idle(self, now: Optional[float] = None) -> None:
        if self._last_text_at is None:
            return
        if now is None:
            now = time.monotonic()
        if now - self._last_text_at >= self.settings.text_gap_seconds:
            self._flush_text()

    def shutdown(self) -> None:
        self._text.clear()
        self._last_text_at = None

    def _append_text(self, byte: int) -> None:
        if self._paused:
            LOG.debug("Discarding text while WinKey is paused")
            return
        self._text.append(byte)
        self._last_text_at = time.monotonic()
        if len(self._text) >= self.settings.max_message_chars:
            self._flush_text()

    def _flush_text(self) -> None:
        if not self._text:
            return
        text = self._text.decode("ascii", errors="replace")
        self._text.clear()
        self._last_text_at = None
        if not self._paused:
            self.bridge.submit_text(text, self._speed)
            self._start_host_activity(text)

    def _consume_pending(self, byte: int) -> None:
        assert self._pending is not None
        kind, count, values = self._pending
        values.append(byte)
        if len(values) < count:
            return
        self._pending = None
        if kind == "admin":
            self._handle_admin(values[0])
        elif kind == "admin_echo":
            self._respond(bytes([values[0]]))
        elif kind == "admin_calibrate":
            LOG.debug("WinKey calibration byte accepted")
        elif kind == "pointer":
            if values[0] in {1, 2}:
                # The input-pointer move commands carry a third byte: the new
                # buffer position.  N1MM emits <16><02><00> before buffered
                # speed/text.  Leaving that position byte in the stream made
                # it look like ADMIN and caused the first CW character to be
                # consumed as a pointer command.
                self._pending = ("pointer_position", 1, [])
            elif values[0] == 3:
                self._pending = ("pointer_nulls", 1, [])
            else:
                LOG.debug("WinKey pointer command %d accepted", values[0])
        elif kind == "pointer_position":
            LOG.debug("WinKey pointer position %d accepted", values[0])
        elif kind == "pointer_nulls":
            LOG.debug("WinKey pointer null padding %d accepted", values[0])
        else:
            self._handle_command(int(kind.split(":", 1)[1]), values)

    def _handle_admin(self, subcommand: int) -> None:
        if subcommand == 0:  # Calibration sequence includes one 0xFF filler byte.
            self._pending = ("admin_calibrate", 1, [])
        elif subcommand == 1:
            self._cancel_host_activity()
            self._opened = False
            self._paused = False
            self._mode = 0
            self._serial_echo_enabled = False
            self._text.clear()
            self.bridge.abort("WinKey reset")
        elif subcommand == 2:
            self._opened = True
            self._paused = False
            LOG.info("WinKey host interface opened")
            self._respond(bytes([self.settings.firmware_revision]))
        elif subcommand == 3:
            LOG.info("WinKey host interface closed")
            self._cancel_host_activity()
            self._opened = False
            self._text.clear()
            self.bridge.abort("WinKey host close")
        elif subcommand == 4:
            self._pending = ("admin_echo", 1, [])
        elif subcommand in {5, 6, 9}:
            self._respond(b"\x00")
        elif subcommand in {10, 11}:
            LOG.debug("WinKey compatibility mode %d selected", subcommand)
        else:
            LOG.debug("Unsupported WinKey admin subcommand %d ignored", subcommand)

    def _handle_command(self, command: int, values: Sequence[int]) -> None:
        if command == SET_SPEED:
            self._set_speed(values[0], "immediate")
        elif command == BUFFERED_SPEED:
            self._set_speed(values[0], "buffered")
        elif command == LOAD_DEFAULTS:
            self._set_mode(values[0], "defaults")
            self._set_speed(values[1], "defaults")
        elif command == 0x0E:
            self._set_mode(values[0], "immediate")
        elif command == SET_PAUSE:
            self._paused = bool(values[0])
            if self._paused:
                self._cancel_host_activity()
                self.bridge.abort("WinKey pause")
            LOG.info("WinKey pause=%s", self._paused)
        elif command == WAIT:
            self.bridge.submit_wait(values[0])
        elif command == MERGE_LETTERS:
            for value in values:
                if 0x20 <= value <= 0x7E:
                    self._append_text(value)
        elif command == KEY_IMMEDIATE:
            LOG.warning("WinKey tune/key-immediate is intentionally not mapped to the radio")
        elif command in {PTT_CONTROL, TIMED_KEY_DOWN}:
            LOG.warning("WinKey command 0x%02X is intentionally not mapped to PTT/CW hardware", command)
        else:
            LOG.debug("WinKey command 0x%02X accepted without a radio mapping", command)

    def _set_speed(self, requested_wpm: int, source: str) -> None:
        # Zero selects the physical speed potentiometer on a real WinKey.  This
        # headless emulator has no pot, so retain the current speed instead.
        if requested_wpm == 0:
            LOG.info("WinKey %s speed=pot ignored; retaining %d WPM", source, self._speed)
            return
        wpm = max(self.settings.min_wpm, min(self.settings.max_wpm, requested_wpm))
        if wpm != requested_wpm:
            LOG.warning("WinKey requested %d WPM; clamped to %d WPM", requested_wpm, wpm)
        self._speed = wpm
        self.bridge.set_speed(wpm)

    def _set_mode(self, mode: int, source: str) -> None:
        self._mode = mode
        self._serial_echo_enabled = bool(mode & 0x04)
        LOG.info(
            "WinKey %s mode=0x%02X serial_echo=%s",
            source,
            mode,
            self._serial_echo_enabled,
        )

    def _start_host_activity(self, text: str) -> None:
        """Return WinKey BUSY/echo/idle events expected by host applications.

        A real WinKey sends a tagged BUSY state while it drains its internal
        buffer, optionally echoes serial characters after they are sent, then
        publishes an idle state.  A remote rigctld keyer has no portable queue
        depth query, so this uses the same conservative PARIS estimate used by
        the bridge.  It prevents N1MM waiting forever for completion.
        """
        now = time.monotonic()
        duration, echoes = morse_timing(text, self._speed)
        was_busy = now < self._host_busy_until
        start = max(now, self._host_busy_until)
        self._host_busy_until = start + duration
        generation = self._activity_generation
        if not was_busy:
            self._respond(bytes([STATUS_TAG | STATUS_BUSY]))
        if self._serial_echo_enabled:
            for character, offset in echoes:
                timer = threading.Timer(
                    max(0.0, start + offset - now),
                    self._echo_serial_character,
                    args=(generation, character),
                )
                timer.daemon = True
                timer.start()
        timer = threading.Timer(
            max(0.0, self._host_busy_until - now),
            self._complete_host_activity,
            args=(generation,),
        )
        timer.daemon = True
        timer.start()

    def _echo_serial_character(self, generation: int, character: str) -> None:
        if generation == self._activity_generation and self._opened:
            self._respond(character.encode("ascii", errors="replace"))

    def _complete_host_activity(self, generation: int) -> None:
        if generation != self._activity_generation or not self._opened:
            return
        remaining = self._host_busy_until - time.monotonic()
        # A preceding batch can complete while a later one remains queued. In
        # that case its echo is still due, but the WinKey must stay BUSY until
        # the last scheduled completion publishes the idle status.
        if remaining > 0.01:
            return
        self._host_busy_until = 0.0
        self._respond(bytes([STATUS_TAG]))

    def _cancel_host_activity(self) -> None:
        was_busy = time.monotonic() < self._host_busy_until
        self._activity_generation += 1
        self._host_busy_until = 0.0
        if was_busy and self._opened:
            self._respond(bytes([STATUS_TAG]))

    def _status_byte(self) -> int:
        busy = self.bridge.is_busy() or time.monotonic() < self._host_busy_until
        return STATUS_TAG | (STATUS_BUSY if busy else 0)

    def _respond(self, payload: bytes) -> None:
        try:
            with self._response_lock:
                self.write_response(payload)
        except Exception as error:
            LOG.error("Could not write WinKey response: %s", error)


def run(settings: Settings) -> int:
    if serial is None:
        LOG.error("pyserial is required. Run with the existing GADX Vector private runtime.")
        return 2
    bridge = RigctldMorseBridge(settings)
    port = None
    try:
        # WinKey compatibility is normally 1200 8N1.  No RTS/DTR outputs are
        # touched: this endpoint is a dedicated virtual pair, never the Vector
        # physical keying port.
        port = serial.Serial(settings.serial_port, settings.serial_baud, timeout=0.02, write_timeout=1)
        protocol = WinKeyProtocol(settings, bridge, port.write)
        LOG.info("WinKey emulator ready on %s @ %d", settings.serial_port, settings.serial_baud)
        LOG.info("rigctld target: %s:%d; transmit=%s", settings.rig_host, settings.rig_port, settings.allow_transmit)
        while True:
            data = port.read(256)
            for value in data:
                protocol.feed(value)
            protocol.flush_if_idle()
    except KeyboardInterrupt:
        LOG.info("Stopped by user")
        return 0
    except Exception as error:
        LOG.error("WinKey emulator failed: %s", error)
        return 2
    finally:
        if "protocol" in locals():
            protocol.shutdown()
        bridge.close()
        if port is not None:
            try:
                port.close()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="GADX isolated WinKey-to-rigctld prototype")
    parser.add_argument("--config", default="winkey.ini", help="path to the independent WinKey INI")
    parser.add_argument("--check", action="store_true", help="validate configuration only; do not open COM or rigctld")
    args = parser.parse_args()
    try:
        settings = load_settings(Path(args.config))
    except Exception as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    if args.check:
        print(
            f"CONFIG_OK port={settings.serial_port} rigctld={settings.rig_host}:{settings.rig_port} "
            f"allow_transmit={settings.allow_transmit}"
        )
        return 0
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run(settings)


if __name__ == "__main__":
    sys.exit(main())
