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

APP_COM_MIN = 15
APP_COM_MAX = 40
VECTOR_COM_MIN = 101
VECTOR_COM_MAX = 140


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

        return [
            ComPair(index, sides["A"], sides["B"])
            for index, sides in sorted(grouped.items())
            if "A" in sides and "B" in sides
        ]

    def busy_names(self) -> Set[str]:
        output = self._interactive(["busynames *"])
        return {
            line.strip().upper()
            for line in output.splitlines()
            if COM_RE.match(line.strip().upper())
        }

    def create_pair(self, app_port: str, vector_port: str) -> str:
        return self._interactive([f"install PortName={app_port} PortName={vector_port}"])

    def remove_pair(self, index: int) -> str:
        return self._interactive([f"remove {index}"])


def active_ports() -> dict[str, str]:
    ports: dict[str, str] = {}
    for item in list_ports.comports():
        name = (item.device or "").upper()
        if name:
            ports[name] = item.description or item.hwid or "Porta serial"
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
        ttk.Label(
            body,
            text="GADX Vector Port Manager",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")

        self.status_var = tk.StringVar(value="Preparando...")
        ttk.Label(body, textvariable=self.status_var).pack(anchor="w", pady=(12, 8))

        self.progress = ttk.Progressbar(body, mode="indeterminate", length=420)
        self.progress.pack(fill="x")

        self.detail_var = tk.StringVar(value="Iniciando operacao...")
        ttk.Label(
            body,
            textvariable=self.detail_var,
            foreground="#555555",
        ).pack(anchor="w", pady=(8, 0))

        self.progress.start(12)
        self.update_idletasks()
        self._center(parent)

    def _center(self, parent: tk.Misc) -> None:
        parent.update_idletasks()
        self.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    def update_status(self, status: str, detail: str = "") -> None:
        self.status_var.set(status)
        self.detail_var.set(detail)
        self.update_idletasks()

    def close(self) -> None:
        try:
            self.progress.stop()
            self.grab_release()
            self.destroy()
        except tk.TclError:
            pass


class ClientRow:
    """One visual row represents one software client with CAT and KEYING."""

    def __init__(self, parent: tk.Misc, manager: "PortManagerApp", desired: DesiredClient):
        self.manager = manager
        self.frame = ttk.Frame(parent)

        self.name = tk.StringVar(value=desired.name)
        self.cat_type = tk.StringVar(value=desired.cat_type)
        self.cat_app = tk.StringVar(value=desired.cat_app)
        self.cat_vector = tk.StringVar(value=desired.cat_vector)
        self.key_type = tk.StringVar(value=desired.key_type)
        self.key_app = tk.StringVar(value=desired.key_app)
        self.key_vector = tk.StringVar(value=desired.key_vector)

        self.name_entry = ttk.Entry(self.frame, textvariable=self.name, width=14)
        self.cat_type_combo = ttk.Combobox(
            self.frame, textvariable=self.cat_type, values=("CAT", "NONE"), width=8, state="readonly"
        )
        self.cat_app_combo = ttk.Combobox(self.frame, textvariable=self.cat_app, width=9, state="readonly")
        self.cat_vector_combo = ttk.Combobox(self.frame, textvariable=self.cat_vector, width=9, state="readonly")
        self.key_type_combo = ttk.Combobox(
            self.frame, textvariable=self.key_type, values=("KEYING", "NONE"), width=9, state="readonly"
        )
        self.key_app_combo = ttk.Combobox(self.frame, textvariable=self.key_app, width=9, state="readonly")
        self.key_vector_combo = ttk.Combobox(self.frame, textvariable=self.key_vector, width=9, state="readonly")

        self.name_entry.grid(row=0, column=0, padx=(0, 6), pady=3, sticky="ew")
        self.cat_type_combo.grid(row=0, column=1, padx=3)
        self.cat_app_combo.grid(row=0, column=2, padx=3)
        ttk.Label(self.frame, text="↔").grid(row=0, column=3, padx=1)
        self.cat_vector_combo.grid(row=0, column=4, padx=3)

        ttk.Separator(self.frame, orient="vertical").grid(row=0, column=5, sticky="ns", padx=8)

        self.key_type_combo.grid(row=0, column=6, padx=3)
        self.key_app_combo.grid(row=0, column=7, padx=3)
        ttk.Label(self.frame, text="↔").grid(row=0, column=8, padx=1)
        self.key_vector_combo.grid(row=0, column=9, padx=3)
        ttk.Button(
            self.frame,
            text="Remover",
            command=lambda: manager.remove_client_row(self),
        ).grid(row=0, column=10, padx=(9, 0))

        self.cat_type_combo.bind("<<ComboboxSelected>>", lambda _e: self._sync_enabled_state())
        self.key_type_combo.bind("<<ComboboxSelected>>", lambda _e: self._sync_enabled_state())

        self.cat_app_combo.configure(postcommand=lambda: self._refresh_combo(self.cat_app_combo, "app", self.cat_app.get()))
        self.cat_vector_combo.configure(postcommand=lambda: self._refresh_combo(self.cat_vector_combo, "vector", self.cat_vector.get()))
        self.key_app_combo.configure(postcommand=lambda: self._refresh_combo(self.key_app_combo, "app", self.key_app.get()))
        self.key_vector_combo.configure(postcommand=lambda: self._refresh_combo(self.key_vector_combo, "vector", self.key_vector.get()))

        self._refresh_all_choices()
        self._sync_enabled_state()

    def _refresh_combo(self, combo: ttk.Combobox, side: str, current: str) -> None:
        combo["values"] = self.manager.port_choices(side, current=current, owner=self)

    def _refresh_all_choices(self) -> None:
        self._refresh_combo(self.cat_app_combo, "app", self.cat_app.get())
        self._refresh_combo(self.cat_vector_combo, "vector", self.cat_vector.get())
        self._refresh_combo(self.key_app_combo, "app", self.key_app.get())
        self._refresh_combo(self.key_vector_combo, "vector", self.key_vector.get())

    def _sync_enabled_state(self) -> None:
        cat_enabled = self.cat_type.get() != "NONE"
        key_enabled = self.key_type.get() != "NONE"

        self.cat_app_combo.configure(state="readonly" if cat_enabled else "disabled")
        self.cat_vector_combo.configure(state="readonly" if cat_enabled else "disabled")
        self.key_app_combo.configure(state="readonly" if key_enabled else "disabled")
        self.key_vector_combo.configure(state="readonly" if key_enabled else "disabled")

    def grid(self, row: int) -> None:
        self.frame.grid(row=row, column=0, sticky="w")

    def selected_ports(self) -> Set[str]:
        ports: Set[str] = set()
        if self.cat_type.get() != "NONE":
            ports.update({self.cat_app.get().strip().upper(), self.cat_vector.get().strip().upper()})
        if self.key_type.get() != "NONE":
            ports.update({self.key_app.get().strip().upper(), self.key_vector.get().strip().upper()})
        return {p for p in ports if p}

    def desired_client(self) -> DesiredClient:
        return DesiredClient(
            name=self.name.get().strip() or "Cliente",
            cat_type=self.cat_type.get().strip().upper() or "NONE",
            cat_app=self.cat_app.get().strip().upper(),
            cat_vector=self.cat_vector.get().strip().upper(),
            key_type=self.key_type.get().strip().upper() or "NONE",
            key_app=self.key_app.get().strip().upper(),
            key_vector=self.key_vector.get().strip().upper(),
        )

    def desired_pairs(self) -> List[DesiredPair]:
        client = self.desired_client()
        result: List[DesiredPair] = []
        if client.cat_type != "NONE":
            result.append(DesiredPair(client.name, "CAT", client.cat_app, client.cat_vector))
        if client.key_type != "NONE":
            result.append(DesiredPair(client.name, "KEYING", client.key_app, client.key_vector))
        return result


class PortManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GADX Vector Port Manager - Phase C SPIKE")
        self.geometry("1120x650")
        self.minsize(1040, 580)

        self.rows: List[ClientRow] = []
        self.com0com: Optional[Com0Com] = None
        self.existing_pairs: List[ComPair] = []
        self.active: dict[str, str] = {}
        self.busy: Set[str] = set()
        self._work_queue: "queue.Queue[tuple]" = queue.Queue()
        self._progress: Optional[ProgressDialog] = None

        self._build()
        self.after(150, lambda: self.refresh_inventory(show_progress=True, initial=True))

    def _build(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(
            top,
            text="GADX Vector Port Manager",
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left")
        self.admin_var = tk.StringVar()
        ttk.Label(top, textvariable=self.admin_var).pack(side="right")

        status = ttk.LabelFrame(self, text="Inventario da maquina", padding=8)
        status.pack(fill="x", padx=10, pady=(0, 8))
        self.setupc_var = tk.StringVar(value="com0com: aguardando inventario...")
        ttk.Label(status, textvariable=self.setupc_var).pack(anchor="w")
        self.inventory_text = tk.Text(status, height=7, wrap="none")
        self.inventory_text.pack(fill="x", pady=(4, 0))

        plan = ttk.LabelFrame(self, text="Clientes e pares virtuais desejados", padding=8)
        plan.pack(fill="both", expand=True, padx=10, pady=8)

        header = ttk.Frame(plan)
        header.pack(anchor="w", fill="x", pady=(0, 3))
        headers = [
            ("Cliente", 14),
            ("CAT Tipo", 8),
            ("CAT COM", 9),
            ("", 2),
            ("CAT Vector", 9),
            ("", 2),
            ("KEY Tipo", 9),
            ("KEY COM", 9),
            ("", 2),
            ("KEY Vector", 9),
            ("", 9),
        ]
        for col, (text, width) in enumerate(headers):
            ttk.Label(header, text=text, width=width, anchor="w").grid(
                row=0, column=col, padx=3 if col not in (0, 5, 10) else 0, sticky="w"
            )

        self.rows_frame = ttk.Frame(plan)
        self.rows_frame.pack(anchor="w", fill="x", pady=2)

        buttons = ttk.Frame(plan)
        buttons.pack(fill="x", pady=10)
        ttk.Button(buttons, text="+ Adicionar cliente", command=self.add_suggested_client).pack(side="left")
        ttk.Button(buttons, text="Sugestao 2 clientes", command=self.load_default_suggestion).pack(side="left", padx=6)
        ttk.Button(
            buttons,
            text="Recarregar inventario",
            command=lambda: self.refresh_inventory(show_progress=True),
        ).pack(side="left")
        ttk.Button(buttons, text="Aplicar configuracao", command=self.apply_plan).pack(side="right")

        self.message_var = tk.StringVar(
            value="Fase C v0.4: uma linha por cliente; COMs selecionadas por lista de portas disponiveis."
        )
        ttk.Label(self, textvariable=self.message_var, padding=(10, 4)).pack(fill="x")

    def _begin_work(
        self,
        title: str,
        worker: Callable[[], object],
        on_success: Callable[[object], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        if self._progress is not None:
            return

        self._progress = ProgressDialog(self, title)

        def run() -> None:
            try:
                self._work_queue.put(("ok", worker()))
            except Exception as exc:
                self._work_queue.put(("error", exc))

        threading.Thread(target=run, daemon=True).start()

        def poll() -> None:
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

    def _progress_status(self, status: str, detail: str = "") -> None:
        self.after(
            0,
            lambda: self._progress and self._progress.update_status(status, detail),
        )

    def _collect_inventory(self):
        self._progress_status(
            "Etapa 1 de 5 - Lendo portas seriais...",
            "Consultando dispositivos COM ativos no Windows",
        )
        active = active_ports()

        self._progress_status(
            "Etapa 2 de 5 - Localizando com0com...",
            "Procurando setupc.exe",
        )
        com0com = Com0Com.discover()

        self._progress_status(
            "Etapa 3 de 5 - Consultando pares virtuais...",
            str(com0com.exe),
        )
        pairs = com0com.list_pairs()

        self._progress_status(
            "Etapa 4 de 5 - Consultando portas reservadas...",
            "Lendo nomes registrados no ComDB",
        )
        busy = com0com.busy_names()

        self._progress_status(
            "Etapa 5 de 5 - Atualizando inventario...",
            f"{len(pairs)} par(es) virtual(is) encontrado(s)",
        )
        return com0com, pairs, active, busy

    def refresh_inventory(self, show_progress: bool = False, initial: bool = False) -> None:
        self.admin_var.set("Administrador: SIM" if is_admin() else "Administrador: NAO")

        def success(result) -> None:
            self.com0com, self.existing_pairs, self.active, self.busy = result
            self.setupc_var.set(f"com0com: {self.com0com.exe}")
            self._render_inventory()
            self.refresh_row_choices()
            if initial and not self.existing_pairs:
                self.load_default_suggestion()

        def error(exc: Exception) -> None:
            self.com0com = None
            self.existing_pairs = []
            self.active = active_ports()
            self.busy = set()
            if isinstance(exc, Com0ComTimeout):
                self.setupc_var.set(str(exc))
            else:
                self.setupc_var.set(f"com0com indisponivel: {exc}")
            self._render_inventory()
            self.refresh_row_choices()
            if initial:
                self.load_default_suggestion()

        if show_progress:
            self._begin_work("Carregando inventario", self._collect_inventory, success, error)
        else:
            try:
                success(self._collect_inventory())
            except Exception as exc:
                error(exc)

    def _render_inventory(self) -> None:
        lines: List[str] = []
        if self.existing_pairs:
            lines.append("Pares com0com existentes:")
            for pair in self.existing_pairs:
                lines.append(f"  #{pair.index}: {pair.app_port} <-> {pair.vector_port}")
        else:
            lines.append("Pares com0com existentes: nenhum")

        lines.extend(["", "Portas seriais ativas:"])
        for name in sorted(
            self.active,
            key=lambda port: com_number(port) if COM_RE.match(port) else 9999,
        ):
            lines.append(f"  {name}: {self.active[name]}")

        self.inventory_text.delete("1.0", "end")
        self.inventory_text.insert("1.0", "\n".join(lines))

    def existing_pair_ports(self) -> Set[str]:
        result: Set[str] = set()
        for pair in self.existing_pairs:
            result.update({pair.app_port, pair.vector_port})
        return result

    def ports_selected_by_other_rows(self, owner: Optional[ClientRow]) -> Set[str]:
        result: Set[str] = set()
        for row in self.rows:
            if row is not owner:
                result.update(row.selected_ports())
        return result

    def port_choices(self, side: str, current: str = "", owner: Optional[ClientRow] = None) -> List[str]:
        """Return selectable free ports, while preserving existing/current mappings."""
        current = current.strip().upper()
        existing = self.existing_pair_ports()
        selected_elsewhere = self.ports_selected_by_other_rows(owner)

        if side == "app":
            start, end = APP_COM_MIN, APP_COM_MAX
        else:
            start, end = VECTOR_COM_MIN, VECTOR_COM_MAX

        choices: List[str] = []
        for number in range(start, end + 1):
            port = f"COM{number}"
            occupied_by_device = port in self.active and port not in existing
            reserved = port in self.busy and port not in existing
            already_selected = port in selected_elsewhere
            if not occupied_by_device and not reserved and not already_selected:
                choices.append(port)

        if current and current not in choices:
            choices.insert(0, current)

        return choices

    def refresh_row_choices(self) -> None:
        for row in self.rows:
            row._refresh_all_choices()

    def clear_rows(self) -> None:
        for row in self.rows:
            row.frame.destroy()
        self.rows.clear()

    def add_client_row(self, desired: DesiredClient) -> None:
        row = ClientRow(self.rows_frame, self, desired)
        self.rows.append(row)
        self.regrid_rows()
        self.refresh_row_choices()

    def remove_client_row(self, row: ClientRow) -> None:
        row.frame.destroy()
        self.rows.remove(row)
        self.regrid_rows()
        self.refresh_row_choices()

    def regrid_rows(self) -> None:
        for index, row in enumerate(self.rows):
            row.grid(index)

    def _next_free(self, start: int, used: Set[str]) -> str:
        candidate = start
        while True:
            name = f"COM{candidate}"
            existing = self.existing_pair_ports()
            if (
                name not in used
                and (name not in self.active or name in existing)
                and (name not in self.busy or name in existing)
            ):
                return name
            candidate += 1

    def load_default_suggestion(self) -> None:
        self.clear_rows()
        used: Set[str] = set()
        app_next = APP_COM_MIN
        vector_next = VECTOR_COM_MIN

        for client_index in range(1, 3):
            cat_app = self._next_free(app_next, used)
            used.add(cat_app)
            app_next = com_number(cat_app) + 1

            cat_vector = self._next_free(vector_next, used)
            used.add(cat_vector)
            vector_next = com_number(cat_vector) + 1

            key_app = self._next_free(app_next, used)
            used.add(key_app)
            app_next = com_number(key_app) + 1

            key_vector = self._next_free(vector_next, used)
            used.add(key_vector)
            vector_next = com_number(key_vector) + 1

            self.add_client_row(
                DesiredClient(
                    name=f"Cliente {client_index}",
                    cat_type="CAT",
                    cat_app=cat_app,
                    cat_vector=cat_vector,
                    key_type="KEYING",
                    key_app=key_app,
                    key_vector=key_vector,
                )
            )

        self.message_var.set(
            "Sugestao criada: cada cliente recebeu CAT + KEYING sem reutilizar COMs ocupadas/reservadas."
        )

    def add_suggested_client(self) -> None:
        used = set()
        for row in self.rows:
            used.update(row.selected_ports())

        cat_app = self._next_free(APP_COM_MIN, used)
        used.add(cat_app)
        cat_vector = self._next_free(VECTOR_COM_MIN, used)
        used.add(cat_vector)
        key_app = self._next_free(APP_COM_MIN, used)
        used.add(key_app)
        key_vector = self._next_free(VECTOR_COM_MIN, used)

        self.add_client_row(
            DesiredClient(
                name=f"Cliente {len(self.rows) + 1}",
                cat_type="CAT",
                cat_app=cat_app,
                cat_vector=cat_vector,
                key_type="KEYING",
                key_app=key_app,
                key_vector=key_vector,
            )
        )

    def desired_pairs(self) -> List[DesiredPair]:
        result: List[DesiredPair] = []
        for row in self.rows:
            result.extend(row.desired_pairs())
        return result

    def validate_plan(self, desired: List[DesiredPair]) -> Optional[str]:
        if not desired:
            return "Nenhum CAT ou KEYING foi configurado."

        endpoint_names: List[str] = []
        existing_ports = self.existing_pair_ports()

        for item in desired:
            try:
                com_number(item.app_port)
                com_number(item.vector_port)
            except ValueError as exc:
                return str(exc)

            if item.app_port == item.vector_port:
                return f"{item.name}/{item.kind}: as duas pontas nao podem ser iguais."

            endpoint_names.extend([item.app_port, item.vector_port])

            for port in (item.app_port, item.vector_port):
                if port in self.active and port not in existing_ports:
                    return f"{port} pertence a um dispositivo ativo e nao sera sobrescrita."
                if port in self.busy and port not in existing_ports:
                    return f"{port} esta reservada no ComDB. A v0.4 nao forca reservas/conflitos."

        if len(endpoint_names) != len(set(endpoint_names)):
            return "Uma mesma COM aparece em mais de um endpoint do plano."

        return None

    def apply_plan(self) -> None:
        if not is_admin():
            messagebox.showerror(
                "Permissao",
                "Execute o Port Manager como Administrador para alterar o com0com.",
            )
            return

        if not self.com0com:
            messagebox.showerror(
                "com0com",
                "com0com nao esta pronto. Use Recarregar inventario e verifique a mensagem exibida.",
            )
            return

        desired = self.desired_pairs()
        error = self.validate_plan(desired)
        if error:
            messagebox.showerror("Plano invalido", error)
            return

        current = {(p.app_port, p.vector_port): p for p in self.existing_pairs}
        wanted = {(d.app_port, d.vector_port) for d in desired}
        to_remove = [pair for key, pair in current.items() if key not in wanted]
        to_create = [d for d in desired if (d.app_port, d.vector_port) not in current]

        summary = ["Alteracoes propostas:"]
        summary.extend(
            f"Remover #{p.index}: {p.app_port} <-> {p.vector_port}" for p in to_remove
        )
        summary.extend(
            f"Criar: {d.app_port} <-> {d.vector_port} ({d.name}/{d.kind})" for d in to_create
        )

        if not to_remove and not to_create:
            messagebox.showinfo(
                "Sem alteracoes",
                "O com0com ja corresponde ao plano exibido.",
            )
            return

        if not messagebox.askyesno("Confirmar", "\n".join(summary)):
            return

        def worker():
            total = max(1, len(to_remove) + len(to_create))
            done = 0

            for pair in to_remove:
                self._progress_status(
                    f"Operacao {done + 1} de {total} - Removendo par...",
                    f"{pair.app_port} <-> {pair.vector_port}",
                )
                self.com0com.remove_pair(pair.index)
                done += 1

            for item in to_create:
                self._progress_status(
                    f"Operacao {done + 1} de {total} - Validando portas...",
                    f"{item.app_port} <-> {item.vector_port}",
                )
                active = active_ports()
                busy = self.com0com.busy_names()
                if (
                    item.app_port in active
                    or item.vector_port in active
                    or item.app_port in busy
                    or item.vector_port in busy
                ):
                    raise RuntimeError(
                        f"Conflito detectado antes de criar {item.app_port} <-> {item.vector_port}; operacao interrompida"
                    )

                self._progress_status(
                    f"Operacao {done + 1} de {total} - Criando par virtual...",
                    f"{item.app_port} <-> {item.vector_port} ({item.name}/{item.kind})",
                )
                output = self.com0com.create_pair(item.app_port, item.vector_port)
                if "ERROR:" in output.upper():
                    raise RuntimeError(output.strip())
                done += 1

            self._progress_status(
                "Finalizando - Confirmando configuracao...",
                "Relendo o inventario do com0com",
            )
            return self._collect_inventory()

        def success(result) -> None:
            self.com0com, self.existing_pairs, self.active, self.busy = result
            self.setupc_var.set(f"com0com: {self.com0com.exe}")
            self._render_inventory()
            self.refresh_row_choices()
            self.message_var.set(
                "Configuracao aplicada. Verifique a lista e reinicie o Windows se o driver solicitar reboot."
            )
            messagebox.showinfo(
                "Concluido",
                "Plano aplicado ao com0com. Confira o inventario antes de iniciar o Vector Hub.",
            )

        def failure(exc: Exception) -> None:
            messagebox.showerror("Falha", str(exc))
            self.refresh_inventory(show_progress=True)

        self._begin_work("Aplicando configuracao", worker, success, failure)


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("GADX Vector Port Manager Phase C requer Windows")
    PortManagerApp().mainloop()
