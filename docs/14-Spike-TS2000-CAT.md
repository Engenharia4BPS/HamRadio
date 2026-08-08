# GADX Vector
# 14 - SPIKE-002 — Emulação CAT TS-2000

Versão: 1.2 (Draft)
Status: Em execução — N1MM conectado com sucesso

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

A escolha permanece experimental até a conclusão dos testes N1MM e DXLog.

---

# Baseline de Laboratório

```text
Radio model: Kenwood TS-2000
Speed:       19200 baud
Data bits:   8
Parity:      None
Stop bits:   1
```

No primeiro laboratório Windows foi utilizado um par com0com:

```text
N1MM      -> COM9
Emulador  -> COM18
```

---

# Resultado Experimental 001 — N1MM

Data: 2026-08-07
Resultado: **sucesso na comunicação serial bidirecional**.

O N1MM abriu COM9 e o emulador abriu COM18. O emulador recebeu tráfego CAT real do logger e respondeu corretamente aos comandos já implementados.

## Sequência observada na inicialização

```text
FR1;IF;FR0;AI0;
```

## Polling normal observado

```text
IF;FA;FB;AG0;
```

O polling foi observado repetidamente em intervalos próximos de 500 ms no primeiro teste.

## Respostas já confirmadas

```text
FA; -> FA00014074000;
FB; -> FB00007074000;
```

Isso comprova o caminho:

```text
N1MM
  -> COM9
  -> com0com
  -> COM18
  -> Python TS-2000 Emulator
  -> resposta CAT
  -> N1MM
```

## Comandos descobertos

| Comando | Observado | Situação atual |
|---|---:|---|
| `FR` | Sim | Implementado |
| `IF` | Sim | Implementado conforme B62-1221-70 |
| `AI0` | Sim | Implementado conforme B62-1221-70 |
| `FA` | Sim | Implementado conforme B62-1221-70 |
| `FB` | Sim | Implementado conforme B62-1221-70 |
| `AG0` | Sim | Implementado conforme B62-1221-70 |
| `MD` | Não nesta captura | Implementado conforme B62-1221-70 |
| `FT` | Não nesta captura | Implementado conforme B62-1221-70 |
| `TX` | Não nesta captura | Implementado conforme B62-1221-70 |
| `RX` | Não nesta captura | Implementado conforme B62-1221-70 |
| `ID` | Não nesta captura | Implementado conforme B62-1221-70 |

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

Campos que ainda não têm representação funcional no `RadioState` devem permanecer com valores coerentes/inativos até serem necessários; eles não devem ser inventados fora da especificação.

---

# Logging de Descoberta

Todo comando recebido é registrado em DEBUG. Comandos não implementados são marcados como `UNSUPPORTED`.

Os próximos testes devem provocar deliberadamente:

1. mudança de frequência pelo N1MM;
2. mudança de banda;
3. mudança de modo;
4. split;
5. PTT;
6. desconexão e reconexão;
7. repetição completa no DXLog.

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
- [ ] `IF` aceito sem comportamento anômalo;
- [ ] frequência simulada apresentada corretamente;
- [ ] alteração de frequência N1MM -> emulador;
- [ ] alteração de estado emulador -> N1MM;
- [ ] modo sincronizado;
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

# Critério de Aceite do SPIKE

O SPIKE será aprovado quando N1MM e DXLog mantiverem comunicação estável, frequência e modo forem sincronizados, PTT puder ser identificado em laboratório e o subconjunto mínimo de comandos estiver documentado.

---

# Fora do Escopo

Nesta fase não entram Vector Gateway, Vector Protocol, Hamlib, `rigctld`, autenticação, Lease, rádio físico, áudio remoto ou transmissão RF real.

PTT altera somente estado booleano simulado.

---

# Próximo Teste

Usar a versão do `ts2000.py` alinhada ao manual B62-1221-70 e repetir o laboratório N1MM.

Resultado esperado no log: ausência de `UNSUPPORTED` para `IF`, `AI0` e `AG0` e reconhecimento consistente da frequência inicial de **14.074.000 Hz / USB**.

Depois, provocar mudanças de frequência, modo, split e PTT para registrar o comportamento real do logger.

---

# Próximo Passo após Aprovação

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
