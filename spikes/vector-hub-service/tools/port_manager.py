from __future__ import annotations

import configparser
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

from serial.tools import list_ports

CONFIG_PATH = Path(r"C:\Ham\GADX-Vector\config\vector.ini")
SETUPC_CANDIDATES = [
    Path(r"C:\Program Files (x86)\com0com\setupc.exe"),
    Path(r"C:\Program Files\com0com\setupc.exe"),
    Path(r"C:\Ham\com0com\setupc.exe"),
    Path(r"D:\Ham\com0com\setupc.exe"),
]
PAIR_RE = re.compile(r"\bCNC([AB])(\d+)\s+.*?(?:PortName|RealPortName)=(COM\d+)", re.I)
COM_RE = re.compile(r"^COM(\d+)$", re.I)
CLIENT_RE = re.compile(r"^client(\d+)$", re.I)
KEYING_LINE_RE = re.compile(r"^(\s*)(client(\d+))(\s*=\s*)(.*?)(\r?\n)?$", re.I)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
SW_HIDE = 0
APP_COM_MIN, APP_COM_MAX = 9, 40
VECTOR_COM_MIN, VECTOR_COM_MAX = 100, 140


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
        for path in SETUPC_CANDIDATES:
            if path.exists():
                return cls(path)
        raise FileNotFoundError("setupc.exe do com0com nao foi encontrado")

    def _startupinfo(self):
        if sys.platform != "win32":
            return None
        info = subprocess.STARTUPINFO()
        info.dwFlags |= STARTF_USESHOWWINDOW
        info.wShowWindow = SW_HIDE
        return info

    def _run(self, args, timeout=8):
        try:
            result = subprocess.run(
                [str(self.exe)] + list(args),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self.exe.parent),
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                startupinfo=self._startupinfo(),
                creationflags=CREATE_NO_WINDOW,
            )
            return result.stdout or ""
        except subprocess.TimeoutExpired as exc:
            raise Com0ComTimeout(f"com0com nao respondeu: {' '.join(args)}") from exc

    def _interactive(self, commands, timeout=12):
        payload = "\n".join(list(commands) + ["quit", ""])
        try:
            result = subprocess.run(
                [str(self.exe)],
                input=payload,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self.exe.parent),
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                startupinfo=self._startupinfo(),
                creationflags=CREATE_NO_WINDOW,
            )
            return result.stdout or ""
        except subprocess.TimeoutExpired as exc:
            raise Com0ComTimeout(f"com0com encontrado em {self.exe}, mas nao respondeu") from exc

    def _query(self, args, commands):
        try:
            output = self._run(args)
            if output.strip():
                return output
        except Exception:
            pass
        return self._interactive(commands)

    def list_pairs(self):
        grouped = {}
        for line in self._query(["list"], ["list"]).splitlines():
            match = PAIR_RE.search(line)
            if match:
                side, index, port = match.groups()
                grouped.setdefault(int(index), {})[side.upper()] = port.upper()
        return [
            ComPair(index, sides["A"], sides["B"])
            for index, sides in sorted(grouped.items())
            if "A" in sides and "B" in sides
        ]

    def busy_names(self):
        return {
            line.strip().upper()
            for line in self._query(["busynames", "*"], ["busynames *"]).splitlines()
            if COM_RE.match(line.strip().upper())
        }

    def create_pair(self, app_port, vector_port):
        try:
            output = self._run(
                ["install", f"PortName={app_port}", f"PortName={vector_port}"],
                timeout=15,
            )
            if output.strip():
                return output
        except Exception:
            pass
        return self._interactive(
            [f"install PortName={app_port} PortName={vector_port}"], timeout=20
        )

    def remove_pair(self, index):
        try:
            output = self._run(["remove", str(index)], timeout=15)
            if output.strip():
                return output
        except Exception:
            pass
        return self._interactive([f"remove {index}"], timeout=20)


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


class ToolTip:
    def __init__(self, widget, text, delay=550):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.after_id = None
        self.tip = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def schedule(self, _event=None):
        self.hide()
        self.after_id = self.widget.after(self.delay, self.show)

    def show(self):
        self.after_id = None
        if self.tip:
            return
        try:
            x = self.widget.winfo_rootx() + 18
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        except tk.TclError:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip,
            text=self.text,
            justify="left",
            relief="solid",
            borderwidth=1,
            background="#ffffe0",
            foreground="#202020",
            font=("Segoe UI", 9),
            padx=7,
            pady=5,
            wraplength=380,
        ).pack()

    def hide(self, _event=None):
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None
        if self.tip:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None


class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        body = ttk.Frame(self, padding=18)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="GADX Vector Port Manager", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.status = tk.StringVar(value="Preparando...")
        ttk.Label(body, textvariable=self.status).pack(anchor="w", pady=(12, 8))
        self.progress = ttk.Progressbar(body, mode="indeterminate", length=420)
        self.progress.pack(fill="x")
        self.detail = tk.StringVar(value="Iniciando operacao...")
        ttk.Label(body, textvariable=self.detail, foreground="#555555").pack(anchor="w", pady=(8, 0))
        self.progress.start(12)
        self.update_idletasks()
        parent.update_idletasks()
        self.geometry(f"+{parent.winfo_rootx()+100}+{parent.winfo_rooty()+100}")

    def update_status(self, status, detail=""):
        self.status.set(status)
        self.detail.set(detail)
        self.update_idletasks()

    def close(self):
        try:
            self.progress.stop()
            self.grab_release()
            self.destroy()
        except tk.TclError:
            pass


class HelpDialog(tk.Toplevel):
    HELP_TEXT = """GADX VECTOR PORT MANAGER

OBJETIVO
O Port Manager organiza as portas seriais virtuais usadas pelo GADX Vector Hub. Ele permite que varios programas de radioamador usem CAT, PTT e CW ao mesmo tempo sem disputar a mesma porta COM.

COMO A ARQUITETURA FUNCIONA
Cada canal usa um par com0com. Uma ponta e apresentada ao software e a outra e aberta exclusivamente pelo Vector Hub.

Exemplo:
  LogHX CAT     COM9  <-> COM101
  LogHX KEYING  COM29 <-> COM102
  N1MM CAT      COM15 <-> COM103
  N1MM KEYING   COM30 <-> COM104

CAT
CAT e o canal de controle do radio: frequencia, modo e outros comandos. O software enxerga uma fachada compatível com Kenwood TS-2000. O radio fisico continua sendo controlado pelo Hamlib/rigctld.

KEYING
KEYING e separado de CAT e transporta PTT e CW pelas linhas de controle da porta serial virtual. A configuracao do cliente define quais linhas representam PTT e CW. O caminho de CW foi mantido separado para reduzir latencia e jitter.

APLICATIVO x VECTOR
Aplicativo = COM configurada dentro do LogHX, N1MM, OmniRig ou outro programa.
Vector = outra ponta do mesmo par, aberta somente pelo GADX Vector Hub.
Dois programas nunca devem abrir a mesma COM.

INVENTARIO DA MAQUINA
Ao iniciar, a ferramenta consulta:
  - portas COM ativas do Windows;
  - pares existentes no com0com;
  - nomes COM reservados no ComDB.
Isso evita sobrescrever silenciosamente uma porta fisica ou uma porta ja utilizada.

CARREGAR CONFIGURACAO ATUAL
Le C:\\Ham\\GADX-Vector\\config\\vector.ini e cruza as COMs internas declaradas no INI com os pares encontrados no com0com. Assim a tela reconstrói o setup atualmente usado pela estacao.

RECARREGAR INVENTARIO
Faz uma nova leitura do Windows e do com0com. Nao altera nenhuma porta nem o vector.ini.

ADICIONAR CLIENTE
Cria uma nova linha e sugere portas livres. Nada e aplicado imediatamente.

SUGESTAO 2 CLIENTES
Monta um plano inicial CAT + KEYING para dois clientes usando portas que parecem livres. E apenas uma sugestao: revise antes de aplicar.

NOME DO CLIENTE
O nome amigavel, por exemplo LogHX, N1MM ou OmniRig, e usado para facilitar diagnostico e logs. No formato atual do INI:
  client1 = LogHX,COM102,DTR,RTS
Se o INI antigo nao possui nome, a tela usa Cliente 1, Cliente 2 etc.

APLICAR CONFIGURACAO
A ferramenta compara a tela com o estado real, mostra um resumo e pede confirmacao. So depois disso cria/remove pares com0com e persiste alteracoes de nome no vector.ini.

IMPORTANTE DURANTE O SPIKE
Nem toda alteracao estrutural do Hub ainda e persistida automaticamente no vector.ini. O Port Manager ja gerencia os pares com0com e os nomes amigaveis. A evolucao seguinte deve transformar a tela inteira na fonte de configuracao persistente do Hub.

POLITICA DE PORTAS
Para novas instalacoes, a preferencia e iniciar as portas apresentadas aos softwares em COM15 e as internas do Vector em COM101, sempre pulando nomes ocupados. Instalacoes existentes podem manter numeros legados como COM9/COM29.

ANTES DE APLICAR
  1. Confirme que o inventario encontrou os pares esperados.
  2. Use Carregar configuracao atual quando estiver alterando uma estacao existente.
  3. Confira as duas pontas de cada par.
  4. Feche programas que possam estar usando uma COM a ser removida.
  5. Leia o resumo antes de confirmar.

DIAGNOSTICO
Se uma COM interna aparece no vector.ini mas o campo Aplicativo fica vazio, o Port Manager nao conseguiu encontrar a outra ponta do par no inventario com0com. Recarregue o inventario e confira o setupc.exe.

Se o com0com nao responder, nenhuma alteracao deve ser forçada. Resolva primeiro o inventario.

Se CAT funciona mas CW/PTT nao, revise o par KEYING e as linhas DTR/RTS configuradas no vector.ini.

PRINCIPIO DE SEGURANCA
O Port Manager nunca deve substituir silenciosamente uma porta fisica ou uma COM ocupada. O operador deve sempre conseguir ver o plano antes de qualquer alteracao.
"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Ajuda - GADX Vector Port Manager")
        self.geometry("760x650")
        self.minsize(620, 480)
        self.transient(parent)

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="GADX Vector Port Manager - Ajuda", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(outer, text="SPIKE 02 / Fase C - Provisionamento e gerenciamento de portas", foreground="#555555").pack(anchor="w", pady=(2, 10))

        frame = ttk.Frame(outer)
        frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        text = tk.Text(frame, wrap="word", yscrollcommand=scrollbar.set, padx=10, pady=10)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=text.yview)
        text.insert("1.0", self.HELP_TEXT)
        text.configure(state="disabled")

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Fechar", command=self.destroy).pack(side="right")


class ClientRow:
    def __init__(self, manager, desired):
        self.manager = manager
        table = manager.table
        self.name = tk.StringVar(value=desired.name)
        self.cat_type = tk.StringVar(value=desired.cat_type)
        self.cat_app = tk.StringVar(value=desired.cat_app)
        self.cat_vector = tk.StringVar(value=desired.cat_vector)
        self.key_type = tk.StringVar(value=desired.key_type)
        self.key_app = tk.StringVar(value=desired.key_app)
        self.key_vector = tk.StringVar(value=desired.key_vector)

        self.widgets = [
            ttk.Entry(table, textvariable=self.name, width=14),
            ttk.Combobox(table, textvariable=self.cat_type, values=("CAT", "NONE"), width=8, state="readonly"),
            ttk.Combobox(table, textvariable=self.cat_app, width=9, state="readonly"),
            ttk.Label(table, text="↔"),
            ttk.Combobox(table, textvariable=self.cat_vector, width=9, state="readonly"),
            ttk.Combobox(table, textvariable=self.key_type, values=("KEYING", "NONE"), width=9, state="readonly"),
            ttk.Combobox(table, textvariable=self.key_app, width=9, state="readonly"),
            ttk.Label(table, text="↔"),
            ttk.Combobox(table, textvariable=self.key_vector, width=9, state="readonly"),
            ttk.Button(table, text="Remover", command=lambda: manager.remove_row(self)),
        ]
        tips = [
            "Nome amigavel do software cliente. Ex.: LogHX, N1MM, OmniRig.",
            "Habilita ou desabilita CAT para este cliente.",
            "COM configurada dentro do software para CAT.",
            "",
            "COM interna aberta pelo Vector Hub para CAT.",
            "Habilita ou desabilita KEYING (PTT/CW) para este cliente.",
            "COM configurada dentro do software para PTT/CW.",
            "",
            "COM interna aberta pelo Vector Hub para PTT/CW.",
            "Remove o cliente do plano. Nada muda ate Aplicar configuracao.",
        ]
        for widget, text in zip(self.widgets, tips):
            if text:
                manager.tip(widget, text)

        self.widgets[1].bind("<<ComboboxSelected>>", lambda _e: self.sync())
        self.widgets[5].bind("<<ComboboxSelected>>", lambda _e: self.sync())
        self.widgets[2].configure(postcommand=lambda: self._choices(self.widgets[2], "app", self.cat_app.get()))
        self.widgets[4].configure(postcommand=lambda: self._choices(self.widgets[4], "vector", self.cat_vector.get()))
        self.widgets[6].configure(postcommand=lambda: self._choices(self.widgets[6], "app", self.key_app.get()))
        self.widgets[8].configure(postcommand=lambda: self._choices(self.widgets[8], "vector", self.key_vector.get()))
        self.refresh()
        self.sync()

    def place(self, row):
        for widget, column in zip(self.widgets, [0, 1, 2, 3, 4, 6, 7, 8, 9, 10]):
            widget.grid(row=row, column=column, padx=4, pady=3, sticky="ew")

    def destroy(self):
        for widget in self.widgets:
            widget.destroy()

    def _choices(self, widget, side, current):
        widget["values"] = self.manager.port_choices(side, current, self)

    def refresh(self):
        self._choices(self.widgets[2], "app", self.cat_app.get())
        self._choices(self.widgets[4], "vector", self.cat_vector.get())
        self._choices(self.widgets[6], "app", self.key_app.get())
        self._choices(self.widgets[8], "vector", self.key_vector.get())

    def sync(self):
        cat = self.cat_type.get() != "NONE"
        key = self.key_type.get() != "NONE"
        self.widgets[2].configure(state="readonly" if cat else "disabled")
        self.widgets[4].configure(state="readonly" if cat else "disabled")
        self.widgets[6].configure(state="readonly" if key else "disabled")
        self.widgets[8].configure(state="readonly" if key else "disabled")

    def selected(self):
        selected = set()
        if self.cat_type.get() != "NONE":
            selected |= {self.cat_app.get().upper(), self.cat_vector.get().upper()}
        if self.key_type.get() != "NONE":
            selected |= {self.key_app.get().upper(), self.key_vector.get().upper()}
        return {item for item in selected if item}

    def pairs(self):
        name = self.name.get().strip() or "Cliente"
        result = []
        if self.cat_type.get() != "NONE":
            result.append(DesiredPair(name, "CAT", self.cat_app.get().upper(), self.cat_vector.get().upper()))
        if self.key_type.get() != "NONE":
            result.append(DesiredPair(name, "KEYING", self.key_app.get().upper(), self.key_vector.get().upper()))
        return result


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GADX Vector Port Manager - Phase C SPIKE")
        self.geometry("1120x700")
        self.minsize(1040, 640)
        self.rows = []
        self.com0com = None
        self.existing_pairs = []
        self.active = {}
        self.busy = set()
        self.queue = queue.Queue()
        self.progress = None
        self.tooltips = []
        self.build()
        self.after(150, lambda: self.refresh_inventory(True, True))

    def tip(self, widget, text):
        self.tooltips.append(ToolTip(widget, text))

    def build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="GADX Vector Port Manager", font=("Segoe UI", 16, "bold")).pack(side="left")
        help_button = ttk.Button(top, text="?", width=3, command=lambda: HelpDialog(self))
        help_button.pack(side="right")
        self.admin = tk.StringVar()
        ttk.Label(top, textvariable=self.admin).pack(side="right", padx=(0, 10))
        self.tip(help_button, "Abre a ajuda completa do Port Manager.")

        inventory = ttk.LabelFrame(self, text="Inventario da maquina", padding=8)
        inventory.pack(fill="x", padx=10, pady=(0, 8))
        self.status = tk.StringVar(value="com0com: aguardando inventario...")
        status_label = ttk.Label(inventory, textvariable=self.status)
        status_label.pack(anchor="w")
        self.inventory_text = tk.Text(inventory, height=7, wrap="none")
        self.inventory_text.pack(fill="x", pady=(4, 0))
        self.tip(status_label, "Caminho do setupc.exe usado e estado da consulta ao com0com.")
        self.tip(self.inventory_text, "Inventario tecnico dos pares com0com e portas seriais ativas do Windows.")

        plan = ttk.LabelFrame(self, text="Clientes e pares virtuais desejados", padding=8)
        plan.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.table = ttk.Frame(plan)
        self.table.pack(anchor="w", fill="x")
        for column, size in {0:115,1:78,2:82,3:24,4:82,5:18,6:86,7:82,8:24,9:82,10:80}.items():
            self.table.grid_columnconfigure(column, minsize=size)

        client_header = ttk.Label(self.table, text="Cliente", font=("Segoe UI", 9, "bold"))
        client_header.grid(row=0, column=0, rowspan=2, sticky="sw")
        cat_header = ttk.Label(self.table, text="CAT", font=("Segoe UI", 9, "bold"))
        cat_header.grid(row=0, column=1, columnspan=4, sticky="ew")
        key_header = ttk.Label(self.table, text="KEYING", font=("Segoe UI", 9, "bold"))
        key_header.grid(row=0, column=6, columnspan=4, sticky="ew")
        headers = {}
        for column, text in {1:"Tipo",2:"Aplicativo",4:"Vector",6:"Tipo",7:"Aplicativo",9:"Vector"}.items():
            headers[column] = ttk.Label(self.table, text=text, anchor="center")
            headers[column].grid(row=1, column=column, sticky="ew")
        ttk.Separator(self.table, orient="vertical").grid(row=0, column=5, rowspan=100, sticky="ns", padx=8)
        self.first_row = 2

        self.tip(client_header, "Nome amigavel do software. Usado para diagnostico e logs.")
        self.tip(cat_header, "CAT: controle de frequencia, modo e comandos do radio.")
        self.tip(key_header, "KEYING: canal separado para PTT e CW por DTR/RTS.")
        self.tip(headers[2], "Porta COM configurada no software cliente.")
        self.tip(headers[4], "Porta COM interna aberta pelo Vector Hub.")
        self.tip(headers[7], "Porta COM configurada no software para PTT/CW.")
        self.tip(headers[9], "Porta COM interna usada pelo Vector Hub para receber PTT/CW.")

        row_buttons = ttk.Frame(plan)
        row_buttons.pack(fill="x", pady=(10, 0))
        add_button = ttk.Button(row_buttons, text="+ Adicionar cliente", command=self.add_client)
        add_button.pack(side="left")
        suggestion_button = ttk.Button(row_buttons, text="Sugestao 2 clientes", command=self.suggest)
        suggestion_button.pack(side="left", padx=6)
        self.tip(add_button, "Adiciona uma linha e sugere o proximo conjunto de COMs livres.")
        self.tip(suggestion_button, "Monta um plano inicial de dois clientes CAT + KEYING.")

        self.message = tk.StringVar(value="v0.11: ajuda completa embarcada no botao ?.")
        ttk.Label(self, textvariable=self.message, padding=(10, 3)).pack(side="bottom", fill="x")

        actions = ttk.Frame(self, padding=(10, 7, 10, 10))
        actions.pack(side="bottom", fill="x")
        load_button = ttk.Button(actions, text="Carregar configuracao atual", command=self.load_ini)
        load_button.pack(side="left")
        reload_button = ttk.Button(actions, text="Recarregar inventario", command=lambda: self.refresh_inventory(True))
        reload_button.pack(side="left", padx=6)
        apply_button = ttk.Button(actions, text="Aplicar configuracao", command=self.apply)
        apply_button.pack(side="right")
        self.tip(load_button, "Le o vector.ini e cruza suas COMs internas com o inventario com0com.")
        self.tip(reload_button, "Relê Windows e com0com sem alterar a configuracao.")
        self.tip(apply_button, "Mostra o plano de alteracoes e, apos confirmacao, aplica ao com0com e nomes no INI.")

    def work(self, title, fn, ok, fail=None):
        if self.progress:
            return
        self.progress = ProgressDialog(self, title)

        def run():
            try:
                self.queue.put((True, fn()))
            except Exception as exc:
                self.queue.put((False, exc))

        threading.Thread(target=run, daemon=True).start()

        def poll():
            try:
                success, value = self.queue.get_nowait()
            except queue.Empty:
                self.after(100, poll)
                return
            dialog = self.progress
            self.progress = None
            dialog.close()
            if success:
                ok(value)
            elif fail:
                fail(value)
            else:
                messagebox.showerror("Falha", str(value))

        self.after(100, poll)

    def progress_status(self, status, detail=""):
        self.after(0, lambda: self.progress and self.progress.update_status(status, detail))

    def collect(self):
        self.progress_status("Etapa 1 de 5 - Lendo portas seriais...")
        active = active_ports()
        self.progress_status("Etapa 2 de 5 - Localizando com0com...")
        com0com = Com0Com.discover()
        self.progress_status("Etapa 3 de 5 - Consultando pares virtuais...", str(com0com.exe))
        pairs = com0com.list_pairs()
        self.progress_status("Etapa 4 de 5 - Consultando portas reservadas...")
        busy = com0com.busy_names()
        self.progress_status("Etapa 5 de 5 - Atualizando inventario...", f"{len(pairs)} par(es)")
        return com0com, pairs, active, busy

    def refresh_inventory(self, show=False, initial=False):
        self.admin.set("Administrador: SIM" if is_admin() else "Administrador: NAO")

        def ok(result):
            self.com0com, self.existing_pairs, self.active, self.busy = result
            self.status.set(f"com0com: {self.com0com.exe}")
            self.render()
            self.refresh_rows()
            if initial and not self.existing_pairs:
                self.suggest()

        def bad(exc):
            self.com0com = None
            self.existing_pairs = []
            self.active = active_ports()
            self.busy = set()
            self.status.set(f"Falha ao consultar com0com: {exc}")
            self.render()
            if initial:
                self.suggest()

        if show:
            self.work("Carregando inventario", self.collect, ok, bad)
        else:
            try:
                ok(self.collect())
            except Exception as exc:
                bad(exc)

    def render(self):
        lines = ["Pares com0com existentes:"]
        if self.existing_pairs:
            lines.extend(f"  #{pair.index}: {pair.app_port} <-> {pair.vector_port}" for pair in self.existing_pairs)
        else:
            lines.append("  nenhum")
        lines.extend(["", "Portas seriais ativas:"])
        for name in sorted(self.active, key=lambda item: com_number(item) if COM_RE.match(item) else 9999):
            lines.append(f"  {name}: {self.active[name]}")
        self.inventory_text.delete("1.0", "end")
        self.inventory_text.insert("1.0", "\n".join(lines))

    def existing(self):
        result = set()
        for pair in self.existing_pairs:
            result |= {pair.app_port, pair.vector_port}
        return result

    def other(self, port):
        port = port.upper()
        for pair in self.existing_pairs:
            if pair.app_port == port:
                return pair.vector_port
            if pair.vector_port == port:
                return pair.app_port
        return ""

    def port_choices(self, side, current, owner):
        selected = set()
        for row in self.rows:
            if row is not owner:
                selected |= row.selected()
        start, end = (APP_COM_MIN, APP_COM_MAX) if side == "app" else (VECTOR_COM_MIN, VECTOR_COM_MAX)
        existing = self.existing()
        result = []
        for number in range(start, end + 1):
            port = f"COM{number}"
            if (
                (port not in self.active or port in existing)
                and (port not in self.busy or port in existing)
                and port not in selected
            ):
                result.append(port)
        if current and current not in result:
            result.insert(0, current)
        return result

    def refresh_rows(self):
        for row in self.rows:
            row.refresh()

    def clear(self):
        for row in self.rows:
            row.destroy()
        self.rows = []

    def addrow(self, desired):
        self.rows.append(ClientRow(self, desired))
        self.regrid()
        self.refresh_rows()

    def remove_row(self, row):
        row.destroy()
        self.rows.remove(row)
        self.regrid()
        self.refresh_rows()

    def regrid(self):
        for index, row in enumerate(self.rows):
            row.place(self.first_row + index)

    def nextfree(self, start, used):
        existing = self.existing()
        number = start
        while True:
            port = f"COM{number}"
            if (
                port not in used
                and (port not in self.active or port in existing)
                and (port not in self.busy or port in existing)
            ):
                return port
            number += 1

    def suggest(self):
        self.clear()
        used = set()
        app = 15
        vector = 101
        for name in ("LogHX", "N1MM"):
            cat_app = self.nextfree(app, used); used.add(cat_app); app = com_number(cat_app) + 1
            cat_vector = self.nextfree(vector, used); used.add(cat_vector); vector = com_number(cat_vector) + 1
            key_app = self.nextfree(app, used); used.add(key_app); app = com_number(key_app) + 1
            key_vector = self.nextfree(vector, used); used.add(key_vector); vector = com_number(key_vector) + 1
            self.addrow(DesiredClient(name, "CAT", cat_app, cat_vector, "KEYING", key_app, key_vector))

    def add_client(self):
        used = set()
        for row in self.rows:
            used |= row.selected()
        cat_app = self.nextfree(15, used); used.add(cat_app)
        cat_vector = self.nextfree(101, used); used.add(cat_vector)
        key_app = self.nextfree(15, used); used.add(key_app)
        key_vector = self.nextfree(101, used)
        self.addrow(DesiredClient(f"Cliente {len(self.rows)+1}", "CAT", cat_app, cat_vector, "KEYING", key_app, key_vector))

    def load_ini(self):
        if not CONFIG_PATH.exists():
            messagebox.showerror("Configuracao", f"Arquivo nao encontrado:\n{CONFIG_PATH}")
            return
        cfg = configparser.ConfigParser()
        cfg.read(CONFIG_PATH, encoding="utf-8-sig")
        cats = [item.strip().upper() for item in cfg.get("cat", "ports", fallback="").split(",") if item.strip()]
        keys = []
        if cfg.has_section("keying"):
            for key, value in cfg.items("keying"):
                match = CLIENT_RE.match(key)
                if not match:
                    continue
                parts = [item.strip() for item in value.split(",")]
                if len(parts) == 4:
                    name = parts[0] or f"Cliente {match.group(1)}"
                    port = parts[1].upper()
                elif len(parts) >= 3:
                    name = f"Cliente {match.group(1)}"
                    port = parts[0].upper()
                else:
                    continue
                keys.append((int(match.group(1)), name, port))
        keys.sort()
        count = max(len(cats), len(keys))
        self.clear()
        unresolved = []
        for index in range(count):
            cat_vector = cats[index] if index < len(cats) else ""
            name = keys[index][1] if index < len(keys) else f"Cliente {index+1}"
            key_vector = keys[index][2] if index < len(keys) else ""
            cat_app = self.other(cat_vector) if cat_vector else ""
            key_app = self.other(key_vector) if key_vector else ""
            if cat_vector and not cat_app:
                unresolved.append(cat_vector)
            if key_vector and not key_app:
                unresolved.append(key_vector)
            self.addrow(DesiredClient(name, "CAT" if cat_vector else "NONE", cat_app, cat_vector, "KEYING" if key_vector else "NONE", key_app, key_vector))
        message = f"vector.ini carregado: {count} cliente(s)."
        if unresolved:
            message += " Sem par conhecido para: " + ", ".join(unresolved)
        self.message.set(message)

    def pairs(self):
        result = []
        for row in self.rows:
            result += row.pairs()
        return result

    def keying_names_from_ini(self):
        result = {}
        if not CONFIG_PATH.exists():
            return result
        cfg = configparser.ConfigParser()
        cfg.read(CONFIG_PATH, encoding="utf-8-sig")
        if not cfg.has_section("keying"):
            return result
        for key, value in cfg.items("keying"):
            match = CLIENT_RE.match(key)
            if not match:
                continue
            parts = [item.strip() for item in value.split(",")]
            index = int(match.group(1))
            result[index] = parts[0] if len(parts) == 4 and parts[0] else f"Cliente {index}"
        return result

    def keying_name_changes(self):
        old = self.keying_names_from_ini()
        changes = []
        for index, row in enumerate(self.rows, 1):
            if row.key_type.get() == "NONE":
                continue
            new = row.name.get().strip() or f"Cliente {index}"
            previous = old.get(index, f"Cliente {index}")
            if new != previous:
                changes.append((index, previous, new))
        return changes

    def persist_keying_names(self):
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"Arquivo nao encontrado: {CONFIG_PATH}")
        desired = {}
        for index, row in enumerate(self.rows, 1):
            if row.key_type.get() != "NONE":
                desired[index] = row.name.get().strip() or f"Cliente {index}"
        text = CONFIG_PATH.read_text(encoding="utf-8-sig")
        lines = text.splitlines(keepends=True)
        inside = False
        changed = 0
        output = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                inside = stripped.lower() == "[keying]"
                output.append(line)
                continue
            if inside:
                match = KEYING_LINE_RE.match(line)
                if match:
                    index = int(match.group(3))
                    parts = [item.strip() for item in match.group(5).split(",")]
                    if index in desired:
                        if len(parts) == 4:
                            parts[0] = desired[index]
                        elif len(parts) >= 3:
                            parts = [desired[index]] + parts[:3]
                        newline = match.group(6) or "\n"
                        line = f"{match.group(1)}{match.group(2)}{match.group(4)}{','.join(parts)}{newline}"
                        changed += 1
            output.append(line)
        if changed:
            CONFIG_PATH.write_text("".join(output), encoding="utf-8")
        return changed

    def validate(self, desired):
        if not desired:
            return "Nenhum CAT ou KEYING configurado."
        names = []
        existing = self.existing()
        for item in desired:
            try:
                com_number(item.app_port)
                com_number(item.vector_port)
            except ValueError as exc:
                return str(exc)
            if item.app_port == item.vector_port:
                return "As duas pontas nao podem ser iguais."
            names += [item.app_port, item.vector_port]
            for port in (item.app_port, item.vector_port):
                if port in self.active and port not in existing:
                    return f"{port} pertence a dispositivo ativo."
        if len(names) != len(set(names)):
            return "Uma COM aparece mais de uma vez."
        return None

    def apply(self):
        if not is_admin():
            messagebox.showerror("Permissao", "Execute como Administrador.")
            return
        if not self.com0com:
            messagebox.showerror("com0com", "Recarregue o inventario.")
            return
        desired = self.pairs()
        error = self.validate(desired)
        if error:
            messagebox.showerror("Plano invalido", error)
            return
        current = {(pair.app_port, pair.vector_port): pair for pair in self.existing_pairs}
        wanted = {(item.app_port, item.vector_port) for item in desired}
        remove = [pair for key, pair in current.items() if key not in wanted]
        create = [item for item in desired if (item.app_port, item.vector_port) not in current]
        name_changes = self.keying_name_changes()
        if not remove and not create and not name_changes:
            messagebox.showinfo("Sem alteracoes", "COMs e nomes de clientes ja correspondem ao plano.")
            return
        summary = ["Alteracoes propostas:"]
        summary += [f"Remover #{pair.index}: {pair.app_port} <-> {pair.vector_port}" for pair in remove]
        summary += [f"Criar: {item.app_port} <-> {item.vector_port} ({item.name}/{item.kind})" for item in create]
        summary += [f"Renomear client{index}: {old} -> {new}" for index, old, new in name_changes]
        if not messagebox.askyesno("Confirmar", "\n".join(summary)):
            return

        def worker():
            total = max(1, len(remove) + len(create) + (1 if name_changes else 0))
            step = 0
            for pair in remove:
                self.progress_status(f"Operacao {step+1} de {total} - Removendo...", f"{pair.app_port} <-> {pair.vector_port}")
                self.com0com.remove_pair(pair.index)
                step += 1
            for item in create:
                self.progress_status(f"Operacao {step+1} de {total} - Criando...", f"{item.app_port} <-> {item.vector_port}")
                self.com0com.create_pair(item.app_port, item.vector_port)
                step += 1
            if name_changes:
                self.progress_status(f"Operacao {step+1} de {total} - Atualizando vector.ini...", "Persistindo nomes amigaveis dos clientes")
                self.persist_keying_names()
            self.progress_status("Finalizando...", "Relendo inventario")
            return self.collect()

        def ok(result):
            self.com0com, self.existing_pairs, self.active, self.busy = result
            self.render()
            self.refresh_rows()
            self.message.set("Configuracao aplicada. Nomes de clientes sincronizados com vector.ini.")

        self.work("Aplicando configuracao", worker, ok)


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("GADX Vector Port Manager requer Windows")
    App().mainloop()
