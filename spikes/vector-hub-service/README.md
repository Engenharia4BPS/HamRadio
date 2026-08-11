# GADX Vector — Vector Hub Runtime / Service / Installer SPIKE

## Status

**ACTIVE / SPIKE 02**

Este SPIKE sucede `../cat-ts2000/`, congelado apos validar a fachada TS-2000, CAT multi-client e keying low-latency.

Estado atual:

- **Fase A — Runtime: VALIDADA em bancada**;
- **Fase B — Windows Service: VALIDADA funcionalmente em bancada**;
- **Fase C — Provisionamento visual: EM DESENVOLVIMENTO**.

A pergunta atual e:

> Conseguimos transformar a arquitetura CAT + keying ja validada em um componente persistente, configuravel, reparavel e instalavel do GADX Vector no Windows?

## Estrutura atual

```text
spikes/vector-hub-service/
├── README.md
├── app/
│   ├── vector_hub.py
│   └── ts2000.py
├── config/
│   └── vector.ini
├── service/
│   ├── vector_service.py
│   ├── install-service.ps1
│   └── uninstall-service.ps1
└── tools/
    ├── port_manager.py
    └── README.md
```

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

Cada software possui sua propria COM virtual. O Hub nao tenta fazer dois processos abrirem a mesma COM.

## Configuracao

O arquivo principal e `config/vector.ini`, organizado por responsabilidade:

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

[runtime]
allow_write = true
allow_ptt = true
allow_cw = true

[service]
startup = delayed-auto
recovery = restart

[logging]
level = INFO
max_mb = 5
backups = 5

[ports]
application_start = 15
vector_start = 101
```

## Politica de portas COM

Convencao desejada:

```text
lado apresentado aos aplicativos: tentar COM15, COM16, COM17... em ordem crescente
lado interno do Vector:           tentar COM101, COM102, COM103... em ordem crescente
```

COM15 e apenas o primeiro candidato. Portas existentes/ocupadas nunca devem ser sobrescritas silenciosamente.

## Principios consolidados

1. Uma COM virtual por cliente.
2. TS-2000 e fachada; o radio fisico fica atras do Hamlib/rigctld.
3. CAT e keying sao canais independentes.
4. RTS/DTR pertencem ao INI da instalacao, nao ao modelo de radio no codigo.
5. CW e tempo-critico e fica fora de polling/chamadas bloqueantes do rigctld.
6. Estados multi-client de PTT/CW sao mantidos por fonte e consolidados logicamente.
7. COMs altas sao internas; COMs baixas sao apresentadas aos softwares sempre que possivel.
8. Fail-safe tem prioridade: parar, falhar ou reiniciar nao pode deixar PTT/CW acionados.
9. ComDB sozinho nao define disponibilidade: o provisionador deve cruzar pares com0com, portas ativas e reservas.
10. O operador deve conseguir ver e aprovar o plano antes da criacao/remocao de COMs.

## Fase A — Runtime

`app/vector_hub.py` e a evolucao da multi-bridge congelada. Ja foi validado manualmente e depois executado pelo servico, preservando CAT, PTT e CW da bancada.

## Fase B — Windows Service

`service/vector_service.py` executa o Hub, usa `vector.ini`, aplica fail-safe, gira logs e funciona com Python privado ou fallback de bancada durante o SPIKE.

Servico:

```text
GADXVectorHub
Automatic (Delayed Start)
Recovery: restart on failure
```

## Fase C — Vector Port Manager

A Fase C passa a ter uma interface visual Tkinter em:

```text
tools/port_manager.py
```

Objetivo da primeira versao:

- inventariar portas ativas;
- localizar a instalacao correta do com0com;
- executar `setupc.exe` com o diretorio de trabalho correto;
- ler `list` e `busynames *`;
- mostrar os pares existentes;
- sugerir 4 pares por padrao;
- permitir aumentar/reduzir a quantidade;
- permitir definir Cliente, Tipo, COM do aplicativo e COM interna;
- mostrar um resumo antes de aplicar;
- criar/remover pares sem forcar conflitos silenciosamente.

A v0.1 **nao reutiliza automaticamente reservas ComDB orfas**. Primeiro queremos validar o fluxo visual e a mecanica segura de `list/create/remove`.

A proxima evolucao da Fase C deve:

- classificar FREE / ACTIVE_PHYSICAL / ACTIVE_COM0COM / RESERVED_COMDB / ORPHAN_RESERVATION / CONFLICT;
- gerar/atualizar `vector.ini`;
- persistir owners/mapeamentos em `ports.json` ou estrutura equivalente;
- permitir PTT/CW por cliente KEYING;
- opcionalmente parar/reiniciar `GADXVectorHub` ao aplicar mudancas.

## Criterios de aceite do SPIKE 02

- [x] runtime multi-client executado em bancada;
- [x] Windows Service inicia o Hub e mantem CAT/keying funcionais;
- [x] logs limitados por configuracao de servico;
- [x] mapeamento PTT via RIGCTLD + CW serial validado em bancada;
- [x] dois ou mais clientes CAT funcionam simultaneamente em bancada;
- [ ] runtime instalado por instalador limpo em `C:\Ham\GADX-Vector`;
- [ ] Python privado provisionado automaticamente;
- [ ] com0com instalado/detectado automaticamente;
- [ ] provisionamento automatico/visual com preferencia COM15+;
- [ ] namespace interno COM101+ criado automaticamente;
- [ ] N clientes CAT/keying configurados pelo Port Manager;
- [ ] reboot completo com servico retomando sozinho validado;
- [ ] repair/reinstall preservando configuracao;
- [ ] Port Manager gera configuracao persistente do Hub;
- [ ] documentacao final de instalacao/diagnostico.

## Fase D — Installer

Somente depois da Fase C provar o provisionamento, construiremos a nova geracao do instalador usando as licoes do instalador antigo.

## Fase E — Regressao

Repetir os cenarios reais em mais de uma estacao antes de encerrar o SPIKE.

## Decisoes que ainda exigem teste

- conflitos de escrita CAT simultanea;
- reconexao depois de queda/reinicio do `rigctld`;
- classificacao segura de reservas ComDB orfas;
- comportamento de service recovery quando COMs ainda nao enumeraram no boot;
- split/VFO A/B multi-client;
- eventual PTT por comando CAT no mesmo OR das fontes de keying.
