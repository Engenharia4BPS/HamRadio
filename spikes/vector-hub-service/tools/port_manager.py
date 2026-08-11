from __future__ import annotations

import ctypes
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, List, Optional, Set

from serial.tools import list_ports

SETUPC_CANDIDATES = [Path(r"C:\Program Files (x86)\com0com\setupc.exe"),Path(r"C:\Program Files\com0com\setupc.exe"),Path(r"C:\Ham\com0com\setupc.exe"),Path(r"D:\Ham\com0com\setupc.exe")]
PAIR_RE=re.compile(r"\bCNC([AB])(\d+)\s+.*?(?:PortName|RealPortName)=(COM\d+)",re.I);COM_RE=re.compile(r"^COM(\d+)$",re.I)
CREATE_NO_WINDOW=getattr(subprocess,"CREATE_NO_WINDOW",0);STARTF_USESHOWWINDOW=getattr(subprocess,"STARTF_USESHOWWINDOW",0);SW_HIDE=0
@dataclass
class ComPair:index:int;app_port:str;vector_port:str
@dataclass
class DesiredPair:name:str;kind:str;app_port:str;vector_port:str
class Com0ComTimeout(TimeoutError):pass
class Com0Com:
 def __init__(self,exe:Path):self.exe=exe
 @classmethod
 def discover(cls):
  for c in SETUPC_CANDIDATES:
   if c.exists():return cls(c)
  raise FileNotFoundError("setupc.exe do com0com nao foi encontrado")
 def _interactive(self,commands:List[str],timeout:int=30)->str:
  payload="\n".join(commands+["quit",""]);si=None
  if sys.platform=="win32":si=subprocess.STARTUPINFO();si.dwFlags|=STARTF_USESHOWWINDOW;si.wShowWindow=SW_HIDE
  try:p=subprocess.run([str(self.exe)],input=payload,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=str(self.exe.parent),encoding="utf-8",errors="replace",timeout=timeout,startupinfo=si,creationflags=CREATE_NO_WINDOW)
  except subprocess.TimeoutExpired as e:raise Com0ComTimeout(f"com0com encontrado em {self.exe}, mas nao respondeu em {timeout} segundos") from e
  return p.stdout or ""
 def list_pairs(self):
  grouped={}
  for line in self._interactive(["list"]).splitlines():
   m=PAIR_RE.search(line)
   if m:s,i,p=m.groups();grouped.setdefault(int(i),{})[s.upper()]=p.upper()
  return [ComPair(i,s["A"],s["B"]) for i,s in sorted(grouped.items()) if "A" in s and "B" in s]
 def busy_names(self):
  return {x.strip().upper() for x in self._interactive(["busynames *"]).splitlines() if COM_RE.match(x.strip().upper())}
 def create_pair(self,a,v):return self._interactive([f"install PortName={a} PortName={v}"])
 def remove_pair(self,i):return self._interactive([f"remove {i}"])
def active_ports():return {(x.device or "").upper():(x.description or x.hwid or "Porta serial") for x in list_ports.comports() if x.device}
def is_admin():
 try:return bool(ctypes.windll.shell32.IsUserAnAdmin())
 except Exception:return False
def com_number(n):
 m=COM_RE.match(n.strip().upper())
 if not m:raise ValueError(f"Porta invalida: {n}")
 return int(m.group(1))
class ProgressDialog(tk.Toplevel):
 def __init__(self,parent,title):
  super().__init__(parent);self.title(title);self.resizable(False,False);self.transient(parent);self.grab_set();self.protocol("WM_DELETE_WINDOW",lambda:None)
  b=ttk.Frame(self,padding=18);b.pack(fill="both",expand=True);ttk.Label(b,text="GADX Vector Port Manager",font=("Segoe UI",12,"bold")).pack(anchor="w")
  self.status_var=tk.StringVar(value="Preparando...");ttk.Label(b,textvariable=self.status_var).pack(anchor="w",pady=(12,8));self.progress=ttk.Progressbar(b,mode="indeterminate",length=420);self.progress.pack(fill="x")
  self.detail_var=tk.StringVar(value="Iniciando operacao...");ttk.Label(b,textvariable=self.detail_var,foreground="#555555").pack(anchor="w",pady=(8,0));self.progress.start(12);self.update_idletasks();self._center(parent)
 def _center(self,p):
  p.update_idletasks();self.update_idletasks();self.geometry(f"+{p.winfo_rootx()+max(0,(p.winfo_width()-self.winfo_width())//2)}+{p.winfo_rooty()+max(0,(p.winfo_height()-self.winfo_height())//2)}")
 def update_status(self,s,d=""):self.status_var.set(s);self.detail_var.set(d);self.update_idletasks()
 def close(self):
  try:self.progress.stop();self.grab_release();self.destroy()
  except tk.TclError:pass
class PairRow:
 def __init__(self,parent,m,d):
  self.manager=m;self.frame=ttk.Frame(parent);self.name=tk.StringVar(value=d.name);self.kind=tk.StringVar(value=d.kind);self.app_port=tk.StringVar(value=d.app_port);self.vector_port=tk.StringVar(value=d.vector_port)
  ttk.Entry(self.frame,textvariable=self.name,width=16).grid(row=0,column=0,padx=3,pady=2);ttk.Combobox(self.frame,textvariable=self.kind,values=("CAT","KEYING","GENERIC"),width=10,state="readonly").grid(row=0,column=1,padx=3);ttk.Entry(self.frame,textvariable=self.app_port,width=10).grid(row=0,column=2,padx=3);ttk.Label(self.frame,text="↔").grid(row=0,column=3);ttk.Entry(self.frame,textvariable=self.vector_port,width=10).grid(row=0,column=4,padx=3);ttk.Button(self.frame,text="Remover",command=lambda:m.remove_row(self)).grid(row=0,column=5,padx=4)
 def grid(self,r):self.frame.grid(row=r,column=0,sticky="ew")
 def desired(self):return DesiredPair(self.name.get().strip() or "Cliente",self.kind.get().strip().upper() or "GENERIC",self.app_port.get().strip().upper(),self.vector_port.get().strip().upper())
class PortManagerApp(tk.Tk):
 def __init__(self):
  super().__init__();self.title("GADX Vector Port Manager - Phase C SPIKE");self.geometry("900x650");self.minsize(820,580);self.rows=[];self.com0com=None;self.existing_pairs=[];self.active={};self.busy=set();self._work_queue=queue.Queue();self._progress=None;self._build();self.after(150,lambda:self.refresh_inventory(True,True))
 def _build(self):
  top=ttk.Frame(self,padding=10);top.pack(fill="x");ttk.Label(top,text="GADX Vector Port Manager",font=("Segoe UI",16,"bold")).pack(side="left");self.admin_var=tk.StringVar();ttk.Label(top,textvariable=self.admin_var).pack(side="right")
  s=ttk.LabelFrame(self,text="Inventario da maquina",padding=8);s.pack(fill="x",padx=10,pady=(0,8));self.setupc_var=tk.StringVar(value="com0com: aguardando inventario...");ttk.Label(s,textvariable=self.setupc_var).pack(anchor="w");self.inventory_text=tk.Text(s,height=7,wrap="none");self.inventory_text.pack(fill="x",pady=(4,0))
  plan=ttk.LabelFrame(self,text="Pares virtuais desejados",padding=8);plan.pack(fill="both",expand=True,padx=10,pady=8);h=ttk.Frame(plan);h.pack(fill="x")
  for text,width in [("Cliente",16),("Tipo",10),("Aplicativo",10),("",2),("Vector",10),("",8)]:ttk.Label(h,text=text,width=width).pack(side="left",padx=3)
  self.rows_frame=ttk.Frame(plan);self.rows_frame.pack(fill="x",pady=4);buttons=ttk.Frame(plan);buttons.pack(fill="x",pady=8);ttk.Button(buttons,text="+ Adicionar par",command=self.add_suggested_row).pack(side="left");ttk.Button(buttons,text="Sugestao 4 pares",command=self.load_default_suggestion).pack(side="left",padx=6);ttk.Button(buttons,text="Recarregar inventario",command=lambda:self.refresh_inventory(True)).pack(side="left");ttk.Button(buttons,text="Aplicar configuracao",command=self.apply_plan).pack(side="right");self.message_var=tk.StringVar(value="Fase C v0.3: progresso detalhado em tempo real; conflitos nunca sao forcados.");ttk.Label(self,textvariable=self.message_var,padding=(10,4)).pack(fill="x")
 def _begin_work(self,title,worker,on_success,on_error=None):
  if self._progress:return
  self._progress=ProgressDialog(self,title)
  def run():
   try:self._work_queue.put(("ok",worker()))
   except Exception as e:self._work_queue.put(("error",e))
  threading.Thread(target=run,daemon=True).start()
  def poll():
   try:k,p=self._work_queue.get_nowait()
   except queue.Empty:self.after(100,poll);return
   d=self._progress;self._progress=None
   if d:d.close()
   if k=="ok":on_success(p)
   elif on_error:on_error(p)
   else:messagebox.showerror("Falha",str(p))
  self.after(100,poll)
 def _progress_status(self,s,d=""):self.after(0,lambda:self._progress and self._progress.update_status(s,d))
 def _collect_inventory(self):
  self._progress_status("Etapa 1 de 5 - Lendo portas seriais...","Consultando dispositivos COM ativos no Windows");a=active_ports()
  self._progress_status("Etapa 2 de 5 - Localizando com0com...","Procurando setupc.exe");c=Com0Com.discover()
  self._progress_status("Etapa 3 de 5 - Consultando pares virtuais...",str(c.exe));pairs=c.list_pairs()
  self._progress_status("Etapa 4 de 5 - Consultando portas reservadas...","Lendo nomes registrados no ComDB");busy=c.busy_names()
  self._progress_status("Etapa 5 de 5 - Atualizando inventario...",f"{len(pairs)} par(es) virtual(is) encontrado(s)");return c,pairs,a,busy
 def refresh_inventory(self,show_progress=False,initial=False):
  self.admin_var.set("Administrador: SIM" if is_admin() else "Administrador: NAO")
  def ok(r):
   self.com0com,self.existing_pairs,self.active,self.busy=r;self.setupc_var.set(f"com0com: {self.com0com.exe}");self._render_inventory()
   if initial and not self.existing_pairs:self.load_default_suggestion()
  def err(e):
   self.com0com=None;self.existing_pairs=[];self.active=active_ports();self.busy=set();self.setupc_var.set(str(e) if isinstance(e,Com0ComTimeout) else f"com0com indisponivel: {e}");self._render_inventory()
   if initial:self.load_default_suggestion()
  if show_progress:self._begin_work("Carregando inventario",self._collect_inventory,ok,err)
  else:
   try:ok(self._collect_inventory())
   except Exception as e:err(e)
 def _render_inventory(self):
  lines=["Pares com0com existentes:"]+[f"  #{p.index}: {p.app_port} <-> {p.vector_port}" for p in self.existing_pairs] if self.existing_pairs else ["Pares com0com existentes: nenhum"]
  lines+=["","Portas seriais ativas:"]+[f"  {n}: {self.active[n]}" for n in sorted(self.active,key=lambda p:com_number(p) if COM_RE.match(p) else 9999)];self.inventory_text.delete("1.0","end");self.inventory_text.insert("1.0","\n".join(lines))
 def clear_rows(self):
  for r in self.rows:r.frame.destroy()
  self.rows.clear()
 def add_row(self,d):r=PairRow(self.rows_frame,self,d);self.rows.append(r);self.regrid_rows()
 def remove_row(self,r):r.frame.destroy();self.rows.remove(r);self.regrid_rows()
 def regrid_rows(self):
  for i,r in enumerate(self.rows):r.grid(i)
 def _next_free(self,start,used):
  n=start
  while True:
   x=f"COM{n}"
   if x not in used and x not in self.active and x not in self.busy:return x
   n+=1
 def load_default_suggestion(self):
  self.clear_rows();used=set();a,v=15,101
  for name,kind in [("Cliente 1","CAT"),("Cliente 1","KEYING"),("Cliente 2","CAT"),("Cliente 2","KEYING")]:
   ap=self._next_free(a,used);used.add(ap);a=com_number(ap)+1;vp=self._next_free(v,used);used.add(vp);v=com_number(vp)+1;self.add_row(DesiredPair(name,kind,ap,vp))
  self.message_var.set("Sugestao criada sem reutilizar nomes atualmente ocupados/reservados.")
 def add_suggested_row(self):
  used={d.app_port for d in (r.desired() for r in self.rows)}|{d.vector_port for d in (r.desired() for r in self.rows)};a=self._next_free(15,used);used.add(a);v=self._next_free(101,used);self.add_row(DesiredPair(f"Cliente {len(self.rows)+1}","CAT",a,v))
 def validate_plan(self,desired):
  if not desired:return "Nenhum par foi configurado."
  names=[];existing={p.app_port for p in self.existing_pairs}|{p.vector_port for p in self.existing_pairs}
  for d in desired:
   try:com_number(d.app_port);com_number(d.vector_port)
   except ValueError as e:return str(e)
   if d.app_port==d.vector_port:return f"{d.name}: as duas pontas nao podem ser iguais."
   names += [d.app_port,d.vector_port]
   for p in (d.app_port,d.vector_port):
    if p in self.active and p not in existing:return f"{p} pertence a um dispositivo ativo e nao sera sobrescrita."
    if p in self.busy and p not in existing:return f"{p} esta reservada no ComDB. A v0.3 nao forca reservas/conflitos."
  if len(names)!=len(set(names)):return "Uma mesma COM aparece em mais de um endpoint do plano."
 def apply_plan(self):
  if not is_admin():messagebox.showerror("Permissao","Execute o Port Manager como Administrador para alterar o com0com.");return
  if not self.com0com:messagebox.showerror("com0com","com0com nao esta pronto. Use Recarregar inventario e verifique a mensagem exibida.");return
  desired=[r.desired() for r in self.rows];e=self.validate_plan(desired)
  if e:messagebox.showerror("Plano invalido",e);return
  current={(p.app_port,p.vector_port):p for p in self.existing_pairs};wanted={(d.app_port,d.vector_port) for d in desired};rem=[p for k,p in current.items() if k not in wanted];create=[d for d in desired if (d.app_port,d.vector_port) not in current];summary=["Alteracoes propostas:"]+[f"Remover #{p.index}: {p.app_port} <-> {p.vector_port}" for p in rem]+[f"Criar: {d.app_port} <-> {d.vector_port} ({d.name}/{d.kind})" for d in create]
  if not rem and not create:messagebox.showinfo("Sem alteracoes","O com0com ja corresponde ao plano exibido.");return
  if not messagebox.askyesno("Confirmar","\n".join(summary)):return
  def worker():
   total=max(1,len(rem)+len(create));done=0
   for p in rem:self._progress_status(f"Operacao {done+1} de {total} - Removendo par...",f"{p.app_port} <-> {p.vector_port}");self.com0com.remove_pair(p.index);done+=1
   for d in create:
    self._progress_status(f"Operacao {done+1} de {total} - Validando portas...",f"{d.app_port} <-> {d.vector_port}");a=active_ports();b=self.com0com.busy_names()
    if d.app_port in a or d.vector_port in a or d.app_port in b or d.vector_port in b:raise RuntimeError(f"Conflito detectado antes de criar {d.app_port} <-> {d.vector_port}; operacao interrompida")
    self._progress_status(f"Operacao {done+1} de {total} - Criando par virtual...",f"{d.app_port} <-> {d.vector_port} ({d.name}/{d.kind})");o=self.com0com.create_pair(d.app_port,d.vector_port)
    if "ERROR:" in o.upper():raise RuntimeError(o.strip())
    done+=1
   self._progress_status("Finalizando - Confirmando configuracao...","Relendo o inventario do com0com");return self._collect_inventory()
  def ok(r):self.com0com,self.existing_pairs,self.active,self.busy=r;self.setupc_var.set(f"com0com: {self.com0com.exe}");self._render_inventory();self.message_var.set("Configuracao aplicada. Verifique a lista e reinicie o Windows se o driver solicitar reboot.");messagebox.showinfo("Concluido","Plano aplicado ao com0com. Confira o inventario antes de iniciar o Vector Hub.")
  def err(e):messagebox.showerror("Falha",str(e));self.refresh_inventory(True)
  self._begin_work("Aplicando configuracao",worker,ok,err)
if __name__=="__main__":
 if sys.platform!="win32":raise SystemExit("GADX Vector Port Manager Phase C requer Windows")
 PortManagerApp().mainloop()
