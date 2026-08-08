# GADX Vector — TS-2000 CAT SPIKE

Protótipo isolado para validar **N1MM Logger+ / DXLog → COM virtual → emulação CAT TS-2000**.

Este código **não transmite RF**, não acessa Hamlib e não utiliza rádio físico. `TX` e `RX` alteram apenas um booleano em memória.

## Estado atual

Primeira iteração do SPIKE.

Comandos implementados:

- `ID`
- `FA`
- `FB`
- `MD`
- `FR`
- `FT`
- `TX`
- `RX`

Comandos desconhecidos são registrados como `UNSUPPORTED` para descobrirmos o conjunto real utilizado pelos loggers.

`IF` ainda não está implementado propositalmente. Ele será incluído após validarmos o formato exato e/ou capturarmos a necessidade concreta durante os primeiros testes.

## Requisitos

- Python 3.9+ recomendado para o SPIKE;
- `pyserial`;
- um par de portas seriais virtuais no Windows.

Instalação:

```powershell
cd spikes\cat-ts2000
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Porta COM virtual

No Windows, crie um par de portas COM virtuais com a ferramenta de sua preferência.

Exemplo conceitual:

```text
COM10 <------ virtual null modem ------> COM11
  |                                      |
  |                                      +-- emulator.py
  |
  +-- N1MM ou DXLog
```

Nunca configure N1MM/DXLog e o emulador na mesma extremidade do par.

## Executar

Exemplo, considerando o emulador em `COM11`:

```powershell
python emulator.py --port COM11 --baud 19200 --log-level DEBUG
```

Estado inicial:

```text
VFO A: 14.074 MHz
VFO B: 7.074 MHz
Mode:  USB
RX:    VFO A
TX:    VFO A
PTT:   OFF
```

## N1MM Logger+

Configuração inicial sugerida:

```text
Radio:     TS-2000
Port:      COM10
Baud:      19200
Data bits: 8
Parity:    None
Stop bits: 1
```

Ative DEBUG no emulador para observar exatamente o que o N1MM envia.

## DXLog

Configuração inicial sugerida:

```text
Radio:     TS-2000
Port:      COM10
Baud:      19200
Data bits: 8
Parity:    None
Stop bits: 1
Polling:   300 ms
```

## Rodar testes unitários

A partir de `spikes/cat-ts2000`:

```powershell
python -m unittest discover -s tests -v
```

Os testes não precisam de `pyserial` nem de porta COM.

## O que observar no primeiro teste

Copie o log DEBUG completo de uma conexão do N1MM e do DXLog.

Queremos responder:

1. Qual é o primeiro comando enviado?
2. O logger consulta `ID`?
3. O logger exige `IF` para considerar o rádio online?
4. Quais comandos aparecem durante polling normal?
5. Quais comandos aparecem ao alterar frequência?
6. Quais aparecem ao alterar modo?
7. Como split é manipulado?
8. Como PTT é solicitado?

A próxima implementação será guiada por essas capturas.

## Arquitetura do protótipo

```text
emulator.py
    |
    | pyserial
    v
ts2000.py
    |
    v
RadioState
```

`ts2000.py` não conhece COM, Windows ou N1MM. Isso é intencional: o parser CAT poderá futuramente virar um Adapter do Vector Client sem carregar dependências de transporte serial.

## Próximo incremento

Após a primeira captura real:

- implementar `IF` corretamente;
- implementar comandos adicionais realmente utilizados;
- criar fixtures de tráfego N1MM e DXLog;
- transformar capturas reais em testes de regressão;
- decidir formalmente se TS-2000 será a fachada CAT da v1.
