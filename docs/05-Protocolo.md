# GADX Vector
# 05 - Vector Protocol

**Versão:** 1.0 (Draft)  
**Status:** Em elaboração

---

# Objetivo

O **Vector Protocol** define a comunicação entre o **Vector Client** e o **Vector Gateway**.

Seu objetivo é abstrair completamente o hardware físico, permitindo que qualquer cliente controle recursos da estação sem conhecer detalhes de implementação dos equipamentos.

O protocolo é orientado a comandos e eventos e permanece independente de fabricantes, protocolos CAT ou da Hamlib.

---

# Princípios

O Vector Protocol foi projetado seguindo os seguintes princípios:

- Independência de hardware.
- Independência da Hamlib.
- Comunicação bidirecional.
- Baixa latência.
- Segurança por padrão.
- Compatibilidade futura.
- Extensibilidade.
- Legibilidade.
- Auditabilidade.
- Estado autoritativo no Gateway.

---

# Transporte

A implementação oficial utiliza:

- **WebSocket Secure (WSS)**;
- sobre **TLS**;
- com mensagens codificadas em **JSON UTF-8**.

## Ambientes

- **Produção:** WSS obrigatório.
- **Laboratório/desenvolvimento:** WS permitido apenas mediante configuração explícita.

---

# Arquitetura

```text
N1MM / DXLog
     |
     v
Vector Client
     |
     v
Vector Protocol
     |
     v
Vector Gateway
     |
     v
Driver
     |
     v
Hamlib / outro backend
     |
     v
Equipamento físico
```

---

# Modelo de Comunicação

Toda comunicação ocorre através de mensagens.

Existem três categorias lógicas:

- **Command** — representa uma intenção do Client.
- **Event** — representa um fato ocorrido no Gateway ou Resource.
- **Error** — representa falha na execução ou validação de uma operação.

O **Vector Gateway é a fonte autoritativa do estado**. O Client solicita mudanças; o Gateway confirma o estado efetivamente aplicado por meio de eventos ou respostas correlacionadas.

---

# Envelope das Mensagens

Todas as mensagens do Vector Protocol utilizam o mesmo envelope lógico.

```json
{
  "version": "1.0",
  "messageId": "5f519d3a-e3d5-4ab3-b773-caf43c31e887",
  "correlationId": "0deed3ba-ad77-48d3-807c-e717cc92df7c",
  "timestamp": "2026-08-07T22:30:00Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "resourceId": "radio-01",
  "type": "Command",
  "name": "SetFrequency",
  "payload": {
    "frequencyHz": 14074000
  }
}
```

## Campos do envelope

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---:|---|
| `version` | string | Sim | Versão do Vector Protocol utilizada pela mensagem. |
| `messageId` | UUID/string | Sim | Identificador único da mensagem. Usado também para idempotência. |
| `correlationId` | UUID/string | Condicional | Relaciona resposta, evento ou erro ao comando que originou a operação. |
| `timestamp` | string ISO-8601 UTC | Sim | Data e hora de criação da mensagem em UTC. |
| `sessionId` | UUID/string | Condicional | Identificador da sessão autenticada. Não existe antes da autenticação inicial. |
| `resourceId` | string | Condicional | Identificador do Resource alvo ou origem da mensagem. |
| `type` | enum | Sim | `Command`, `Event` ou `Error`. |
| `name` | string | Sim | Nome semântico da operação ou evento. |
| `payload` | object | Sim | Dados específicos da mensagem. Pode ser `{}` quando não houver parâmetros. |

## Regras

- `messageId` DEVE ser único por mensagem.
- `timestamp` DEVE utilizar UTC.
- `correlationId` DEVE apontar para o `messageId` do comando original quando aplicável.
- Campos desconhecidos DEVEM ser ignoráveis por implementações compatíveis da mesma major version, salvo quando definidos como críticos em versão futura.
- Credenciais permanentes NÃO DEVEM fazer parte do envelope genérico.

---

# Handshake e Versionamento

Ao abrir a conexão, Client e Gateway devem negociar uma versão compatível do protocolo antes de permitir operação de Resources.

Exemplo conceitual:

```json
{
  "version": "1.0",
  "messageId": "6af8f7dc-1ec8-4687-b866-fca9bfaf4ac9",
  "timestamp": "2026-08-07T22:30:00Z",
  "type": "Command",
  "name": "Hello",
  "payload": {
    "client": "Vector Client",
    "clientVersion": "0.1.0",
    "supportedProtocolVersions": ["1.0"]
  }
}
```

O Gateway deverá responder informando a versão negociada e suas capacidades básicas.

---

# Autenticação

A autenticação ocorre somente após a criação de um canal TLS válido.

## Authenticate

Exemplo:

```json
{
  "version": "1.0",
  "messageId": "bb5b6d95-fd55-489d-83cb-4d1803639669",
  "timestamp": "2026-08-07T22:30:02Z",
  "type": "Command",
  "name": "Authenticate",
  "payload": {
    "username": "PY5XT",
    "password": "<credential-protected-by-TLS>"
  }
}
```

Após autenticação bem-sucedida, o Gateway devolve uma sessão e um token temporário.

```json
{
  "version": "1.0",
  "messageId": "6b679bb1-92f4-4c69-8605-144082feff64",
  "correlationId": "bb5b6d95-fd55-489d-83cb-4d1803639669",
  "timestamp": "2026-08-07T22:30:02Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "type": "Event",
  "name": "Authenticated",
  "payload": {
    "sessionToken": "<temporary-token>",
    "expiresInSeconds": 3600,
    "roles": ["Operator"]
  }
}
```

A forma final de apresentação do token no transporte será definida pela implementação de segurança, mas ele NÃO DEVE ser incluído em URLs ou logs.

---

# Sessões

Após autenticação, o Gateway cria uma sessão lógica.

Cada sessão possui, no mínimo:

- `sessionId`;
- usuário autenticado;
- roles/permissões;
- horário de criação;
- último heartbeat válido;
- estado;
- Resources adquiridos;
- expiração do token de sessão.

Estados previstos:

- `CREATED`
- `AUTHENTICATED`
- `ACTIVE`
- `DISCONNECTED`
- `TIMEOUT`
- `CLOSED`

---

# Resources e Lease

Resources controláveis são adquiridos através de **Lease**.

O Lease representa o direito temporário de controle exclusivo de um Resource.

## AcquireResource

```json
{
  "version": "1.0",
  "messageId": "8cb96274-481b-43c6-8e73-d284076351e7",
  "timestamp": "2026-08-07T22:30:05Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "resourceId": "radio-01",
  "type": "Command",
  "name": "AcquireResource",
  "payload": {}
}
```

Resposta/evento:

```json
{
  "version": "1.0",
  "messageId": "ca46a4da-0b36-48c3-93e2-70a58e57d5c5",
  "correlationId": "8cb96274-481b-43c6-8e73-d284076351e7",
  "timestamp": "2026-08-07T22:30:05Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "resourceId": "radio-01",
  "type": "Event",
  "name": "ResourceAcquired",
  "payload": {
    "leaseId": "5834a258-81d7-4561-acd2-019230198b6a",
    "leaseDurationSeconds": 30
  }
}
```

Enquanto existir Lease válido, outro operador não poderá controlar o mesmo Resource, salvo política administrativa explicitamente definida.

---

# Heartbeat e Política de Temporização

Heartbeat tem quatro objetivos principais:

- confirmar disponibilidade da sessão;
- medir latência;
- renovar Leases;
- detectar desconexões rapidamente.

## Defaults recomendados para Vector Protocol v1

| Parâmetro | Default | Observação |
|---|---:|---|
| `heartbeatIntervalSeconds` | 5 s | Intervalo sugerido entre Heartbeats do Client. |
| `heartbeatTimeoutSeconds` | 15 s | Após este período sem Heartbeat válido a sessão entra em estado degradado/timeout. |
| `leaseDurationSeconds` | 30 s | Duração inicial do Lease de Resource. |
| `leaseRenewal` | automático | Heartbeats válidos renovam os Leases ativos da sessão. |
| `sessionResumeWindowSeconds` | 30 s | Janela sugerida para tentativa de recuperação da sessão após perda transitória de conexão. |

Esses valores são **defaults**, não constantes do protocolo. O Gateway pode anunciar valores diferentes durante o handshake ou autenticação.

## Heartbeat

```json
{
  "version": "1.0",
  "messageId": "56dfdb42-376b-4a63-b632-b7dd962b0966",
  "timestamp": "2026-08-07T22:30:10Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "type": "Command",
  "name": "Heartbeat",
  "payload": {
    "sequence": 42
  }
}
```

Resposta:

```json
{
  "version": "1.0",
  "messageId": "fae33e8b-55a7-4888-a724-bd96dd999fcb",
  "correlationId": "56dfdb42-376b-4a63-b632-b7dd962b0966",
  "timestamp": "2026-08-07T22:30:10Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "type": "Event",
  "name": "HeartbeatAck",
  "payload": {
    "sequence": 42,
    "gatewayTime": "2026-08-07T22:30:10Z"
  }
}
```

---

# Snapshot e Sincronização de Estado

Após adquirir um Resource, o Gateway envia um **Snapshot** completo do estado conhecido.

Depois do Snapshot, o Gateway envia apenas eventos diferenciais de estado.

Exemplo conceitual para rádio:

```json
{
  "version": "1.0",
  "messageId": "94b0ad4f-22ae-436e-b594-40815a3176d0",
  "timestamp": "2026-08-07T22:30:06Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "resourceId": "radio-01",
  "type": "Event",
  "name": "StateSnapshot",
  "payload": {
    "online": true,
    "frequencyHz": 14074000,
    "mode": "USB",
    "ptt": false,
    "split": false
  }
}
```

---

# Comandos de Rádio

## SetFrequency

```json
{
  "version": "1.0",
  "messageId": "1d5afe0c-d8cf-4681-a5e0-f57a17d7f243",
  "timestamp": "2026-08-07T22:30:15Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "resourceId": "radio-01",
  "type": "Command",
  "name": "SetFrequency",
  "payload": {
    "frequencyHz": 14074000
  }
}
```

O Gateway somente confirma a alteração quando o backend/hardware confirmar ou quando a política do Driver determinar que o estado foi efetivamente aceito.

Evento:

```json
{
  "version": "1.0",
  "messageId": "1a42e528-1245-473d-b773-bc98215ca07c",
  "correlationId": "1d5afe0c-d8cf-4681-a5e0-f57a17d7f243",
  "timestamp": "2026-08-07T22:30:15Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "resourceId": "radio-01",
  "type": "Event",
  "name": "FrequencyChanged",
  "payload": {
    "frequencyHz": 14074000
  }
}
```

## SetMode

```json
{
  "version": "1.0",
  "messageId": "8b6aa69b-a78f-4872-b3fe-6d8ce0744ce6",
  "timestamp": "2026-08-07T22:30:17Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "resourceId": "radio-01",
  "type": "Command",
  "name": "SetMode",
  "payload": {
    "mode": "USB"
  }
}
```

## SetPTT

```json
{
  "version": "1.0",
  "messageId": "11120bdb-11ad-4df4-87c2-a3d3131bf090",
  "timestamp": "2026-08-07T22:30:20Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "resourceId": "radio-01",
  "type": "Command",
  "name": "SetPTT",
  "payload": {
    "enabled": true
  }
}
```

Evento:

```json
{
  "version": "1.0",
  "messageId": "06166695-3dd4-425e-ae23-d9eb6c27eebe",
  "correlationId": "11120bdb-11ad-4df4-87c2-a3d3131bf090",
  "timestamp": "2026-08-07T22:30:20Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "resourceId": "radio-01",
  "type": "Event",
  "name": "PTTChanged",
  "payload": {
    "enabled": true
  }
}
```

**PTT OFF é uma operação de segurança e deverá receber prioridade de processamento sobre comandos operacionais comuns.**

---

# Comandos Iniciais Previstos

- `Hello`
- `Authenticate`
- `Heartbeat`
- `AcquireResource`
- `ReleaseResource`
- `GetState`
- `SetFrequency`
- `SetMode`
- `SetPTT`
- `SetSplit`
- `MoveRotor`
- `PowerAmplifier`
- `Disconnect`
- `ResumeSession`

---

# Eventos Iniciais Previstos

- `HelloAck`
- `Authenticated`
- `HeartbeatAck`
- `ResourceAcquired`
- `ResourceReleased`
- `StateSnapshot`
- `FrequencyChanged`
- `ModeChanged`
- `PTTChanged`
- `RotorMoved`
- `AmplifierFault`
- `ResourceOffline`
- `OperatorConnected`
- `OperatorDisconnected`
- `LeaseExpired`
- `SessionResumed`

---

# Ordenação

Commands destinados ao mesmo Resource devem preservar ordem lógica de processamento.

Events gerados por um mesmo Resource devem preservar a ordem de geração observável pelo Gateway.

Uma futura versão poderá introduzir `sequenceNumber` por sessão ou Resource caso os testes demonstrem necessidade explícita.

---

# Idempotência

O Gateway deve manter proteção contra duplicação de Commands utilizando `messageId`.

Um Command repetido com o mesmo `messageId` não deve provocar efeitos duplicados no hardware.

O período mínimo de retenção do cache de idempotência deverá ser superior à janela de reconexão e será configurável.

---

# Reconexão e Recuperação de Sessão

Falhas transitórias de rede não devem obrigatoriamente destruir imediatamente todo o contexto do operador.

Durante `sessionResumeWindowSeconds`, o Client pode tentar `ResumeSession` utilizando informações de sessão apropriadas.

A recuperação somente é válida se:

- o token ainda for válido;
- a sessão não tiver sido revogada;
- a política de segurança permitir;
- os Leases ainda forem considerados recuperáveis.

Mesmo durante a janela de recuperação, ações de segurança como **PTT OFF** não devem ser revertidas automaticamente.

---

# Segurança

## Filosofia

Toda funcionalidade do GADX Vector deve seguir o princípio **Secure by Default**.

## Transporte Seguro

- Produção: WSS obrigatório.
- WS sem TLS: permitido apenas em desenvolvimento/laboratório explicitamente configurado.

## Credenciais

Credenciais são informações sensíveis.

Regras obrigatórias:

- usuário e senha nunca trafegam fora de TLS;
- usuário e senha nunca aparecem em logs;
- usuário e senha são utilizados apenas durante autenticação;
- depois da autenticação, o Gateway emite token temporário;
- tokens possuem expiração e podem ser revogados;
- tokens não aparecem em URLs;
- tokens não aparecem em logs;
- codificação Base64 NÃO é considerada proteção criptográfica.

## Armazenamento de Senhas

O Gateway nunca deve armazenar senhas em texto puro ou de forma reversível.

Algoritmos aceitáveis incluem:

- **Argon2id** — preferencial;
- bcrypt;
- scrypt.

Não devem ser usados isoladamente para armazenamento de senha:

- MD5;
- SHA-1;
- SHA-256 puro.

## Certificados

O Client deve validar o certificado TLS do Gateway.

Falha de validação deve impedir a conexão, salvo ambiente de laboratório explicitamente configurado para certificados de desenvolvimento.

## Autorização

Perfis iniciais previstos:

- `Administrator`
- `Operator`
- `Guest`
- `Monitor`

Cada Command deve passar por verificação de autorização antes de atingir o Driver.

## Auditoria

Comandos e eventos críticos devem gerar trilha de auditoria, incluindo, quando aplicável:

- usuário/callsign;
- sessão;
- site;
- Resource;
- operação;
- horário UTC;
- resultado;
- origem da conexão.

Segredos, senhas e tokens nunca devem ser registrados.

## Segurança Operacional

Em perda de comunicação ou condição de segurança, o Gateway deve priorizar a proteção da estação.

Política inicial:

- **PTT OFF imediatamente**;
- CW interrompido;
- Voice Keyer interrompido;
- amplificador colocado em estado seguro/Standby quando suportado;
- Resources liberados conforme política de Lease;
- comandos pendentes não críticos podem ser descartados;
- o estado físico real deve ser novamente sincronizado antes de retomar operação.

---

# Tratamento de Erros

Erros utilizam o mesmo envelope e `type: "Error"`.

Exemplo:

```json
{
  "version": "1.0",
  "messageId": "6ff4b0ae-2e0e-46e5-a1e3-7fc064417cc9",
  "correlationId": "1d5afe0c-d8cf-4681-a5e0-f57a17d7f243",
  "timestamp": "2026-08-07T22:30:15Z",
  "sessionId": "1ef3ee88-21e7-41fa-a48c-e4af78d82fd2",
  "resourceId": "radio-01",
  "type": "Error",
  "name": "CommandRejected",
  "payload": {
    "code": "RESOURCE_BUSY",
    "message": "Resource is controlled by another active lease",
    "retryable": true
  }
}
```

Códigos iniciais previstos:

- `INVALID_SESSION`
- `AUTHENTICATION_FAILED`
- `ACCESS_DENIED`
- `RESOURCE_BUSY`
- `LEASE_EXPIRED`
- `INVALID_COMMAND`
- `INVALID_PAYLOAD`
- `UNSUPPORTED`
- `INVALID_STATE`
- `RESOURCE_OFFLINE`
- `GATEWAY_BUSY`
- `PROTOCOL_VERSION_UNSUPPORTED`
- `INTERNAL_ERROR`

Mensagens de erro não devem revelar detalhes internos sensíveis, credenciais, stack traces ou informações que facilitem exploração do Gateway.

---

# Capabilities

Cada Resource anuncia suas capacidades.

Exemplo conceitual:

```json
{
  "resourceId": "radio-01",
  "type": "Radio",
  "capabilities": [
    "Frequency",
    "Mode",
    "PTT",
    "Split"
  ]
}
```

O Client não deve presumir que todo rádio ou equipamento implementa todas as operações conhecidas pelo Vector Protocol.

---

# Versionamento

O protocolo utiliza Semantic Versioning como referência conceitual.

- `1.x`: mudanças compatíveis dentro da mesma major version.
- `2.x`: mudanças que podem quebrar compatibilidade.

Client e Gateway devem negociar versão durante o handshake.

---

# Compatibilidade e Abstração

O Vector Protocol nunca dependerá diretamente de:

- Hamlib;
- CAT;
- Kenwood;
- Icom;
- Yaesu;
- FlexRadio;
- qualquer outro fabricante ou backend específico.

Integrações são realizadas exclusivamente por Drivers/Adapters.

---

# Fluxo Simplificado

```text
Client
  |
  v
Hello / Version Negotiation
  |
  v
Authenticate
  |
  v
Authenticated + Session
  |
  v
AcquireResource
  |
  v
ResourceAcquired + Lease
  |
  v
StateSnapshot
  |
  v
Heartbeat <-----------------------+
  |                               |
  v                               |
SetFrequency / SetMode / SetPTT   |
  |                               |
  v                               |
Events de estado -----------------+
  |
  v
ReleaseResource
  |
  v
Disconnect
```

---

# Objetivo Final

O Vector Protocol expressa apenas:

1. **o que o operador deseja fazer**; e
2. **o que realmente aconteceu no Resource**.

Ele nunca expõe ao Client **como** o hardware executa a operação.

Todo acesso ao hardware ocorre exclusivamente através do Driver/Adapter correspondente.

Essa separação é uma premissa fundamental do GADX Vector.
