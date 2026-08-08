# GADX Vector
# 10 - Backlog

Versão: 1.1 (Draft)

---

# Objetivo

Este documento representa o Product Backlog oficial do GADX Vector.

Seu objetivo é organizar toda a evolução funcional e técnica da plataforma, permitindo planejamento, priorização e rastreabilidade.

---

# Filosofia

O Backlog é organizado por:

- Épicos
- User Stories
- Technical Stories
- Spikes
- Débito Técnico
- Ideias Futuras

Toda funcionalidade deverá estar vinculada a um Épico.

---

# Prioridades

| Prioridade | Significado |
|------------|-------------|
| P0 | Bloqueia o desenvolvimento |
| P1 | Essencial para o MVP |
| P2 | Necessário para a versão 1.0 |
| P3 | Melhoria planejada |
| P4 | Ideia futura / Pesquisa |

---

# Milestones

| ID | Objetivo |
|----|----------|
| M1 | Gateway operacional |
| M2 | Driver Hamlib funcional |
| M3 | Vector Client operacional |
| M4 | Compatibilidade N1MM/DXLog |
| M5 | Primeiro QSO remoto |
| M6 | Primeiro Contest |
| M7 | Primeira DXpedition utilizando o Vector |

---

# MVP

## Gateway

- Inicialização
- Configuração
- Driver Manager
- Session Manager
- Resource Manager
- Health Check

## Drivers

- Driver Interface
- Hamlib Driver usando `rigctld` como backend preferencial
- Dummy Driver

## Client

- Login
- Seleção de Site
- Seleção de Rádio
- Interface Web
- COM Virtual
- CAT Adapter
- Keying Adapter para RTS/DTR

## Protocol

- Authenticate
- Heartbeat
- Lease
- Frequency
- Mode
- PTT

---

# Épicos

## EPIC-001 — Gateway Core

Prioridade: P0

### Stories

- Inicialização
- Configuração
- Logging
- Driver Manager
- Health Check

---

## EPIC-002 — Driver Framework

Prioridade: P0

### Stories

- Interface de Drivers
- Hamlib Driver
- Integração do Hamlib Driver com `rigctld`
- Dummy Driver

---

## EPIC-003 — Session Manager

Prioridade: P1

### Stories

- Login
- Logout
- Lease
- Heartbeat
- Session Resume

---

## EPIC-004 — Resource Manager

Prioridade: P1

### Stories

- Registro de Resources
- Discovery
- Ownership
- Capabilities

---

## EPIC-005 — Segurança

Prioridade: P1

### Stories

- TLS
- Tokens
- Auditoria
- Perfis de acesso

---

## EPIC-006 — Vector Client

Prioridade: P1

### Stories

- Interface Web
- Seleção de Site
- Seleção de Resource
- Monitoramento
- CAT Adapter local
- Keying Adapter local

---

## EPIC-007 — COM Virtual / Compatibilidade Legada

Prioridade: P0

### Stories

- Integração nativa de COM virtual
- Emulação CAT TS-2000
- Porta dedicada de Keying quando exigida pelo logger
- Captura de DTR para PTT
- Captura de RTS para CW
- Compatibilidade N1MM
- Compatibilidade DXLog

---

## EPIC-008 — Interface Web

Prioridade: P2

### Stories

- Dashboard
- Recursos
- Eventos
- Logs

---

## EPIC-009 — Resource Discovery

Prioridade: P2

### Stories

- Descoberta automática
- Profiles
- Capabilities

---

## EPIC-010 — Multi Site

Prioridade: P2

### Stories

- Guatupê
- Purunã
- Casa 68
- Estação Satélite

---

# User Stories

## US-001

Como operador, quero selecionar um Site para controlar seus Resources.

## US-002

Como operador, quero reservar um Rádio para evitar conflitos de operação.

## US-003

Como operador, quero alterar frequência para operar remotamente.

## US-004

Como administrador, quero bloquear um Resource para manutenção.

## US-005

Como operador, quero reconectar automaticamente após perda temporária da conexão.

---

# Technical Stories

## TS-001
Implementar Driver Interface.

## TS-002
Implementar Heartbeat.

## TS-003
Implementar Lease Manager.

## TS-004
Implementar Resource Discovery.

## TS-005
Implementar Session Resume.

## TS-006
Promover a fachada CAT TS-2000 validada no SPIKE-002 para um CAT Adapter do Vector Client.

## TS-007
Promover o monitoramento RTS/DTR validado no SPIKE-002 para um Keying Adapter do Vector Client.

---

# Spikes

## SPIKE-001
Validar a integração oficial Hamlib Driver + `rigctld`, incluindo comandos, polling, erros, capabilities e comportamento de reconexão.

Status: Planejado.

## SPIKE-002
Escolher e validar o modelo CAT utilizado pela COM Virtual e investigar a interface local de Keying.

Status: **Em fase final — N1MM validado com sucesso; DXLog pendente.**

Resultados já comprovados no N1MM:

- fachada CAT Kenwood TS-2000 aceita;
- polling CAT estável;
- frequência bidirecional;
- modos USB/LSB/CW;
- VFO A/B;
- Split com RX e TX em VFOs distintos;
- PTT via DTR em porta serial dedicada;
- CW keying via RTS em porta serial dedicada;
- pulsos de CW capturados com timing coerente e suficientes para reconstrução da mensagem transmitida.

Referência: `14-Spike-TS2000-CAT.md`.

## SPIKE-003
Avaliar transportes alternativos apenas para versões futuras, preservando WSS + JSON como decisão da v1 (ADR-011).

Status: Futuro.

## SPIKE-004
Avaliar suporte a mTLS.

Status: Futuro.

## SPIKE-005
Definir a estratégia de transporte/execução de CW remoto, medindo impacto de latência e jitter e decidindo se o timing crítico deve residir no Gateway ou em keyer dedicado próximo ao hardware.

Status: Planejado após o encerramento do SPIKE-002.

---

# Débito Técnico / Pesquisas Futuras

- Avaliar Protobuf para versões futuras.
- Avaliar QUIC para versões futuras.
- Avaliar tecnologia de persistência/banco de dados.
- Avaliar necessidade de cache distribuído quando houver escala que o justifique.

---

# Ideias Futuras

- Controle de WebSDR
- Cluster DX
- DXSpider
- Rotor Genius
- PST Rotator
- Satélites
- Voice Keyer
- CW Skimmer
- Band Decoder
- Estação Meteorológica
- Monitor de Energia
- Integração com Log4OM
- Integração com WSJT-X
- API pública para terceiros

---

# Definition of Done

Uma funcionalidade será considerada concluída somente quando:

- Código implementado.
- Testes executados.
- Revisão concluída.
- Documentação atualizada.
- Compatibilidade validada.
- Logs implementados.
- Auditoria implementada, quando aplicável.
- Segurança revisada.
- ADR atualizada, quando necessário.

---

# Rastreabilidade

| ID | Categoria | Status | Prioridade | Milestone |
|----|-----------|---------|------------|-----------|
| EPIC-001 | Gateway Core | Planejado | P0 | M1 |
| EPIC-002 | Driver Framework | Planejado | P0 | M2 |
| EPIC-003 | Session Manager | Planejado | P1 | M1 |
| EPIC-004 | Resource Manager | Planejado | P1 | M1 |
| EPIC-005 | Segurança | Planejado | P1 | M5 |
| EPIC-006 | Vector Client | Em preparação técnica | P1 | M3 |
| EPIC-007 | COM Virtual / Compatibilidade Legada | N1MM validado / DXLog pendente | P0 | M4 |
| EPIC-008 | Interface Web | Planejado | P2 | M3 |
| EPIC-009 | Resource Discovery | Planejado | P2 | M1 |
| EPIC-010 | Multi Site | Planejado | P2 | M6 |
| SPIKE-002 | CAT TS-2000 + Keying | N1MM SUCCESS / DXLog pendente | P0 | M4 |
| SPIKE-005 | CW remoto / timing | Planejado | P1 | M4 |

---

# Considerações Finais

O Backlog é um documento vivo.

Novas funcionalidades deverão ser adicionadas preservando rastreabilidade, priorização e organização por Épicos.

Decisões já formalizadas em ADR não devem permanecer como questões abertas no backlog; nesses casos, o backlog deve conter apenas atividades de validação ou implementação da decisão.
