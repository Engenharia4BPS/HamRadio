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
    auto_information: int = 0  # TS-2000: 0=OFF, 2=extended AI ON
    af_gain_main: int = 128  # 000..255

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
    only the subset observed/required during compatibility testing with
    N1MM/DXLog. Unknown commands are surfaced to the caller so logger traffic
    can expand the compatibility matrix empirically.
    """

    MODEL_ID = "019"

    def __init__(self, state: Optional[RadioState] = None) -> None:
        self.state = state or RadioState()
        self._rx_buffer = ""
        self.unsupported_commands: List[str] = []

    def feed(self, data: str) -> List[str]:
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
            "IF": self._if,
            "AI": self._ai,
            "AG": self._ag,
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
        if param not in ("", "0"):
            raise ValueError("unsupported TX parameter")
        self.state.ptt = True
        return ""

    def _rx(self, param: str) -> str:
        if param:
            raise ValueError("RX has no parameter in this spike")
        self.state.ptt = False
        return ""

    def _ai(self, param: str) -> str:
        # TS-2000 supports AI0 (OFF) and AI2 (extended AI ON).
        if not param:
            return f"AI{self.state.auto_information};"
        if param not in ("0", "2"):
            raise ValueError("TS-2000 supports AI0 or AI2")
        self.state.auto_information = int(param)
        return ""

    def _ag(self, param: str) -> str:
        # AG P1 P2: P1=0 main transceiver, P2=000..255.
        # N1MM was observed polling with AG0;.
        if param == "0":
            return f"AG0{self.state.af_gain_main:03d};"
        if len(param) == 4 and param[0] == "0" and param[1:].isdigit():
            gain = int(param[1:])
            if not 0 <= gain <= 255:
                raise ValueError("AF gain out of range")
            self.state.af_gain_main = gain
            return ""
        raise ValueError("unsupported AG parameter")

    def _if(self, param: str) -> str:
        if param:
            raise ValueError("IF is read-only")

        # TS-2000 IF answer fields (Kenwood PC command table):
        # frequency(11), step(4), RIT/XIT offset(6), RIT(1), XIT(1),
        # memory bank/channel(3), RX/TX(1), mode(1), VFO(1), scan(1),
        # split(1), tone state(1), tone number(2), shift(1).
        # For the spike, unsupported ancillary features are reported inactive.
        frequency = self.state.active_rx_frequency_hz
        step = "0000"
        rit_xit = "+00000"
        rit = "0"
        xit = "0"
        memory = "000"
        rx_tx = "1" if self.state.ptt else "0"
        mode = str(self.state.mode_code)
        vfo = str(self.state.rx_vfo)
        scan = "0"
        split = "1" if self.state.split else "0"
        tone_state = "0"
        tone_number = "00"
        shift = "0"

        return (
            f"IF{frequency:011d}{step}{rit_xit}{rit}{xit}{memory}"
            f"{rx_tx}{mode}{vfo}{scan}{split}{tone_state}{tone_number}{shift};"
        )

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
            f"SPLIT={'ON' if self.state.split else 'OFF'} "
            f"AI={self.state.auto_information} AG0={self.state.af_gain_main}"
        )
