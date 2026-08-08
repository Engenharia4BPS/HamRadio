# GADX Vector – Decisões Arquiteturais

Este documento registra decisões importantes para preservar o contexto técnico do projeto ao longo do tempo.

---

## ADR-001 — Protocolo interno independente do Hamlib
**Data:** 2026-08-07

### Decisão
O protocolo de comunicação entre Vector Client e Vector Gateway será próprio e independente do Hamlib.

### Motivo
O Hamlib deve ser tratado como uma integração externa e não como o núcleo da plataforma.

### Consequência
Será possível substituir ou complementar o Hamlib por outros backends no futuro sem redesenhar todo o sistema.

---

## ADR-002 — Compatibilidade CAT como camada de borda
**Data:** 2026-08-07

### Decisão
A emulação CAT será implementada no Vector Client como camada de compatibilidade com programas como N1MM e DXLog.

### Motivo
Permitir que softwares existentes enxerguem o rádio remoto como se fosse um rádio local suportado.

### Consequência
O núcleo do GADX Vector não dependerá de um protocolo CAT específico.

---

## ADR-003 — Interface Web com serviço local
**Data:** 2026-08-07

### Decisão
A experiência do usuário será baseada em interface Web, acompanhada por um serviço nativo local apenas para recursos que navegadores não conseguem fornecer diretamente, como COM virtual.

### Consequência
A maior parte da aplicação permanece independente de sistema operacional, isolando código nativo específico.

---

## ADR-004 — Gateway por site
**Data:** 2026-08-07

### Decisão
Cada site físico terá seu próprio Vector Gateway.

### Sites iniciais
- Guatupê
- Purunã
- Casa 68
- Estação de satélite

### Consequência
Cada Gateway torna-se autoridade local sobre seus recursos e sessões.

---

## ADR-005 — Identidade da plataforma
**Data:** 2026-08-07

### Decisão
**GADX** identifica o **Grupo Araucária de DX** e **GADX Vector** é o nome oficial da plataforma de automação e operação remota desenvolvida pelo grupo.

Os componentes da plataforma utilizarão a marca Vector, incluindo **Vector Gateway**, **Vector Client**, **Vector Protocol** e **Vector API**.

### Motivo
Separar claramente a identidade da organização da identidade do produto e permitir a evolução futura de outros produtos sob a marca GADX.

---

## ADR-006 — Recursos e Drivers como abstração de hardware
**Data:** 2026-08-07

### Decisão
Equipamentos físicos serão representados no núcleo como Resources e acessados por meio de Drivers específicos.

### Motivo
Evitar acoplamento do domínio a fabricantes, protocolos ou bibliotecas específicas.

### Consequência
Protocolos, APIs, interfaces e automações do Vector manipularão entidades do domínio em vez de hardware diretamente.

---

## ADR-007 — Secure by Default
**Data:** 2026-08-07

### Decisão
Toda funcionalidade do GADX Vector deverá seguir o princípio **Secure by Default**.

### Consequências
- WSS/TLS obrigatório em produção para Vector Protocol.
- Credenciais permanentes utilizadas apenas no processo de autenticação.
- Tokens temporários para sessões.
- Credenciais e tokens não podem aparecer em logs ou URLs.
- Auditoria de operações críticas.
- Falhas de comunicação devem priorizar segurança operacional.
- Estado de PTT não deve ser declarado como seguro sem confirmação quando a comunicação com o equipamento tiver sido perdida.

---

## ADR-008 — Hamlib/rigctld como backend oficial de rádio da v1
**Data:** 2026-08-07

### Decisão
Na primeira versão do GADX Vector, o backend oficial para controle de rádios será o **Hamlib**, preferencialmente através do daemon **rigctld**.

O acesso ao Hamlib ocorrerá exclusivamente através do **Hamlib Driver**. Vector API, Vector Protocol, Modelo de Domínio e demais camadas não deverão depender diretamente do Hamlib.

### Motivo
- Grande quantidade de rádios suportados.
- Evita reimplementação e manutenção de múltiplos protocolos CAT proprietários.
- Disponibiliza interface de rede através do `rigctld`.
- Permite concentrar o desenvolvimento do Vector em segurança, sessões, multiestação, automação e abstração.

### Consequências
- Hamlib é backend, não protocolo interno.
- O Hamlib Driver traduz operações e estados entre o domínio Vector e `rigctld`.
- Outros Drivers poderão ser adicionados futuramente sem alterar Vector API ou Vector Protocol.
- `rigctld` deve permanecer na rede confiável do site e não deve ser exposto diretamente à Internet como interface pública do Vector.
- A compatibilidade funcional deve ser determinada por capabilities reais do rádio/backend, e não apenas pela existência conceitual da operação no Vector.
