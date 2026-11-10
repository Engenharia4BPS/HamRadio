"""Local, non-transmitting rigctld endpoint for WinKey diagnosis.

It accepts one-line rigctld commands, prints the exact received line and
returns ``RPRT 0``. Bind only to 127.0.0.1; it never communicates with a rig.
"""

from __future__ import annotations

import argparse
import socketserver
import sys
from datetime import datetime


class Recorder(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        received = bytearray()
        while not received.endswith(b"\n"):
            block = self.request.recv(1024)
            if not block:
                return
            received.extend(block)
        text = received.decode("ascii", errors="replace").rstrip("\r\n")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"{timestamp} RIGCTL RX -> {text!r}", flush=True)
        self.request.sendall(b"RPRT 0\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Local non-transmitting rigctld recorder")
    parser.add_argument("--port", type=int, default=45330)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    with Recorder(("127.0.0.1", args.port), Handler) as server:
        print(f"Rigctld recorder ready on 127.0.0.1:{args.port}; no radio is connected.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Recorder stopped.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
