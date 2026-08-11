from __future__ import annotations
import configparser,ctypes,queue,re,subprocess,sys,threading,tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox,ttk
from serial.tools import list_ports
CONFIG_PATH=Path(r"C:\Ham\GADX-Vector\config\vector.ini")
SETUPC_CANDIDATES=[Path(r"C:\Program Files (x86)\com0com\setupc.exe"),Path(r"C:\Program Files\com0com\setupc.exe"),Path(r"C:\Ham\com0com\setupc.exe"),Path(r"D:\Ham\com0com\setupc.exe")]
PAIR_RE=re.compile(r"\bCNC([AB])(\d+)\s+.*?(?:PortName|RealPortName)=(COM\d+)",re.I);COM_RE=re.compile(r"^COM(\d+)$",re.I);CLIENT_RE=re.compile(r"^client(\d+)$",re.I);KEY_RE=re.compile(r"^(\s*)(client(\d+))(\s*=\s*)(.*?)(\r?\n)?$",re.I)
CNW=getattr(subprocess,"CREATE_NO_WINDOW",0);SU=getattr(subprocess,"STARTF_USESHOWWINDOW",0);APP_MIN,APP_MAX,VEC_MIN,VEC_MAX=9,40,100,140
@dataclass
class ComPair:index:int;app_port:str;vector_port:str
@dataclass
class DesiredPair:name:str;kind:str;app_port:str;vector_port:str
@dataclass
class DesiredClient:name:str;cat_type:str;cat_app:str;cat_vector:str;key_type:str;key_app:str;key_vector:str
class Com0Com:
 def __init__(self,e):self.exe=e
 @classmethod
 def discover(cls):
  for x in SETUPC_CANDIDATES:
   if x.exists():return cls(x)
  raise FileNotFoundError("setupc.exe do com0com nao foi encontrado")
 def si(self):
  if sys.platform!="win32":return None
  x=subprocess.STARTUPINFO();x.dwFlags|=SU;x.wShowWindow=0;return x
 def run(self,args,timeout=8,input=None):return subprocess.run([str(self.exe)]+args,input=input,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=str(self.exe.parent),encoding="utf-8",errors="replace",timeout=timeout,startupinfo=self.si(),creationflags=CNW).stdout or ""
 def query(self,args,cmd):
  try:
   o=self.run(args)
   if o.strip():return o
  except Exception:pass
  return self.run([],12,"\n".join([cmd,"quit",""]))
 def list_pairs(self):
  g={}
  for l in self.query(["list"],"list").splitlines():
   m=PAIR_RE.search(l)
   if m:s,i,p=m.groups();g.setdefault(int(i),{})[s.upper()]=p.upper()
  return [ComPair(i,x["A"],x["B"]) for i,x in sorted(g.items()) if "A" in x and "B" in x]
 def busy_names(self):return {x.strip().upper() for x in self.query(["busynames","*"],"busynames *").splitlines() if COM_RE.match(x.strip().upper())}
 def create_pair(self,a,v):return self.run(["install",f"PortName={a}",f"PortName={v}"],20)
 def remove_pair(self,i):return self.run(["remove",str(i)],20)
def active_ports():return {(x.device or "").upper():(x.description or x.hwid or "Porta serial") for x in list_ports.comports() if x.device}
def admin():
 try:return bool(ctypes.windll.shell32.IsUserAnAdmin())
 except:return False
def num(x):
 m=COM_RE.match(x.strip().upper())
 if not m:raise ValueError(f"Porta invalida: {x}")
 return int(m.group(1))
class Tip:
 def __init__(self,w,t):self.w=w;self.t=t;self.a=None;self.p=None;w.bind("<Enter>",self.enter,add="+");w.bind("<Leave>",self.hide,add="+")
 def enter(self,e=None):self.a=self.w.after(550,self.show)
 def show(self):
  x=self.w.winfo_rootx()+18;y=self.w.winfo_rooty()+self.w.winfo_height()+8;self.p=tk.Toplevel(self.w);self.p.overrideredirect(True);self.p.geometry(f"+{x}+{y}");tk.Label(self.p,text=self.t,justify="left",relief="solid",borderwidth=1,background="#ffffe0",padx=7,pady=5,wraplength=380).pack()
 def hide(self,e=None):
  if self.a:
   try:self.w.after_cancel(self.a)
   except:pass
   self.a=None
  if self.p:self.p.destroy();self.p=None
class Progress(tk.Toplevel):
 def __init__(self,p,title):
  super().__init__(p);self.title(title);self.transient(p);self.grab_set();b=ttk.Frame(self,padding=18);b.pack();ttk.Label(b,text="GADX Vector Port Manager",font=("Segoe UI",12,"bold")).pack(anchor="w");self.s=tk.StringVar(value="Preparando...");ttk.Label(b,textvariable=self.s).pack(anchor="w",pady=10);self.pb=ttk.Progressbar(b,mode="indeterminate",length=420);self.pb.pack();self.pb.start(12)
 def set(self,s):self.s.set(s);self.update_idletasks()
 def close(self):self.pb.stop();self.destroy()
class Help(tk.Toplevel):
 TEXT="""GADX VECTOR PORT MANAGER\n\nOBJETIVO\nO Port Manager organiza as portas seriais virtuais usadas pelo GADX Vector Hub. Ele permite que varios programas de radioamador usem CAT, PTT e CW ao mesmo tempo sem disputar a mesma porta COM.\n\nCOMO A ARQUITETURA FUNCIONA\nCada canal usa um par com0com. Uma ponta e apresentada ao software e a outra e aberta exclusivamente pelo Vector Hub.\n\nExemplo:\n  Log4OM CAT     COM15 <-> COM101\n  Log4OM KEYING  COM16 <-> COM102\n  N1MM CAT       COM17 <-> COM103\n  N1MM KEYING    COM18 <-> COM104\n\nCAT\nCanal de controle do radio: frequencia, modo e outros comandos. O software enxerga uma fachada compativel com Kenwood TS-2000; o radio fisico continua controlado pelo Hamlib/rigctld.\n\nKEYING\nCanal separado de CAT para PTT e CW pelas linhas DTR/RTS. O caminho de CW e mantido separado para reduzir latencia e jitter.\n\nAPLICATIVO x VECTOR\nAplicativo = COM configurada no Log4OM, N1MM, OmniRig ou outro programa.\nVector = outra ponta do mesmo par, aberta somente pelo GADX Vector Hub.\n\nCARREGAR CONFIGURACAO ATUAL\nLe o vector.ini e cruza as COMs internas com os pares encontrados no com0com para reconstruir o setup atual.\n\nRECARREGAR INVENTARIO\nRelê Windows, com0com e reservas sem alterar a configuracao.\n\nADICIONAR / SUGESTAO\nAdiciona clientes ou monta um plano inicial. Nada e aplicado ate a confirmacao.\n\nNOME DO CLIENTE\nO nome amigavel facilita logs e diagnostico. Exemplo:\n  client1 = Log4OM,COM102,DTR,RTS\nSem nome declarado, a tela usa Cliente 1, Cliente 2 etc.\n\nAPLICAR CONFIGURACAO\nCompara o plano da tela com o estado real, mostra um resumo e pede confirmacao antes de criar/remover pares e atualizar nomes no vector.ini.\n\nPOLITICA DE PORTAS\nNovas instalacoes tentam COM15 em diante no lado dos aplicativos e COM101 em diante no lado interno do Vector, sempre pulando portas ocupadas.\n\nANTES DE APLICAR\n1. Confira o inventario.\n2. Em estacao existente, carregue a configuracao atual.\n3. Confira as duas pontas de cada par.\n4. Feche programas usando COMs que serao removidas.\n5. Leia o resumo antes de confirmar.\n\nDIAGNOSTICO\nSe uma COM interna do vector.ini nao encontra a ponta Aplicativo, confira o inventario com0com. Se CAT funciona mas PTT/CW nao, revise KEYING e DTR/RTS.\n\nSEGURANCA\nO Port Manager nao deve substituir silenciosamente uma porta fisica ou COM ocupada. O operador sempre visualiza o plano antes da alteracao.\n"""
 def __init__(self,p):
  super().__init__(p);self.title("Ajuda - GADX Vector Port Manager");self.geometry("760x650");o=ttk.Frame(self,padding=12);o.pack(fill="both",expand=True);ttk.Label(o,text="GADX Vector Port Manager - Ajuda",font=("Segoe UI",14,"bold")).pack(anchor="w",pady=(0,10));f=ttk.Frame(o);f.pack(fill="both",expand=True);s=ttk.Scrollbar(f);s.pack(side="right",fill="y");t=tk.Text(f,wrap="word",yscrollcommand=s.set,padx=10,pady=10);t.pack(fill="both",expand=True);s.config(command=t.yview);t.insert("1.0",self.TEXT);t.config(state="disabled");ttk.Button(o,text="Fechar",command=self.destroy).pack(side="right",pady=(10,0))
class Row:
 def __init__(self,m,d):
  self.m=m;t=m.table;self.name=tk.StringVar(value=d.name);self.ct=tk.StringVar(value=d.cat_type);self.ca=tk.StringVar(value=d.cat_app);self.cv=tk.StringVar(value=d.cat_vector);self.kt=tk.StringVar(value=d.key_type);self.ka=tk.StringVar(value=d.key_app);self.kv=tk.StringVar(value=d.key_vector);self.w=[ttk.Entry(t,textvariable=self.name,width=14),ttk.Combobox(t,textvariable=self.ct,values=("CAT","NONE"),width=8,state="readonly"),ttk.Combobox(t,textvariable=self.ca,width=9,state="readonly"),ttk.Label(t,text="↔"),ttk.Combobox(t,textvariable=self.cv,width=9,state="readonly"),ttk.Combobox(t,textvariable=self.kt,values=("KEYING","NONE"),width=9,state="readonly"),ttk.Combobox(t,textvariable=self.ka,width=9,state="readonly"),ttk.Label(t,text="↔"),ttk.Combobox(t,textvariable=self.kv,width=9,state="readonly"),ttk.Button(t,text="Remover",command=lambda:m.remove(self))];tips=["Nome amigavel: Log4OM, N1MM, OmniRig...","Habilita CAT","COM configurada no aplicativo","","COM interna do Vector","Habilita PTT/CW","COM de KEYING no aplicativo","","COM interna de KEYING","Remove do plano"]
  for w,x in zip(self.w,tips):
   if x:m.tip(w,x)
  self.w[2].config(postcommand=lambda:self.choice(self.w[2],"app",self.ca.get()));self.w[4].config(postcommand=lambda:self.choice(self.w[4],"vec",self.cv.get()));self.w[6].config(postcommand=lambda:self.choice(self.w[6],"app",self.ka.get()));self.w[8].config(postcommand=lambda:self.choice(self.w[8],"vec",self.kv.get()));self.refresh()
 def choice(self,w,s,c):w["values"]=self.m.choices(s,c,self)
 def refresh(self):self.choice(self.w[2],"app",self.ca.get());self.choice(self.w[4],"vec",self.cv.get());self.choice(self.w[6],"app",self.ka.get());self.choice(self.w[8],"vec",self.kv.get())
 def place(self,r):
  for w,c in zip(self.w,[0,1,2,3,4,6,7,8,9,10]):w.grid(row=r,column=c,padx=4,pady=3)
 def selected(self):return {x.upper() for x in (self.ca.get(),self.cv.get(),self.ka.get(),self.kv.get()) if x}
 def destroy(self):
  for w in self.w:w.destroy()
 def pairs(self):
  n=self.name.get().strip() or "Cliente";r=[]
  if self.ct.get()!="NONE":r.append(DesiredPair(n,"CAT",self.ca.get().upper(),self.cv.get().upper()))
  if self.kt.get()!="NONE":r.append(DesiredPair(n,"KEYING",self.ka.get().upper(),self.kv.get().upper()))
  return r
class App(tk.Tk):
 def __init__(self):super().__init__();self.title("GADX Vector Port Manager");self.geometry("1120x700");self.rows=[];self.c=None;self.ep=[];self.active={};self.busy=set();self.q=queue.Queue();self.progress=None;self.tips=[];self.build();self.after(150,lambda:self.refresh(True,True))
 def tip(self,w,t):self.tips.append(Tip(w,t))
 def build(self):
  top=ttk.Frame(self,padding=10);top.pack(fill="x");ttk.Label(top,text="GADX Vector Port Manager",font=("Segoe UI",16,"bold")).pack(side="left");hb=ttk.Button(top,text="?",width=3,command=lambda:Help(self));hb.pack(side="right");self.ad=tk.StringVar();ttk.Label(top,textvariable=self.ad).pack(side="right",padx=10);self.tip(hb,"Abre a ajuda completa")
  f=ttk.LabelFrame(self,text="Inventario da maquina",padding=8);f.pack(fill="x",padx=10);self.st=tk.StringVar();ttk.Label(f,textvariable=self.st).pack(anchor="w");self.inv=tk.Text(f,height=7);self.inv.pack(fill="x")
  p=ttk.LabelFrame(self,text="Clientes e pares virtuais desejados",padding=8);p.pack(fill="both",expand=True,padx=10,pady=8);self.table=ttk.Frame(p);self.table.pack(fill="x");ttk.Label(self.table,text="Cliente",font=("Segoe UI",9,"bold")).grid(row=0,column=0,rowspan=2);ttk.Label(self.table,text="CAT",font=("Segoe UI",9,"bold")).grid(row=0,column=1,columnspan=4);ttk.Label(self.table,text="KEYING",font=("Segoe UI",9,"bold")).grid(row=0,column=6,columnspan=4)
  for c,x in {1:"Tipo",2:"Aplicativo",4:"Vector",6:"Tipo",7:"Aplicativo",9:"Vector"}.items():ttk.Label(self.table,text=x).grid(row=1,column=c)
  b=ttk.Frame(p);b.pack(fill="x",pady=10);ttk.Button(b,text="+ Adicionar cliente",command=self.add).pack(side="left");ttk.Button(b,text="Sugestao 2 clientes",command=self.suggest).pack(side="left",padx=6)
  self.msg=tk.StringVar(value="v0.12: ajuda orientada ao operador.");ttk.Label(self,textvariable=self.msg,padding=10).pack(side="bottom",fill="x");a=ttk.Frame(self,padding=10);a.pack(side="bottom",fill="x");ttk.Button(a,text="Carregar configuracao atual",command=self.load).pack(side="left");ttk.Button(a,text="Recarregar inventario",command=lambda:self.refresh(True)).pack(side="left",padx=6);ttk.Button(a,text="Aplicar configuracao",command=self.apply).pack(side="right")
 def work(self,title,fn,ok):
  self.progress=Progress(self,title)
  def r():
   try:self.q.put((1,fn()))
   except Exception as e:self.q.put((0,e))
  threading.Thread(target=r,daemon=True).start()
  def poll():
   try:k,v=self.q.get_nowait()
   except queue.Empty:self.after(100,poll);return
   self.progress.close();self.progress=None;ok(v) if k else messagebox.showerror("Falha",str(v))
  self.after(100,poll)
 def collect(self):
  a=active_ports();c=Com0Com.discover();return c,c.list_pairs(),a,c.busy_names()
 def refresh(self,show=False,initial=False):
  self.ad.set("Administrador: SIM" if admin() else "Administrador: NAO")
  def ok(x):self.c,self.ep,self.active,self.busy=x;self.st.set(f"com0com: {self.c.exe}");self.render();[r.refresh() for r in self.rows];initial and not self.ep and self.suggest()
  self.work("Carregando inventario",self.collect,ok) if show else ok(self.collect())
 def render(self):
  l=["Pares com0com existentes:"]+[f"  #{p.index}: {p.app_port} <-> {p.vector_port}" for p in self.ep]+["","Portas seriais ativas:"]+[f"  {x}: {self.active[x]}" for x in sorted(self.active,key=lambda x:num(x) if COM_RE.match(x) else 9999)];self.inv.delete("1.0","end");self.inv.insert("1.0","\n".join(l))
 def existing(self):return {x for p in self.ep for x in (p.app_port,p.vector_port)}
 def other(self,x):
  for p in self.ep:
   if p.app_port==x:return p.vector_port
   if p.vector_port==x:return p.app_port
  return ""
 def choices(self,side,current,owner):
  used={x for r in self.rows if r is not owner for x in r.selected()};lo,hi=(APP_MIN,APP_MAX) if side=="app" else (VEC_MIN,VEC_MAX);e=self.existing();r=[f"COM{n}" for n in range(lo,hi+1) if f"COM{n}" not in used and (f"COM{n}" not in self.active or f"COM{n}" in e) and (f"COM{n}" not in self.busy or f"COM{n}" in e)];return ([current]+r if current and current not in r else r)
 def clear(self):[r.destroy() for r in self.rows];self.rows=[]
 def addrow(self,d):self.rows.append(Row(self,d));[r.place(i+2) for i,r in enumerate(self.rows)]
 def remove(self,r):r.destroy();self.rows.remove(r);[x.place(i+2) for i,x in enumerate(self.rows)]
 def free(self,start,used):
  n=start;e=self.existing()
  while f"COM{n}" in used or (f"COM{n}" in self.active and f"COM{n}" not in e) or (f"COM{n}" in self.busy and f"COM{n}" not in e):n+=1
  return f"COM{n}"
 def add(self):
  u={x for r in self.rows for x in r.selected()};ca=self.free(15,u);u.add(ca);cv=self.free(101,u);u.add(cv);ka=self.free(15,u);u.add(ka);kv=self.free(101,u);self.addrow(DesiredClient(f"Cliente {len(self.rows)+1}","CAT",ca,cv,"KEYING",ka,kv))
 def suggest(self):self.clear();self.add();self.rows[0].name.set("Log4OM");self.add();self.rows[1].name.set("N1MM")
 def load(self):
  if not CONFIG_PATH.exists():return messagebox.showerror("Configuracao",str(CONFIG_PATH))
  c=configparser.ConfigParser();c.read(CONFIG_PATH,encoding="utf-8-sig");cats=[x.strip().upper() for x in c.get("cat","ports",fallback="").split(",") if x.strip()];keys=[]
  for k,v in c.items("keying") if c.has_section("keying") else []:
   m=CLIENT_RE.match(k);p=[x.strip() for x in v.split(",")]
   if m and len(p)>=3:keys.append((int(m.group(1)),p[0] if len(p)==4 else f"Cliente {m.group(1)}",p[1].upper() if len(p)==4 else p[0].upper()))
  keys.sort();self.clear()
  for i in range(max(len(cats),len(keys))):cv=cats[i] if i<len(cats) else "";kv=keys[i][2] if i<len(keys) else "";self.addrow(DesiredClient(keys[i][1] if i<len(keys) else f"Cliente {i+1}","CAT" if cv else "NONE",self.other(cv),cv,"KEYING" if kv else "NONE",self.other(kv),kv))
 def pairs(self):return [p for r in self.rows for p in r.pairs()]
 def oldnames(self):
  c=configparser.ConfigParser();c.read(CONFIG_PATH,encoding="utf-8-sig");r={}
  for k,v in c.items("keying") if c.has_section("keying") else []:
   m=CLIENT_RE.match(k);p=[x.strip() for x in v.split(",")]
   if m:r[int(m.group(1))]=p[0] if len(p)==4 else f"Cliente {m.group(1)}"
  return r
 def namechanges(self):
  o=self.oldnames();return [(i,o.get(i,f"Cliente {i}"),r.name.get().strip() or f"Cliente {i}") for i,r in enumerate(self.rows,1) if r.kt.get()!="NONE" and (r.name.get().strip() or f"Cliente {i}")!=o.get(i,f"Cliente {i}")]
 def persist(self):
  desired={i:r.name.get().strip() or f"Cliente {i}" for i,r in enumerate(self.rows,1) if r.kt.get()!="NONE"};out=[];inside=False
  for line in CONFIG_PATH.read_text(encoding="utf-8-sig").splitlines(True):
   s=line.strip()
   if s.startswith("["):inside=s.lower()=="[keying]"
   if inside:
    m=KEY_RE.match(line)
    if m and int(m.group(3)) in desired:
     p=[x.strip() for x in m.group(5).split(",")];p=([desired[int(m.group(3))]]+p[:3]) if len(p)==3 else [desired[int(m.group(3))]]+p[1:];line=f"{m.group(1)}{m.group(2)}{m.group(4)}{','.join(p)}{m.group(6) or chr(10)}"
   out.append(line)
  CONFIG_PATH.write_text("".join(out),encoding="utf-8")
 def apply(self):
  if not admin():return messagebox.showerror("Permissao","Execute como Administrador.")
  d=self.pairs();cur={(p.app_port,p.vector_port):p for p in self.ep};want={(x.app_port,x.vector_port) for x in d};rem=[p for k,p in cur.items() if k not in want];create=[x for x in d if (x.app_port,x.vector_port) not in cur];nc=self.namechanges()
  if not rem and not create and not nc:return messagebox.showinfo("Sem alteracoes","COMs e nomes ja correspondem ao plano.")
  s=["Alteracoes propostas:"]+[f"Remover {p.app_port} <-> {p.vector_port}" for p in rem]+[f"Criar {x.app_port} <-> {x.vector_port} ({x.name}/{x.kind})" for x in create]+[f"Renomear client{i}: {a} -> {b}" for i,a,b in nc]
  if not messagebox.askyesno("Confirmar","\n".join(s)):return
  def worker():
   for p in rem:self.c.remove_pair(p.index)
   for x in create:self.c.create_pair(x.app_port,x.vector_port)
   if nc:self.persist()
   return self.collect()
  self.work("Aplicando configuracao",worker,lambda x:(setattr(self,"c",x[0]),setattr(self,"ep",x[1]),setattr(self,"active",x[2]),setattr(self,"busy",x[3]),self.render()))
if __name__=="__main__":
 if sys.platform!="win32":raise SystemExit("GADX Vector Port Manager requer Windows")
 App().mainloop()
