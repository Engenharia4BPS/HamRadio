# GADX Vector
# 05 - Vector Protocol

Versão: 1.0 (Draft)
Status: Em elaboração

---

# Objetivo

O Vector Protocol define a comunicação entre o **Vector Client**
e o **Vector Gateway**.

Seu objetivo é abstrair completamente o hardware físico,
permitindo que qualquer cliente controle recursos da estação
sem conhecer detalhes de implementação dos equipamentos.

O protocolo é orientado a comandos e eventos e permanece
independente de fabricantes, protocolos CAT ou da Hamlib.

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

---

# Transporte

A implementação oficial utiliza

• WebSocket Secure (WSS)

sobre

• TLS

com mensagens codificadas em

• JSON UTF-8

---

## Ambientes

Produção

WSS obrigatório.

Laboratório

WS permitido mediante configuração explícita.

---

# Arquitetura

```
N1MM / DXLog

↓

Vector Client

↓

Vector Protocol

↓

Vector Gateway

↓

Driver

↓

Hamlib

↓

rigctld

↓

Radio
```

---

# Modelo de Comunicação

Toda comunicação ocorre através de mensagens.

Existem apenas dois tipos:

• Commands

• Events

Commands representam uma intenção.

Events representam um fato ocorrido.

---

# Envelope das Mensagens

Todas as mensagens seguem o mesmo envelope.

```json
{
  "version":"1.0",
  "messageId":"uuid",
  "correlationId":"uuid",
  "timestamp":"2026-08-07T19:30:00Z",
  "session":"uuid",
  "resource":"radio-01",
  "type":"Command",
  "name":"SetFrequency",
  "payload":{}
}
```

---

## Campos

version

Versão do protocolo.

messageId

Identificador único da mensagem.

correlationId

Relaciona respostas ao comando original.

timestamp

Data UTC.

session

Sessão autenticada.

resource

Recurso alvo.

type

Command

ou

Event

name

Nome da operação.

payload

Dados específicos.

---

# Comandos

Exemplos

Authenticate

Heartbeat

AcquireResource

ReleaseResource

GetState

SetFrequency

SetMode

SetPTT

SetSplit

MoveRotor

PowerAmplifier

Disconnect

---

# Eventos

Exemplos

Authenticated

HeartbeatAck

ResourceAcquired

ResourceReleased

FrequencyChanged

ModeChanged

PTTChanged

RotorMoved

AmplifierFault

ResourceOffline

OperatorConnected

OperatorDisconnected

LeaseExpired

---

# Sessões

Após autenticação o Gateway cria uma sessão.

Cada sessão possui

Session ID

Lease

Permissões

Último Heartbeat

Estado

Estados possíveis

CREATED

AUTHENTICATED

ACTIVE

DISCONNECTED

TIMEOUT

CLOSED

---

# Lease

Recursos são adquiridos através de Lease.

O Lease garante exclusividade.

Enquanto existir Lease válido:

nenhum outro operador poderá controlar o recurso.

Caso expire

o Gateway libera automaticamente o recurso.

---

# Heartbeat

Heartbeat é enviado periodicamente.

Objetivos

renovar Lease

medir latência

confirmar disponibilidade

detectar desconexões

---

# Snapshot

Ao conectar

o Gateway envia o estado completo do recurso.

Após isso

somente eventos diferenciais.

---

# Ordenação

Mensagens possuem ordem lógica.

Commands

devem ser processados na ordem de recebimento.

Events

devem preservar a ordem de geração.

---

# Idempotência

Comandos repetidos com mesmo

messageId

não devem produzir efeitos duplicados.

---

# Segurança

## Filosofia

Toda funcionalidade do GADX Vector deve seguir o princípio

Secure by Default.

---

## Transporte Seguro

Produção

WSS obrigatório.

Laboratório

WS permitido apenas para desenvolvimento.

---

## Credenciais

Credenciais são consideradas informações sensíveis.

Regras

Usuário e senha nunca trafegam fora de TLS.

Usuário e senha nunca aparecem em logs.

Usuário e senha são utilizados apenas durante autenticação.

Após autenticação

o Gateway devolve um

Session Token

temporário.

Todas as mensagens seguintes utilizam apenas este token.

Tokens

possuem expiração.

podem ser revogados.

não aparecem em URLs.

não aparecem em logs.

---

## Armazenamento de Senhas

O Gateway nunca armazena senhas em texto puro.

Algoritmos aceitos

Argon2id

bcrypt

scrypt

Não permitidos

MD5

SHA1

SHA256 puro

---

## Certificados

O Client deve validar o certificado digital do Gateway.

Caso a validação falhe

a conexão deve ser encerrada.

---

## Autorização

Perfis previstos

Administrator

Operator

Guest

Monitor

Cada comando verifica permissões.

---

## Auditoria

Todos os comandos críticos devem gerar auditoria.

Exemplos

Login

Logout

AcquireResource

ReleaseResource

SetFrequency

SetMode

PTT

Rotor

Amplifier

Administração

---

## Segurança Operacional

Em qualquer perda de comunicação

o Gateway deve priorizar a segurança da estação.

PTT OFF imediatamente.

CW interrompido.

Voice Keyer interrompido.

Amplificador em Standby.

Rotor conclui movimento atual.

Lease expira.

Recurso liberado.

---

# Tratamento de Erros

Exemplos

INVALID_SESSION

ACCESS_DENIED

RESOURCE_BUSY

LEASE_EXPIRED

INVALID_COMMAND

UNSUPPORTED

INVALID_STATE

RESOURCE_OFFLINE

GATEWAY_BUSY

INTERNAL_ERROR

---

# Capabilities

Cada Resource anuncia suas capacidades.

Exemplo

Radio

Frequency

Mode

PTT

Split

CW

Voice

Rotor

Azimuth

Elevation

Tracking

---

# Versionamento

O protocolo utiliza

Semantic Versioning.

1.x

Compatível.

2.x

Quebra de compatibilidade.

---

# Compatibilidade

O Vector Protocol nunca dependerá de:

Hamlib

CAT

Kenwood

Icom

Yaesu

FlexRadio

Qualquer integração será realizada exclusivamente através de Drivers.

---

# Fluxo Simplificado

```
Client

↓

Authenticate

↓

Authenticated

↓

Acquire Resource

↓

Lease Granted

↓

Snapshot

↓

Heartbeat

↓

SetFrequency

↓

FrequencyChanged

↓

SetPTT ON

↓

PTTChanged

↓

Release Resource

↓

Disconnected
```

---

# Objetivo Final

O Vector Protocol expressa apenas:

o que o operador deseja fazer

e

o que realmente aconteceu.

Nunca como o hardware realiza a operação.

Todo acesso ao hardware ocorre exclusivamente através do Driver correspondente.
