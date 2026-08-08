# GADX Vector
# 09 - Modelo de Recursos

Versão: 1.0 (Draft)  
Status: Em elaboração

---

# 1. Objetivo

Este documento detalha como equipamentos, dispositivos e serviços são representados como **Resources** no GADX Vector, complementando o `04-ModeloDeDominio.md`.

O Modelo de Domínio define as entidades e relações conceituais. Este documento define o contrato comum, propriedades, capabilities, dependências e especializações dos Resources.

> **Regra central:** todo equipamento ou serviço controlável ou monitorável pelo GADX Vector é representado por um Resource. O tipo informa o que ele é; as Capabilities informam o que ele efetivamente sabe fazer.

---

# 2. Hierarquia inicial

```text
Resource
├── Radio
├── Rotor
├── Amplifier
├── Antenna
├── AntennaSwitch
├── AudioDevice
├── Camera
├── Relay
├── Sensor
├── PowerController
└── ServiceResource
```

Novos tipos podem ser adicionados sem alterar o contrato base.

---

# 3. Contrato base de Resource

Todo Resource deve possuir, conceitualmente:

| Campo | Tipo conceitual | Obrigatório | Descrição |
|---|---|:---:|---|
| `id` | string | Sim | Identificador único e estável. |
| `type` | string | Sim | Tipo funcional do Resource. |
| `name` | string | Sim | Nome amigável. |
| `description` | string | Não | Descrição operacional. |
| `siteId` | string | Sim | Site ao qual pertence. |
| `driverId` | string | Condicional | Driver responsável pelo acesso. |
| `profileId` | string | Não | Resource Profile associado. |
| `manufacturer` | string | Não | Fabricante. |
| `model` | string | Não | Modelo. |
| `serialNumber` | string | Não | Número de série quando aplicável. |
| `firmware` | string | Não | Versão de firmware conhecida. |
| `state` | enum | Sim | Estado conforme máquina de Resource. |
| `health` | enum | Sim | Saúde operacional. |
| `capabilities` | collection | Sim | Funções efetivamente disponíveis. |
| `lease` | object/null | Sim | Lease de controle vigente, quando existir. |
| `tags` | collection | Não | Classificação livre. |
| `properties` | object | Sim | Estado/propriedades específicas. |
| `metadata` | object | Não | Metadados extensíveis não normativos. |

`metadata` não deve ser utilizado para contornar campos normativos ou contratos públicos.

---

# 4. Identidade

`resourceId` deve ser estável durante a vida lógica do Resource e não deve depender de endereço IP, porta serial ou posição física temporária.

Exemplos:

```text
radio-01
rotor-20m
amp-station-a
switch-main
weather-01
```

Alterar backend, porta ou Driver não deve obrigatoriamente alterar o `resourceId`.

---

# 5. Site e pertencimento

Todo Resource pertence a exatamente um Site operacional por vez.

```text
Site Purunã
├── radio-01
├── radio-02
├── rotor-20m
├── amp-01
└── weather-01
```

O Vector Gateway daquele Site é a autoridade local sobre o estado publicado desses Resources.

---

# 6. Estado e Health

O estado de Resource deve obedecer ao `06-MaquinaDeEstados.md`.

Estados base:

- `OFFLINE`
- `ONLINE`
- `AVAILABLE`
- `RESERVED`
- `IN_USE`
- `RELEASING`
- `FAULT`
- `MAINTENANCE`

Health é uma dimensão separada do estado e utiliza, inicialmente:

- `Healthy`
- `Warning`
- `Critical`
- `Offline`

Um Resource pode, por exemplo, estar `IN_USE` e possuir Health `Warning` se uma função secundária estiver degradada e a política permitir continuidade.

---

# 7. Capabilities

Capabilities são a fonte de verdade funcional.

O sistema nunca deve presumir que uma operação existe apenas porque `type`, fabricante ou modelo normalmente a suportam.

Uma Capability pode conter metadados como:

```json
{
  "name": "Frequency",
  "read": true,
  "write": true,
  "unit": "Hz",
  "min": 1800000,
  "max": 54000000
}
```

Resource Profiles podem sugerir capabilities esperadas, mas o Driver/Gateway deve publicar as efetivamente disponíveis.

---

# 8. Properties

Properties representam valores observáveis ou configuráveis.

Exemplos:

| Property | Tipo | Unidade | Acesso |
|---|---|---|---|
| `frequencyHz` | integer | Hz | R/W |
| `mode` | enum | — | R/W |
| `ptt` | boolean | — | R/W |
| `azimuthDeg` | number | graus | R/W |
| `temperatureC` | number | °C | R |

Quando aplicável, o sistema deve distinguir **Desired State** de **Observed State**.

---

# 9. Commands e Events

Commands representam intenção. Events representam fatos reconhecidos pelo Gateway.

Eventos comuns a Resources podem incluir:

- `StateChanged`
- `HealthChanged`
- `PropertyChanged`
- `ResourceAcquired`
- `ResourceReleased`
- `LeaseExpired`
- `ResourceOffline`
- `FaultRaised`
- `CapabilityChanged`

Os nomes normativos de mensagens pertencem ao Vector Protocol/API; este documento descreve sua relação com Resources.

---

# 10. Ownership e Lease

Resources que exigem controle exclusivo utilizam Lease conforme ADR-010.

Regras:

- no máximo um Lease exclusivo de controle por Resource;
- somente a Session proprietária pode emitir comandos mutáveis durante `IN_USE`;
- observadores read-only podem ser permitidos por política;
- expiração, revogação ou liberação executam a política de fail-safe apropriada;
- a duração do Lease é configurável e anunciada pelo Gateway.

Os defaults temporais normativos da versão do protocolo devem ser consultados no `05-Protocolo.md`.

---

# 11. Radio

Resource que representa transceptor ou receptor.

Properties típicas:

- `frequencyHz`
- `mode`
- `vfo`
- `split`
- `ptt`
- `powerW`
- `band`
- `filterWidthHz`

Capabilities possíveis:

- `Frequency`
- `Mode`
- `PTT`
- `Split`
- `VFO`
- `Power`
- `Filter`

Modos como USB, LSB, CW ou DIGI são valores de propriedade/capability, não estados base de Resource.

---

# 12. Rotor

Properties típicas:

- `azimuthDeg`
- `elevationDeg`
- `targetAzimuthDeg`
- `targetElevationDeg`
- `moving`
- `parkPosition`

Capabilities possíveis:

- `Azimuth`
- `Elevation`
- `Move`
- `Stop`
- `Park`
- `Preset`
- `Tracking`

---

# 13. Amplifier

Properties típicas:

- `operate`
- `standby`
- `band`
- `inputPowerW`
- `outputPowerW`
- `temperatureC`
- `swr`
- `fault`

Capabilities possíveis:

- `Operate`
- `Standby`
- `Band`
- `Power`
- `Temperature`
- `SWR`
- `Fault`

Amplifiers devem possuir políticas de interlock e fail-safe adequadas antes de controle remoto de TX.

---

# 14. Antenna

Representa uma antena como entidade operacional, mesmo quando ela não possui interface ativa própria.

Properties podem incluir:

- bandas suportadas;
- polarização;
- azimute atual/nominal;
- ganho nominal;
- limites operacionais;
- Resource Rotor associado.

Antenna pode ser um Resource passivo usado para modelar dependências e roteamento de RF.

---

# 15. AntennaSwitch

Properties típicas:

- `selectedPort`
- `ports`
- `locked`

Capabilities possíveis:

- `SelectPort`
- `ReadPort`
- `Lock`
- `Interlock`

Trocas de caminho de RF devem respeitar interlocks, especialmente durante PTT.

---

# 16. AudioDevice

Representa dispositivos ou serviços de áudio.

Properties possíveis:

- input/output selecionado;
- codec;
- sample rate;
- nível;
- mute;
- estado do stream.

O transporte de áudio não é definido por este documento.

---

# 17. Camera

Representa câmera ou serviço de vídeo associado ao Site.

Capabilities possíveis:

- `Stream`
- `Snapshot`
- `PTZ`
- `Preset`

Credenciais e URLs privadas de streams são configuração sensível e não devem ser publicadas como metadata aberta.

---

# 18. Relay

Representa um ou mais canais de relé controláveis.

Properties típicas:

- canais;
- estado por canal;
- modo momentâneo/latching;
- descrição da carga associada.

Relays que acionem cargas críticas devem possuir políticas específicas de autorização e fail-safe.

---

# 19. Sensor

Representa telemetria sem necessidade de controle mutável.

Exemplos:

- temperatura;
- umidade;
- vento;
- tensão;
- corrente;
- potência;
- SWR;
- presença/porta aberta.

Sensores normalmente não exigem Lease para leitura.

---

# 20. PowerController

Representa alimentação elétrica, PDU, UPS, fonte, bateria ou gerador controlável/monitorável.

Properties possíveis:

- `voltageV`
- `currentA`
- `powerW`
- `batteryPercent`
- `generatorState`
- `upsState`

Commands destrutivos ou de interrupção de energia devem exigir autorização elevada e confirmação apropriada.

---

# 21. ServiceResource

Permite representar serviços lógicos monitoráveis/controláveis quando fizer sentido no domínio.

Exemplos futuros:

- WebSDR;
- DX Cluster local;
- serviço de áudio;
- decoder;
- serviço de automação.

Um serviço só deve ser modelado como Resource quando se beneficiar de identidade, estado, health, capabilities ou política de acesso comuns aos demais Resources.

---

# 22. Dependencies

Resources podem declarar dependências explícitas.

Exemplo:

```text
Radio 1
├── Amplifier 1
├── AntennaSwitch 1
└── Rotor 1
        └── Antenna 20m
```

Dependências podem sustentar regras como:

- não trocar antena durante PTT;
- não permitir TX se amplificador estiver em Fault;
- não permitir duas estações no mesmo caminho de RF;
- impedir movimento além de limites mecânicos;
- selecionar banda do amplificador de forma coerente.

Dependência não implica automaticamente política: interlocks devem ser definidos explicitamente.

---

# 23. Resource Profile

Resource Profile descreve características conhecidas de um modelo sem incorporá-las ao núcleo.

Estrutura prevista:

```text
profiles/
└── radio/
    ├── kenwood/
    │   └── ts440.yaml
    ├── yaesu/
    │   └── ftdx10.yaml
    └── icom/
        └── ic7300.yaml
```

Um Profile pode conter:

- fabricante/modelo;
- capabilities esperadas;
- limites de frequência;
- modos;
- VFOs;
- potência;
- parâmetros de configuração;
- peculiaridades;
- bugs conhecidos;
- workarounds.

Profiles não devem sobrescrever silenciosamente a realidade observada pelo Driver.

---

# 24. Discovery

Ao inicializar ou reconectar, o Driver deve descobrir, quando possível:

- disponibilidade do equipamento;
- capabilities reais;
- estado inicial;
- versão do backend/firmware relevante.

O Gateway normaliza essas informações e publica o Resource ao Client.

Exemplo resumido:

```json
{
  "id": "radio-01",
  "type": "Radio",
  "state": "AVAILABLE",
  "health": "Healthy",
  "capabilities": ["Frequency", "Mode", "PTT", "Split"]
}
```

---

# 25. Segurança e informações sensíveis

Resource configuration pode conter informações sensíveis, mas o modelo público não deve expor:

- senhas;
- tokens;
- chaves privadas;
- secrets de API;
- credenciais de câmera;
- credenciais de backend.

Referências a secrets devem utilizar mecanismo seguro de configuração da implementação.

---

# 26. Extensibilidade

Adicionar um novo Resource Type não deve exigir alteração estrutural em Client, Protocol ou API quando puder ser representado pelo contrato comum de Resource + Capabilities + Properties + Commands/Events.

Mudanças que alterem contratos públicos ou semântica global devem gerar ADR.

---

# 27. Regra final

> **O tipo descreve o Resource. As Capabilities descrevem o que ele pode fazer. O Driver observa o equipamento. O Gateway publica o estado autoritativo.**

Essa regra deve orientar a implementação de todos os Resources do GADX Vector.