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

SETUPC_CANDIDATES = [
    Path(r"C:\Program Files (x86)\com0com\setupc.exe"),
    Path(r"C:\Program Files\com0com\setupc.exe"),
    Path(r"C:\Ham\com0com\setupc.exe"),
    Path(r"D:\Ham\com0com\setupc.exe"),
]
PAIR_RE = re.compile(r"\bCNC([AB])(\d+)\s+.*?(?:PortName|RealPortName)=(COM\d+)", re.I)
COM_RE = re.compile(r"^COM(\d+)$", re.I)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
SW_HIDE = 0
APP_COM_MIN, APP_COM_MAX = 15, 40
VECTOR_COM_MIN, VECTOR_COM_MAX = 101, 140

@dataclass
class ComPair:
    index: int
    app_port: str
    vector_port: str

@dataclass
class DesiredPair:
    name: str
    kind: str
    app_port: str
    vector_port: str

@dataclass
class DesiredClient:
    name: str
    cat_type: str
    cat_app: str
    cat_vector: str
    key_type: str
    key_app: str
    key_vector: str

class Com0ComTimeout(TimeoutError):
    pass

class Com0Com:
    def __init__(self, exe: Path): self.exe = exe
    @classmethod
    def discover(cls):
        for candidate in SETUPC_CANDIDATES:
            if candidate.exists(): return cls(candidate)
        raise FileNotFoundError("setupc.exe do com0com nao foi encontrado")
    def _interactive(self, commands: List[str], timeout: int = 30) -> str:
        payload = "\n".join(commands + ["quit", ""])
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= STARTF_USESHOWWINDOW; startupinfo.wShowWindow = SW_HIDE
        try:
            proc = subprocess.run([str(self.exe)], input=payload, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=str(self.exe.parent), encoding="utf-8", errors="replace", timeout=timeout,
                startupinfo=startupinfo, creationflags=CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired as exc:
            raise Com0ComTimeout(f"com0com encontrado em {self.exe}, mas nao respondeu em {timeout} segundos") from exc
        return proc.stdout or ""
    def list_pairs(self) -> List[ComPair]:
        grouped = {}
        for line in self._interactive(["list"]).splitlines():
            match = PAIR_RE.search(line)
            if match:
                side, index, port = match.groups(); grouped.setdefault(int(index), {})[side.upper()] = port.upper()
        return [ComPair(i, s["A"], s["B"]) for i, s in sorted(grouped.items()) if "A" in s and "B" in s]
    def busy_names(self) -> Set[str]:
        return {line.strip().upper() for line in self._interactive(["busynames *"]).splitlines() if COM_RE.match(line.strip().upper())}
    def create_pair(self, app_port: str, vector_port: str) -> str:
        return self._interactive([f"install PortName={app_port} PortName={vector_port}"])
    def remove_pair(self, index: int) -> str:
        return self._interactive([f"remove {index}"])

def active_ports() -> dict[str, str]:
    ports = {}
    for item in list_ports.comports():
        name = (item.device or "").upper()
        if name: ports[name] = item.description or item.hwid or "Porta serial"
    return ports

def is_admin() -> bool:
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False

def com_number(name: str) -> int:
    match = COM_RE.match(name.strip().upper())
    if not match: raise ValueError(f"Porta invalida: {name}")
    return int(match.group(1))

class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, title):
        super().__init__(parent); self.title(title); self.resizable(False, False); self.transient(parent); self.grab_set(); self.protocol("WM_DELETE_WINDOW", lambda: None)
        body = ttk.Frame(self, padding=18); body.pack(fill="both", expand=True)
        ttk.Label(body, text="GADX Vector Port Manager", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.status_var = tk.StringVar(value="Preparando..."); ttk.Label(body, textvariable=self.status_var).pack(anchor="w", pady=(12,8))
        self.progress = ttk.Progressbar(body, mode="indeterminate", length=420); self.progress.pack(fill="x")
        self.detail_var = tk.StringVar(value="Iniciando operacao..."); ttk.Label(body, textvariable=self.detail_var, foreground="#555555").pack(anchor="w", pady=(8,0))
        self.progress.start(12); self.update_idletasks(); self._center(parent)
    def _center(self, parent):
        parent.update_idletasks(); self.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width()-self.winfo_width())//2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height()-self.winfo_height())//2)
        self.geometry(f"+{x}+{y}")
    def update_status(self, status, detail=""):
        self.status_var.set(status); self.detail_var.set(detail); self.update_idletasks()
    def close(self):
        try: self.progress.stop(); self.grab_release(); self.destroy()
        except tk.TclError: pass

class ClientRow:
    def __init__(self, manager: "PortManagerApp", desired: DesiredClient):
        self.manager = manager; table = manager.table
        self.name = tk.StringVar(value=desired.name); self.cat_type = tk.StringVar(value=desired.cat_type)
        self.cat_app = tk.StringVar(value=desired.cat_app); self.cat_vector = tk.StringVar(value=desired.cat_vector)
        self.key_type = tk.StringVar(value=desired.key_type); self.key_app = tk.StringVar(value=desired.key_app); self.key_vector = tk.StringVar(value=desired.key_vector)
        self.name_entry = ttk.Entry(table, textvariable=self.name, width=14)
        self.cat_type_combo = ttk.Combobox(table, textvariable=self.cat_type, values=("CAT","NONE"), width=8, state="readonly")
        self.cat_app_combo = ttk.Combobox(table, textvariable=self.cat_app, width=9, state="readonly")
        self.cat_arrow = ttk.Label(table, text="↔", anchor="center")
        self.cat_vector_combo = ttk.Combobox(table, textvariable=self.cat_vector, width=9, state="readonly")
        self.key_type_combo = ttk.Combobox(table, textvariable=self.key_type, values=("KEYING","NONE"), width=9, state="readonly")
        self.key_app_combo = ttk.Combobox(table, textvariable=self.key_app, width=9, state="readonly")
        self.key_arrow = ttk.Label(table, text="↔", anchor="center")
        self.key_vector_combo = ttk.Combobox(table, textvariable=self.key_vector, width=9, state="readonly")
        self.remove_button = ttk.Button(table, text="Remover", command=lambda: manager.remove_client_row(self))
        self.widgets = [self.name_entry,self.cat_type_combo,self.cat_app_combo,self.cat_arrow,self.cat_vector_combo,
                        self.key_type_combo,self.key_app_combo,self.key_arrow,self.key_vector_combo,self.remove_button]
        self.cat_type_combo.bind("<<ComboboxSelected>>", lambda _e: self._sync_enabled_state())
        self.key_type_combo.bind("<<ComboboxSelected>>", lambda _e: self._sync_enabled_state())
        self.cat_app_combo.configure(postcommand=lambda: self._refresh_combo(self.cat_app_combo,"app",self.cat_app.get()))
        self.cat_vector_combo.configure(postcommand=lambda: self._refresh_combo(self.cat_vector_combo,"vector",self.cat_vector.get()))
        self.key_app_combo.configure(postcommand=lambda: self._refresh_combo(self.key_app_combo,"app",self.key_app.get()))
        self.key_vector_combo.configure(postcommand=lambda: self._refresh_combo(self.key_vector_combo,"vector",self.key_vector.get()))
        self._refresh_all_choices(); self._sync_enabled_state()
    def place(self, row):
        self.name_entry.grid(row=row,column=0,padx=(2,8),pady=3,sticky="ew")
        self.cat_type_combo.grid(row=row,column=1,padx=4,pady=3,sticky="ew")
        self.cat_app_combo.grid(row=row,column=2,padx=4,pady=3,sticky="ew")
        self.cat_arrow.grid(row=row,column=3,padx=1,pady=3)
        self.cat_vector_combo.grid(row=row,column=4,padx=4,pady=3,sticky="ew")
        self.key_type_combo.grid(row=row,column=6,padx=4,pady=3,sticky="ew")
        self.key_app_combo.grid(row=row,column=7,padx=4,pady=3,sticky="ew")
        self.key_arrow.grid(row=row,column=8,padx=1,pady=3)
        self.key_vector_combo.grid(row=row,column=9,padx=4,pady=3,sticky="ew")
        self.remove_button.grid(row=row,column=10,padx=(10,2),pady=3,sticky="ew")
    def destroy(self):
        for w in self.widgets: w.destroy()
    def _refresh_combo(self, combo, side, current): combo["values"] = self.manager.port_choices(side,current,self)
    def _refresh_all_choices(self):
        self._refresh_combo(self.cat_app_combo,"app",self.cat_app.get()); self._refresh_combo(self.cat_vector_combo,"vector",self.cat_vector.get())
        self._refresh_combo(self.key_app_combo,"app",self.key_app.get()); self._refresh_combo(self.key_vector_combo,"vector",self.key_vector.get())
    def _sync_enabled_state(self):
        cat = self.cat_type.get() != "NONE"; key = self.key_type.get() != "NONE"
        self.cat_app_combo.configure(state="readonly" if cat else "disabled"); self.cat_vector_combo.configure(state="readonly" if cat else "disabled")
        self.key_app_combo.configure(state="readonly" if key else "disabled"); self.key_vector_combo.configure(state="readonly" if key else "disabled")
    def selected_ports(self):
        ports=set()
        if self.cat_type.get() != "NONE": ports.update({self.cat_app.get().strip().upper(),self.cat_vector.get().strip().upper()})
        if self.key_type.get() != "NONE": ports.update({self.key_app.get().strip().upper(),self.key_vector.get().strip().upper()})
        return {p for p in ports if p}
    def desired_pairs(self):
        result=[]; name=self.name.get().strip() or "Cliente"
        if self.cat_type.get() != "NONE": result.append(DesiredPair(name,"CAT",self.cat_app.get().strip().upper(),self.cat_vector.get().strip().upper()))
        if self.key_type.get() != "NONE": result.append(DesiredPair(name,"KEYING",self.key_app.get().strip().upper(),self.key_vector.get().strip().upper()))
        return result

class PortManagerApp(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("GADX Vector Port Manager - Phase C SPIKE"); self.geometry("1120x650"); self.minsize(1040,580)
        self.rows=[]; self.com0com=None; self.existing_pairs=[]; self.active={}; self.busy=set(); self._work_queue=queue.Queue(); self._progress=None
        self._build(); self.after(150, lambda: self.refresh_inventory(True,True))
    def _build(self):
        top=ttk.Frame(self,padding=10); top.pack(fill="x"); ttk.Label(top,text="GADX Vector Port Manager",font=("Segoe UI",16,"bold")).pack(side="left")
        self.admin_var=tk.StringVar(); ttk.Label(top,textvariable=self.admin_var).pack(side="right")
        status=ttk.LabelFrame(self,text="Inventario da maquina",padding=8); status.pack(fill="x",padx=10,pady=(0,8))
        self.setupc_var=tk.StringVar(value="com0com: aguardando inventario..."); ttk.Label(status,textvariable=self.setupc_var).pack(anchor="w")
        self.inventory_text=tk.Text(status,height=7,wrap="none"); self.inventory_text.pack(fill="x",pady=(4,0))
        plan=ttk.LabelFrame(self,text="Clientes e pares virtuais desejados",padding=8); plan.pack(fill="both",expand=True,padx=10,pady=8)
        self.table=ttk.Frame(plan); self.table.pack(anchor="w",fill="x",pady=(2,6))
        for col,size in {0:115,1:78,2:82,3:24,4:82,5:18,6:86,7:82,8:24,9:82,10:80}.items(): self.table.grid_columnconfigure(col,minsize=size)
        ttk.Label(self.table,text="Cliente",font=("Segoe UI",9,"bold"),anchor="w").grid(row=0,column=0,rowspan=2,padx=(2,8),pady=(0,4),sticky="sw")
        ttk.Label(self.table,text="CAT",font=("Segoe UI",9,"bold"),anchor="center").grid(row=0,column=1,columnspan=4,pady=(0,2),sticky="ew")
        ttk.Label(self.table,text="KEYING",font=("Segoe UI",9,"bold"),anchor="center").grid(row=0,column=6,columnspan=4,pady=(0,2),sticky="ew")
        for col,text in {1:"Tipo",2:"Aplicativo",3:"",4:"Vector",6:"Tipo",7:"Aplicativo",8:"",9:"Vector",10:""}.items():
            ttk.Label(self.table,text=text,anchor="center").grid(row=1,column=col,padx=4,pady=(0,4),sticky="ew")
        ttk.Separator(self.table,orient="vertical").grid(row=0,column=5,rowspan=100,padx=10,sticky="ns")
        self._first_client_grid_row=2
        buttons=ttk.Frame(plan); buttons.pack(fill="x",pady=10)
        ttk.Button(buttons,text="+ Adicionar cliente",command=self.add_suggested_client).pack(side="left")
        ttk.Button(buttons,text="Sugestao 2 clientes",command=self.load_default_suggestion).pack(side="left",padx=6)
        ttk.Button(buttons,text="Recarregar inventario",command=lambda:self.refresh_inventory(True)).pack(side="left")
        ttk.Button(buttons,text="Aplicar configuracao",command=self.apply_plan).pack(side="right")
        self.message_var=tk.StringVar(value="Fase C v0.5: tabela alinhada por cliente; CAT e KEYING agrupados visualmente.")
        ttk.Label(self,textvariable=self.message_var,padding=(10,4)).pack(fill="x")
    def _begin_work(self,title,worker,on_success,on_error=None):
        if self._progress is not None: return
        self._progress=ProgressDialog(self,title)
        def run():
            try:self._work_queue.put(("ok",worker()))
            except Exception as exc:self._work_queue.put(("error",exc))
        threading.Thread(target=run,daemon=True).start()
        def poll():
            try:kind,payload=self._work_queue.get_nowait()
            except queue.Empty:self.after(100,poll);return
            p=self._progress; self._progress=None
            if p:p.close()
            if kind=="ok":on_success(payload)
            elif on_error:on_error(payload)
            else:messagebox.showerror("Falha",str(payload))
        self.after(100,poll)
    def _progress_status(self,status,detail=""): self.after(0,lambda:self._progress and self._progress.update_status(status,detail))
    def _collect_inventory(self):
        self._progress_status("Etapa 1 de 5 - Lendo portas seriais...","Consultando dispositivos COM ativos no Windows"); active=active_ports()
        self._progress_status("Etapa 2 de 5 - Localizando com0com...","Procurando setupc.exe"); c=Com0Com.discover()
        self._progress_status("Etapa 3 de 5 - Consultando pares virtuais...",str(c.exe)); pairs=c.list_pairs()
        self._progress_status("Etapa 4 de 5 - Consultando portas reservadas...","Lendo nomes registrados no ComDB"); busy=c.busy_names()
        self._progress_status("Etapa 5 de 5 - Atualizando inventario...",f"{len(pairs)} par(es) virtual(is) encontrado(s)"); return c,pairs,active,busy
    def refresh_inventory(self,show_progress=False,initial=False):
        self.admin_var.set("Administrador: SIM" if is_admin() else "Administrador: NAO")
        def ok(r):
            self.com0com,self.existing_pairs,self.active,self.busy=r; self.setupc_var.set(f"com0com: {self.com0com.exe}"); self._render_inventory(); self.refresh_row_choices()
            if initial and not self.existing_pairs:self.load_default_suggestion()
        def fail(exc):
            self.com0com=None; self.existing_pairs=[]; self.active=active_ports(); self.busy=set(); self.setupc_var.set(str(exc) if isinstance(exc,Com0ComTimeout) else f"com0com indisponivel: {exc}"); self._render_inventory(); self.refresh_row_choices()
            if initial:self.load_default_suggestion()
        if show_progress:self._begin_work("Carregando inventario",self._collect_inventory,ok,fail)
        else:
            try:ok(self._collect_inventory())
            except Exception as exc:fail(exc)
    def _render_inventory(self):
        lines=[]
        if self.existing_pairs:
            lines.append("Pares com0com existentes:"); lines.extend(f"  #{p.index}: {p.app_port} <-> {p.vector_port}" for p in self.existing_pairs)
        else:lines.append("Pares com0com existentes: nenhum")
        lines.extend(["","Portas seriais ativas:"])
        for name in sorted(self.active,key=lambda p:com_number(p) if COM_RE.match(p) else 9999): lines.append(f"  {name}: {self.active[name]}")
        self.inventory_text.delete("1.0","end"); self.inventory_text.insert("1.0","\n".join(lines))
    def existing_pair_ports(self):
        result=set()
        for p in self.existing_pairs:result.update({p.app_port,p.vector_port})
        return result
    def ports_selected_by_other_rows(self,owner):
        result=set()
        for row in self.rows:
            if row is not owner:result.update(row.selected_ports())
        return result
    def port_choices(self,side,current="",owner=None):
        current=current.strip().upper(); existing=self.existing_pair_ports(); selected=self.ports_selected_by_other_rows(owner)
        start,end=(APP_COM_MIN,APP_COM_MAX) if side=="app" else (VECTOR_COM_MIN,VECTOR_COM_MAX); choices=[]
        for n in range(start,end+1):
            p=f"COM{n}"; occupied=p in self.active and p not in existing; reserved=p in self.busy and p not in existing
            if not occupied and not reserved and p not in selected:choices.append(p)
        if current and current not in choices:choices.insert(0,current)
        return choices
    def refresh_row_choices(self):
        for row in self.rows:row._refresh_all_choices()
    def clear_rows(self):
        for row in self.rows:row.destroy()
        self.rows.clear()
    def add_client_row(self,d):
        row=ClientRow(self,d); self.rows.append(row); self.regrid_rows(); self.refresh_row_choices()
    def remove_client_row(self,row):
        row.destroy(); self.rows.remove(row); self.regrid_rows(); self.refresh_row_choices()
    def regrid_rows(self):
        for i,row in enumerate(self.rows):row.place(self._first_client_grid_row+i)
    def _next_free(self,start,used):
        existing=self.existing_pair_ports(); n=start
        while True:
            p=f"COM{n}"
            if p not in used and (p not in self.active or p in existing) and (p not in self.busy or p in existing):return p
            n+=1
    def load_default_suggestion(self):
        self.clear_rows(); used=set(); app=APP_COM_MIN; vector=VECTOR_COM_MIN
        for name in ("LogHX","N1MM"):
            ca=self._next_free(app,used); used.add(ca); app=com_number(ca)+1
            cv=self._next_free(vector,used); used.add(cv); vector=com_number(cv)+1
            ka=self._next_free(app,used); used.add(ka); app=com_number(ka)+1
            kv=self._next_free(vector,used); used.add(kv); vector=com_number(kv)+1
            self.add_client_row(DesiredClient(name,"CAT",ca,cv,"KEYING",ka,kv))
        self.message_var.set("Sugestao criada: cada cliente recebeu CAT + KEYING sem reutilizar COMs ocupadas/reservadas.")
    def add_suggested_client(self):
        used=set()
        for row in self.rows:used.update(row.selected_ports())
        ca=self._next_free(APP_COM_MIN,used); used.add(ca); cv=self._next_free(VECTOR_COM_MIN,used); used.add(cv)
        ka=self._next_free(APP_COM_MIN,used); used.add(ka); kv=self._next_free(VECTOR_COM_MIN,used)
        self.add_client_row(DesiredClient(f"Cliente {len(self.rows)+1}","CAT",ca,cv,"KEYING",ka,kv))
    def desired_pairs(self):
        result=[]
        for row in self.rows:result.extend(row.desired_pairs())
        return result
    def validate_plan(self,desired):
        if not desired:return "Nenhum CAT ou KEYING foi configurado."
        names=[]; existing=self.existing_pair_ports()
        for item in desired:
            try:com_number(item.app_port);com_number(item.vector_port)
            except ValueError as exc:return str(exc)
            if item.app_port==item.vector_port:return f"{item.name}/{item.kind}: as duas pontas nao podem ser iguais."
            names.extend([item.app_port,item.vector_port])
            for p in (item.app_port,item.vector_port):
                if p in self.active and p not in existing:return f"{p} pertence a um dispositivo ativo e nao sera sobrescrita."
                if p in self.busy and p not in existing:return f"{p} esta reservada no ComDB. A v0.5 nao forca reservas/conflitos."
        if len(names)!=len(set(names)):return "Uma mesma COM aparece em mais de um endpoint do plano."
        return None
    def apply_plan(self):
        if not is_admin():messagebox.showerror("Permissao","Execute o Port Manager como Administrador para alterar o com0com.");return
        if not self.com0com:messagebox.showerror("com0com","com0com nao esta pronto. Use Recarregar inventario e verifique a mensagem exibida.");return
        desired=self.desired_pairs(); err=self.validate_plan(desired)
        if err:messagebox.showerror("Plano invalido",err);return
        current={(p.app_port,p.vector_port):p for p in self.existing_pairs}; wanted={(d.app_port,d.vector_port) for d in desired}
        rem=[p for k,p in current.items() if k not in wanted]; create=[d for d in desired if (d.app_port,d.vector_port) not in current]
        summary=["Alteracoes propostas:"]+[f"Remover #{p.index}: {p.app_port} <-> {p.vector_port}" for p in rem]+[f"Criar: {d.app_port} <-> {d.vector_port} ({d.name}/{d.kind})" for d in create]
        if not rem and not create:messagebox.showinfo("Sem alteracoes","O com0com ja corresponde ao plano exibido.");return
        if not messagebox.askyesno("Confirmar","\n".join(summary)):return
        def worker():
            total=max(1,len(rem)+len(create)); done=0
            for p in rem:
                self._progress_status(f"Operacao {done+1} de {total} - Removendo par...",f"{p.app_port} <-> {p.vector_port}"); self.com0com.remove_pair(p.index); done+=1
            for d in create:
                self._progress_status(f"Operacao {done+1} de {total} - Validando portas...",f"{d.app_port} <-> {d.vector_port}"); active=active_ports(); busy=self.com0com.busy_names()
                if d.app_port in active or d.vector_port in active or d.app_port in busy or d.vector_port in busy:raise RuntimeError(f"Conflito detectado antes de criar {d.app_port} <-> {d.vector_port}; operacao interrompida")
                self._progress_status(f"Operacao {done+1} de {total} - Criando par virtual...",f"{d.app_port} <-> {d.vector_port} ({d.name}/{d.kind})"); output=self.com0com.create_pair(d.app_port,d.vector_port)
                if "ERROR:" in output.upper():raise RuntimeError(output.strip())
                done+=1
            self._progress_status("Finalizando - Confirmando configuracao...","Relendo o inventario do com0com"); return self._collect_inventory()
        def ok(r):
            self.com0com,self.existing_pairs,self.active,self.busy=r; self.setupc_var.set(f"com0com: {self.com0com.exe}"); self._render_inventory(); self.refresh_row_choices(); self.message_var.set("Configuracao aplicada. Verifique a lista e reinicie o Windows se o driver solicitar reboot."); messagebox.showinfo("Concluido","Plano aplicado ao com0com. Confira o inventario antes de iniciar o Vector Hub.")
        def fail(exc):messagebox.showerror("Falha",str(exc)); self.refresh_inventory(True)
        self._begin_work("Aplicando configuracao",worker,ok,fail)

if __name__ == "__main__":
    if sys.platform != "win32": raise SystemExit("GADX Vector Port Manager Phase C requer Windows")
    PortManagerApp().mainloop()
