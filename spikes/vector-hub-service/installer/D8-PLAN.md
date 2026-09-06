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

Artefatos iniciais:

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

A GUI mostrou `Healthy installation`, manteve `Apply` desabilitado e refletiu o mesmo estado reportado pelo backend em Preview (`CURRENT / NONE / Payload drift: NO`).

**Status: D8B.1 VALIDADA EM CAMPO; fluxo do botao Run Preview ainda em validacao.**

---

## D8C — UX de instalacao / repair / update

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
