# GADX Vector — D8 Productization / Release Packaging

## Objetivo

D1-D7 provaram o backend tecnico em maquinas reais. D8 transforma esse baseline em uma experiencia de produto distribuivel para Windows 10/11, sem reescrever a logica de seguranca ja validada.

Principio central:

> D8 e uma camada de produto e distribuicao sobre D1-D7. Safety gate, backup, rollback, fail-safe, preservacao de `vector.ini` e preservacao de COMs continuam sendo responsabilidade do backend existente.

---

## D8A — Release identity / versionamento

**Objetivo:** toda execucao precisa saber qual geracao do instalador esta sendo usada e deixar isso visivel ao operador e ao diagnostico posterior.

Entregas:

- `installer/release.json`;
- versao do produto visivel no bootstrap e no orquestrador;
- canal de release (`development`, futuramente `rc` / `stable`);
- baseline de origem documentado;
- versao gravada em `config/installed-build.txt` nas operacoes que geram manifesto.

**Status: VALIDADA EM CAMPO em 2026-09-06.**

A validacao confirmou que bootstrap e orquestrador exibem a mesma identidade de release e que uma instalacao CURRENT saudavel chega a `Mode: NONE / Payload drift: NO` sem alteracoes.

---

## D8B — Launcher unico

**Objetivo:** eliminar a necessidade de o operador conhecer comandos PowerShell internos.

O launcher deve:

- solicitar elevacao UAC quando necessario;
- detectar `CLEAN`, `CURRENT`, `LEGACY` ou `BROKEN`;
- mostrar a versao do produto;
- mostrar o plano recomendado (`INSTALL`, `REPAIR`, `MIGRATE`, `NONE`);
- executar primeiro Preview;
- exigir confirmacao explicita antes de Apply;
- exibir claramente quando o radio sera colocado em safety gate;
- chamar `setup-vector.ps1` como backend.

O launcher nao deve duplicar a logica de D1-D7.

Artefatos:

```text
installer/setup-launcher.ps1
installer/GADX-Vector-Setup.cmd
setup-vector.ps1 -AsJson
```

`setup-vector.ps1 -AsJson` e a interface read-only entre o backend validado e a GUI. Ela inclui classificacao, modo recomendado, payload drift e o resultado completo do detector, evitando que o launcher replique as regras do orquestrador.

### Validacao D8B.1 — CURRENT saudavel

Data: 2026-09-06

O launcher grafico foi aberto em uma instalacao CURRENT saudavel e exibiu corretamente:

```text
Release        0.8.0-dev.2 / development / D8B
Detected       CURRENT
Recommended    NONE
Payload drift  NO
Service        Running
Runtime        OK
com0com        OK
Safety         No changes required
```

A GUI mostrou `Healthy installation`, manteve `Apply` desabilitado e refletiu o mesmo estado reportado pelo backend.

### Validacao D8B.2 — Preview pela GUI

Data: 2026-09-06

O botao **Run Preview** executou o backend read-only e exibiu na propria janela:

```text
GADX Vector Setup - D1-D7 Backend Orchestrator
Release      : 0.8.0-dev.2 / development / D8B
Install root : C:\Ham\GADX-Vector
Detected     : CURRENT
Mode         : NONE
Payload drift: NO

Current installation is healthy and matches the installer generation. No repair or migration is required.
```

O rodape mostrou `Preview passed. No Apply is required.` e o botao **Apply permaneceu desabilitado**.

Isso valida a regra central da GUI: Preview e obrigatorio antes de qualquer Apply e uma instalacao `NONE` nunca habilita Apply.

**Status: D8B VALIDADA EM CAMPO para CURRENT saudavel + Preview read-only.**

---

## D8C — UX de instalacao / repair / update

**Status: EM IMPLEMENTACAO — release 0.8.0-dev.3.**

Fluxo alvo:

```text
Abrir GADX Vector Setup
        ↓
UAC / Administrador
        ↓
Versao + detector
        ↓
Resumo da maquina
        ↓
Plano recomendado
        ↓
PREVIEW
        ↓
Confirmar Apply
        ↓
Safety gate quando aplicavel
        ↓
D1-D7 backend
        ↓
Port Manager quando necessario
        ↓
Commissioning
        ↓
INSTALLATION STATUS: READY
```

A interface deve distinguir claramente:

- nenhuma alteracao feita;
- alteracoes planejadas;
- alteracoes aplicadas;
- reboot pendente;
- falha com rollback seguro;
- instalacao pronta.

### Primeiro alvo de D8C

Validar o estado visual e o gating de um plano `REPAIR` sem colocar a estacao operacional em risco.

A primeira validacao sera feita em modo de simulacao somente de interface:

```text
CURRENT + REPAIR
Payload drift = YES
Service = Running
Safety = Hub will be Disabled / Stopped before Apply
```

Nesse modo:

- a janela deve deixar claro que e SIMULATION / NO CHANGES;
- o plano de Repair deve ser apresentado como seria numa maquina real;
- Preview visual pode ser exercitado;
- Apply deve permanecer fisicamente desabilitado em simulacao;
- nenhum arquivo, servico, COM ou radio pode ser alterado.

### Validacao D8C.1 — abertura segura da simulacao REPAIR

Data: 2026-09-06

A simulacao isolada abriu corretamente usando:

```text
installer/setup-repair-simulation.ps1
installer/D8C-Repair-Simulation.cmd
```

A janela exibiu:

```text
Release        0.8.0-dev.3 / development / D8C
Detected       CURRENT
Recommended    REPAIR
Payload drift  YES
Service        Running
Runtime        OK
com0com        OK
Safety         SIMULATION - real Hub untouched
```

O botao `Apply REPAIR` permaneceu desabilitado e a estacao operacional continuou em `CURRENT / NONE / Payload drift: NO` no backend real.

Durante a implementacao foi encontrado um problema de encoding no Windows PowerShell 5.1 causado por caracteres Unicode em `setup-launcher.ps1`. Para nao arriscar regressao no launcher D8B ja validado, a simulacao D8C foi isolada em um script ASCII-only e o launcher de producao foi restaurado ao baseline validado.

**Status: D8C.1 VALIDADA EM CAMPO. Proximo passo: validar Run Preview dentro da simulacao REPAIR.**

Depois dessa validacao visual, D8C sera testada numa instalacao real que naturalmente esteja em estado REPAIR, reutilizando o backend D7 ja validado.

---

## D8D — Distribuicao e dependencias

Definir um artefato previsivel de distribuicao contendo ou sabendo obter:

- bootstrap/launcher;
- scripts do installer;
- payload app/service/tools;
- metadados de release;
- com0com quando a politica de redistribuicao permitir;
- Python/runtime conforme estrategia escolhida.

Objetivo: evitar depender de arquivos aleatorios ja presentes na maquina.

---

## D8E — Port Manager integrado

O Port Manager continua congelado funcionalmente, mas deve ser chamado pelo fluxo de produto quando houver configuracao de COMs a revisar/criar.

O operador nao deve precisar executar `python.exe tools\port_manager.py` manualmente.

---

## D8F — Commissioning e relatorio final

Ao final, mostrar um resumo de saude contendo no minimo:

```text
Produto / versao
Modo executado
Runtime
com0com
vector.ini
GADXVectorHub
CAT ports
Keying ports
PTT safe state
Backup criado
Reboot pending
INSTALLATION STATUS
```

Quando houver falha, apontar diretamente para backup e log diagnostico preservado.

---

## D8G — Release Candidate

Antes de declarar D8 concluida, repetir em maquinas reais:

```text
1. CLEAN Windows 10/11
2. CURRENT saudavel
3. CURRENT com payload drift
4. CURRENT quebrada
5. LEGACY com GADXVectorBridge
6. runtime ausente
7. runtime incompleto
8. reboot apos mudanca de COMs
9. repair repetido / idempotencia
10. falha induzida + rollback
```

---

## Criterios de aceite da D8

- um unico ponto de entrada para o operador;
- versao/release visivel;
- Preview antes de Apply;
- UAC/elevacao tratados pela experiencia de produto;
- D1-D7 reutilizados sem duplicacao;
- safety gate claramente comunicado;
- `vector.ini` e COMs preservados nos caminhos de Repair/Migration apropriados;
- Port Manager integrado;
- commissioning final legivel;
- instalacao/repair chega a `INSTALLATION STATUS: READY` sem comandos internos manuais;
- Release Candidate repetivel em maquina limpa e em instalacao existente.

---

## Regra de desenvolvimento

Cada subfase D8 deve ser pequena e validavel em campo. Nao avancar para um grande instalador monolitico antes de termos versionamento, launcher e fluxo Preview/Apply funcionando separadamente.
