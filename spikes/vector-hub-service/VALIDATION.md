# Vector Hub SPIKE 02 — Validation log

## Status geral

**BASELINE VALIDADO EM CAMPO — 2026-09-06**

O conjunto Runtime + Windows Service + Port Manager + Installer D1-D7 foi validado em maquinas reais, incluindo uma instalacao antiga/problematicamente divergente que foi reparada sem renumerar COMs nem perder `vector.ini`.

---

## Phase A — Runtime

**Status: VALIDATED**

Data inicial: 2026-08-10

A Fase A foi validada manualmente em uma estacao que ainda utilizava a primeira geracao single-client, anterior ao instalador e anterior ao ambiente multi-client mais recente.

Configuracao da estacao:

```text
CAT Vector:       COM18 @ 19200
Keying Vector:    COM32 @ 19200
CW fisico:        COM22 / RTS @ 9600
PTT fisico:       rigctld
rigctld:          127.0.0.1:4532
```

O `vector_hub.py` foi executado manualmente com `config/vector.ini` e manteve o comportamento funcional esperado.

### Aprendizado adicional

`radio_keying.ptt_line` precisa aceitar `RIGCTLD` alem de `RTS`, `DTR` e `NONE`, porque existem instalacoes validas em que CW usa uma linha serial fisica enquanto PTT permanece controlado pelo Hamlib.

Isso reforca o principio de que PTT e CW sao canais de saida configuraveis independentemente.

---

## Phase B — Windows Service

**Status: VALIDATED**

Artefatos:

```text
service/vector_service.py
service/install-service.ps1
service/uninstall-service.ps1
```

Servico atual:

```text
GADXVectorHub
Automatic (Delayed Start)
Recovery: restart on failure
Account: LocalSystem
```

Validado com Hub executando como Windows Service, log ativo, CAT/keying funcionais e fail-safe aplicado na partida, parada, falha e reinicio.

---

## Phase C — Vector Port Manager

**Status: VALIDATED / FROZEN**

O Port Manager foi validado em mais de uma maquina para inventario de COMs, leitura de pares com0com, carga/persistencia de `vector.ini`, nomes amigaveis, criacao/remocao de clientes e revisao visual do plano antes de aplicar alteracoes.

O requisito de Tcl/Tk foi incorporado ao runtime privado porque `tools/port_manager.py` usa Tkinter.

---

# Phase D — Installer / Repair / Migration

## Status consolidado

```text
D1 — Detector/classificador ................. VALIDADO
D2 — Backup + migracao de configuracao ...... VALIDADO
D3 — Migracao/troca transacional do servico  VALIDADO
D4 — Runtime privado + com0com ............... VALIDADO
D5 — Clean install + Port Manager ............ VALIDADO
D6 — Post-install / commissioning ............ VALIDADO
D7 — Current repair/update ................... VALIDADO EM CAMPO
```

---

## D7 — Field validation — 2026-09-06

### Cenario

Maquina antiga que ja havia funcionado anteriormente, mas passou a apresentar risco de transmissao aleatoria e divergencia entre arquivos instalados e configuracao atual.

Topologia preservada:

```text
Radio: IC-7760
rigctld: 127.0.0.1:4532
CAT fisico do radio: COM20
CW fisico: COM22 / RTS @ 9600
PTT fisico: RIGCTLD

LogHX:
  CAT    COM9  <-> COM101
  KEYING COM29 <-> COM102

N1MM:
  CAT    COM15 <-> COM103
  KEYING COM30 <-> COM104

OmniRig:
  CAT    COM16 <-> COM105
  KEYING COM31 <-> COM106
```

`vector.ini` utilizado:

```ini
[keying]
client1 = LogHX,COM102,DTR,RTS
client2 = N1MM,COM104,DTR,RTS
client3 = OmniRig,COM106,DTR,NONE

[radio_keying]
port = COM22
baud = 9600
ptt_line = RIGCTLD
cw_line = RTS

[rig]
host = 127.0.0.1
port = 4532
poll_ms = 250
```

### Problemas encontrados

1. A instalacao antiga possuia um `vector_hub.py` que aceitava apenas o formato legado de tres campos `PORT,PTT,CW`, enquanto o `vector.ini` ja usava quatro campos `NAME,PORT,PTT,CW`.
2. O Hub antigo entrava repetidamente em erro de configuracao, criando um ambiente propenso a reinicios/recovery.
3. A abertura da serial fisica ocorria antes de desassertar RTS/DTR, permitindo um pulso de modem-line durante `open()` em determinados drivers/hardwares.
4. O instalador D7 precisou aprender a reutilizar Python 3.10 x64 + Tcl/Tk ja existente e construir um runtime privado consistente.
5. O host de Windows Service do pywin32 precisou ser preparado de forma totalmente local ao runtime privado, incluindo `pythonservice.exe`, `pywintypes310.dll` e `pythoncom310.dll`.

### Correcoes de seguranca validadas

A serial fisica agora e aberta com RTS/DTR desassertados antes e depois de `open()`:

```python
out = serial.Serial(port=None, baudrate=..., timeout=0, write_timeout=None)
out.rts = False
out.dtr = False
out.port = "COM22"
out.open()
out.rts = False
out.dtr = False
```

O mesmo principio e usado no fail-safe independente do Windows Service.

O D7 tambem aplica um safety gate antes de qualquer reparo:

```text
GADXVectorHub -> Disabled
GADXVectorHub -> Stopped
```

Somente depois disso runtime, payload e service registration podem ser alterados.

### Runtime privado validado

Runtime final:

```text
C:\Ham\GADX-Vector\runtime\python.exe
Python 3.10.11 x64
Tcl/Tk / tkinter 8.6
pyserial 3.5
pywin32 312
pythonservice.exe
pywintypes310.dll
pythoncom310.dll
```

O Python 3.10.11 existente em `C:\Python\Python310\python.exe` foi detectado e usado como fonte para o runtime privado sem alterar a instalacao original.

### D7 transaction validada

Fluxo executado com sucesso:

```text
quiesce / safety gate
        ↓
ensure runtime + com0com
        ↓
backup timestampado
        ↓
deploy payload atual
        ↓
validar vector.ini preservado
        ↓
reinstalar GADXVectorHub
        ↓
configurar delayed-auto + recovery
        ↓
iniciar e validar por health check
        ↓
confirmar "Vector Hub ready"
        ↓
confirmar rigctld PTT = 0
        ↓
remover GADXVectorBridge legado
        ↓
gravar installed-build.txt
```

Backup final da validacao:

```text
C:\Ham\GADX-Vector\backups\repair-20260906-193039
```

### Evidencia final

Servico:

```text
GADXVectorHub  Running
StartMode      Auto (DelayedAutoStart configurado pelo instalador)
GADXVectorBridge removido
```

Log final:

```text
GADX Vector Hub Phase A
Configuration file: C:\Ham\GADX-Vector\config\vector.ini
CAT ports: COM101,COM103,COM105 @ 19200
Keying clients: LogHX:COM102, N1MM:COM104, OmniRig:COM106
Physical keying: COM22 @ 9600 PTT=RIGCTLD CW=RTS
Connected to rigctld
Keying LogHX ready
Keying N1MM ready
Keying OmniRig ready
CAT client ready: COM101
CAT client ready: COM103
CAT client ready: COM105
Vector Hub ready
```

Manifesto criado:

```text
C:\Ham\GADX-Vector\config\installed-build.txt
installer_phase = D7
```

### Testes funcionais finais

Passaram em campo:

- CAT LogHX;
- CAT N1MM;
- CAT OmniRig;
- retorno de estado do radio para os clientes;
- PTT;
- CW LogHX;
- CW N1MM;
- OmniRig com `CW=NONE` sem chaveamento indevido;
- restart do servico;
- fail-safe de PTT/CW;
- preservacao de `vector.ini`;
- preservacao dos pares COM existentes;
- remocao segura de `GADXVectorBridge` somente apos o novo Hub estar saudavel.

**Resultado final: `INSTALLATION STATUS: READY`.**

---

## Baseline apos D7

A combinacao abaixo passa a ser o baseline estavel conhecido do SPIKE 02:

```text
vector_hub.py multi-client
vector_service.py com fail-safe
Port Manager congelado
runtime Python privado 3.10.x + Tcl/Tk + pyserial + pywin32
bootstrap-vector.ps1
setup-vector.ps1
repair-current.ps1
post-install-check.ps1
installed-build.txt
```

Mudancas futuras devem preservar os invariantes de seguranca e a compatibilidade com instalacoes existentes.

---

# Proxima fase — D8

D8 sera a fase de **productization / release packaging** do instalador: transformar o fluxo tecnico ja validado em uma experiencia distribuivel, repetivel e simples para o operador final, sem perder os safety gates e mecanismos de rollback da D7.
