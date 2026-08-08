# GADX Vector
# 08 - Drivers

Versão: 1.0 (Draft)  
Status: Em elaboração

---

# Objetivo

Este documento define a arquitetura de **Drivers** do GADX Vector e o contrato entre o núcleo da plataforma e tecnologias externas de controle de equipamentos.

O Driver é a única camada autorizada a conhecer detalhes de implementação de fabricantes, bibliotecas, protocolos ou serviços externos.

A **Vector API**, o **Vector Protocol**, o **Modelo de Domínio** e as **Máquinas de Estado** NÃO devem depender diretamente de Hamlib, rigctld, CAT, CI-V ou qualquer tecnologia equivalente.

> **Regra central:** o domínio solicita uma operação normalizada; o Driver traduz essa operação para o backend específico, observa a resposta real do equipamento e devolve ao Gateway um estado normalizado.

---

# 1. Posição na arquitetura

```text
N1MM / DXLog
      |
      v
Vector Client
      |
      v
Vector Protocol / Vector API
      |
      v
Vector Gateway
      |
      v
Modelo de Domínio
      |
      v
Driver Interface
      |
      +---------------------------+
      |                           |
      v                           v
Hamlib Driver                Outros Drivers
      |
      v
rigctld
      |
      v
Hamlib
      |
      v
Rádio físico
```

O Vector Gateway conhece apenas o contrato de Driver. Ele não deve conter regras específicas de Hamlib ou de fabricantes.

---

# 2. Backend oficial da primeira versão

O backend oficial para controle de rádios na primeira versão do GADX Vector será:

**Hamlib + rigctld**

O acesso preferencial será feito através do daemon `rigctld`, utilizando conexão TCP dentro do site onde o equipamento está instalado.

O Hamlib será tratado como uma dependência externa do **Hamlib Driver**, e não como protocolo interno da plataforma.

## 2.1 Motivos

- Ampla quantidade de rádios suportados.
- Evita reimplementação de protocolos CAT de diversos fabricantes.
- Permite padronizar operações de rádios heterogêneos.
- Já suporta operação em rede através do `rigctld`.
- Facilita testes com equipamentos diferentes sem alterar o núcleo do Vector.

---

# 3. Princípios dos Drivers

Todo Driver deve seguir estes princípios:

1. **Isolamento** — detalhes do backend não vazam para o domínio.
2. **Normalização** — entradas e saídas são convertidas para modelos Vector.
3. **Capability-driven** — apenas funções realmente suportadas são anunciadas.
4. **Estado confirmado** — comando enviado não significa estado alterado; sempre que possível, o estado deve ser confirmado pelo equipamento/backend.
5. **Fail-safe** — falhas devem priorizar segurança operacional.
6. **Reconexão** — perda temporária do backend não deve exigir reinicialização do Gateway.
7. **Observabilidade** — saúde, latência e erros devem ser mensuráveis.
8. **Testabilidade** — todo Driver deve poder ser substituído por mocks/simuladores.
9. **Sem credenciais em logs** — dados sensíveis nunca devem ser registrados.
10. **Sem acesso externo direto** — backends locais como `rigctld` não devem ser expostos diretamente à Internet pelo Vector.

---

# 4. Contrato lógico de Driver

Todo Driver deve oferecer, conceitualmente, as seguintes operações básicas.

```text
initialize()
connect()
disconnect()
healthCheck()
discoverCapabilities()
readState()
execute(command)
recover()
shutdown()
```

A implementação concreta poderá utilizar classes, interfaces, traits ou mecanismos equivalentes conforme a linguagem escolhida.

## 4.1 initialize

Carrega configuração, valida dependências e prepara o Driver.

Não implica necessariamente conexão com o equipamento.

## 4.2 connect

Estabelece comunicação com o backend.

No Hamlib Driver, normalmente representa a conexão TCP com uma instância de `rigctld`.

## 4.3 healthCheck

Verifica se o backend continua acessível e funcional.

O health check não deve causar alteração no equipamento.

## 4.4 discoverCapabilities

Descobre quais funcionalidades podem ser oferecidas pelo Resource.

O resultado deve ser convertido para **Capabilities Vector**.

## 4.5 readState

Obtém o estado observado do equipamento.

Para um rádio, pode incluir:

- frequência;
- modo;
- largura de filtro;
- VFO;
- split;
- PTT;
- potência, quando suportada;
- outros estados anunciados por capabilities.

## 4.6 execute

Recebe um comando normalizado do domínio Vector e o traduz para o backend.

Exemplo:

```text
Vector Command
SetFrequency(14074000)
        |
        v
Hamlib Driver
        |
        v
rigctld command
        |
        v
Radio
```

## 4.7 recover

Executa procedimentos de recuperação após perda de comunicação ou erro transitório.

## 4.8 shutdown

Finaliza o Driver de forma segura, fechando conexões e executando ações de segurança quando aplicável.

---

# 5. Estados do Driver

Um Driver deve possuir estado próprio, independente do estado do Resource.

Estados mínimos:

```text
UNINITIALIZED
INITIALIZING
DISCONNECTED
CONNECTING
READY
DEGRADED
RECONNECTING
FAULT
STOPPING
STOPPED
```

## Regras principais

- Apenas `READY` permite execução normal de comandos.
- `DEGRADED` pode permitir leitura parcial, mas deve restringir operações inseguras.
- `FAULT` torna o Resource indisponível até recuperação ou intervenção.
- Mudanças do estado do Driver devem refletir no estado autoritativo do Resource quando relevantes.

---

# 6. Hamlib Driver

O **Hamlib Driver** é a implementação de referência para Resources do tipo `Radio` na versão inicial.

## 6.1 Topologia recomendada

Cada rádio pode possuir sua própria instância de `rigctld`, com endereço e porta configuráveis.

Exemplo conceitual:

```text
Vector Gateway
   |
   +-- Hamlib Driver: radio-01 --> 127.0.0.1:4532 --> rigctld --> Rádio 1
   |
   +-- Hamlib Driver: radio-02 --> 127.0.0.1:4533 --> rigctld --> Rádio 2
   |
   +-- Hamlib Driver: radio-03 --> 192.168.10.25:4532 --> rigctld --> Rádio 3
```

O Gateway não deve assumir portas fixas. Host, porta e demais parâmetros são configuração do Resource/Driver.

## 6.2 Comunicação

O Driver deve manter conexão TCP controlada com `rigctld` e implementar:

- timeout de conexão;
- timeout de comando;
- detecção de socket fechado;
- reconexão com backoff;
- validação de respostas;
- serialização de comandos quando necessária;
- proteção contra comandos concorrentes conflitantes.

---

# 7. Operações mínimas do Hamlib Driver v1

O Hamlib Driver v1 deve implementar, quando suportado pelo rádio:

| Operação Vector | Objetivo |
|---|---|
| `GetState` | Obter estado atual do rádio |
| `GetFrequency` | Ler frequência |
| `SetFrequency` | Alterar frequência |
| `GetMode` | Ler modo |
| `SetMode` | Alterar modo |
| `GetPTT` | Ler estado de PTT |
| `SetPTT` | Ativar/desativar PTT |
| `GetSplit` | Ler estado de split |
| `SetSplit` | Ativar/desativar split |
| `GetVFO` | Ler VFO ativo, quando disponível |
| `SetVFO` | Alterar VFO, quando suportado |

Funções adicionais serão adicionadas conforme as capabilities reais e as necessidades do GADX Vector.

---

# 8. Capabilities

O Driver é responsável por informar ao domínio quais funções estão realmente disponíveis.

Exemplo normalizado:

```json
{
  "resourceId": "radio-01",
  "driver": "hamlib",
  "capabilities": [
    "radio.frequency.read",
    "radio.frequency.write",
    "radio.mode.read",
    "radio.mode.write",
    "radio.ptt.read",
    "radio.ptt.write",
    "radio.split.read",
    "radio.split.write"
  ]
}
```

Uma função que não é suportada pelo backend ou pelo rádio **não deve ser anunciada**.

O Client nunca deve precisar saber qual comando Hamlib corresponde a uma Capability.

---

# 9. Mapeamento e normalização

O Hamlib Driver deve possuir uma camada explícita de mapeamento entre:

```text
Vector Domain <-> Hamlib Driver <-> rigctld/Hamlib
```

Exemplos:

| Domínio Vector | Backend |
|---|---|
| Frequência em Hz | valor de frequência Hamlib |
| `USB` | modo correspondente do Hamlib |
| `LSB` | modo correspondente do Hamlib |
| `CW` | modo correspondente do Hamlib |
| `DIGI` | modo digital compatível disponível |
| `PTT=true` | comando de PTT do backend |
| `PTT=false` | desligamento de PTT |

As particularidades de nomenclatura e sintaxe ficam exclusivamente dentro do Driver.

---

# 10. Estado desejado e estado observado

O Driver deve distinguir:

- **Desired State** — o que o Gateway solicitou;
- **Observed State** — o que foi efetivamente observado no backend/equipamento.

Exemplo:

```text
Gateway -> SetFrequency(14074000)
             |
             v
Driver envia comando
             |
             v
Driver consulta/confirma estado
             |
             v
ObservedFrequency = 14074000
             |
             v
Gateway publica FrequencyChanged
```

O evento de sucesso deve representar o estado observado, não apenas o envio do comando.

Quando a confirmação não for tecnicamente possível, essa limitação deve ser conhecida pelo Driver e refletida na confiabilidade do estado.

---

# 11. Polling e atualização de estado

Como equipamentos e backends podem variar em sua capacidade de publicar mudanças espontâneas, o Driver poderá utilizar polling.

A frequência de polling deve ser configurável.

Valores muito agressivos devem ser evitados para não sobrecarregar:

- interface serial;
- rádio;
- `rigctld`;
- rede local;
- CPU do Gateway.

Mudanças observadas devem gerar eventos Vector somente quando houver alteração de estado relevante.

Exemplo:

```text
Polling
  |
  v
Frequency mudou?
  |
  +-- não --> nenhum evento
  |
  +-- sim --> FrequencyChanged
```

---

# 12. Concorrência

O Driver não é responsável por decidir quem pode controlar um Resource.

Essa autorização pertence ao **Vector Gateway**, às Sessions e aos Leases.

Porém, depois de autorizado, o Driver deve garantir execução segura de comandos concorrentes.

Comandos que não possam ser executados simultaneamente devem ser serializados.

Operações críticas como PTT devem possuir prioridade adequada e comportamento determinístico.

---

# 13. Timeouts

Os tempos devem ser configuráveis por Driver/Resource.

Defaults iniciais sugeridos para desenvolvimento:

| Parâmetro | Default inicial |
|---|---:|
| Connect timeout | 3 s |
| Command timeout | 2 s |
| Health check interval | 5 s |
| Reconnect initial delay | 1 s |
| Reconnect maximum delay | 30 s |

Esses valores são defaults de engenharia e poderão ser ajustados após medições reais.

Timeout não deve ser confundido com confirmação de falha definitiva do equipamento.

---

# 14. Reconexão

Ao perder comunicação com `rigctld`, o Hamlib Driver deve:

1. marcar a conexão como indisponível;
2. informar o Gateway;
3. colocar o Resource em estado seguro apropriado;
4. iniciar tentativas de reconexão com backoff;
5. ao reconectar, redescobrir capabilities quando necessário;
6. obter um novo snapshot completo;
7. reconciliar o estado observado;
8. somente então retornar o Resource a um estado operacional.

O Driver não deve assumir que o equipamento permaneceu no mesmo estado durante a desconexão.

---

# 15. Segurança operacional

Falhas de Driver não podem deixar a estação em condição deliberadamente insegura.

## 15.1 PTT

`PTT OFF` é uma operação de segurança prioritária.

Em situações como:

- encerramento voluntário da Session;
- Lease expirado;
- desligamento controlado do Gateway;
- falha recuperável em que o backend ainda responde;

...o sistema deve tentar garantir `PTT OFF` antes da liberação definitiva do Resource.

Se a comunicação com o equipamento foi completamente perdida, o Vector deve registrar que não foi possível confirmar o estado físico do PTT e elevar o incidente para condição de falha operacional.

> O software não deve declarar `PTT OFF` como estado observado quando não houver evidência suficiente para confirmá-lo.

## 15.2 Amplificadores e outros equipamentos

Drivers futuros devem adotar comportamento fail-safe equivalente apropriado ao tipo do equipamento.

---

# 16. Tratamento de erros

Erros de backend devem ser normalizados para erros Vector.

Exemplo:

| Situação do backend | Erro Vector sugerido |
|---|---|
| Backend sem conexão | `DRIVER_DISCONNECTED` |
| Timeout | `DRIVER_TIMEOUT` |
| Comando não suportado | `UNSUPPORTED_CAPABILITY` |
| Resposta inválida | `DRIVER_PROTOCOL_ERROR` |
| Equipamento indisponível | `RESOURCE_OFFLINE` |
| Erro não recuperável | `DRIVER_FAULT` |

Detalhes internos podem ser registrados em logs técnicos, mas não devem vazar desnecessariamente para Clients.

---

# 17. Observabilidade

Cada Driver deve expor métricas e diagnóstico suficientes para operação.

Informações úteis incluem:

- estado do Driver;
- uptime da conexão;
- última comunicação bem-sucedida;
- latência média;
- timeouts;
- número de reconexões;
- último erro;
- versão do backend;
- capabilities descobertas;
- Resource associado.

Credenciais, tokens e outros segredos nunca entram nessas métricas ou logs.

---

# 18. Configuração conceitual

Exemplo de configuração de um Hamlib Driver:

```json
{
  "driverId": "hamlib-radio-01",
  "type": "hamlib-rigctld",
  "resourceId": "radio-01",
  "host": "127.0.0.1",
  "port": 4532,
  "connectTimeoutMs": 3000,
  "commandTimeoutMs": 2000,
  "healthCheckIntervalMs": 5000,
  "autoReconnect": true
}
```

Esse exemplo representa configuração interna do Gateway e **não** faz parte do Vector Protocol público.

---

# 19. Múltiplos rádios

Um Vector Gateway deve poder executar múltiplas instâncias independentes de Drivers.

```text
Site Purunã

Vector Gateway
   |
   +-- radio-01 -> Hamlib Driver -> rigctld #1 -> Radio A
   +-- radio-02 -> Hamlib Driver -> rigctld #2 -> Radio B
   +-- radio-03 -> Hamlib Driver -> rigctld #3 -> Radio C
```

Falha em um Driver não deve derrubar os demais Resources do site.

---

# 20. Drivers de desenvolvimento e testes

Além do Hamlib Driver, o projeto deve prever:

## Dummy Driver

Aceita comandos e devolve respostas determinísticas sem hardware real.

## Simulator Driver

Simula comportamento, latência, mudanças espontâneas e falhas de um equipamento.

## Fault Injection Driver

Uso futuro para testar timeout, desconexão, respostas inválidas e recuperação.

Esses Drivers são importantes para CI, testes unitários e testes de integração sem necessidade de rádio físico.

---

# 21. Drivers futuros

A arquitetura poderá receber outros Drivers sem alterar Vector API ou Vector Protocol.

Possibilidades futuras incluem:

- acesso direto à biblioteca Hamlib;
- FlexRadio;
- Icom CI-V;
- Yaesu CAT;
- Kenwood CAT;
- OmniRig;
- rotores;
- amplificadores;
- antenna switches;
- controladores de energia;
- áudio remoto;
- sensores e automação de estação.

A inclusão de um Driver direto de fabricante deve ocorrer apenas quando houver benefício técnico claro em relação ao backend existente.

---

# 22. O que NÃO pertence a um Driver

Um Driver não deve implementar:

- login de usuários Vector;
- autorização de operadores;
- criação de Session;
- Lease de Resource;
- regras de negócio globais;
- API HTTP pública;
- Vector Protocol;
- interface de usuário;
- seleção de site;
- política global de auditoria.

Essas responsabilidades pertencem a outras camadas da plataforma.

---

# 23. Regra de compatibilidade

A primeira versão operacional do GADX Vector deve ser validada prioritariamente utilizando o **Hamlib Driver via rigctld**.

A compatibilidade do Vector com um rádio é determinada por três fatores:

1. o rádio ser controlável pelo backend configurado;
2. o Driver conseguir mapear as funções necessárias;
3. as capabilities necessárias ao caso de uso estarem disponíveis.

Não se deve declarar uma função suportada apenas porque ela existe conceitualmente no Vector.

---

# 24. Critérios mínimos de aceite do Hamlib Driver v1

O Driver será considerado apto para a primeira prova de conceito quando conseguir, através de `rigctld`:

- conectar e desconectar de forma controlada;
- detectar perda da conexão;
- reconectar automaticamente;
- ler frequência;
- alterar frequência;
- ler modo;
- alterar modo;
- ler PTT, quando disponível;
- ativar e desativar PTT;
- produzir snapshot inicial;
- detectar mudanças relevantes;
- traduzir erros para o modelo Vector;
- reportar health status;
- manter isolamento entre múltiplas instâncias.

A validação deverá incluir pelo menos um fluxo real:

```text
N1MM/DXLog
   -> Vector Client
   -> Vector Gateway
   -> Hamlib Driver
   -> rigctld
   -> rádio físico
```

---

# 25. Princípio final

> **O Vector não reinventa o controle de hardware quando já existe uma camada madura para fazê-lo. Ele abstrai, protege, coordena e automatiza essa capacidade.**

Na primeira versão, o Hamlib e o `rigctld` fornecem o controle técnico dos rádios. O GADX Vector fornece a camada acima: segurança, sessões, leases, multiestação, estado autoritativo, abstração, compatibilidade de clientes e automação.
