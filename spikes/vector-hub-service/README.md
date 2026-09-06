# GADX Vector — Vector Hub Runtime / Service / Installer SPIKE

## Status

**ACTIVE / SPIKE 02 — D7 FIELD-VALIDATED BASELINE**

Este SPIKE sucede `../cat-ts2000/`, congelado apos validar a fachada TS-2000, CAT multi-client e keying low-latency.

Estado atual:

- **Fase A — Runtime: VALIDADA**;
- **Fase B — Windows Service: VALIDADA**;
- **Fase C — Vector Port Manager: VALIDADA E CONGELADA**;
- **Fase D — Installer / Repair / Migration: VALIDADA ATE D7**;
- **D8 — Productization / Release packaging: PROXIMA ETAPA**.

Em 2026-09-06 o fluxo D7 de repair/update foi validado em campo numa instalacao antiga/problematicamente divergente, preservando `vector.ini`, pares COM e funcionalidade CAT/PTT/CW.

---

## Estrutura atual

```text
spikes/vector-hub-service/
├── README.md
├── VALIDATION.md
├── app/
│   ├── vector_hub.py
│   └── ts2000.py
├── config/
│   └── vector.ini
├── service/
│   ├── vector_service.py
│   ├── install-service.ps1
│   └── uninstall-service.ps1
├── tools/
│   ├── port_manager.py
│   └── README.md
└── installer/
    ├── README.md
    ├── bootstrap-vector.ps1
    ├── setup-vector.ps1
    ├── detect-installation.ps1
    ├── plan-migration.ps1
    ├── apply-migration.ps1
    ├── migrate-service.ps1
    ├── ensure-runtime.ps1
    ├── prepare-clean-install.ps1
    ├── post-install-check.ps1
    ├── repair-current.ps1
    └── payload/
        ├── app/
        ├── service/
        └── tools/
```

---

## Arquitetura consolidada

```text
                            GADX VECTOR HUB

 CAT clients                                      Keying clients
 COM101 -- TS2000 adapter --\                    COM102 --\
 COM103 -- TS2000 adapter ---+-- shared rig -->  COM104 ---+-- logical states
 COM105 -- TS2000 adapter ---+   rigctld         COM106 --/        |
 COM107 -- TS2000 adapter --/                                  physical COM
                                                                  |
                                                               PTT / CW
```

Cada software possui sua propria COM virtual. O Hub nunca depende de dois processos abrirem a mesma COM.

TS-2000 e a fachada de compatibilidade; Hamlib/rigctld permanece como adapter do radio fisico, nao como protocolo interno do produto.

---

## Conceito de pares COM

Cada canal virtual usa um par com0com:

```text
COM do aplicativo  <->  COM interna do Vector
```

Politica para novas instalacoes:

```text
lado apresentado aos aplicativos: COM15 em diante
lado interno do Vector:           COM101 em diante
```

Portas ocupadas, fisicas, reservadas ou pertencentes a outro par sao puladas.

Instalacoes existentes preservam COMs legadas sempre que ainda validas. Exemplo real validado em D7:

```text
LogHX CAT       COM9  <-> COM101
LogHX KEYING    COM29 <-> COM102
N1MM CAT        COM15 <-> COM103
N1MM KEYING     COM30 <-> COM104
OmniRig CAT     COM16 <-> COM105
OmniRig KEYING  COM31 <-> COM106
```

---

## CAT x KEYING

CAT e o canal de controle de frequencia, modo e comandos.

KEYING e separado e transporta PTT/CW por DTR/RTS. O caminho de CW permanece fora de chamadas bloqueantes do rigctld para preservar baixa latencia e baixo jitter.

Estados multi-client de PTT/CW sao mantidos por fonte e consolidados por OR logico.

---

## Configuracao principal

Arquivo:

```text
C:\Ham\GADX-Vector\config\vector.ini
```

Formato recomendado:

```ini
[cat]
ports = COM101, COM103, COM105
baud = 19200

[keying]
; clientN = NOME,PORTA_VECTOR,PTT_INPUT,CW_INPUT
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

[runtime]
allow_write = true
allow_ptt = true
allow_cw = true

[service]
startup = delayed-auto
recovery = restart

[logging]
level = INFO
max_mb = 5
backups = 5

[ports]
application_start = 15
vector_start = 101
```

O runtime continua aceitando o formato legado de tres campos:

```ini
client1 = COM102,DTR,RTS
```

---

## Fail-safe de radio

Fail-safe tem prioridade sobre disponibilidade.

A serial fisica nunca deve ser aberta deixando o driver escolher primeiro o estado de RTS/DTR. O baseline atual usa pre-open seguro:

```python
out = serial.Serial(port=None, baudrate=..., timeout=0, write_timeout=None)
out.rts = False
out.dtr = False
out.port = serial_port
out.open()
out.rts = False
out.dtr = False
```

O Windows Service possui uma camada independente de `force_safe_state()` que tenta:

- desassertar RTS/DTR da porta fisica;
- enviar PTT OFF ao rigctld;
- repetir o fail-safe ao parar/falhar/reiniciar.

O D7 tambem desabilita e para o service antes de runtime/download/update.

---

## Runtime privado

Baseline:

```text
C:\Ham\GADX-Vector\runtime\python.exe
Python 3.10.x x64
Tcl/Tk / tkinter
pyserial 3.5
pywin32 312
```

O runtime pode ser criado a partir de Python 3.10 x64 + Tcl/Tk ja existente, sem alterar a instalacao de origem.

O host de Windows Service permanece local ao produto:

```text
runtime\pythonservice.exe
runtime\python310.dll
runtime\pywintypes310.dll
runtime\pythoncom310.dll
```

Nao e necessario instalar DLLs do Vector em `System32`.

---

## Windows Service

Servico:

```text
GADXVectorHub
Automatic (Delayed Start)
Recovery: restart on failure
Account: LocalSystem
```

`service/vector_service.py`:

- aplica fail-safe antes/depois do child;
- executa o Hub com o Python privado;
- grava `logs\vector-hub.log`;
- limita logs por tamanho/backups;
- detecta child que morre durante startup;
- encerra o Hub e radio de forma segura em stop/failure.

---

## Vector Port Manager

Ferramenta:

```text
tools/port_manager.py
```

Fase C esta congelada como baseline funcional.

Valida:

- inventario de COMs ativas;
- pares com0com;
- nomes reservados;
- carga do `vector.ini`;
- nomes amigaveis;
- criacao/remocao/revisao de clientes;
- dropdowns de portas disponiveis;
- preservacao de comentarios no INI;
- resumo e confirmacao antes de aplicar.

Mudancas futuras devem ser apenas bug real ou integracao necessaria.

---

# Fase D — Installer / Repair / Migration

## Status atual

```text
D1 — Detector/classificador ................. VALIDADO
D2 — Backup + migracao de configuracao ...... VALIDADO
D3 — Migracao/troca transacional do servico  VALIDADO
D4 — Runtime privado + com0com ............... VALIDADO
D5 — Clean install + Port Manager ............ VALIDADO
D6 — Post-install / commissioning ............ VALIDADO
D7 — Current repair/update ................... VALIDADO EM CAMPO
```

Detalhes operacionais ficam em `installer/README.md`. Evidencias de bancada/campo ficam em `VALIDATION.md`.

---

## Bootstrap / update

O bootstrap permite atualizar o instalador local antes de executar o plano detectado:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "$env:TEMP\gadx-vector-bootstrap.ps1" `
  -InstallRoot "C:\Ham\GADX-Vector"
```

Preview nao altera a maquina.

Apply:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "$env:TEMP\gadx-vector-bootstrap.ps1" `
  -InstallRoot "C:\Ham\GADX-Vector" `
  -Apply
```

---

## D7 — Current repair/update

D7 foi criado para reparar/atualizar uma instalacao CURRENT sem reconfigurar a estacao.

Invariantes:

```text
vector.ini         PRESERVADO
pares com0com      PRESERVADOS
radio safety       PRIORIDADE
backup             OBRIGATORIO
rollback           TRANSACIONAL
```

Fluxo:

```text
quiesce GADXVectorHub
        ↓
ensure runtime/com0com
        ↓
backup timestampado
        ↓
deploy payload atual
        ↓
validar vector.ini
        ↓
reinstalar service
        ↓
delayed-auto + recovery
        ↓
health check
        ↓
"Vector Hub ready"
        ↓
rigctld PTT = 0
        ↓
remover bridge legado
        ↓
installed-build.txt
```

Em falha, o log da tentativa e preservado quando possivel e a instalacao anterior e restaurada, deixando o Hub parado/desabilitado para seguranca.

---

## Validacao de campo D7 — 2026-09-06

Cenario:

```text
IC-7760
CAT fisico do radio: COM20 via rigctld
CW fisico: COM22 / RTS @ 9600
PTT: RIGCTLD
LogHX + N1MM + OmniRig
```

Resultado final:

```text
GADXVectorHub      Running / delayed-auto
GADXVectorBridge   removido
vector.ini         SHA256 preservado
pares COM          preservados
CAT                OK
PTT                OK
CW                 OK
restart/fail-safe  OK
PTT final          OFF
INSTALLATION STATUS: READY
```

Esse resultado passa a ser o baseline estavel conhecido para evolucao posterior.

---

## Principios consolidados

1. Uma COM virtual por cliente/canal.
2. TS-2000 e fachada; o radio fisico fica atras de rigctld.
3. CAT e keying sao independentes.
4. RTS/DTR pertencem ao INI da instalacao.
5. CW fica fora de polling/chamadas bloqueantes do rigctld.
6. PTT/CW multi-client usam estados por fonte + OR logico.
7. COMs internas altas; COMs de aplicativo baixas quando possivel.
8. Fail-safe tem prioridade sobre disponibilidade.
9. ComDB sozinho nao define disponibilidade.
10. O operador revisa o plano de COMs antes de aplicar.
11. Repair preserva configuracao valida.
12. Migration preserva COMs validas sempre que possivel.
13. Configuracao antiga nunca e descartada sem backup.
14. Mudancas de pares com0com podem exigir reboot.
15. Payload novo nunca deve remover o service legado antes de o novo Hub estar saudavel.
16. Uma instalacao CURRENT com payload drift deve entrar em REPAIR.
17. Preview e read-only.
18. Rollback deve deixar o radio em estado seguro.

---

# D8 — Productization / Release packaging

D1-D7 provaram a arquitetura tecnica. D8 passa a responder outra pergunta:

> Como transformar esse baseline validado em um produto Windows instalavel por um operador sem conhecimento dos scripts internos?

## Objetivo D8

Criar uma experiencia de instalacao/update/repair distribuivel, reutilizando D1-D7 como backend e sem reabrir a logica de seguranca validada.

Escopo inicial:

```text
1. artefato/versionamento de release
2. launcher unico Install / Repair / Update
3. UX Preview -> Confirmar -> Apply
4. resumo visual do safety gate
5. dependencias obtidas/empacotadas de forma previsivel
6. Port Manager integrado ao fluxo
7. commissioning final visivel ao operador
8. versao/build instalada visivel
9. update baseado no bootstrap validado
10. Release Candidate para maquina limpa
```

Criterio de aceite inicial:

```text
Windows 10/11
        ↓
operador abre um unico instalador/launcher
        ↓
instalador detecta CLEAN/CURRENT/LEGACY/BROKEN
        ↓
mostra plano
        ↓
operador confirma
        ↓
executa D1-D7 conforme necessario
        ↓
Port Manager quando aplicavel
        ↓
commissioning
        ↓
INSTALLATION STATUS: READY
```

O operador nao deve precisar conhecer Python, `sc.exe`, caminhos internos ou scripts PowerShell.

---

## Decisoes ainda fora do baseline D7

Pontos para fases posteriores ou testes especificos:

- conflitos de escrita CAT simultanea;
- reconexao depois de queda/reinicio do rigctld;
- reservas ComDB orfas;
- service recovery quando COMs ainda nao enumeraram no boot;
- split/VFO A/B multi-client;
- eventual PTT por comando CAT no mesmo OR das fontes de keying;
- politica final de Uninstall e preservacao de configuracao.
