import socketserver
import sys
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from winkey_emulator import RigctldMorseBridge, RigctldTransport, Settings


class RecordingRigctld(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, response=b"RPRT 0\n"):
        self.commands = []
        self.response = response
        super().__init__(("127.0.0.1", 0), RecordingHandler)


class RecordingHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = bytearray()
        while not data.endswith(b"\n"):
            block = self.request.recv(1024)
            if not block:
                return
            data.extend(block)
        self.server.commands.append(data.decode("ascii"))
        self.request.sendall(self.server.response)


class RigctldTransportTests(unittest.TestCase):
    def setUp(self):
        self.server = RecordingRigctld()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.client = RigctldTransport(host, port, 1)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def test_uses_plain_rigctld_commands_requested_by_the_spike(self):
        self.client.command("L KEYSPD 32")
        self.client.command("b CQ TEST PY5XT")
        self.client.command("0xbb")
        self.assertEqual(
            self.server.commands,
            ["L KEYSPD 32\n", "b CQ TEST PY5XT\n", "0xbb\n"],
        )

    def test_rejects_nonzero_rprt(self):
        self.server.response = b"RPRT -1\n"
        with self.assertRaisesRegex(RuntimeError, "RPRT -1"):
            self.client.command("b TEST")


class RigctldMorseBridgeTests(unittest.TestCase):
    def setUp(self):
        self.server = RecordingRigctld()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.bridge = RigctldMorseBridge(
            Settings(
                serial_port="COM140", serial_baud=1200, text_gap_seconds=0.015,
                max_message_chars=240, firmware_revision=23, initial_wpm=28,
                min_wpm=5, max_wpm=99, rig_host=host, rig_port=port,
                rig_timeout_seconds=1, allow_transmit=True, log_text=True, protocol_trace=False,
            )
        )

    def tearDown(self):
        self.bridge.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def wait_for_commands(self, count):
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            if len(self.server.commands) >= count:
                return
            time.sleep(0.01)
        self.fail(f"expected {count} rigctld commands, got {self.server.commands!r}")

    def test_abort_only_stops_messages_this_process_has_sent(self):
        self.bridge.abort("empty buffer")
        time.sleep(0.05)
        self.assertEqual(self.server.commands, [])

        self.bridge.set_speed(28)
        self.bridge.submit_text("TEST", 28)
        self.wait_for_commands(2)
        self.bridge.abort("test abort")
        self.wait_for_commands(3)

        self.assertEqual(self.server.commands, ["L KEYSPD 28\n", "b TEST\n", "0xbb\n"])

    def test_abort_does_not_stop_a_message_that_has_already_completed(self):
        self.bridge.submit_text("E", 28)
        self.wait_for_commands(1)

        # Simulate an N1MM CLEAR BUFFER or host close after the estimated CW
        # interval.  It must not issue a stale 0xbb to the rigctld backend.
        with self.bridge._busy_lock:
            self.bridge._busy_until = time.monotonic() - 0.01
        self.bridge.abort("late clear buffer")
        time.sleep(0.05)

        self.assertEqual(self.server.commands, ["b E\n"])


if __name__ == "__main__":
    unittest.main()
