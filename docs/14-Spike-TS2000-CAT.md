# GADX Vector
# 14 - SPIKE-002 — Emulação CAT TS-2000

Versão: 1.0 (Draft)
Status: Em execução

---

# Objetivo

Validar tecnicamente a camada de compatibilidade CAT do **Vector Client**, provando que **N1MM Logger+** e **DXLog** conseguem controlar um rádio virtual local apresentado como **Kenwood TS-2000** através de uma porta COM virtual.

Este SPIKE não utiliza Vector Gateway, Hamlib, `rigctld` ou rádio físico. O objetivo é isolar e eliminar o risco técnico da borda local:

```text
N1MM / DXLog
      |
      v
COM Virtual
      |
      v
TS-2000 CAT Emulator
      |
      v
Estado simulado
```

Quando esta camada estiver validada, ela será conectada ao Vector Client e o estado simulado será substituído por comandos e eventos do Vector Protocol.

---

# Hipótese

O **Kenwood TS-2000** é um bom candidato para a fachada CAT inicial do GADX Vector porque:

- possui suporte específico no N1MM Logger+;
- possui suporte específico no DXLog;
- utiliza comandos ASCII curtos e terminados por `;`;
- suporta leitura e escrita de frequência, modo, VFO, split e PTT;
- permite implementação incremental do subconjunto realmente utilizado pelos loggers.

A escolha ainda é experimental. O TS-2000 somente será adotado como fachada oficial após os testes deste SPIKE.

---

# Referências verificadas

## Kenwood

A documentação oficial do TS-2000 define:

- comandos de duas letras;
- parâmetros de tamanho fixo por comando;
- `;` como terminador;
- `FA;` como leitura do VFO A;
- `FA00007000000;` como exemplo de ajuste do VFO A para 7 MHz;
- erro de formato representado por `?;`;
- suporte a comandos como `FA`, `FB`, `FR`, `FT`, `ID`, `IF`, `MD`, `RX` e `TX`.

Referência oficial:

https://www.kenwood.com/jp/products/amateur/pdf/ts2000_pc_command_j.pdf

## N1MM Logger+

O N1MM possui seleção específica **TS-2000** e recomenda velocidade acima de 9600 baud, 8 data bits, sem paridade e 1 stop bit para velocidades superiores a 4800 baud.

Referência:

https://n1mmwp.hamdocs.com/manual-supported/supported-radios/

## DXLog

O DXLog possui suporte específico ao TS-2000 e recomenda:

- 19200 bps;
- 8 bits;
- sem paridade;
- 1 stop bit;
- polling de aproximadamente 300 ms.

Referência:

https://www.dxlog.net/docs/index.php?title=Radios

---

# Baseline de Laboratório

Configuração inicial sugerida:

```text
Radio model: Kenwood TS-2000
Speed:       19200 baud
Data bits:   8
Parity:      None
Stop bits:   1
Polling:     300 ms (DXLog)
```

O controle de fluxo será validado empiricamente durante o SPIKE, pois aplicações e drivers de COM virtual podem tratar RTS/CTS de maneiras diferentes.

---

# Estratégia de Implementação

O emulador deve possuir duas camadas independentes:

```text
Serial Transport
      |
      v
TS2000 Parser / Emulator
      |
      v
RadioState
```

Essa separação permite testar o protocolo CAT sem precisar de uma porta COM real.

## RadioState inicial

O estado mínimo simulado inclui:

- VFO A frequency;
- VFO B frequency;
- RX VFO;
- TX VFO;
- mode;
- PTT;
- split derivado de RX/TX VFO.

---

# Subconjunto CAT inicial

## Implementado na primeira iteração

| Comando | Função |
|---|---|
| `ID` | Identificação do rádio |
| `FA` | Ler/alterar frequência do VFO A |
| `FB` | Ler/alterar frequência do VFO B |
| `MD` | Ler/alterar modo |
| `FR` | Ler/alterar VFO de recepção |
| `FT` | Ler/alterar VFO de transmissão |
| `TX` | Entrar em transmissão |
| `RX` | Retornar à recepção |

## Próximos comandos candidatos

- `IF` — informação agregada do estado;
- `AI` — Auto Information;
- `PS` — Power status;
- comandos adicionais observados nos logs de N1MM/DXLog.

A implementação seguirá uma regra importante:

> **Implementar somente comandos necessários e comprovadamente utilizados, mantendo logging completo dos comandos desconhecidos.**

Isso evita recriar desnecessariamente todo o firmware CAT do TS-2000.

---

# Logging de Descoberta

Todo comando recebido deve ser registrado em modo DEBUG.

Comandos ainda não implementados devem ser claramente marcados como `UNSUPPORTED`.

O objetivo inicial é descobrir empiricamente quais comandos N1MM e DXLog utilizam durante:

1. conexão;
2. polling normal;
3. mudança de frequência;
4. mudança de banda;
5. mudança de modo;
6. split;
7. PTT;
8. desconexão/reconexão.

Essa captura formará a **matriz real de compatibilidade CAT** do Vector Client.

---

# Critérios de Sucesso

## Etapa A — Parser

- comandos podem chegar fragmentados em múltiplas leituras serial;
- múltiplos comandos podem chegar em uma única leitura;
- o parser separa corretamente mensagens pelo terminador `;`;
- comandos inválidos não derrubam o processo.

## Etapa B — N1MM

1. Criar par de portas COM virtuais.
2. Emulador abre uma extremidade.
3. N1MM abre a outra extremidade.
4. Selecionar rádio `TS-2000`.
5. N1MM deve permanecer conectado.
6. Frequência simulada deve aparecer no logger.
7. Alteração de frequência no logger deve chegar ao emulador.
8. Alteração de estado no emulador deve ser percebida pelo polling.

## Etapa C — DXLog

Repetir os testes utilizando DXLog com baseline 19200/8N1 e polling de 300 ms.

## Etapa D — Captura

Gerar relação de todos os comandos enviados por cada logger e classificá-los como:

- obrigatório;
- desejável;
- opcional;
- não necessário.

---

# Critério de Aceite do SPIKE

O SPIKE será considerado aprovado quando:

- N1MM reconhecer e mantiver comunicação estável com o emulador;
- DXLog reconhecer e mantiver comunicação estável com o emulador;
- leitura e alteração de frequência funcionarem nos dois sentidos;
- modo for corretamente sincronizado;
- PTT puder ser identificado e alterado em laboratório;
- o conjunto mínimo de comandos CAT necessários estiver documentado.

---

# Fora do Escopo

Nesta fase não serão implementados:

- Vector Gateway;
- Vector Protocol;
- Hamlib;
- `rigctld`;
- autenticação;
- Lease;
- rádio físico;
- áudio remoto;
- transmissão RF real.

PTT neste SPIKE altera apenas um estado booleano simulado.

---

# Estrutura de Código

```text
spikes/cat-ts2000/
├── README.md
├── requirements.txt
├── emulator.py
├── ts2000.py
└── tests/
    └── test_ts2000.py
```

---

# Próximo Passo após Aprovação

Após o SPIKE ser aprovado, a arquitetura evolui para:

```text
N1MM / DXLog
      |
      v
COM Virtual
      |
      v
TS-2000 CAT Adapter
      |
      v
Vector Client
      |
      v
Vector Protocol
      |
      v
Vector Gateway
```

Nesse momento, alterações CAT deixarão de modificar `RadioState` local e passarão a produzir comandos normalizados do domínio Vector.
