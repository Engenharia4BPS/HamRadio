from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


# Canonical source for CAT behavior implemented in this SPIKE:
# Kenwood TS-2000/TS-2000X/TS-B2000 Instruction Manual B62-1221-70,
# Chapter 21 Appendix, "Computer Control" and "PC Control Command Tables"
# (manual pages 113-141).
#
# Important: this remains a deliberately small compatibility emulator.  The
# official manual defines many more commands; we implement only the subset that
# is required/observed by N1MM and DXLog, but fields and replies implemented
# here should follow the Kenwood tables rather than guessed formats.

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

    # Kenwood FR/FT P1 values used in this SPIKE:
    # 0=VFO A, 1=VFO B.  The real TS-2000 also defines 2=M.CH and 3=CALL.
    rx_vfo: int = 0
    tx_vfo: int = 0

    ptt: bool = False
    tx_band: int = 0  # TX command P1: 0=main, 1=sub-receiver

    # AI P1 according to the official command table:
    # 0=OFF, 2=Extended AI ON.  AI1/AI3 are not supported by TS-2000.
    auto_information: int = 0

    # AG command: separate 000..255 values for main and sub receiver.
    af_gain_main: int = 128
    af_gain_sub: int = 128

    # Ancillary fields needed to build the official fixed-position IF answer.
    frequency_step: str = "0000"       # IF P2, 4 characters
    rit_xit_offset: str = "+00000"     # IF P3, signed 6 characters
    rit_on: bool = False                # IF P4
    xit_on: bool = False                # IF P5
    memory_bank: str = "0"             # IF P6, one character
    memory_channel: str = "00"         # IF P7, two characters
    scan_status: int = 0                # IF P11
    tone_status: int = 0                # IF P13: 0=OFF,1=TONE,2=CTCSS,3=DCS
    tone_number: str = "00"            # IF P14, two characters
    shift_status: int = 0               # IF P15, see OS command

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

    Canonical protocol reference: Kenwood manual B62-1221-70, Chapter 21.

    This is not intended to clone the complete TS-2000 firmware.  It implements
    the smallest standards-conformant subset needed for compatibility testing
    with N1MM/DXLog. Unknown commands are captured so the subset can be expanded
    empirically without inventing behavior.
    """

    MODEL_ID = "019"  # Official ID response for TS-2000.

    def __init__(self, state: Optional[RadioState] = None) -> None:
        self.state = state or RadioState()
        self._rx_buffer = ""
        self.unsupported_commands: List[str] = []

    def feed(self, data: str) -> List[str]:
        """Feed arbitrary serial text and return zero or more CAT replies.

        Kenwood commands are terminated by ';'.  Serial reads may be fragmented
        or may contain several complete commands at once.
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
            # Official Computer Control section defines ?; as command error.
            return "?;"

    # ------------------------------------------------------------------
    # Official command subset
    # ------------------------------------------------------------------

    def _id(self, param: str) -> str:
        """ID; -> ID019;  (TS-2000 transceiver ID)."""
        if param:
            raise ValueError("ID is read-only")
        return f"ID{self.MODEL_ID};"

    def _fa(self, param: str) -> str:
        """FA: read/set VFO A frequency, 11-digit Hz field."""
        if not param:
            return f"FA{self.state.frequency_a_hz:011d};"
        self.state.frequency_a_hz = self._parse_frequency(param)
        return ""

    def _fb(self, param: str) -> str:
        """FB: read/set VFO B frequency, 11-digit Hz field."""
        if not param:
            return f"FB{self.state.frequency_b_hz:011d};"
        self.state.frequency_b_hz = self._parse_frequency(param)
        return ""

    def _md(self, param: str) -> str:
        """MD: read/set operating mode according to Kenwood P1 codes."""
        if not param:
            return f"MD{self.state.mode_code};"
        if len(param) != 1 or not param.isdigit():
            raise ValueError("invalid MD parameter")
        code = int(param)
        if code not in MODE_CODES:
            raise ValueError("reserved/unsupported mode")
        self.state.mode_code = code
        return ""

    def _fr(self, param: str) -> str:
        """FR: select/read receiver VFO/M.CH/CALL.

        The official table allows 0=A, 1=B, 2=M.CH, 3=CALL.  The SPIKE state
        model currently emulates VFO A/B only, therefore 2/3 are rejected until
        there is a corresponding memory/call-channel model.
        """
        if not param:
            return f"FR{self.state.rx_vfo};"
        self.state.rx_vfo = self._parse_vfo(param)
        return ""

    def _ft(self, param: str) -> str:
        """FT: select/read transmitter VFO/M.CH/CALL.

        As with FR, this SPIKE currently models only VFO A/B.
        """
        if not param:
            return f"FT{self.state.tx_vfo};"
        self.state.tx_vfo = self._parse_vfo(param)
        return ""

    def _tx(self, param: str) -> str:
        """TX: place the transceiver in transmit mode.

        Official form is TXP1; where P1=0 main band or P1=1 sub-receiver.
        For compatibility discovery we also tolerate bare TX; as TX0 because
        some logger implementations may use the legacy shorthand.
        """
        if param == "":
            tx_band = 0
        elif param in ("0", "1"):
            tx_band = int(param)
        else:
            raise ValueError("TX expects P1=0 or 1")

        self.state.tx_band = tx_band
        self.state.ptt = True
        return ""

    def _rx(self, param: str) -> str:
        """RX; returns the transceiver to receive mode."""
        if param:
            raise ValueError("RX has no set parameter")
        self.state.ptt = False
        return ""

    def _ai(self, param: str) -> str:
        """AI: Auto Information; TS-2000 supports P1=0 and P1=2."""
        if not param:
            return f"AI{self.state.auto_information};"
        if param not in ("0", "2"):
            raise ValueError("TS-2000 supports AI0 or AI2")
        self.state.auto_information = int(param)
        return ""

    def _ag(self, param: str) -> str:
        """AG: AF gain.

        Official forms:
          AGP1;       read, P1 0=main / 1=sub
          AGP1PPP;    set, gain 000..255
        """
        if len(param) == 1 and param in ("0", "1"):
            gain = self.state.af_gain_main if param == "0" else self.state.af_gain_sub
            return f"AG{param}{gain:03d};"

        if len(param) == 4 and param[0] in ("0", "1") and param[1:].isdigit():
            gain = int(param[1:])
            if not 0 <= gain <= 255:
                raise ValueError("AF gain out of range")
            if param[0] == "0":
                self.state.af_gain_main = gain
            else:
                self.state.af_gain_sub = gain
            return ""

        raise ValueError("AG expects receiver selector and 000..255 gain")

    def _if(self, param: str) -> str:
        """IF; -> fixed-position transceiver status reply.

        Field layout follows the official B62-1221-70 command table:
          P1  frequency, 11-digit Hz
          P2  frequency step, 4 chars
          P3  RIT/XIT offset, signed 6 chars
          P4  RIT status
          P5  XIT status
          P6  memory bank, 1 char
          P7  memory channel, 2 chars
          P8  RX/TX status
          P9  operating mode (MD code)
          P10 receiver/transmitter VFO selector (FR/FT semantics)
          P11 scan status
          P12 simplex/split
          P13 tone/CTCSS/DCS status
          P14 tone number, 2 chars
          P15 shift status

        Result length including 'IF' and ';' is 38 characters.
        """
        if param:
            raise ValueError("IF is read-only")

        self._validate_if_fields()

        # P10 is the current VFO relevant to the operating direction.  While in
        # RX it follows FR; during TX it follows FT.
        current_vfo = self.state.tx_vfo if self.state.ptt else self.state.rx_vfo

        response = (
            f"IF{self.state.active_rx_frequency_hz:011d}"
            f"{self.state.frequency_step}"
            f"{self.state.rit_xit_offset}"
            f"{1 if self.state.rit_on else 0}"
            f"{1 if self.state.xit_on else 0}"
            f"{self.state.memory_bank}"
            f"{self.state.memory_channel}"
            f"{1 if self.state.ptt else 0}"
            f"{self.state.mode_code}"
            f"{current_vfo}"
            f"{self.state.scan_status}"
            f"{1 if self.state.split else 0}"
            f"{self.state.tone_status}"
            f"{self.state.tone_number}"
            f"{self.state.shift_status};"
        )

        if len(response) != 38:
            raise ValueError(f"invalid IF response length: {len(response)}")
        return response

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_frequency(param: str) -> int:
        if len(param) != 11 or not param.isdigit():
            raise ValueError("frequency must contain exactly 11 digits")
        return int(param)

    @staticmethod
    def _parse_vfo(param: str) -> int:
        if param not in ("0", "1"):
            raise ValueError("SPIKE currently models only VFO A/B")
        return int(param)

    def _validate_if_fields(self) -> None:
        if len(self.state.frequency_step) != 4:
            raise ValueError("IF P2 frequency_step must be 4 characters")
        if len(self.state.rit_xit_offset) != 6:
            raise ValueError("IF P3 rit_xit_offset must be 6 characters")
        if len(self.state.memory_bank) != 1:
            raise ValueError("IF P6 memory_bank must be 1 character")
        if len(self.state.memory_channel) != 2:
            raise ValueError("IF P7 memory_channel must be 2 characters")
        if len(self.state.tone_number) != 2:
            raise ValueError("IF P14 tone_number must be 2 characters")

    def describe_state(self) -> str:
        mode = MODE_CODES.get(self.state.mode_code, f"MODE-{self.state.mode_code}")
        return (
            f"FA={self.state.frequency_a_hz}Hz "
            f"FB={self.state.frequency_b_hz}Hz "
            f"RX=VFO-{'B' if self.state.rx_vfo else 'A'} "
            f"TX=VFO-{'B' if self.state.tx_vfo else 'A'} "
            f"MODE={mode} PTT={'ON' if self.state.ptt else 'OFF'} "
            f"SPLIT={'ON' if self.state.split else 'OFF'} "
            f"AI={self.state.auto_information} "
            f"AG0={self.state.af_gain_main} AG1={self.state.af_gain_sub}"
        )
