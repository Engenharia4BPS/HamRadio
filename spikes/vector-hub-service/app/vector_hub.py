from __future__ import annotations

import argparse, configparser, logging, queue, socket, sys, threading, time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import serial
from ts2000 import MODE_NAMES, TS2000Emulator

LOG=logging.getLogger("gadx.vector.hub")
HAMLIB_TO_TS2000={"LSB":"LSB","USB":"USB","CW":"CW","CWR":"CW-R","FM":"FM","WFM":"FM","AM":"AM","RTTY":"FSK","RTTYR":"FSK-R","PKTLSB":"LSB","PKTUSB":"USB","PKTFM":"FM"}
SERIAL_LINES={"DTR","RTS","NONE"}; PTT_LINES=SERIAL_LINES|{"RIGCTLD"}; KEYING_POLL_SECONDS=.0005

@dataclass
class RigSnapshot: frequency_hz:int; mode:str; passband_hz:int
@dataclass
class KeyingClientConfig: name:str; port:str; ptt_input:str; cw_input:str
@dataclass
class HubConfig:
    cat_ports:List[str]; cat_baud:int; keying_clients:List[KeyingClientConfig]; radio_keying_port:Optional[str]; radio_keying_baud:int; radio_ptt_line:str; radio_cw_line:str; rig_host:str; rig_port:int; rig_poll_ms:int; allow_write:bool; allow_ptt:bool; allow_cw:bool; log_level:str

class RigctldClient:
    def __init__(self,host,port,timeout=2.0): self.host=host;self.port=port;self.timeout=timeout;self.sock=None;self.file=None;self.lock=threading.RLock()
    def connect(self):
        with self.lock:self._connect_locked()
    def _connect_locked(self):
        self._close_locked();LOG.info("Connecting to rigctld at %s:%d",self.host,self.port);self.sock=socket.create_connection((self.host,self.port),timeout=self.timeout);self.sock.settimeout(self.timeout);self.file=self.sock.makefile("rwb",buffering=0);LOG.info("Connected to rigctld")
    def close(self):
        with self.lock:self._close_locked()
    def _close_locked(self):
        if self.file:
            try:self.file.close()
            except OSError:pass
            self.file=None
        if self.sock:
            try:self.sock.close()
            except OSError:pass
            self.sock=None
    def command(self,cmd,*args):
        with self.lock:
            if self.sock is None or self.file is None:self._connect_locked()
            payload="+\\"+cmd+(" "+" ".join(map(str,args)) if args else "")+"\n";LOG.debug("RIGCTL TX: %s",payload.rstrip())
            try:
                self.file.write(payload.encode("ascii"));records=[]
                while True:
                    raw=self.file.readline()
                    if not raw:raise ConnectionError("rigctld closed connection")
                    line=raw.decode("utf-8",errors="replace").rstrip("\r\n");LOG.debug("RIGCTL RX: %s",line);records.append(line)
                    if line.startswith("RPRT "):
                        code=int(line.split(maxsplit=1)[1])
                        if code:raise RuntimeError(f"rigctld {cmd} failed with RPRT {code}")
                        break
            except (OSError,ConnectionError):self._close_locked();raise
            values={}
            for line in records:
                if ": " in line:
                    k,v=line.split(": ",1);values[k.strip()]=v.strip()
            return values
    def get_snapshot(self):
        f=self.command("get_freq");m=self.command("get_mode");return RigSnapshot(int(float(f["Frequency"])),m["Mode"].upper(),int(float(m.get("Passband","0"))))
    def set_frequency(self,hz):self.command("set_freq",hz)
    def set_mode(self,mode,pb=0):self.command("set_mode",mode,pb)
    def set_ptt(self,on):self.command("set_ptt",1 if on else 0)

class SharedRigState:
    def __init__(self,s):self.lock=threading.RLock();self.snapshot=s
    def get(self):
        with self.lock:return RigSnapshot(self.snapshot.frequency_hz,self.snapshot.mode,self.snapshot.passband_hz)
    def set(self,s):
        with self.lock:self.snapshot=s
class LogicalState:
    def __init__(self):self.lock=threading.RLock();self.sources={}
    def set(self,source,on)->Tuple[bool,bool,int]:
        with self.lock:
            old=any(self.sources.values());self.sources[source]=bool(on);new=any(self.sources.values());return old,new,sum(self.sources.values())

def _ports(v):return [x.strip().upper() for x in v.split(",") if x.strip()]
def _client(name,v):
    p=[x.strip().upper() for x in v.split(",")]
    if len(p)!=3 or p[1] not in SERIAL_LINES or p[2] not in SERIAL_LINES:raise ValueError(f"{name} must be PORT,PTT_INPUT,CW_INPUT")
    if p[1]!="NONE" and p[1]==p[2]:raise ValueError(f"{name}: PTT and CW cannot share input")
    return KeyingClientConfig(name,p[0],p[1],p[2])
def load_config(path):
    c=configparser.ConfigParser();loaded=c.read(path,encoding="utf-8-sig")
    if not loaded:raise ValueError(f"cannot read configuration: {path}")
    for s in ("cat","radio_keying","rig","runtime","logging"):
        if s not in c:raise ValueError(f"INI must contain [{s}]")
    cp=_ports(c["cat"].get("ports",""))
    if not cp:raise ValueError("[cat] ports must not be empty")
    clients=[]
    if "keying" in c:
        for k,v in c["keying"].items():
            if k.lower().startswith("client"):clients.append(_client(k,v))
    rk=c["radio_keying"];ptt=rk.get("ptt_line","NONE").strip().upper();cw=rk.get("cw_line","NONE").strip().upper()
    if ptt not in PTT_LINES or cw not in SERIAL_LINES:raise ValueError("invalid [radio_keying] line mapping")
    if ptt in SERIAL_LINES-{"NONE"} and ptt==cw:raise ValueError("PTT and CW cannot share the same physical serial line")
    run=c["runtime"];log=c["logging"]
    return HubConfig(cp,c["cat"].getint("baud",19200),clients,rk.get("port","").strip().upper() or None,rk.getint("baud",19200),ptt,cw,c["rig"].get("host","127.0.0.1"),c["rig"].getint("port",4532),c["rig"].getint("poll_ms",250),run.getboolean("allow_write",True),run.getboolean("allow_ptt",True),run.getboolean("allow_cw",True),log.get("level","INFO").upper())
def set_line(p,line,on):
    if line=="DTR":p.dtr=on
    elif line=="RTS":p.rts=on
def read_line(p,line):
    if line=="DTR":return bool(p.dsr or p.cd)
    if line=="RTS":return bool(p.cts)
    return False
def apply_snapshot(r,s):
    r.state.frequency_a_hz=s.frequency_hz;m=HAMLIB_TO_TS2000.get(s.mode)
    if m:r.state.mode_code=MODE_NAMES[m]

def apply_ptt_output(rig,out,out_lock,ptt_line,on):
    if ptt_line=="RIGCTLD":
        rig.set_ptt(on)
    elif ptt_line in ("DTR","RTS"):
        if out is None:raise RuntimeError("serial PTT configured but physical keying port is not open")
        with out_lock:set_line(out,ptt_line,on)

def key_worker(client,rig,out,out_lock,ptt_line,cw_line,allow_ptt,allow_cw,ptts,cws,stop,errors):
    inp=None
    try:
        inp=serial.Serial(client.port,19200,timeout=0,write_timeout=None);lp=read_line(inp,client.ptt_input);lc=read_line(inp,client.cw_input);ptts.set(client.name,lp);cws.set(client.name,lc);LOG.info("Keying %s ready: %s PTT=%s CW=%s",client.name,client.port,client.ptt_input,client.cw_input)
        while not stop.is_set():
            np=read_line(inp,client.ptt_input);nc=read_line(inp,client.cw_input)
            if np!=lp:
                lp=np;o,n,_=ptts.set(client.name,np)
                if allow_ptt and o!=n and ptt_line!="NONE":apply_ptt_output(rig,out,out_lock,ptt_line,n)
            if nc!=lc:
                lc=nc;t0=time.perf_counter_ns();o,n,a=cws.set(client.name,nc)
                if a>1 and nc:LOG.warning("CW collision: %d clients active",a)
                if allow_cw and o!=n and out and cw_line!="NONE":
                    with out_lock:set_line(out,cw_line,n)
                if LOG.isEnabledFor(logging.DEBUG):LOG.debug("%s CW %s combined=%s %.1fus",client.name,"ON" if nc else "OFF","ON" if n else "OFF",(time.perf_counter_ns()-t0)/1000)
            time.sleep(KEYING_POLL_SECONDS)
    except Exception as e:errors.put(f"keying {client.name}: {e}")
    finally:
        old,new,_=ptts.set(client.name,False);cws.set(client.name,False)
        if allow_ptt and old!=new and ptt_line!="NONE":
            try:apply_ptt_output(rig,out,out_lock,ptt_line,new)
            except Exception:pass
        if inp:
            try:inp.close()
            except Exception:pass

def cat_worker(port,baud,rig,state,allow_write,stop,errors):
    radio=TS2000Emulator()
    try:
        with serial.Serial(port,baud,timeout=.01,write_timeout=None) as cat:
            LOG.info("CAT client ready: %s @ %d",port,baud)
            while not stop.is_set():
                apply_snapshot(radio,state.get());data=cat.read(4096)
                if not data:continue
                text=data.decode("ascii",errors="replace");LOG.debug("CAT %s RX: %r",port,text);bf,bm=radio.state.frequency_a_hz,radio.state.mode_code;responses=radio.feed(text);af,am=radio.state.frequency_a_hz,radio.state.mode_code
                if allow_write:
                    if af!=bf:rig.set_frequency(af)
                    if am!=bm:
                        name=next((n for n,c in MODE_NAMES.items() if c==am),None);rev={"LSB":"LSB","USB":"USB","CW":"CW","CW-R":"CWR","FM":"FM","AM":"AM","FSK":"RTTY","FSK-R":"RTTYR"}
                        if name in rev:rig.set_mode(rev[name],0)
                else:apply_snapshot(radio,state.get());radio.state.ptt=False
                for response in responses:cat.write(response.encode("ascii"))
    except Exception as e:errors.put(f"CAT {port}: {e}")
def poll_worker(rig,state,ms,stop):
    while not stop.is_set():
        try:state.set(rig.get_snapshot())
        except Exception as e:LOG.error("rigctld poll failed: %s",e)
        time.sleep(max(10,ms)/1000)

def main():
    ap=argparse.ArgumentParser(description="GADX Vector Hub SPIKE 02");ap.add_argument("--config",default="vector.ini");a=ap.parse_args()
    try:c=load_config(a.config)
    except Exception as e:print(f"Configuration error: {e}",file=sys.stderr);return 2
    logging.basicConfig(level=getattr(logging,c.log_level,logging.INFO),format="%(asctime)s %(levelname)s %(message)s");LOG.info("GADX Vector Hub Phase A");LOG.info("Configuration file: %s",a.config);LOG.info("CAT ports: %s @ %d",",".join(c.cat_ports),c.cat_baud);LOG.info("Keying clients: %s",", ".join(f"{x.name}:{x.port}" for x in c.keying_clients) or "none");LOG.info("Physical keying: %s @ %d PTT=%s CW=%s",c.radio_keying_port or "disabled",c.radio_keying_baud,c.radio_ptt_line,c.radio_cw_line)
    rig=RigctldClient(c.rig_host,c.rig_port)
    try:rig.connect();initial=rig.get_snapshot()
    except Exception as e:LOG.error("Cannot initialize rigctld: %s",e);return 2
    state=SharedRigState(initial);ptts=LogicalState();cws=LogicalState();stop=threading.Event();errors=queue.SimpleQueue();out_lock=threading.RLock();out=None
    needs_serial=(c.radio_ptt_line in ("DTR","RTS")) or (c.radio_cw_line in ("DTR","RTS"))
    if needs_serial:
        if not c.radio_keying_port:LOG.error("serial keying enabled without physical port");return 2
        try:out=serial.Serial(c.radio_keying_port,c.radio_keying_baud,timeout=0,write_timeout=None);out.rts=False;out.dtr=False
        except Exception as e:LOG.error("Cannot open physical keying port %s: %s",c.radio_keying_port,e);return 2
    threads=[];t=threading.Thread(target=poll_worker,args=(rig,state,c.rig_poll_ms,stop),daemon=True,name="RigPoll");t.start();threads.append(t)
    for x in c.keying_clients:
        t=threading.Thread(target=key_worker,args=(x,rig,out,out_lock,c.radio_ptt_line,c.radio_cw_line,c.allow_ptt,c.allow_cw,ptts,cws,stop,errors),daemon=True,name=f"Key-{x.name}");t.start();threads.append(t)
    for p in c.cat_ports:
        t=threading.Thread(target=cat_worker,args=(p,c.cat_baud,rig,state,c.allow_write,stop,errors),daemon=True,name=f"CAT-{p}");t.start();threads.append(t)
    LOG.info("Vector Hub ready");rc=0
    try:
        while True:
            try:e=errors.get_nowait()
            except queue.Empty:e=None
            if e:raise RuntimeError(e)
            time.sleep(.25)
    except KeyboardInterrupt:LOG.info("Stopped by user")
    except Exception as e:LOG.error("Vector Hub error: %s",e);rc=2
    finally:
        stop.set()
        for t in threads:t.join(timeout=2)
        if out:
            try:out.rts=False;out.dtr=False
            except Exception:pass
            try:out.close()
            except Exception:pass
        try:
            if c.allow_ptt:rig.set_ptt(False)
        except Exception:pass
        rig.close()
    return rc
if __name__=="__main__":sys.exit(main())
