# GADX Vector — Phase D Installer

Esta pasta concentra a geracao atual do instalador/reparador do GADX Vector Hub.

## Status

```text
D1 — Detector/classificador ................. VALIDADO
D2 — Backup + migracao de configuracao ...... VALIDADO
D3 — Migracao/troca transacional do servico  VALIDADO
D4 — Runtime privado + com0com ............... VALIDADO
D5 — Clean install + Port Manager ............ VALIDADO
D6 — Post-install / commissioning ............ VALIDADO
D7 — Current repair/update ................... VALIDADO EM CAMPO
D8 — Productization / release packaging ...... PROXIMO
```

A validacao cobre instalacao limpa, migracao de ambiente legado e repair/update de uma instalacao atual com payload divergente, preservando `vector.ini` e pares com0com existentes.

---

## Ponto de entrada recomendado

Para uma maquina que ja possua apenas o bootstrap local:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "$env:TEMP\gadx-vector-bootstrap.ps1" `
  -InstallRoot "C:\Ham\GADX-Vector"
```

Preview apenas; nao altera a maquina.

Para aplicar:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "$env:TEMP\gadx-vector-bootstrap.ps1" `
  -InstallRoot "C:\Ham\GADX-Vector" `
  -Apply
```

`bootstrap-vector.ps1` baixa a versao atual de `main`, atualiza somente a pasta `installer` local e entrega o controle a `setup-vector.ps1`.

---

# D1 — Detector/classificador

Arquivo:

```text
installer/detect-installation.ps1
```

O detector e read-only e classifica a maquina em:

```text
CLEAN
CURRENT
LEGACY
BROKEN
```

Planos possiveis:

```text
INSTALL
MIGRATE
MIGRATE_REPAIR
REPAIR
NONE
```

Tambem e usado payload drift: uma instalacao estruturalmente CURRENT pode ser encaminhada para REPAIR quando app/service/tools instalados diferem do payload atual.

---

# D2 — Backup e migracao de configuracao

Arquivos:

```text
installer/plan-migration.ps1
installer/apply-migration.ps1
```

O fluxo:

- prioriza `bridge_multi.ini` quando presente;
- le CAT, keying, radio keying, rigctld e permissoes;
- cria backup timestampado;
- gera `config\vector.ini` atual;
- preserva INIs antigos;
- nao renumera pares com0com existentes sem necessidade.

Clientes legados sem nome amigavel recebem identificadores genericos e podem ser renomeados no Port Manager.

---

# D3 — Migracao/troca transacional do servico

Arquivo:

```text
installer/migrate-service.ps1
```

Fluxo:

```text
validar payload/runtime/vector.ini
        ↓
deploy payload atual
        ↓
parar GADXVectorBridge temporariamente
        ↓
instalar GADXVectorHub
        ↓
configurar delayed-auto + recovery
        ↓
iniciar e validar estabilidade
        ↓
SUCESSO: remover GADXVectorBridge
FALHA:   rollback seguro
```

Preview nao exige runtime ja presente; `-Apply` exige os pre-requisitos antes de alterar service state.

---

# D4 — Runtime privado + com0com

Arquivo:

```text
installer/ensure-runtime.ps1
```

Runtime atual:

```text
C:\Ham\GADX-Vector\runtime\python.exe
Python 3.10.x x64
Tcl/Tk / tkinter
pyserial == 3.5
pywin32 == 312
```

O script valida os imports reais em vez de confiar apenas na existencia de `python.exe`.

## Reuso de Python existente

Se um Python 3.10 x64 com Tcl/Tk ja existir, o instalador pode clona-lo para o runtime privado sem alterar a instalacao original.

A descoberta inclui:

- Python Launcher (`py.exe -3.10`);
- PEP 514 / Registry;
- PATH;
- locais comuns;
- `C:\Python\Python310\python.exe`;
- instalacoes em perfis locais.

Compatibilidade e testada por exit code:

```python
sys.version_info[:2] == (3, 10)
struct.calcsize("P") * 8 == 64
import tkinter
```

## Host de Windows Service do pywin32

Para manter o produto isolado, o host e preparado dentro do proprio runtime:

```text
runtime\pythonservice.exe
runtime\python310.dll
runtime\pywintypes310.dll
runtime\pythoncom310.dll
```

O staging aceita `pythonservice.exe` ainda em `Lib\site-packages\win32` ou ja movido para `runtime\` pelo proprio pywin32.

Validacao:

```text
PYWIN32_SERVICE_HOST_OK
```

Nao e necessario copiar DLLs do Vector para `C:\Windows\System32`.

## com0com

O instalador localiza `setupc.exe` em caminhos conhecidos e preserva pares existentes durante Repair/Migration.

---

# D5 — Clean install + Port Manager

A instalacao limpa prepara:

- diretorio `C:\Ham\GADX-Vector`;
- runtime privado;
- com0com;
- payload atual;
- service/tools;
- Port Manager;
- configuracao inicial a ser revisada pelo operador.

Politica de novas COMs:

```text
Aplicativo: COM15 em diante
Vector:     COM101 em diante
```

Portas ocupadas/reservadas sao puladas. Instalacoes existentes preservam COMs legadas quando validas.

---

# D6 — Post-install / commissioning

Arquivo:

```text
installer/post-install-check.ps1
```

Valida, entre outros pontos:

- runtime;
- Tcl/Tk;
- pyserial/pywin32;
- com0com;
- `vector.ini`;
- payload atual;
- `GADXVectorHub`;
- enumeracao de COMs esperadas;
- estado seguro do radio.

D6 foi validada em instalacao limpa real.

---

# D7 — Current repair/update

Arquivo:

```text
installer/repair-current.ps1
```

D7 e o caminho para uma instalacao CURRENT que precisa receber payload novo ou ser reparada sem perder configuracao operacional.

## Safety gate

Antes de runtime/download/update:

```text
GADXVectorHub -> Disabled
GADXVectorHub -> forced Stopped
```

Nenhum deploy comeca se o Hub nao puder ser colocado em estado seguro.

## Transacao D7

```text
1. quiesce do Hub
2. ensure runtime/com0com
3. backup timestampado
4. deploy app/service/tools atuais
5. confirmar SHA de vector.ini inalterado
6. validar vector.ini com o Hub novo
7. reinstalar GADXVectorHub
8. delayed-auto + recovery
9. iniciar e exigir estabilidade
10. exigir log novo com "Vector Hub ready"
11. consultar rigctld e exigir PTT = 0
12. remover GADXVectorBridge somente apos saude confirmada
13. gravar installed-build.txt
```

D7 nunca reescreve `vector.ini` nem pares com0com em um CURRENT/REPAIR.

## Backup e rollback

Exemplo:

```text
C:\Ham\GADX-Vector\backups\repair-YYYYMMDD-HHMMSS
```

Backup inclui app/service/tools, configuracao e log atual.

Em falha:

- a tentativa nova e interrompida;
- o log da tentativa e preservado como `failed-vector-hub.log` quando disponivel;
- arquivos anteriores sao restaurados;
- o service e deixado `Stopped / Disabled` sempre que possivel.

Isso prioriza seguranca do radio sobre disponibilidade automatica.

## Manifesto

Em sucesso:

```text
C:\Ham\GADX-Vector\config\installed-build.txt
```

Contem timestamp UTC, fase do instalador, backup associado e SHA256 dos artefatos instalados.

## Validacao de campo

D7 foi validada em 2026-09-06 numa instalacao antiga/problematicamente divergente com:

```text
IC-7760
rigctld 127.0.0.1:4532
COM22 / RTS para CW fisico
PTT por RIGCTLD
LogHX + N1MM + OmniRig
COMs Vector COM101..COM106
COMs de aplicativo existentes preservadas
```

Resultado:

```text
GADXVectorHub      Running / delayed-auto
GADXVectorBridge   removido
vector.ini         preservado
com0com pairs      preservados
PTT safe state     OFF
INSTALLATION STATUS: READY
```

CAT, PTT, CW e restart/fail-safe passaram nos testes funcionais finais.

---

## Regras de seguranca consolidadas

- preservar `vector.ini` em Repair;
- preservar pares com0com existentes durante Migration/Repair;
- nunca sobrescrever COM ocupada silenciosamente;
- backup antes de conversao/deploy transacional;
- nunca remover `GADXVectorBridge` antes de o novo Hub estar saudavel;
- abrir a serial fisica com RTS/DTR desassertados antes de `open()` e reafirmar OFF depois;
- fail-safe independente do child process;
- PTT/CW devem terminar OFF em stop/failure/restart;
- em rollback D7, disponibilidade e secundaria a deixar o radio seguro;
- Preview nunca deve alterar service/runtime/configuracao.

---

# D8 — Proxima etapa: Productization / Release packaging

D1-D7 provaram a arquitetura e o reparo em maquinas reais. D8 deve transformar esse fluxo tecnico em um instalador distribuivel para o operador final.

## Objetivo

Reduzir o uso normal de PowerShell/comandos manuais para uma experiencia de produto, mantendo exatamente os mesmos safety gates internos.

Escopo proposto:

```text
1. definir artefato de distribuicao/versionamento
2. launcher unico de Install / Repair / Update
3. UX de Preview -> Confirmar -> Apply
4. mostrar plano e estado de seguranca antes de alterar a maquina
5. empacotar/obter dependencias de forma previsivel
6. integrar Port Manager no fluxo visual
7. tela/relatorio final de commissioning
8. versao/build visivel ao operador
9. mecanismo simples de update usando o bootstrap ja validado
10. preparar uma Release Candidate instalavel em maquina limpa
```

## Criterio de aceite inicial de D8

Um operador em Windows 10/11 deve conseguir sair de uma maquina limpa ou instalacao existente para `INSTALLATION STATUS: READY` sem precisar conhecer scripts internos, caminhos Python ou comandos de service management.

O backend tecnico de D8 deve reutilizar D1-D7; D8 nao deve reescrever a logica de seguranca ja validada.
