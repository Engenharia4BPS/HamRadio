# GADX Vector
# 14 - SPIKE-002 — Emulação CAT TS-2000

Versão: 1.1 (Draft)
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

| Comando | Observado | Situação após iteração 2 |
|---|---:|---|
| `FR` | Sim | Implementado |
| `IF` | Sim | Implementado |
| `AI0` | Sim | Implementado |
| `FA` | Sim | Implementado |
| `FB` | Sim | Implementado |
| `AG0` | Sim | Implementado |
| `MD` | Não nesta captura | Implementado |
| `FT` | Não nesta captura | Implementado |
| `TX` | Não nesta captura | Implementado |
| `RX` | Não nesta captura | Implementado |
| `ID` | Não nesta captura | Implementado |

A captura real demonstrou que `IF`, `AI` e `AG` precisavam entrar já na segunda iteração.

---

# Subconjunto CAT implementado

| Comando | Função |
|---|---|
| `ID` | Identificação TS-2000 (`019`) |
| `FA` | Frequência VFO A |
| `FB` | Frequência VFO B |
| `MD` | Modo |
| `FR` | VFO de recepção |
| `FT` | VFO de transmissão |
| `TX` | Estado TX simulado |
| `RX` | Estado RX simulado |
| `IF` | Estado agregado do transceptor |
| `AI` | Auto Information (`0`/`2`) |
| `AG` | AF gain do transceptor principal |

A implementação seguirá a regra:

> **Implementar somente comandos necessários e comprovadamente utilizados, mantendo logging completo dos comandos desconhecidos.**

---

# Estrutura do IF

A segunda iteração implementa a resposta `IF` conforme os campos definidos na tabela de comandos PC do TS-2000. O estado do SPIKE preenche dinamicamente frequência, RX/TX, modo, VFO e split; campos ainda não modelados são publicados como valores inativos seguros.

Essa resposta deverá ser validada empiricamente pelo comportamento do N1MM. Caso o logger revele divergência de posição ou semântica, a captura real terá precedência e o emulador será corrigido.

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

Substituir `ts2000.py` pela iteração 2 e repetir o laboratório N1MM.

Resultado esperado no log: desaparecerem os avisos `UNSUPPORTED` para `IF`, `AI0` e `AG0`.

Depois, confirmar visualmente se o N1MM reconhece a frequência inicial de **14.074.000 Hz / USB** e provocar mudanças de frequência para observar comandos `FAxxxxxxxxxxx;` enviados pelo logger.

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
