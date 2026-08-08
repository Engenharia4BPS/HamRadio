# GADX Vector
# 11 - Roadmap

Versão: 1.0 (Draft)
Status: Planejamento

---

# Objetivo

Este documento define o roadmap de evolução do **GADX Vector**, organizando a implementação da plataforma em fases progressivas, com objetivos, dependências, entregáveis e critérios de saída claros.

O roadmap não substitui o `10-Backlog.md`. O backlog descreve **o que precisa ser feito**; este documento descreve **em que ordem a plataforma deverá evoluir**.

---

# Princípios do Roadmap

1. Entregar valor de forma incremental.
2. Validar os maiores riscos técnicos primeiro.
3. Priorizar compatibilidade real com N1MM e DXLog.
4. Utilizar Hamlib/`rigctld` como backend oficial de rádio da versão 1.
5. Manter API, protocolo e domínio independentes do backend.
6. Segurança operacional deve existir desde a primeira prova de conceito que permita transmissão.
7. Nenhuma fase avança sem seus critérios mínimos de saída atendidos.
8. O primeiro QSO remoto é um marco técnico e operacional, não apenas simbólico.

---

# Visão Geral

```text
F0  Fundação Arquitetural
        ↓
F1  Prova de Conceito CAT / COM
        ↓
F2  Hamlib Driver / rigctld
        ↓
F3  Vector Gateway Core
        ↓
F4  Vector Client
        ↓
F5  Integração N1MM / DXLog
        ↓
M5  Primeiro QSO Remoto
        ↓
F6  Segurança e Operação Assistida
        ↓
F7  Multi-Rádio / Multi-Site
        ↓
M6  Primeiro Contest
        ↓
F8  Expansão de Resources
        ↓
F9  Automação Avançada
```

---

# Milestones Oficiais

| ID | Milestone | Resultado esperado |
|---|---|---|
| M1 | Gateway operacional | Vector Gateway executando e gerenciando Resources |
| M2 | Hamlib funcional | Rádio físico controlado através do Hamlib Driver/`rigctld` |
| M3 | Vector Client operacional | Client conectado ao Gateway e controlando Resource remoto |
| M4 | N1MM/DXLog compatíveis | Logger controla o rádio remoto através da COM virtual |
| M5 | Primeiro QSO remoto | QSO completo realizado pelo GADX Vector |
| M6 | Primeiro Contest | Operação real de contest utilizando Vector |
| M7 | Primeira DXpedition | Uso do Vector em cenário operacional externo ou DXpedition |

---

# Fase 0 — Fundação Arquitetural

## Objetivo

Concluir a base conceitual necessária para implementar a plataforma sem acoplamentos prematuros.

## Entregáveis

- Visão Geral.
- Escopo.
- Premissas.
- Arquitetura.
- Modelo de Domínio.
- Vector Protocol.
- Máquina de Estados.
- Vector API.
- Drivers.
- Modelo de Resources.
- Backlog.
- Roadmap.
- ADRs.
- Glossário.

## Critério de saída

A equipe deve conseguir responder, sem ambiguidade:

- O que é o Vector?
- Quem é Client e quem é Gateway?
- Como uma sessão funciona?
- Como um Resource é adquirido?
- Como comandos e eventos trafegam?
- Como hardware é abstraído?
- Qual backend será utilizado na versão 1?

---

# Fase 1 — Prova de Conceito CAT / COM Virtual

## Objetivo

Eliminar o primeiro grande risco técnico: provar que N1MM e DXLog conseguem controlar um rádio virtual local apresentado pelo Vector Client.

## Escopo

- Criar porta COM virtual.
- Implementar emulador CAT mínimo.
- Selecionar o modelo CAT inicial usado como fachada do Vector.
- Implementar leitura de frequência.
- Implementar escrita de frequência.
- Implementar leitura de modo.
- Implementar PTT mínimo, inicialmente em ambiente controlado.

## Spike obrigatório

**SPIKE-002 — Seleção do modelo CAT de emulação.**

O TS-2000 permanece candidato, mas a escolha deverá ser validada contra:

- N1MM.
- DXLog.
- simplicidade do protocolo CAT;
- cobertura de funções necessárias;
- estabilidade de polling;
- comportamento diante de comandos não suportados.

## Critério de saída

- N1MM reconhece a COM virtual como rádio suportado.
- DXLog reconhece a COM virtual como rádio suportado.
- Alterar frequência no logger altera o estado do emulador.
- Alterar estado no emulador é refletido no logger.
- Nenhum rádio físico é necessário para concluir esta fase.

---

# Fase 2 — Hamlib Driver / rigctld

## Objetivo

Conectar o modelo interno do Vector a um rádio físico real através do backend oficial da v1.

## Backend oficial

```text
Vector Domain
    ↓
Hamlib Driver
    ↓
rigctld
    ↓
Hamlib
    ↓
Rádio físico
```

## Entregáveis

- Conexão TCP com `rigctld`.
- Health check.
- Reconexão automática.
- Leitura de frequência.
- Escrita de frequência.
- Leitura e escrita de modo.
- PTT ON/OFF.
- Split, quando suportado.
- VFO, quando suportado.
- Leitura de capabilities.
- Tradução de erros Hamlib → erros Vector.
- Polling do estado observado.
- Dummy Driver para desenvolvimento e testes.

## Segurança mínima

A partir desta fase, qualquer teste envolvendo TX deverá obedecer às regras de fail-safe definidas no Vector Protocol e na Máquina de Estados.

## Critério de saída

- Um comando do domínio Vector altera um rádio real via `rigctld`.
- Alterações feitas diretamente no rádio são percebidas pelo Driver e refletidas no estado observado.
- PTT OFF é garantido em perda de comunicação crítica.

### Milestone

**M2 — Hamlib funcional**.

---

# Fase 3 — Vector Gateway Core

## Objetivo

Transformar a prova de conceito local em um serviço de estação capaz de concentrar e governar Resources.

## Entregáveis

- Inicialização e configuração do Gateway.
- Driver Manager.
- Resource Registry.
- Resource Manager.
- Session Manager.
- Lease Manager.
- Heartbeat.
- Event Bus interno.
- Logging estruturado.
- Auditoria.
- Health endpoints.
- Configuração de múltiplos radios.
- Persistência mínima de configuração.

## Critério de saída

- Gateway inicia de forma autônoma.
- Detecta/configura Resources.
- Mantém estado autoritativo.
- Concede e revoga leases.
- Controla rádio através do Hamlib Driver.
- Recupera-se de desconexão temporária de `rigctld`.

### Milestone

**M1 — Gateway operacional**.

---

# Fase 4 — Vector Client

## Objetivo

Criar o componente instalado no computador do operador.

## Entregáveis

- Serviço local do Vector Client.
- Interface Web local.
- Login.
- Configuração de Gateways.
- Seleção de Site.
- Seleção de Resource.
- Aquisição/liberação de lease.
- Visualização do estado do rádio.
- COM virtual.
- Emulação CAT integrada.
- Vector Protocol Client.
- Reconexão automática.
- Session Resume.

## Critério de saída

Um operador deve conseguir, utilizando apenas o Vector Client:

1. conectar a um Gateway;
2. autenticar;
3. selecionar um rádio;
4. adquirir o Resource;
5. visualizar frequência/modo;
6. alterar frequência;
7. liberar o Resource.

### Milestone

**M3 — Vector Client operacional**.

---

# Fase 5 — Integração N1MM / DXLog

## Objetivo

Fechar o ciclo original que motivou o projeto: permitir que softwares de contest controlem remotamente o rádio como se ele estivesse conectado localmente.

## Fluxo alvo

```text
N1MM / DXLog
      ↓
COM Virtual
      ↓
CAT Emulator
      ↓
Vector Client
      ↓
Vector Protocol
      ↓
Vector Gateway
      ↓
Hamlib Driver
      ↓
rigctld
      ↓
Rádio físico
```

## Testes mínimos

- Polling contínuo de frequência.
- Mudança de banda.
- Mudança de modo.
- PTT.
- Split.
- VFO, se necessário ao logger.
- Reconexão do logger.
- Reinício do Client.
- Reinício do Gateway.
- Perda temporária de rede.

## Critério de saída

N1MM e DXLog devem operar sem conhecer a existência de Hamlib, `rigctld`, Gateway ou rede remota.

### Milestone

**M4 — Compatibilidade N1MM/DXLog**.

---

# Milestone 5 — Primeiro QSO Remoto

Este milestone deverá receber tratamento especial.

## Objetivo

Realizar um QSO real utilizando o fluxo completo do Vector.

## Critérios

- Operador autenticado.
- Rádio adquirido por lease.
- Frequência controlada pelo logger.
- PTT controlado através do Vector.
- Comunicação de áudio disponível por solução definida para o teste.
- Logs de auditoria preservados.
- Fail-safe validado antes da transmissão.

## Registro recomendado

Registrar:

- data/hora UTC;
- operador;
- callsign trabalhado;
- banda;
- modo;
- Site utilizado;
- rádio;
- versão do Client;
- versão do Gateway;
- versão Hamlib;
- latência observada;
- eventuais problemas encontrados.

---

# Fase 6 — Segurança e Operação Assistida

## Objetivo

Levar o sistema de prova operacional para um nível adequado a uso regular por membros do grupo.

## Entregáveis

- WSS/TLS obrigatório.
- Gestão segura de credenciais.
- Session Tokens.
- Expiração e revogação.
- Perfis Administrator/Operator/Guest/Monitor.
- Auditoria centralizada.
- Bloqueio administrativo de Resource.
- Aprovação local opcional.
- Fail-safe de TX.
- Rate limiting.
- Alertas operacionais.

## Critério de saída

Nenhuma operação de transmissão pode ocorrer fora de uma sessão autenticada, autorizada e com lease válido.

---

# Fase 7 — Multi-Rádio e Multi-Site

## Objetivo

Escalar o Vector para a topologia real do Grupo Araucária de DX.

## Sites iniciais

- Guatupê.
- Purunã.
- Casa 68.
- Estação de Satélite.

## Entregáveis

- Cadastro de múltiplos Gateways.
- Discovery de Sites.
- Múltiplos Resources por Site.
- Seleção de rádio.
- Políticas por Site.
- Status agregado.
- Resource Profiles.
- Configuração independente por estação.

## Critério de saída

O mesmo Vector Client deve ser capaz de selecionar diferentes Sites e Resources sem reconfigurar N1MM/DXLog além da COM virtual previamente definida.

---

# Milestone 6 — Primeiro Contest

## Objetivo

Utilizar o GADX Vector durante um contest real, inicialmente em escopo controlado.

## Estratégia recomendada

Primeiro teste:

- um operador;
- um rádio;
- uma banda ou período controlado;
- operador local de contingência disponível.

## Métricas

- tempo total de operação;
- número de QSOs;
- desconexões;
- reconexões automáticas;
- latência média;
- falhas CAT;
- falhas de PTT;
- incidentes de lease;
- intervenção manual necessária.

---

# Fase 8 — Expansão de Resources

## Objetivo

Expandir o Vector além do controle de rádio.

## Resources previstos

- Rotor.
- Amplifier.
- Antenna.
- AntennaSwitch.
- Relay.
- Sensor.
- PowerController.
- AudioDevice.
- Camera.

## Integrações candidatas

- Rotor Genius.
- PST Rotator.
- amplificadores via rede/serial.
- relés IP.
- câmeras IP.
- sensores ambientais.
- monitoramento de energia.

## Critério de saída

Novos Resources devem ser adicionados através do Driver Framework sem exigir alteração estrutural no Vector Protocol ou na Vector API.

---

# Fase 9 — Automação Avançada

## Objetivo

Evoluir o Vector de plataforma de operação remota para plataforma de automação de estação.

## Possibilidades

- seleção automática de antena por banda;
- movimentação automática de rotor;
- intertravamentos de amplificador;
- automação de TX/RX;
- perfis de contest;
- profiles por operador;
- sequenciamento seguro de estação;
- integração com cluster DX;
- integração com BandWatch/DXHunter;
- integração WSJT-X;
- integração Log4OM;
- automação de satélites;
- telemetria e dashboards históricos.

---

# Fase 10 — Escala e Ecossistema

## Objetivo

Preparar a plataforma para integrações externas e crescimento além dos primeiros Sites.

## Possibilidades

- Vector SDK.
- API pública controlada.
- plugins.
- Drivers de terceiros.
- catálogo de Resource Profiles.
- integração OpenID Connect.
- MFA/passkeys.
- observabilidade centralizada.
- atualização coordenada de Gateways e Clients.

---

# Dependências Principais

```text
Modelo de Domínio
      ↓
Vector Protocol
      ↓
Máquina de Estados
      ↓
Driver Framework
      ↓
Hamlib Driver
      ↓
Gateway Core
      ↓
Vector Client
      ↓
COM/CAT
      ↓
N1MM / DXLog
```

A implementação poderá ocorrer parcialmente em paralelo, mas nenhuma camada deverá depender de detalhes internos da camada abaixo além de seu contrato público.

---

# Critérios de Go / No-Go

Antes de avançar para operação real com TX, deverão estar validados:

- autenticação;
- autorização;
- lease exclusivo;
- heartbeat;
- fail-safe;
- PTT OFF em falha;
- estado autoritativo no Gateway;
- auditoria;
- reconexão;
- comportamento do Hamlib Driver diante de erro.

Falha em qualquer item crítico implica **No-Go para TX remoto**.

---

# Métricas de Evolução

O projeto deverá acompanhar pelo menos:

- cobertura de testes;
- taxa de reconexão bem-sucedida;
- latência Client ↔ Gateway;
- latência comando ↔ hardware;
- número de Resources suportados;
- número de modelos de rádio validados;
- tempo médio entre falhas;
- incidentes de segurança operacional;
- compatibilidade N1MM/DXLog;
- estabilidade em sessões longas.

---

# Política de Versões

## 0.x

Provas de conceito e desenvolvimento interno.

## 0.5

Gateway + Hamlib + Client funcionando em laboratório.

## 0.7

N1MM/DXLog funcionando de ponta a ponta.

## 0.9

Operação remota real controlada pelo GADX.

## 1.0

Versão considerada estável quando:

- primeiro QSO remoto validado;
- primeiro contest controlado concluído;
- segurança obrigatória implementada;
- pelo menos dois Sites validados;
- documentação operacional existente;
- procedimentos de recuperação testados.

---

# Relação com o Backlog

O `10-Backlog.md` é a fonte de tarefas e histórias.

Este roadmap é a fonte da sequência estratégica.

Uma mudança de prioridade no backlog não deve alterar automaticamente a arquitetura ou a ordem das fases críticas deste roadmap.

Mudanças estruturais relevantes deverão ser registradas em ADR.

---

# Objetivo Final

O roadmap deve conduzir o GADX Vector de uma prova de conceito de CAT remoto até uma plataforma confiável de automação e operação remota multiestação.

A evolução deverá preservar sempre os princípios centrais:

> **O Client solicita. O Gateway decide. O Driver executa. O hardware confirma. O Gateway publica o estado autoritativo.**

E, para qualquer operação crítica:

> **Segurança da estação tem prioridade sobre continuidade da operação.**
