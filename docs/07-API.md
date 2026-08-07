# GADX Vector
# 07 - Vector API

Versão: 1.0 (Draft)  
Status: Em elaboração

---

# 1. Objetivo

A **Vector API** define a interface de aplicação do **GADX Vector**.

Ela expõe de forma consistente os conceitos do Modelo de Domínio, da Máquina de Estados e do Vector Protocol para interfaces Web, ferramentas administrativas, integrações e aplicações futuras.

A API não controla hardware diretamente.

Toda operação segue a cadeia lógica:

```text
Aplicação / Interface
        |
        v
    Vector API
        |
        v
 Modelo de Domínio
        |
        v
 Máquina de Estados
        |
        v
 Vector Gateway
        |
        v
     Driver
        |
        v
    Hardware
```

A API expressa **intenções sobre o domínio** e consulta **estado autoritativo** mantido pelo Vector Gateway.

---

# 2. Princípios

A Vector API deverá seguir estes princípios:

- Orientação a recursos e domínio.
- Independência de fabricantes e protocolos físicos.
- Segurança por padrão.
- Versionamento explícito.
- Idempotência para operações mutáveis quando aplicável.
- Baixo acoplamento.
- Estados e erros previsíveis.
- Auditabilidade.
- Compatibilidade com múltiplos sites.
- Extensibilidade para novos tipos de Resource.
- Separação entre consultas, comandos e eventos em tempo real.

---

# 3. Escopo

A Vector API deverá permitir, no mínimo:

- autenticar usuários;
- consultar a sessão atual;
- listar sites;
- consultar gateways;
- listar Resources;
- consultar capabilities;
- adquirir e liberar Resources;
- consultar Leases;
- consultar estado autoritativo;
- executar comandos sobre Resources;
- receber eventos em tempo real;
- consultar saúde e telemetria;
- realizar operações administrativas autorizadas.

A API não deve expor detalhes internos de Hamlib, CAT, CI-V, protocolos de fabricantes ou implementação de Drivers.

---

# 4. Interfaces da Vector API

A Vector API possui duas interfaces complementares.

## 4.1 HTTP/REST

Utilizada para:

- autenticação;
- descoberta;
- consultas;
- configuração;
- aquisição e liberação de Resources;
- comandos transacionais;
- administração;
- recuperação de estado.

## 4.2 WebSocket

Utilizado para:

- eventos em tempo real;
- atualizações de estado;
- mudanças de frequência;
- PTT;
- telemetria;
- mudanças de Lease;
- presença de operadores;
- eventos de falha;
- notificações do Gateway.

O WebSocket da API deverá utilizar os mesmos princípios semânticos definidos no **Vector Protocol**.

---

# 5. Transporte e Segurança

## 5.1 Produção

Em produção, todo acesso deverá utilizar:

- `HTTPS` para REST;
- `WSS` para WebSocket;
- TLS válido;
- validação obrigatória de certificado.

Conexões HTTP ou WS sem TLS não deverão ser aceitas em produção.

## 5.2 Laboratório

HTTP/WS poderá ser habilitado apenas mediante configuração explícita para ambiente de laboratório ou desenvolvimento.

## 5.3 Credenciais

Credenciais permanentes não deverão ser enviadas em URLs, query strings ou logs.

Após autenticação, a API utilizará token temporário de sessão.

Exemplo:

```http
Authorization: Bearer <session-token>
```

Tokens deverão possuir:

- expiração;
- revogação;
- associação ao usuário;
- associação à sessão;
- escopos/permissões;
- auditoria de emissão e revogação.

---

# 6. URL Base e Versionamento

A API REST utilizará versionamento no caminho.

Exemplo:

```text
https://vector-gateway.example/api/v1/
```

O WebSocket utilizará caminho equivalente:

```text
wss://vector-gateway.example/api/v1/events
```

## 6.1 Política de versão

- `v1` — primeira versão pública estável.
- Alterações compatíveis poderão ocorrer dentro da mesma versão.
- Quebras de compatibilidade exigem nova versão principal da API.
- Recursos obsoletos deverão ser marcados como deprecated antes da remoção, sempre que possível.

A versão da API é independente da versão do software do Gateway.

---

# 7. Formato dos Dados

A representação padrão será **JSON UTF-8**.

Datas e horários deverão utilizar UTC no formato ISO 8601.

Exemplo:

```json
{
  "timestamp": "2026-08-07T23:30:00Z"
}
```

Frequências deverão ser representadas em **Hz inteiros**.

Exemplo:

```json
{
  "frequencyHz": 14074000
}
```

Azimute e elevação deverão utilizar graus decimais.

```json
{
  "azimuthDeg": 273.5,
  "elevationDeg": 18.0
}
```

---

# 8. Envelope Padrão de Resposta

Respostas bem-sucedidas poderão retornar diretamente o recurso solicitado.

Quando houver necessidade de metadados, será utilizado o envelope:

```json
{
  "data": {},
  "meta": {
    "requestId": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-08-07T23:30:00Z"
  }
}
```

Listagens utilizarão:

```json
{
  "data": [],
  "meta": {
    "count": 4,
    "requestId": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

---

# 9. Erros

Erros deverão utilizar estrutura previsível.

```json
{
  "error": {
    "code": "RESOURCE_BUSY",
    "message": "Resource radio-01 is currently controlled by another session.",
    "requestId": "550e8400-e29b-41d4-a716-446655440000",
    "details": {
      "resourceId": "radio-01"
    }
  }
}
```

## 9.1 Códigos HTTP

| HTTP | Uso |
|---|---|
| `200` | Consulta ou comando concluído |
| `201` | Recurso lógico criado, como Lease |
| `202` | Comando aceito para processamento assíncrono |
| `204` | Operação concluída sem conteúdo |
| `400` | Requisição inválida |
| `401` | Não autenticado |
| `403` | Sem autorização |
| `404` | Entidade não encontrada |
| `409` | Conflito de estado ou Resource ocupado |
| `422` | Comando semanticamente inválido |
| `429` | Limite de requisições excedido |
| `503` | Gateway ou Resource indisponível |
| `500` | Erro interno inesperado |

## 9.2 Códigos de domínio

Exemplos:

- `INVALID_SESSION`
- `ACCESS_DENIED`
- `RESOURCE_NOT_FOUND`
- `RESOURCE_BUSY`
- `RESOURCE_OFFLINE`
- `LEASE_REQUIRED`
- `LEASE_EXPIRED`
- `INVALID_STATE`
- `INVALID_COMMAND`
- `UNSUPPORTED_CAPABILITY`
- `INVALID_FREQUENCY`
- `INVALID_MODE`
- `PTT_INTERLOCK`
- `GATEWAY_DEGRADED`
- `GATEWAY_BUSY`
- `RATE_LIMITED`
- `INTERNAL_ERROR`

---

# 10. Autenticação

## 10.1 Login

```http
POST /api/v1/auth/login
```

Exemplo de requisição:

```json
{
  "username": "operator",
  "password": "<secret>"
}
```

A transmissão só é permitida sobre TLS.

Exemplo de resposta:

```json
{
  "sessionId": "sess-7fdb1b",
  "token": "<temporary-session-token>",
  "expiresAt": "2026-08-08T00:30:00Z",
  "operator": {
    "id": "op-001",
    "callsign": "PY5XXX",
    "roles": ["Operator"]
  }
}
```

A senha não deverá ser devolvida, persistida em logs ou reutilizada nas chamadas seguintes.

## 10.2 Sessão atual

```http
GET /api/v1/session
```

Exemplo:

```json
{
  "id": "sess-7fdb1b",
  "state": "ACTIVE",
  "operatorId": "op-001",
  "createdAt": "2026-08-07T23:00:00Z",
  "lastHeartbeatAt": "2026-08-07T23:29:55Z"
}
```

## 10.3 Logout

```http
POST /api/v1/auth/logout
```

O logout deverá:

- invalidar o token;
- iniciar liberação segura dos Leases da sessão;
- executar fail-safe quando necessário;
- gerar evento de auditoria.

---

# 11. Sites

## 11.1 Listar Sites

```http
GET /api/v1/sites
```

Exemplo:

```json
{
  "data": [
    {
      "id": "site-puruna",
      "name": "Purunã",
      "gridLocator": "GG54xx",
      "status": "ONLINE"
    },
    {
      "id": "site-guatupe",
      "name": "Guatupê",
      "status": "ONLINE"
    }
  ]
}
```

## 11.2 Consultar Site

```http
GET /api/v1/sites/{siteId}
```

A resposta poderá incluir:

- identificação;
- localização;
- Grid Locator;
- timezone;
- Gateway associado;
- estado;
- Resources disponíveis.

---

# 12. Gateways

## 12.1 Estado do Gateway

```http
GET /api/v1/gateway
```

Exemplo:

```json
{
  "id": "gateway-puruna-01",
  "siteId": "site-puruna",
  "state": "READY",
  "version": "0.1.0",
  "protocolVersion": "1.0",
  "apiVersion": "v1",
  "uptimeSeconds": 86400
}
```

## 12.2 Health Check

```http
GET /api/v1/health
```

Exemplo:

```json
{
  "status": "healthy",
  "gatewayState": "READY",
  "timestamp": "2026-08-07T23:30:00Z"
}
```

O Health Check não deverá revelar informações sensíveis a usuários não autenticados.

---

# 13. Resources

## 13.1 Listar Resources

```http
GET /api/v1/resources
```

Filtros poderão ser suportados:

```text
GET /api/v1/resources?siteId=site-puruna&type=Radio&state=AVAILABLE
```

Exemplo:

```json
{
  "data": [
    {
      "id": "radio-01",
      "siteId": "site-puruna",
      "type": "Radio",
      "name": "Radio 01",
      "state": "AVAILABLE",
      "online": true,
      "capabilities": [
        "Frequency",
        "Mode",
        "PTT",
        "Split"
      ]
    }
  ]
}
```

## 13.2 Consultar Resource

```http
GET /api/v1/resources/{resourceId}
```

## 13.3 Estado Autoritativo

```http
GET /api/v1/resources/{resourceId}/state
```

Para um rádio:

```json
{
  "resourceId": "radio-01",
  "resourceState": "IN_USE",
  "observedAt": "2026-08-07T23:30:00Z",
  "radio": {
    "frequencyHz": 14074000,
    "mode": "USB",
    "ptt": false,
    "split": false
  }
}
```

O estado retornado pelo Gateway é a fonte autoritativa para a plataforma.

---

# 14. Capabilities

Capabilities determinam quais operações são suportadas por cada Resource.

```http
GET /api/v1/resources/{resourceId}/capabilities
```

Exemplo:

```json
{
  "resourceId": "radio-01",
  "capabilities": {
    "Frequency": {
      "read": true,
      "write": true
    },
    "Mode": {
      "read": true,
      "write": true,
      "values": ["USB", "LSB", "CW", "DIGI", "AM", "FM"]
    },
    "PTT": {
      "read": true,
      "write": true
    },
    "Split": {
      "read": true,
      "write": true
    }
  }
}
```

Um Client não deverá assumir que uma operação existe apenas porque o tipo do Resource normalmente a suporta.

A Capability anunciada pelo Gateway é a referência.

---

# 15. Leases e Controle Exclusivo

## 15.1 Adquirir Resource

```http
POST /api/v1/resources/{resourceId}/lease
```

Exemplo:

```json
{
  "requestedDurationSeconds": 30
}
```

Resposta:

```json
{
  "leaseId": "lease-a192",
  "resourceId": "radio-01",
  "sessionId": "sess-7fdb1b",
  "state": "ACTIVE",
  "expiresAt": "2026-08-07T23:30:30Z",
  "heartbeatIntervalSeconds": 5
}
```

O Gateway poderá limitar ou substituir a duração solicitada conforme política local.

## 15.2 Consultar Lease

```http
GET /api/v1/resources/{resourceId}/lease
```

## 15.3 Renovar Lease

A renovação normal deverá ocorrer pelo mecanismo de heartbeat da sessão.

Poderá existir endpoint explícito para cenários administrativos:

```http
POST /api/v1/resources/{resourceId}/lease/renew
```

## 15.4 Liberar Resource

```http
DELETE /api/v1/resources/{resourceId}/lease
```

A liberação deverá executar as transições definidas em `06-MaquinaDeEstados.md`.

---

# 16. Comandos Genéricos

A API deverá possuir uma forma genérica de executar comandos do domínio.

```http
POST /api/v1/resources/{resourceId}/commands
```

Exemplo:

```json
{
  "command": "SetFrequency",
  "commandId": "cmd-9102",
  "parameters": {
    "frequencyHz": 14074000
  }
}
```

Resposta síncrona quando a operação for confirmada rapidamente:

```json
{
  "commandId": "cmd-9102",
  "status": "COMPLETED",
  "resourceId": "radio-01",
  "state": {
    "frequencyHz": 14074000
  }
}
```

Quando o comando for assíncrono:

```json
{
  "commandId": "cmd-9102",
  "status": "ACCEPTED"
}
```

Nesse caso, a confirmação final será publicada como evento.

---

# 17. API de Rádio

Além da interface genérica, a implementação poderá oferecer endpoints de conveniência para tipos principais.

## 17.1 Frequência

Consulta:

```http
GET /api/v1/resources/{radioId}/radio/frequency
```

Alteração:

```http
PUT /api/v1/resources/{radioId}/radio/frequency
```

```json
{
  "frequencyHz": 14074000
}
```

## 17.2 Modo

```http
PUT /api/v1/resources/{radioId}/radio/mode
```

```json
{
  "mode": "USB"
}
```

## 17.3 PTT

```http
PUT /api/v1/resources/{radioId}/radio/ptt
```

```json
{
  "enabled": true
}
```

PTT é uma operação crítica.

O Gateway deverá verificar antes de aceitar PTT ON:

- sessão válida;
- Lease ativo;
- Resource em estado permitido;
- Capability `PTT` disponível;
- interlocks de segurança;
- políticas locais;
- estado do Driver;
- condições adicionais configuradas no site.

PTT OFF deverá ser permitido e priorizado sempre que tecnicamente possível, inclusive em cenários de degradação.

## 17.4 Split

```http
PUT /api/v1/resources/{radioId}/radio/split
```

```json
{
  "enabled": true
}
```

---

# 18. API de Rotor

Exemplo de posicionamento:

```http
POST /api/v1/resources/{rotorId}/rotor/move
```

```json
{
  "azimuthDeg": 273.0,
  "elevationDeg": 0.0
}
```

Parada:

```http
POST /api/v1/resources/{rotorId}/rotor/stop
```

Consulta:

```http
GET /api/v1/resources/{rotorId}/rotor/position
```

A implementação deverá validar limites mecânicos e capabilities antes da movimentação.

---

# 19. API de Amplificador

Exemplos previstos:

```http
GET  /api/v1/resources/{amplifierId}/amplifier/state
POST /api/v1/resources/{amplifierId}/amplifier/power-on
POST /api/v1/resources/{amplifierId}/amplifier/standby
POST /api/v1/resources/{amplifierId}/amplifier/power-off
```

Comandos de amplificador deverão respeitar interlocks e estados definidos na Máquina de Estados.

---

# 20. Eventos em Tempo Real

Endpoint:

```text
WSS /api/v1/events
```

O Client autenticado poderá receber eventos referentes a:

- Session;
- Gateway;
- Resource;
- Lease;
- Radio;
- Rotor;
- Amplifier;
- segurança;
- administração, conforme permissão.

## 20.1 Envelope de Evento

```json
{
  "version": "1.0",
  "eventId": "evt-6721",
  "timestamp": "2026-08-07T23:30:01Z",
  "name": "FrequencyChanged",
  "siteId": "site-puruna",
  "resourceId": "radio-01",
  "payload": {
    "frequencyHz": 14074000
  }
}
```

## 20.2 Eventos principais

Exemplos:

- `GatewayStateChanged`
- `ResourceStateChanged`
- `ResourceAcquired`
- `ResourceReleased`
- `LeaseExpiring`
- `LeaseExpired`
- `FrequencyChanged`
- `ModeChanged`
- `PTTChanged`
- `SplitChanged`
- `RotorPositionChanged`
- `AmplifierStateChanged`
- `ResourceOffline`
- `DriverFault`
- `SessionDisconnected`

---

# 21. Snapshot e Sincronização

Ao iniciar uma conexão em tempo real, o Client deverá obter um snapshot autoritativo antes de processar eventos diferenciais.

Fluxo recomendado:

```text
GET Resource State
       |
       v
Snapshot local
       |
       v
Abrir WebSocket
       |
       v
Processar eventos
```

Alternativamente, o Gateway poderá enviar um `StateSnapshot` imediatamente após a assinatura do WebSocket.

A implementação deverá impedir que eventos antigos sobrescrevam estado mais recente.

---

# 22. Concorrência e Estado

Toda operação mutável deverá ser validada contra a Máquina de Estados.

Exemplo:

```text
AVAILABLE + SetFrequency = inválido
IN_USE   + SetFrequency = permitido, se Lease pertence à Session
```

O fato de uma chamada HTTP estar autenticada não significa que ela possui autorização operacional para alterar um Resource.

Autenticação, autorização, ownership, capabilities e estado devem ser validados separadamente.

---

# 23. Idempotência

Operações críticas ou suscetíveis a repetição deverão aceitar identificador idempotente.

Exemplo:

```http
Idempotency-Key: 4f747e0d-6cc8-47fe-95ce-fc83087a84af
```

ou `commandId` no corpo.

Repetições do mesmo comando não deverão provocar efeitos físicos duplicados.

Isto é especialmente importante para:

- movimentação de rotor;
- mudança de estado de amplificador;
- operações administrativas;
- aquisição de Resource;
- comandos retransmitidos após reconexão.

---

# 24. Heartbeat

O heartbeat do Vector Protocol continua sendo o mecanismo autoritativo para presença e renovação de Lease.

Defaults iniciais sugeridos:

| Parâmetro | Default inicial |
|---|---:|
| Heartbeat | 5 segundos |
| Lease | 30 segundos |
| Aviso de expiração | 10 segundos antes |
| Timeout para sessão degradada | Configurável |

Esses valores são defaults e poderão ser alterados pelo Gateway conforme o site, Resource ou política operacional.

A API deverá informar ao Client os valores efetivos negociados.

---

# 25. Reconexão

Após perda temporária de conectividade, o Client poderá tentar recuperar a sessão conforme regras do Vector Protocol.

A recuperação nunca deverá presumir que o Client ainda possui controle do Resource.

Após reconexão, o Client deverá:

1. validar a sessão;
2. consultar o Lease;
3. obter snapshot autoritativo;
4. reconciliar estado local;
5. somente então voltar a emitir comandos.

Se o Lease tiver expirado, o Client deverá solicitar nova aquisição.

---

# 26. Segurança Operacional

A API nunca deverá permitir que conveniência de software tenha prioridade sobre segurança física.

Regras mínimas:

- PTT OFF é fail-safe.
- Perda de sessão não mantém transmissão indefinidamente.
- Lease expirado remove autoridade de controle.
- Resource em `FAULT` rejeita comandos incompatíveis.
- Amplificador em falha não poderá ser colocado em TX por chamada comum de API.
- Comandos administrativos críticos deverão ser auditados.
- O Gateway poderá rejeitar qualquer comando que viole interlock local.

---

# 27. Autorização

Perfis iniciais previstos:

- `Administrator`
- `Operator`
- `Guest`
- `Monitor`

Exemplo conceitual:

| Operação | Administrator | Operator | Guest | Monitor |
|---|:---:|:---:|:---:|:---:|
| Ver estado | ✓ | ✓ | ✓ | ✓ |
| Adquirir Radio | ✓ | ✓ | — | — |
| Alterar frequência | ✓ | ✓ | — | — |
| PTT | ✓ | ✓ | — | — |
| Mover rotor | ✓ | ✓* | — | — |
| Configurar Gateway | ✓ | — | — | — |
| Administrar usuários | ✓ | — | — | — |

`*` Sujeito a política do site e ao Resource adquirido.

Permissões finais deverão ser configuráveis e não depender exclusivamente de nomes fixos de perfil.

---

# 28. Auditoria

A API deverá gerar registros de auditoria para ações relevantes.

Campos mínimos recomendados:

- timestamp UTC;
- requestId / commandId;
- Session;
- usuário/callsign;
- site;
- Resource;
- operação;
- resultado;
- estado anterior quando relevante;
- estado final quando relevante;
- endereço/origem técnica quando apropriado.

Dados sensíveis como senha e token nunca deverão ser registrados.

---

# 29. Rate Limiting

O Gateway poderá aplicar limites por:

- Session;
- usuário;
- endpoint;
- Resource;
- tipo de comando.

Comandos de alta frequência, como ajuste de frequência durante tuning, poderão utilizar política específica para evitar sobrecarga sem comprometer usabilidade.

PTT OFF e comandos de segurança não deverão ser bloqueados por rate limiting convencional.

---

# 30. Paginação e Filtros

Listagens extensas deverão suportar paginação quando necessário.

Formato sugerido:

```text
GET /api/v1/resources?limit=50&cursor=<cursor>
```

Resposta:

```json
{
  "data": [],
  "meta": {
    "nextCursor": null,
    "count": 12
  }
}
```

Filtros deverão usar parâmetros claros e documentados.

---

# 31. Observabilidade

A API poderá expor dados operacionais apropriados para diagnóstico, sem revelar segredos.

Exemplos:

```http
GET /api/v1/health
GET /api/v1/status
```

Dados avançados de métricas deverão possuir autorização própria.

Telemetria poderá incluir:

- latência;
- uptime;
- número de sessões;
- Resources online/offline;
- estado de Drivers;
- filas internas;
- quantidade de erros.

---

# 32. API Administrativa

Operações administrativas deverão permanecer claramente separadas das operações normais.

Prefixo sugerido:

```text
/api/v1/admin/
```

Exemplos futuros:

```text
GET  /api/v1/admin/users
POST /api/v1/admin/users
GET  /api/v1/admin/resources
PUT  /api/v1/admin/resources/{id}
GET  /api/v1/admin/audit
```

A API administrativa deverá possuir autorização explícita e auditoria obrigatória.

---

# 33. Integrações Externas

Aplicações externas deverão integrar-se pela Vector API ou pelo Vector Protocol, nunca diretamente com Drivers internos.

Isso inclui futuras integrações com:

- dashboards;
- aplicações móveis;
- automações;
- sistemas de reserva;
- ferramentas de contest;
- monitoramento;
- sistemas de terceiros.

A existência de um Driver Hamlib não significa que aplicações externas deverão conhecer `rigctld`.

---

# 34. Relação entre API e Vector Protocol

A API e o protocolo compartilham o mesmo domínio, porém cumprem papéis diferentes.

| Vector API | Vector Protocol |
|---|---|
| Interface de aplicação | Comunicação operacional Client ↔ Gateway |
| REST + WebSocket | WebSocket orientado a comandos/eventos |
| Integrações e UI | Controle distribuído em tempo real |
| Descoberta e administração | Estado e operação de Resources |
| Pode possuir endpoints de conveniência | Mantém envelope canônico do protocolo |

Nenhuma das duas interfaces deverá criar semânticas contraditórias.

Um `SetFrequency` significa a mesma intenção independentemente de ter sido originado pela API ou pelo Vector Protocol.

---

# 35. Regra de Autoridade

A regra fundamental da Vector API é:

> **A aplicação solicita. A Vector API valida. O Gateway decide. O Driver executa. O hardware confirma. O Gateway publica o estado autoritativo.**

Portanto:

- sucesso HTTP não deve ser confundido com estado físico quando a operação for assíncrona;
- o Client não deve inventar estado;
- o estado observado pelo Gateway prevalece sobre o estado desejado pela aplicação;
- qualquer divergência deverá ser reconciliada pelo Gateway.

---

# 36. Exemplo Completo — Operação de Rádio

```text
1. POST /auth/login
          |
          v
2. GET /sites
          |
          v
3. GET /resources?type=Radio
          |
          v
4. POST /resources/radio-01/lease
          |
          v
5. GET /resources/radio-01/state
          |
          v
6. WSS /events
          |
          v
7. PUT /radio/frequency
          |
          v
8. Evento FrequencyChanged
          |
          v
9. PUT /radio/ptt { enabled:true }
          |
          v
10. Evento PTTChanged
          |
          v
11. PUT /radio/ptt { enabled:false }
          |
          v
12. DELETE /resources/radio-01/lease
```

Em nenhuma etapa a aplicação precisa conhecer se o equipamento é Kenwood, Icom, Yaesu, FlexRadio ou se é controlado por Hamlib.

---

# 37. Fora do Escopo Inicial

A versão 1 não precisa definir de forma definitiva:

- streaming de áudio;
- streaming de vídeo;
- transferência de arquivos;
- CAT binário direto pela API;
- WebRTC;
- controle de SDR IQ;
- gerenciamento de firmware;
- integração pública aberta à Internet sem autenticação.

Esses recursos poderão ser especificados futuramente sem alterar os fundamentos da API.

---

# 38. Objetivo Final

A **Vector API** deverá ser a interface estável e previsível do ecossistema GADX Vector.

Ela deve permitir que novas interfaces e aplicações sejam construídas sem conhecer a implementação interna do Gateway ou dos equipamentos físicos.

O contrato externo é o domínio Vector.

O hardware é um detalhe de implementação atrás dos Drivers.
