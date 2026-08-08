from __future__ import annotations

import argparse
import logging
import sys
import time

import serial


LOG = logging.getLogger("gadX.vector.keying-spike")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "GADX Vector SPIKE: monitor modem-control lines from a virtual COM "
            "pair for N1MM CW/PTT testing"
        )
    )
    parser.add_argument(
        "--port",
        required=True,
        help="Serial port opened by the Vector side, e.g. COM32",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=19200,
        help="Serial speed (default: 19200; data speed is irrelevant for RTS/DTR monitoring)",
    )
    parser.add_argument(
        "--poll-ms",
        type=float,
        default=2.0,
        help="Polling interval for modem lines in milliseconds (default: 2.0)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def state_text(ptt: bool, cw: bool, cts: bool, dsr: bool, dcd: bool) -> str:
    return (
        f"PTT={'ON' if ptt else 'OFF'} "
        f"CW={'ON' if cw else 'OFF'} "
        f"CTS={int(cts)} DSR={int(dsr)} DCD={int(dcd)}"
    )


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    poll_seconds = max(args.poll_ms, 0.1) / 1000.0

    LOG.info("Opening %s at %d baud, 8N1", args.port, args.baud)
    LOG.info("Expected com0com mapping: remote RTS -> local CTS; remote DTR -> local DSR/DCD")
    LOG.info("Expected N1MM mapping for this SPIKE: DTR=PTT, RTS=CW")

    try:
        with serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0,
            write_timeout=None,
        ) as key_port:
            # Do not intentionally drive the local output-control lines.
            key_port.dtr = False
            key_port.rts = False

            previous_cts = bool(key_port.cts)
            previous_dsr = bool(key_port.dsr)
            previous_dcd = bool(key_port.cd)

            # With com0com defaults used in the laboratory:
            # COM31 RTS is observed on COM32 CTS  -> CW
            # COM31 DTR is observed on COM32 DSR/DCD -> PTT
            previous_cw = previous_cts
            previous_ptt = previous_dsr or previous_dcd

            cw_started = time.perf_counter() if previous_cw else None
            ptt_started = time.perf_counter() if previous_ptt else None

            LOG.info(
                "Initial state: %s",
                state_text(
                    previous_ptt,
                    previous_cw,
                    previous_cts,
                    previous_dsr,
                    previous_dcd,
                ),
            )
            LOG.info("Keying monitor ready")

            while True:
                cts = bool(key_port.cts)
                dsr = bool(key_port.dsr)
                dcd = bool(key_port.cd)

                cw = cts
                ptt = dsr or dcd

                now = time.perf_counter()

                if ptt != previous_ptt:
                    if ptt:
                        ptt_started = now
                        LOG.info("PTT ON  (remote DTR asserted)")
                    else:
                        duration_ms = (
                            (now - ptt_started) * 1000.0 if ptt_started is not None else 0.0
                        )
                        LOG.info("PTT OFF (duration %.1f ms)", duration_ms)
                        ptt_started = None

                if cw != previous_cw:
                    if cw:
                        cw_started = now
                        LOG.info("CW  ON  (remote RTS asserted)")
                    else:
                        duration_ms = (
                            (now - cw_started) * 1000.0 if cw_started is not None else 0.0
                        )
                        LOG.info("CW  OFF (pulse %.1f ms)", duration_ms)
                        cw_started = None

                if (
                    cts != previous_cts
                    or dsr != previous_dsr
                    or dcd != previous_dcd
                ):
                    LOG.debug(
                        "MODEM %s",
                        state_text(ptt, cw, cts, dsr, dcd),
                    )

                previous_cts = cts
                previous_dsr = dsr
                previous_dcd = dcd
                previous_cw = cw
                previous_ptt = ptt

                time.sleep(poll_seconds)

    except KeyboardInterrupt:
        LOG.info("Stopped by user")
        return 0
    except (serial.SerialException, OSError) as exc:
        LOG.error("Serial error: %s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
