from __future__ import annotations

import argparse
import logging
import sys

import serial

from ts2000 import TS2000Emulator


LOG = logging.getLogger("gadX.vector.ts2000-spike")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GADX Vector SPIKE: minimal Kenwood TS-2000 CAT emulator"
    )
    parser.add_argument("--port", required=True, help="Serial port opened by the emulator, e.g. COM18")
    parser.add_argument("--baud", type=int, default=19200, help="Serial speed (default: 19200)")
    parser.add_argument("--timeout", type=float, default=0.1, help="Serial read timeout in seconds")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    radio = TS2000Emulator()

    LOG.info("Opening %s at %d baud, 8N1", args.port, args.baud)
    LOG.info("Initial state: %s", radio.describe_state())

    try:
        with serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=args.timeout,
            # com0com may temporarily block writes while the peer side is
            # switching/opening the paired COM port. A finite write timeout
            # caused the SPIKE to abort during N1MM initialization. Blocking
            # writes are preferable for this isolated laboratory transport.
            write_timeout=None,
        ) as cat_port:
            LOG.info("TS-2000 emulator ready")

            while True:
                data = cat_port.read(4096)
                if not data:
                    continue

                text = data.decode("ascii", errors="replace")
                LOG.debug("CAT RX raw: %r", text)

                before = radio.describe_state()
                responses = radio.feed(text)
                after = radio.describe_state()

                if after != before:
                    LOG.info("State changed: %s", after)

                for response in responses:
                    payload = response.encode("ascii")
                    LOG.debug("CAT TX: %s", response)
                    written = cat_port.write(payload)
                    if written != len(payload):
                        LOG.warning(
                            "Partial CAT write: %d/%d bytes for %r",
                            written,
                            len(payload),
                            response,
                        )

                if radio.unsupported_commands:
                    while radio.unsupported_commands:
                        unknown = radio.unsupported_commands.pop(0)
                        LOG.warning("UNSUPPORTED CAT command: %s;", unknown)

    except KeyboardInterrupt:
        LOG.info("Stopped by user")
        return 0
    except serial.SerialException as exc:
        LOG.error("Serial error: %s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
