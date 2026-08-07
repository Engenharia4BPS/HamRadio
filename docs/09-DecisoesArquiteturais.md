# GADX Vector – Decisões Arquiteturais

Este documento registra decisões importantes para preservar o contexto técnico do projeto ao longo do tempo.

---

## ADR-001 — Protocolo interno independente do Hamlib
**Data:** 2026-08-07

### Decisão
O protocolo de comunicação entre **Vector Client** e **Vector Gateway** será próprio, identificado como **Vector Protocol**, e independente do Hamlib.

### Motivo
O Hamlib deve ser tratado como uma integração externa e não como o núcleo da plataforma.

### Consequência
Será possível substituir ou complementar o Hamlib por outros backends no futuro sem redesenhar todo o sistema.

---

## ADR-002 — Compatibilidade CAT como camada de borda
**Data:** 2026-08-07

### Decisão
A emulação CAT será implementada no **Vector Client** como camada de compatibilidade com programas como N1MM e DXLog.

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
Cada site físico terá seu próprio **Vector Gateway**.

### Sites iniciais
- Guatupê
- Purunã
- Casa 68
- Estação de satélite

### Consequência
Cada Vector Gateway torna-se autoridade local sobre seus recursos e sessões.

---

## ADR-005 — Nome oficial da plataforma: GADX Vector
**Data:** 2026-08-07

### Decisão
O nome oficial da plataforma será **GADX Vector**.

**GADX** identifica o **Grupo Araucária de DX**, organização responsável pelo desenvolvimento e manutenção do projeto. **Vector** identifica a plataforma de automação e operação remota de estações de rádio amador.

### Componentes oficiais
- Vector Gateway.
- Vector Client.
- Vector Protocol.
- Vector API.
- Vector SDK, quando aplicável.

### Motivo
O nome Vector remete a direção, azimute, trajetória e precisão, conceitos presentes no radioamadorismo, e também à engenharia por meio de vetores, direção e magnitude. É curto, facilmente pronunciável em português e inglês e adequado como marca de produto.

### Consequência
Documentação, código e novos componentes deverão usar **GADX Vector** para a plataforma e **Vector** como prefixo dos componentes do produto, evitando utilizar GADX isoladamente como nome da plataforma.
