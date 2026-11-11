import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from winkey_emulator import Settings, WinKeyProtocol, morse_timing


def settings(**overrides):
    values = dict(
        serial_port="COM140", serial_baud=1200, text_gap_seconds=0.015,
        max_message_chars=240, firmware_revision=23, initial_wpm=28,
        min_wpm=5, max_wpm=99, rig_host="127.0.0.1", rig_port=4532,
        rig_timeout_seconds=1.5, abort_mode="none", allow_transmit=False, log_text=True, protocol_trace=False,
    )
    values.update(overrides)
    return Settings(**values)


class RecordingBridge:
    def __init__(self):
        self.actions = []
        self.busy = False

    def set_speed(self, wpm):
        self.actions.append(("speed", wpm))

    def submit_text(self, text, wpm):
        self.actions.append(("text", text, wpm))

    def submit_wait(self, seconds):
        self.actions.append(("wait", seconds))

    def abort(self, reason):
        self.actions.append(("abort", reason))

    def is_busy(self):
        return self.busy

    def close(self):
        pass


class WinKeyProtocolTests(unittest.TestCase):
    def make_protocol(self):
        self.bridge = RecordingBridge()
        self.responses = []
        return WinKeyProtocol(settings(), self.bridge, self.responses.append)

    def open_host(self, protocol):
        protocol.feed(0x00)
        protocol.feed(0x02)
        self.assertEqual(self.responses[-1], bytes([23]))

    def test_echo_then_open_handshake(self):
        protocol = self.make_protocol()
        protocol.feed(0x00)
        protocol.feed(0x04)
        protocol.feed(0x55)
        self.assertEqual(self.responses, [b"\x55"])
        self.open_host(protocol)
        self.assertTrue(protocol.opened)

    def test_ascii_batch_becomes_one_morse_request(self):
        protocol = self.make_protocol()
        self.open_host(protocol)
        for byte in b"CQ TEST PY5XT":
            protocol.feed(byte)
        protocol.flush_if_idle()
        # First call happens immediately, so advance beyond the configured
        # inactivity window for the deterministic unit test.
        import time
        protocol.flush_if_idle(now=time.monotonic() + 1)
        self.assertEqual(self.bridge.actions, [("text", "CQ TEST PY5XT", 28)])

    def test_speed_is_clamped_and_forwarded(self):
        protocol = self.make_protocol()
        self.open_host(protocol)
        protocol.feed(0x02)
        protocol.feed(120)
        self.assertEqual(self.bridge.actions, [("speed", 99)])

    def test_clear_buffer_aborts_and_discards_pending_text(self):
        protocol = self.make_protocol()
        self.open_host(protocol)
        for byte in b"CQ":
            protocol.feed(byte)
        protocol.feed(0x0A)
        protocol.flush_if_idle(now=10.0)
        self.assertEqual(self.bridge.actions, [("abort", "WinKey clear buffer")])

    def test_status_uses_winkey_busy_bit(self):
        protocol = self.make_protocol()
        self.open_host(protocol)
        self.bridge.busy = True
        protocol.feed(0x15)
        self.assertEqual(self.responses[-1], b"\xC4")

    def test_defaults_speed_and_wait_are_parsed(self):
        protocol = self.make_protocol()
        self.open_host(protocol)
        protocol.feed(0x0F)
        for value in [0, 32] + [0] * 13:
            protocol.feed(value)
        protocol.feed(0x1A)
        protocol.feed(2)
        self.assertEqual(self.bridge.actions, [("speed", 32), ("wait", 2)])

    def test_serial_echo_and_idle_status_complete_a_message(self):
        protocol = self.make_protocol()
        self.open_host(protocol)
        protocol.feed(0x0E)
        protocol.feed(0x04)  # WK2 serial echo enabled.
        for byte in b"TU":
            protocol.feed(byte)
        protocol.flush_if_idle(now=time.monotonic() + 1)
        # "TU" at 28 WPM takes roughly 0.56 s. Leave scheduler headroom for
        # timer delivery on a busy Windows host.
        time.sleep(1.0)
        self.assertIn(b"\xC4", self.responses)
        self.assertIn(b"T", self.responses)
        self.assertIn(b"U", self.responses)
        self.assertEqual(self.responses[-1], b"\xC0")

    def test_morse_timing_uses_paris_dit_units(self):
        duration, echoes = morse_timing("TU", 20)
        self.assertAlmostEqual(duration, 0.78, places=2)
        self.assertEqual(echoes, [("T", 0.18), ("U", 0.78)])

    def test_n1mm_pointer_append_keeps_the_first_cw_character(self):
        protocol = self.make_protocol()
        self.open_host(protocol)
        # Captured from N1MM: clear, reset pointer, append at position zero,
        # buffered 22 WPM, then the F3 text "TU".
        for byte in (0x0A, 0x16, 0x00, 0x16, 0x02, 0x00, 0x1C, 22, ord("T"), ord("U")):
            protocol.feed(byte)
        protocol.flush_if_idle(now=time.monotonic() + 1)
        self.assertEqual(
            self.bridge.actions,
            [("abort", "WinKey clear buffer"), ("speed", 22), ("text", "TU", 22)],
        )


if __name__ == "__main__":
    unittest.main()
