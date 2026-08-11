from __future__ import annotations
import configparser,ctypes,queue,re,subprocess,sys,threading,tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox,ttk
from typing import List,Optional,Set
from serial.tools import list_ports

CONFIG_PATH=Path(r"C:\Ham\GADX-Vector\config\vector.ini")
SETUPC_CANDIDATES=[Path(r"C:\Program Files (x86)\com0com\setupc.exe"),Path(r"C:\Program Files\com0com\setupc.exe"),Path(r"C:\Ham\com0com\setupc.exe"),Path(r"D:\Ham\com0com\setupc.exe")]
PAIR_RE=re.compile(r"\bCNC([AB])(\d+)\s+.*?(?:PortName|RealPortName)=(COM\d+)",re.I);COM_RE=re.compile(r"^COM(\d+)$",re.I);CLIENT_RE=re.compile(r"^client(\d+)$",re.I)
CREATE_NO_WINDOW=getattr(subprocess,"CREATE_NO_WINDOW",0);STARTF_USESHOWWINDOW=getattr(subprocess,"STARTF_USESHOWWINDOW",0);SW_HIDE=0;APP_COM_MIN,APP_COM_MAX=9,40;VECTOR_COM_MIN,VECTOR_COM_MAX=100,140
@dataclass
class ComPair:index:int;app_port:str;vector_port:str
@dataclass
class DesiredPair:name:str;kind:str;app_port:str;vector_port:str
@dataclass
class DesiredClient:name:str;cat_type:str;cat_app:str;cat_vector:str;key_type:str;key_app:str;key_vector:str
class Com0ComTimeout(TimeoutError):pass
class Com0Com:
 def __init__(self,exe:Path):self.exe=exe
 @classmethod
 def discover(cls):
  for x in SETUPC_CANDIDATES:
   if x.exists():return cls(x)
  raise FileNotFoundError("setupc.exe do com0com nao foi encontrado")
 def _si(self):
  if sys.platform!="win32":return None
  x=subprocess.STARTUPINFO();x.dwFlags|=STARTF_USESHOWWINDOW;x.wShowWindow=SW_HIDE;return x
 def _run(self,args,timeout=8):
  try:return subprocess.run([str(self.exe)]+args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=str(self.exe.parent),encoding="utf-8",errors="replace",timeout=timeout,startupinfo=self._si(),creationflags=CREATE_NO_WINDOW).stdout or ""
  except subprocess.TimeoutExpired as e:raise Com0ComTimeout(f"com0com nao respondeu: {' '.join(args)}") from e
 def _interactive(self,commands,timeout=12):
  try:return subprocess.run([str(self.exe)],input="\n".join(commands+["quit",""]),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=str(self.exe.parent),encoding="utf-8",errors="replace",timeout=timeout,startupinfo=self._si(),creationflags=CREATE_NO_WINDOW).stdout or ""
  except subprocess.TimeoutExpired as e:raise Com0ComTimeout(f"com0com encontrado em {self.exe}, mas nao respondeu") from e
 def _query(self,args,commands):
  try:
   out=self._run(args)
   if out.strip():return out
  except Exception:pass
  return self._interactive(commands)
 def list_pairs(self):
  g={}
  for line in self._query(["list"],["list"]).splitlines():
   m=PAIR_RE.search(line)
   if m:s,i,p=m.groups();g.setdefault(int(i),{})[s.upper()]=p.upper()
  return [ComPair(i,x["A"],x["B"]) for i,x in sorted(g.items()) if "A" in x and "B" in x]
 def busy_names(self):
  return {x.strip().upper() for x in self._query(["busynames","*"],["busynames *"]).splitlines() if COM_RE.match(x.strip().upper())}
 def create_pair(self,a,v):
  try:
   out=self._run(["install",f"PortName={a}",f"PortName={v}"],15)
   if out.strip():return out
  except Exception:pass
  return self._interactive([f"install PortName={a} PortName={v}"],20)
 def remove_pair(self,i):
  try:
   out=self._run(["remove",str(i)],15)
   if out.strip():return out
  except Exception:pass
  return self._interactive([f"remove {i}"],20)
def active_ports():return {(x.device or "").upper():(x.description or x.hwid or "Porta serial") for x in list_ports.comports() if x.device}
def is_admin():
 try:return bool(ctypes.windll.shell32.IsUserAnAdmin())
 except Exception:return False
def com_number(x):
 m=COM_RE.match(x.strip().upper())
 if not m:raise ValueError(f"Porta invalida: {x}")
 return int(m.group(1))
class ProgressDialog(tk.Toplevel):
 def __init__(self,parent,title):
  super().__init__(parent);self.title(title);self.resizable(False,False);self.transient(parent);self.grab_set();self.protocol("WM_DELETE_WINDOW",lambda:None);b=ttk.Frame(self,padding=18);b.pack(fill="both",expand=True);ttk.Label(b,text="GADX Vector Port Manager",font=("Segoe UI",12,"bold")).pack(anchor="w");self.s=tk.StringVar(value="Preparando...");ttk.Label(b,textvariable=self.s).pack(anchor="w",pady=(12,8));self.p=ttk.Progressbar(b,mode="indeterminate",length=420);self.p.pack(fill="x");self.d=tk.StringVar(value="Iniciando operacao...");ttk.Label(b,textvariable=self.d,foreground="#555555").pack(anchor="w",pady=(8,0));self.p.start(12);self.update_idletasks();parent.update_idletasks();self.geometry(f"+{parent.winfo_rootx()+100}+{parent.winfo_rooty()+100}")
 def update_status(self,s,d=""):self.s.set(s);self.d.set(d);self.update_idletasks()
 def close(self):
  try:self.p.stop();self.grab_release();self.destroy()
  except tk.TclError:pass
class ClientRow:
 def __init__(self,m,d):
  self.m=m;t=m.table;self.name=tk.StringVar(value=d.name);self.ct=tk.StringVar(value=d.cat_type);self.ca=tk.StringVar(value=d.cat_app);self.cv=tk.StringVar(value=d.cat_vector);self.kt=tk.StringVar(value=d.key_type);self.ka=tk.StringVar(value=d.key_app);self.kv=tk.StringVar(value=d.key_vector)
  self.w=[ttk.Entry(t,textvariable=self.name,width=14),ttk.Combobox(t,textvariable=self.ct,values=("CAT","NONE"),width=8,state="readonly"),ttk.Combobox(t,textvariable=self.ca,width=9,state="readonly"),ttk.Label(t,text="↔"),ttk.Combobox(t,textvariable=self.cv,width=9,state="readonly"),ttk.Combobox(t,textvariable=self.kt,values=("KEYING","NONE"),width=9,state="readonly"),ttk.Combobox(t,textvariable=self.ka,width=9,state="readonly"),ttk.Label(t,text="↔"),ttk.Combobox(t,textvariable=self.kv,width=9,state="readonly"),ttk.Button(t,text="Remover",command=lambda:m.remove_row(self))]
  self.w[1].bind("<<ComboboxSelected>>",lambda e:self.sync());self.w[5].bind("<<ComboboxSelected>>",lambda e:self.sync());self.w[2].configure(postcommand=lambda:self.choices(self.w[2],"app",self.ca.get()));self.w[4].configure(postcommand=lambda:self.choices(self.w[4],"vector",self.cv.get()));self.w[6].configure(postcommand=lambda:self.choices(self.w[6],"app",self.ka.get()));self.w[8].configure(postcommand=lambda:self.choices(self.w[8],"vector",self.kv.get()));self.refresh();self.sync()
 def place(self,r):
  cols=[0,1,2,3,4,6,7,8,9,10]
  for w,c in zip(self.w,cols):w.grid(row=r,column=c,padx=4,pady=3,sticky="ew")
 def destroy(self):
  for x in self.w:x.destroy()
 def choices(self,w,side,current):w["values"]=self.m.port_choices(side,current,self)
 def refresh(self):self.choices(self.w[2],"app",self.ca.get());self.choices(self.w[4],"vector",self.cv.get());self.choices(self.w[6],"app",self.ka.get());self.choices(self.w[8],"vector",self.kv.get())
 def sync(self):
  c=self.ct.get()!="NONE";k=self.kt.get()!="NONE";self.w[2].configure(state="readonly" if c else "disabled");self.w[4].configure(state="readonly" if c else "disabled");self.w[6].configure(state="readonly" if k else "disabled");self.w[8].configure(state="readonly" if k else "disabled")
 def selected(self):
  s=set()
  if self.ct.get()!="NONE":s|={self.ca.get().upper(),self.cv.get().upper()}
  if self.kt.get()!="NONE":s|={self.ka.get().upper(),self.kv.get().upper()}
  return {x for x in s if x}
 def pairs(self):
  n=self.name.get().strip() or "Cliente";r=[]
  if self.ct.get()!="NONE":r.append(DesiredPair(n,"CAT",self.ca.get().upper(),self.cv.get().upper()))
  if self.kt.get()!="NONE":r.append(DesiredPair(n,"KEYING",self.ka.get().upper(),self.kv.get().upper()))
  return r
class App(tk.Tk):
 def __init__(self):
  super().__init__();self.title("GADX Vector Port Manager - Phase C SPIKE");self.geometry("1120x650");self.minsize(1040,580);self.rows=[];self.com0com=None;self.existing_pairs=[];self.active={};self.busy=set();self.q=queue.Queue();self.progress=None;self.build();self.after(150,lambda:self.refresh_inventory(True,True))
 def build(self):
  top=ttk.Frame(self,padding=10);top.pack(fill="x");ttk.Label(top,text="GADX Vector Port Manager",font=("Segoe UI",16,"bold")).pack(side="left");self.admin=tk.StringVar();ttk.Label(top,textvariable=self.admin).pack(side="right")
  f=ttk.LabelFrame(self,text="Inventario da maquina",padding=8);f.pack(fill="x",padx=10,pady=(0,8));self.status=tk.StringVar(value="com0com: aguardando inventario...");ttk.Label(f,textvariable=self.status).pack(anchor="w");self.inv=tk.Text(f,height=7,wrap="none");self.inv.pack(fill="x",pady=(4,0))
  p=ttk.LabelFrame(self,text="Clientes e pares virtuais desejados",padding=8);p.pack(fill="both",expand=True,padx=10,pady=8);self.table=ttk.Frame(p);self.table.pack(anchor="w",fill="x")
  for c,s in {0:115,1:78,2:82,3:24,4:82,5:18,6:86,7:82,8:24,9:82,10:80}.items():self.table.grid_columnconfigure(c,minsize=s)
  ttk.Label(self.table,text="Cliente",font=("Segoe UI",9,"bold")).grid(row=0,column=0,rowspan=2,sticky="sw");ttk.Label(self.table,text="CAT",font=("Segoe UI",9,"bold")).grid(row=0,column=1,columnspan=4,sticky="ew");ttk.Label(self.table,text="KEYING",font=("Segoe UI",9,"bold")).grid(row=0,column=6,columnspan=4,sticky="ew")
  for c,x in {1:"Tipo",2:"Aplicativo",4:"Vector",6:"Tipo",7:"Aplicativo",9:"Vector"}.items():ttk.Label(self.table,text=x,anchor="center").grid(row=1,column=c,sticky="ew")
  ttk.Separator(self.table,orient="vertical").grid(row=0,column=5,rowspan=100,sticky="ns",padx=8);self.first=2
  b=ttk.Frame(p);b.pack(fill="x",pady=10);ttk.Button(b,text="+ Adicionar cliente",command=self.add_client).pack(side="left");ttk.Button(b,text="Sugestao 2 clientes",command=self.suggest).pack(side="left",padx=6);ttk.Button(b,text="Carregar configuracao atual",command=self.load_ini).pack(side="left");ttk.Button(b,text="Recarregar inventario",command=lambda:self.refresh_inventory(True)).pack(side="left",padx=6);ttk.Button(b,text="Aplicar configuracao",command=self.apply).pack(side="right");self.msg=tk.StringVar(value="v0.8: nomes amigaveis no keying e carga do INI.");ttk.Label(self,textvariable=self.msg,padding=(10,4)).pack(fill="x")
 def work(self,title,fn,ok,fail=None):
  if self.progress:return
  self.progress=ProgressDialog(self,title)
  def run():
   try:self.q.put((1,fn()))
   except Exception as e:self.q.put((0,e))
  threading.Thread(target=run,daemon=True).start()
  def poll():
   try:k,v=self.q.get_nowait()
   except queue.Empty:self.after(100,poll);return
   d=self.progress;self.progress=None;d.close()
   if k:ok(v)
   elif fail:fail(v)
   else:messagebox.showerror("Falha",str(v))
  self.after(100,poll)
 def ps(self,s,d=""):self.after(0,lambda:self.progress and self.progress.update_status(s,d))
 def collect(self):
  self.ps("Etapa 1 de 5 - Lendo portas seriais...");a=active_ports();self.ps("Etapa 2 de 5 - Localizando com0com...");c=Com0Com.discover();self.ps("Etapa 3 de 5 - Consultando pares virtuais...",str(c.exe));pairs=c.list_pairs();self.ps("Etapa 4 de 5 - Consultando portas reservadas...");busy=c.busy_names();self.ps("Etapa 5 de 5 - Atualizando inventario...",f"{len(pairs)} par(es)");return c,pairs,a,busy
 def refresh_inventory(self,show=False,initial=False):
  self.admin.set("Administrador: SIM" if is_admin() else "Administrador: NAO")
  def ok(x):self.com0com,self.existing_pairs,self.active,self.busy=x;self.status.set(f"com0com: {self.com0com.exe}");self.render();self.refresh_rows();initial and not self.existing_pairs and self.suggest()
  def bad(e):self.com0com=None;self.existing_pairs=[];self.active=active_ports();self.busy=set();self.status.set(f"Falha ao consultar com0com: {e}");self.render();initial and self.suggest()
  if show:self.work("Carregando inventario",self.collect,ok,bad)
  else:
   try:ok(self.collect())
   except Exception as e:bad(e)
 def render(self):
  l=["Pares com0com existentes:"]+[f"  #{p.index}: {p.app_port} <-> {p.vector_port}" for p in self.existing_pairs] if self.existing_pairs else ["Pares com0com existentes: nenhum"]
  l+=["","Portas seriais ativas:"]+[f"  {n}: {self.active[n]}" for n in sorted(self.active,key=lambda x:com_number(x) if COM_RE.match(x) else 9999)];self.inv.delete("1.0","end");self.inv.insert("1.0","\n".join(l))
 def existing(self):
  s=set()
  for p in self.existing_pairs:s|={p.app_port,p.vector_port}
  return s
 def other(self,x):
  x=x.upper()
  for p in self.existing_pairs:
   if p.app_port==x:return p.vector_port
   if p.vector_port==x:return p.app_port
  return ""
 def port_choices(self,side,current,owner):
  selected=set()
  for r in self.rows:
   if r is not owner:selected|=r.selected()
  start,end=(APP_COM_MIN,APP_COM_MAX) if side=="app" else (VECTOR_COM_MIN,VECTOR_COM_MAX);existing=self.existing();r=[]
  for n in range(start,end+1):
   p=f"COM{n}"
   if (p not in self.active or p in existing) and (p not in self.busy or p in existing) and p not in selected:r.append(p)
  if current and current not in r:r.insert(0,current)
  return r
 def refresh_rows(self):
  for r in self.rows:r.refresh()
 def clear(self):
  for r in self.rows:r.destroy()
  self.rows=[]
 def addrow(self,d):self.rows.append(ClientRow(self,d));self.regrid();self.refresh_rows()
 def remove_row(self,r):r.destroy();self.rows.remove(r);self.regrid();self.refresh_rows()
 def regrid(self):
  for i,r in enumerate(self.rows):r.place(self.first+i)
 def nextfree(self,start,used):
  e=self.existing();n=start
  while True:
   p=f"COM{n}"
   if p not in used and (p not in self.active or p in e) and (p not in self.busy or p in e):return p
   n+=1
 def suggest(self):
  self.clear();u=set();a=15;v=101
  for name in ("LogHX","N1MM"):
   ca=self.nextfree(a,u);u.add(ca);a=com_number(ca)+1;cv=self.nextfree(v,u);u.add(cv);v=com_number(cv)+1;ka=self.nextfree(a,u);u.add(ka);a=com_number(ka)+1;kv=self.nextfree(v,u);u.add(kv);v=com_number(kv)+1;self.addrow(DesiredClient(name,"CAT",ca,cv,"KEYING",ka,kv))
 def add_client(self):
  u=set()
  for r in self.rows:u|=r.selected()
  ca=self.nextfree(15,u);u.add(ca);cv=self.nextfree(101,u);u.add(cv);ka=self.nextfree(15,u);u.add(ka);kv=self.nextfree(101,u);self.addrow(DesiredClient(f"Cliente {len(self.rows)+1}","CAT",ca,cv,"KEYING",ka,kv))
 def load_ini(self):
  if not CONFIG_PATH.exists():messagebox.showerror("Configuracao",f"Arquivo nao encontrado:\n{CONFIG_PATH}");return
  c=configparser.ConfigParser();c.read(CONFIG_PATH,encoding="utf-8-sig");cats=[x.strip().upper() for x in c.get("cat","ports",fallback="").split(",") if x.strip()];keys=[]
  if c.has_section("keying"):
   for k,v in c.items("keying"):
    m=CLIENT_RE.match(k)
    if not m:continue
    p=[x.strip() for x in v.split(",")]
    if len(p)==4:name=p[0] or f"Cliente {m.group(1)}";port=p[1].upper()
    elif len(p)>=3:name=f"Cliente {m.group(1)}";port=p[0].upper()
    else:continue
    keys.append((int(m.group(1)),name,port))
  keys.sort();count=max(len(cats),len(keys));self.clear();un=[]
  for i in range(count):
   cv=cats[i] if i<len(cats) else "";name=keys[i][1] if i<len(keys) else f"Cliente {i+1}";kv=keys[i][2] if i<len(keys) else "";ca=self.other(cv) if cv else "";ka=self.other(kv) if kv else ""
   if cv and not ca:un.append(cv)
   if kv and not ka:un.append(kv)
   self.addrow(DesiredClient(name,"CAT" if cv else "NONE",ca,cv,"KEYING" if kv else "NONE",ka,kv))
  self.msg.set(f"vector.ini carregado: {count} cliente(s)."+(" Sem par conhecido para: "+", ".join(un) if un else ""))
 def pairs(self):
  x=[]
  for r in self.rows:x+=r.pairs()
  return x
 def validate(self,d):
  if not d:return "Nenhum CAT ou KEYING configurado."
  names=[];e=self.existing()
  for x in d:
   try:com_number(x.app_port);com_number(x.vector_port)
   except ValueError as z:return str(z)
   if x.app_port==x.vector_port:return "As duas pontas nao podem ser iguais."
   names += [x.app_port,x.vector_port]
   for p in (x.app_port,x.vector_port):
    if p in self.active and p not in e:return f"{p} pertence a dispositivo ativo."
  if len(names)!=len(set(names)):return "Uma COM aparece mais de uma vez."
 def apply(self):
  if not is_admin():messagebox.showerror("Permissao","Execute como Administrador.");return
  if not self.com0com:messagebox.showerror("com0com","Recarregue o inventario.");return
  d=self.pairs();err=self.validate(d)
  if err:messagebox.showerror("Plano invalido",err);return
  cur={(p.app_port,p.vector_port):p for p in self.existing_pairs};want={(x.app_port,x.vector_port) for x in d};rem=[p for k,p in cur.items() if k not in want];create=[x for x in d if (x.app_port,x.vector_port) not in cur]
  if not rem and not create:messagebox.showinfo("Sem alteracoes","O com0com ja corresponde ao plano.");return
  summary=["Alteracoes propostas:"]+[f"Remover #{p.index}: {p.app_port} <-> {p.vector_port}" for p in rem]+[f"Criar: {x.app_port} <-> {x.vector_port} ({x.name}/{x.kind})" for x in create]
  if not messagebox.askyesno("Confirmar","\n".join(summary)):return
  def worker():
   total=len(rem)+len(create);n=0
   for p in rem:self.ps(f"Operacao {n+1} de {total} - Removendo...",f"{p.app_port} <-> {p.vector_port}");self.com0com.remove_pair(p.index);n+=1
   for x in create:self.ps(f"Operacao {n+1} de {total} - Criando...",f"{x.app_port} <-> {x.vector_port}");self.com0com.create_pair(x.app_port,x.vector_port);n+=1
   return self.collect()
  def ok(x):self.com0com,self.existing_pairs,self.active,self.busy=x;self.render();self.refresh_rows();self.msg.set("Configuracao aplicada ao com0com. vector.ini ainda nao foi regravado.")
  self.work("Aplicando configuracao",worker,ok)
if __name__=="__main__":
 if sys.platform!="win32":raise SystemExit("GADX Vector Port Manager requer Windows")
 App().mainloop()
