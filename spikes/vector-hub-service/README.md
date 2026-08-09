# GADX Vector — Vector Hub Runtime / Service / Installer SPIKE

## Status

**ACTIVE / SPIKE 02**

Este SPIKE sucede `../cat-ts2000/`, que foi congelado apos validar a viabilidade da fachada TS-2000, CAT multi-client e keying low-latency.

A pergunta agora e diferente:

> Conseguimos transformar a arquitetura CAT + keying ja validada em um componente persistente, configuravel, reparavel e instalavel do GADX Vector no Windows?

## Escopo

Este SPIKE deve construir a proxima geracao do runtime sem reabrir problemas ja resolvidos no SPIKE anterior.

O foco e:

- promover a multi-bridge validada para um `Vector Hub` com nomenclatura propria;
- usar um unico arquivo de configuracao do sistema;
- executar como Windows Service de forma nativa para a configuracao multi-client;
- manter fail-safe coerente com o novo INI;
- provisionar/reutilizar multiplos pares com0com;
- usar runtime Python privado;
- automatizar install / repair / reinstall;
- limitar logs;
- sobreviver a reboot;
- preservar configuracao existente durante reparo;
- preparar a base para adicionar/remover clientes posteriormente.

## Fora de escopo por enquanto

Nao vamos reescrever o protocolo TS-2000 nem substituir a estrategia de keying que ja funcionou.

Tambem nao vamos, nesta primeira etapa, resolver adapters nativos de MMTTY, UI completa do Vector Client, arbitragem sofisticada entre writers CAT ou suporte completo a todo o protocolo TS-2000.

Esses assuntos so entram quando interferirem diretamente nos criterios de aceite deste SPIKE.

## Arquitetura-alvo

```text
                            GADX VECTOR HUB

 CAT clients                                      Keying clients
 COM101 -- TS2000 adapter --\                    COM102 --\
 COM103 -- TS2000 adapter ---+-- shared rig -->  COM104 ---+-- logical states
 COM105 -- TS2000 adapter ---+   rigctld         COM106 --/        |
 COM107 -- TS2000 adapter --/                                  physical COM
                                                                  |
                                                               PTT / CW
```

Cada software continua tendo sua propria COM virtual. O Hub nao tenta fazer dois processos abrirem a mesma COM.

## Nomenclatura nova

No novo SPIKE, a aplicacao principal passa a se chamar:

```text
app/vector_hub.py
```

O arquivo de configuracao passa a ser:

```text
config/vector.ini
```

A expressao `bridge` fica reservada aos artefatos historicos do SPIKE 01.

## Estrutura planejada

```text
spikes/vector-hub-service/
├── README.md
├── app/
│   ├── vector_hub.py
│   └── ts2000.py
├── config/
│   └── vector.ini
├── service/
│   └── vector_service.py
├── installer/
│   └── ...
└── tests/
    └── ...
```

## Configuracao

A configuracao do sistema sera organizada por responsabilidade:

```ini
[cat]
ports = COM101, COM103
baud = 19200

[keying]
client1 = COM102,DTR,RTS
client2 = COM104,DTR,NONE

[radio_keying]
port = COM4
baud = 19200
ptt_line = RTS
cw_line = DTR

[rig]
host = 127.0.0.1
port = 4532
poll_ms = 250

[service]
startup = delayed-auto
recovery = restart

[logging]
level = INFO
max_mb = 5
backups = 5
```

O runtime deve ler apenas o que lhe pertence. O wrapper de servico deve ser responsavel por `service` e `logging`, evitando misturar configuracao operacional com politica de supervisao.

## Politica de portas COM

A convencao futura e:

```text
lado apresentado aos aplicativos: tentar COM15, COM16, COM17... em ordem crescente
lado interno do Vector:          tentar COM101, COM102, COM103... em ordem crescente
```

COM15 e apenas o primeiro candidato. O provisionador deve consultar portas ocupadas e nunca sobrescrever uma COM existente.

Exemplo de alocacao:

```text
COM15 <-> COM101   CAT #1
COM16 <-> COM102   Keying #1
COM17 <-> COM103   CAT #2
COM18 <-> COM104   Keying #2
COM19 <-> COM105   CAT #3
COM20 <-> COM106   Keying #3
```

## Principios herdados do SPIKE 01

1. Uma COM virtual por cliente.
2. TS-2000 e fachada; o radio fisico fica atras do Hamlib/rigctld.
3. CAT e keying sao canais independentes.
4. RTS/DTR pertencem ao INI da instalacao, nao ao modelo de radio no codigo.
5. CW e tempo-critico e fica fora de polling/chamadas bloqueantes do rigctld.
6. Estados multi-client de PTT/CW sao mantidos por fonte e consolidados logicamente.
7. COMs altas sao internas; COMs baixas sao apresentadas aos softwares sempre que possivel.
8. Fail-safe tem prioridade: parar, falhar ou reiniciar nao pode deixar PTT/CW acionados.

## Criterios de aceite

O SPIKE 02 sera considerado validado quando todos estes itens forem demonstrados em uma instalacao limpa e depois repetidos em pelo menos outra estacao:

- [ ] runtime instalado em `C:\Ham\GADX-Vector`;
- [ ] Python privado instalado e versionado pelo Vector;
- [ ] com0com instalado ou detectado;
- [ ] provisionamento automatico com preferencia COM15+ no lado dos aplicativos;
- [ ] namespace interno COM101+;
- [ ] N clientes CAT configuraveis;
- [ ] N clientes keying configuraveis;
- [ ] Windows Service inicia automaticamente apos reboot;
- [ ] recovery/restart do servico funciona;
- [ ] logs possuem limite de tamanho e backups;
- [ ] stop/restart/crash nao deixa PTT ou CW acionados;
- [ ] repair/reinstall preserva configuracao quando apropriado;
- [ ] N1MM continua funcionando;
- [ ] LogHX continua funcionando;
- [ ] MMTTY continua funcionando no desenho generico;
- [ ] CW permanece limpo em velocidade de contest;
- [ ] PTT funciona com mapeamentos diferentes de RTS/DTR;
- [ ] dois ou mais clientes CAT funcionam simultaneamente;
- [ ] documentacao de instalacao e diagnostico reflete o comportamento real.

## Fases de construcao

### Fase A — Runtime

Copiar a base multi-client validada para este SPIKE, renomear para `vector_hub.py`, ajustar leitura de `vector.ini` e criar testes de regressao basicos sem alterar o caminho low-latency.

### Fase B — Service

Criar `vector_service.py` que:

- inicia `vector_hub.py`;
- entende `vector.ini`;
- aplica fail-safe usando `[radio_keying]` e `[rig]`;
- gira logs segundo `[logging]`;
- encerra o filho de forma previsivel;
- funciona com runtime Python privado.

### Fase C — Provisionamento

Criar camada idempotente para:

- detectar com0com;
- ler ComDB/busynames;
- encontrar portas livres;
- criar/reutilizar N pares;
- preservar mapeamentos existentes durante repair;
- documentar o dono de cada COM no INI/summary.

### Fase D — Installer

Construir nova geracao do instalador usando as licoes do `cat-ts2000/installer/production`, mas gerando a arquitetura multi-client e a politica COM15+/COM101+.

### Fase E — Regressao de bancada

Repetir os cenarios reais antes de considerar o SPIKE encerrado.

## Baseline de codigo

A referencia funcional inicial e:

```text
../cat-ts2000/rigctld_bridge_multi.py
../cat-ts2000/ts2000.py
```

Esses arquivos foram congelados. O desenvolvimento novo deve ocorrer neste diretorio para manter a referencia validada intacta.

## Decisoes que exigem teste, nao suposicao

- comportamento quando dois clientes escrevem CAT simultaneamente;
- reconexao apos queda/reinicio de `rigctld`;
- politica para adicionar/remover pares depois da instalacao;
- tratamento de COM fisica ausente no boot;
- comportamento de service recovery quando portas ainda nao estao enumeradas;
- split/VFO A/VFO B multi-client;
- eventual PTT via comandos CAT no mesmo OR das fontes de keying.

Esses itens devem ser promovidos a requisito somente depois de teste de bancada.
