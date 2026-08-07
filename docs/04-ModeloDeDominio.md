# GADX Vector
# 04 - Modelo de Domínio

Versão: 1.0  
Status: Draft

---

# Objetivo

Este documento define o modelo de domínio do GADX Vector.

Seu objetivo é estabelecer quais entidades existem dentro da plataforma, como elas se relacionam e quais responsabilidades possuem.

Este documento **não** define protocolos, APIs ou detalhes de implementação. Essas definições encontram-se nos documentos posteriores.

---

# Filosofia

No GADX Vector, equipamentos físicos não são controlados diretamente. Todos os equipamentos são abstraídos como **Recursos (Resources)**, acessados por meio de **Drivers** e manipulados através do Modelo de Domínio.

Um rádio, um rotor, um amplificador, uma câmera IP ou um WebSDR são recursos controláveis.

O Vector Gateway não trabalha diretamente com equipamentos. Ele trabalha com Recursos e utiliza Drivers para integrar tecnologias específicas.

Essa decisão torna a plataforma independente do hardware utilizado e permite sua evolução para novos tipos de equipamentos sem alterar a arquitetura central.

---

# Hierarquia Geral

```text
Site
 |
 ├── Gateway
 |
 ├── Resources
 |      |
 |      ├── Radio
 |      ├── Rotor
 |      ├── Amplifier
 |      ├── Antenna Switch
 |      ├── Power Controller
 |      ├── Camera
 |      ├── Audio Device
 |      └── ...
 |
 └── Sessions
        |
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

## Atributos conceituais

- `id`
- `name`
- `description`
- `location`
- `grid_locator`
- `timezone`
- `status`
- `capabilities`
- `resources`

---

# Resource

Entidade base para qualquer equipamento ou serviço controlável dentro da plataforma.

Todos os equipamentos controláveis devem ser representados por uma especialização de Resource.

## Atributos conceituais

- `id`
- `name`
- `type`
- `manufacturer`
- `model`
- `status`
- `online`
- `availability`
- `current_operator`
- `gateway`
- `capabilities`

---

# Radio

Especialização de Resource que representa um transceptor ou receptor controlável.

## Estados iniciais

- `ONLINE`
- `OFFLINE`
- `ERROR`
- `BUSY`
- `LOCKED`
- `MAINTENANCE`

## Capacidades possíveis

- Frequency
- Mode
- Split
- PTT
- CW
- Voice
- AM
- FM
- USB
- LSB
- RTTY
- Data
- Satellite

A presença de uma capacidade deve ser anunciada pelo próprio recurso, evitando pressupor que todos os rádios suportam todas as funções.

---

# Rotor

Especialização de Resource que representa um sistema de rotação de antena.

## Capacidades possíveis

- Azimuth
- Elevation
- Preset
- Tracking
- Stop

---

# Amplifier

Especialização de Resource que representa um amplificador de RF.

## Capacidades possíveis

- Power On
- Power Off
- Standby
- Operate
- Band
- Output Power
- Temperature
- Fault State

---

# Antenna Switch

Especialização de Resource responsável por seleção e roteamento de antenas ou caminhos de RF.

## Capacidades possíveis

- Select Port
- Current Port
- Lock
- Interlock

---

# Power Controller

Especialização de Resource para controle de alimentação elétrica ou dispositivos auxiliares.

## Capacidades possíveis

- Power On
- Power Off
- Restart
- Voltage
- Current
- Fault State

---

# Audio Device

Representa dispositivos ou serviços relacionados a áudio de operação.

Exemplos:

- Sound Card
- Remote Audio
- Voice Keyer

---

# Camera

Representa dispositivos de monitoramento visual da estação.

Pode representar:

- Webcam
- Câmera IP
- PTZ

---

# Operator

Representa um operador autenticado na plataforma.

## Atributos conceituais

- `id`
- `callsign`
- `name`
- `permissions`
- `active_sessions`

---

# Session

Representa uma conexão autenticada entre um operador e um Vector Gateway.

Uma sessão pode solicitar e controlar múltiplos recursos conforme permissões e políticas de acesso.

## Estados iniciais

- `CREATED`
- `CONNECTED`
- `AUTHENTICATED`
- `ACTIVE`
- `DISCONNECTED`
- `TIMEOUT`
- `REVOKED`

---

# Vector Gateway

Representa o serviço Vector instalado em um Site.

É responsável por:

- autenticação;
- autorização;
- gerenciamento de sessões;
- publicação e descoberta de recursos;
- manutenção de estado;
- gerenciamento de ownership;
- integração com Drivers;
- aplicação de políticas e interlocks.

O Vector Gateway não deve controlar equipamentos diretamente quando existir uma camada de Driver apropriada.

---

# Driver

Camada responsável por integrar o Vector Gateway com tecnologias e protocolos específicos.

Exemplos futuros:

- Hamlib Driver
- FlexRadio Driver
- Kenwood CAT Driver
- Icom CI-V Driver
- Yaesu CAT Driver
- Rotor Driver
- Amplifier Driver
- Simulator Driver

Um Driver traduz operações do Modelo de Domínio para a tecnologia específica e converte estados externos de volta para o domínio Vector.

---

# Vector Client

Aplicação utilizada pelo operador para acessar a plataforma.

Responsabilidades iniciais:

- interface Web local;
- autenticação do operador;
- seleção de Site;
- seleção e aquisição de recursos;
- comunicação com Vector Gateway;
- COM virtual;
- emulação CAT;
- compatibilidade com N1MM, DXLog e outros softwares externos.

---

# Capabilities

Capabilities descrevem o que um Resource consegue fazer.

O sistema não deve presumir funções apenas com base no tipo do equipamento.

Exemplo:

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

Isso permite que diferentes equipamentos do mesmo tipo apresentem conjuntos diferentes de recursos suportados.

---

# Ownership e Reserva de Recursos

Todo Resource controlável deve possuir um estado de disponibilidade e uma política clara de ownership.

Estados conceituais iniciais:

- `FREE`
- `RESERVED`
- `IN_USE`
- `ADMIN_LOCK`
- `MAINTENANCE`

O ownership é temporário e vinculado a uma Session.

A perda da Session deve provocar uma política segura de liberação ou recuperação do Resource.

---

# Relações entre Recursos

Recursos podem possuir dependências entre si.

Exemplo:

```text
Radio 1
  |
  ├── Amplifier 1
  ├── Antenna Switch 1
  └── Rotor 1
```

Essas relações permitem que o Vector futuramente aplique automações e interlocks.

Exemplos:

- impedir troca de antena durante PTT;
- impedir movimento de rotor além de limites configurados;
- selecionar automaticamente a banda do amplificador;
- bloquear dois rádios de utilizarem simultaneamente o mesmo caminho de RF.

---

# Estado Desejado e Estado Observado

Sempre que possível, o domínio deve distinguir:

- **Desired State** — estado solicitado pelo operador ou automação;
- **Observed State** — estado efetivamente observado no equipamento.

Exemplo:

```text
Desired Frequency: 14.074.000 Hz
Observed Frequency: 14.074.000 Hz
```

Essa distinção será importante para equipamentos remotos, latência de rede, falhas de comunicação e confirmação de comandos.

---

# Eventos de Domínio

Mudanças relevantes no estado dos Resources devem gerar eventos.

Exemplos:

- `FrequencyChanged`
- `ModeChanged`
- `PTTChanged`
- `ResourceAcquired`
- `ResourceReleased`
- `ResourceOffline`
- `RotorMoved`
- `AmplifierFault`
- `CameraOffline`
- `SessionExpired`

A especificação formal dos eventos será definida em documento próprio.

---

# Princípios do Modelo de Domínio

1. Equipamentos físicos são abstraídos como Resources.
2. Integrações específicas são encapsuladas em Drivers.
3. Capabilities descrevem funcionalidades suportadas.
4. Sessions representam conexões de operadores.
5. Ownership define quem pode comandar um Resource.
6. Mudanças relevantes produzem eventos de domínio.
7. O domínio é independente de Hamlib, CAT, fabricantes e sistemas operacionais.
8. Protocolos e APIs manipulam entidades do domínio e não hardware diretamente.

---

# Regra Central

> **No GADX Vector, equipamentos físicos não são controlados diretamente. Todos os equipamentos são abstraídos como Resources, acessados por meio de Drivers e manipulados através do Modelo de Domínio.**

Todo protocolo, API, interface ou automação do GADX Vector deve respeitar esta regra.
