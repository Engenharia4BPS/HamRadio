from __future__ import annotations

import ctypes
import re
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import List, Optional, Set

from serial.tools import list_ports


SETUPC_CANDIDATES = [
    Path(r"C:\Program Files (x86)\com0com\setupc.exe"),
    Path(r"C:\Program Files\com0com\setupc.exe"),
    Path(r"C:\Ham\com0com\setupc.exe"),
    Path(r"D:\Ham\com0com\setupc.exe"),
]

PAIR_RE = re.compile(r"\bCNC([AB])(\d+)\s+.*?(?:PortName|RealPortName)=(COM\d+)", re.I)
COM_RE = re.compile(r"^COM(\d+)$", re.I)


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


class Com0Com:
    def __init__(self, exe: Path):
        self.exe = exe

    @classmethod
    def discover(cls) -> "Com0Com":
        for candidate in SETUPC_CANDIDATES:
            if candidate.exists():
                return cls(candidate)
        raise FileNotFoundError("setupc.exe do com0com nao foi encontrado")

    def _interactive(self, commands: List[str]) -> str:
        payload = "\n".join(commands + ["quit", ""])
        proc = subprocess.run(
            [str(self.exe)],
            input=payload,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(self.exe.parent),
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
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
        self._build()
        self.refresh_inventory()
        if not self.existing_pairs:
            self.load_default_suggestion()

    def _build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="GADX Vector Port Manager", font=("Segoe UI", 16, "bold")).pack(side="left")
        self.admin_var = tk.StringVar()
        ttk.Label(top, textvariable=self.admin_var).pack(side="right")

        status = ttk.LabelFrame(self, text="Inventario da maquina", padding=8)
        status.pack(fill="x", padx=10, pady=(0, 8))
        self.setupc_var = tk.StringVar(value="com0com: procurando...")
        ttk.Label(status, textvariable=self.setupc_var).pack(anchor="w")
        self.inventory_text = tk.Text(status, height=7, wrap="none")
        self.inventory_text.pack(fill="x", pady=(4, 0))

        plan = ttk.LabelFrame(self, text="Pares virtuais desejados", padding=8)
        plan.pack(fill="both", expand=True, padx=10, pady=8)

        header = ttk.Frame(plan)
        header.pack(fill="x")
        for text, width in [("Cliente", 16), ("Tipo", 10), ("Aplicativo", 10), ("", 2), ("Vector", 10), ("", 8)]:
            ttk.Label(header, text=text, width=width).pack(side="left", padx=3)

        self.rows_frame = ttk.Frame(plan)
        self.rows_frame.pack(fill="x", pady=4)

        buttons = ttk.Frame(plan)
        buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="+ Adicionar par", command=self.add_suggested_row).pack(side="left")
        ttk.Button(buttons, text="Sugestao 4 pares", command=self.load_default_suggestion).pack(side="left", padx=6)
        ttk.Button(buttons, text="Recarregar inventario", command=self.refresh_inventory).pack(side="left")
        ttk.Button(buttons, text="Aplicar configuracao", command=self.apply_plan).pack(side="right")

        self.message_var = tk.StringVar(value="Fase C v0.1: conflitos nunca sao forçados automaticamente.")
        ttk.Label(self, textvariable=self.message_var, padding=(10, 4)).pack(fill="x")

    def refresh_inventory(self):
        self.admin_var.set("Administrador: SIM" if is_admin() else "Administrador: NAO")
        self.active = active_ports()
        try:
            self.com0com = Com0Com.discover()
            self.setupc_var.set(f"com0com: {self.com0com.exe}")
            self.existing_pairs = self.com0com.list_pairs()
            self.busy = self.com0com.busy_names()
        except Exception as exc:
            self.com0com = None
            self.existing_pairs = []
            self.busy = set()
            self.setupc_var.set(f"com0com indisponivel: {exc}")

        lines = []
        if self.existing_pairs:
            lines.append("Pares com0com existentes:")
            for pair in self.existing_pairs:
                lines.append(f"  #{pair.index}: {pair.app_port} <-> {pair.vector_port}")
        else:
            lines.append("Pares com0com existentes: nenhum")
        lines.append("")
        lines.append("Portas seriais ativas:")
        for name in sorted(self.active, key=lambda p: com_number(p) if COM_RE.match(p) else 9999):
            lines.append(f"  {name}: {self.active[name]}")
        self.inventory_text.delete("1.0", "end")
        self.inventory_text.insert("1.0", "\n".join(lines))

    def clear_rows(self):
        for row in self.rows:
            row.frame.destroy()
        self.rows.clear()

    def add_row(self, desired: DesiredPair):
        row = PairRow(self.rows_frame, self, desired)
        self.rows.append(row)
        self.regrid_rows()

    def remove_row(self, row: PairRow):
        row.frame.destroy()
        self.rows.remove(row)
        self.regrid_rows()

    def regrid_rows(self):
        for index, row in enumerate(self.rows):
            row.grid(index)

    def _next_free(self, start: int, used: Set[str]) -> str:
        candidate = start
        while True:
            name = f"COM{candidate}"
            if name not in used and name not in self.active and name not in self.busy:
                return name
            candidate += 1

    def load_default_suggestion(self):
        self.clear_rows()
        used = set()
        app_start, vector_start = 15, 101
        defaults = [
            ("Cliente 1", "CAT"),
            ("Cliente 1", "KEYING"),
            ("Cliente 2", "CAT"),
            ("Cliente 2", "KEYING"),
        ]
        for offset, (name, kind) in enumerate(defaults):
            app = self._next_free(app_start, used)
            used.add(app)
            app_start = com_number(app) + 1
            vector = self._next_free(vector_start, used)
            used.add(vector)
            vector_start = com_number(vector) + 1
            self.add_row(DesiredPair(name, kind, app, vector))
        self.message_var.set("Sugestao criada sem reutilizar nomes atualmente ocupados/reservados.")

    def add_suggested_row(self):
        used = {d.app_port for d in (r.desired() for r in self.rows)} | {d.vector_port for d in (r.desired() for r in self.rows)}
        app = self._next_free(15, used)
        used.add(app)
        vector = self._next_free(101, used)
        self.add_row(DesiredPair(f"Cliente {len(self.rows)+1}", "CAT", app, vector))

    def validate_plan(self, desired: List[DesiredPair]) -> Optional[str]:
        if not desired:
            return "Nenhum par foi configurado."
        names = []
        existing_ports = {p.app_port for p in self.existing_pairs} | {p.vector_port for p in self.existing_pairs}
        for item in desired:
            try:
                com_number(item.app_port); com_number(item.vector_port)
            except ValueError as exc:
                return str(exc)
            if item.app_port == item.vector_port:
                return f"{item.name}: as duas pontas nao podem ser iguais."
            names.extend([item.app_port, item.vector_port])
            for port in (item.app_port, item.vector_port):
                if port in self.active and port not in existing_ports:
                    return f"{port} pertence a um dispositivo ativo e nao sera sobrescrita."
                if port in self.busy and port not in existing_ports:
                    return f"{port} esta reservada no ComDB. A v0.1 nao força reservas/conflitos."
        if len(names) != len(set(names)):
            return "Uma mesma COM aparece em mais de um endpoint do plano."
        return None

    def apply_plan(self):
        if not is_admin():
            messagebox.showerror("Permissao", "Execute o Port Manager como Administrador para alterar o com0com.")
            return
        if not self.com0com:
            messagebox.showerror("com0com", "setupc.exe nao foi encontrado.")
            return
        desired = [row.desired() for row in self.rows]
        error = self.validate_plan(desired)
        if error:
            messagebox.showerror("Plano invalido", error)
            return

        current = {(p.app_port, p.vector_port): p for p in self.existing_pairs}
        wanted = {(d.app_port, d.vector_port) for d in desired}
        to_remove = [pair for key, pair in current.items() if key not in wanted]
        to_create = [d for d in desired if (d.app_port, d.vector_port) not in current]

        summary = ["Alteracoes propostas:"]
        summary += [f"Remover #{p.index}: {p.app_port} <-> {p.vector_port}" for p in to_remove]
        summary += [f"Criar: {d.app_port} <-> {d.vector_port} ({d.name}/{d.kind})" for d in to_create]
        if not to_remove and not to_create:
            messagebox.showinfo("Sem alteracoes", "O com0com ja corresponde ao plano exibido.")
            return
        if not messagebox.askyesno("Confirmar", "\n".join(summary)):
            return

        try:
            for pair in to_remove:
                self.com0com.remove_pair(pair.index)
            self.refresh_inventory()
            # Revalidar depois das remocoes: nunca criar sobre conflito residual.
            for d in to_create:
                self.active = active_ports(); self.busy = self.com0com.busy_names()
                if d.app_port in self.active or d.vector_port in self.active or d.app_port in self.busy or d.vector_port in self.busy:
                    raise RuntimeError(f"Conflito detectado antes de criar {d.app_port} <-> {d.vector_port}; operacao interrompida")
                output = self.com0com.create_pair(d.app_port, d.vector_port)
                if "ERROR:" in output.upper():
                    raise RuntimeError(output.strip())
            self.refresh_inventory()
            self.message_var.set("Configuracao aplicada. Verifique a lista e reinicie o Windows se o driver solicitar reboot.")
            messagebox.showinfo("Concluido", "Plano aplicado ao com0com. Confira o inventario antes de iniciar o Vector Hub.")
        except Exception as exc:
            self.refresh_inventory()
            messagebox.showerror("Falha", str(exc))


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("GADX Vector Port Manager Phase C requer Windows")
    PortManagerApp().mainloop()
