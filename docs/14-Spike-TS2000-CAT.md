# GADX Vector
# 14 - SPIKE-002 — Emulação CAT TS-2000

Versão: 1.5
Status: **SUCCESS — N1MM CAT + Split + Keying validados / DXLog pendente**

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

Após o primeiro ensaio bem-sucedido, foi identificado que uma configuração típica de contest pode utilizar **duas interfaces seriais independentes**: uma para CAT e outra para CW/PTT por linhas RTS/DTR.

---

# Fonte Canônica do Protocolo CAT

A especificação normativa utilizada pelo emulador é o manual oficial:

**JVCKENWOOD — TS-2000 / TS-2000X / TS-B2000 Instruction Manual — B62-1221-70**

A parte de Computer Control encontra-se no **Chapter 21 — Appendix**:

- COM Connector — página 113;
- Computer Control — página 114;
- PC Control Command Tables — páginas 115 a 141.

Quando houver conflito entre implementação anterior, exemplos de terceiros ou suposições de teste e a tabela oficial, **o manual B62-1221-70 prevalece**.

Caminho previsto para a cópia de referência no repositório:

```text
references/kenwood/TS-2000/B62-1221-70.pdf
```

---

# Hipótese CAT

O **Kenwood TS-2000** é um bom candidato para a fachada CAT inicial do GADX Vector porque possui suporte específico nos loggers alvo, protocolo ASCII terminado por `;` e comandos suficientes para frequência, modo, VFO, split e PTT.

**Resultado da hipótese para N1MM: CONFIRMADA.**

A validação com DXLog permanece como último teste de interoperabilidade previsto no escopo original deste SPIKE.

---

# Baseline de Laboratório

## CAT

```text
Radio model: Kenwood TS-2000
Speed:       19200 baud
Data bits:   8
Parity:      None
Stop bits:   1

N1MM      -> COM9
Emulador  -> COM18
```

## Keying

```text
N1MM      -> COM31
Monitor   -> COM32

DTR -> PTT
RTS -> CW
```

O laboratório utilizou pares virtuais fornecidos pelo com0com.

---

# Resultado Experimental 001 — N1MM CAT

Data: 2026-08-07
Resultado: **SUCCESS — comunicação CAT bidirecional estável**.

O N1MM abriu COM9 e o emulador abriu COM18. O emulador recebeu tráfego CAT real, respondeu continuamente ao polling e aceitou alterações de frequência e modo originadas no N1MM.

## Polling normal observado

```text
IF;FA;FB;AG0;
```

Intervalo observado: aproximadamente 500 ms.

## Sequência especial observada

```text
FR1;IF;FR0;AI0;
```

O emulador alternou temporariamente RX para VFO-B, respondeu `IF` com a frequência correspondente e retornou ao VFO-A sem interromper a sessão.

## Funções confirmadas

- frequência em múltiplas bandas;
- mudança de modo USB/LSB/CW;
- VFO A e VFO B;
- polling estável;
- resposta `IF` aceita;
- nenhuma exceção fatal no ensaio;
- nenhum `UNSUPPORTED` no fluxo normal observado.

---

# Resultado Experimental 002 — N1MM Keying

Data: 2026-08-08
Resultado: **SUCCESS — PTT via DTR e CW via RTS detectados corretamente**.

Foi criado um segundo par serial virtual:

```text
N1MM COM31
   |
   +-- DTR = PTT
   +-- RTS = CW
   |
   v
COM32
   |
   v
keying_monitor.py
```

O primeiro ensaio manual comprovou a propagação das modem-control lines pelo com0com.

Em seguida, o N1MM transmitiu uma mensagem CW real através de RTS enquanto mantinha PTT ativo por DTR.

Trecho representativo:

```text
PTT ON  (remote DTR asserted)
CW  ON  (remote RTS asserted)
CW  OFF (pulse ~137 ms)
CW  ON
CW  OFF (pulse ~46 ms)
...
PTT OFF (duration 6411.6 ms)
```

Os pulsos apresentaram duas durações predominantes:

```text
DIT ≈ 44..48 ms
DAH ≈ 137..140 ms
```

A relação observada é aproximadamente 1:3, coerente com CW.

A análise temporal permitiu reconstruir integralmente a mensagem transmitida pelo N1MM:

```text
QRL? DE PY5XT
```

Isso comprova que o Vector Client consegue observar o keying local com fidelidade temporal suficiente para identificar elementos Morse e limites de caracteres/palavras no ambiente de laboratório.

## Importante

Este resultado **não** autoriza concluir que cada transição de RTS deve ser enviada individualmente pela WAN.

A qualidade de CW remoto poderá ser prejudicada por latência, jitter, perda ou scheduling. A localização definitiva do timing crítico será tratada em SPIKE próprio.

---

# Resultado Experimental 003 — N1MM Split

Data: 2026-08-08
Resultado: **SUCCESS — Split sincronizado e modelagem RX/TX VFO validada**.

O N1MM foi colocado em Split com:

```text
VFO A / RX = 28.450 MHz
VFO B / TX = 28.005 MHz
Mode        = USB
```

A sequência CAT observada para entrada em Split foi:

```text
FB00028005000;
FR1;
MD2;FR0;
FT1;
```

Interpretação:

1. `FB00028005000;` programa VFO B em 28.005 MHz;
2. `FR1;` seleciona temporariamente VFO B para RX;
3. `MD2;` garante USB nesse contexto;
4. `FR0;` retorna RX ao VFO A;
5. `FT1;` seleciona VFO B como VFO de transmissão.

Estados intermediários observados:

```text
Inicial: RX=A / TX=A -> Split OFF
FR1:    RX=B / TX=A -> Split ON temporário
FR0:    RX=A / TX=A -> Split OFF
FT1:    RX=A / TX=B -> Split ON definitivo
```

Estado final:

```text
FA=28450000 Hz
FB=28005000 Hz
RX=VFO-A
TX=VFO-B
MODE=USB
SPLIT=ON
```

O polling subsequente confirmou repetidamente:

```text
IF000284500000000+0000000000020010000;
FA00028450000;
FB00028005000;
```

## Consequência para o modelo

O ensaio confirmou a modelagem adotada no protótipo:

```text
Split = (RX VFO != TX VFO)
```

Não é necessário manter um booleano independente de Split como fonte de verdade. O estado de Split é derivado da seleção distinta dos VFOs de RX e TX.

---

# Descoberta Arquitetural — CAT separado de CW/PTT

Os ensaios demonstraram que o Vector Client deve suportar interfaces locais independentes:

```text
                 N1MM / DXLog
                      |
           +----------+----------+
           |                     |
           v                     v
      COM CAT                COM KEYING
 frequência/modo/          RTS/DTR
   VFO/split              CW / PTT
           |                     |
           +----------+----------+
                      |
                 Vector Client
```

## CAT Adapter

Responsável por:

- frequência;
- modo;
- VFO;
- split;
- CAT PTT (`TX`/`RX`) quando utilizado pelo software legado.

## Keying Adapter

Responsável por:

- observar RTS;
- observar DTR;
- transformar DTR/RTS em intenções normalizadas de PTT/CW;
- preservar medição temporal para diagnóstico e futuros testes.

PTT via CAT e PTT via linha serial são entradas diferentes para a mesma intenção lógica de PTT antes das regras de Lease, máquina de estados, autorização e fail-safe.

---

# Questão arquitetural aberta — CW remoto

O SPIKE comprova a captura local de CW, mas não define ainda sua estratégia WAN.

A decisão futura deverá avaliar:

1. envio de eventos de keying pela rede;
2. envio de texto/macro para execução remota;
3. geração no Vector Gateway;
4. keyer dedicado junto à estação;
5. mecanismos de buffer, timestamp e compensação de jitter.

A preferência inicial continua sendo manter o **timing crítico próximo ao hardware**, porém isso ainda não é ADR normativa.

---

# Subconjunto CAT implementado

| Comando | Função | Regra oficial usada |
|---|---|---|
| `ID` | Identificação TS-2000 | `ID019;` |
| `FA` | Frequência VFO A | 11 dígitos em Hz |
| `FB` | Frequência VFO B | 11 dígitos em Hz |
| `MD` | Modo | códigos Kenwood |
| `FR` | seleção RX | VFO A/B e estados previstos no protocolo |
| `FT` | seleção TX | VFO A/B e estados previstos no protocolo |
| `TX` | Transmit | main/sub conforme protocolo |
| `RX` | Receive | `RX;` |
| `IF` | Estado agregado | resposta fixa de 38 caracteres |
| `AI` | Auto Information | valores previstos pelo TS-2000 |
| `AG` | AF gain | receiver + nível |

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
- [x] frequência sincronizada;
- [x] alteração de frequência N1MM -> emulador;
- [x] resposta emulador -> N1MM;
- [x] modo USB/LSB/CW sincronizado;
- [x] VFO A/B sincronizados;
- [x] Split sincronizado.

## Etapa C — N1MM Keying

- [x] segundo par COM virtual criado;
- [x] RTS observado;
- [x] DTR observado;
- [x] PTT por DTR identificado;
- [x] CW por RTS identificado;
- [x] timing dos elementos registrado;
- [x] mensagem CW reconstruída a partir do log.

## Etapa D — DXLog

- [ ] conexão CAT;
- [ ] frequência;
- [ ] modo;
- [ ] split;
- [ ] PTT/keying quando aplicável;
- [ ] captura do polling real.

---

# Conclusão do marco N1MM

## **SPIKE TS-2000 / N1MM — SUCCESS**

Os ensaios validaram os principais riscos da compatibilidade local com N1MM:

- CAT TS-2000 sobre COM virtual;
- polling estável;
- frequência;
- modo;
- VFO A/B;
- Split;
- PTT via DTR;
- CW via RTS.

Também ficou comprovado que o keying de CW capturado localmente mantém estrutura temporal suficientemente clara para reconstruir a mensagem Morse no laboratório.

A arquitetura **software legado -> interfaces COM virtuais -> CAT Adapter/Keying Adapter -> estado interno Vector** está tecnicamente comprovada para N1MM.

---

# Estado do SPIKE

O objetivo N1MM está concluído com **SUCCESS**.

Para encerrar formalmente o SPIKE-002 conforme seu objetivo original, resta apenas a validação equivalente com **DXLog**.

Não é necessário ampliar o emulador TS-2000 antes desse teste, exceto se o DXLog revelar comandos adicionais realmente necessários.

A estratégia de transporte de CW pela WAN será tratada separadamente e não bloqueia o encerramento deste SPIKE.

---

# Fora do Escopo

Nesta fase não entram Vector Gateway, Vector Protocol, Hamlib, `rigctld`, autenticação, Lease, rádio físico, áudio remoto ou transmissão RF real.

Nenhum teste deste SPIKE deve exigir transmissão RF real.

---

# Próximo Teste

Repetir no **DXLog** a bancada já validada:

```text
DXLog -> COM CAT -> TS-2000 Emulator
DXLog -> COM Keying -> keying_monitor.py
```

Registrar:

- sequência inicial;
- polling;
- frequência;
- modo;
- Split;
- PTT/CW quando aplicável;
- comandos adicionais não suportados.

Se os resultados forem equivalentes aos obtidos no N1MM, o SPIKE-002 deverá ser marcado **CLOSED / SUCCESS** e os protótipos promovidos para componentes formais do Vector Client.
