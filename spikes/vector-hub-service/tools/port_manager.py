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


class Com0ComTimeout(TimeoutError):
    pass


class Com0Com:
    def __init__(self, exe: Path):
        self.exe = exe

    @classmethod
    def discover(cls) -> "Com0Com":
        for candidate in SETUPC_CANDIDATES:
            if candidate.exists():
                return cls(candidate)
        raise FileNotFoundError("setupc.exe do com0com nao foi encontrado")

    def _interactive(self, commands: List[str], timeout: int = 30) -> str:
        payload = "\n".join(commands + ["quit", ""])
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = SW_HIDE
        try:
            proc = subprocess.run(
                [str(self.exe)],
                input=payload,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self.exe.parent),
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                startupinfo=startupinfo,
                creationflags=CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:
            raise Com0ComTimeout(
                f"com0com encontrado em {self.exe}, mas nao respondeu em {timeout} segundos"
            ) from exc
        return proc.stdout or ""

    def list_pairs(self) -> List[ComPair]:
        output = self._interactive(["list"])
        grouped = {}
        for line in output.splitlines():
            match = PAIR_RE.search(line)
            if not match:
                continue
            side, index, port = match.groups()
            grouped.setdefault(int(index), {})[side.upper()] = port.upper()
        pairs = []
        for index, sides in sorted(grouped.items()):
            if "A" in sides and "B" in sides:
                pairs.append(ComPair(index, sides["A"], sides["B"]))
        return pairs

    def busy_names(self) -> Set[str]:
        output = self._interactive(["busynames *"])
        result = set()
        for line in output.splitlines():
            item = line.strip().upper()
            if COM_RE.match(item):
                result.add(item)
        return result

    def create_pair(self, app_port: str, vector_port: str) -> str:
        return self._interactive([f"install PortName={app_port} PortName={vector_port}"])

    def remove_pair(self, index: int) -> str:
        return self._interactive([f"remove {index}"])


def active_ports() -> dict[str, str]:
    ports = {}
    for item in list_ports.comports():
        name = (item.device or "").upper()
        if name:
            description = item.description or item.hwid or "Porta serial"
            ports[name] = description
    return ports


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def com_number(name: str) -> int:
    match = COM_RE.match(name.strip().upper())
    if not match:
        raise ValueError(f"Porta invalida: {name}")
    return int(match.group(1))


class ProgressDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, title: str):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        body = ttk.Frame(self, padding=18)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="GADX Vector Port Manager", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.status_var = tk.StringVar(value="Preparando...")
        ttk.Label(body, textvariable=self.status_var).pack(anchor="w", pady=(12, 8))
        self.progress = ttk.Progressbar(body, mode="indeterminate", length=420)
        self.progress.pack(fill="x")
        self.detail_var = tk.StringVar(value="")
        ttk.Label(body, textvariable=self.detail_var, foreground="#555555").pack(anchor="w", pady=(8, 0))
        self.progress.start(12)
        self.update_idletasks()
        self._center(parent)

    def _center(self, parent: tk.Misc):
        parent.update_idletasks()
        self.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    def update_status(self, status: str, detail: str = ""):
        self.status_var.set(status)
        self.detail_var.set(detail)

    def close(self):
        try:
            self.progress.stop()
            self.grab_release()
            self.destroy()
        except tk.TclError:
            pass


class PairRow:
    def __init__(self, parent, manager: "PortManagerApp", desired: DesiredPair):
        self.manager = manager
        self.frame = ttk.Frame(parent)
        self.name = tk.StringVar(value=desired.name)
        self.kind = tk.StringVar(value=desired.kind)
        self.app_port = tk.StringVar(value=desired.app_port)
        self.vector_port = tk.StringVar(value=desired.vector_port)
        ttk.Entry(self.frame, textvariable=self.name, width=16).grid(row=0, column=0, padx=3, pady=2)
        ttk.Combobox(self.frame, textvariable=self.kind, values=("CAT", "KEYING", "GENERIC"), width=10, state="readonly").grid(row=0, column=1, padx=3)
        ttk.Entry(self.frame, textvariable=self.app_port, width=10).grid(row=0, column=2, padx=3)
        ttk.Label(self.frame, text="↔").grid(row=0, column=3)
        ttk.Entry(self.frame, textvariable=self.vector_port, width=10).grid(row=0, column=4, padx=3)
        ttk.Button(self.frame, text="Remover", command=lambda: manager.remove_row(self)).grid(row=0, column=5, padx=4)

    def grid(self, row: int):
        self.frame.grid(row=row, column=0, sticky="ew")

    def desired(self) -> DesiredPair:
        return DesiredPair(
            self.name.get().strip() or "Cliente",
            self.kind.get().strip().upper() or "GENERIC",
            self.app_port.get().strip().upper(),
            self.vector_port.get().strip().upper(),
        )


class PortManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GADX Vector Port Manager - Phase C SPIKE")
        self.geometry("900x650")
        self.minsize(820, 580)
        self.rows: List[PairRow] = []
        self.com0com: Optional[Com0Com] = None
        self.existing_pairs: List[ComPair] = []
        self.active: dict[str, str] = {}
        self.busy: Set[str] = set()
        self._work_queue: "queue.Queue[tuple]" = queue.Queue()
        self._progress: Optional[ProgressDialog] = None
        self._build()
        self.after(150, lambda: self.refresh_inventory(show_progress=True, initial=True))

    def _build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="GADX Vector Port Manager", font=("Segoe UI", 16, "bold")).pack(side="left")
        self.admin_var = tk.StringVar()
        ttk.Label(top, textvariable=self.admin_var).pack(side="right")

        status = ttk.LabelFrame(self, text="Inventario da maquina", padding=8)
        status.pack(fill="x", padx=10, pady=(0, 8))
        self.setupc_var = tk.StringVar(value="com0com: aguardando inventario...")
        ttk.Label(status, textvariable=self.setupc_var).pack(anchor="w")
        self.inventory_text = tk.Text(status, height=7, wrap="none")
        self.inventory_text.pack(fill="x", pady=(4, 0))

        plan = ttk.LabelFrame(self, text="Pares virtuais desejados", padding=8)
        plan.pack(fill="both", expand=True, padx=10, pady=8)
        header = ttk.Frame(plan); header.pack(fill="x")
        for text, width in [("Cliente",16),("Tipo",10),("Aplicativo",10),("",2),("Vector",10),("",8)]:
            ttk.Label(header, text=text, width=width).pack(side="left", padx=3)
        self.rows_frame = ttk.Frame(plan); self.rows_frame.pack(fill="x", pady=4)

        buttons = ttk.Frame(plan); buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="+ Adicionar par", command=self.add_suggested_row).pack(side="left")
        ttk.Button(buttons, text="Sugestao 4 pares", command=self.load_default_suggestion).pack(side="left", padx=6)
        ttk.Button(buttons, text="Recarregar inventario", command=lambda: self.refresh_inventory(show_progress=True)).pack(side="left")
        ttk.Button(buttons, text="Aplicar configuracao", command=self.apply_plan).pack(side="right")

        self.message_var = tk.StringVar(value="Fase C v0.2: operacoes executadas em background; conflitos nunca sao forcados.")
        ttk.Label(self, textvariable=self.message_var, padding=(10,4)).pack(fill="x")

    def _begin_work(self, title: str, worker: Callable[[], object], on_success: Callable[[object], None], on_error: Optional[Callable[[Exception], None]] = None):
        if self._progress is not None:
            return
        self._progress = ProgressDialog(self, title)

        def run():
            try:
                result = worker()
                self._work_queue.put(("ok", result))
            except Exception as exc:
                self._work_queue.put(("error", exc))

        threading.Thread(target=run, daemon=True).start()

        def poll():
            try:
                kind, payload = self._work_queue.get_nowait()
            except queue.Empty:
                self.after(100, poll)
                return
            progress = self._progress
            self._progress = None
            if progress:
                progress.close()
            if kind == "ok":
                on_success(payload)
            elif on_error:
                on_error(payload)
            else:
                messagebox.showerror("Falha", str(payload))

        self.after(100, poll)

    def _progress_status(self, status: str, detail: str = ""):
        self.after(0, lambda: self._progress and self._progress.update_status(status, detail))

    def _collect_inventory(self):
        self._progress_status("Lendo portas seriais do Windows...")
        active = active_ports()
        self._progress_status("Localizando com0com...")
        com0com = Com0Com.discover()
        self._progress_status("Consultando pares virtuais...", str(com0com.exe))
        pairs = com0com.list_pairs()
        self._progress_status("Consultando nomes COM reservados...")
        busy = com0com.busy_names()
        return com0com, pairs, active, busy

    def refresh_inventory(self, show_progress: bool = False, initial: bool = False):
        self.admin_var.set("Administrador: SIM" if is_admin() else "Administrador: NAO")

        def success(result):
            self.com0com, self.existing_pairs, self.active, self.busy = result
            self.setupc_var.set(f"com0com: {self.com0com.exe}")
            self._render_inventory()
            if initial and not self.existing_pairs:
                self.load_default_suggestion()

        def error(exc: Exception):
            self.com0com = None; self.existing_pairs=[]; self.active=active_ports(); self.busy=set()
            if isinstance(exc, Com0ComTimeout):
                self.setupc_var.set(str(exc))
            else:
                self.setupc_var.set(f"com0com indisponivel: {exc}")
            self._render_inventory()
            if initial:
                self.load_default_suggestion()

        if show_progress:
            self._begin_work("Carregando inventario", self._collect_inventory, success, error)
        else:
            try:
                success(self._collect_inventory())
            except Exception as exc:
                error(exc)

    def _render_inventory(self):
        lines=[]
        if self.existing_pairs:
            lines.append("Pares com0com existentes:")
            for pair in self.existing_pairs: lines.append(f"  #{pair.index}: {pair.app_port} <-> {pair.vector_port}")
        else: lines.append("Pares com0com existentes: nenhum")
        lines += ["", "Portas seriais ativas:"]
        for name in sorted(self.active, key=lambda p: com_number(p) if COM_RE.match(p) else 9999):
            lines.append(f"  {name}: {self.active[name]}")
        self.inventory_text.delete("1.0","end"); self.inventory_text.insert("1.0","\n".join(lines))

    def clear_rows(self):
        for row in self.rows: row.frame.destroy()
        self.rows.clear()
    def add_row(self, desired: DesiredPair):
        row=PairRow(self.rows_frame,self,desired);self.rows.append(row);self.regrid_rows()
    def remove_row(self,row:PairRow):
        row.frame.destroy();self.rows.remove(row);self.regrid_rows()
    def regrid_rows(self):
        for i,row in enumerate(self.rows):row.grid(i)
    def _next_free(self,start:int,used:Set[str])->str:
        n=start
        while True:
            name=f"COM{n}"
            if name not in used and name not in self.active and name not in self.busy:return name
            n+=1
    def load_default_suggestion(self):
        self.clear_rows();used=set();app_start,vector_start=15,101
        for name,kind in [("Cliente 1","CAT"),("Cliente 1","KEYING"),("Cliente 2","CAT"),("Cliente 2","KEYING")]:
            app=self._next_free(app_start,used);used.add(app);app_start=com_number(app)+1
            vector=self._next_free(vector_start,used);used.add(vector);vector_start=com_number(vector)+1
            self.add_row(DesiredPair(name,kind,app,vector))
        self.message_var.set("Sugestao criada sem reutilizar nomes atualmente ocupados/reservados.")
    def add_suggested_row(self):
        used={d.app_port for d in (r.desired() for r in self.rows)}|{d.vector_port for d in (r.desired() for r in self.rows)}
        app=self._next_free(15,used);used.add(app);vector=self._next_free(101,used)
        self.add_row(DesiredPair(f"Cliente {len(self.rows)+1}","CAT",app,vector))
    def validate_plan(self,desired:List[DesiredPair])->Optional[str]:
        if not desired:return "Nenhum par foi configurado."
        names=[];existing_ports={p.app_port for p in self.existing_pairs}|{p.vector_port for p in self.existing_pairs}
        for item in desired:
            try:com_number(item.app_port);com_number(item.vector_port)
            except ValueError as exc:return str(exc)
            if item.app_port==item.vector_port:return f"{item.name}: as duas pontas nao podem ser iguais."
            names += [item.app_port,item.vector_port]
            for port in (item.app_port,item.vector_port):
                if port in self.active and port not in existing_ports:return f"{port} pertence a um dispositivo ativo e nao sera sobrescrita."
                if port in self.busy and port not in existing_ports:return f"{port} esta reservada no ComDB. A v0.2 nao forca reservas/conflitos."
        if len(names)!=len(set(names)):return "Uma mesma COM aparece em mais de um endpoint do plano."
        return None

    def apply_plan(self):
        if not is_admin():messagebox.showerror("Permissao","Execute o Port Manager como Administrador para alterar o com0com.");return
        if not self.com0com:messagebox.showerror("com0com","com0com nao esta pronto. Use Recarregar inventario e verifique a mensagem exibida.");return
        desired=[row.desired() for row in self.rows];error=self.validate_plan(desired)
        if error:messagebox.showerror("Plano invalido",error);return
        current={(p.app_port,p.vector_port):p for p in self.existing_pairs};wanted={(d.app_port,d.vector_port) for d in desired}
        to_remove=[pair for key,pair in current.items() if key not in wanted];to_create=[d for d in desired if (d.app_port,d.vector_port) not in current]
        summary=["Alteracoes propostas:"]+[f"Remover #{p.index}: {p.app_port} <-> {p.vector_port}" for p in to_remove]+[f"Criar: {d.app_port} <-> {d.vector_port} ({d.name}/{d.kind})" for d in to_create]
        if not to_remove and not to_create:messagebox.showinfo("Sem alteracoes","O com0com ja corresponde ao plano exibido.");return
        if not messagebox.askyesno("Confirmar","\n".join(summary)):return

        def worker():
            total=max(1,len(to_remove)+len(to_create));done=0
            for pair in to_remove:
                self._progress_status("Removendo par virtual...",f"{pair.app_port} <-> {pair.vector_port}")
                self.com0com.remove_pair(pair.index);done+=1
            for d in to_create:
                self._progress_status("Validando portas antes da criacao...",f"{d.app_port} <-> {d.vector_port}")
                active=active_ports();busy=self.com0com.busy_names()
                if d.app_port in active or d.vector_port in active or d.app_port in busy or d.vector_port in busy:
                    raise RuntimeError(f"Conflito detectado antes de criar {d.app_port} <-> {d.vector_port}; operacao interrompida")
                self._progress_status("Criando par virtual...",f"{d.app_port} <-> {d.vector_port} ({done+1}/{total})")
                output=self.com0com.create_pair(d.app_port,d.vector_port)
                if "ERROR:" in output.upper():raise RuntimeError(output.strip())
                done+=1
            self._progress_status("Confirmando configuracao no com0com...")
            return self._collect_inventory()

        def success(result):
            self.com0com,self.existing_pairs,self.active,self.busy=result;self.setupc_var.set(f"com0com: {self.com0com.exe}");self._render_inventory()
            self.message_var.set("Configuracao aplicada. Verifique a lista e reinicie o Windows se o driver solicitar reboot.")
            messagebox.showinfo("Concluido","Plano aplicado ao com0com. Confira o inventario antes de iniciar o Vector Hub.")

        def error(exc:Exception):
            messagebox.showerror("Falha",str(exc));self.refresh_inventory(show_progress=True)

        self._begin_work("Aplicando configuracao",worker,success,error)


if __name__=="__main__":
    if sys.platform!="win32":raise SystemExit("GADX Vector Port Manager Phase C requer Windows")
    PortManagerApp().mainloop()
