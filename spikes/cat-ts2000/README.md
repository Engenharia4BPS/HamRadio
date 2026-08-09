# GADX Vector — TS-2000 CAT/Keying SPIKE

Protótipo para validar uma fachada **Kenwood TS-2000** apresentada a softwares de radio, enquanto o radio fisico permanece controlado pelo GADX Vector via Hamlib/`rigctld`.

## Status

**Arquitetura multi-client validada em bancada e repetida em mais de uma instalacao.**

O SPIKE comecou single-client e evoluiu para um **hub CAT + keying multi-client**. Os arquivos antigos permanecem no repositorio como historico/regressao; eles nao devem ser confundidos com a arquitetura-alvo atual.

## O que foi efetivamente validado

- fachada CAT TS-2000 para softwares que esperam um radio Kenwood compativel;
- leitura e alteracao de frequencia;
- leitura e alteracao de modo;
- varios clientes CAT simultaneos, cada um com sua propria COM virtual;
- uma instancia independente de `TS2000Emulator` por cliente CAT;
- um unico acesso compartilhado ao `rigctld`, serializado por lock;
- entradas de keying independentes e configuraveis por cliente;
- PTT de entrada por DTR ou RTS;
- CW de entrada por DTR ou RTS;
- saida fisica de PTT/CW configuravel por INI;
- caminho de CW dedicado/low-latency, sem depender do polling CAT/rigctld;
- OR logico entre fontes de PTT;
- OR logico entre fontes de CW, com `WARNING` quando ha mais de uma fonte CW ativa;
- runtime Python privado e servico Windows na primeira geracao do instalador;
- rotação limitada do log do wrapper de servico;
- uso real durante o SPIKE com N1MM Logger+, LogHX, MMTTY e outros consumidores CAT/keying, incluindo cenarios com OmniRig/Nexus.

## Arquitetura atual

```text
                       +---------------- TS2000Emulator #1 <-- COM CAT #1
                       |
software CAT #1 <----> | 
software CAT #2 <----> +-- GADX Vector -- lock -- rigctld -- radio fisico
software CAT #3 <----> | 
                       +---------------- TS2000Emulator #N <-- COM CAT #N

software keying #1 --> worker dedicado --\
software keying #2 --> worker dedicado ---+--> estados logicos --> COM fisica --> PTT/CW
software keying #N --> worker dedicado --/
```

O CAT virtual e o keying serial sao **interfaces distintas**. Um software pode precisar somente CAT, somente PTT, ou CAT + keying em portas diferentes.

## Arquivos

- `ts2000.py` — emulador/subconjunto CAT Kenwood TS-2000;
- `rigctld_bridge.py` — bridge single-client historica;
- `rigctld_bridge_multi.py` — bridge multi-client atual do SPIKE;
- `bridge.ini` — configuracao historica single-client;
- `bridge_multi.ini` — configuracao de referencia para a multi-client;
- `service/vector_bridge_service.py` — wrapper de servico Windows da geracao single-client;
- `installer/production/` — primeira geracao do instalador; validou mecanica de instalacao, mas ainda nao foi migrada para o INI multi-client.

## CAT multi-client

Cada aplicacao recebe a sua propria ponta de um par com0com. A bridge abre a ponta interna correspondente.

Exemplo de **bancada atual** (nao e a numeracao-alvo do instalador):

```text
Aplicacao       lado aplicacao      lado Vector
-----------------------------------------------
LogHX           COM28        <->    COM101
N1MM            COM26        <->    COM103
Terceiro CAT    COM25        <->    COM105
OmniRig         COM20        <->    COM107
```

```ini
[cat]
ports = COM101, COM103, COM105, COM107
baud = 19200
```

A lista `ports` e a fonte de verdade; nao existe um contador `ids` separado.

Cada CAT worker possui seu proprio estado/protocolo TS-2000. Todos compartilham o mesmo `RigctldClient`; o socket e protegido por lock para que comandos e respostas nao sejam misturados entre threads.

### Consistencia de estado

O estado fisico (frequencia/modo) e consultado periodicamente do `rigctld` e publicado aos emuladores. Assim, uma alteracao feita por um cliente ou diretamente no radio passa a aparecer aos demais no ciclo de atualizacao.

O SPIKE ainda nao deve ser descrito como um barramento transacional perfeito entre varios writers: conflitos simultaneos de escrita, split/VFO A/B e politicas de arbitragem ainda merecem testes especificos.

## Keying multi-client

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

Entradas aceitas:

```text
DTR | RTS | NONE
```

Exemplo:

```text
client1 = COM102,DTR,RTS   -> PTT pelo DTR; CW pelo RTS
client2 = COM104,DTR,NONE  -> PTT pelo DTR; sem CW
client3 = COM106,RTS,DTR   -> PTT pelo RTS; CW pelo DTR
```

### Como DTR/RTS chegam pela COM virtual

No ambiente com0com validado no SPIKE, a outra ponta observa os sinais desta forma:

```text
DTR do software -> DSR/DCD na ponta Vector
RTS do software -> CTS na ponta Vector
```

Por isso `read_input_line()` traduz a semantica configurada (`DTR`/`RTS`) para os sinais observados na ponta interna.

## Saida fisica de keying

A saida e configuracao da **interface/radio daquela instalacao**, nao uma propriedade do protocolo TS-2000:

```ini
[radio_keying]
port = COM4
baud = 19200
ptt_line = RTS
cw_line = DTR
```

Em outra bancada a combinacao pode ser invertida. A bridge nao deve codificar `Icom = RTS/DTR`, `Kenwood = ...` etc.; o mapeamento pertence ao INI.

O `baud` e necessario para abrir a porta serial, mas PTT/CW aqui sao feitos pelas linhas de controle RTS/DTR, nao por bytes enviados nessa velocidade.

## PTT: OR logico

Fontes independentes de PTT sao consolidadas:

```text
PTT_RADIO = PTT1 OR PTT2 OR ... OR PTTN
```

Assim, a desativacao de uma fonte nao derruba o PTT enquanto outra ainda estiver ativa.

### CAT PTT x keying PTT

Na **multi-bridge atual**, o caminho fisico de PTT implementado e o dos clientes `[keying]`. O `TS2000Emulator` ainda reconhece comandos CAT como `TX`/`RX`, mas a multi-bridge atual nao deve ser documentada como se `TX`/`RX` CAT ja participassem do mesmo OR fisico de PTT. Se quisermos esse comportamento, ele deve ser implementado/testado explicitamente.

Essa distincao corrige uma simplificacao feita em documentacao anterior.

## CW: OR logico + low latency

O primeiro desenho encaminhava eventos CW por um fluxo que concorria com CAT/polling. Em transmissao real isso produziu deformacao perceptivel do Morse.

A solucao validada foi manter workers dedicados de keying e retirar `rigctld` do caminho critico:

```text
ANTES
keying -> fila/loop compartilhado -> CAT/rigctld -> saida

ATUAL
keying -> worker dedicado -> estado CW -> COM fisica
```

Com varios clientes:

```text
CW_RADIO = CW1 OR CW2 OR ... OR CWN
```

Se mais de uma fonte CW ficar ativa simultaneamente, o estado fisico continua coerente pelo OR, mas a bridge registra colisao. Isso e protecao de estado, nao um mecanismo de mistura de duas transmissoes Morse.

## Politica de portas COM

### O que usamos no laboratorio

Durante o SPIKE foram usados numeros como COM20, COM25..COM30 no lado dos aplicativos e COM101+ no lado interno. Esses numeros sao historicos de bancada.

### Convencao para instalacoes futuras

Softwares antigos de radio frequentemente trabalham melhor com numeros baixos de COM. A politica planejada para o instalador automatico passa a ser:

```text
lado dos aplicativos: iniciar tentativa em COM15 e avancar
lado interno Vector:  iniciar em COM101 e avancar
```

Exemplo:

```text
COM15 <-> COM101   CAT #1
COM16 <-> COM102   Keying #1
COM17 <-> COM103   CAT #2
COM18 <-> COM104   Keying #2
COM19 <-> COM105   CAT #3
COM20 <-> COM106   Keying #3
```

**COM15 nao e uma reserva fixa.** O instalador deve consultar as portas ocupadas (ComDB/com0com), tentar COM15 primeiro e avancar sem sobrescrever recursos existentes.

O lado COM101+ e uma convencao interna do Vector e facilita diagnostico/suporte.

## Exemplo `bridge_multi.ini`

```ini
[cat]
; numeros abaixo sao exemplo de bancada
ports = COM101, COM103, COM105, COM107
baud = 19200

[keying]
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

Comentarios INI podem comecar com `;` ou `#`.

## com0com

Criacao manual de um par:

```text
install PortName=COM15 PortName=COM101
```

Consulta:

```text
list
```

Para o SPIKE, cada aplicacao tem uma COM exclusiva. O com0com cria um par ponto-a-ponto; ele nao transforma uma unica COM em uma porta compartilhada por varios processos. O fan-out e feito pelo Vector criando varias fachadas COM, uma por cliente.

## MMTTY

O desenho generico testado permite separar:

```text
MMTTY CAT    -> uma COM CAT dedicada
MMTTY PTT    -> uma COM keying dedicada (se necessario)
```

A engine MMTTY tambem oferece integracao por mensagens Windows. Isso e uma possibilidade futura de adapter nativo; nao e requisito para a arquitetura generica atual e ainda nao deve ser tratado como componente validado do Vector.

## rigctld / Hamlib

```ini
[rig]
host = 127.0.0.1
port = 4532
poll_ms = 250
```

O radio fisico e configurado no Hamlib/rigctld. A fachada TS-2000 existe do lado das aplicacoes; ela nao exige que o radio fisico seja um TS-2000.

## Executar a multi-bridge

```powershell
& "C:\Ham\GADX-Vector\runtime\python.exe" `
  "C:\Ham\GADX-Vector\app\rigctld_bridge_multi.py" `
  --config "C:\Ham\GADX-Vector\config\bridge_multi.ini"
```

Saida esperada:

```text
CAT ports: COM101,COM103,... @ 19200
Keying clients: client1:COM102, client2:COM104, ...
Physical keying: COM4 @ 19200 PTT=RTS CW=DTR
Connected to rigctld
CAT client ready: COM101 @ 19200
Keying client1 ready: COM102 PTT=DTR CW=RTS
Bridge ready
```

## Logging

Para diagnostico:

```ini
log_level = DEBUG
```

Para operacao e especialmente testes de CW:

```ini
log_level = INFO
```

`log_max_mb` e `log_backups` sao consumidos pelo **wrapper de servico**. A `rigctld_bridge_multi.py` executada diretamente apenas configura seu nivel de logging; ela nao implementa sozinha a rotacao de arquivo.

## Fail-safe

A bridge multi-client coloca RTS/DTR da porta fisica em OFF ao abri-la e novamente no encerramento normal/falha tratada. No `finally`, tambem tenta `set_ptt(False)` via rigctld como best effort.

O wrapper de servico adiciona uma segunda camada de `force_safe_state`, mas a versao atual desse wrapper ainda entende o formato single-client do INI. Portanto, o fail-safe do **servico multi-client** ainda precisa ser migrado/testado antes de ser chamado de concluido.

## Servico Windows e instalador

A primeira geracao validou:

- instalacao em `C:\Ham\GADX-Vector`;
- Python 3.10 privado;
- `pyserial` + `pywin32`;
- com0com assinado;
- `GADXVectorBridge` como Automatic (Delayed Start);
- recovery/restart on failure;
- log limitado por rotacao;
- reparo/reinstalacao do servico.

Entretanto, `service/vector_bridge_service.py` e `installer/production/install-vector.ps1` ainda pertencem a geracao single-client. O instalador v0.1 procura portas do software em COM10..COM30 e gera `[bridge]` antigo. A proxima geracao deve usar a politica COM15+ / COM101+ e gerar o INI multi-client.

## Compatibilidade TS-2000

`ts2000.py` implementa apenas o subconjunto necessario observado/necessario durante o SPIKE. Nao e objetivo afirmar compatibilidade completa com todo o protocolo TS-2000.

Comandos trabalhados incluem, entre outros:

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

O parser permanece desacoplado de Windows, COM virtual e Hamlib.

## Conceitos consolidados

1. **Uma COM por cliente.** Nao tentamos fazer varios programas abrirem a mesma COM.
2. **TS-2000 e fachada, nao radio fisico.** O equipamento real continua abstraido pelo Hamlib.
3. **CAT e keying sao canais diferentes.** Nao devemos presumir que todo software usa ambos nem que usa as mesmas linhas.
4. **Mapeamento RTS/DTR pertence a configuracao.** Nao ao modelo do radio no codigo.
5. **CW e caminho de tempo critico.** Nao deve depender de polling ou chamadas bloqueantes do rigctld.
6. **PTT/CW multi-client precisam estado por fonte.** Um cliente nao pode desligar uma linha ainda requerida por outro.
7. **COM15 e preferencia inicial, nao garantia.** A deteccao de portas livres vem antes da criacao.
8. **COM101+ e namespace interno convencional.** Facilita diagnostico e evita expor portas altas a software legado.
9. **SPIKE validado nao significa produto final.** Service wrapper, instalador multi-client, arbitragem de writers, split/VFO e recuperacao de falhas ainda precisam regressao propria.

## Pontos ainda abertos

- promover `rigctld_bridge_multi.py` a bridge oficial;
- migrar `vector_bridge_service.py` para o INI multi-client;
- migrar o instalador para N pares e politica COM15+ / COM101+;
- decidir UX para adicionar/remover clientes apos a instalacao;
- testar conflitos de escrita CAT simultanea;
- testar split, VFO A/B e recursos CAT adicionais;
- testar/reprojetar reconexao robusta apos perda/reinicio do `rigctld`;
- medir jitter de CW de forma sistematica;
- testar stop/restart/crash do servico multi-client e seu fail-safe;
- avaliar adapter nativo MMTTY somente depois da base generica estar consolidada.
