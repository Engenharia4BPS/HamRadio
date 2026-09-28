from __future__ import annotations

import configparser
import ctypes
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from serial.tools import list_ports


CONFIG_PATH = Path(r"C:\Ham\GADX-Vector\config\vector.ini")

SETUPC_CANDIDATES = [
    Path(r"C:\Program Files (x86)\com0com\setupc.exe"),
    Path(r"C:\Program Files\com0com\setupc.exe"),
    Path(r"C:\Ham\com0com\setupc.exe"),
    Path(r"D:\Ham\com0com\setupc.exe"),
]

PAIR_RE = re.compile(
    r"\bCNC([AB])(\d+)\s+.*?(?:PortName|RealPortName)=(COM\d+)", re.I
)
COM_RE = re.compile(r"^COM(\d+)$", re.I)
CLIENT_RE = re.compile(r"^client(\d+)$", re.I)

CNW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SU = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)

APP_MIN = 9
APP_MAX = 40
FSK_APP_MAX = 20
VEC_MIN = 100
VEC_MAX = 140


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
class KeyingChannel:
    index: int
    name: str
    vector_port: str
    ptt_input: str
    key_input: str


@dataclass
class DesiredClient:
    name: str

    cat_type: str = "NONE"
    cat_app: str = ""
    cat_vector: str = ""

    cw_type: str = "NONE"
    cw_app: str = ""
    cw_vector: str = ""
    cw_ptt_input: str = "RTS"
    cw_key_input: str = "DTR"

    fsk_type: str = "NONE"
    fsk_app: str = ""
    fsk_vector: str = ""
    fsk_ptt_input: str = "RTS"
    fsk_key_input: str = "DTR"


class Com0Com:
    def __init__(self, exe: Path):
        self.exe = exe

    @classmethod
    def discover(cls) -> "Com0Com":
        for candidate in SETUPC_CANDIDATES:
            if candidate.exists():
                return cls(candidate)
        raise FileNotFoundError("setupc.exe do com0com nao foi encontrado")

    def startup_info(self):
        if sys.platform != "win32":
            return None
        info = subprocess.STARTUPINFO()
        info.dwFlags |= SU
        info.wShowWindow = 0
        return info

    def run_result(self, args, timeout=8, input_text=None):
        return subprocess.run(
            [str(self.exe)] + args,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(self.exe.parent),
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            startupinfo=self.startup_info(),
            creationflags=CNW,
        )

    def run(self, args, timeout=8, input_text=None):
        return self.run_result(args, timeout, input_text).stdout or ""

    def query(self, args, command):
        try:
            proc = self.run_result(args)
            if proc.returncode == 0:
                return proc.stdout or ""
        except Exception:
            pass

        return self.run([], 12, "\n".join([command, "quit", ""]))

    def list_pairs(self):
        grouped = {}
        for line in self.query(["list"], "list").splitlines():
            match = PAIR_RE.search(line)
            if not match:
                continue

            side, index, port = match.groups()
            grouped.setdefault(int(index), {})[side.upper()] = port.upper()

        return [
            ComPair(index, ports["A"], ports["B"])
            for index, ports in sorted(grouped.items())
            if "A" in ports and "B" in ports
        ]

    def busy_names(self):
        return {
            line.strip().upper()
            for line in self.query(["busynames", "*"], "busynames *").splitlines()
            if COM_RE.match(line.strip().upper())
        }

    def create_pair(self, app_port, vector_port):
        try:
            return self.run(
                ["install", f"PortName={app_port}", f"PortName={vector_port}"],
                60,
            )
        except subprocess.TimeoutExpired:
            # com0com pode concluir a criacao depois de setupc exceder o timeout.
            time.sleep(2)
            for pair in self.list_pairs():
                if (
                    pair.app_port == app_port.upper()
                    and pair.vector_port == vector_port.upper()
                ):
                    return "Par criado; setupc excedeu o tempo de resposta."
            raise

    def remove_pair(self, index):
        return self.run(["remove", str(index)], 20)


def active_ports():
    return {
        (item.device or "").upper(): (item.description or item.hwid or "Porta serial")
        for item in list_ports.comports()
        if item.device
    }


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def com_number(value):
    match = COM_RE.match(value.strip().upper())
    if not match:
        raise ValueError(f"Porta invalida: {value}")
    return int(match.group(1))


class Tip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.after_id = None
        self.popup = None
        widget.bind("<Enter>", self.enter, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def enter(self, _event=None):
        self.after_id = self.widget.after(550, self.show)

    def show(self):
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.popup = tk.Toplevel(self.widget)
        self.popup.overrideredirect(True)
        self.popup.geometry(f"+{x}+{y}")
        tk.Label(
            self.popup,
            text=self.text,
            justify="left",
            relief="solid",
            borderwidth=1,
            background="#ffffe0",
            padx=7,
            pady=5,
            wraplength=420,
        ).pack()

    def hide(self, _event=None):
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

        if self.popup:
            self.popup.destroy()
            self.popup = None


class Progress(tk.Toplevel):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()

        body = ttk.Frame(self, padding=18)
        body.pack()
        ttk.Label(
            body,
            text="GADX Vector Port Manager",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")

        self.status = tk.StringVar(value="Preparando...")
        ttk.Label(body, textvariable=self.status).pack(anchor="w", pady=10)

        self.progress = ttk.Progressbar(body, mode="indeterminate", length=420)
        self.progress.pack()
        self.progress.start(12)

    def close(self):
        self.progress.stop()
        self.destroy()


class Help(tk.Toplevel):
    TEXT = """GADX VECTOR PORT MANAGER - v0.15

OBJETIVO
Organizar as portas virtuais do GADX Vector por cliente e por funcao.

A TELA E DIVIDIDA EM QUATRO GRUPOS
CLIENTE
Nome do programa ou integracao, por exemplo LogHX, N1MM ou OmniRig.

CAT
Porta de controle do radio: frequencia, modo e comandos.
Aplicativo = porta configurada no programa.
Vector = outra ponta do par com0com, aberta pelo Vector Hub.

CW KEYING
Canal para PTT e CW.
O tipo CW representa PTT + KEYING.
O tipo PTT representa somente PTT.
Em novos canais CW, o padrao e:
  RTS = PTT
  DTR = CW KEYING

FSK KEYING
Canal independente para RTTY/FSK.
Em novos canais FSK, o padrao e:
  RTS = PTT
  DTR = FSK KEYING

A porta de aplicativo do FSK e limitada a COM9..COM20 para manter
compatibilidade com MMTTY/EXTFSK.

UM MESMO CLIENTE PODE TER CAT + CW + FSK
Exemplo N1MM:
  CAT         COM15 <-> COM103
  CW KEYING   COM30 <-> COM104
  FSK KEYING  COM18 <-> COM107

VÁRIOS PROGRAMAS RTTY
Cada cliente pode ter seu proprio canal FSK. Exemplo:
  N1MM   FSK COM18 <-> COM107
  Fldigi FSK COM17 <-> COM108
  LogHX  FSK COM14 <-> COM109

O Vector converge os canais:
  PTT    -> rigctld
  KEYING -> saida fisica configurada no vector.ini

CARREGAR CONFIGURACAO ATUAL
Le vector.ini, encontra as pontas correspondentes no com0com e agrupa
automaticamente canais FSK com o cliente principal.

Compatibilidade:
  um antigo client chamado MMTTY e associado ao N1MM quando houver
  um cliente N1MM na configuracao.

APLICAR CONFIGURACAO
Mostra primeiro um resumo. Somente depois da confirmacao cria/remove
pares com0com e atualiza vector.ini.

SEGURANCA
O Port Manager nao deve substituir silenciosamente uma porta fisica
ou uma COM ocupada. Sempre confira o resumo antes de confirmar.
"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Ajuda - GADX Vector Port Manager")
        self.geometry("800x680")

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="GADX Vector Port Manager - Ajuda",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        frame = ttk.Frame(outer)
        frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")

        text = tk.Text(
            frame,
            wrap="word",
            yscrollcommand=scrollbar.set,
            padx=10,
            pady=10,
        )
        text.pack(fill="both", expand=True)
        scrollbar.config(command=text.yview)

        text.insert("1.0", self.TEXT)
        text.config(state="disabled")

        ttk.Button(outer, text="Fechar", command=self.destroy).pack(
            side="right", pady=(10, 0)
        )


class ClientRow:
    def __init__(self, manager: "App", desired: DesiredClient):
        self.manager = manager

        self.name = tk.StringVar(value=desired.name)

        self.cat_type = tk.StringVar(value=desired.cat_type)
        self.cat_app = tk.StringVar(value=desired.cat_app)
        self.cat_vector = tk.StringVar(value=desired.cat_vector)

        self.cw_type = tk.StringVar(value=desired.cw_type)
        self.cw_app = tk.StringVar(value=desired.cw_app)
        self.cw_vector = tk.StringVar(value=desired.cw_vector)
        self.cw_ptt_input = desired.cw_ptt_input.upper()
        self.cw_key_input = desired.cw_key_input.upper()

        self.fsk_type = tk.StringVar(value=desired.fsk_type)
        self.fsk_app = tk.StringVar(value=desired.fsk_app)
        self.fsk_vector = tk.StringVar(value=desired.fsk_vector)
        self.fsk_ptt_input = desired.fsk_ptt_input.upper()
        self.fsk_key_input = desired.fsk_key_input.upper()

        self.client_widget = ttk.Entry(
            manager.client_group,
            textvariable=self.name,
            width=17,
        )

        self.cat_widgets = self._channel_widgets(
            manager.cat_group,
            self.cat_type,
            ("CAT", "NONE"),
            self.cat_app,
            self.cat_vector,
            "cat",
        )

        self.cw_widgets = self._channel_widgets(
            manager.cw_group,
            self.cw_type,
            ("CW", "PTT", "NONE"),
            self.cw_app,
            self.cw_vector,
            "cw",
        )

        self.fsk_widgets = self._channel_widgets(
            manager.fsk_group,
            self.fsk_type,
            ("FSK", "NONE"),
            self.fsk_app,
            self.fsk_vector,
            "fsk",
        )

        self.remove_button = ttk.Button(
            manager.action_group,
            text="Remover",
            command=lambda: manager.remove_row(self),
        )

        manager.tip(
            self.client_widget,
            "Nome do programa/cliente. CAT, CW e FSK ficam agrupados na mesma linha.",
        )

        self.refresh_choices()

    def _channel_widgets(
        self,
        parent,
        type_var,
        types,
        app_var,
        vector_var,
        role,
    ):
        type_combo = ttk.Combobox(
            parent,
            textvariable=type_var,
            values=types,
            width=8,
            state="readonly",
        )
        app_combo = ttk.Combobox(
            parent,
            textvariable=app_var,
            width=9,
            state="readonly",
        )
        arrow = ttk.Label(parent, text="↔")
        vector_combo = ttk.Combobox(
            parent,
            textvariable=vector_var,
            width=9,
            state="readonly",
        )

        app_combo.config(
            postcommand=lambda: self._fill_combo(
                app_combo,
                "fsk_app" if role == "fsk" else "app",
                app_var.get(),
            )
        )
        vector_combo.config(
            postcommand=lambda: self._fill_combo(
                vector_combo,
                "vector",
                vector_var.get(),
            )
        )

        if role == "cat":
            self.manager.tip(type_combo, "CAT ou NONE.")
            self.manager.tip(app_combo, "COM usada pelo aplicativo para CAT.")
            self.manager.tip(vector_combo, "COM interna de CAT aberta pelo Vector.")
        elif role == "cw":
            self.manager.tip(type_combo, "CW = PTT + CW keying; PTT = somente PTT.")
            self.manager.tip(app_combo, "COM usada pelo aplicativo para CW/PTT.")
            self.manager.tip(vector_combo, "COM interna de CW/PTT aberta pelo Vector.")
        else:
            self.manager.tip(type_combo, "FSK = PTT + RTTY/FSK keying.")
            self.manager.tip(
                app_combo,
                "COM usada pelo MMTTY/EXTFSK. Limitada a COM9..COM20.",
            )
            self.manager.tip(vector_combo, "COM interna de FSK aberta pelo Vector.")

        return (type_combo, app_combo, arrow, vector_combo)

    def _fill_combo(self, combo, side, current):
        combo["values"] = self.manager.port_choices(side, current, self)

    def place(self, row_number):
        self.client_widget.grid(
            row=row_number,
            column=0,
            padx=5,
            pady=4,
            sticky="ew",
        )

        for widgets, group in (
            (self.cat_widgets, self.manager.cat_group),
            (self.cw_widgets, self.manager.cw_group),
            (self.fsk_widgets, self.manager.fsk_group),
        ):
            for column, widget in enumerate(widgets):
                widget.grid(
                    row=row_number,
                    column=column,
                    padx=4,
                    pady=4,
                )

        self.remove_button.grid(
            row=row_number,
            column=0,
            padx=5,
            pady=4,
        )

    def destroy(self):
        self.client_widget.destroy()
        for widgets in (self.cat_widgets, self.cw_widgets, self.fsk_widgets):
            for widget in widgets:
                widget.destroy()
        self.remove_button.destroy()

    def refresh_choices(self):
        self._fill_combo(self.cat_widgets[1], "app", self.cat_app.get())
        self._fill_combo(self.cat_widgets[3], "vector", self.cat_vector.get())

        self._fill_combo(self.cw_widgets[1], "app", self.cw_app.get())
        self._fill_combo(self.cw_widgets[3], "vector", self.cw_vector.get())

        self._fill_combo(self.fsk_widgets[1], "fsk_app", self.fsk_app.get())
        self._fill_combo(self.fsk_widgets[3], "vector", self.fsk_vector.get())

    def selected_ports(self):
        values = (
            self.cat_app.get(),
            self.cat_vector.get(),
            self.cw_app.get(),
            self.cw_vector.get(),
            self.fsk_app.get(),
            self.fsk_vector.get(),
        )
        return {value.upper() for value in values if value}

    def desired_pairs(self):
        name = self.name.get().strip() or "Cliente"
        result = []

        if self.cat_type.get() != "NONE":
            result.append(
                DesiredPair(
                    name,
                    "CAT",
                    self.cat_app.get().upper(),
                    self.cat_vector.get().upper(),
                )
            )

        if self.cw_type.get() != "NONE":
            result.append(
                DesiredPair(
                    name,
                    "CW KEYING",
                    self.cw_app.get().upper(),
                    self.cw_vector.get().upper(),
                )
            )

        if self.fsk_type.get() != "NONE":
            result.append(
                DesiredPair(
                    name,
                    "FSK KEYING",
                    self.fsk_app.get().upper(),
                    self.fsk_vector.get().upper(),
                )
            )

        return result

    def desired_keying_channels(self):
        name = self.name.get().strip() or "Cliente"
        result = []

        if self.cw_type.get() != "NONE":
            ptt = self.cw_ptt_input.upper()
            key = self.cw_key_input.upper()

            if self.cw_type.get() == "PTT":
                key = "NONE"

            result.append(
                (
                    name,
                    self.cw_vector.get().upper(),
                    ptt,
                    key,
                )
            )

        if self.fsk_type.get() != "NONE":
            result.append(
                (
                    f"{name} FSK",
                    self.fsk_vector.get().upper(),
                    self.fsk_ptt_input.upper(),
                    self.fsk_key_input.upper(),
                )
            )

        return result


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GADX Vector Port Manager")
        self.geometry("1480x760")
        self.minsize(1260, 650)

        self.rows = []
        self.com0com = None
        self.existing_pairs = []
        self.active = {}
        self.busy = set()
        self.queue = queue.Queue()
        self.progress = None
        self.tips = []

        self.build()
        self.after(150, lambda: self.refresh_inventory(show_progress=True, initial=True))

    def tip(self, widget, text):
        self.tips.append(Tip(widget, text))

    def build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(
            top,
            text="GADX Vector Port Manager",
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left")

        help_button = ttk.Button(top, text="?", width=3, command=lambda: Help(self))
        help_button.pack(side="right")
        self.tip(help_button, "Abre a ajuda completa.")

        self.admin_text = tk.StringVar()
        ttk.Label(top, textvariable=self.admin_text).pack(side="right", padx=10)

        inventory = ttk.LabelFrame(self, text="Inventario da maquina", padding=8)
        inventory.pack(fill="x", padx=10)

        self.setupc_text = tk.StringVar()
        ttk.Label(inventory, textvariable=self.setupc_text).pack(anchor="w")

        self.inventory_text = tk.Text(inventory, height=7)
        self.inventory_text.pack(fill="x")

        desired = ttk.LabelFrame(
            self,
            text="Clientes e pares virtuais desejados",
            padding=8,
        )
        desired.pack(fill="both", expand=True, padx=10, pady=8)

        groups = ttk.Frame(desired)
        groups.pack(fill="x")

        self.client_group = ttk.LabelFrame(groups, text="CLIENTE", padding=5)
        self.cat_group = ttk.LabelFrame(groups, text="CAT", padding=5)
        self.cw_group = ttk.LabelFrame(groups, text="CW KEYING", padding=5)
        self.fsk_group = ttk.LabelFrame(groups, text="FSK KEYING", padding=5)
        self.action_group = ttk.Frame(groups, padding=(5, 26, 5, 5))

        self.client_group.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.cat_group.grid(row=0, column=1, sticky="nsew", padx=5)
        self.cw_group.grid(row=0, column=2, sticky="nsew", padx=5)
        self.fsk_group.grid(row=0, column=3, sticky="nsew", padx=5)
        self.action_group.grid(row=0, column=4, sticky="ns", padx=(5, 0))

        groups.columnconfigure(0, weight=1)
        groups.columnconfigure(1, weight=2)
        groups.columnconfigure(2, weight=2)
        groups.columnconfigure(3, weight=2)

        ttk.Label(
            self.client_group,
            text="Programa",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=0, padx=5, pady=(0, 4))

        for group in (self.cat_group, self.cw_group, self.fsk_group):
            ttk.Label(group, text="Tipo", font=("Segoe UI", 9, "bold")).grid(
                row=0, column=0, padx=4, pady=(0, 4)
            )
            ttk.Label(group, text="Aplicativo", font=("Segoe UI", 9, "bold")).grid(
                row=0, column=1, padx=4, pady=(0, 4)
            )
            ttk.Label(group, text="", font=("Segoe UI", 9, "bold")).grid(
                row=0, column=2
            )
            ttk.Label(group, text="Vector", font=("Segoe UI", 9, "bold")).grid(
                row=0, column=3, padx=4, pady=(0, 4)
            )

        buttons = ttk.Frame(desired)
        buttons.pack(fill="x", pady=10)

        ttk.Button(
            buttons,
            text="+ Adicionar cliente",
            command=self.add_client,
        ).pack(side="left")

        ttk.Button(
            buttons,
            text="Preparar N1MM CW + RTTY",
            command=self.prepare_n1mm_cw_rtty,
        ).pack(side="left", padx=6)

        ttk.Button(
            buttons,
            text="Sugestao 2 clientes",
            command=self.suggest,
        ).pack(side="left", padx=6)

        self.message = tk.StringVar(
            value=(
                "v0.15: interface agrupada por CLIENTE / CAT / CW KEYING / "
                "FSK KEYING; FSK limitado a COM<=20."
            )
        )
        ttk.Label(self, textvariable=self.message, padding=10).pack(
            side="bottom", fill="x"
        )

        actions = ttk.Frame(self, padding=10)
        actions.pack(side="bottom", fill="x")

        ttk.Button(
            actions,
            text="Carregar configuracao atual",
            command=self.load_config,
        ).pack(side="left")

        ttk.Button(
            actions,
            text="Recarregar inventario",
            command=lambda: self.refresh_inventory(show_progress=True),
        ).pack(side="left", padx=6)

        ttk.Button(
            actions,
            text="Aplicar configuracao",
            command=self.apply,
        ).pack(side="right")

    def work(self, title, function, on_success):
        self.progress = Progress(self, title)

        def runner():
            try:
                self.queue.put((True, function()))
            except Exception as exc:
                self.queue.put((False, exc))

        threading.Thread(target=runner, daemon=True).start()

        def poll():
            try:
                ok, value = self.queue.get_nowait()
            except queue.Empty:
                self.after(100, poll)
                return

            self.progress.close()
            self.progress = None

            if ok:
                on_success(value)
            else:
                messagebox.showerror("Falha", str(value))

        self.after(100, poll)

    def collect_inventory(self):
        active = active_ports()
        com0com = Com0Com.discover()
        return com0com, com0com.list_pairs(), active, com0com.busy_names()

    def refresh_inventory(self, show_progress=False, initial=False):
        self.admin_text.set("Administrador: SIM" if is_admin() else "Administrador: NAO")

        def on_success(result):
            self.com0com, self.existing_pairs, self.active, self.busy = result
            self.setupc_text.set(f"com0com: {self.com0com.exe}")
            self.render_inventory()

            for row in self.rows:
                row.refresh_choices()

            if initial and not self.existing_pairs:
                self.suggest()

        if show_progress:
            self.work("Carregando inventario", self.collect_inventory, on_success)
        else:
            on_success(self.collect_inventory())

    def render_inventory(self):
        lines = ["Pares com0com existentes:"]
        lines.extend(
            f"  #{pair.index}: {pair.app_port} <-> {pair.vector_port}"
            for pair in self.existing_pairs
        )
        lines.extend(["", "Portas seriais ativas:"])
        lines.extend(
            f"  {port}: {self.active[port]}"
            for port in sorted(
                self.active,
                key=lambda value: (
                    com_number(value) if COM_RE.match(value) else 9999
                ),
            )
        )

        self.inventory_text.delete("1.0", "end")
        self.inventory_text.insert("1.0", "\n".join(lines))

    def existing_ports(self):
        return {
            port
            for pair in self.existing_pairs
            for port in (pair.app_port, pair.vector_port)
        }

    def other_end(self, port):
        port = port.upper()
        for pair in self.existing_pairs:
            if pair.app_port == port:
                return pair.vector_port
            if pair.vector_port == port:
                return pair.app_port
        return ""

    def used_by_other_rows(self, owner):
        return {
            port
            for row in self.rows
            if row is not owner
            for port in row.selected_ports()
        }

    def port_choices(self, side, current, owner):
        used = self.used_by_other_rows(owner)
        existing = self.existing_ports()

        if side == "vector":
            low, high = VEC_MIN, VEC_MAX
        elif side == "fsk_app":
            low, high = APP_MIN, FSK_APP_MAX
        else:
            low, high = APP_MIN, APP_MAX

        result = []
        for number in range(low, high + 1):
            port = f"COM{number}"

            if port in used:
                continue
            if port in self.active and port not in existing:
                continue
            if port in self.busy and port not in existing:
                continue

            result.append(port)

        if current and current not in result:
            result.insert(0, current)

        return result

    def clear_rows(self):
        for row in self.rows:
            row.destroy()
        self.rows = []

    def add_row(self, desired):
        row = ClientRow(self, desired)
        self.rows.append(row)
        self.layout_rows()
        return row

    def layout_rows(self):
        for index, row in enumerate(self.rows, start=1):
            row.place(index)

    def remove_row(self, row):
        row.destroy()
        self.rows.remove(row)
        self.layout_rows()

    def first_free(self, start, used, maximum=None):
        number = start
        existing = self.existing_ports()

        while maximum is None or number <= maximum:
            port = f"COM{number}"
            if (
                port not in used
                and (port not in self.active or port in existing)
                and (port not in self.busy or port in existing)
            ):
                return port
            number += 1

        raise RuntimeError("Nao ha porta COM livre dentro da faixa permitida.")

    def next_vector_port(self, used):
        return self.first_free(101, used, VEC_MAX)

    def next_app_port(self, used, start=15):
        return self.first_free(start, used, APP_MAX)

    def next_fsk_port(self, used):
        # COM18 e a preferencia desta estacao; depois procura COM9..COM20.
        order = [18] + [number for number in range(APP_MIN, FSK_APP_MAX + 1) if number != 18]
        existing = self.existing_ports()

        for number in order:
            port = f"COM{number}"
            if port in used:
                continue
            if port in self.active and port not in existing:
                continue
            if port in self.busy and port not in existing:
                continue
            return port

        raise RuntimeError("Nenhuma COM entre COM9 e COM20 esta livre para FSK/RTTY.")

    def add_client(self):
        used = {
            port
            for row in self.rows
            for port in row.selected_ports()
        }

        cat_app = self.next_app_port(used, 15)
        used.add(cat_app)
        cat_vector = self.next_vector_port(used)
        used.add(cat_vector)

        cw_app = self.next_app_port(used, 15)
        used.add(cw_app)
        cw_vector = self.next_vector_port(used)

        self.add_row(
            DesiredClient(
                name=f"Cliente {len(self.rows) + 1}",
                cat_type="CAT",
                cat_app=cat_app,
                cat_vector=cat_vector,
                cw_type="CW",
                cw_app=cw_app,
                cw_vector=cw_vector,
                cw_ptt_input="RTS",
                cw_key_input="DTR",
            )
        )

    def suggest(self):
        self.clear_rows()
        first = self.add_client()
        first.name.set("LogHX")
        second = self.add_client()
        second.name.set("N1MM")

    def parse_keying(self, config):
        channels = []

        if not config.has_section("keying"):
            return channels

        for key, value in config.items("keying"):
            match = CLIENT_RE.match(key)
            if not match:
                continue

            parts = [part.strip() for part in value.split(",")]
            if len(parts) < 3:
                continue

            index = int(match.group(1))

            if len(parts) >= 4:
                name = parts[0]
                vector_port = parts[1].upper()
                ptt_input = parts[2].upper()
                key_input = parts[3].upper()
            else:
                name = f"Cliente {index}"
                vector_port = parts[0].upper()
                ptt_input = parts[1].upper()
                key_input = parts[2].upper()

            channels.append(
                KeyingChannel(
                    index,
                    name,
                    vector_port,
                    ptt_input,
                    key_input,
                )
            )

        channels.sort(key=lambda item: item.index)
        return channels

    @staticmethod
    def is_fsk_channel(channel):
        upper = channel.name.strip().upper()
        return (
            upper == "MMTTY"
            or upper.endswith(" FSK")
            or upper.endswith("/FSK")
            or upper.endswith("-FSK")
        )

    @staticmethod
    def fsk_base_name(channel):
        name = channel.name.strip()

        if name.upper() == "MMTTY":
            return "N1MM"

        for suffix in (" FSK", "/FSK", "-FSK"):
            if name.upper().endswith(suffix):
                return name[: -len(suffix)].strip()

        return name

    def load_config(self):
        if not CONFIG_PATH.exists():
            messagebox.showerror("Configuracao", str(CONFIG_PATH))
            return

        config = configparser.ConfigParser()
        config.read(CONFIG_PATH, encoding="utf-8-sig")

        cat_ports = [
            item.strip().upper()
            for item in config.get("cat", "ports", fallback="").split(",")
            if item.strip()
        ]

        channels = self.parse_keying(config)
        primary = [channel for channel in channels if not self.is_fsk_channel(channel)]
        fsk_channels = [channel for channel in channels if self.is_fsk_channel(channel)]

        self.clear_rows()

        # O formato historico de [cat] nao guarda o nome do cliente.
        # Mantemos a associacao por ordem com os canais principais.
        row_count = max(len(cat_ports), len(primary))

        for index in range(row_count):
            if index < len(primary):
                channel = primary[index]
                name = channel.name
                cw_vector = channel.vector_port
                cw_app = self.other_end(cw_vector)
                cw_type = "PTT" if channel.key_input == "NONE" else "CW"
                cw_ptt = channel.ptt_input
                cw_key = channel.key_input
            else:
                name = f"Cliente {index + 1}"
                cw_vector = ""
                cw_app = ""
                cw_type = "NONE"
                cw_ptt = "RTS"
                cw_key = "DTR"

            if index < len(cat_ports):
                cat_vector = cat_ports[index]
                cat_app = self.other_end(cat_vector)
                cat_type = "CAT"
            else:
                cat_vector = ""
                cat_app = ""
                cat_type = "NONE"

            self.add_row(
                DesiredClient(
                    name=name,
                    cat_type=cat_type,
                    cat_app=cat_app,
                    cat_vector=cat_vector,
                    cw_type=cw_type,
                    cw_app=cw_app,
                    cw_vector=cw_vector,
                    cw_ptt_input=cw_ptt,
                    cw_key_input=cw_key,
                )
            )

        # Anexa os canais FSK ao cliente correspondente.
        for channel in fsk_channels:
            base = self.fsk_base_name(channel)
            target = next(
                (
                    row
                    for row in self.rows
                    if row.name.get().strip().upper() == base.upper()
                ),
                None,
            )

            # Compatibilidade com a v0.14: MMTTY era uma linha separada,
            # mas pertence ao N1MM no modelo agrupado.
            if target is None and channel.name.strip().upper() == "MMTTY":
                target = next(
                    (
                        row
                        for row in self.rows
                        if row.name.get().strip().upper() == "N1MM"
                    ),
                    None,
                )

            if target is None:
                target = self.add_row(DesiredClient(name=base))

            target.fsk_type.set("FSK")
            target.fsk_vector.set(channel.vector_port)
            target.fsk_app.set(self.other_end(channel.vector_port))
            target.fsk_ptt_input = channel.ptt_input
            target.fsk_key_input = channel.key_input
            target.refresh_choices()

        self.message.set(
            "Configuracao atual carregada e agrupada por cliente. "
            "Confira CAT, CW KEYING e FSK KEYING antes de aplicar."
        )

    def prepare_n1mm_cw_rtty(self):
        n1mm = next(
            (
                row
                for row in self.rows
                if row.name.get().strip().upper() == "N1MM"
            ),
            None,
        )

        if n1mm is None:
            messagebox.showerror(
                "N1MM",
                "Cliente N1MM nao encontrado. Carregue a configuracao atual primeiro.",
            )
            return

        used_without_n1mm = {
            port
            for row in self.rows
            if row is not n1mm
            for port in row.selected_ports()
        }

        if "COM30" in used_without_n1mm:
            messagebox.showerror(
                "N1MM",
                "COM30 ja esta atribuida a outro cliente.",
            )
            return

        n1mm.cw_type.set("CW")
        n1mm.cw_app.set("COM30")
        n1mm.cw_ptt_input = "RTS"
        n1mm.cw_key_input = "DTR"

        if not n1mm.cw_vector.get():
            used = {
                port
                for row in self.rows
                for port in row.selected_ports()
            }
            n1mm.cw_vector.set(self.next_vector_port(used))

        used = {
            port
            for row in self.rows
            for port in row.selected_ports()
            if port != n1mm.fsk_app.get()
        }

        n1mm.fsk_type.set("FSK")
        if not n1mm.fsk_app.get() or com_number(n1mm.fsk_app.get()) > FSK_APP_MAX:
            n1mm.fsk_app.set(self.next_fsk_port(used))

        if not n1mm.fsk_vector.get():
            used.add(n1mm.fsk_app.get())
            n1mm.fsk_vector.set(self.next_vector_port(used))

        n1mm.fsk_ptt_input = "RTS"
        n1mm.fsk_key_input = "DTR"
        n1mm.refresh_choices()

        self.message.set(
            f"N1MM preparado: CW {n1mm.cw_app.get()} <-> {n1mm.cw_vector.get()} | "
            f"FSK {n1mm.fsk_app.get()} <-> {n1mm.fsk_vector.get()} | "
            "RTS=PTT, DTR=KEYING."
        )

    def all_pairs(self):
        return [
            pair
            for row in self.rows
            for pair in row.desired_pairs()
        ]

    def desired_config(self):
        cat_ports = [
            row.cat_vector.get().upper()
            for row in self.rows
            if row.cat_type.get() != "NONE" and row.cat_vector.get()
        ]

        channels = []
        for row in self.rows:
            channels.extend(row.desired_keying_channels())

        return cat_ports, channels

    def current_config_snapshot(self):
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH, encoding="utf-8-sig")

        cat_ports = [
            item.strip().upper()
            for item in config.get("cat", "ports", fallback="").split(",")
            if item.strip()
        ]

        channels = [
            (
                channel.name,
                channel.vector_port,
                channel.ptt_input,
                channel.key_input,
            )
            for channel in self.parse_keying(config)
        ]

        return cat_ports, channels

    def config_changes(self):
        old_cat, old_channels = self.current_config_snapshot()
        new_cat, new_channels = self.desired_config()

        changes = []

        if old_cat != new_cat:
            changes.append(
                "Atualizar [cat] ports: "
                + (", ".join(new_cat) if new_cat else "nenhuma")
            )

        if old_channels != new_channels:
            rendered = "; ".join(
                f"{name},{port},{ptt},{key}"
                for name, port, ptt, key in new_channels
            )
            changes.append(
                "Atualizar [keying]: " + (rendered if rendered else "nenhum canal")
            )

        return changes

    def persist_config(self):
        cat_ports, channels = self.desired_config()

        generated_keying = [
            "; Formato: clientN = NOME,PORTA_VECTOR,PTT_INPUT,KEY_INPUT\n",
            ";\n",
            "; RTS/DTR sao lidos na ponta Vector atraves das linhas com0com.\n",
            "; CW e FSK usam canais independentes, mas convergem no Vector.\n",
        ]

        for index, (name, port, ptt, key) in enumerate(channels, start=1):
            generated_keying.append(
                f"client{index} = {name},{port},{ptt},{key}\n"
            )

        generated_keying.append("\n")

        source = CONFIG_PATH.read_text(encoding="utf-8-sig").splitlines(True)
        output = []
        section = ""
        skip_keying_body = False
        cat_written = False
        keying_found = False

        for line in source:
            stripped = line.strip()

            if stripped.startswith("[") and stripped.endswith("]"):
                section = stripped[1:-1].strip().lower()
                skip_keying_body = section == "keying"

                output.append(line)

                if section == "keying":
                    keying_found = True
                    output.extend(generated_keying)

                continue

            if skip_keying_body:
                continue

            if section == "cat" and re.match(r"^\s*ports\s*=", line, re.I):
                newline = "\r\n" if line.endswith("\r\n") else "\n"
                output.append(f"ports = {', '.join(cat_ports)}{newline}")
                cat_written = True
                continue

            output.append(line)

        if not keying_found:
            if output and not output[-1].endswith("\n"):
                output[-1] += "\n"
            output.extend(["\n[keying]\n"] + generated_keying)

        if not cat_written:
            # O arquivo atual da estacao possui [cat]/ports. Se algum arquivo
            # futuro nao possuir, nao criamos uma segunda secao [cat] aqui.
            pass

        CONFIG_PATH.write_text("".join(output), encoding="utf-8")

    def validate(self):
        used = {}
        errors = []

        for row in self.rows:
            name = row.name.get().strip() or "Cliente"

            groups = [
                ("CAT", row.cat_type.get(), row.cat_app.get(), row.cat_vector.get()),
                (
                    "CW KEYING",
                    row.cw_type.get(),
                    row.cw_app.get(),
                    row.cw_vector.get(),
                ),
                (
                    "FSK KEYING",
                    row.fsk_type.get(),
                    row.fsk_app.get(),
                    row.fsk_vector.get(),
                ),
            ]

            for group_name, channel_type, app_port, vector_port in groups:
                if channel_type == "NONE":
                    continue

                if not app_port or not vector_port:
                    errors.append(f"{name}/{group_name}: informe Aplicativo e Vector.")
                    continue

                try:
                    app_number = com_number(app_port)
                    vector_number = com_number(vector_port)
                except ValueError as exc:
                    errors.append(str(exc))
                    continue

                if group_name == "FSK KEYING" and app_number > FSK_APP_MAX:
                    errors.append(
                        f"{name}/FSK: {app_port} nao e permitida. "
                        f"Use COM{APP_MIN}..COM{FSK_APP_MAX}."
                    )

                if not (VEC_MIN <= vector_number <= VEC_MAX):
                    errors.append(
                        f"{name}/{group_name}: {vector_port} deve estar entre "
                        f"COM{VEC_MIN} e COM{VEC_MAX}."
                    )

                for port in (app_port.upper(), vector_port.upper()):
                    if port in used:
                        errors.append(
                            f"{port} esta repetida em {used[port]} e "
                            f"{name}/{group_name}."
                        )
                    else:
                        used[port] = f"{name}/{group_name}"

        if errors:
            raise ValueError("\n".join(errors))

    def apply(self):
        if not is_admin():
            messagebox.showerror(
                "Permissao",
                "Execute o Port Manager como Administrador.",
            )
            return

        try:
            self.validate()
        except Exception as exc:
            messagebox.showerror("Configuracao invalida", str(exc))
            return

        desired_pairs = self.all_pairs()
        current = {
            (pair.app_port, pair.vector_port): pair
            for pair in self.existing_pairs
        }
        wanted = {
            (pair.app_port, pair.vector_port)
            for pair in desired_pairs
        }

        remove = [
            pair
            for key, pair in current.items()
            if key not in wanted
        ]

        create = [
            pair
            for pair in desired_pairs
            if (pair.app_port, pair.vector_port) not in current
        ]

        config_changes = self.config_changes()

        if not remove and not create and not config_changes:
            messagebox.showinfo(
                "Sem alteracoes",
                "COMs e vector.ini ja correspondem ao plano.",
            )
            return

        summary = ["Alteracoes propostas:"]

        summary.extend(
            f"Remover {pair.app_port} <-> {pair.vector_port}"
            for pair in remove
        )

        summary.extend(
            (
                f"Criar {pair.app_port} <-> {pair.vector_port} "
                f"({pair.name}/{pair.kind})"
            )
            for pair in create
        )

        summary.extend(config_changes)

        if not messagebox.askyesno("Confirmar", "\n".join(summary)):
            return

        def worker():
            for pair in remove:
                self.com0com.remove_pair(pair.index)

            for pair in create:
                self.com0com.create_pair(pair.app_port, pair.vector_port)

            if config_changes:
                self.persist_config()

            return self.collect_inventory()

        def on_success(result):
            self.com0com, self.existing_pairs, self.active, self.busy = result
            self.render_inventory()

            for row in self.rows:
                row.refresh_choices()

            self.message.set(
                "Configuracao aplicada. Reinicie o GADXVectorHub para carregar "
                "alteracoes do vector.ini."
            )

        self.work("Aplicando configuracao", worker, on_success)


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("GADX Vector Port Manager requer Windows")

    App().mainloop()
