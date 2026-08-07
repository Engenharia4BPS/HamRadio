# GADX Vector
# 06 - Máquina de Estados

**Versão:** 1.0 (Draft)  
**Status:** Em elaboração

---

# 1. Objetivo

Este documento define as máquinas de estados utilizadas pelo **GADX Vector**.

Seu objetivo é estabelecer, de forma determinística:

- quais estados cada entidade pode assumir;
- quais transições são válidas;
- quais eventos provocam transições;
- quais comandos podem solicitar transições;
- quais invariantes de segurança devem ser preservados;
- qual componente é autoridade sobre cada estado.

Toda implementação do **Vector Gateway** e do **Vector Client** deve obedecer a estas definições.

Estados e transições não definidos neste documento devem ser considerados inválidos até que sejam formalmente incorporados à especificação.

---

# 2. Princípios

1. **Comandos representam intenção.** Um comando solicita uma ação, mas não garante que a transição ocorrerá.
2. **Eventos representam fatos.** Uma transição confirmada deve produzir um evento correspondente quando relevante ao restante do sistema.
3. **O Vector Gateway é a autoridade do estado remoto.** O Client pode manter uma cópia local, mas não é a fonte autoritativa.
4. **O estado real do hardware prevalece sobre o estado desejado.** Se um Driver informar situação diferente da esperada, o domínio deve refletir o estado observado.
5. **Transições inválidas falham explicitamente.** Não devem ser corrigidas silenciosamente.
6. **Segurança operacional prevalece sobre continuidade.** Em situações ambíguas ou de falha, o sistema deve adotar a transição mais segura.
7. **Toda transição crítica deve ser auditável.**

---

# 3. Convenções

## 3.1 Tipos de transição

- **Normal:** parte do fluxo operacional esperado.
- **Falha:** provocada por erro de comunicação, Driver, hardware ou infraestrutura.
- **Segurança:** provocada para proteger pessoas, equipamentos ou espectro.
- **Administrativa:** provocada por operador autorizado para manutenção ou intervenção.

## 3.2 Resultado de uma solicitação

Uma solicitação de transição pode resultar em:

- transição confirmada;
- permanência no estado atual;
- erro de autorização;
- erro de estado inválido;
- erro de capacidade não suportada;
- falha operacional.

## 3.3 Eventos

Quando uma transição for observável por outros componentes, o Gateway deve emitir um evento correspondente pelo Vector Protocol.

---

# 4. Session State Machine

A **Session** representa uma relação autenticada entre um operador e um Vector Gateway.

## 4.1 Estados

| Estado | Descrição |
|---|---|
| `CREATED` | Estrutura de sessão criada, ainda sem autenticação válida. |
| `AUTHENTICATING` | Credenciais ou token estão sendo validados. |
| `AUTHENTICATED` | Identidade validada e token de sessão emitido. |
| `ACTIVE` | Sessão operacional e apta a emitir comandos autorizados. |
| `IDLE` | Sessão autenticada sem atividade operacional recente; heartbeat permanece válido. |
| `RECONNECTING` | Conexão caiu e existe tentativa válida de retomar a sessão. |
| `TIMEOUT` | Limite de heartbeat/reconexão foi excedido. |
| `DISCONNECTED` | Transporte encerrado, podendo ainda existir janela de retomada. |
| `CLOSED` | Sessão finalizada e não retomável. |

## 4.2 Fluxo principal

```text
CREATED
   |
   v
AUTHENTICATING
   |
   v
AUTHENTICATED
   |
   v
ACTIVE <------> IDLE
   |
   +------> RECONNECTING -----> ACTIVE
   |               |
   |               v
   |            TIMEOUT
   |               |
   v               v
DISCONNECTED ----> CLOSED
```

## 4.3 Matriz de transição

| Estado atual | Evento/condição | Próximo estado | Válido | Observação |
|---|---|---|:---:|---|
| `CREATED` | Início da autenticação | `AUTHENTICATING` | ✅ | Fluxo normal. |
| `AUTHENTICATING` | Credenciais válidas | `AUTHENTICATED` | ✅ | Token é emitido. |
| `AUTHENTICATING` | Credenciais inválidas | `CLOSED` | ✅ | Falha de autenticação. |
| `AUTHENTICATED` | Sessão habilitada | `ACTIVE` | ✅ | Operação liberada conforme permissões. |
| `ACTIVE` | Inatividade operacional | `IDLE` | ✅ | Heartbeat continua ativo. |
| `IDLE` | Novo comando válido | `ACTIVE` | ✅ | Retorno imediato à operação. |
| `ACTIVE` | Perda temporária de transporte | `RECONNECTING` | ✅ | Recursos permanecem sujeitos às regras de lease. |
| `RECONNECTING` | `session.resume` aceito | `ACTIVE` | ✅ | Snapshot deve ser reenviado. |
| `RECONNECTING` | Janela de retomada excedida | `TIMEOUT` | ✅ | Segurança operacional aplicada. |
| `TIMEOUT` | Limpeza da sessão | `CLOSED` | ✅ | Tokens e leases associados são invalidados. |
| `ACTIVE` | Logout | `CLOSED` | ✅ | Liberação ordenada dos recursos. |
| `CLOSED` | Qualquer operação | — | ❌ | Uma sessão fechada nunca é reativada. |

## 4.4 Invariantes

- `CLOSED` é terminal.
- Uma Session não controla Resources antes de `AUTHENTICATED`.
- Uma Session em `TIMEOUT` não pode emitir comandos de controle.
- Tokens revogados não podem restaurar uma Session.

---

# 5. Vector Gateway State Machine

## 5.1 Estados

| Estado | Descrição |
|---|---|
| `BOOTING` | Processo iniciado. |
| `INITIALIZING` | Configurações, Drivers e recursos estão sendo carregados. |
| `READY` | Gateway plenamente operacional. |
| `DEGRADED` | Gateway operacional parcialmente; um ou mais subsistemas apresentam falha. |
| `MAINTENANCE` | Operação normal bloqueada por intervenção administrativa. |
| `STOPPING` | Encerramento ordenado em andamento. |
| `OFFLINE` | Gateway indisponível. |

## 5.2 Fluxo principal

```text
BOOTING
   |
   v
INITIALIZING
   |
   +------> DEGRADED
   |
   v
 READY <------> DEGRADED
   |
   +------> MAINTENANCE
   |
   v
STOPPING
   |
   v
OFFLINE
```

## 5.3 Regras

- O Gateway só aceita novas operações de controle em `READY` ou, seletivamente, em `DEGRADED` quando o Resource solicitado estiver saudável.
- `MAINTENANCE` bloqueia novas aquisições de Resource salvo autorização administrativa explícita.
- Ao entrar em `STOPPING`, o Gateway inicia liberação segura de leases e força estados seguros nos equipamentos críticos.

---

# 6. Vector Client State Machine

## 6.1 Estados

| Estado | Descrição |
|---|---|
| `STARTING` | Aplicação iniciando. |
| `DISCONNECTED` | Sem conexão com Gateway. |
| `CONNECTING` | Abrindo transporte WebSocket. |
| `AUTHENTICATING` | Realizando autenticação. |
| `CONNECTED` | Transporte e autenticação válidos. |
| `SYNCING` | Recebendo snapshot e sincronizando estado local. |
| `READY` | Pronto para atender N1MM, DXLog e interface Web. |
| `RECONNECTING` | Tentando retomar conexão/sessão. |
| `ERROR` | Falha não recuperável automaticamente. |
| `STOPPING` | Encerramento local. |

## 6.2 Fluxo principal

```text
STARTING
   |
   v
DISCONNECTED
   |
   v
CONNECTING
   |
   v
AUTHENTICATING
   |
   v
CONNECTED
   |
   v
SYNCING
   |
   v
READY
   |
   +------> RECONNECTING ------> SYNCING
   |               |
   |               v
   |             ERROR
   v
STOPPING
```

## 6.3 Regra crítica

O Vector Client nunca deve apresentar ao software local um estado inferido como se fosse confirmado. Mudanças recebidas do N1MM/DXLog são intenções até que o Gateway confirme o estado real.

---

# 7. Resource State Machine

A máquina de estados de **Resource** é comum a todos os equipamentos controláveis.

## 7.1 Estados

| Estado | Descrição |
|---|---|
| `OFFLINE` | Driver/hardware inacessível. |
| `ONLINE` | Comunicação estabelecida, ainda não validada para uso. |
| `AVAILABLE` | Recurso saudável e disponível para aquisição. |
| `RESERVED` | Lease concedido a uma Session. |
| `IN_USE` | Resource sob controle ativo da Session proprietária. |
| `RELEASING` | Liberação ordenada em andamento. |
| `FAULT` | Falha funcional detectada. |
| `MAINTENANCE` | Recurso retirado administrativamente de operação. |

## 7.2 Fluxo principal

```text
OFFLINE
   |
   v
 ONLINE
   |
   v
AVAILABLE
   |
   v
RESERVED
   |
   v
 IN_USE
   |
   v
RELEASING
   |
   v
AVAILABLE
```

Transições de falha podem levar qualquer estado operacional para `FAULT` ou `OFFLINE`.

## 7.3 Matriz de transição

| Estado atual | Evento/condição | Próximo estado | Válido | Observação |
|---|---|---|:---:|---|
| `OFFLINE` | Driver conectado | `ONLINE` | ✅ | Comunicação restabelecida. |
| `ONLINE` | Health check OK | `AVAILABLE` | ✅ | Resource liberado para uso. |
| `ONLINE` | Health check falhou | `FAULT` | ✅ | Não pode ser adquirido. |
| `AVAILABLE` | `AcquireResource` autorizado | `RESERVED` | ✅ | Lease criado. |
| `RESERVED` | Lease ativado | `IN_USE` | ✅ | Controle concedido. |
| `RESERVED` | Lease cancelado/expirado | `RELEASING` | ✅ | Liberação segura. |
| `IN_USE` | `ReleaseResource` | `RELEASING` | ✅ | Encerramento ordenado. |
| `RELEASING` | Estado seguro confirmado | `AVAILABLE` | ✅ | Resource liberado. |
| `AVAILABLE` | `SetFrequency` | — | ❌ | Comando de controle exige `IN_USE`. |
| `RESERVED` | Comando operacional antes da ativação | — | ❌ | Ainda não está em uso. |
| `IN_USE` | Driver desconectado | `OFFLINE` | ✅ | Ações de segurança são aplicadas quando possível. |
| Qualquer operacional | Falha de hardware | `FAULT` | ✅ | Deve gerar evento. |
| `FAULT` | Recuperação confirmada | `ONLINE` | ✅ | Novo health check obrigatório. |
| `AVAILABLE` | Administração inicia manutenção | `MAINTENANCE` | ✅ | Bloqueia aquisições. |
| `MAINTENANCE` | Administração encerra manutenção | `ONLINE` | ✅ | Deve ser revalidado antes de `AVAILABLE`. |

## 7.4 Invariantes

- Um Resource possui no máximo **um lease de controle exclusivo**.
- Apenas a Session proprietária pode emitir comandos mutáveis durante `IN_USE`.
- `OFFLINE`, `FAULT` e `MAINTENANCE` não permitem novas aquisições normais.
- A saída de `IN_USE` deve levar o equipamento a um estado operacional seguro antes de `AVAILABLE`.

---

# 8. Lease State Machine

## 8.1 Estados

| Estado | Descrição |
|---|---|
| `CREATED` | Lease criado, ainda não ativado. |
| `ACTIVE` | Lease válido e garantindo ownership. |
| `RENEWING` | Renovação em processamento. |
| `EXPIRING` | Próximo ao vencimento; operação deve preparar contingência. |
| `EXPIRED` | Prazo ultrapassado; controle não é mais válido. |
| `RELEASING` | Liberação explícita em processamento. |
| `RELEASED` | Lease finalizado. Estado terminal. |
| `REVOKED` | Lease cancelado por política ou ação administrativa. Estado terminal. |

## 8.2 Fluxo

```text
CREATED
   |
   v
 ACTIVE <----> RENEWING
   |
   +------> EXPIRING
   |           |
   |           v
   |         EXPIRED
   |
   +------> RELEASING ------> RELEASED
   |
   +------> REVOKED
```

## 8.3 Regras temporais padrão

Os valores efetivos são configuráveis pelo Gateway e anunciados ao Client.

- Heartbeat sugerido: **5 s**.
- Lease sugerido: **15 s**.
- Estado `EXPIRING`: pode ser ativado quando restar menos de um heartbeat completo para o vencimento.
- O Client deve renovar antes do vencimento; nunca deve depender do último instante possível.

## 8.4 Segurança

Ao chegar a `EXPIRED` ou `REVOKED`, nenhum comando mutável do antigo proprietário é aceito.

Para recursos de transmissão, expiração ou revogação deve provocar imediatamente a política segura aplicável, incluindo `PTT OFF` quando tecnicamente possível.

---

# 9. Radio Operational State Machine

O Radio possui a máquina de Resource e, adicionalmente, estados operacionais próprios.

## 9.1 TX/RX

```text
RX ---- SetPTT(true) ----> TX
TX ---- SetPTT(false) ---> RX
```

### Estados

- `RX`: rádio não está transmitindo.
- `TX`: rádio está transmitindo.

### Regras críticas

- `TX` só é permitido quando o Resource está `IN_USE` e a Session possui permissão de transmissão.
- Perda da Session, expiração do Lease ou falha crítica deve resultar em tentativa imediata de `TX -> RX`.
- `SetPTT(false)` é um comando de segurança e deve possuir prioridade sobre comandos não críticos.
- O Gateway deve confirmar o estado observado do rádio por Driver quando a tecnologia suportar essa leitura.

## 9.2 Mode

Modos como `USB`, `LSB`, `CW`, `CW-R`, `AM`, `FM`, `RTTY`, `DIGI` e outros não são uma sequência obrigatória de estados. São valores mutuamente exclusivos da propriedade operacional `mode`.

A lista efetiva é determinada pelas **Capabilities** do Resource.

## 9.3 Split

```text
OFF <----> ON
```

A ativação de Split deve ser rejeitada quando o rádio/Driver não anunciar a capability correspondente.

---

# 10. Rotor Operational State Machine

## 10.1 Estados

| Estado | Descrição |
|---|---|
| `IDLE` | Parado e disponível. |
| `MOVING` | Movimento em curso. |
| `POSITIONING` | Aproximação/ajuste final, quando suportado. |
| `STOPPING` | Comando de parada em processamento. |
| `FAULT` | Falha operacional. |
| `RECOVERING` | Processo de recuperação/calibração. |

```text
IDLE
 |
 v
MOVING
 |
 +----> POSITIONING ----> IDLE
 |
 +----> STOPPING -------> IDLE
 |
 +----> FAULT ----> RECOVERING ----> IDLE
```

### Regras

- Limites mecânicos e zonas proibidas prevalecem sobre qualquer comando do Client.
- `STOP` deve ser tratado como comando de segurança de alta prioridade.
- Falha de comunicação não deve iniciar novo movimento.

---

# 11. Amplifier Operational State Machine

## 11.1 Estados

| Estado | Descrição |
|---|---|
| `OFF` | Desenergizado. |
| `STARTING` | Inicialização em andamento. |
| `STANDBY` | Energizado, transmissão bloqueada. |
| `READY` | Pronto para operação. |
| `TX` | Amplificando transmissão. |
| `FAULT` | Proteção/falha ativa. |
| `COOLING` | Recuperação térmica, quando aplicável. |
| `SHUTTING_DOWN` | Desligamento ordenado. |

```text
OFF -> STARTING -> STANDBY -> READY
                         |       |
                         |       v
                         |      TX
                         |       |
                         +<------+

READY/TX -> FAULT -> STANDBY ou OFF
READY -> SHUTTING_DOWN -> OFF
```

### Regras críticas

- `TX` só é permitido em estado compatível e sem interlocks ativos.
- `FAULT` prevalece sobre comandos do operador.
- Em perda de controle remoto, a política padrão deve favorecer `STANDBY` quando suportado.

---

# 12. Estado Autoritativo e Convergência

O GADX Vector distingue três conceitos:

1. **Desired State** — estado solicitado pelo Client.
2. **Command Accepted** — solicitação validada pelo Gateway.
3. **Observed State** — estado efetivamente observado através do Driver.

Exemplo:

```text
Client: SetFrequency(14.074 MHz)
        |
        v
Gateway valida comando
        |
        v
Driver envia comando ao rádio
        |
        v
Driver lê 14.074 MHz
        |
        v
Gateway atualiza estado autoritativo
        |
        v
FrequencyChanged(14.074 MHz)
```

O recebimento do comando pelo Gateway **não equivale** à confirmação de mudança do hardware.

Sempre que possível, a transição só deve ser considerada confirmada após observação ou confirmação confiável do Driver.

---

# 13. Falhas e Estados Seguros

## 13.1 Princípio Fail-Safe

Quando não for possível determinar com segurança o estado atual, o Gateway deve preferir a condição de menor risco operacional.

Exemplos:

- transmissão: `PTT OFF`;
- amplificador: `STANDBY` ou política segura configurada;
- novo movimento de rotor: bloqueado;
- novas aquisições: bloqueadas quando o Resource não está saudável;
- lease: expirado/revogado quando ownership não pode ser garantido.

## 13.2 Falha parcial

A falha de um Resource não deve necessariamente derrubar o Gateway inteiro. O Gateway pode permanecer `DEGRADED`, expondo apenas recursos saudáveis.

---

# 14. Concorrência

Para cada Resource de controle exclusivo:

- apenas uma transição de ownership pode estar em processamento por vez;
- `AcquireResource` concorrentes devem ser serializados pelo Gateway;
- apenas uma Session pode chegar a `IN_USE` para o mesmo Resource;
- comandos de uma Session antiga devem ser rejeitados imediatamente após troca, expiração ou revogação do lease.

---

# 15. Eventos de Transição

Eventos sugeridos:

- `SessionAuthenticated`
- `SessionResumed`
- `SessionTimedOut`
- `GatewayReady`
- `GatewayDegraded`
- `ResourceOnline`
- `ResourceAvailable`
- `ResourceReserved`
- `ResourceInUse`
- `ResourceReleasing`
- `ResourceReleased`
- `ResourceOffline`
- `ResourceFault`
- `LeaseGranted`
- `LeaseRenewed`
- `LeaseExpiring`
- `LeaseExpired`
- `LeaseRevoked`
- `PTTChanged`
- `RotorStateChanged`
- `AmplifierStateChanged`

Os nomes definitivos devem permanecer consistentes com o `05-Protocolo.md`.

---

# 16. Erros de Transição

Uma transição inválida deve retornar erro explícito, preferencialmente utilizando os códigos definidos no Vector Protocol.

Exemplos:

- `INVALID_STATE`
- `ACCESS_DENIED`
- `RESOURCE_BUSY`
- `LEASE_EXPIRED`
- `RESOURCE_OFFLINE`
- `UNSUPPORTED`
- `SAFETY_INTERLOCK`

Exemplo:

```json
{
  "type": "Error",
  "name": "INVALID_STATE",
  "payload": {
    "resource": "radio-01",
    "currentState": "AVAILABLE",
    "command": "SetFrequency",
    "requiredState": "IN_USE"
  }
}
```

---

# 17. Testabilidade

As matrizes deste documento devem ser usadas como fonte para testes automatizados.

Para cada entidade, a suíte de testes deve validar:

- todas as transições permitidas;
- rejeição de transições proibidas;
- estados terminais;
- comportamento em timeout;
- concorrência de leases;
- políticas fail-safe;
- emissão dos eventos esperados;
- consistência entre estado do Gateway e estado observado pelo Driver.

---

# 18. Regra Fundamental

> **O Client solicita. O Gateway decide. O Driver executa. O hardware confirma. O Gateway publica o estado autoritativo.**

Essa regra deve orientar toda implementação de transições no GADX Vector.

---

# 19. Objetivo Final

A Máquina de Estados do GADX Vector deve garantir que sessões, recursos e equipamentos físicos se comportem de maneira:

- previsível;
- determinística;
- auditável;
- testável;
- resiliente;
- segura.

O propósito não é apenas representar estados, mas impedir que condições inválidas ou perigosas sejam alcançadas durante a operação real da estação.
