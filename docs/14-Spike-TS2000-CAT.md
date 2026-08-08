# GADX Vector
# 14 - SPIKE-002 — Emulação CAT TS-2000

Versão: 1.4
Status: **SUCCESS — N1MM CAT validado / Keying em validação**

---

# Objetivo

Validar tecnicamente a camada de compatibilidade do **Vector Client**, provando que **N1MM Logger+** e **DXLog** conseguem controlar um rádio virtual local apresentado como **Kenwood TS-2000** através de porta COM virtual e investigar a interface separada utilizada para CW/PTT.

O SPIKE começou isolando o risco CAT:

```text
N1MM / DXLog
      |
      v
COM Virtual CAT
      |
      v
TS-2000 CAT Emulator
      |
      v
Estado simulado
```

Após o primeiro ensaio bem-sucedido, foi identificado que uma configuração típica de contest pode utilizar **duas interfaces seriais independentes**: uma para CAT e outra para CW/PTT por linhas RTS/DTR. Essa segunda interface passa a fazer parte da investigação do SPIKE.

---

# Fonte Canônica do Protocolo CAT

A especificação normativa utilizada pelo emulador é o manual oficial:

**JVCKENWOOD — TS-2000 / TS-2000X / TS-B2000 Instruction Manual — B62-1221-70**

A parte de Computer Control encontra-se no **Chapter 21 — Appendix**:

- COM Connector — página 113;
- Computer Control — página 114;
- PC Control Command Tables — páginas 115 a 141.

Quando houver conflito entre uma implementação anterior do SPIKE, exemplos encontrados na Internet ou suposições feitas durante testes e a tabela oficial do manual, **o manual B62-1221-70 prevalece**.

Caminho previsto para a cópia de referência no repositório:

```text
references/kenwood/TS-2000/B62-1221-70.pdf
```

---

# Hipótese CAT

O **Kenwood TS-2000** é um bom candidato para a fachada CAT inicial do GADX Vector porque possui suporte específico nos loggers alvo, protocolo ASCII terminado por `;` e comandos suficientes para frequência, modo, VFO, split e PTT.

**Resultado da hipótese para N1MM: CONFIRMADA.**

A validação com DXLog permanece pendente como teste adicional de interoperabilidade.

---

# Baseline de Laboratório CAT

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

# Resultado Experimental 001 — N1MM CAT

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

---

# Descoberta Experimental 002 — CAT separado de CW/PTT

Durante a configuração do N1MM foi observado que o logger permite uma arquitetura típica de estação de contest com funções seriais distintas:

```text
                 N1MM / DXLog
                      |
           +----------+----------+
           |                     |
           v                     v
      COM CAT                COM KEYING
  frequência/modo/       RTS/DTR para
   VFO/split/PTT           CW e/ou PTT
           |                     |
           +----------+----------+
                      |
                 Vector Client
```

## Decisão de projeto decorrente

O Vector Client deverá ser capaz de expor **interfaces virtuais independentes**:

### CAT Adapter
Responsável pela fachada TS-2000 e comandos de rádio, incluindo:

- frequência;
- modo;
- VFO;
- split;
- PTT via CAT (`TX`/`RX`) quando configurado pelo software legado.

### Keying Adapter
Responsável por observar sinais de controle serial usados pelo logger, inicialmente:

- RTS;
- DTR;
- PTT por linha serial;
- CW keying por linha serial.

A implementação de uma origem de PTT não exclui a outra. O Vector deverá aceitar tanto **PTT via CAT** quanto **PTT via Keying**, convertendo ambos para a mesma intenção normalizada de PTT antes das regras de autorização, Lease, máquina de estados e fail-safe.

---

# Questão arquitetural aberta — timing de CW

CW não deve ser tratado prematuramente como uma simples sequência de eventos JSON enviados individualmente pela WAN.

O keying de CW é sensível a:

- latência;
- jitter;
- perda ou reordenação de comunicação;
- variações de scheduling do sistema operacional.

Portanto, o SPIKE deverá medir e avaliar onde o timing de CW deve ser executado:

1. Vector Client;
2. Vector Gateway;
3. keyer dedicado junto à estação;
4. outra solução de execução local.

A preferência arquitetural inicial é manter o **timing crítico próximo ao hardware**, mas esta preferência ainda **não é uma decisão normativa**. Ela deverá ser confirmada experimentalmente antes de gerar ADR própria.

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

---

# Critérios de Sucesso

## Etapa A — Parser

- [x] comandos fragmentados entre leituras;
- [x] múltiplos comandos na mesma leitura;
- [x] separação pelo terminador `;`;
- [x] comando desconhecido não encerra o processo.

## Etapa B — N1MM CAT

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
- [ ] PTT via CAT identificado.

## Etapa C — N1MM Keying

- [ ] segundo par COM virtual criado;
- [ ] RTS observado pelo protótipo;
- [ ] DTR observado pelo protótipo;
- [ ] PTT por linha serial identificado;
- [ ] CW keying identificado;
- [ ] comportamento/timing registrado.

## Etapa D — DXLog

- [ ] conexão CAT;
- [ ] frequência;
- [ ] modo;
- [ ] split;
- [ ] PTT;
- [ ] captura do polling real;
- [ ] comportamento da interface de keying registrado quando aplicável.

---

# Conclusão do marco N1MM CAT

## **SPIKE CAT TS-2000 / N1MM — SUCCESS**

O ensaio de 2026-08-07 validou o principal risco técnico inicial: um software legado pode conversar por COM virtual com uma fachada CAT TS-2000 implementada pelo GADX Vector, consultar seu estado e comandar frequência e modo de forma bidirecional e estável.

Com isso, a hipótese **CAT legado -> COM virtual -> adaptador TS-2000 -> estado interno Vector** está tecnicamente comprovada para N1MM.

A descoberta da segunda porta não invalida o sucesso CAT. Ela amplia o escopo de compatibilidade local do Vector Client para representar corretamente estações reais de contest.

---

# Fora do Escopo

Nesta fase não entram Vector Gateway, Vector Protocol, Hamlib, `rigctld`, autenticação, Lease, rádio físico, áudio remoto ou transmissão RF real.

PTT altera somente estado simulado. Nenhum teste deste SPIKE deve provocar transmissão RF real.

---

# Próximos Testes

1. provocar e registrar Split no N1MM;
2. testar PTT via Radio Command (`TX`/`RX`) na COM CAT;
3. criar segundo par com0com para Keying;
4. capturar RTS/DTR usados pelo N1MM para PTT/CW;
5. medir/avaliar o problema de timing de CW;
6. repetir a integração com DXLog;
7. encerrar formalmente o SPIKE e promover CAT Adapter e Keying Adapter para componentes do Vector Client.

---

# Próximo Passo Arquitetural

```text
                         N1MM / DXLog
                              |
                 +------------+------------+
                 |                         |
                 v                         v
             COM CAT                  COM KEYING
          TS-2000 Adapter            RTS/DTR Adapter
                 |                         |
                 +------------+------------+
                              |
                         Vector Client
                              |
                              v
                        Vector Protocol
                              |
                              v
                        Vector Gateway
```
