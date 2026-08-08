# GADX Vector — TS-2000 CAT SPIKE

Protótipo isolado para validar a fachada **Kenwood TS-2000** entre loggers de contest e um rádio físico controlado pelo GADX Vector.

## Status: VALIDADO COM N1MM LOGGER+

O SPIKE foi validado em bancada com **N1MM Logger+** e funcionou 100% no fluxo testado:

- N1MM reconhece a interface como TS-2000;
- leitura e alteração de frequência via CAT;
- leitura e alteração de modo;
- PTT encaminhado ao rádio físico;
- CW keying em tempo real encaminhado ao rádio físico;
- mensagem CW gerada pelo N1MM transmitida corretamente pelo rádio.

O teste fecha a cadeia completa:

```text
N1MM Logger+
   |
   | CAT TS-2000 / COM virtual
   v
GADX Vector - rigctld_bridge.py
   |
   +---------------- CAT / Hamlib ----------------> rigctld -> rádio físico
   |
   +---------------- PTT --------------------------> rádio físico
   |
   +---------------- CW keying RTS ----------------> porta USB(B) do rádio
```

Este SPIKE deixou de ser apenas uma prova do parser TS-2000: ele demonstrou que podemos usar o TS-2000 como **fachada CAT para o logger**, mantendo o rádio físico atrás da camada Vector/Hamlib.

## Configuração validada em bancada

Configuração utilizada no teste bem-sucedido:

```text
N1MM CAT:           COM9  / TS-2000 / 19200 baud
N1MM CW/PTT:        COM31

Vector CAT:         COM18
Vector keying input: COM32

Rádio físico CAT:   COM20 -> rigctld
Rádio físico CW:    COM22 -> RTS
```

Os pares COM virtuais ficam conceitualmente assim:

```text
N1MM COM9  <------ virtual null modem ------> COM18 Vector CAT
N1MM COM31 <------ virtual null modem ------> COM32 Vector keying
```

## Fluxo CAT

O N1MM conversa exclusivamente com uma fachada TS-2000.

```text
N1MM
  |
  | Kenwood TS-2000 CAT
  v
COM9 <-> COM18
          |
          v
  rigctld_bridge.py
          |
          | Hamlib rigctld
          v
       rádio real
```

Assim, o logger não precisa conhecer o modelo real do equipamento conectado atrás do Vector.

## Fluxo CW

O CW não é decodificado nem reconstruído pela bridge.

A temporização produzida pelo N1MM é encaminhada em tempo real através das linhas seriais:

```text
N1MM COM31 RTS
      |
      v
COM32 CTS
      |
      | detecção de KEY DOWN / KEY UP
      v
rigctld_bridge.py
      |
      v
COM22 RTS
      |
      v
CW KEY do rádio físico
```

Exemplo conceitual:

```text
N1MM:       RTS ON  ---------------- RTS OFF
                       47 ms

Vector:     CTS ON  -> evento CW -> CTS OFF

Rádio:      RTS ON  ---------------- RTS OFF
            KEY DOWN                  KEY UP
```

A bridge preserva a temporização enviada pelo logger em vez de tentar interpretar caracteres Morse.

## Fluxo PTT

PTT pode chegar tanto pelo CAT quanto pela entrada de keying.

A bridge consolida essas solicitações antes de alterar o PTT físico:

```text
CAT PTT -------+
                +----> estado PTT desejado ----> rigctld ----> rádio
Keying PTT ----+
```

O envio físico de PTT exige explicitamente:

```text
--allow-write --allow-ptt
```

## Fail-safe

CW e PTT possuem desligamento de segurança independente.

Na abertura da porta física de keying:

```text
RTS = OFF
DTR = OFF
```

Ao encerrar a bridge, inclusive após erro:

```text
CW KEY UP -> RTS OFF
PTT OFF   -> rigctld set_ptt 0
```

Isso reduz o risco de deixar o rádio preso em TX ou com a chave CW acionada após uma interrupção do processo.

## Requisitos

- Python 3.9+;
- `pyserial`;
- Hamlib / `rigctld` para acesso ao rádio físico;
- pares de portas seriais virtuais no Windows;
- porta serial física configurada para CW por RTS quando o keying direto for utilizado.

Instalação:

```powershell
cd spikes\cat-ts2000
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Executar somente o emulador

Para testes sem rádio físico:

```powershell
python emulator.py --port COM18 --baud 19200 --log-level DEBUG
```

## Executar a bridge validada

Com a configuração utilizada no teste:

```powershell
python rigctld_bridge.py `
  --port COM18 `
  --keying-port COM32 `
  --radio-keying-port COM22 `
  --radio-keying-baud 9600 `
  --rig-host 127.0.0.1 `
  --rig-port 4532 `
  --allow-write `
  --allow-ptt `
  --allow-cw `
  --log-level DEBUG
```

Em CMD, use uma única linha:

```cmd
python rigctld_bridge.py --port COM18 --keying-port COM32 --radio-keying-port COM22 --radio-keying-baud 9600 --rig-host 127.0.0.1 --rig-port 4532 --allow-write --allow-ptt --allow-cw --log-level DEBUG
```

> `--allow-cw` habilita keying real no rádio. Use potência/carga/antena adequadas durante testes.

## N1MM Logger+

Configuração CAT validada:

```text
Radio:     TS-2000
Port:      COM9
Baud:      19200
Data bits: 8
Parity:    None
Stop bits: 1
```

A porta de CW/PTT do N1MM foi configurada na outra extremidade do segundo par virtual (`COM31` no teste).

## Comandos TS-2000

O emulador implementa a base CAT necessária ao SPIKE e pode ser ampliado conforme novos loggers e recursos forem testados.

Entre os comandos trabalhados pelo protótipo estão:

- `ID`
- `FA`
- `FB`
- `MD`
- `FR`
- `FT`
- `TX`
- `RX`

Comandos desconhecidos são registrados para permitir ampliar a compatibilidade com base em tráfego real.

## Rodar testes unitários

A partir de `spikes/cat-ts2000`:

```powershell
python -m unittest discover -s tests -v
```

## Arquitetura atual do SPIKE

```text
                    +------------------+
                    |   N1MM Logger+   |
                    +---------+--------+
                              |
                    TS-2000 CAT + keying
                              |
                 +------------v-------------+
                 |     GADX Vector SPIKE     |
                 |                           |
                 | ts2000.py                 |
                 | rigctld_bridge.py         |
                 +------+---------------+----+
                        |               |
                  Hamlib CAT/PTT     CW RTS
                        |               |
                 +------v---------------v----+
                 |       rádio físico        |
                 +---------------------------+
```

`ts2000.py` continua desacoplado de COM, Windows, N1MM e Hamlib. O parser CAT pode portanto evoluir para um Adapter do Vector Client sem carregar dependências do transporte serial.

`rigctld_bridge.py` faz a integração experimental entre essa fachada CAT, Hamlib e o caminho de keying em tempo real.

## Resultado do SPIKE

**Hipótese validada:** é tecnicamente viável apresentar ao N1MM uma interface CAT TS-2000 virtual e traduzir/encaminhar o controle para um rádio físico diferente através do Vector.

Também foi validado que o caminho de CW pode permanecer fora do protocolo CAT, preservando os pulsos KEY DOWN/KEY UP produzidos pelo próprio logger.

Mensagem utilizada no teste final:

```text
QRL? DE PY5XT
```

O rádio físico transmitiu corretamente a mensagem comandada pelo N1MM.

## Próximos passos sugeridos

Agora que o caminho N1MM -> Vector -> rádio está comprovado, os próximos incrementos naturais são:

- transformar as capturas reais do N1MM em testes de regressão;
- testar split/VFO A/VFO B de forma sistemática;
- testar troca rápida de banda e modo;
- validar recuperação após desconexão/reconexão do rigctld;
- medir jitter/latência do caminho CW;
- validar DXLog usando a mesma fachada TS-2000;
- evoluir o SPIKE para os adapters/interfaces definitivos do Vector Client.
