# GADX Vector
# 13 - Glossário

Versão: 1.0 (Draft)

---

# Objetivo

Este documento estabelece a terminologia oficial utilizada na documentação, no código, nas interfaces e nas discussões técnicas do **GADX Vector**.

Quando um termo definido neste glossário for utilizado em documentos normativos do projeto, deverá conservar o significado descrito aqui.

---

# Identidade e Plataforma

## GADX
**Grupo Araucária de DX.** Organização responsável pelo desenvolvimento e manutenção do GADX Vector.

GADX identifica o grupo; não é o nome da plataforma.

## GADX Vector
Plataforma de automação, integração e operação remota de estações de radioamador desenvolvida pelo Grupo Araucária de DX.

## Vector
Forma curta permitida para se referir ao **GADX Vector** quando o contexto não gerar ambiguidade.

## Vector Gateway
Serviço instalado em cada Site físico. É responsável pela autoridade local sobre Resources, Sessions, Leases, políticas, segurança operacional e integração com equipamentos locais através de Drivers.

## Vector Client
Componente executado no computador do operador. É responsável pela integração do operador com a plataforma, incluindo interface Web e serviços locais necessários para funcionalidades não oferecidas diretamente pelo navegador, como COM virtual.

## Vector Protocol
Protocolo interno bidirecional utilizado principalmente entre Vector Client e Vector Gateway.

Na versão 1, utiliza WebSocket Secure (WSS), TLS e mensagens JSON UTF-8.

O Vector Protocol é independente de Hamlib, CAT e fabricantes específicos.

## Vector API
Interface normalizada de aplicação do GADX Vector. Expõe operações do domínio sem exigir que aplicações consumidoras conheçam Hamlib, CAT ou detalhes do equipamento físico.

---

# Organização Física

## Site
Local físico que hospeda um Vector Gateway e seus Resources.

Sites iniciais previstos incluem Guatupê, Purunã, Casa 68 e Estação de Satélite.

## Gateway por Site
Princípio arquitetural segundo o qual cada Site possui seu próprio Vector Gateway, que permanece como autoridade local sobre os equipamentos daquele local.

---

# Recursos e Domínio

## Resource
Abstração universal de qualquer equipamento, dispositivo ou serviço que possa ser representado, monitorado ou controlado pelo GADX Vector.

Exemplos: Radio, Rotor, Amplifier, AntennaSwitch, Relay, Sensor e PowerController.

## Resource Type
Categoria funcional de um Resource, como `Radio`, `Rotor`, `Amplifier` ou `Sensor`.

O tipo descreve a natureza do Resource, mas não determina sozinho suas funcionalidades disponíveis.

## Resource ID
Identificador único e estável de um Resource dentro do domínio Vector.

## Resource Profile
Descrição declarativa das características conhecidas de um modelo de equipamento.

Pode conter capabilities esperadas, limites, bandas, VFOs, potência, propriedades, peculiaridades e workarounds.

Um Profile auxilia a integração, mas não substitui a descoberta das capabilities efetivamente disponíveis em tempo de execução.

## Property
Valor observável ou configurável pertencente a um Resource.

Exemplos: frequência, modo, azimute, temperatura e potência.

## Capability
Capacidade funcional efetivamente anunciada por um Resource.

Exemplos: `Frequency`, `Mode`, `PTT`, `Split`, `Azimuth`, `Elevation` e `Power`.

Capabilities são a fonte de verdade funcional: uma operação somente deve ser oferecida quando a capability correspondente estiver disponível.

## Command
Solicitação para que o sistema execute uma operação ou tente produzir uma mudança de estado.

Um Command expressa intenção; não constitui confirmação de que a operação ocorreu.

## Event
Mensagem que representa um fato observado ou uma mudança efetivamente reconhecida pelo sistema.

Exemplos: `FrequencyChanged`, `PTTChanged`, `LeaseExpired` e `ResourceOffline`.

## Snapshot
Representação completa do estado conhecido de um Resource ou conjunto de Resources em determinado instante.

É utilizado principalmente durante sincronização inicial ou recuperação após reconexão.

## Dependency
Relação em que a operação segura ou válida de um Resource depende do estado ou disponibilidade de outro Resource.

---

# Estado

## State
Condição atual reconhecida de uma entidade do domínio.

As transições relevantes devem obedecer às máquinas de estado definidas pelo projeto.

## Desired State
Estado ou valor solicitado pelo Gateway ao Driver.

Representa a intenção de controle e não deve ser confundido com confirmação do hardware.

## Observed State
Estado ou valor efetivamente observado pelo Driver no backend ou equipamento.

## Authoritative State
Estado que o Vector Gateway reconhece e publica como verdade operacional do sistema após considerar a confirmação disponível do Driver/hardware.

O Gateway é a autoridade sobre o estado publicado para Clients.

## State Transition
Mudança válida entre dois estados definida pela máquina de estados correspondente.

## State Transition Matrix
Tabela normativa que define quais eventos ou comandos podem provocar cada transição de estado.

## Health
Condição de saúde operacional de um Resource ou componente.

Estados típicos incluem `Healthy`, `Warning`, `Critical` e `Offline`.

## Fault
Condição de falha detectada que pode impedir ou restringir a operação normal de um Resource.

## Degraded
Estado no qual um componente continua operacional, porém com parte de suas funções indisponíveis ou degradadas.

---

# Sessões, Concorrência e Controle

## Session
Contexto autenticado de comunicação entre um operador/Client e o Vector Gateway.

## Session Token
Credencial temporária emitida após autenticação e utilizada para identificar e autorizar uma Session sem retransmitir continuamente a senha do usuário.

## Session Resume
Mecanismo que permite tentar recuperar uma Session após perda temporária de conectividade, respeitando regras de validade, segurança e estado do Lease.

## Lease
Concessão temporária e renovável que autoriza uma Session a controlar determinado Resource.

O Lease evita que múltiplos operadores comandem simultaneamente o mesmo Resource quando isso não for permitido.

## Ownership
Vínculo operacional que identifica qual Session possui o direito corrente de controle de um Resource.

## Acquire Resource
Operação utilizada para solicitar um Lease sobre um Resource.

## Release Resource
Operação utilizada para devolver voluntariamente o controle de um Resource.

## Heartbeat
Mensagem periódica utilizada para verificar conectividade e manter viva uma Session e/ou Lease conforme as regras do protocolo.

A ausência de heartbeat dentro dos limites configurados pode provocar timeout, expiração de Lease e ações de segurança.

## Timeout
Condição produzida quando uma operação ou comunicação não é concluída dentro do intervalo permitido.

## Idempotência
Propriedade pela qual a repetição segura da mesma solicitação identificada não produz efeitos adicionais indevidos.

## Correlation ID
Identificador utilizado para relacionar uma resposta ou evento à solicitação que lhe deu origem.

## Message ID
Identificador único de uma mensagem do Vector Protocol.

---

# Drivers e Backends

## Driver
Camada de adaptação que traduz operações e estados entre o Modelo de Domínio do Vector e uma tecnologia, protocolo, biblioteca ou equipamento específico.

Drivers isolam o núcleo da plataforma de detalhes externos.

## Driver Interface
Contrato comum que todo Driver deve implementar para integrar-se ao Vector Gateway.

## Driver Manager
Componente responsável pelo ciclo de vida, registro, inicialização, monitoramento e encerramento dos Drivers no Gateway.

## Backend
Tecnologia externa utilizada por um Driver para executar operações sobre um equipamento.

## Hamlib
Projeto open source que fornece uma camada padronizada para controle de diversos equipamentos de radioamador.

Na v1, é o backend oficial para controle de rádios do GADX Vector.

## Hamlib Driver
Driver oficial inicial para Resources do tipo Radio.

Traduz operações normalizadas do Vector para o backend Hamlib, preferencialmente através de `rigctld`.

## rigctld
Daemon TCP fornecido pelo Hamlib que disponibiliza funções de controle de rádio através de uma interface de rede.

No Vector, deve permanecer na rede confiável do Site e não deve ser exposto diretamente à Internet como interface pública.

## Dummy Driver
Driver sem hardware real utilizado para desenvolvimento, testes e validação do comportamento do núcleo.

## Simulator Driver
Driver capaz de simular comportamento, estados, latência e falhas de equipamentos para testes mais completos.

## Discovery
Processo de identificação de Resources, propriedades ou capabilities disponíveis através de um Driver/backend.

## Polling
Consulta periódica realizada pelo Driver para observar propriedades ou estados que o backend não publica espontaneamente.

## Reconciliation
Processo de comparar Desired State e Observed State e atualizar o estado autoritativo conforme o resultado real da operação.

---

# Rádio e Compatibilidade

## Radio
Resource que representa um transceptor ou receptor controlável pela plataforma.

## CAT
**Computer Aided Transceiver.** Termo utilizado para protocolos de controle de transceptores por software.

## Emulação CAT
Camada de compatibilidade que apresenta ao software legado um protocolo CAT conhecido enquanto traduz as operações para o domínio Vector.

## COM Virtual
Porta serial virtual apresentada ao sistema operacional e a aplicações como se fosse uma interface serial física.

No Vector Client, será utilizada principalmente para compatibilidade com aplicações de radioamador que esperam comunicação CAT serial.

## N1MM Logger+
Software de contest prioritário para compatibilidade do Vector Client através da camada CAT/COM virtual.

## DXLog
Software de contest prioritário para compatibilidade do Vector Client através da camada CAT/COM virtual.

## PTT
**Push-To-Talk.** Estado/comando que coloca um transmissor em transmissão.

Por representar uma operação crítica, PTT está sujeito às regras de Lease, autorização, confirmação de estado e fail-safe.

## VFO
**Variable Frequency Oscillator.** Contexto de frequência selecionável em rádios que suportam múltiplos VFOs.

## Split
Modo de operação no qual transmissão e recepção utilizam frequências ou VFOs distintos.

---

# Segurança

## Secure by Default
Princípio segundo o qual funcionalidades do GADX Vector devem nascer com configurações seguras por padrão, sem depender de ação adicional do usuário para proteger credenciais e operações críticas.

## TLS
**Transport Layer Security.** Protocolo criptográfico utilizado para proteger confidencialidade e integridade das comunicações.

## WSS
**WebSocket Secure.** WebSocket protegido por TLS. É obrigatório para o Vector Protocol em produção.

## Authentication
Processo de comprovar a identidade de um usuário ou componente.

## Authorization
Processo de determinar quais operações uma identidade autenticada possui permissão para executar.

## Audit Log
Registro de segurança e rastreabilidade de operações relevantes, como autenticação, aquisição de Resource, PTT e alterações administrativas.

Credenciais e tokens sensíveis não devem ser gravados no Audit Log.

## Fail-safe
Comportamento de segurança adotado quando o sistema perde informações suficientes para garantir uma operação segura.

A segurança da estação possui prioridade sobre a continuidade operacional.

## PTT OFF
Estado seguro esperado para transmissão quando uma condição de falha exige interromper TX.

O Vector não deve declarar PTT OFF como confirmado se perdeu a capacidade de observar o estado real do equipamento.

## mTLS
**Mutual TLS.** Extensão de TLS na qual cliente e servidor apresentam certificados. É uma evolução de segurança prevista, mas não obrigatória na primeira versão.

---

# Rede e Comunicação

## WebSocket
Protocolo de comunicação bidirecional persistente utilizado pelo Vector Protocol.

## JSON
Formato textual estruturado utilizado para mensagens do Vector Protocol v1.

## REST
Estilo de interface HTTP utilizado pela Vector API para operações adequadas ao modelo request/response.

## Reconnection
Processo de restabelecer comunicação após perda de conectividade.

Reconectar transporte não significa automaticamente recuperar Session, Lease ou Ownership anteriores.

## Latency
Tempo decorrido entre envio e recebimento/processamento de informações através da comunicação remota.

---

# Desenvolvimento e Arquitetura

## ADR
**Architecture Decision Record.** Registro de uma decisão arquitetural relevante, incluindo contexto, decisão, motivos e consequências.

## MVP
**Minimum Viable Product.** Menor conjunto funcional capaz de validar a proposta central do produto.

## Spike
Atividade de pesquisa técnica limitada cujo objetivo é reduzir incerteza antes de uma decisão ou implementação.

## Technical Story
Item de backlog voltado principalmente a uma necessidade técnica ou arquitetural.

## User Story
Descrição de uma necessidade do produto a partir da perspectiva de um usuário ou papel do sistema.

## Definition of Done
Conjunto mínimo de critérios que deve ser atendido para que uma funcionalidade seja considerada concluída.

## Capability-driven Design
Abordagem em que interfaces e operações disponíveis são determinadas pelas capabilities efetivamente anunciadas pelos Resources, e não apenas pelo seu tipo ou modelo.

---

# Regra de Terminologia

A documentação e o código devem preferir os termos oficiais deste glossário.

Em especial:

- **GADX** = Grupo Araucária de DX.
- **GADX Vector** = plataforma.
- **Vector Gateway** = autoridade local de um Site.
- **Vector Client** = componente do operador.
- **Resource** = abstração de equipamento ou serviço.
- **Driver** = adaptador entre Vector e backend/hardware.
- **Capability** = função efetivamente disponível.
- **Desired State** = intenção.
- **Observed State** = estado observado.
- **Authoritative State** = estado reconhecido e publicado pelo Gateway.
- **Lease** = direito temporário de controle.

Termos novos que adquirirem significado arquitetural específico deverão ser adicionados a este documento.