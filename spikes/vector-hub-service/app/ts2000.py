from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

MODE_CODES = {1: "LSB", 2: "USB", 3: "CW", 4: "FM", 5: "AM", 6: "FSK", 7: "CW-R", 9: "FSK-R"}
MODE_NAMES = {name: code for code, name in MODE_CODES.items()}

@dataclass
class RadioState:
    frequency_a_hz: int = 14_074_000
    frequency_b_hz: int = 7_074_000
    mode_code: int = 2
    rx_vfo: int = 0
    tx_vfo: int = 0
    ptt: bool = False
    tx_band: int = 0
    auto_information: int = 0
    af_gain_main: int = 128
    af_gain_sub: int = 128
    frequency_step: str = "0000"
    rit_xit_offset: str = "+00000"
    rit_on: bool = False
    xit_on: bool = False
    memory_bank: str = "0"
    memory_channel: str = "00"
    scan_status: int = 0
    tone_status: int = 0
    tone_number: str = "00"
    shift_status: int = 0

    @property
    def split(self) -> bool: return self.rx_vfo != self.tx_vfo
    @property
    def active_rx_frequency_hz(self) -> int: return self.frequency_b_hz if self.rx_vfo == 1 else self.frequency_a_hz

class TS2000Emulator:
    """Validated TS-2000 compatibility subset carried from SPIKE 01."""
    MODEL_ID = "019"
    def __init__(self, state: Optional[RadioState] = None) -> None:
        self.state = state or RadioState(); self._rx_buffer = ""; self.unsupported_commands: List[str] = []
    def feed(self, data: str) -> List[str]:
        self._rx_buffer += data; responses=[]
        while ";" in self._rx_buffer:
            raw,self._rx_buffer=self._rx_buffer.split(";",1); raw=raw.strip()
            if not raw: continue
            response=self.handle_command(raw)
            if response: responses.append(response)
        return responses
    def handle_command(self, raw: str) -> Optional[str]:
        command=raw.upper()
        if len(command)<2:return "?;"
        prefix,param=command[:2],command[2:]
        handlers={"ID":self._id,"FA":self._fa,"FB":self._fb,"MD":self._md,"FR":self._fr,"FT":self._ft,"TX":self._tx,"RX":self._rx,"IF":self._if,"AI":self._ai,"AG":self._ag}
        handler=handlers.get(prefix)
        if handler is None:self.unsupported_commands.append(command);return None
        try:return handler(param)
        except (ValueError,IndexError):return "?;"
    def _id(self,p):
        if p:raise ValueError();return f"ID{self.MODEL_ID};"
    def _fa(self,p):
        if not p:return f"FA{self.state.frequency_a_hz:011d};"
        self.state.frequency_a_hz=self._freq(p);return ""
    def _fb(self,p):
        if not p:return f"FB{self.state.frequency_b_hz:011d};"
        self.state.frequency_b_hz=self._freq(p);return ""
    def _md(self,p):
        if not p:return f"MD{self.state.mode_code};"
        if len(p)!=1 or not p.isdigit() or int(p) not in MODE_CODES:raise ValueError()
        self.state.mode_code=int(p);return ""
    def _fr(self,p):
        if not p:return f"FR{self.state.rx_vfo};"
        self.state.rx_vfo=self._vfo(p);return ""
    def _ft(self,p):
        if not p:return f"FT{self.state.tx_vfo};"
        self.state.tx_vfo=self._vfo(p);return ""
    def _tx(self,p):
        if p not in ("","0","1"):raise ValueError()
        self.state.tx_band=int(p or "0");self.state.ptt=True;return ""
    def _rx(self,p):
        if p:raise ValueError()
        self.state.ptt=False;return ""
    def _ai(self,p):
        if not p:return f"AI{self.state.auto_information};"
        if p not in ("0","2"):raise ValueError()
        self.state.auto_information=int(p);return ""
    def _ag(self,p):
        if len(p)==1 and p in ("0","1"):
            g=self.state.af_gain_main if p=="0" else self.state.af_gain_sub;return f"AG{p}{g:03d};"
        if len(p)==4 and p[0] in ("0","1") and p[1:].isdigit() and 0<=int(p[1:])<=255:
            if p[0]=="0":self.state.af_gain_main=int(p[1:])
            else:self.state.af_gain_sub=int(p[1:])
            return ""
        raise ValueError()
    def _if(self,p):
        if p:raise ValueError()
        s=self.state; current=s.tx_vfo if s.ptt else s.rx_vfo
        r=(f"IF{s.active_rx_frequency_hz:011d}{s.frequency_step}{s.rit_xit_offset}{1 if s.rit_on else 0}{1 if s.xit_on else 0}{s.memory_bank}{s.memory_channel}{1 if s.ptt else 0}{s.mode_code}{current}{s.scan_status}{1 if s.split else 0}{s.tone_status}{s.tone_number}{s.shift_status};")
        if len(r)!=38:raise ValueError()
        return r
    @staticmethod
    def _freq(p):
        if len(p)!=11 or not p.isdigit():raise ValueError()
        return int(p)
    @staticmethod
    def _vfo(p):
        if p not in ("0","1"):raise ValueError()
        return int(p)
