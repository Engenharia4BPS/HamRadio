# GADX Vector
# 04 - Modelo de Domínio

Versão: 1.0  
Status: Draft

---

# Objetivo

Este documento define o modelo conceitual do GADX Vector: quais entidades existem, como se relacionam e quais responsabilidades possuem.

Este documento não redefine contratos normativos posteriores. Estados e transições são definidos em `06-MaquinaDeEstados.md`; mensagens em `05-Protocolo.md`; API em `07-API.md`; Drivers em `08-Drivers.md`; detalhamento de Resources em `09-ModeloDeRecursos.md`.

---

# Filosofia

Equipamentos físicos não são controlados diretamente pelo núcleo. Eles são abstraídos como **Resources**, acessados por meio de **Drivers** e manipulados através do Modelo de Domínio.

Um rádio, rotor, amplificador, câmera, sensor ou serviço pode ser representado como Resource quando fizer sentido operacional.

---

# Hierarquia Geral

```text
Site
├── Vector Gateway
├── Resources
│   ├── Radio
│   ├── Rotor
│   ├── Amplifier
│   ├── Antenna
│   ├── AntennaSwitch
│   ├── PowerController
│   ├── Camera
│   ├── AudioDevice
│   └── ...
└── Sessions
    └── Operators
```

---

# Site

Representa uma estação física controlada pelo GADX Vector.

Exemplos iniciais:
- Purunã
- Guatupê
- Casa 68
- Estação de Satélite

Atributos conceituais:
- `id`
- `name`
- `description`
- `location`
- `gridLocator`
- `timezone`
- `status`
- `resources`

Cada Site possui um Vector Gateway como autoridade local.

---

# Resource

Entidade base para equipamento, dispositivo ou serviço controlável/monitorável.

Atributos conceituais:
- `id`
- `name`
- `type`
- `siteId`
- `manufacturer`
- `model`
- `state`
- `health`
- `capabilities`
- `lease`
- `properties`

Os estados normativos de Resource são definidos exclusivamente em `06-MaquinaDeEstados.md`.

---

# Radio

Especialização de Resource para transceptor ou receptor.

Capabilities possíveis incluem:
- Frequency
- Mode
- Split
- PTT
- VFO
- Power
- Filter

USB, LSB, CW, DIGI, AM, FM e equivalentes são valores/modos operacionais, não estados base do Resource.

---

# Rotor

Especialização de Resource para sistema de rotação.

Capabilities possíveis:
- Azimuth
- Elevation
- Preset
- Tracking
- Stop
- Park

---

# Amplifier

Especialização de Resource para amplificador de RF.

Capabilities possíveis:
- Operate
- Standby
- Band
- Output Power
- Temperature
- SWR
- Fault

---

# Antenna e AntennaSwitch

**Antenna** representa a antena como entidade operacional, inclusive quando passiva, permitindo modelar banda, direção e dependências.

**AntennaSwitch** representa seleção e roteamento de caminhos de RF e pode oferecer SelectPort, Lock e Interlock.

---

# PowerController, Relay, Sensor, AudioDevice e Camera

Esses tipos representam, respectivamente, controle/telemetria elétrica, relés, sensores, áudio e monitoramento visual.

Seu contrato detalhado encontra-se em `09-ModeloDeRecursos.md`.

---

# Operator

Representa um operador autenticável/autorizável.

Atributos conceituais:
- `id`
- `callsign`
- `name`
- `roles`
- `permissions`

---

# Session

Contexto autenticado entre Operator/Client e Vector Gateway.

Uma Session pode adquirir Resources conforme permissões e políticas.

Os estados normativos da Session são definidos em `06-MaquinaDeEstados.md` e não devem ser duplicados neste documento.

---

# Lease e Ownership

**Lease** é a concessão temporária de controle de um Resource a uma Session.

**Ownership** identifica qual Session possui o direito corrente de controle.

Resources que exigem exclusividade possuem no máximo um Lease exclusivo de controle por vez, conforme ADR-010.

Observadores somente leitura podem existir quando permitidos pela política do Resource.

---

# Vector Gateway

Serviço instalado em um Site e responsável por:
- autenticação e autorização;
- Sessions e Leases;
- Resource Registry/Manager;
- estado autoritativo;
- políticas e interlocks;
- integração com Drivers;
- auditoria e health.

O Gateway não controla hardware diretamente quando existir Driver apropriado.

---

# Driver

Camada que traduz operações e estados entre o domínio Vector e backend/hardware específico.

Exemplos:
- Hamlib Driver
- Rotor Driver
- Amplifier Driver
- Simulator Driver

Na v1, o backend oficial de Radio é Hamlib, preferencialmente via `rigctld`, acessado pelo Hamlib Driver.

---

# Vector Client

Componente do operador responsável por:
- interface Web local;
- autenticação;
- seleção de Site e Resource;
- aquisição/liberação de Lease;
- comunicação via Vector Protocol;
- serviço local nativo;
- COM virtual;
- emulação CAT;
- compatibilidade com N1MM Logger+ e DXLog.

---

# Capabilities

Capabilities descrevem o que um Resource efetivamente consegue fazer.

O sistema não deve presumir funções apenas pelo tipo ou modelo.

```text
Radio
├── Frequency
├── Mode
├── Split
└── PTT

Rotor
├── Azimuth
└── Elevation
```

A Capability anunciada pelo Gateway é a referência funcional para Clients.

---

# Relações e Dependencies

Resources podem depender uns dos outros.

```text
Radio 1
├── Amplifier 1
├── AntennaSwitch 1
└── Rotor 1
```

Essas relações permitem políticas/interlocks como:
- impedir troca de antena durante PTT;
- bloquear caminhos de RF incompatíveis;
- limitar movimento de rotor;
- coordenar banda do amplificador.

---

# Desired, Observed e Authoritative State

- **Desired State** — estado solicitado.
- **Observed State** — estado efetivamente observado pelo Driver/backend/hardware.
- **Authoritative State** — estado reconhecido e publicado pelo Gateway.

```text
Client solicita
      ↓
Gateway valida
      ↓
Driver executa
      ↓
Hardware/backend confirma
      ↓
Gateway publica estado autoritativo
```

Quando não houver confirmação técnica suficiente, o sistema não deve apresentar estado inferido como confirmado.

---

# Eventos de Domínio

Mudanças relevantes produzem eventos, por exemplo:
- `FrequencyChanged`
- `ModeChanged`
- `PTTChanged`
- `ResourceAcquired`
- `ResourceReleased`
- `ResourceOffline`
- `LeaseExpired`
- `FaultRaised`

A especificação das mensagens pertence ao Vector Protocol.

---

# Princípios do Modelo de Domínio

1. Equipamentos e serviços são abstraídos como Resources.
2. Integrações específicas são encapsuladas em Drivers.
3. Capabilities descrevem funcionalidades efetivamente disponíveis.
4. Sessions representam contextos autenticados.
5. Leases/Ownership governam controle exclusivo.
6. Mudanças relevantes produzem Events.
7. O domínio é independente de Hamlib, CAT, fabricantes e sistemas operacionais.
8. Protocolos e APIs manipulam domínio, não hardware diretamente.
9. O Gateway publica o estado autoritativo.
10. Estados normativos pertencem à Máquina de Estados, evitando definições concorrentes.

---

# Regra Central

> **No GADX Vector, equipamentos físicos não são controlados diretamente. Todos os equipamentos são abstraídos como Resources, acessados por meio de Drivers e manipulados através do Modelo de Domínio.**
