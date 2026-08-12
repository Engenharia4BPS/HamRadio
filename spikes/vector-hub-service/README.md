# GADX Vector — Vector Hub Runtime / Service / Installer SPIKE

## Status

**ACTIVE / SPIKE 02**

Este SPIKE sucede `../cat-ts2000/`, congelado apos validar a fachada TS-2000, CAT multi-client e keying low-latency.

Estado atual:

- **Fase A — Runtime: VALIDADA**;
- **Fase B — Windows Service: VALIDADA**;
- **Fase C — Vector Port Manager: VALIDADA E CONGELADA**;
- **Fase D — Installer / Repair / Migration / Uninstall: EM DESENVOLVIMENTO**.

A pergunta atual passa a ser:

> Conseguimos transformar o conjunto Runtime + Service + Port Manager ja validado em uma instalacao Windows completa, repetivel, reparavel, migravel e segura?

---

## Estrutura atual

```text
spikes/vector-hub-service/
├── README.md
├── app/
│   ├── vector_hub.py
│   └── ts2000.py
├── config/
│   └── vector.ini
├── service/
│   ├── vector_service.py
│   ├── install-service.ps1
│   └── uninstall-service.ps1
└── tools/
    ├── port_manager.py
    └── README.md
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

---

## Conceito de pares COM

Cada canal virtual usa um par com0com:

```text
COM do aplicativo  <->  COM interna do Vector
```

Exemplo:

```text
Log4OM CAT       COM15 <-> COM101
Log4OM KEYING    COM16 <-> COM102
N1MM CAT         COM17 <-> COM103
N1MM KEYING      COM18 <-> COM104
OmniRig CAT      COM19 <-> COM105
OmniRig KEYING   COM20 <-> COM106
```

A ponta **Aplicativo** e configurada dentro do Log4OM, N1MM, OmniRig etc. A ponta **Vector** e aberta exclusivamente pelo `vector_hub.py`.

Instalacoes existentes podem manter COMs legadas, por exemplo COM9/COM29. A migracao nao deve renumerar portas que ja funcionam sem necessidade.

---

## CAT x KEYING

CAT e o canal de controle do radio: frequencia, modo e comandos. O software cliente enxerga uma fachada TS-2000; o radio fisico continua atras do Hamlib/rigctld.

KEYING e separado de CAT e transporta PTT/CW por linhas DTR/RTS. O caminho de CW permanece fora de chamadas bloqueantes do rigctld para preservar baixa latencia e baixo jitter.

---

## Configuracao principal

O arquivo principal da arquitetura atual e:

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
client1 = Log4OM,COM102,DTR,RTS
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

O runtime continua aceitando o formato legado de keying:

```ini
client1 = COM102,DTR,RTS
```

Nesse caso ferramentas e logs usam identificadores genericos como `Cliente 1` / `client1`.

---

## Politica de portas COM

Para novas instalacoes:

```text
lado apresentado aos aplicativos: tentar COM15, COM16, COM17... em ordem crescente
lado interno do Vector:           tentar COM101, COM102, COM103... em ordem crescente
```

COM15 e apenas o primeiro candidato. Nenhuma porta ativa, fisica, reservada ou ja pertencente a outro par deve ser sobrescrita silenciosamente.

Repair/Migration deve preferir preservar pares existentes quando eles ainda sao validos.

---

## Principios consolidados

1. Uma COM virtual por cliente/canal.
2. TS-2000 e fachada; o radio fisico fica atras do Hamlib/rigctld.
3. CAT e keying sao canais independentes.
4. RTS/DTR pertencem ao INI da instalacao, nao ao modelo de radio no codigo.
5. CW e tempo-critico e fica fora de polling/chamadas bloqueantes do rigctld.
6. Estados multi-client de PTT/CW sao mantidos por fonte e consolidados logicamente.
7. COMs altas sao internas; COMs baixas sao apresentadas aos softwares sempre que possivel.
8. Fail-safe tem prioridade: parar, falhar ou reiniciar nao pode deixar PTT/CW acionados.
9. ComDB sozinho nao define disponibilidade: o provisionador cruza pares com0com, portas ativas e reservas.
10. O operador deve conseguir ver e aprovar o plano antes da criacao/remocao de COMs.
11. Nomes amigaveis de clientes fazem parte da configuracao gerenciada e ajudam diagnostico futuro.
12. Repair nao e apenas reinstalacao: ele tambem deve corrigir instalacoes incompletas e migrar instalacoes legadas quando necessario.
13. Migracao deve preservar configuracao e COMs validas sempre que possivel.
14. Arquivos de configuracao antigos nunca devem ser descartados sem backup.
15. Alteracoes de driver/pares com0com exigem reboot antes da validacao final da instalacao.

---

# Fase A — Runtime

`app/vector_hub.py` e a evolucao da multi-bridge congelada.

Validado em bancada com:

- CAT multi-client;
- escrita de frequencia/modo;
- PTT por rigctld;
- CW serial low-latency;
- estados independentes por cliente;
- nomes amigaveis em `[keying]`;
- compatibilidade com formato legado.

**Status: CONCLUIDA.**

---

# Fase B — Windows Service

`service/vector_service.py` executa o Hub, usa `vector.ini`, aplica fail-safe, gira logs e foi validado como Windows Service.

Servico atual:

```text
GADXVectorHub
Automatic (Delayed Start)
Recovery: restart on failure
```

**Status: CONCLUIDA.**

---

# Fase C — GADX Vector Port Manager

Ferramenta:

```text
tools/port_manager.py
```

A Fase C foi validada em mais de uma maquina e fica congelada como baseline funcional para a Fase D.

## Funcionalidades validadas

O Port Manager consegue:

- inventariar portas COM ativas do Windows;
- localizar `setupc.exe` do com0com;
- consultar pares com0com e nomes reservados;
- esconder consoles auxiliares durante operacoes normais;
- mostrar progresso visual e etapa atual;
- mostrar cada cliente em uma unica linha;
- separar visualmente CAT e KEYING;
- usar dropdowns de portas disponiveis;
- adicionar/remover clientes no plano;
- sugerir COMs livres;
- carregar `vector.ini` existente;
- cruzar COMs internas do INI com a outra ponta do par com0com;
- ler nomes amigaveis de `clientN`;
- usar fallback `Cliente N` em configuracoes legadas;
- detectar alteracoes de nome mesmo quando nenhuma COM mudou;
- persistir nomes amigaveis no `[keying]` preservando comentarios do INI;
- mostrar resumo antes de aplicar alteracoes;
- oferecer tooltips em campos, cabecalhos e botoes;
- abrir ajuda completa pelo botao `?`.

## Fluxo validado de uso

Para alterar uma estacao existente:

1. executar o Port Manager como Administrador;
2. aguardar o inventario inicial;
3. clicar em **Carregar configuracao atual**;
4. conferir nomes, CAT, KEYING e os dois lados de cada par;
5. alterar/adicionar/remover somente o necessario;
6. clicar em **Aplicar configuracao**;
7. ler o resumo das alteracoes;
8. confirmar somente se o plano estiver correto.

**Recarregar inventario** apenas consulta novamente Windows/com0com e nao altera a configuracao.

## Requisito de runtime descoberto na Fase C

O Port Manager usa Tkinter. Portanto o runtime Python privado deve obrigatoriamente incluir Tcl/Tk.

Instalacao Python requerida:

```text
Include_tcltk=1
```

Validacao minima do runtime:

```powershell
& "$InstallRoot\runtime\python.exe" -c "import serial, win32serviceutil, tkinter; print('Runtime OK')"
```

O instalador legado foi corrigido para reparar automaticamente runtime existente sem `tkinter`.

## Congelamento

A partir deste ponto, a Fase C fica congelada.

Mudancas no Port Manager durante a Fase D devem ser apenas:

- bug real encontrado em regressao;
- integracao necessaria com o instalador;
- persistencia adicional exigida pelo fluxo de Install/Repair/Migration.

Nao reabrir arquitetura visual sem necessidade.

**Status: CONCLUIDA / VALIDADA / CONGELADA.**

---

# Fase D — Installer / Repair / Migration / Uninstall

## Objetivo

Produzir um instalador Windows capaz de levar uma maquina limpa ou antiga ate a arquitetura atual do GADX Vector sem procedimentos manuais.

A Fase D deve fornecer quatro modos logicos:

```text
INSTALL
REPAIR
MIGRATION
UNINSTALL
```

O modo pode ser detectado automaticamente pela instalacao encontrada, mas o comportamento precisa ser claramente separado internamente.

---

## D1 — Descoberta e classificacao da instalacao

Antes de alterar qualquer arquivo, o instalador deve inventariar:

- `C:\Ham\GADX-Vector`;
- runtime Python privado;
- componentes Python obrigatorios;
- com0com e `setupc.exe`;
- pares COM existentes;
- `vector.ini` atual;
- INIs legados;
- arquivos Python legados;
- servicos Windows antigos e atuais;
- estado do `GADXVectorHub`;
- estado do antigo `GADXVectorBridge`.

Classificacao minima:

```text
CLEAN
CURRENT
LEGACY
BROKEN / INCOMPLETE
```

### CLEAN

Nenhuma instalacao relevante encontrada.

### CURRENT

Arquitetura atual encontrada:

```text
app\vector_hub.py
service\vector_service.py
config\vector.ini
service GADXVectorHub
```

### LEGACY

Pode conter combinacoes como:

```text
app\rigctld_bridge.py
app\rigctld_bridge_multi.py
service\vector_bridge_service.py
config\bridge.ini
config\bridge_multi.ini
config\logger.ini
service GADXVectorBridge
```

### BROKEN / INCOMPLETE

Exemplos:

```text
runtime\python.exe existe, mas tkinter nao
servico existe, mas arquivo alvo nao
vector.ini ausente
configuracao antiga existe em local legado
com0com parcialmente instalado
```

---

## D2 — Install limpo

Fluxo esperado:

```text
Verificar Administrador
        ↓
Criar C:\Ham\GADX-Vector
        ↓
Instalar/validar com0com
        ↓
Instalar Python privado + Tcl/Tk
        ↓
Instalar pyserial + pywin32
        ↓
Validar runtime
        ↓
Copiar Runtime / Service / Tools / Config
        ↓
Instalar GADXVectorHub
        ↓
Abrir Port Manager
        ↓
Operador revisa/cria clientes e COMs
        ↓
Aplicar configuracao
        ↓
Marcar reboot pendente
        ↓
Solicitar reinicio do Windows
```

O instalador nao deve criar silenciosamente toda a topologia de clientes sem permitir revisao pelo operador. O Port Manager e a interface oficial para o plano de portas.

---

## D3 — Repair

Repair deve corrigir uma instalacao atual incompleta sem destruir configuracao valida.

Exemplos que precisam ser reparados automaticamente:

- Python privado sem Tcl/Tk;
- `pyserial` ausente;
- `pywin32` ausente;
- `pythonservice.exe` ausente;
- service registration ausente ou quebrada;
- arquivos atuais faltando;
- configuracao movida ou incompleta;
- com0com instalado mas nao localizado;
- Port Manager ausente;
- nomes/arquivos de geracao antiga ainda presentes.

Repair deve ser idempotente: executa-lo novamente numa instalacao saudavel nao deve destruir o ambiente.

---

## D4 — Migration de instalacao antiga

Repair deve detectar automaticamente quando a instalacao e antiga e entrar em caminho de migracao.

### Objetivos da migracao

- preservar COMs existentes quando ainda validas;
- preservar configuracoes operacionais;
- construir o novo `config\vector.ini` a partir dos INIs antigos;
- converter nomes/caminhos de arquivos para a arquitetura atual;
- substituir o servico antigo pelo atual;
- manter backup dos arquivos legados;
- evitar obrigar o operador a reconfigurar Log4OM, N1MM, OmniRig etc. sem necessidade.

### INIs legados

Possiveis fontes:

```text
config\bridge.ini
config\bridge_multi.ini
config\logger.ini
```

O migrador nao deve apenas renomear arquivos. Ele deve ler os valores relevantes e gerar `vector.ini` no formato atual.

Valores potencialmente migraveis:

- CAT interno;
- keying interno;
- portas do lado do aplicativo quando identificaveis;
- baud rates;
- `rig_host`;
- `rig_port`;
- `poll_ms`;
- COM fisica de keying;
- `ptt_line`;
- `cw_line`;
- `allow_write`;
- `allow_ptt`;
- `allow_cw`;
- politica de logging.

### Backup da configuracao antiga

Antes de converter:

```text
config\legacy\
```

Exemplo:

```text
config\legacy\bridge.ini
config\legacy\bridge_multi.ini
config\legacy\logger.ini
```

Nada legado deve ser apagado antes da nova configuracao ser validada.

### Migracao do servico

Se encontrar:

```text
GADXVectorBridge
```

o fluxo deve:

1. parar o servico antigo;
2. remover o registro antigo;
3. instalar `GADXVectorHub`;
4. configurar Delayed Auto Start;
5. configurar recovery;
6. validar o novo servico.

---

## D5 — Runtime Python privado

Runtime obrigatorio:

```text
Python 3.10.x privado
├── pip
├── pyserial
├── pywin32
└── Tcl/Tk / tkinter
```

O instalador deve usar:

```text
Include_tcltk=1
```

Se `runtime\python.exe` ja existir, nao basta considera-lo saudavel. Deve validar imports.

Teste minimo:

```python
import serial
import win32serviceutil
import tkinter
```

Se qualquer import falhar, Repair deve reparar o runtime antes de continuar.

---

## D6 — Integracao com Port Manager

Ao final de Install, Repair ou Migration, o instalador deve abrir automaticamente:

```text
GADX Vector Port Manager
```

Objetivo:

- mostrar o inventario real da maquina;
- carregar configuracao migrada/existente quando houver;
- permitir confirmar ou ajustar clientes;
- permitir criar/remover pares com0com;
- permitir revisar a topologia antes do reboot.

O usuario nao deve precisar conhecer o caminho de `port_manager.py` nem executar Python manualmente.

A distribuicao final deve possuir launcher/atalho apropriado.

---

## D7 — Reboot obrigatorio / pendente

Criacao, remocao ou alteracao de pares com0com pode exigir reinicio do Windows para enumeracao correta das portas.

Portanto o fluxo oficial termina com:

```text
Configuracao aplicada
        ↓
Reboot required
        ↓
[ Reiniciar agora ]  [ Reiniciar depois ]
```

Se o usuario escolher **Reiniciar depois**, a instalacao deve permanecer marcada como pendente.

A conclusao real da instalacao so ocorre apos validacao posterior ao reboot.

---

## D8 — Pos-reboot / Post-install check

No primeiro boot apos Install/Repair/Migration, validar:

```text
[ ] com0com encontrado
[ ] pares COM esperados enumerados
[ ] runtime Python encontrado
[ ] tkinter import OK
[ ] pyserial import OK
[ ] pywin32 import OK
[ ] vector.ini valido
[ ] arquivos atuais presentes
[ ] GADXVectorHub instalado
[ ] GADXVectorHub Running
[ ] nenhuma condicao fail-safe violada
```

Se tudo estiver OK:

```text
installation_state = healthy
pending_reboot = false
```

Se algo falhar, oferecer Repair/diagnostico.

---

## D9 — Uninstall

Uninstall deve remover os componentes do GADX Vector sem destruir recursos compartilhados sem confirmacao.

Deve remover:

- `GADXVectorHub`;
- arquivos do produto;
- atalhos/launchers;
- runtime privado do Vector;
- configuracao somente conforme politica definida.

Decisoes que exigem cuidado:

- remover ou preservar `vector.ini`;
- remover ou preservar logs;
- remover pares com0com criados pelo Vector;
- nao remover com0com inteiro se estiver sendo usado por outros programas;
- oferecer backup da configuracao antes da remocao.

---

## D10 — Estado da instalacao

A Fase D deve manter algum estado local simples para distinguir:

```text
installing
healthy
repair-required
migration-required
pending-reboot
```

O formato ainda pode ser definido, por exemplo:

```text
config\install-state.json
```

Esse estado nao substitui a verificacao real da maquina; serve apenas como apoio ao fluxo.

---

## Criterios de aceite da Fase D

- [ ] instalacao limpa em `C:\Ham\GADX-Vector` sem passos manuais;
- [ ] Python privado provisionado automaticamente;
- [ ] Tcl/Tk/tkinter provisionado automaticamente;
- [ ] pyserial/pywin32 provisionados automaticamente;
- [ ] com0com instalado/detectado automaticamente;
- [ ] GADXVectorHub instalado automaticamente;
- [ ] Port Manager aberto automaticamente no fim;
- [ ] novas COMs configuradas/revisadas pelo Port Manager;
- [ ] reboot solicitado quando necessario;
- [ ] estado `pending-reboot` preservado se reboot for adiado;
- [ ] post-install check executado apos reboot;
- [ ] Repair de runtime incompleto validado;
- [ ] Repair de service quebrado validado;
- [ ] Migration de instalacao `GADXVectorBridge` validada;
- [ ] INIs antigos convertidos para `vector.ini`;
- [ ] arquivos legados preservados em backup;
- [ ] COMs existentes preservadas durante Migration quando possivel;
- [ ] Repair idempotente validado;
- [ ] Uninstall validado sem remover recursos compartilhados indevidamente.

---

# Fase E — Regressao

Depois da Fase D, repetir os testes em cenarios reais:

```text
1. Maquina limpa
2. Instalacao atual saudavel
3. Instalacao atual quebrada
4. Instalacao antiga / GADXVectorBridge
5. Reboot apos criacao de COMs
6. Repair repetido
7. Uninstall + reinstall
```

Preferencia: executar em mais de uma maquina fisica.

---

## Criterios globais ja atendidos

- [x] runtime multi-client executado em bancada;
- [x] Windows Service inicia o Hub e mantem CAT/keying funcionais;
- [x] logs limitados por configuracao;
- [x] PTT via RIGCTLD + CW serial validado;
- [x] dois ou mais clientes CAT simultaneos validados;
- [x] Port Manager inventaria com0com e portas ativas;
- [x] Port Manager carrega configuracao existente;
- [x] Port Manager cruza INI com pares com0com;
- [x] nomes amigaveis de keying carregados e persistidos;
- [x] dropdowns, progresso, tooltips e HELP incorporados;
- [x] Port Manager testado em mais de uma maquina;
- [x] requisito Tcl/Tk identificado e validado em maquina sem tkinter;
- [x] instalador legado corrigido para reparar Tcl/Tk ausente.

---

## Decisoes que ainda exigem teste

- conflitos de escrita CAT simultanea;
- reconexao depois de queda/reinicio do `rigctld`;
- classificacao segura de reservas ComDB orfas;
- comportamento do service recovery quando COMs ainda nao enumeraram no boot;
- split/VFO A/B multi-client;
- eventual PTT por comando CAT no mesmo OR das fontes de keying;
- estrategia final de persistencia completa da tabela do Port Manager em `vector.ini`;
- mecanismo final de post-reboot check;
- politica final de preservacao de configuracao no Uninstall.
