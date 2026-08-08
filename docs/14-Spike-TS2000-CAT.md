# GADX Vector
# 14 - SPIKE-002 — Emulação CAT TS-2000

Versão: 1.3
Status: **SUCCESS — N1MM validado**

---

# Objetivo

Validar tecnicamente a camada de compatibilidade CAT do **Vector Client**, provando que **N1MM Logger+** e **DXLog** conseguem controlar um rádio virtual local apresentado como **Kenwood TS-2000** através de uma porta COM virtual.

Este SPIKE não utiliza Vector Gateway, Hamlib, `rigctld` ou rádio físico. O objetivo é isolar o risco técnico da borda local:

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

---

# Fonte Canônica do Protocolo CAT

A especificação normativa utilizada pelo emulador é o manual oficial:

**JVCKENWOOD — TS-2000 / TS-2000X / TS-B2000 Instruction Manual — B62-1221-70**

A parte de Computer Control encontra-se no **Chapter 21 — Appendix**:

- COM Connector — página 113;
- Computer Control — página 114;
- PC Control Command Tables — páginas 115 a 141.

Quando houver conflito entre uma implementação anterior do SPIKE, exemplos encontrados na Internet ou suposições feitas durante testes e a tabela oficial do manual, **o manual B62-1221-70 prevalece**.

A captura empírica de N1MM/DXLog continua sendo usada para decidir **quais comandos precisam ser implementados**, mas o formato e a semântica de cada comando implementado devem seguir a documentação oficial Kenwood.

Caminho previsto para a cópia de referência no repositório:

```text
references/kenwood/TS-2000/B62-1221-70.pdf
```

---

# Hipótese

O **Kenwood TS-2000** é um bom candidato para a fachada CAT inicial do GADX Vector porque possui suporte específico nos loggers alvo, protocolo ASCII terminado por `;` e comandos suficientes para frequência, modo, VFO, split e PTT.

**Resultado da hipótese para N1MM: CONFIRMADA.**

A validação com DXLog permanece pendente como teste adicional de interoperabilidade.

---

# Baseline de Laboratório

```text
Radio model: Kenwood TS-2000
Speed:       19200 baud
Data bits:   8
Parity:      None
Stop bits:   1
```

No laboratório Windows foi utilizado um par com0com:

```text
N1MM      -> COM9
Emulador  -> COM18
```

---

# Resultado Experimental 001 — N1MM

Data: 2026-08-07
Resultado: **SUCCESS — comunicação CAT bidirecional estável**.

O N1MM abriu COM9 e o emulador abriu COM18. O emulador recebeu tráfego CAT real do logger, respondeu ao polling continuamente e aceitou alterações de frequência e modo originadas no N1MM.

## Polling normal observado

```text
IF;FA;FB;AG0;
```

O polling foi observado repetidamente em intervalos próximos de 500 ms.

## Sequência especial observada

```text
FR1;IF;FR0;AI0;
```

O emulador alternou temporariamente o RX para VFO-B, respondeu `IF` com a frequência correspondente e retornou ao VFO-A sem interromper a sessão.

## Evidência de execução — log real

Trecho representativo do ensaio bem-sucedido:

```text
2026-08-07 23:47:11,301 INFO Opening COM18 at 19200 baud, 8N1
2026-08-07 23:47:11,302 INFO TS-2000 emulator ready
2026-08-07 23:47:11,806 DEBUG CAT RX raw: 'IF;FA;FB;AG0;'
2026-08-07 23:47:11,806 DEBUG CAT TX: IF000140740000000+0000000000020000000;
2026-08-07 23:47:11,807 DEBUG CAT TX: FA00014074000;
2026-08-07 23:47:11,807 DEBUG CAT TX: FB00007074000;
2026-08-07 23:47:11,808 DEBUG CAT TX: AG0128;

2026-08-07 23:47:28,382 DEBUG CAT RX raw: 'FA00014200000;'
2026-08-07 23:47:28,382 INFO State changed: FA=14200000Hz FB=7074000Hz RX=VFO-A TX=VFO-A MODE=USB PTT=OFF SPLIT=OFF AI=0 AG0=128 AG1=128

2026-08-07 23:47:37,369 DEBUG CAT RX raw: 'FA00021070000;'
2026-08-07 23:47:37,369 INFO State changed: FA=21070000Hz FB=7074000Hz RX=VFO-A TX=VFO-A MODE=USB PTT=OFF SPLIT=OFF AI=0 AG0=128 AG1=128

2026-08-07 23:47:41,914 DEBUG CAT RX raw: 'MD3;'
2026-08-07 23:47:41,914 INFO State changed: FA=21070000Hz FB=7074000Hz RX=VFO-A TX=VFO-A MODE=CW PTT=OFF SPLIT=OFF AI=0 AG0=128 AG1=128

2026-08-07 23:47:44,852 DEBUG CAT RX raw: 'MD2;'
2026-08-07 23:47:44,852 INFO State changed: FA=21070000Hz FB=7074000Hz RX=VFO-A TX=VFO-A MODE=USB PTT=OFF SPLIT=OFF AI=0 AG0=128 AG1=128

2026-08-07 23:47:55,148 DEBUG CAT RX raw: 'FA00007150000;'
2026-08-07 23:47:55,148 INFO State changed: FA=7150000Hz FB=7074000Hz RX=VFO-A TX=VFO-A MODE=USB PTT=OFF SPLIT=OFF AI=0 AG0=128 AG1=128
2026-08-07 23:47:55,249 DEBUG CAT RX raw: 'MD1;'
2026-08-07 23:47:55,249 INFO State changed: FA=7150000Hz FB=7074000Hz RX=VFO-A TX=VFO-A MODE=LSB PTT=OFF SPLIT=OFF AI=0 AG0=128 AG1=128

2026-08-07 23:48:06,156 DEBUG CAT RX raw: 'FA00003520000;'
2026-08-07 23:48:06,156 INFO State changed: FA=3520000Hz FB=7074000Hz RX=VFO-A TX=VFO-A MODE=CW PTT=OFF SPLIT=OFF AI=0 AG0=128 AG1=128

2026-08-07 23:48:18,066 DEBUG CAT RX raw: 'FA00028500000;MD2;'
2026-08-07 23:48:18,066 INFO State changed: FA=28500000Hz FB=7074000Hz RX=VFO-A TX=VFO-A MODE=USB PTT=OFF SPLIT=OFF AI=0 AG0=128 AG1=128
```

Durante o ensaio registrado não ocorreram `Write timeout`, exceções fatais ou comandos `UNSUPPORTED` no fluxo normal observado.

O log comprova mudanças reais entre 20 m, 15 m, 40 m, 80 m e 10 m, além de mudanças USB/LSB/CW, mantendo o polling e o estado interno coerentes.

## Caminho comprovado

```text
N1MM
  -> COM9
  -> com0com
  -> COM18
  -> emulator.py
  -> ts2000.py
  -> RadioState
  -> resposta CAT
  -> N1MM
```

---

# Subconjunto CAT implementado

| Comando | Função | Regra oficial usada |
|---|---|---|
| `ID` | Identificação TS-2000 | `ID019;` |
| `FA` | Frequência VFO A | 11 dígitos em Hz |
| `FB` | Frequência VFO B | 11 dígitos em Hz |
| `MD` | Modo | códigos Kenwood 1..9, com 8 reservado |
| `FR` | seleção RX | 0=A, 1=B; 2=M.CH e 3=CALL previstos pelo protocolo |
| `FT` | seleção TX | 0=A, 1=B; 2=M.CH e 3=CALL previstos pelo protocolo |
| `TX` | Transmit | `TX0;` main / `TX1;` sub |
| `RX` | Receive | `RX;` |
| `IF` | Estado agregado | resposta fixa de 38 caracteres |
| `AI` | Auto Information | `0=OFF`, `2=Extended AI`; AI1/AI3 não suportados |
| `AG` | AF gain | receiver 0/1 + nível `000..255` |

A implementação seguirá duas regras:

> **Implementar somente comandos necessários e comprovadamente utilizados pelos loggers.**

> **Para cada comando implementado, seguir o formato oficial B62-1221-70.**

---

# Estrutura Oficial do IF

A resposta `IF` segue os campos da tabela oficial Kenwood:

| Campo | Conteúdo |
|---|---|
| P1 | Frequência em Hz, 11 dígitos |
| P2 | Frequency step, 4 caracteres |
| P3 | Offset RIT/XIT assinado, 6 caracteres |
| P4 | RIT OFF/ON |
| P5 | XIT OFF/ON |
| P6 | Memory bank |
| P7 | Memory channel, 2 caracteres |
| P8 | RX/TX |
| P9 | Operating mode, conforme `MD` |
| P10 | VFO/M.CH/CALL, conforme `FR`/`FT` |
| P11 | Scan status |
| P12 | Simplex/Split |
| P13 | OFF/TONE/CTCSS/DCS |
| P14 | Tone number, 2 caracteres |
| P15 | Shift status |

Com prefixo `IF` e terminador `;`, a resposta possui **38 caracteres**.

---

# Critérios de Sucesso

## Etapa A — Parser

- [x] comandos fragmentados entre leituras;
- [x] múltiplos comandos na mesma leitura;
- [x] separação pelo terminador `;`;
- [x] comando desconhecido não encerra o processo.

## Etapa B — N1MM

- [x] par COM virtual criado;
- [x] emulador abre uma extremidade;
- [x] N1MM abre a outra;
- [x] tráfego CAT bidirecional comprovado;
- [x] `IF` aceito sem comportamento anômalo;
- [x] frequência simulada apresentada e consultada corretamente;
- [x] alteração de frequência N1MM -> emulador;
- [x] resposta de estado emulador -> N1MM;
- [x] modo sincronizado USB/LSB/CW;
- [ ] split sincronizado;
- [ ] PTT identificado.

## Etapa C — DXLog

- [ ] conexão;
- [ ] frequência;
- [ ] modo;
- [ ] split;
- [ ] PTT;
- [ ] captura do polling real.

---

# Conclusão do marco N1MM

## **SPIKE CAT TS-2000 / N1MM — SUCCESS**

O ensaio de 2026-08-07 validou o principal risco técnico que motivou o SPIKE: um software legado pode conversar por COM virtual com uma fachada CAT TS-2000 implementada pelo GADX Vector, consultar seu estado e comandar frequência e modo de forma bidirecional e estável.

Com isso, a hipótese arquitetural **CAT legado -> COM virtual -> adaptador TS-2000 -> estado interno Vector** está tecnicamente comprovada para N1MM.

Split, PTT e DXLog permanecem como testes complementares antes do encerramento formal completo do SPIKE, mas não invalidam o marco de sucesso já obtido para a integração N1MM.

---

# Fora do Escopo

Nesta fase não entram Vector Gateway, Vector Protocol, Hamlib, `rigctld`, autenticação, Lease, rádio físico, áudio remoto ou transmissão RF real.

PTT altera somente estado booleano simulado.

---

# Próximos Testes

1. provocar e registrar Split no N1MM;
2. provocar e registrar PTT em laboratório;
3. repetir a integração com DXLog;
4. após isso, encerrar formalmente o SPIKE e promover a fachada CAT para o adaptador do Vector Client.

---

# Próximo Passo Arquitetural

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
