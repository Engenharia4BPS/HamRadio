# GADX Vector
# 12 - Decisões Arquiteturais

Versão: 1.0 (Draft)
Status: Ativo

---

# Objetivo

Este documento registra as principais **Architectural Decision Records (ADRs)** do GADX Vector.

O objetivo é preservar não apenas **o que foi decidido**, mas também **por que foi decidido** e quais consequências cada decisão produz sobre a arquitetura, implementação e evolução da plataforma.

As decisões deste documento são normativas para a implementação enquanto estiverem com status **Aceita**.

---

# Status possíveis

| Status | Significado |
|---|---|
| Proposta | Em análise, ainda não obrigatória |
| Aceita | Decisão vigente e obrigatória |
| Substituída | Substituída por uma ADR posterior |
| Depreciada | Mantida apenas por compatibilidade |
| Rejeitada | Avaliada e descartada |

---

# Índice

| ADR | Decisão | Status |
|---|---|---|
| ADR-001 | Vector Protocol independente do Hamlib | Aceita |
| ADR-002 | CAT como camada de compatibilidade no Client | Aceita |
| ADR-003 | Interface Web com serviço local nativo | Aceita |
| ADR-004 | Um Vector Gateway por Site | Aceita |
| ADR-005 | Identidade oficial GADX Vector | Aceita |
| ADR-006 | Resources e Drivers como abstração de hardware | Aceita |
| ADR-007 | Secure by Default | Aceita |
| ADR-008 | Hamlib/rigctld como backend oficial de rádio da v1 | Aceita |
| ADR-009 | Gateway como autoridade do estado | Aceita |
| ADR-010 | Controle exclusivo de Resource por Lease | Aceita |
| ADR-011 | Vector Protocol v1 sobre WSS + JSON UTF-8 | Aceita |
| ADR-012 | Máquinas de estados normativas | Aceita |
| ADR-013 | Capabilities em vez de suposições por tipo/modelo | Aceita |
| ADR-014 | Resource Profiles para características específicas | Aceita |
| ADR-015 | Fail-safe tem prioridade sobre continuidade operacional | Aceita |

---

# ADR-001 — Vector Protocol independente do Hamlib

**Data:** 2026-08-07  
**Status:** Aceita

## Contexto

O GADX Vector utilizará inicialmente Hamlib para controlar rádios físicos. Entretanto, tornar Hamlib o protocolo interno criaria acoplamento entre Client, Gateway e uma tecnologia externa específica.

## Decisão

A comunicação entre **Vector Client** e **Vector Gateway** utilizará um protocolo próprio, denominado **Vector Protocol**, independente do Hamlib.

## Motivo

Preservar a autonomia da plataforma e permitir novos backends sem alterações nos clientes.

## Consequências

- Hamlib pode ser substituído ou complementado futuramente.
- Vector Client não conhece `rigctld`.
- Vector API não expõe comandos Hamlib diretamente.
- O modelo de domínio permanece independente de fabricantes e bibliotecas externas.

---

# ADR-002 — CAT como camada de compatibilidade no Vector Client

**Data:** 2026-08-07  
**Status:** Aceita

## Contexto

N1MM, DXLog e outros softwares esperam controlar um rádio através de protocolos CAT e, frequentemente, uma porta COM.

## Decisão

A emulação CAT será implementada no **Vector Client**, funcionando como uma camada de borda destinada à compatibilidade com aplicações existentes.

## Motivo

Permitir que N1MM, DXLog e softwares semelhantes enxerguem o rádio remoto como se fosse um rádio local suportado.

## Consequências

- O núcleo do Vector não dependerá de um protocolo CAT específico.
- O modelo CAT emulado poderá evoluir sem alterar Gateway ou hardware remoto.
- A porta COM virtual é responsabilidade da camada nativa do Client.

---

# ADR-003 — Interface Web com serviço local nativo

**Data:** 2026-08-07  
**Status:** Aceita

## Contexto

A experiência de usuário deve ser moderna e multiplataforma, porém navegadores não conseguem fornecer diretamente determinadas integrações nativas, como COM virtual.

## Decisão

O Vector Client será composto por:

1. uma **interface Web** para operação e configuração;
2. um **serviço local nativo** para funções dependentes do sistema operacional.

## Consequências

- A maior parte do Client permanece multiplataforma.
- Integrações específicas de Windows, Linux ou macOS ficam isoladas.
- COM virtual e emulação local não contaminam a interface Web.

---

# ADR-004 — Um Vector Gateway por Site

**Data:** 2026-08-07  
**Status:** Aceita

## Decisão

Cada Site físico terá seu próprio **Vector Gateway**.

## Sites iniciais

- Guatupê
- Purunã
- Casa 68
- Estação de satélite

## Motivo

Manter a autoridade de controle próxima aos equipamentos físicos e permitir que cada Site opere de forma independente.

## Consequências

- O Gateway é responsável pelos Resources locais.
- Falhas entre Sites não devem necessariamente afetar os demais.
- Políticas e drivers podem variar por Site.

---

# ADR-005 — Identidade oficial da plataforma

**Data:** 2026-08-07  
**Status:** Aceita

## Decisão

**GADX** identifica o **Grupo Araucária de DX**.

**GADX Vector** é o nome oficial da plataforma de automação e operação remota desenvolvida pelo grupo.

Os componentes utilizarão a marca **Vector**, incluindo:

- Vector Gateway
- Vector Client
- Vector Protocol
- Vector API
- Vector SDK, quando aplicável

## Motivo

Separar claramente a identidade da organização da identidade do produto.

---

# ADR-006 — Resources e Drivers como abstração de hardware

**Data:** 2026-08-07  
**Status:** Aceita

## Contexto

A plataforma precisa controlar equipamentos de diferentes fabricantes, protocolos e categorias sem incorporar detalhes de hardware ao núcleo.

## Decisão

Todo equipamento ou serviço controlável será representado como um **Resource**.

O acesso a tecnologias externas ocorrerá por meio de **Drivers**.

## Regra arquitetural

```text
Vector API / Vector Protocol
          ↓
     Modelo de Domínio
          ↓
        Resource
          ↓
         Driver
          ↓
      Backend/Hardware
```

## Consequências

- API e protocolo manipulam domínio, não hardware.
- Novos fabricantes podem ser adicionados por Drivers.
- Testes podem utilizar Dummy/Simulator Drivers.

---

# ADR-007 — Secure by Default

**Data:** 2026-08-07  
**Status:** Aceita

## Decisão

Toda funcionalidade do GADX Vector deverá seguir o princípio **Secure by Default**.

## Regras derivadas

- WSS/TLS obrigatório em produção.
- Credenciais permanentes utilizadas apenas durante autenticação.
- Senhas nunca armazenadas em texto puro.
- Tokens temporários e revogáveis para sessões.
- Credenciais e tokens não aparecem em logs ou URLs.
- Certificados TLS devem ser validados.
- Operações críticas devem possuir auditoria.
- Segurança operacional prevalece diante de falha de comunicação.

## Armazenamento de senhas

Algoritmos adequados incluem:

- Argon2id, preferencial;
- bcrypt;
- scrypt.

MD5, SHA-1 ou SHA-256 puro não são mecanismos aceitáveis para armazenamento de senha.

---

# ADR-008 — Hamlib/rigctld como backend oficial de rádio da v1

**Data:** 2026-08-07  
**Status:** Aceita

## Decisão

Na primeira versão do GADX Vector, o backend oficial para controle de rádios será o **Hamlib**, preferencialmente através do daemon **rigctld**.

O acesso ocorrerá exclusivamente através do **Hamlib Driver**.

## Motivo

- Ampla cobertura de rádios.
- Evita reimplementação de protocolos CAT proprietários.
- Disponibiliza interface de rede através do `rigctld`.
- Permite concentrar o desenvolvimento em segurança, sessão, multiestação e automação.

## Consequências

- Hamlib é backend, não protocolo interno.
- `rigctld` deve permanecer na rede confiável do Site.
- `rigctld` não deverá ser exposto diretamente à Internet como interface pública do Vector.
- Outros Drivers poderão coexistir futuramente.

---

# ADR-009 — Vector Gateway como autoridade do estado

**Data:** 2026-08-07  
**Status:** Aceita

## Contexto

Em um sistema distribuído, Client, Gateway, Driver e hardware podem possuir percepções diferentes do estado de um equipamento.

## Decisão

O **Vector Gateway** será a fonte autoritativa do estado publicado aos Clients.

O estado deverá ser derivado, sempre que possível, da confirmação do Driver e do hardware físico.

## Princípio

> O Client solicita. O Gateway decide. O Driver executa. O hardware confirma. O Gateway publica o estado autoritativo.

## Consequências

- O Client não assume que um comando solicitado foi efetivamente aplicado.
- Comandos produzem intenção; Events representam fatos confirmados.
- Desired State e Observed State devem ser diferenciados quando necessário.

---

# ADR-010 — Controle exclusivo de Resource por Lease

**Data:** 2026-08-07  
**Status:** Aceita

## Contexto

Dois operadores controlando simultaneamente o mesmo rádio podem provocar condições imprevisíveis e perigosas.

## Decisão

Resources que exigem controle exclusivo utilizarão **Lease** associado a uma Session.

## Regras

- Somente o proprietário de Lease válido pode executar comandos de controle exclusivos.
- Heartbeat renova o Lease.
- Lease possui expiração configurável.
- Perda de Session ou expiração libera o Resource segundo as regras de fail-safe.

## Consequências

- Conflitos de operadores são prevenidos pelo Gateway.
- O controle não depende de bloqueios implementados no rádio físico.
- Observadores podem possuir acesso somente leitura sem adquirir ownership exclusivo.

---

# ADR-011 — Vector Protocol v1 sobre WSS + JSON UTF-8

**Data:** 2026-08-07  
**Status:** Aceita

## Decisão

A primeira versão do Vector Protocol utilizará:

- **WebSocket Secure (WSS)** como transporte em produção;
- **TLS** para confidencialidade e integridade;
- **JSON UTF-8** para representação das mensagens.

## Motivo

- Comunicação bidirecional em tempo real.
- Facilidade de implementação e diagnóstico.
- Integração natural com aplicações Web.
- Legibilidade durante desenvolvimento e troubleshooting.

## Consequências

- Protocolos binários, QUIC ou Protobuf poderão ser avaliados futuramente sem alterar o modelo de domínio.
- `ws://` sem TLS será permitido apenas em ambiente controlado de desenvolvimento quando explicitamente habilitado.

---

# ADR-012 — Máquinas de estados são normativas

**Data:** 2026-08-07  
**Status:** Aceita

## Decisão

Session, Gateway, Client, Resource, Lease e Resources especializados deverão obedecer às máquinas de estados definidas em `06-MaquinaDeEstados.md`.

## Regra

Uma transição não definida é inválida por padrão.

## Consequências

- Estados e transições podem gerar testes automatizados.
- API e Protocol devem respeitar as mesmas regras.
- O Gateway rejeitará operações incompatíveis com o estado atual.

---

# ADR-013 — Capabilities em vez de suposições por tipo ou modelo

**Data:** 2026-08-07  
**Status:** Aceita

## Contexto

Dois equipamentos da mesma categoria podem possuir funções completamente diferentes.

## Decisão

Clients e serviços deverão descobrir o que um Resource pode fazer através de **Capabilities**.

## Exemplo

Um Radio poderá anunciar:

```text
Frequency
Mode
PTT
Split
VFO
```

Outro Radio poderá anunciar apenas:

```text
Frequency
Mode
```

## Consequências

- Funcionalidades não serão presumidas apenas porque `type = Radio`.
- A interface poderá habilitar ou ocultar controles dinamicamente.
- Drivers devem anunciar somente capacidades realmente suportadas.

---

# ADR-014 — Resource Profiles para características específicas

**Data:** 2026-08-07  
**Status:** Aceita

## Decisão

Características específicas de modelos de equipamento poderão ser descritas através de **Resource Profiles** externos ao núcleo.

## Exemplos previstos

```text
profiles/radio/kenwood/ts440.yaml
profiles/radio/yaesu/ftdx10.yaml
profiles/radio/icom/ic7300.yaml
```

## Profiles podem registrar

- capabilities;
- limites de frequência;
- modos;
- VFOs;
- potência;
- parâmetros particulares;
- bugs conhecidos;
- workarounds.

## Consequências

- Novos equipamentos podem exigir apenas Profile e configuração de Driver.
- Particularidades não contaminam o modelo de domínio.
- Profiles não substituem confirmação dinâmica de capabilities pelo backend quando esta estiver disponível.

---

# ADR-015 — Fail-safe tem prioridade sobre continuidade operacional

**Data:** 2026-08-07  
**Status:** Aceita

## Contexto

O Vector controla equipamentos físicos capazes de transmitir RF e acionar sistemas de potência. Uma perda de comunicação não pode deixar o sistema em condição potencialmente perigosa.

## Decisão

Quando houver conflito entre continuidade de operação e segurança da estação, o sistema deverá priorizar o comportamento **fail-safe**.

## Exemplos

- Solicitar ou garantir PTT OFF quando possível.
- Interromper geração remota de CW/Voice Keyer.
- Colocar amplificador em Standby quando suportado e seguro.
- Expirar ou liberar Lease conforme política definida.
- Não declarar um estado como seguro sem confirmação quando a comunicação com o hardware estiver perdida.

## Consequências

- Fail-safe deve fazer parte dos testes de integração.
- O comportamento específico poderá variar por Resource e Driver.
- O sistema deve distinguir claramente **estado confirmado**, **estado desconhecido** e **estado desejado**.

---

# Política para novas ADRs

Uma nova ADR deve ser criada quando uma decisão:

- afetar múltiplos componentes;
- modificar contratos públicos;
- criar dependência tecnológica relevante;
- alterar segurança ou comportamento fail-safe;
- mudar modelo de domínio, protocolo ou API;
- substituir uma decisão existente.

Correções locais de implementação não precisam gerar ADR.

---

# Alteração de decisões existentes

ADRs aceitas não devem ser silenciosamente reescritas quando a arquitetura mudar.

Quando uma decisão for substituída:

1. criar nova ADR;
2. marcar a anterior como **Substituída**;
3. indicar explicitamente qual ADR a substituiu;
4. registrar impactos de migração e compatibilidade.

---

# Princípios arquiteturais consolidados

A arquitetura do GADX Vector deverá preservar os seguintes princípios:

1. **Hardware é abstraído por Resources.**
2. **Integrações externas ficam atrás de Drivers.**
3. **Hamlib é backend, não núcleo.**
4. **CAT é compatibilidade de borda.**
5. **O Gateway é a autoridade do estado.**
6. **O Client solicita; não presume sucesso.**
7. **Capabilities descrevem o que o Resource realmente suporta.**
8. **Leases evitam conflito de controle.**
9. **Segurança é padrão, não configuração opcional.**
10. **Fail-safe prevalece sobre disponibilidade.**
11. **Protocolos e APIs devem permanecer independentes de fabricantes.**
12. **Estados e transições devem ser explícitos e testáveis.**

---

# Regra final

> O GADX Vector deve permanecer uma plataforma de automação de estação, e não um conjunto de integrações específicas de equipamentos.

Novas funcionalidades devem ser incorporadas preservando a separação entre domínio, protocolo, API, Drivers e hardware físico.
