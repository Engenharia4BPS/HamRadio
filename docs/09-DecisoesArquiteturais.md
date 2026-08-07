# GADX – Decisões Arquiteturais

Este documento registra decisões importantes para preservar o contexto técnico do projeto ao longo do tempo.

---

## ADR-001 — Protocolo interno independente do Hamlib
**Data:** 2026-08-07

### Decisão
O protocolo de comunicação entre GADX Bridge e GADX Gateway será próprio e independente do Hamlib.

### Motivo
O Hamlib deve ser tratado como uma integração externa e não como o núcleo da plataforma.

### Consequência
Será possível substituir ou complementar o Hamlib por outros backends no futuro sem redesenhar todo o sistema.

---

## ADR-002 — Compatibilidade CAT como camada de borda
**Data:** 2026-08-07

### Decisão
A emulação CAT será implementada no GADX Bridge como camada de compatibilidade com programas como N1MM e DXLog.

### Motivo
Permitir que softwares existentes enxerguem o rádio remoto como se fosse um rádio local suportado.

### Consequência
O núcleo GADX não dependerá de um protocolo CAT específico.

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
Cada site físico terá seu próprio GADX Gateway.

### Sites iniciais
- Guatupê
- Purunã
- Casa 68
- Estação de satélite

### Consequência
Cada Gateway torna-se autoridade local sobre seus recursos e sessões.
