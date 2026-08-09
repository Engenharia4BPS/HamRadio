# GADX Vector — TS-2000 CAT SPIKE

Protótipo isolado para validar a fachada **Kenwood TS-2000** entre softwares de rádio/loggers e um rádio físico controlado pelo GADX Vector.

## Status atual: VALIDADO EM MÚLTIPLAS INSTALAÇÕES

O SPIKE evoluiu de uma bridge single-client para um **hub CAT/keying multi-client**.

Foi validado em bancada e depois repetido em outras instalações com sucesso nos seguintes pontos:

- fachada CAT TS-2000 apresentada aos softwares;
- leitura e alteração de frequência;
- leitura e alteração de modo;
- múltiplos clientes CAT simultâneos, cada um em sua própria COM virtual;
- keying serial configurável por cliente;
- PTT por DTR ou RTS;
- CW por DTR ou RTS;
- caminho CW low-latency, fora do loop de CAT/rigctld;
- PTT consolidado por OR lógico entre clientes;
- CW consolidado por OR lógico entre clientes, com aviso de colisão;
- uso com rádio físico atrás do `rigctld`/Hamlib;
- operação testada com N1MM Logger+, LogHX, MMTTY e outros clientes CAT/keying durante o SPIKE.

A ideia central validada é:

```text
Software A CAT ---- COM virtual ----\
Software B CAT ---- COM virtual -----+--> GADX Vector --> rigctld --> rádio físico
Software C CAT ---- COM virtual ----/

Software A keying -- COM virtual ---\
Software B keying -- COM virtual ----+--> keying hub --> COM física --> PTT/CW do rádio
Software C keying -- COM virtual ---/
```

## Arquivos principais

- `ts2000.py` — emulador/compatibilidade CAT Kenwood TS-2000;
- `rigctld_bridge.py` — geração single-client anterior do SPIKE;
- `rigctld_bridge_multi.py` — geração multi-client atual;
- `bridge.ini` — exemplo legado/single-client;
- `bridge_multi.ini` — exemplo atual multi-client;
- `service/vector_bridge_service.py` — wrapper de serviço Windows usado durante os testes.

## Evolução arquitetural

### Primeira versão

A primeira bridge tinha uma única CAT e uma única entrada de keying:

```text
Logger CAT --> COM virtual --> Vector --> rigctld
Logger CW  --> COM virtual --> Vector --> COM física
```

Ela provou a compatibilidade TS-2000 e o fluxo completo com N1MM.

### Problema encontrado em CW

No primeiro desenho, eventos CW passavam por uma fila e eram processados no mesmo fluxo que CAT/polling do `rigctld`.

Em velocidades de contest isso introduzia jitter suficiente para deformar pontos, traços e espaçamentos.

A correção foi separar o keying em thread dedicado:

```text
ANTES
COM keying --> Queue --> loop CAT/rigctld --> COM física

AGORA
COM keying --> thread low-latency --> COM física
```

O caminho de CW não espera mais consultas de frequência/modo nem chamadas bloqueantes ao `rigctld`.

## Hub CAT multi-client

Cada programa recebe sua própria COM virtual. O Vector abre a outra ponta de cada par.

Exemplo:

```text
Software         lado software    lado Vector
---------------------------------------------
LogHX            COM28      <->   COM101
N1MM             COM26      <->   COM103
Terceiro CAT     COM25      <->   COM105
OmniRig          COM20      <->   COM107
```

No INI:

```ini
[cat]
ports = COM101, COM103, COM105, COM107
baud = 19200
```

Não existe variável `ids`/quantidade. A própria lista define quantos clientes existem.

Cada porta CAT recebe uma instância independente do `TS2000Emulator`, enquanto o acesso ao mesmo `RigctldClient` é serializado por lock.

Conceitualmente:

```text
CAT COM101 --\
CAT COM103 ---+--> workers TS-2000 --> lock --> rigctld --> rádio
CAT COM105 ---+
CAT COM107 --/
```

## Keying multi-client

O formato do INI é:

```ini
[keying]
client1 = COM102,DTR,RTS
client2 = COM104,DTR,NONE
client3 = COM106,RTS,DTR
```

Formato:

```text
clientN = PORTA_VECTOR,PTT_INPUT,CW_INPUT
```

Valores aceitos para PTT/CW de entrada:

```text
DTR
RTS
NONE
```

Exemplo interpretado:

```text
client1 = COM102,DTR,RTS
                 |   |
                 |   +-- CW vem do RTS do software
                 +------ PTT vem do DTR do software

client2 = COM104,DTR,NONE
                 |
                 +------ somente PTT

client3 = COM106,RTS,DTR
                 |   |
                 |   +-- CW vem do DTR
                 +------ PTT vem do RTS
```

No com0com, devido ao cross-wiring dos sinais:

```text
DTR do lado do software --> DSR/DCD no lado Vector
RTS do lado do software --> CTS no lado Vector
```

## Saída física de keying

A saída física é centralizada:

```ini
[radio_keying]
port = COM4
baud = 19200
ptt_line = RTS
cw_line = DTR
```

Isso permite adaptar rádios/interfaces diferentes apenas pelo INI.

Exemplos observados no SPIKE:

```text
IC-746PRO / interface testada:
PTT = RTS
CW  = DTR

Outra instalação testada anteriormente:
PTT = DTR
CW  = RTS
```

A bridge não precisa conhecer o modelo do rádio para decidir isso.

## OR lógico de PTT

Todos os clientes podem solicitar PTT.

O rádio permanece em TX enquanto pelo menos uma fonte estiver ativa:

```text
PTT_RADIO = CAT/PTT1 OR KEYING1 OR KEYING2 OR KEYING3 ...
```

Isso evita que um cliente solte o PTT enquanto outro ainda precisa transmitir.

## OR lógico de CW

A versão multi-client também mantém estado de CW por cliente:

```text
CW_RADIO = CW1 OR CW2 OR CW3 ...
```

Se dois clientes entrarem em CW ao mesmo tempo, o estado físico continua consistente, mas a bridge registra `WARNING` de colisão.

Operacionalmente, duas aplicações não deveriam transmitir Morse simultaneamente.

## Exemplo atual de `bridge_multi.ini`

```ini
[cat]
; COM101 <-> COM28 = LogHX
; COM103 <-> COM26 = N1MM
; COM105 <-> COM25 = terceiro cliente CAT
; COM107 <-> COM20 = OmniRig
ports = COM101, COM103, COM105, COM107
baud = 19200

[keying]
; COM102 <-> COM30 = Logger - PTT via DTR / CW via RTS
; COM104 <-> COM27 = MMTTY - PTT via DTR / sem CW
; COM106 <-> COM29 = Nexus - PTT via RTS / CW via DTR
client1 = COM102,DTR,RTS
client2 = COM104,DTR,NONE
client3 = COM106,RTS,DTR

[radio_keying]
port = COM4
baud = 19200
ptt_line = RTS
cw_line = DTR

[rig]
host = 127.0.0.1
port = 4532
poll_ms = 250

[bridge]
allow_write = true
allow_ptt = true
allow_cw = true
log_level = INFO
log_max_mb = 5
log_backups = 5
```

Use `;` ou `#` no início da linha para comentários em arquivos INI.

## com0com

Os testes foram feitos com pares de portas virtuais com0com.

Exemplos de comandos no `setupc.exe`/Setup Command Prompt:

```text
install PortName=COM28 PortName=COM101
install PortName=COM30 PortName=COM102
install PortName=COM26 PortName=COM103
install PortName=COM27 PortName=COM104
install PortName=COM25 PortName=COM105
install PortName=COM29 PortName=COM106
```

Para conferir:

```text
list
```

O conceito adotado é manter, quando possível:

```text
COM baixa (< 30)  = lado do software
COM 100+          = lado interno do Vector
```

Isso ajuda programas antigos que não lidam bem com números altos de COM.

## MMTTY

No SPIKE, o MMTTY pode receber uma CAT dedicada e uma porta dedicada de PTT.

Exemplo:

```text
MMTTY CAT: COM26 <-> COM103
MMTTY PTT: COM27 <-> COM104
```

No `bridge_multi.ini`:

```ini
[cat]
ports = COM101, COM103

[keying]
client1 = COM102,DTR,RTS
client2 = COM104,DTR,NONE
```

A engine do MMTTY possui também mecanismos próprios de integração via mensagens Windows. Isso pode ser estudado futuramente como adapter nativo, mas não é necessário para validar a arquitetura genérica de COMs virtuais.

## rigctld / Hamlib

O rádio físico continua atrás do Hamlib:

```ini
[rig]
host = 127.0.0.1
port = 4532
poll_ms = 250
```

A bridge multi-client compartilha um único cliente `rigctld`, protegido por lock para impedir que múltiplos CAT workers misturem comandos/respostas no mesmo socket.

## Executar a versão multi-client

Exemplo em PowerShell:

```powershell
python rigctld_bridge_multi.py `
  --config .\bridge_multi.ini
```

Na instalação de teste do Vector:

```powershell
& "C:\Ham\GADX-Vector\runtime\python.exe" `
  "C:\Ham\GADX-Vector\app\rigctld_bridge_multi.py" `
  --config "C:\Ham\GADX-Vector\config\bridge_multi.ini"
```

Saída esperada:

```text
CAT ports: COM101,COM103,... @ 19200
Keying clients: client1:COM102, client2:COM104, ...
Physical keying: COM4 @ 19200 PTT=RTS CW=DTR
Connected to rigctld
CAT client ready: COM101 @ 19200
CAT client ready: COM103 @ 19200
Keying client1 ready: COM102 PTT=DTR CW=RTS
Bridge ready
```

## Log level e CW

Para diagnóstico:

```ini
log_level = DEBUG
```

Para operação/teste de CW em velocidade de contest, prefira:

```ini
log_level = INFO
```

Evitar logging excessivo no caminho de keying reduz I/O concorrente e ajuda a manter a temporização limpa.

## Fail-safe

Na abertura da porta física:

```text
RTS = OFF
DTR = OFF
```

Na saída da bridge:

```text
RTS = OFF
DTR = OFF
PTT rigctld = OFF (best effort)
```

O objetivo é não deixar rádio/interface presos em TX ou CW após falha do processo.

## Serviço Windows

Durante o SPIKE foi criado `service/vector_bridge_service.py` para manter a bridge rodando como serviço Windows e fazer rotação de logs.

A instalação de desenvolvimento adotou:

```text
C:\Ham\GADX-Vector\
```

com runtime Python privado.

O wrapper atual ainda está ligado ao layout `bridge.ini`/`rigctld_bridge.py`. Ao promover a versão multi-client para a bridge oficial, o próximo ajuste deve fazer o serviço entender diretamente as seções:

```text
[cat]
[keying]
[radio_keying]
[rig]
[bridge]
```

especialmente no `force_safe_state`.

## Logs

A configuração de serviço usa limites para evitar crescimento indefinido:

```ini
log_max_mb = 5
log_backups = 5
```

## Compatibilidade TS-2000

`ts2000.py` implementa o subconjunto CAT necessário ao SPIKE e continua sendo expandido conforme tráfego real é observado.

Comandos trabalhados incluem:

- `ID`
- `FA`
- `FB`
- `MD`
- `FR`
- `FT`
- `TX`
- `RX`
- `IF`
- `AI`
- `AG`

O parser CAT permanece desacoplado de COM, Windows e Hamlib.

## Resultado atual do SPIKE

As hipóteses abaixo estão validadas em bancada:

1. é possível apresentar uma fachada TS-2000 a softwares distintos enquanto o rádio físico é controlado via Hamlib/rigctld;
2. múltiplos softwares podem receber CAT simultaneamente quando cada um possui sua própria COM virtual;
3. PTT e CW podem ser recebidos por clientes diferentes e mapeados por INI;
4. CW precisa de caminho dedicado low-latency, separado do polling CAT/rigctld;
5. a configuração pode ser genérica, sem regras específicas para N1MM/MMTTY/LogHX no código;
6. a arquitetura começa naturalmente a se comportar como um **CAT + Keying Hub**, que é uma boa base para o futuro Vector Client.

## Próximos passos

- promover `rigctld_bridge_multi.py` para bridge principal depois de mais regressão;
- atualizar `vector_bridge_service.py` para entender nativamente o INI multi-client;
- transformar configurações/pairs com0com em setup automatizado;
- adicionar testes de regressão multi-CAT;
- testar recuperação após perda de rigctld;
- medir jitter de CW sistematicamente;
- testar split/VFO A/VFO B com múltiplos clientes;
- avaliar adapter nativo MMTTY via Windows messages;
- evoluir o SPIKE para os adapters definitivos do GADX Vector.
