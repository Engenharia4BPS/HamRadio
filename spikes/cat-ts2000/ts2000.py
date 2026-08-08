from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


MODE_CODES = {
    1: "LSB",
    2: "USB",
    3: "CW",
    4: "FM",
    5: "AM",
    6: "FSK",
    7: "CW-R",
    9: "FSK-R",
}

MODE_NAMES = {name: code for code, name in MODE_CODES.items()}


@dataclass
class RadioState:
    frequency_a_hz: int = 14_074_000
    frequency_b_hz: int = 7_074_000
    mode_code: int = 2  # USB
    rx_vfo: int = 0  # 0=A, 1=B
    tx_vfo: int = 0  # 0=A, 1=B
    ptt: bool = False

    @property
    def split(self) -> bool:
        return self.rx_vfo != self.tx_vfo

    @property
    def active_rx_frequency_hz(self) -> int:
        return self.frequency_b_hz if self.rx_vfo == 1 else self.frequency_a_hz

    @property
    def active_tx_frequency_hz(self) -> int:
        return self.frequency_b_hz if self.tx_vfo == 1 else self.frequency_a_hz


class TS2000Emulator:
    """Minimal Kenwood TS-2000 CAT emulator for the GADX Vector SPIKE.

    This is deliberately not a full TS-2000 implementation. It implements
    only the subset required to begin compatibility testing with N1MM/DXLog.
    Unknown commands are surfaced to the caller so real logger traffic can be
    captured and the compatibility matrix can be expanded empirically.
    """

    MODEL_ID = "019"

    def __init__(self, state: Optional[RadioState] = None) -> None:
        self.state = state or RadioState()
        self._rx_buffer = ""
        self.unsupported_commands: List[str] = []

    def feed(self, data: str) -> List[str]:
        """Feed arbitrary serial text and return zero or more CAT responses.

        CAT commands are terminated by ';'. The method tolerates fragmented
        serial reads and multiple commands in one read.
        """
        self._rx_buffer += data
        responses: List[str] = []

        while ";" in self._rx_buffer:
            raw, self._rx_buffer = self._rx_buffer.split(";", 1)
            raw = raw.strip()
            if not raw:
                continue

            response = self.handle_command(raw)
            if response:
                responses.append(response)

        return responses

    def handle_command(self, raw: str) -> Optional[str]:
        command = raw.upper()

        if len(command) < 2:
            return "?;"

        prefix = command[:2]
        param = command[2:]

        handlers = {
            "ID": self._id,
            "FA": self._fa,
            "FB": self._fb,
            "MD": self._md,
            "FR": self._fr,
            "FT": self._ft,
            "TX": self._tx,
            "RX": self._rx,
        }

        handler = handlers.get(prefix)
        if handler is None:
            self.unsupported_commands.append(command)
            return None

        try:
            return handler(param)
        except (ValueError, IndexError):
            return "?;"

    def _id(self, param: str) -> str:
        if param:
            return "?;"
        return f"ID{self.MODEL_ID};"

    def _fa(self, param: str) -> str:
        if not param:
            return f"FA{self.state.frequency_a_hz:011d};"
        self.state.frequency_a_hz = self._parse_frequency(param)
        return ""

    def _fb(self, param: str) -> str:
        if not param:
            return f"FB{self.state.frequency_b_hz:011d};"
        self.state.frequency_b_hz = self._parse_frequency(param)
        return ""

    def _md(self, param: str) -> str:
        if not param:
            return f"MD{self.state.mode_code};"

        if len(param) != 1:
            raise ValueError("invalid MD parameter")

        code = int(param)
        if code not in MODE_CODES:
            raise ValueError("unsupported mode")

        self.state.mode_code = code
        return ""

    def _fr(self, param: str) -> str:
        if not param:
            return f"FR{self.state.rx_vfo};"
        self.state.rx_vfo = self._parse_vfo(param)
        return ""

    def _ft(self, param: str) -> str:
        if not param:
            return f"FT{self.state.tx_vfo};"
        self.state.tx_vfo = self._parse_vfo(param)
        return ""

    def _tx(self, param: str) -> str:
        # TS-2000 TX is primarily a set command. Some software may send TX0.
        if param not in ("", "0"):
            raise ValueError("unsupported TX parameter")
        self.state.ptt = True
        return ""

    def _rx(self, param: str) -> str:
        if param:
            raise ValueError("RX has no parameter in this spike")
        self.state.ptt = False
        return ""

    @staticmethod
    def _parse_frequency(param: str) -> int:
        if len(param) != 11 or not param.isdigit():
            raise ValueError("frequency must contain exactly 11 digits")
        value = int(param)
        if value < 0 or value > 99_999_999_999:
            raise ValueError("frequency out of range")
        return value

    @staticmethod
    def _parse_vfo(param: str) -> int:
        if param not in ("0", "1"):
            raise ValueError("spike currently supports only VFO A/B")
        return int(param)

    def describe_state(self) -> str:
        mode = MODE_CODES.get(self.state.mode_code, f"MODE-{self.state.mode_code}")
        return (
            f"FA={self.state.frequency_a_hz}Hz "
            f"FB={self.state.frequency_b_hz}Hz "
            f"RX=VFO-{'B' if self.state.rx_vfo else 'A'} "
            f"TX=VFO-{'B' if self.state.tx_vfo else 'A'} "
            f"MODE={mode} PTT={'ON' if self.state.ptt else 'OFF'} "
            f"SPLIT={'ON' if self.state.split else 'OFF'}"
        )
