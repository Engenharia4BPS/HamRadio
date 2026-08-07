# GADX Vector – Vector Protocol

**Versão do documento:** 1.0-draft  
**Status:** Draft  
**Escopo:** Comunicação entre **Vector Client** e **Vector Gateway**

---

# 1. Objetivo

O **Vector Protocol** é o protocolo interno de comunicação do **GADX Vector**.

Ele define como o **Vector Client** e o **Vector Gateway** trocam comandos, respostas, eventos, estados e informações de sessão de forma previsível, versionável e independente do hardware físico controlado.

O protocolo não deve conhecer detalhes específicos de Hamlib, CAT, CI-V, fabricantes ou modelos de rádio. Essas particularidades pertencem aos Drivers e Adapters definidos na arquitetura da plataforma.

> O Vector Protocol transporta intenções e estados do domínio; nunca comandos nativos de hardware.

---

# 2. Princípios de Projeto

O Vector Protocol deve seguir os seguintes princípios:

1. **Independência de hardware** — nenhuma mensagem depende diretamente de Hamlib, CAT, CI-V, fabricante ou modelo de equipamento.
2. **Bidirecionalidade** — Client e Gateway devem poder transmitir informações em tempo real.
3. **Orientação a comandos e eventos** — o Client solicita ações; o Gateway confirma, rejeita e publica mudanças de estado.
4. **Baixa latência** — operações de rádio, especialmente PTT, devem ter tratamento prioritário e comportamento previsível.
5. **Observabilidade** — toda operação relevante deve poder ser correlacionada, registrada e auditada.
6. **Versionamento explícito** — alterações incompatíveis não podem quebrar clientes silenciosamente.
7. **Reconexão segura** — perda de rede não deve produzir controle órfão de recursos.
8. **Idempotência quando aplicável** — repetição de comandos decorrente de reconexões não deve gerar efeitos indesejados.
9. **Falha segura** — em dúvida, o sistema deve privilegiar o estado seguro do equipamento, especialmente transmissão e potência.
10. **Extensibilidade** — novos tipos de Resource, Command e Event devem poder ser adicionados sem redesenhar o protocolo.

---

# 3. Arquitetura de Comunicação

Fluxo lógico principal:

```text
N1MM / DXLog / Aplicação local
            |
            v
      Vector Client
            |
            |  Vector Protocol
            |  WSS + JSON
            v
      Vector Gateway
            |
            v
     Domain / Drivers
            |
            v
 Hamlib / CAT / Hardware
```

O **Vector Client** converte interações locais em comandos de domínio.

O **Vector Gateway** valida autorização, sessão, ownership e capabilities antes de executar qualquer operação sobre um Resource.

---

# 4. Transporte

## 4.1 Transporte padrão v1

O transporte padrão da versão 1 será:

- **WebSocket** para comunicação persistente e bidirecional;
- **TLS obrigatório** fora de redes explicitamente confiáveis;
- URI recomendada: `wss://<gateway>/vector/v1`;
- **JSON UTF-8** como formato de serialização inicial.

WebSocket foi escolhido por permitir comandos e eventos na mesma conexão, simplificar comunicação em tempo real e oferecer boa compatibilidade com aplicações Web e serviços nativos.

## 4.2 Independência do transporte

A semântica do Vector Protocol não deve depender de WebSocket.

No futuro, o mesmo modelo poderá ser transportado por tecnologias como QUIC, gRPC ou outro mecanismo, desde que mantenha as mesmas regras de domínio.

---

# 5. Modelo de Mensagens

Todas as mensagens utilizam um envelope comum.

## 5.1 Envelope base

```json
{
  "vector": "1.0",
  "type": "command",
  "name": "radio.setFrequency",
  "messageId": "01JXYZ...",
  "correlationId": null,
  "timestamp": "2026-08-07T22:00:00.000Z",
  "sessionId": "sess_abc123",
  "resourceId": "radio_puruna_01",
  "payload": {}
}
```

## 5.2 Campos obrigatórios

| Campo | Descrição |
|---|---|
| `vector` | Versão do protocolo |
| `type` | Tipo da mensagem |
| `name` | Nome semântico da mensagem |
| `messageId` | Identificador único da mensagem |
| `timestamp` | Data/hora UTC em ISO 8601 |
| `payload` | Conteúdo específico da mensagem |

## 5.3 Campos condicionais

| Campo | Uso |
|---|---|
| `correlationId` | Relaciona resposta ou evento à mensagem original |
| `sessionId` | Obrigatório após criação/autenticação da sessão |
| `resourceId` | Obrigatório quando a mensagem atua sobre um Resource |

## 5.4 Tipos de mensagem

Valores iniciais de `type`:

- `command`
- `response`
- `event`
- `error`
- `system`

---

# 6. Convenção de Nomes

Os nomes devem utilizar namespaces semânticos em `lowerCamelCase`.

Exemplos:

```text
system.hello
system.heartbeat
session.authenticate
session.resume
resource.list
resource.acquire
resource.release
radio.getState
radio.setFrequency
radio.setMode
radio.setPtt
rotor.setAzimuth
amplifier.powerOn
```

Eventos usam a mesma estrutura:

```text
resource.acquired
resource.released
radio.frequencyChanged
radio.modeChanged
radio.pttChanged
radio.stateChanged
session.expired
```

---

# 7. Ciclo de Vida da Conexão

O fluxo nominal é:

```text
CONNECT
   |
   v
system.hello
   |
   v
session.authenticate
   |
   v
session.authenticated
   |
   v
resource.list
   |
   v
resource.acquire
   |
   v
resource.acquired
   |
   v
COMMANDS + EVENTS
   |
   v
resource.release
   |
   v
DISCONNECT
```

---

# 8. Handshake

Após abrir a conexão, o Client envia:

```json
{
  "vector": "1.0",
  "type": "system",
  "name": "system.hello",
  "messageId": "msg_001",
  "timestamp": "2026-08-07T22:00:00.000Z",
  "payload": {
    "client": "Vector Client",
    "clientVersion": "0.1.0",
    "protocols": ["1.0"],
    "platform": "windows"
  }
}
```

O Gateway responde informando a versão negociada:

```json
{
  "vector": "1.0",
  "type": "response",
  "name": "system.helloAccepted",
  "messageId": "msg_002",
  "correlationId": "msg_001",
  "timestamp": "2026-08-07T22:00:00.010Z",
  "payload": {
    "gateway": "Puruna-GW01",
    "gatewayVersion": "0.1.0",
    "protocol": "1.0",
    "siteId": "puruna"
  }
}
```

Se não houver versão compatível, a conexão deve ser encerrada de forma explícita com erro `PROTOCOL_VERSION_UNSUPPORTED`.

---

# 9. Autenticação

A autenticação ocorre após o handshake.

O protocolo não fixa permanentemente o mecanismo de autenticação; define apenas sua semântica.

Para a primeira implementação poderá existir autenticação simples de usuário/senha ou token, porém credenciais jamais devem trafegar sem TLS.

Exemplo conceitual:

```json
{
  "vector": "1.0",
  "type": "command",
  "name": "session.authenticate",
  "messageId": "msg_003",
  "timestamp": "2026-08-07T22:00:01.000Z",
  "payload": {
    "username": "PY5XT",
    "credential": "<secret>"
  }
}
```

Resposta:

```json
{
  "vector": "1.0",
  "type": "response",
  "name": "session.authenticated",
  "messageId": "msg_004",
  "correlationId": "msg_003",
  "timestamp": "2026-08-07T22:00:01.050Z",
  "sessionId": "sess_abc123",
  "payload": {
    "operator": {
      "callsign": "PY5XT",
      "roles": ["operator"]
    }
  }
}
```

---

# 10. Descoberta de Resources

O Client pode solicitar a lista de Resources publicados pelo Gateway.

```json
{
  "vector": "1.0",
  "type": "command",
  "name": "resource.list",
  "messageId": "msg_010",
  "timestamp": "2026-08-07T22:01:00.000Z",
  "sessionId": "sess_abc123",
  "payload": {}
}
```

Resposta resumida:

```json
{
  "vector": "1.0",
  "type": "response",
  "name": "resource.listResult",
  "messageId": "msg_011",
  "correlationId": "msg_010",
  "timestamp": "2026-08-07T22:01:00.010Z",
  "sessionId": "sess_abc123",
  "payload": {
    "resources": [
      {
        "id": "radio_puruna_01",
        "type": "radio",
        "name": "Radio 1",
        "state": "ONLINE",
        "ownership": "FREE",
        "capabilities": [
          "frequency",
          "mode",
          "ptt",
          "split"
        ]
      }
    ]
  }
}
```

Capabilities devem ser anunciadas dinamicamente. O Client não deve presumir que todos os Resources do mesmo tipo oferecem as mesmas funções.

---

# 11. Ownership e Lease de Recursos

Antes de modificar um Resource, uma Session precisa adquiri-lo.

## 11.1 Acquire

```json
{
  "vector": "1.0",
  "type": "command",
  "name": "resource.acquire",
  "messageId": "msg_020",
  "timestamp": "2026-08-07T22:02:00.000Z",
  "sessionId": "sess_abc123",
  "resourceId": "radio_puruna_01",
  "payload": {}
}
```

Resposta:

```json
{
  "vector": "1.0",
  "type": "event",
  "name": "resource.acquired",
  "messageId": "msg_021",
  "correlationId": "msg_020",
  "timestamp": "2026-08-07T22:02:00.020Z",
  "sessionId": "sess_abc123",
  "resourceId": "radio_puruna_01",
  "payload": {
    "leaseId": "lease_xyz789",
    "leaseTimeoutSeconds": 15
  }
}
```

## 11.2 Lease

Ownership deve possuir tempo de vida controlado por **lease**.

O lease evita que uma desconexão deixe um rádio permanentemente bloqueado.

A Session mantém o lease ativo através do heartbeat.

Se a Session desaparecer e o lease expirar, o Gateway deve:

1. executar a política de segurança do Resource;
2. cancelar PTT quando aplicável;
3. liberar ownership;
4. publicar `resource.released`;
5. registrar o motivo no audit log.

---

# 12. Comandos de Rádio

A versão inicial do protocolo deve suportar pelo menos:

```text
radio.getState
radio.setFrequency
radio.setMode
radio.setPtt
radio.setSplit
```

## 12.1 Set Frequency

Frequência é sempre expressa como inteiro em **Hz**.

```json
{
  "vector": "1.0",
  "type": "command",
  "name": "radio.setFrequency",
  "messageId": "msg_100",
  "timestamp": "2026-08-07T22:05:00.000Z",
  "sessionId": "sess_abc123",
  "resourceId": "radio_puruna_01",
  "payload": {
    "frequencyHz": 14074000
  }
}
```

O Gateway valida:

- Session autenticada;
- Resource adquirido pela Session;
- capability `frequency`;
- valor dentro dos limites expostos pelo Resource/Driver;
- estado operacional compatível.

Após executar, o Gateway publica o estado efetivamente confirmado:

```json
{
  "vector": "1.0",
  "type": "event",
  "name": "radio.frequencyChanged",
  "messageId": "msg_101",
  "correlationId": "msg_100",
  "timestamp": "2026-08-07T22:05:00.030Z",
  "sessionId": "sess_abc123",
  "resourceId": "radio_puruna_01",
  "payload": {
    "frequencyHz": 14074000
  }
}
```

O evento contém o **estado confirmado pelo Gateway**, não apenas o valor solicitado pelo Client.

## 12.2 Set Mode

```json
{
  "vector": "1.0",
  "type": "command",
  "name": "radio.setMode",
  "messageId": "msg_110",
  "timestamp": "2026-08-07T22:05:05.000Z",
  "sessionId": "sess_abc123",
  "resourceId": "radio_puruna_01",
  "payload": {
    "mode": "USB",
    "passbandHz": 2400
  }
}
```

Modes devem utilizar nomes canônicos definidos pelo GADX Vector, e não nomes particulares de cada fabricante.

## 12.3 Set PTT

```json
{
  "vector": "1.0",
  "type": "command",
  "name": "radio.setPtt",
  "messageId": "msg_120",
  "timestamp": "2026-08-07T22:05:10.000Z",
  "sessionId": "sess_abc123",
  "resourceId": "radio_puruna_01",
  "payload": {
    "enabled": true
  }
}
```

PTT é um comando crítico.

O Gateway deve sempre privilegiar **PTT OFF** em condições de erro, timeout, perda de Session, falha de lease ou parada do serviço.

PTT ON não deve permanecer ativo apenas porque o último comando recebido foi `true`.

---

# 13. Estado Autoritativo

O **Vector Gateway é a fonte autoritativa do estado dos Resources**.

O Client pode manter cache local para interface e emulação CAT, porém deve considerar os eventos recebidos do Gateway como verdade operacional.

Exemplo:

```text
Client solicita 14.074.000 Hz
          |
          v
Gateway envia ao Driver
          |
          v
Driver confirma 14.074.000 Hz
          |
          v
Gateway atualiza Domain State
          |
          v
radio.frequencyChanged
          |
          v
Client atualiza cache + CAT virtual
```

Isso permite inclusive detectar alterações feitas localmente no rádio físico.

---

# 14. Eventos Assíncronos

Eventos podem ocorrer sem comando prévio do Client.

Exemplos:

```text
radio.frequencyChanged
radio.modeChanged
radio.pttChanged
radio.stateChanged
resource.acquired
resource.released
resource.offline
resource.online
session.expiring
session.expired
gateway.warning
```

Exemplo de alteração local no rádio:

```json
{
  "vector": "1.0",
  "type": "event",
  "name": "radio.frequencyChanged",
  "messageId": "evt_500",
  "correlationId": null,
  "timestamp": "2026-08-07T22:10:00.000Z",
  "resourceId": "radio_puruna_01",
  "payload": {
    "frequencyHz": 14200000,
    "source": "hardware"
  }
}
```

Valores possíveis iniciais para `source`:

- `client`
- `hardware`
- `gateway`
- `system`

---

# 15. Heartbeat

O heartbeat possui duas funções:

1. confirmar saúde da conexão;
2. renovar leases associados à Session.

Intervalo inicial recomendado:

- Client envia heartbeat a cada **5 segundos**;
- lease inicial de **15 segundos**.

Esses valores são parâmetros de implementação e poderão ser ajustados após testes reais de latência e estabilidade.

Exemplo:

```json
{
  "vector": "1.0",
  "type": "system",
  "name": "system.heartbeat",
  "messageId": "msg_200",
  "timestamp": "2026-08-07T22:10:05.000Z",
  "sessionId": "sess_abc123",
  "payload": {
    "leases": ["lease_xyz789"]
  }
}
```

---

# 16. Respostas e Confirmações

Um comando não deve ser considerado executado apenas porque foi recebido.

Fluxo típico:

```text
COMMAND
  |
  +--> rejeitado --------> ERROR
  |
  +--> aceito/executado -> EVENT/RESPONSE confirmado
```

Comandos rápidos podem ser confirmados diretamente pelo evento resultante.

Comandos de longa duração podem utilizar resposta intermediária `accepted` seguida do evento final.

---

# 17. Idempotência

Comandos cujo reenvio possa causar efeitos indesejados devem utilizar `messageId` como chave de deduplicação durante uma janela de tempo definida.

Se o Gateway receber novamente um `messageId` já processado, deve retornar o resultado anterior quando possível e não executar novamente a operação.

Exemplo importante: reconexão enquanto o Client não sabe se o último comando foi processado.

---

# 18. Ordenação e Concorrência

Mensagens enviadas pela mesma Session sobre o mesmo Resource devem preservar ordenação lógica.

O Gateway é responsável por serializar comandos conflitantes quando necessário.

Exemplo:

```text
setFrequency(14074000)
setFrequency(14200000)
```

O estado final deve refletir o segundo comando, salvo erro explícito.

Nenhuma garantia global de ordenação entre Resources diferentes é necessária.

---

# 19. Erros

Erros utilizam envelope padrão.

```json
{
  "vector": "1.0",
  "type": "error",
  "name": "error",
  "messageId": "msg_301",
  "correlationId": "msg_300",
  "timestamp": "2026-08-07T22:20:00.000Z",
  "sessionId": "sess_abc123",
  "resourceId": "radio_puruna_01",
  "payload": {
    "code": "RESOURCE_BUSY",
    "message": "Resource is currently owned by another session",
    "retryable": true
  }
}
```

## 19.1 Códigos iniciais

```text
PROTOCOL_VERSION_UNSUPPORTED
AUTHENTICATION_REQUIRED
AUTHENTICATION_FAILED
AUTHORIZATION_DENIED
SESSION_INVALID
SESSION_EXPIRED
RESOURCE_NOT_FOUND
RESOURCE_OFFLINE
RESOURCE_BUSY
RESOURCE_NOT_OWNED
CAPABILITY_NOT_SUPPORTED
INVALID_ARGUMENT
COMMAND_REJECTED
DRIVER_ERROR
TIMEOUT
INTERNAL_ERROR
```

Os Clients devem tomar decisões pelo `code`, nunca pelo texto de `message`.

---

# 20. Reconexão

Perdas breves de conectividade são esperadas em operação remota.

O Vector Protocol deve permitir tentativa de recuperação de Session enquanto ela ainda for considerada válida pelo Gateway.

Fluxo:

```text
Connection lost
      |
      v
Client reconnects
      |
      v
system.hello
      |
      v
session.resume
      |
      +---- accepted ---> resync state
      |
      +---- rejected ---> new authentication
```

Após `session.resume`, o Gateway deve enviar um **snapshot atual** dos Resources pertencentes à Session antes que o Client volte a aceitar operações normais.

O Client nunca deve presumir que o estado anterior à desconexão permanece válido.

---

# 21. Sincronização Inicial de Estado

Após adquirir um Resource ou recuperar uma Session, o Gateway envia seu snapshot.

Exemplo:

```json
{
  "vector": "1.0",
  "type": "event",
  "name": "radio.stateSnapshot",
  "messageId": "evt_600",
  "timestamp": "2026-08-07T22:30:00.000Z",
  "sessionId": "sess_abc123",
  "resourceId": "radio_puruna_01",
  "payload": {
    "online": true,
    "frequencyHz": 14074000,
    "mode": "USB",
    "ptt": false,
    "split": false
  }
}
```

Snapshots devem ser distinguíveis de eventos incrementais.

---

# 22. Segurança Operacional

A segurança de uma estação remota é requisito central do protocolo.

## 22.1 Regras mínimas

- PTT OFF é o estado seguro padrão.
- Resource não pode receber comandos de alteração sem ownership válido.
- Session expirada perde imediatamente direito de controle.
- Gateway pode revogar ownership administrativamente.
- Gateway pode colocar Resource em `ADMIN_LOCK` ou `MAINTENANCE`.
- comandos recebidos após revogação devem ser rejeitados.
- credenciais nunca devem ser registradas em logs.
- timestamps e identificadores devem permitir auditoria posterior.

## 22.2 Controle local

O Gateway deve possuir autoridade para interromper imediatamente uma Session remota.

A operação local da estação deve poder prevalecer sobre controle remoto conforme políticas definidas para o site.

---

# 23. Auditoria

O Gateway deve registrar no mínimo:

- início e término de Session;
- autenticação bem-sucedida e falha;
- aquisição e liberação de Resource;
- PTT ON/OFF;
- revogações administrativas;
- erros críticos;
- reconexões e expiração de lease.

Mudanças de frequência e modo podem possuir política configurável de auditoria para evitar volume excessivo.

---

# 24. Compatibilidade Evolutiva

Novos campos de `payload` devem ser ignorados por Clients que não os conhecem, salvo quando marcados como necessários por uma nova versão major.

Política de versão proposta:

```text
1.x  = mudanças compatíveis
2.0  = mudança incompatível
```

O handshake determina a versão comum suportada.

---

# 25. Unidade e Representação de Dados

Para evitar ambiguidades:

- frequência: inteiro em **Hz**;
- potência: **W**;
- azimute: graus decimais `0 <= x < 360`;
- elevação: graus decimais conforme capability do rotor;
- timestamps: UTC ISO 8601;
- duração/timeout: segundos ou milissegundos explicitados no nome do campo;
- estados booleanos: `true` / `false`;
- identificadores: strings opacas, sem significado semântico obrigatório.

Nunca usar valores como `14.074` sem unidade explícita.

---

# 26. Capabilities

O protocolo é capability-driven.

O Client deve adaptar sua interface e comandos ao conjunto anunciado pelo Resource.

Exemplo futuro:

```json
{
  "capabilities": {
    "frequency": {
      "read": true,
      "write": true
    },
    "ptt": {
      "read": true,
      "write": true
    },
    "power": {
      "read": true,
      "write": false
    }
  }
}
```

Isso permite suportar equipamentos heterogêneos sem criar protocolos separados.

---

# 27. Operações Futuras

O Vector Protocol deve poder evoluir para suportar, sem alteração de conceito:

- rotores e elevação;
- amplificadores;
- antenna switches;
- interlocks;
- sensores ambientais;
- energia e UPS;
- áudio remoto;
- voice keyer;
- CW keying;
- câmeras;
- WebSDR;
- automações e macros;
- tracking de satélite;
- múltiplos operadores e cenários multi-op.

---

# 28. Fluxo Completo de Exemplo

```text
Vector Client                           Vector Gateway
     |                                        |
     |---- WebSocket/TLS -------------------->|
     |                                        |
     |---- system.hello --------------------->|
     |<--- system.helloAccepted --------------|
     |                                        |
     |---- session.authenticate ------------->|
     |<--- session.authenticated -------------|
     |                                        |
     |---- resource.list -------------------->|
     |<--- resource.listResult ---------------|
     |                                        |
     |---- resource.acquire(Radio1) --------->|
     |<--- resource.acquired -----------------|
     |<--- radio.stateSnapshot ---------------|
     |                                        |
     |---- radio.setFrequency(14074000) ----->|
     |<--- radio.frequencyChanged ------------|
     |                                        |
     |---- radio.setMode(USB) ---------------->|
     |<--- radio.modeChanged -----------------|
     |                                        |
     |---- radio.setPtt(true) ---------------->|
     |<--- radio.pttChanged(true) ------------|
     |                                        |
     |---- radio.setPtt(false) --------------->|
     |<--- radio.pttChanged(false) -----------|
     |                                        |
     |---- system.heartbeat ----------------->|
     |<--- system.heartbeatAck ---------------|
     |                                        |
     |---- resource.release ----------------->|
     |<--- resource.released -----------------|
```

---

# 29. Decisões da Versão 1

Para a primeira implementação do GADX Vector ficam adotadas como direção inicial:

- transporte persistente: **WebSocket**;
- segurança de transporte: **TLS / WSS**;
- serialização: **JSON UTF-8**;
- paradigma: **Commands + Responses + Events**;
- Gateway como fonte autoritativa de estado;
- ownership temporário por **lease**;
- heartbeat para saúde da Session e renovação de lease;
- frequência canônica em **Hz**;
- falha segura com prioridade absoluta para **PTT OFF**;
- protocolo independente de Hamlib e de CAT.

Essas decisões devem ser validadas pela prova de conceito antes da publicação da versão estável `Vector Protocol 1.0`.

---

# 30. Próximos Passos

Antes de considerar o Vector Protocol 1.0 estável deverão ser produzidos:

1. schemas formais das mensagens;
2. lista canônica de modos de rádio;
3. catálogo de capabilities;
4. política definitiva de autenticação;
5. política de lease e timeout validada em rede real;
6. testes de falha durante PTT;
7. testes de reconexão;
8. testes com N1MM e DXLog através do Vector Client;
9. testes de integração com Hamlib/rigctld;
10. suíte automatizada de compatibilidade de protocolo.

---

# Regra Fundamental

> **O Vector Protocol expressa o que o operador deseja fazer e o que o Resource realmente está fazendo. Ele nunca expõe ao Client a forma específica como o hardware realiza essa operação.**
